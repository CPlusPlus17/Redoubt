# Autoconfig on Android — spike result

**Task: LW-M3-08. Owner of this file and of
`patches/android/autoconfig-resource-fallback.patch`.**

> **LANDED BY LW-M3-02 (2026-08-18).** The patch is in
> `assets/patches/android.txt`, its `xmas-common` ordering constraint is a
> declared row in `scripts/check-patch-order.py`, and the "Pending" section of
> `docs/android/PATCH-SCOPE.md` is empty again. Both `check-patchfail` runs now
> *apply* the patch instead of passing vacuously with respect to it. §8 below is
> the list of what was owed, annotated with what landed; §8.1 is the gate status
> as the **spike** left the tree and is kept as a record, not as current state.
> LW-M3-02 re-proved the channel end to end on its own build — including one
> finding the spike could not have had, because the spike ran a hand-composed
> `.cfg`: **`privacy.resistFingerprinting=true` arrives with the `.cfg` and makes
> `scripts/android-smoke.sh`'s `webgl` check fail.** See §13.

---

## Verdict

**YES. `settings/librewolf.cfg` can be evaluated natively on Android, and
`lockPref` really locks.** Both are demonstrated below from a running build on
an emulator, not from source reading.

What that buys, concretely:

* Android evaluates **the same `.cfg` file** desktop does — no compiler, no
  derivative artifact, no second grammar to keep in step.
* `lockPref` calls `Preferences::Lock` exactly as on desktop, so the 38
  `lockPref`s in `common.cfg` become real locks instead of advisory comments.
* The 24 bare `pref()` calls in `common.cfg` keep their **user-branch**
  semantics (`prefcalls.js:12-18`) rather than being silently promoted to
  defaults. Measured: 16 of the 25 bare `pref()` calls in the tested
  composition (24 from `common.cfg`, plus the one spike sentinel) are sitting in
  the running profile's `prefs.js` as `user_pref`; the other 9 are accounted for
  in §6.
* Landmine **L2 is defeated for anything we lock** — and only for what we lock.
  See the precedence table; the counter-example is measured too.

What it does **not** buy, and the sting is new (§6): a bare `pref()` is *not*
safe on Android for any pref GeckoView declares, because
`GeckoView:ResetUserPrefs` `clearUserPref()`s all ~101 of them ~25 ms after
autoconfig runs. That is a **third** L2 channel, and `docs/android/AGENTS.md`
currently documents only two.

The cost is one C++ patch (three hunks, ~30 lines) and two lines in the Android
packaging manifest.

---

## 1. The starting measurement

`~/lw-m2-04/out/apk/fenix-x86_64-debug.apk`, the APK LW-M2-04 shipped, contains
`assets/omni.ja`, and inside it:

```
     7221  defaults/autoconfig/prefcalls.js          <- present
      359  chrome/en-US/locale/en-US/autoconfig/autoconfig.properties
```

`librewolf.cfg`, `defaults/pref/local-settings.js` and
`distribution/policies.json` are **absent**. Half the autoconfig machinery
already shipped and had never been exercised: with no `local-settings.js` there
is no `general.config.filename`, and `Preferences.cpp:3931-3939` only creates the
`pref-config-startup` category — i.e. only instantiates `nsReadConfig` at all —
when that pref has a value. So on Android, before this spike, `nsReadConfig` had
literally never run.

---

## 2. The trace — two corrections to what the board says

The board's trace is right about the shape and **wrong in two places that both
matter**. Both corrections came out of executions, not re-reading.

### 2.1 `NS_GRE_DIR` does not fail on Android. It answers the wrong directory.

`docs/android/AGENTS.md`, `docs/android/tasks.yaml` and `settings/common.cfg`
all say `NS_GetSpecialDirectory(NS_GRE_DIR)` "returns nothing" on Android,
citing the `#if !defined(MOZ_WIDGET_ANDROID)` guard in
`toolkit/xre/nsXREDirProvider.cpp` (~:392-397). The guard is real; the
conclusion does not follow. `nsXREDirProvider` only *declines*, and
`nsDirectoryService` then answers from its own built-in table:

```cpp
// xpcom/io/nsDirectoryService.cpp:334-338
// Unless otherwise set, the core pieces of the GRE exist
// in the current process directory.
else if (inAtom == nsGkAtoms::DirectoryService_GRE_Directory ||
         inAtom == nsGkAtoms::DirectoryService_GRE_BinDirectory) {
  rv = GetCurrentProcessDirectory(getter_AddRefs(localFile));
}
```

Measured with a temporary probe compiled into `nsReadConfig.cpp` and read out of
`logcat`:

```
D/MCD PROBE NS_GRE_DIR rv=0x0
      path=/data/app/~~7pbGnCQj7-VV7gRMcnK40A==/org.mozilla.fenix.debug-GpYkftUFChX-3oM0Koi7_Q==/lib/x86_64
```

`rv=0x0` is `NS_OK`. The path is the APK's extracted **native-library**
directory: `.so` files only, not writable by the app, nothing we can package
into.

This was caught before the probe existed, by the error code alone. The
*unpatched* binary reported

```
D/MCD error evaluating .cfg file librewolf.cfg 80520012
```

and `0x80520012` is `NS_ERROR_FILE_NOT_FOUND` (`xpcom/base/ErrorList.py`,
`FILES` module 13, code 18) — which in the unpatched function can only come out
of `NS_NewLocalFileInputStream`, i.e. *after* `NS_GetSpecialDirectory` and
`AppendNative` both succeeded. Had the directory service declined, the code
would have been `NS_ERROR_FAILURE` (`0x80004005`).

**Consequence: the obvious patch is dead code.** The first version of
`patches/android/autoconfig-resource-fallback.patch` fell back to `resource:`
when `NS_FAILED(NS_GetSpecialDirectory(NS_GRE_DIR))`. It compiled, it shipped,
and it never executed a single one of its added lines. That was only visible
because the added `MOZ_LOG` lines did not appear in `logcat`. The patch now
keys off the target (`#if defined(MOZ_WIDGET_ANDROID)`), not off a runtime
failure that never happens.

Note this also means a `.cfg` dropped into the app's data directory does
**not** get picked up — tried it, `/data/user/0/org.mozilla.fenix.debug/librewolf.cfg`
was ignored, because `GRE_HOME` (`GeckoLoader.java:219`, the app data dir) is
*not* what the directory service returns; `SetCurrentProcessDirectory` has
already been given the lib dir by then.

### 2.2 `FINAL_TARGET_FILES` at the package root is dropped on the floor

LW-M1-09 verified `lw/moz.build`'s `FINAL_TARGET_FILES` install into `dist/bin`
on any target. They do:

```
obj-x86_64/dist/bin/librewolf.cfg -> /work/src/lw/librewolf.cfg
obj-x86_64/dist/bin/defaults/pref/local-settings.js -> /work/src/lw/local-settings.js
```

But `resource://gre/` maps to the **GRE omnijar**, so the `.cfg` has to be
*inside* `omni.ja`, and membership is decided by
`OmniJarSubFormatter.is_resource` (`python/mozbuild/mozpack/packager/formats.py:322-356`).
A top-level `librewolf.cfg` matches none of its branches, so it is packaged
**flat**, into `dist/geckoview/` — and `mobile/android/geckoview/build.gradle:118-121`
copies only `dist/geckoview/assets` (that is, `omni.ja`) and `dist/geckoview/lib`
into the AAR. Anything flat is silently dropped. `dist/geckoview/` really does
contain `application.ini`, `platform.ini`, `precomplete` and `removed-files`
that never reach the APK.

`defaults/...` *does* match `is_resource` (`:340-343`), so the fix is to install
and package the `.cfg` as `defaults/autoconfig/librewolf.cfg`, beside
`prefcalls.js`, and read it as
`resource://gre/defaults/autoconfig/librewolf.cfg`.

---

## 3. The change

`patches/android/autoconfig-resource-fallback.patch`, three hunks:

| file | what |
|---|---|
| `extensions/pref/autoconfig/src/nsReadConfig.cpp` | on Android, always take the `resource:` branch in `openAndEvaluateJSFile`; keep one `MOZ_LOG` of the outcome |
| `lw/moz.build` | also install `librewolf.cfg` into `FINAL_TARGET_FILES.defaults.autoconfig` |
| `mobile/android/installer/package-manifest.in` | name `defaults/pref/local-settings.js` and `defaults/autoconfig/librewolf.cfg` in the `MOZ_PREF_EXTENSIONS` block |

Two properties of the C++ hunk are load-bearing and are the reason it is a
separate `fromResourceURI` flag rather than "pass `isBinDir=false`":

1. **`isBinDir` is not flipped.** The last argument of
   `EvaluateAdminConfigScript` is `!isBinDir`, i.e. `isPrivileged`. LibreWolf
   sets `general.config.sandbox_enabled=true` in `local-settings.js`, so an
   `isBinDir` file runs in the **unprivileged NullPrincipal sandbox** and sees
   only the functions `prefcalls.js` exported into `gSandbox`. Reaching the
   `resource:` branch by passing `isBinDir=false` would have silently promoted
   the admin `.cfg` to the system-principal sandbox — a privilege escalation
   dressed as a one-character simplification. `skipFirstLine` rides on a
   *different* argument (`isEncoded`) and is likewise untouched. **This section
   was right and the patch's own comment was wrong**: it claimed `isBinDir`
   "still decides `skipFirstLine`". It does not — the call is
   `EvaluateAdminConfigScript(buf, amt, aFileName, false, true, isEncoded,
   !isBinDir)` and the signature (`nsJSConfigTriggers.h:11-14`) is
   `(…, bGlobalContext, bCallbacks, skipFirstLine, isPrivileged)`, so `isBinDir`
   reaches `isPrivileged` only. LW-M3-02 fixed both the patch header and the C++
   comment that would have landed in the Gecko tree.
2. **Everything is inside `#if defined(MOZ_WIDGET_ANDROID)`.** Off Android,
   `fromResourceURI == !isBinDir` and the generated code is upstream's. The
   patch cannot change desktop behaviour, which is why it belongs in
   `android.txt` and not in `common.txt`.

`MOZ_WIDGET_GTK` and `MOZ_WIDGET_ANDROID` are mutually exclusive, so the
`NS_OS_SYSTEM_CONFIG_DIR` block that desktop Linux uses is untouched and
unreachable on Android.

---

## 4. Proof 1 — a pref set only by `librewolf.cfg` is live on a fresh profile

The `.cfg` used was `settings/common.cfg` + `settings/android.cfg` concatenated
(common first, so its sacrificial `null;` line 1 is the one
`skipFirstLine` eats), plus a spike block appending three sentinels that exist
nowhere else in the tree:

```js
pref       ("librewolf.m3_08.bare_pref",    "USER-BRANCH-OK");
defaultPref("librewolf.m3_08.default_pref", "DEFAULT-BRANCH-OK");
lockPref   ("librewolf.m3_08.locked_pref",  "LOCKED-OK");
```

Fresh install, fresh profile (`adb uninstall` then `adb install`), API 30
x86_64 emulator. `logcat` with `MOZ_LOG=MCD:5` supplied through
`/data/local/tmp/org.mozilla.fenix.debug-geckoview-config.yaml`:

```
D/MCD general.config.filename = librewolf.cfg
D/MCD opened resource://gre/defaults/autoconfig/prefcalls.js: 0x0
D/MCD evaluating .cfg file librewolf.cfg with obscureValue 0
D/MCD opened resource://gre/defaults/autoconfig/librewolf.cfg: 0x0
```

No `error evaluating .cfg file` line, and no
`"Autoconfig is sandboxed by default…"` console warning — `nsReadConfig::Observe`
emits that one on *every* failure when the sandbox is on, and its absence is a
second, independent success signal.

`about:config` in the running app, filtered to `librewolf.m3_08`, shows all
three, with the **padlock** on the locked one
(`config.js:620-621` renders it from `Services.prefs.prefIsLocked`) and a
**Reset** button on the bare one (`config.js:616-617`, i.e. it has a user
value):

```
librewolf.m3_08.bare_pref       USER-BRANCH-OK       [Reset]
librewolf.m3_08.default_pref    DEFAULT-BRANCH-OK
librewolf.m3_08.locked_pref     LOCKED-OK            🔒
```

And the profile's own `prefs.js`, read back through `run-as`:

```
$ adb shell 'run-as org.mozilla.fenix.debug sh -c "cat files/mozilla/*.default/prefs.js"'
...
user_pref("librewolf.m3_08.bare_pref", "USER-BRANCH-OK");
```

That last line is the proof that bare `pref()` still means **user branch** on
Android, not "default". Across the whole file, 16 of the 25 bare `pref()` calls
(24 from `common.cfg` plus the sentinel) are persisted as `user_pref`. The other
9 are either equal to the default, so `Pref::SetUserValue` drops them
(`Preferences.cpp:913-919`), or were wiped — see §6.

---

## 5. Proof 2 — a `lockPref` survives the Fenix settings screen, the unlocked control does not

Both arms in **one build, one profile, one session**, so the lock is the only
difference between them.

* **Locked arm** — `devtools.debugger.remote-enabled`. One of the 21 prefs
  `board.py --check-policies` reports as GeckoView-declared
  (`GeckoRuntimeSettings.java:748`, `mRemoteDebugging`). `common.cfg:561` sets
  it with a bare `pref()`; the spike block re-declares it as
  `lockPref("devtools.debugger.remote-enabled", false)`.
* **Unlocked control** — `privacy.globalprivacycontrol.enabled`
  (`GeckoRuntimeSettings.java:812`), left exactly as `common.cfg:304` has it:
  `defaultPref(..., true)`.

| | before | action | after |
|---|---|---|---|
| `devtools.debugger.remote-enabled` (**locked**) | `false` 🔒 | Settings → Advanced → **Remote debugging via USB** toggled ON | **`false` 🔒** |
| `privacy.globalprivacycontrol.enabled` (unlocked) | `true` | Settings → Enhanced Tracking Protection → **Tell websites not to share & sell data** toggled ON then OFF | **`false`** |

Each toggle produced `D/GeckoViewStartup: onEvent GeckoView:SetDefaultPrefs` in
`logcat`, so the runtime write really did reach Gecko in both cases —
`GeckoViewStartup.sys.mjs:400-402` writes it through
`Services.prefs.getDefaultBranch("")`. The lock holds because
`Pref::SetDefaultValue` is a no-op on a locked pref:

```cpp
// modules/libpref/Preferences.cpp:884-885
// Should we set the default value? Only if the pref is not locked, and
// doing so would change the default value.
if (!IsLocked()) {
```

and reads of a locked pref return the default regardless of any user value
(`WantValueKind`, `:1265`).

Then the app was force-stopped and restarted, with Fenix's own SharedPreference
now saying remote debugging is *enabled* — so `MOZ_DEFAULT_PREFS` carried
`devtools.debugger.remote-enabled=true` into the next startup:

* `devtools.debugger.remote-enabled` → still **`false`**, still locked.
* `privacy.globalprivacycontrol.enabled` → back to **`true`**, because
  autoconfig runs after `MOZ_DEFAULT_PREFS`… and will be clobbered again the
  next time anybody opens that settings screen.

That last pair is the whole of landmine L2 in two lines: **`defaultPref` wins
the startup race and loses every race after it. `lockPref` wins both.**

Screenshots and raw `logcat` for all of the above are in the spike's scratch
directory; they are evidence, not deliverables, and are not committed.

---

## 6. The measured pref precedence on Android

Timestamps are from one real startup, same millisecond clock, `MOZ_LOG=MCD:5`
plus `GeckoViewStartup`'s own debug lines.

| # | channel | when | what it writes | beaten by |
|---|---|---|---|---|
| 1 | `greprefs.js`, `defaults/pref/*.js` from `omni.ja` (`Preferences::InitInitialObjects`, `:5189-5191`) | first pref-service use | default branch | 2,3,4,6 |
| 2 | `MOZ_DEFAULT_PREFS` env (`GeckoLoader` ← `settings.getPrefsMap()`, all ~101 GeckoView prefs) | `Preferences.cpp:3962-3965`, still inside `GetInstanceForService` | default branch | 3,4,6 |
| 3 | profile `prefs.js` (`InitializeUserPrefs`) | `nsAppRunner.cpp:5992` | user branch | 4 (for the same pref), 5 |
| 4 | **autoconfig — our `.cfg`** | `nsAppRunner.cpp:6008` → `NS_PREFSERVICE_READ` — `14:17:39.531` | user branch (`pref`), default branch (`defaultPref`), default+**lock** (`lockPref`) | 5 and 6, **unless locked** |
| 5 | `GeckoView:ResetUserPrefs` — `clearUserPref()` × ~101 | `GeckoRuntimeSettings.attachTo` → `commitResetPrefs` — `14:17:39.556` | clears the **user** branch | — (nothing restores it until next startup) |
| 6 | `GeckoView:SetDefaultPrefs` — `Pref.commit()` | every settings change, and any engine-settings assignment whose Java value changes | default branch | — |

**Channel 5 is new and is not in `docs/android/AGENTS.md`.** It fires
unconditionally at every startup, 25 ms after autoconfig, and it is why bare
`pref()` is unsafe on Android for a GeckoView-declared pref. Measured
counter-example, from the same running build:

* `common.cfg:117` is `pref("browser.contentblocking.category", "strict")`.
* `about:config` after startup reads **`standard`**.
* `browser.contentblocking.category` is declared at `ContentBlocking.java:579`,
  so it is in the reset list.

Three of our bare `pref()` calls are GeckoView-declared and therefore in this
trap today: `browser.contentblocking.category`, `devtools.console.stdout.chrome`,
`devtools.debugger.remote-enabled`. All three carry an `[ANDROID: LOCK]` marker
already — `board.py --check-policies` was right about *which* prefs, for a
reason nobody had measured.

One more thing channel 6 does that is worth knowing: `Pref.commit(v)` returns
early when `v.equals(mValue)` on the Java side
(`RuntimeSettings.java:100-106`), so most of `GeckoEngine.kt`'s ~70
`this.<setting> = defaultSettings.<setting>` assignments at engine construction
dispatch nothing. The runtime write happens when the **Java** value changes —
which is exactly "the user touched a settings screen".

---

## 7. What this means for the rest of M3

* **LW-M3-02 (write a cfg compiler) largely collapses.** There is nothing to
  compile. What remains is the trivial composition step — Android's
  `librewolf.cfg` is `common.cfg + android.cfg`, concatenated in that order,
  the same way `librewolf.cfg` is `common.cfg + desktop.cfg` today, and
  `board.py --check-cfg-split` already knows how to verify a concatenation byte
  for byte. That is a `scripts/librewolf-patches.py` change plus a gate, not a
  compiler.
  **STATUS: LW-M3-02 landed the patch and the lists; it did NOT do the
  composition, and does not own `scripts/librewolf-patches.py`.** The board's
  rewritten LW-M3-02 brief has four items and composition is not one of them, so
  the sentence above is the only place it is tracked and it is tracked against a
  task that has closed. **Today an `--targets=android` run copies
  `settings/librewolf.cfg`, i.e. `common + desktop`, into `lw/`** —
  `scripts/librewolf-patches.py`'s `cp` of the composed desktop file is
  unconditional. LW-M3-02 verified this is what a real Android build ships and
  what its end-to-end proof ran against: `privacy.resistFingerprinting.letterboxing`
  (`settings/desktop.cfg:146`, and nowhere else) was observed live in the running
  Android app. Nothing breaks — `desktop.cfg` is 539 lines of nothing but
  `pref`/`defaultPref`/`lockPref`/`clearPref` calls, verified mechanically, so
  there is no statement in it that can throw and abort evaluation — but Android
  is getting desktop prefs and not getting `android.cfg` at all. **This needs a
  board task with `owns: [scripts/librewolf-patches.py]`.**
* **LW-M3-03 (wire `MOZ_DEFAULT_PREFS`) collapses to nothing** for the prefs in
  the `.cfg`. `MOZ_DEFAULT_PREFS` is still there as channel 2 and still cannot
  express a lock; it simply stops being our delivery mechanism.
* **LW-M3-04 (the must-lock list) becomes more important, not less**, and its
  input set grows: it must cover bare `pref()` calls too, because of channel 5.
  Its output is now directly actionable — a marker in `common.cfg` turns into a
  `lockPref` in the file we actually ship.
* **`distribution/policies.json` is still not packaged** (it is not under
  `defaults/`, so `is_resource` rejects it and it goes flat). LW-M3-06 needs the
  same treatment or a different answer; this spike did not touch it.
* Landmine **L2's prescribed mitigation is available again**, and the paragraph
  in `docs/android/AGENTS.md` saying it is not needs rewriting — along with the
  `NS_GRE_DIR` claim in §2.1 and the missing channel in §6.

---

## 8. What would need to land, and the ownership questions

This spike deliberately stopped short of landing. Four things were owed.
**LW-M3-02 landed items 1–3 and decided item 4**; each is annotated below.

1. **`patches/android/autoconfig-resource-fallback.patch`** — written, applies
   at `--fuzz=0`, builds, runs. Owned by this task; ready.
   **LANDED unchanged in substance.** LW-M3-02 edited only comments (the
   `skipFirstLine` correction in §3) and corrected the second hunk's `+`-side
   start line from `316` to `317`, which the added comment lines had made stale.
   Re-verified at `--fuzz=0` against the pristine tree and in the full
   `--targets=android` sequence.
2. **One line in `assets/patches/android.txt`.** *Not added by this task.*
   **LANDED by LW-M3-02**, after `patches/android/webgl-prompt-default.patch`,
   in substantially the suggested wording. The
   patch-list files are `shared_edit` and adding my own line is permitted, but
   the entry pulls a new ordering constraint in with it (item 3) that lives in
   files this task does not own, and the board's own instruction for a spike is
   not to turn it into an implementation. Suggested line, to append after
   `patches/android/webgl-prompt-default.patch`:

   ```
   patches/android/autoconfig-resource-fallback.patch   # LW-M3-08: makes nsReadConfig read the .cfg from resource://gre/defaults/autoconfig/ on Android, and packages librewolf.cfg + local-settings.js into omni.ja. NS_GRE_DIR does NOT fail on Android - it returns the APK's lib/ dir - so the fallback is keyed off the target, not off a failed directory lookup. Needs patches/xmas-common.patch (common.txt) first: it shares lw/moz.build
   ```

3. **A new row in the patch-ordering table** — `docs/android/AGENTS.md` and
   `scripts/check-patch-order.py`, neither of which this task owns.
   **LANDED in `scripts/check-patch-order.py` (LW-M3-02); still NOT in
   `docs/android/AGENTS.md`**, whose table still says "five pairs" and which no
   live task owns. That gap is reported to the board. The checker's own header
   now names both undeclared-in-AGENTS.md rows, so the divergence is at least
   visible from the file the CI gate runs:

   | first | then | shared file |
   |---|---|---|
   | `xmas-common` (common.txt) | `android/autoconfig-resource-fallback` (android.txt) | `lw/moz.build` |

   It is the third **cross-list** constraint, so it has the same shape as the
   `mozilla_dirs`/`xdg-dir` pair that a within-list checker cannot see. It holds
   by construction (common is always applied first) but must be declared, not
   assumed.

   This is not a prediction. Run against a scratch repo root that has item 2's
   line in `assets/patches/android.txt`, `scripts/check-patch-order.py` finds
   the pair by itself and refuses to pass until it is classified:

   ```
   shared files:
     lw/moz.build: hunks are in disjoint regions
   ...
   1 problem(s).
   ```

   The tuple it asks for:

   ```python
   ('patches/xmas-common.patch',
    'patches/android/autoconfig-resource-fallback.patch',
    'lw/moz.build',
    "xmas-common creates lw/moz.build; the android patch appends "
    "FINAL_TARGET_FILES.defaults.autoconfig to it. Cross-list "
    "(common.txt before android.txt), so it holds by construction."),
   ```

   `scripts/lint-patch-scope.py` is clean with the entry added (68 patch files,
   no scope violations) — the three touched files are core Gecko, a build file
   and `mobile/android/`, none of them desktop-only. And
   `./scripts/check-patchfail.sh --targets=android --use-desktop-tarball`
   applies the whole sequence with the entry in place:

   ```
   ==> patches/android/autoconfig-resource-fallback.patch:
   patching file extensions/pref/autoconfig/src/nsReadConfig.cpp
   patching file lw/moz.build
   patching file mobile/android/installer/package-manifest.in
   success: All patches where applied successfully.
   ```

   (with the usual `--use-desktop-tarball` caveat: 153.0.4, not the 153.0esr
   base `version.android` pins.)

4. **The packaging-manifest ownership question.** The `lw/moz.build` hunk lives
   in an *Android* patch while the file is created by a *common* patch
   (`patches/xmas-common.patch`, LW-M1-09). Two defensible resolutions:

   * keep it here — the extra install is Android-only, and a desktop build that
     never applies this patch keeps a byte-identical package. This is what the
     patch does today.
   * move it into `xmas-common.patch` behind
     `if CONFIG["MOZ_BUILD_APP"] == "mobile/android":`, which removes the
     cross-list ordering constraint (item 3) entirely at the cost of editing a
     file this task does not own.

   Recommendation: **the second**, when whoever owns `xmas-common.patch` next
   touches it. It trades a declared-and-checkable constraint for no constraint
   at all, and it puts both halves of "where do LibreWolf's files get installed"
   in one place. Until then the first is correct and is what ships.

   **LW-M3-02's decision: keep all three hunks in this one patch, and keep the
   constraint declared.** The recommendation above is not wrong, but it is a
   change to a file LW-M3-02 does not own either, and the trade is worse than it
   looks. Splitting the three hunks apart produces halves that each apply cleanly
   alone and are each broken *differently*:

   * install without the manifest entry → the file lands in `dist/bin` and is
     **silently** dropped from `omni.ja`. Not a prediction: that is the measured
     pre-patch state, §1 and §2.2.
   * C++ read without either → `NS_ERROR_FILE_NOT_FOUND`, which
     `nsReadConfig::Observe` swallows into one console warning. Also silent.
   * manifest entry without the install → **not** silent, a hard packaging
     error. `SimpleManifestSink.add`
     (`python/mozbuild/mozpack/packager/__init__.py:409-422`) calls
     `errors.error("Missing file(s): %s")` when a pattern matches nothing. (An
     earlier draft of this paragraph and of the patch header claimed this one was
     a silent no-op too. It is not — checked in the tree.)

   So two of the three failure modes are landmine L4's shape and the third makes
   the two halves order-coupled. One patch makes `check-patchfail`'s apply
   all-or-nothing. The reasoning is recorded in the patch header under "WHY THE
   PACKAGING HUNK IS IN THIS PATCH AND NOT A SIBLING".

Also worth a board decision, not resolved here: LibreWolf's
`patches/profile-directory.patch` is in `common.txt` and therefore active on
Android, where it sets

```
autoadmin.global_config_url = file:///data/user/0/<pkg>/files/.librewolf/librewolf.overrides.cfg
```

(`$HOME` on Android is the app's `files/` directory). Confirmed in `logcat`:
`D/MCD running MCD url file:///data/user/0/org.mozilla.fenix.debug/files/.librewolf/librewolf.overrides.cfg`,
failing benignly with `NS_ERROR_FILE_NOT_FOUND` and falling through to
`readOfflineFile()`. That is a **user-writable autoconfig override path inside
the app sandbox**, which is a feature on desktop and a decision on Android:
anything with write access to the app's data directory can `lockPref` whatever
it likes. It costs one synchronous `SpinEventLoopUntil` at every startup, too.
Not a blocker, not this task's call.

---

### 8.1 Gate status as **this task** left the tree (historical — see §14 for after LW-M3-02)

`patches/android/autoconfig-resource-fallback.patch` is on disk and in **no
patch list**, on purpose (item 2). One consequence, stated so nobody has to
rediscover it:

```
$ python3 docs/android/board.py --check-scope
error: patch file on disk is in no list and is not separately applied: patches/android/autoconfig-resource-fallback.patch
error: PATCH-SCOPE.md says 6 android, lists have 7
error: PATCH-SCOPE.md says 66 total, lists have 68
```

`board.py --check-scope:366-376` has no way to say "this patch exists but is
deliberately not wired up yet", so an unlisted file is always an error. **The
second and third errors are not this task's** — they are already present with
this patch moved out of the way (`6 android, lists have 7` / `66 total, lists
have 67`), i.e. `docs/android/PATCH-SCOPE.md`'s counts are stale against a patch
another task has already listed. Adding item 2's line removes the first error
and moves the count drift by one more.

Everything else is green with this task's files in place: `--check` (81 tasks),
`--check-cfg-split`, `--check-policies`, `--diff-mozconfig`,
`scripts/lint-patch-scope.py`, `scripts/check-patch-order.py`, and both
`check-patchfail.sh` runs — none of which this task's two files can reach,
since neither is referenced from a patch list.

---

## 9. Rejected alternatives

* **Package `librewolf.cfg` at the omnijar root and read
  `resource://gre/librewolf.cfg`.** Requires teaching
  `mozpack/packager/formats.py:is_resource` about a LibreWolf filename — a patch
  to shared build machinery to save moving a file into a directory that already
  qualifies. No.
* **Ship the `.cfg` as an Android asset and have Fenix copy it into the app data
  directory at first run**, which *is* where `GRE_HOME` points. Kotlin code, a
  copy that can fail open (landmine L4's shape), a file the app itself can
  rewrite, and it still would not work without a patch, because the directory
  service returns the lib dir rather than `GRE_HOME`. No.
* **Give up and build the compiler.** That is what this spike existed to avoid,
  and `modules/libpref/parser/src/lib.rs:14,297-321` still has no `locked_pref`
  token, so the compiler could not have expressed the 38 locks anyway.

---

## 10. How to reproduce

```sh
# 1. tree (do not build in a tree anyone else reads)
cp -a <a patched android tree with an objdir> ~/lw-m3-08/src
cd ~/lw-m3-08/src && patch -p1 -F0 < <repo>/patches/android/autoconfig-resource-fallback.patch

# 2. the Android .cfg, until scripts/librewolf-patches.py composes it
cat <repo>/settings/common.cfg <repo>/settings/android.cfg > lw/librewolf.cfg

# 3. build (see the trap in §11 - do NOT use scripts/android-apk.sh for this)
podman run --rm -v ~/lw-m3-08/src:/work/src:z -v ~/lw-m3-08/out:/work/out:z \
  -v ~/lw-m3-08/out/mozbuild-srcdirs:/root/.mozbuild/srcdirs:z -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e GRADLE_USER_HOME=/work/out/gradle-home \
  librewolf-android-build \
  bash -c './mach configure && ./mach build -j16 && ./mach gradle fenix:assembleDebug --no-configuration-cache'

# 4. run it, with the autoconfig log on
adb -s <serial> uninstall org.mozilla.fenix.debug          # fresh profile
adb -s <serial> install obj-x86_64/gradle/build/mobile/android/fenix/app/outputs/apk/debug/fenix-x86_64-debug.apk
printf 'env:\n  MOZ_LOG: MCD:5,timestamp\n' > /tmp/gv.yaml
adb -s <serial> push /tmp/gv.yaml /data/local/tmp/org.mozilla.fenix.debug-geckoview-config.yaml
adb -s <serial> logcat -c
adb -s <serial> shell am start -n org.mozilla.fenix.debug/org.mozilla.fenix.HomeActivity
adb -s <serial> logcat -d | grep -E 'D/MCD|ResetUserPrefs|SetDefaultPrefs'

# 5. read prefs back, two ways
adb -s <serial> shell 'run-as org.mozilla.fenix.debug sh -c "cat files/mozilla/*.default/prefs.js"'
#   ... and about:config in the app, which is the only way to see default-branch
#   values and the lock state (chrome://geckoview/content/config.xhtml,
#   docshell/base/nsAboutRedirector.cpp:110)
```

The `MOZ_LOG=MCD:5` line is the important part. It is the only way to see this
path work or fail on a device, and it is what turned a wrong patch into a
correct one in ten minutes.

---

## 11. Two build-system traps found on the way

Both cost real time and both will bite the next person testing a C++ change on
Android.

### 11.1 `scripts/android-apk.sh` builds an APK whose native code is **not** from `--srcdir`

With `MOZ_ANDROID_FAT_AAR_ARCHITECTURES` set — which `android-apk.sh` always
sets — `mobile/android/geckoview/build.gradle:130-136` points the AAR's
`jniLibs` at `dist/fat-aar/output/jni`, i.e. at the `libxul.so` of the *per-ABI
AAR run* named by `--aar-dir`. Only `omni.ja`, `classes.jar` and the manifest
come from the tree you patched. The script's own header says so; the failure is
still silent, because the APK builds, installs and runs.

Measured: `strings libxul.so | grep -c 'NS_GRE_DIR unavailable'` was `1` in
`obj-x86_64/dist/geckoview/lib/x86_64/libxul.so` and `0` in the same path
*inside* the APK the script produced — and the two files differ in size
(172443304 vs 172443176). A whole test round was run against an unpatched
Gecko before that was noticed.

**For a C++ change, drop the fat-AAR environment and build a single-ABI APK**
(the recipe in §10). Then verify provenance before trusting a result:

```sh
unzip -p <apk> lib/x86_64/libxul.so > /tmp/x.so
strings -a /tmp/x.so | grep -c '<a string your patch adds>'   # must be 1
```

### 11.2 Gradle's configuration cache survives a `mach configure` that changes substs

Reconfiguring without `MOZ_ANDROID_FAT_AAR_ARCHITECTURES` left
`'MOZ_ANDROID_FAT_AAR_ARCHITECTURES': []` in `config.status`, and Gradle
**still** built the fat APK — twice — because it reused a cached configuration
in which `:geckoview`'s `jniLibs` srcDir was already resolved to
`dist/fat-aar/output/jni`. `./mach gradle fenix:assembleDebug --no-configuration-cache`
fixed it in one run; the per-ABI APKs immediately dropped from ~154 MB to
~76 MB, which is the visible tell that they no longer carry three ABIs' native
libraries.

---

## 12. What was NOT verified

* **x86_64 only, API 30 emulator, one device.** No arm64 run, no physical
  device. The patch has no ABI-dependent code, but "it was never run on arm" is
  the honest statement.
* **The Android `.cfg` used here was `common.cfg + android.cfg` assembled by
  hand.** `scripts/librewolf-patches.py` does not compose it yet; that is item 1
  of LW-M3-02's remainder.
* **Not every pref was checked individually** — `board.py --check-cfg-split`
  counts 182 calls in `common.cfg` plus 2 in `android.cfg`. What was checked:
  the `.cfg` evaluated with no error and no console warning; the three sentinels
  and both proof-2 prefs read back correctly; and 16 of 25 bare `pref()` values
  are in the profile's `prefs.js`. A per-pref audit is `scripts/android-pref-audit.sh`'s
  job, not this spike's.
* **`distribution/policies.json` was not packaged and not tested.** It is not
  under `defaults/`, so it is still dropped flat. LW-M3-06.
* **Desktop was not rebuilt.** The C++ hunk is inside
  `#if defined(MOZ_WIDGET_ANDROID)`, so desktop's preprocessed source is
  unchanged — but no desktop build was run to confirm it.
  *This bullet used to add "and the patch is in `android.txt` so a desktop build
  never applies it at all", which contradicted §8 item 2 ("**Not added by this
  task**") for as long as the spike's tree stood. §8 was the correct one. Since
  LW-M3-02 the patch **is** in `assets/patches/android.txt`, so the claim is now
  true and the two sections agree — but it is true because LW-M3-02 put it there,
  not because the spike did.* What remains genuinely unverified is the desktop
  build: `./scripts/check-patchfail.sh` (the desktop run) applies `common ∪
  desktop` and never sees this file, which is evidence that the desktop patch
  **set** is unchanged, not that a desktop binary was produced.
* **The `MOZ_LOG` line kept in the patch has not been benchmarked.** It is
  `LogLevel::Debug` under a module that is off by default, so it is a branch on
  a disabled log module twice per startup.
* **Nothing here says the 38 locks are the *right* 38.** This spike proves the
  mechanism. Which prefs to lock, and the must-not-lock allowlist that keeps
  visible toggles from becoming inert, is LW-M3-04 — and §6 says its input set
  is bigger than it thought.

---

## 13. LW-M3-02: landing the channel turns the smoke test's `webgl` check red

**Added by LW-M3-02. This is a real finding and it is the one thing standing
between the landed channel and a green `./scripts/android-smoke.sh` baseline.**

The spike ran a hand-composed `common.cfg + android.cfg`. LW-M3-02's proof ran
what the repository actually produces — `settings/librewolf.cfg`, i.e.
`common + desktop` — and that composition carries
`defaultPref("privacy.resistFingerprinting", true)` (`settings/common.cfg:300`).
With the autoconfig channel landed, that pref reaches Android for the first time,
and `scripts/android-smoke.sh`'s `webgl` check fails:

```
webgl  FAIL  no verified pixel (stage=readPixels reason=None creationErrors=[]
             pixel=[44, 254, 56, 180]).  librewolf.webgl.prompt=False -- if that
             is false the cause is the GL stack under the emulator, not L1.
```

**It is not the GL stack, and it is not landmine L1.** WebGL is fully working:
a `webgl2` context is created, a vertex and a fragment shader compile and link, a
triangle is drawn, and `readPixels` returns data. What the check asserts is the
*value* of that data, and RFP rewrites it.

Three executions, on one host, establish the cause:

| # | build | config | `readPixels` |
|---|---|---|---|
| 1 | LW-M3-02's APK | as shipped | `[44, 254, 56, 180]` → FAIL |
| 2 | LW-M3-02's APK, **same emulator config** | as shipped, second run | `[196, 112, 189, 134]` → FAIL, **a different wrong pixel** |
| 3 | LW-M3-02's APK, same binary | `LW_SMOKE_EXTRA_PREFS={"privacy.resistFingerprinting.exemptedDomains":"10.0.2.2"}`, RFP still `true` globally | **`[51, 102, 153, 255]` → PASS**, and all seven checks pass |
| 4 | `~/lw-m2-04/out-make/apk/fenix-x86_64-debug.apk` (pre-autoconfig control) | `privacy.resistFingerprinting=false` | `[51, 102, 153, 255]` → PASS |

Run 4 rules out the host and the emulator's SwiftShader. Run 3 rules out the
binary — same `libxul.so`, one pref that exempts *the test origin only*, and the
pixel becomes exact. Run 2 rules out a deterministic driver bug: a broken GL
stack does not return a different wrong colour every time.

The mechanism, read off the tree afterwards rather than guessed at first:
`CanvasUtils::ImageExtractionResult` returns `ImageExtraction::Placeholder` when
`IsImageExtractionAllowed` is false (`dom/canvas/CanvasUtils.cpp:307-368`), which
with RFP on is the fresh-profile case — no `canvas` permission for the origin and
no user gesture yet, so `RFPTarget::CanvasImageExtractionPrompt` /
`CanvasExtractionBeforeUserInputIsBlocked` block it.
`ClientWebGLContext::ReadPixels` then calls
`dom::GeneratePlaceholderCanvasData(range->size(), range->Elements())`
(`dom/canvas/ClientWebGLContext.cpp:5215`), which samples **32 random bytes and
repeats them** across the buffer (`dom/canvas/GeneratePlaceholderCanvasData.h:83`,
`FillPlaceholderCanvas`). The harness reads one pixel from the start of that
buffer, so it gets four random bytes.

That the path is `Placeholder` and not `Randomize` is not an assumption — it is
what runs 1 and 2 show. The `Randomize` path
(`nsRFPService::RandomizeElements`) adds noise "to the lowest order bit of the
channel" and deliberately **skips the alpha channel**; it would have produced
something within ±1 of `[51, 102, 153, 255]` with alpha still `255`. Both observed
pixels have a randomised alpha (`180`, `134`) and colour channels nowhere near the
original. (Incidentally `patches/fpp-canvas-fix.patch` comments out
`RandomizeElements`' "don't randomize if all groups are uniform" early return,
which would matter for a solid-colour readback — but on this path that code is
never reached, so the patch is *not* implicated.)

**What this means for whoever owns `scripts/android-smoke.sh` (LW-M2-07).**

* The `webgl` check's expected pixel `[51, 102, 153, 255]` is **unreachable on any
  LibreWolf build**, on Android *or* desktop, for an unprivileged page on a fresh
  profile with no canvas permission. It was reachable only because Android had no
  `librewolf.cfg`. It should not be "fixed" by weakening the check to "a context
  was created" — that is precisely the shape L1 slips through.
* The plausible fix keeps the whole pipeline load-bearing and stops asserting the
  exact colour: assert that `getContext` succeeded, that both shaders compiled and
  the program linked, that `drawArrays` produced no GL error, and that `readPixels`
  returned a buffer — and then assert the colour **only** when canvas extraction is
  not being randomised, deciding that from the running build rather than assuming
  it. The three-way discriminator this section used (control build, per-origin
  exemption, pixel differs between runs) is available to the harness too.
* **The failure message is now actively wrong** and will cost the next person an
  afternoon: it says "if `librewolf.webgl.prompt` is false the cause is the GL
  stack under the emulator, not L1". On this build the pref *is* false, the cause
  is neither, and the message points away from the answer.
* Until that lands, an Android smoke run with autoconfig present reports
  **6 of 7 PASS with `webgl` FAIL**, and that single failure is a harness
  expectation, not a defect in the build.

## 14. LW-M3-02: the end-to-end proof, and gate status after landing

Built from `~/lw-m3-02/src` (a private copy of a fully patched Android tree, with
the landed patch text re-applied so the tree matches the repository byte for byte
in all three touched files) and `./mach build` + `./mach gradle
fenix:assembleDebug --no-configuration-cache`, single-ABI x86_64, **no**
`MOZ_ANDROID_FAT_AAR_ARCHITECTURES` — see §11.1 for why that matters for a C++
change.

**Provenance first**, because §11.1 exists: the `lib/x86_64/libxul.so` *inside*
the APK is sha256-identical to `dist/geckoview/lib/x86_64/libxul.so` in the tree
that was patched (`5382cd83…`), the APK contains no other ABI, the patch's own
`MOZ_LOG` format string appears exactly once in it, and `config.status` has
`'MOZ_ANDROID_FAT_AAR_ARCHITECTURES': []`.

**Packaging.** `assets/omni.ja` *inside the APK* now contains
`defaults/autoconfig/librewolf.cfg` (63742 bytes, byte-for-byte
`settings/librewolf.cfg`) and `defaults/pref/local-settings.js` (317 bytes),
beside the `defaults/autoconfig/prefcalls.js` that already shipped. Compare §1:
on the LW-M2-04 APK both were absent.

**A pref set only by `librewolf.cfg` is live on a fresh profile.**
`librewolf.cfg.version = "8.6"` is in the running app's pref set. That name
appears **nowhere** in the Firefox 153.0.4 tree — a recursive grep over
`firefox-153.0.4/` returns nothing — and only at `settings/common.cfg:68` /
`settings/librewolf.cfg:68`, as a `lockPref`. There is no other channel it could
have arrived by.

**`lockPref` really locked.** `--pref-dump` reports the `locked` column, and
exactly eight of the 56 curated prefs come back locked — precisely the members of
the curated list that `common.cfg` declares with `lockPref`:
`app.shield.optoutstudies.enabled`, `app.update.auto`,
`datareporting.healthreport.uploadEnabled`,
`datareporting.policy.dataSubmissionEnabled`, `toolkit.telemetry.archive.enabled`,
`toolkit.telemetry.enabled`, `toolkit.telemetry.server` (`data:,`) and
`toolkit.telemetry.unified`. Nothing else in the build locks a pref. On the
LW-M2-04 control dump, **zero** prefs are locked.

**The before/after on the curated dump** is what the channel is for. Selected
rows, LW-M2-04 control → LW-M3-02 build:

| pref | before | after |
|---|---|---|
| `browser.safebrowsing.provider.google4.updateURL` | the Google v4 endpoint | *empty* |
| `browser.safebrowsing.provider.google4.gethashURL` | the Google v4 endpoint | *empty* |
| `browser.safebrowsing.malware.enabled` / `.phishing.enabled` | `true` | `false` |
| `browser.safebrowsing.downloads.remote.enabled` | `true` | `false` |
| `network.prefetch-next` | `true` | `false` |
| `network.dns.disablePrefetch` | `false` | `true` |
| `network.http.speculative-parallel-limit` | `20` | `0` |
| `privacy.globalprivacycontrol.enabled` | `false` | `true` |
| `security.ssl.require_safe_negotiation` | `false` | `true` |
| `privacy.resistFingerprinting` | `false` | `true` |
| `app.update.auto`, `app.shield.optoutstudies.enabled`, `datareporting.policy.dataSubmissionEnabled`, `doh-rollout.enabled`, `extensions.getAddons.showPane`, `media.gmp-gmpopenh264.enabled` | **missing** | present, several locked |

**Landmine L2b reproduced on the way, unprompted.**
`browser.contentblocking.category` reads `standard` in the dump despite
`pref("browser.contentblocking.category", "strict")` at `common.cfg:117` — the
same measurement §6 records, on an independent build. Bare `pref()` is still
unsafe on Android; LW-M3-09.

**Gates, all run in the repository after the change:**
`board.py --check`, `--check-scope`, `--check-cfg-split`, `--check-policies`,
`--diff-mozconfig`, `scripts/lint-patch-scope.py`, `scripts/check-patch-order.py`
(now `6/6` declared constraints), `./scripts/check-patchfail.sh` and
`./scripts/check-patchfail.sh --targets=android --use-desktop-tarball` — the last
of which is the point of the exercise: it now *applies* this patch instead of
never seeing it.

`./scripts/android-smoke.sh --emulator` is **6 of 7**, failing only `webgl`, for
the reason §13 sets out.
