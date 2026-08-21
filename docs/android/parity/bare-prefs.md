# The 24 bare `pref()` calls in `common.cfg` — disposition, per pref

**Owner: LW-M3-09.** This is landmine **L2b**: a bare `pref()` in a `.cfg` writes
the **user** branch, and on Android `GeckoView:ResetUserPrefs` runs *after*
autoconfig and clears the user branch. One question decides every one of the 24
calls, and the answer is mechanical rather than a matter of taste:

> **Is the pref's name in the list `ResetUserPrefs` is given?**

`GeckoViewStartup.sys.mjs:394-398` is the whole handler —
`for (const name of aData.names) Services.prefs.clearUserPref(name);` — and the
list comes from `RuntimeSettings.java:353-367`, which walks `forAllPrefs` over
the settings object and its children and skips a pref only when
`!pref.hasDefault() && !pref.isSet()`. `Pref.hasDefault()` returns **true
unconditionally**; only `PrefWithoutDefault` overrides it to false. So the name
universe is every `Pref<>` declared by the three `RuntimeSettings` subclasses
(`GeckoRuntimeSettings.java:34`, `ContentBlocking.java:104`,
`ContentBlocking.java:1571`) — **101 literal declarations + 36 built at runtime**
by `SafeBrowsingProvider` as `ROOT + mName + "…"`
(`ContentBlocking.java:1572,1815-1826`, twelve suffixes × `google`, `google4`,
`google5`) — plus any `PrefWithoutDefault` that has been set.

**Four of the 24 are in that universe. Twenty are not**, and for those twenty a
bare `pref()` on Android behaves exactly as it does on desktop.

The correlation with what the running build actually reads is exact, and that is
the strongest single piece of evidence here: **all four** of the declared ones
were wrong or right-by-coincidence with the fix reverted, and **all twenty** of
the others were already correct. Nothing in the model is unaccounted for.

Second attempt. Everything measured in this file was re-measured on
2026-08-19T14:08–14:19Z with a four-arm experiment built from one tree; the
first attempt's comparison is retracted below rather than quietly replaced, and
none of its numbers are reused.

## Headline

| | |
|---|---|
| bare `pref()` calls in `common.cfg` | 24 |
| in the `ResetUserPrefs` name universe | **4** |
| **measured** reading the wrong value on Android with the fix reverted | **3** |
| right only because GeckoView's Java default coincides with ours | **1** |
| promoted, in `settings/android.cfg` | 4 (2 `lockPref`, 2 `defaultPref`) |
| changed in `settings/common.cfg` | **0 bytes** — desktop cannot move |
| bare `pref()` calls reading LibreWolf's value, with the fix reverted | 21 / 24 |
| bare `pref()` calls reading LibreWolf's value, with the fix in | **24 / 24** |
| does any of this reach a device from `make` today? | **no** — see "the delivery gap", LW-M3-10 |
| the `verify:` line `tasks.yaml` declares for this task | **vacuous** — see "The declared `verify:` is vacuous" |

---

## Run provenance — four builds from one tree, one changed file each

### First, a retraction

The first pass of this task claimed a *"controlled A/B on one variable"*. It was
not one. Its BEFORE APK came from `/home/mgysin/lw-batch-combined/src` and its
AFTER APK from `/home/mgysin/lw-m3-09/src`, an rsync copy of that tree made
fifteen hours later; the two were built from different objdirs at different
times, and the AFTER build used an `android.cfg` that had since been edited —
which that write-up disclosed itself, in a caveat under a headline claiming a
controlled experiment. The entry-level `omni.ja` comparison in it was real and
its numbers were real, but "same base, one variable" was an inference from the
rsync, not a fact about the two builds — so the sentence was doing work the
experiment had not done. It is also the third time in this project that a
measured-sounding sentence has sat over a comparison that was not the one
described, which is why the fix here is a new experiment rather than a
reworded paragraph. This section replaces it with an experiment that was actually run that
way, on **2026-08-19T14:08–14:19Z**, and nothing below is carried over from the
earlier measurement.

### The design

Everything below lives under **`/home/mgysin/lw-m3-09/ab3/`**, and every relative
path in this section is relative to it. Two sibling directories are deliberately
**not** used: `evidence/` holds the first attempt's dumps (12:07–12:11Z), and
`ab2/` holds a pair of builds made at 13:53–13:58Z that this attempt did not
create, cannot vouch for, and does not draw on. Nothing from either is quoted
here.

One source tree, `/home/mgysin/lw-m3-09/src`, one objdir, four consecutive
builds. Between two consecutive builds **exactly one file changes**:
`lw/librewolf.cfg`, the file `nsReadConfig` evaluates. Four arms, because two
different questions need answering and one A/B cannot answer both:

| arm | `lw/librewolf.cfg` is | answers |
|---|---|---|
| **A** | `settings/librewolf.cfg` = `common + desktop` — **what `make` puts on a device today** | what LW-M3-10 will change |
| **B** | `cat settings/common.cfg settings/android.cfg` — **the fix, composed by hand** | the target state |
| **C** | B, minus the four promotion lines | **isolates this task's four promotions** |
| **D** | B, minus only `lockPref("browser.contentblocking.category", …)` | was run to isolate the `url_decorations` side effect — now shown to be noise, see "Adjacent findings" |

C is the arm the first pass did not have. A→B changes the whole
`desktop.cfg` → `android.cfg` fragment, so it cannot attribute anything to
*this* task; **C→B differs by four lines and nothing else**, and that is the
comparison this task's claims rest on.

### The builds

Identical command for every arm, from `ab3/build-one.sh`:

```
podman run --rm -v …/src:/work/src -v …/out:/work/out \
  -v …/ab3/android-home:/root/.android \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=20260816204534 \
  -e GRADLE_USER_HOME=/work/out/gradle-home librewolf-android-build \
  bash -c './mach build -j16; rc=$?; echo MACH_BUILD_EXIT=$rc; \
           ./mach gradle fenix:assembleDebug --no-configuration-cache; rc2=$?; \
           echo MACH_GRADLE_EXIT=$rc2; exit $((rc+rc2))'
```

(`;` and two recorded exit codes rather than `&&`, so a green Gradle cannot hide
a red `mach build`.)

| arm | built (UTC) | `lw/librewolf.cfg` md5 | APK md5 | `omni.ja` md5 |
|---|---|---|---|---|
| A | 14:08:56 → 14:09:57 | `70fe84a7d24594c03e6f8cd2e9130bf6` | `55b63ce0f3f768de8f5502848f363048` | `de9d6d3dd0ec3494dc14d006341646c6` |
| B | 14:10:04 → 14:11:03 | `688df38ff8ff69ddb9c59dac67c06ab4` | `120842853944193241391571ad1b370d` | `fc6a8c1a5f206a98ded82419b62f9027` |
| C | 14:13:23 → 14:14:36 | `1a3c93e432db4c946525c3116f1fb80f` | `762b8b9b115fcd91ba5757360751cf34` | `bdfe14d3350327c1522cf8cde6fed4fb` |
| D | 14:17:25 → 14:18:19 | `7c345fb7b9c8ba1ca5855eaf9af726de` | `65d5a7a87783a2564b405ac8276dad0a` | `b6f2716011e69f20535bc6bb75f75eed` |

`MACH_BUILD_EXIT=0` and `MACH_GRADLE_EXIT=0` in all four (`ab3/*/build.log`).
Arm A's cfg md5 is byte-identical to `settings/librewolf.cfg` — `cmp` says so,
not just the hash — which is what makes A "the build `make` produces today"
rather than an approximation of it.

`MOZ_BUILD_DATE` is pinned, and the packaging is reproducible on that input:
arms A and B were each built **twice** — once before and once after a debug
keystore was made persistent (see below) — and both rounds produced a
byte-identical `omni.ja`, `de9d6d3d…` for A and `fc6a8c1a…` for B. The discarded
first round is kept as `A-nokey/` and `B-nokey/` so that is checkable.

### One variable, checked three ways

1. **At the input.** Over the *whole* experiment — from the moment arm A's build
   started to after arm D's finished — everything under `src/` that was modified,
   excluding the objdir and Gradle's own caches, is **one path**:

   ```sh
   $ find src -xdev -type f -not -path 'src/obj-x86_64/*' \
          -newermt '2026-08-19 14:08:56' -printf '%p\n' | grep -v '/\.gradle/'
   src/lw/librewolf.cfg
   ```

   48 files match before the `grep -v`; the other 47 are Gradle's own
   `*.lock`, `*.bin` and `buildOutputCleanup` files, which the build rewrites on
   every run regardless of input. Both lists are kept
   (`src-changed-whole-experiment{,-unfiltered}.txt`), as is the same check run
   at the A→B transition (`src-changed-during-{A,B}.txt`). Nothing else in the
   tree — no patch, no `moz.build`, no mozconfig — moved at any point.
2. **At the artefact.** Every arm's APK has **3447** zip entries and every arm's
   `omni.ja` has **2276**. Comparing `(CRC-32, uncompressed size)` per entry
   (`ab3/compare.py`, `zipfile`, no hand-rolled parsing):

   | pair | entries only in one side | entries whose CRC differs |
   |---|---|---|
   | A vs B, inside `omni.ja` | 0 | **1** — `defaults/autoconfig/librewolf.cfg` |
   | A vs B, whole APK | 0 | **1** — `assets/omni.ja` |
   | C vs B, inside `omni.ja` | 0 | **1** — `defaults/autoconfig/librewolf.cfg` |
   | C vs B, whole APK | 0 | **1** — `assets/omni.ja` |

   And the `.cfg` **inside** each APK's `omni.ja` hashes to the same md5 as the
   `.cfg` that went in. So the thing that differs between two arms is the file
   this task edits, packaged, on the shipped artefact — not a claim about the
   objdir.
3. **At the signing key.** The first attempt at this A/B produced two APKs signed
   with *different* debug keys, because AGP generates `~/.android/debug.keystore`
   inside the container and `--rm` threw it away. `adb install` of the second APK
   over the first then failed with `INSTALL_FAILED_UPDATE_INCOMPATIBLE` — which
   is how it was noticed. Both arms were rebuilt with `ab3/android-home` mounted
   at `/root/.android`; the keystore md5 (`bac25a5a7f4ab036ac9b9bdb9c5efdd2`) is
   unchanged before and after every build, and Android's own verifier confirms
   it: each later arm installs **over** the previous one without an uninstall,
   which the platform only permits when the signing certificates match.

   One asymmetry that is *not* controlled and should be stated: arm B's APK file
   is 178 MB against A's 166 MB. The incremental packager appends the replaced
   `assets/omni.ja` at the end and leaves the superseded 12 MB unreferenced by
   the central directory. Both APKs list 3447 entries and Android resolves
   entries through the central directory, so this is dead weight, not content —
   and the pref values measured below are the new `.cfg`'s, which is the direct
   evidence that the live entry is the one being read.

### The device

**One** emulator instance for all seven runs: AVD `lw-smoke` (android-30/default,
x86_64) under `ab3/smokework/`, booted once by `android-smoke.sh --emulator
--keep-emulator` and reachable afterwards as `emulator-5584`, then killed. Every
run is `./scripts/android-smoke.sh --serial emulator-5584 --pref-dump --apk <arm>`,
which wipes app data (`pm clear`) and reinstalls before it measures. Every run
exited **0**, and every `result.json` records `"tainted": false` and
`"injected_prefs": {}` — no `LW_SMOKE_EXTRA_PREFS` was used anywhere in this
exercise. The harness's own two prefs (`remote.prefs.recommended`,
`marionette.port`) are neither of the 24 and are excluded from the dump by
construction.

Runs, in the order they happened:

```
14:11:43Z  A     14:14:59Z  C      14:18:34Z  D
14:11:56Z  B     14:15:32Z  B2     14:19:29Z  B3
                 14:15:59Z  C2
```

### The noise floor, measured rather than assumed

The same APK was run three times (B, B2, B3) and another twice (C, C2). Across
`prefs-all.json` — all ~4150 prefs in the running profile, not the curated 56 —
repeated runs of one APK differ in exactly **four** names, all of them
per-profile identifiers or clocks:

```
extensions.webextensions.uuids     nimbus.profileId     toolkit.startup.last_success
captchadetection.lastSubmission
```

The fourth, `captchadetection.lastSubmission`, moves `1787148` → `1787149`
between B2 and B3 (and appears in the D→B delta); the other three are stable
within an arm. The curated `prefs.txt` was **byte-identical** across B/B2/B3 and
across C/C2, because none of the four noise names is in the curated 56. So any
name outside those four that moves between arms is a real difference, and that is
what the next section reports.

### What is kept, and what was thrown away

Under `ab3/`, per arm (`A`, `B`, `C`, `D`, plus the discarded `A-nokey`,
`B-nokey`): the **APK itself**, `build.log`, `build.{start,end}`, `cfg.md5`,
`apk.md5`, the exact `librewolf.cfg.installed` that went in, the
`omni-librewolf.cfg` that came back out of the APK, `output-metadata.json`
(where the harness reads the applicationId, never a guess), and per device run
`prefs-stdout.txt`, `prefs-all.json`, `result.json`, `smoke.log` — the repeats
`B2`, `B3`, `C2` keep the run files only. Alongside them:
`packaged-cfg.md5` (input md5 == packaged md5, for all six APKs),
`compare.py` / `compare.txt` / `compare-BC.txt`, `prefs-all-diff*.txt`,
`noise-floor.txt`, `counterfactual.txt`, `src-changed-*.txt`, `keystore.md5`,
the four composed `cfg-*.cfg` inputs, and `build-one.sh`.

Deleted after the fact because they are large and regenerable: the AVD image
under `smokework/avd` (the emulator was killed at the end of the run) and the
14 MB `capture.pcap`, which no check in this file reads — `--pref-dump` opens no
capture window. The extracted `omni.ja` blobs were deleted too; `compare.py`
rebuilds them from the APKs in seconds.

### Result 1 — this task's four promotions, isolated (C → B)

C and B are four lines apart. Their APKs differ in one zip entry. Across all
~4150 prefs in the profile, their dumps differ in the **four promotions** below,
plus `url_decorations` (which is **not** one of the 24 and — per the corrected
"Adjacent findings" — **not** a consequence of this task's lock), plus the noise
floor, and in nothing else:

| pref | C (fix reverted) | B (fix in) |
|---|---|---|
| `browser.contentblocking.category` | `standard` | **`strict`, `locked`** |
| `devtools.console.stdout.chrome` | `true` | **`false`** |
| `browser.safebrowsing.provider.google4.dataSharingURL` | `https://safebrowsing.googleapis.com/v4/threatHits?…` | **`""`** |
| `devtools.debugger.remote-enabled` | `false`, unlocked | `false`, **`locked`** |

Reproduced on both C runs and all three B runs; full listing in
`prefs-all-diff-CB.txt`. The `url_decorations` name is **not** one of the 24 and
is **not** a consequence of this task's category lock — the `A-nokey` arm (arm-A
content, `category` reading `standard`) dumped it **empty**, the arm-B outcome, so
it does not track the lock and arm D does not isolate it. It is written up under
"Adjacent findings" as unexplained noise; do not read this paragraph as if the
C→B delta were only the four promotions.

This is what the acceptance line *"the measured casualties are fixed, verified on
a running build not by reading"* asks for. Note the fourth row is why the count
of **values** fixed is three, not four: `devtools.debugger.remote-enabled`
already read `false`, because GeckoView's Java default happens to be `false`.
What changed there is ownership, and the `locked` column is the visible evidence
for it.

### Result 2 — what LW-M3-10 will change wholesale (A → B)

A is the composition a `make` build ships to Android today. Against B, the
curated dump moves three lines:

```
-browser.contentblocking.category   string  standard  -       -
+browser.contentblocking.category   string  strict    locked  -
-devtools.debugger.remote-enabled   bool    false     -       -
+devtools.debugger.remote-enabled   bool    false     locked  -
-media.eme.enabled                  bool    true      -       -
+media.eme.enabled                  bool    false     -       -
```

`media.eme.enabled` is the **positive control**: it is LW-M3-06's `defaultPref`
in `android.cfg` and belongs to no part of this task, so its flip is independent
evidence that the composed `.cfg` was really evaluated. The other half of the
same control is subtractive — **79** prefs present in A are absent in B, every
one of them a `desktop.cfg` pref (`librewolf.aboutMenu.checkVersion`,
`privacy.resistFingerprinting.letterboxing`, `browser.uitour.*`, …), and **0**
prefs appear in B that were absent in A. Full list: `ab3/prefs-all-diff.txt`.

**The complete A→B account**, so nothing is left to a reader's trust. Twelve
names change value; every one is attributed:

| name | why it moved |
|---|---|
| `browser.contentblocking.category` | this task (`android.cfg` `lockPref`) |
| `devtools.console.stdout.chrome` | this task (`android.cfg` `defaultPref`) |
| `browser.safebrowsing.provider.google4.dataSharingURL` | this task (`android.cfg` `defaultPref`) |
| `media.eme.enabled` | LW-M3-06's `android.cfg` line — the positive control |
| `privacy.restrict3rdpartystorage.url_decorations` | **not** a consequence of this task's lock — `A-nokey` (arm-A content, `category=standard`) dumped it empty; unexplained noise, see "Adjacent findings" |
| `privacy.sanitize.sanitizeOnShutdown` `true`→`false` | `desktop.cfg:66` has no `android.cfg` counterpart |
| `privacy.window.maxInnerWidth` `1600`→`1400` | `desktop.cfg:144` (letterboxing pair with `:146`) has none either |
| `extensions.webcompat-reporter.enabled` `false`→`true` | `desktop.cfg:284` `lockPref` has none either |
| `extensions.webcompat-reporter.newIssueEndpoint` `""`→`https://webcompat.com/issues/new` | `desktop.cfg:285` `lockPref` has none either |
| `extensions.webextensions.uuids`, `nimbus.profileId`, `toolkit.startup.last_success` | the measured noise floor |

The four `desktop.cfg`-only rows are **not** this task's — none of them moves
between C and B — but they are a parity gap that lands the moment LW-M3-10
switches the composition: on that day Android silently gains a webcompat
reporter pointed at `webcompat.com` and loses sanitize-on-shutdown. Somebody
should own them before it does. Whether each belongs in `common.cfg` or in
`android.cfg` is a judgement this task did not make and did not sneak in.

---

## The table

`declared` answers the `ResetUserPrefs` question. **`C` and `B` are the two arms
above**: `C` is the composed `common + android` build with this task's four
lines deleted, `B` is the same build with them in. Every value is read off a
running APK; none is read off a source file. The twenty undeclared rows were
identical in every one of the seven device runs.

| # | `common.cfg` | pref | our value | declared at | C (reverted) | B (fixed) |
|---|---|---|---|---|---|---|
| 1 | :117 | `browser.contentblocking.category` | `"strict"` | `ContentBlocking.java:579` | `standard` ✗ | **`strict` 🔒** |
| 2 | :144 | `browser.privatebrowsing.autostart` | `false` | — | `false` ✓ | `false` ✓ |
| 3 | :165 | `browser.dom.window.dump.enabled` | `false` | — | `false` ✓ | `false` ✓ |
| 4 | :166 | `devtools.console.stdout.chrome` | `false` | `GeckoRuntimeSettings.java:767` | `true` ✗ | **`false`** |
| 5 | :275 | `network.prefetch-next` | `false` | — | `false` ✓ | `false` ✓ |
| 6 | :276 | `network.http.speculative-parallel-limit` | `0` | — | `0` ✓ | `0` ✓ |
| 7 | :277 | `network.early-hints.preconnect.max_connections` | `0` | — | `0` ✓ | `0` ✓ |
| 8 | :309 | `webgl.disabled` | `false` | — | `false` ✓ | `false` ✓ |
| 9 | :349 | `security.tls.enable_0rtt_data` | `false` | — | `false` ✓ | `false` ✓ |
| 10 | :350 | `network.http.http3.enable_0rtt` | `false` | — | `false` ✓ | `false` ✓ |
| 11 | :351 | `security.tls.version.enable-deprecated` | `false` | — | `false` ✓ | `false` ✓ |
| 12 | :359 | `permissions.manager.defaultsUrl` | `""` | — | `""` ✓ | `""` ✓ |
| 13 | :379 | `browser.safebrowsing.downloads.remote.enabled` | `false` | — | `false` ✓ | `false` ✓ |
| 14 | :380 | `…downloads.remote.block_potentially_unwanted` | `false` | — | `false` ✓ | `false` ✓ |
| 15 | :381 | `…downloads.remote.block_uncommon` | `false` | — | `false` ✓ | `false` ✓ |
| 16 | :383 | `browser.safebrowsing.downloads.remote.url` | `""` | — | `""` ✓ | `""` ✓ |
| 17 | :384 | `browser.safebrowsing.provider.google4.dataSharingURL` | `""` | `ContentBlocking.java:1824` (dynamic) | Google's `threatHits` URL ✗ | **`""`** |
| 18 | :416 | `browser.region.network.url` | `""` | — | `""` ✓ | `""` ✓ |
| 19 | :417 | `browser.region.update.enabled` | `false` | — | `false` ✓ | `false` ✓ |
| 20 | :561 | `devtools.debugger.remote-enabled` | `false` | `GeckoRuntimeSettings.java:748` | `false` — *by coincidence* | **`false` 🔒** |
| 21 | :642 | `network.connectivity-service.enabled` | `false` | — | `false` ✓ | `false` ✓ |
| 22 | :644 | `network.captive-portal-service.enabled` | `false` | — | `false` ✓ | `false` ✓ |
| 23 | :645 | `captivedetect.canonicalURL` | `""` | — | `""` ✓ | `""` ✓ |
| 24 | :647 | `dom.private-attribution.submission.enabled` | `false` | — | `false` ✓ | `false` ✓ |

Dispositions: **1** and **20** → `lockPref` in `android.cfg`; **4** and **17** →
`defaultPref` in `android.cfg`; the other twenty → **keep bare**, unchanged, with
the reason in the next section. 🔒 means the pref dump's `locked` column reads
`locked`.

The three wrong values, as arm C reads them, in full:

| pref | LibreWolf says | Android read |
|---|---|---|
| `browser.contentblocking.category` | `strict` | **`standard`** |
| `devtools.console.stdout.chrome` | `false` | **`true`** |
| `browser.safebrowsing.provider.google4.dataSharingURL` | `""` | **`https://safebrowsing.googleapis.com/v4/threatHits?$ct=application/x-protobuf&key=%GOOGLE_SAFEBROWSING_API_KEY%&$httpMethod=POST`** |

---

## Why the twenty stay bare — and why promoting them would be a regression

They are not in the reset universe, so their user value survives on Android
exactly as on desktop, and all twenty were **measured** at LibreWolf's value in
every one of the seven device runs, on all four arms — including arm C, where
this task's fix is reverted, which is the arm that could have exposed them. That
is the first reason. The second is that promoting them would
make Android *weaker* than desktop, not stronger:

- a bare `pref()` re-asserts the value on the user branch at **every startup**,
  so it overrides whatever is already in the profile;
- a `defaultPref` writes the default branch and leaves a stale or user-set
  profile value winning.

For prefs whose whole purpose is "always this, every launch" — the three
`security.tls.*` / `http3.enable_0rtt` lines, the four
`safebrowsing.downloads.remote.*` lines, the two `browser.region.*` lines — the
bare call is the stronger construct, on both platforms. `common.cfg:114` says the
same thing in as many words for the category pref: *"the desired category must be
set with `pref()` otherwise it won't stick."* Restating twenty working prefs in
`android.cfg` would also create twenty new places for the two files to drift.

This is the same argument `android.cfg`'s own header makes against restating
`librewolf.webgl.prompt`: two sources for one value is how they drift.

---

## Why the four are split 2 `lockPref` / 2 `defaultPref`

`ResetUserPrefs` only clears the **user** branch, so `defaultPref` alone already
defeats L2b. `lockPref` is needed only where a **second** writer exists:
`Pref.commit()` (`RuntimeSettings.java:113-122`) dispatches
`GeckoView:SetDefaultPrefs` at *runtime*, and `GeckoViewStartup.sys.mjs:400-420`
writes it straight onto the default branch — which beats an unlocked
`defaultPref` (landmine L2). A lock is not free: it leaves the Fenix control that
writes the pref visibly working and functionally dead. So a lock was used only
where a runtime writer was actually found in the tree.

**And a lock genuinely wins, in libpref rather than by anecdote.**
`Pref::SetDefaultValue` (`modules/libpref/Preferences.cpp:876-902`) opens with

```cpp
// Should we set the default value? Only if the pref is not locked, and
// doing so would change the default value.
if (!IsLocked()) { … }
```

so a locked pref's *default* value cannot be changed, and the call still returns
`NS_OK` — nothing throws, Fenix sees no error, the write is a silent no-op. That
is the mechanism behind LW-M3-08's observation, and it is also why locking is
safe to do: `commit()` on a locked pref cannot crash the settings screen.

### `browser.contentblocking.category` → `lockPref`

- **Runtime writer, found:** `ContentBlocking.java:1062-1073`
  (`setEnhancedTrackingProtectionCategory` → `mEtpCategory.commit(…)`), reached
  from `GeckoEngine.kt:1510-1512` in the `trackingProtectionPolicy` setter, which
  Fenix drives from `Core.kt:176` at engine construction and from
  `TrackingProtectionFragment.kt` afterwards. `commit()` early-returns while the
  Java value is unchanged, so an unlocked `defaultPref` would in fact survive a
  *fresh* profile — and then die the first time the user touched the ETP screen.
  Locking removes that cliff.
- **It is not a cosmetic desktop-UI aggregate on Android.** Three non-test
  readers ship here:
  `netwerk/url-classifier/UrlClassifierExceptionListEntry.cpp:99-112` skips a
  Remote Settings tracking-protection **exception** entry unless its
  `filterContentBlockingCategories` list contains this string — so `standard`
  activates the standard-category exceptions, i.e. allow-lists trackers that
  `strict` keeps blocked;
  `netwerk/url-classifier/UrlClassifierExceptionListService.sys.mjs:184,278`
  watches it as one of three `ETP_PREFERENCES` and comments, in-tree, *"This pref
  is set on both Desktop and Fenix (Bug 1956620)"*; and
  `toolkit/components/url-classifier/RealTimeRequestSimulator.cpp:26`.
- **No cascade to expect.** The `:278` migration that would flip
  `privacy.trackingprotection.allow_list.{baseline,convenience}.enabled` when the
  category is not `standard` is gated on
  `privacy.trackingprotection.allow_list.hasMigratedCategoryPrefs`, which
  `common.cfg:120` already ships as `lockPref(true)`. Measured: all three of
  those prefs read `true` on **every arm and every run**, `standard` and
  `strict` alike. Do not read the fix as having moved them. (The one name that
  *did* move between the C and B arms,
  `privacy.restrict3rdpartystorage.url_decorations`, is **not** a consequence of
  the lock — the `A-nokey` arm breaks that correlation; see "Adjacent findings".)
- **Cost:** Fenix's *Settings → Enhanced Tracking Protection* category selector
  becomes inert — it still moves, the behaviour does not follow. Desktop
  LibreWolf does the same thing by hiding that UI and rewriting the pref at every
  startup, so this is parity rather than a new decision. **For LW-M3-04: this
  belongs on the "locked, known to leave a visible control dead" list, not on the
  must-not-lock allowlist.**

### `devtools.debugger.remote-enabled` → `lockPref`

- **Runtime writer, found:** `SettingsFragment.kt:601-604` assigns
  `requireComponents.core.engine.settings.remoteDebuggingEnabled` from the
  *Remote debugging via USB* switch, which is `mRemoteDebugging.commit(…)`
  (`GeckoRuntimeSettings.java:1330`); `Core.kt:174` feeds the same value into
  `DefaultSettings` at engine construction.
- **Already measured, by LW-M3-08:** locked, it stayed `false` after that switch
  was turned ON, while an unlocked control pref flipped in the same session and
  process. That observation is the evidence landmine L2 rests on; the libpref
  quote above is why it generalises.
- Read `false` before the fix only because GeckoView's own Java default
  (`GeckoRuntimeSettings.java:747-748`) happens to be `false` too. Our user value
  was wiped just the same, so the value was being supplied by Fenix, not by us,
  and it would flip silently if that default ever changed. After the fix the
  value is the same and the `locked` column is what changed — which is precisely
  the point: it is now **ours**.
- **The alternative was considered and rejected.** `defaultPref` would keep the
  switch alive and would track the user's own choice, which is arguably closer to
  desktop, where a user *can* turn remote debugging on for a session. It was
  rejected because it would leave LibreWolf's value doing nothing at all: Fenix
  re-applies its SharedPreference at every engine construction, so the effective
  value would always be Fenix's, never ours. If LW-M3-04 decides a live switch is
  worth more than an owned value, this is the one of the four to revisit — and
  the change is one word.
- **Cost:** the *Remote debugging via USB* switch becomes inert. Desktop
  LibreWolf ships remote debugging off. For LW-M3-04's dead-control list.

### `devtools.console.stdout.chrome` → `defaultPref`

**Correction to the first pass of this task**, which attributed this pref to
`mConsoleOutput` / `Builder.consoleOutput()` / `setConsoleOutputEnabled`. That is
the **wrong field**: `mConsoleOutput` is `geckoview.console.enabled`
(`GeckoRuntimeSettings.java:751-752`), a pref we do not ship. The conclusion is
unchanged; the reasoning below is the one that holds.

- The field is `mDevToolsConsoleToLogcat`, `new Pref<>("devtools.console.stdout.chrome", true)`
  at `GeckoRuntimeSettings.java:766-767`.
- **No runtime writer.** It is assigned in exactly one place in the whole tree:
  `Builder.debugLogging()` (`GeckoRuntimeSettings.java:517-521`), which calls
  `set()`, not `commit()`. There is no setter on `GeckoRuntimeSettings` that
  commits it. So its value arrives before the profile via
  `getPrefsMap`/`MOZ_DEFAULT_PREFS`, and autoconfig runs after that.
- `GeckoProvider.kt:122` calls
  `debugLogging(Config.channel.isDebug || settings.enableGeckoLogs)` — on a
  **debug** build, which every smoke APK is, that argument is unconditionally
  `true`. That is why the miss was visible at all, and it is also why a release
  APK would not have shown it. Flipping the secret-menu toggle
  (`SettingsFragment.kt:718-740`) only writes a SharedPreference and calls
  `exitProcess(0)`, so the value is re-derived through the Builder next launch.
- Leaving it unlocked keeps the rest of that debug toggle (`geckoview.logging`,
  `consoleservice.logcat`) working, and locking would buy nothing.
- Effect of the miss, before the fix: chrome console output went to logcat on
  Android while LibreWolf disables it everywhere else — see the
  `common.cfg:161-164` rationale (these are off in official Mozilla builds).
- **Measured:** `true` on arms A, C and C2; `false` on arms D, B, B2 and B3.
  `defaultPref` was enough.

### `browser.safebrowsing.provider.google4.dataSharingURL` → `defaultPref`

- **`defaultPref` is enough, and this is measured rather than argued:** it reads
  `""` on arms B, B2, B3 and D, and Google's `threatHits` URL on arms A, C and
  C2. The four sibling provider URLs `common.cfg:371-374` already ships as
  `defaultPref` (`google`/`google4` × `gethashURL`/`updateURL`) are declared by
  the *same* `SafeBrowsingProvider` mechanism and read `""` on **all four
  arms** — which is the direct evidence that `defaultPref` is enough for a name
  in the reset universe, and the reason the fifth one did not need a lock.
- **No runtime writer.** `mDataSharingUrl` is assigned only by the provider
  Builder (`ContentBlocking.java:1753`, `set()`), and Fenix never calls
  `setSafeBrowsingProviders` — there is no reference to it anywhere in
  `mobile/android/fenix` or `android-components`.
- `browser.safebrowsing.provider.google4.dataSharing.enabled` is `false`, so
  nothing was being sent even before the fix — but blanking the URL is the
  defence in depth the `common.cfg:378-384` comment asks for, and it was not in
  place.
- **Why it is in the reset list**, precisely: not because a provider "supplies a
  value and makes `isSet()` true" (that was the first pass's reasoning and it is
  not how the filter works) but because it is a plain `Pref<>`, and
  `Pref.hasDefault()` is unconditionally `true`. All 36 dynamic names are in the
  list whether or not anyone ever set them.
- **This name was invisible to every gate.** It is not one of the 101 literal
  declarations; `SafeBrowsingProvider` builds it as `ROOT + mName + ".dataSharingURL"`.
  See the board items below.

---

## The "16 of 25 persisted" figure was measured with the wrong instrument

The figure quoted in `AGENTS.md` (L2b), `tasks.yaml` and `AUTOCONFIG-SPIKE.md`
§12 — *"16 of 25 bare `pref()` values are in the profile's `prefs.js`"* — is a
true statement about `prefs.js` and **not** a count of casualties. `prefs.js`
records user-branch values, and libpref deliberately does not store one when the
value you set already equals the default:

`Pref::SetUserValue` (`modules/libpref/Preferences.cpp:904-936`) — *"Should we
clear the user value, if present? Only if the new user value matches the default
value, and the pref isn't sticky, and we aren't force-setting it during
initialization"* — clears (or never stores) the user value in exactly that case.
Autoconfig's `pref()` is not `aFromInit`, so it hits that branch.

So a bare `pref()` that restates the platform default is **absent from
`prefs.js` while being perfectly in effect**. `webgl.disabled` is the clean
example: `false` is the Gecko default, the pref dump shows no user value, and the
effective value is the one we want. Nine names missing from `prefs.js` is
therefore 3 real casualties + 1 latent + 5 no-ops, not 9 casualties.

**Read effective values, not `prefs.js`.** `./scripts/android-smoke.sh
--pref-dump` writes both `prefs.txt` (curated, with `locked` and `user` columns)
and `prefs-all.json` (every pref in the running profile). The `user` column in
`prefs.txt` is what makes the mechanism visible in one glance — these six rows
are copied out of **arm C's** dump (`ab3/C/prefs-stdout.txt`), the composed
Android build with this task's fix reverted, and they were identical in arm C2:

```
browser.contentblocking.category                string  standard  -  -      <- declared: user value wiped
devtools.debugger.remote-enabled                bool    false     -  -      <- declared: user value wiped
browser.safebrowsing.downloads.remote.enabled   bool    false     -  user   <- not declared: user value survives
network.prefetch-next                           bool    false     -  user   <- not declared: user value survives
network.http.speculative-parallel-limit         int     0         -  user   <- not declared: user value survives
webgl.disabled                                  bool    false     -  -      <- not declared: == default, so no user value ever stored
```

Two of those six rows carry the whole L2b argument on their own:
`browser.safebrowsing.downloads.remote.enabled` and
`browser.contentblocking.category` are both bare `pref()` calls in the same file
with the same construct, and only the second one is declared by GeckoView — and
only the second one lost its user value.

---

## Desktop is unchanged, and that is checkable rather than asserted

1. `settings/common.cfg`, `settings/desktop.cfg` and `settings/librewolf.cfg`
   are **byte-identical** to their pre-task state, verified by md5 before and
   after the whole exercise, second attempt included:
   `common.cfg 19cae9cb7ae443ad91c70e0a590ab2f7`,
   `desktop.cfg 186c743e55f7ce5710eba5c8e18e4aa8`,
   `librewolf.cfg 70fe84a7d24594c03e6f8cd2e9130bf6`.
   (`librewolf.cfg` *is* modified in the submodule's working tree — by LW-M3-01's
   split, which regenerated it — but not by this task, and not during it.)
   The desktop input is not merely hashed on disk, it was **built and shipped**:
   arm A's `lw/librewolf.cfg` is `cmp`-identical to `settings/librewolf.cfg`, and
   the copy extracted back out of arm A's *APK* — `assets/omni.ja` →
   `defaults/autoconfig/librewolf.cfg` — hashes to that same
   `70fe84a7d24594c03e6f8cd2e9130bf6`. What a desktop build consumes is the same
   bytes it consumed before this task, so its effective prefs cannot have moved.
   (That is proof by input identity. No desktop LibreWolf build was made here —
   see "What this file does not prove".)
2. `board.py --check-cfg-split`'s checks **A** (librewolf.cfg is the byte
   concatenation of common+desktop), **B** (per-`(kind,name,value)` conservation
   against `HEAD:librewolf.cfg`) and **D** (the recorded totals for
   common+desktop) all pass. Those three exist precisely to catch a desktop
   semantic change and none of them fires.
3. The desktop build never reads `android.cfg` at all:
   `scripts/librewolf-patches.py:376` copies `settings/librewolf.cfg`, which is
   `common + desktop`. Nothing else in the repository references `android.cfg`
   except `board.py` and documentation.
4. The counterfactual was **re-measured for this attempt**, at 2026-08-19, not
   carried over: promoting the category pref inside `common.cfg` instead —
   `pref` → `lockPref` on line 117, nothing else — turns `--check-cfg-split` red
   (exit 1) with exactly the desktop-semantics errors A, B (×2) and D (×2):
   `error: A: librewolf.cfg is not the byte concatenation …`,
   `error: B: lockPref(browser.contentblocking.category) changed: 0 before, 1 after`,
   `error: B: pref(browser.contentblocking.category) changed: 1 before, 0 after`,
   `error: D: 61 lockPref in common+desktop, expected 60`,
   `error: D: 25 pref in common+desktop, expected 26`.
   `common.cfg` was restored from a backup taken seconds earlier and `cmp`'d
   byte-identical before continuing; the edit existed for the length of one
   `board.py` run. Transcript: `ab3/counterfactual.txt`.

---

## The delivery gap this task cannot close, and must not be read as closed

**`settings/android.cfg` is not shipped to Android by the repository today.**
`scripts/librewolf-patches.py:376` unconditionally copies `settings/librewolf.cfg`
(= `common + desktop`) into `lw/`, on every target. LW-M3-09 does not own that
file.

That is now a board task: **LW-M3-10, "Ship the common+android cfg composition,
not the desktop one"**, `owns: [scripts/librewolf-patches.py]`,
`depends_on: [LW-M3-02, LW-M3-09]`. Until it lands, the four promotions in
`android.cfg` are **correct and inert** in a build made by `make`.

**Say this out loud when quoting any number in this file: arms B, C and D do not
exist unless somebody composes them by hand.** `cat settings/common.cfg
settings/android.cfg > lw/librewolf.cfg` is what produced them, and it was typed
by this task, not by `scripts/librewolf-patches.py`. A `make`-built APK today is
arm **A**, where `browser.contentblocking.category` reads `standard`. This
task's fix is correct, measured, and **inert in the shipping path**. A gate
going green does not change that, and no sentence in this file should be read as
if it did.

The same by-hand composition already supplies the measurement LW-M3-10's third
acceptance line asks for ("on a running Android build, a pref set only in
`android.cfg` is observable in about:config"): `media.eme.enabled` flips
`true` → `false` between A and B, and 79 `desktop.cfg` prefs — including
`privacy.resistFingerprinting.letterboxing` — disappear. What LW-M3-10 still has
to prove is that *its* code path produces the same two files, and that the
desktop one is byte-identical to `settings/librewolf.cfg`.

---

## The declared `verify:` is vacuous — shown by running it, and what replaces it

The line `tasks.yaml` declares for LW-M3-09 is

```
verify: python3 docs/android/board.py --check-cfg-split && ./scripts/android-smoke.sh --pref-dump
```

`--pref-dump` **prints** prefs. It asserts nothing about any of them:
`android-smoke.sh:1598-1606` records `res.add("pref-dump", True, …)` — the
literal `True` — and returns. The only way that check goes red is if the
harness cannot reach the device at all, which is exit code 2, not a failed
check.

Demonstrated, rather than reasoned, on **arm A — the APK a `make` build produces
today, in which the pref this task exists to fix reads `standard`**:

```
$ python3 docs/android/board.py --check-cfg-split && \
    ./scripts/android-smoke.sh --serial emulator-5584 --apk …/A/…apk --pref-dump
browser.contentblocking.category   string   standard   -   -
$ echo $?
0
```

A gate that exits 0 while printing the defect it is supposed to catch is not a
gate.

### The replacement

Two changes: assert the **value**, and do not put the harness in a pipeline
(`SMOKE.md`, "watch out for pipelines" — in `a | b`, `$?` is `b`'s, so the
harness's exit code is discarded).

```
verify: python3 docs/android/board.py --check-cfg-split && d=$(mktemp) && ./scripts/android-smoke.sh --emulator --pref-dump > "$d" && awk -F'\t' '$1=="browser.contentblocking.category" && $3=="strict" && $4=="locked" {ok=1} END{exit !ok}' "$d"
```

That is the exact line for the owner of `tasks.yaml` to paste; LW-M3-09 does not
own that file. It is POSIX `sh`-safe (`$(mktemp)`, no `pipefail` needed, no
bashism), and it is a plain YAML scalar — it neither starts with a quote nor
contains `": "` or `" #"`.

Reading it: `--check-cfg-split` still guards the conservation counts; the
redirect keeps the harness's own exit status in the `&&` chain, so exit 1 (a
failed check) and exit 2 (harness could not run) both stop the verify; and the
`awk` exits non-zero unless a row exists whose value is `strict` **and** whose
`locked` column says `locked`.

### Proof that it fails on a broken build

The whole complaint about the old line is that it passes either way, so the new
one was run both ways, end to end, on the same emulator, minutes apart:

| APK under test | what it is | proposed verify exits |
|---|---|---|
| arm **C** | `common + android` with this task's four lines deleted | **1** ✗ |
| arm **B** | `common + android`, the fix in | **0** ✓ |

and the assertion alone, replayed over every dump captured in this exercise:

```
arm A  -> 1      arm C  -> 1      arm C2 -> 1      arm D  -> 1
arm B  -> 0      arm B2 -> 0      arm B3 -> 0
```

Arm C is the honest negative control: it is not "an old build" or "a different
tree", it is this build with the fix reverted and nothing else changed.

### Two things the owner must decide with it

1. **It fails today on a `make`-built APK, and that is correct.** `make` ships
   arm A (LW-M3-10, below), where the pref reads `standard`. Do **not** resolve
   that with `depends_on: [LW-M3-10]` on this task — LW-M3-10 already declares
   `depends_on: [LW-M3-02, LW-M3-09]`, so that edge is a cycle and
   `board.py --check` would reject it. The two workable shapes are: run this
   verify against a hand-composed build via `--apk` until the composition lands
   (which is exactly what was done above), and/or put the same assertion on
   **LW-M3-10's** verify, where it will run against a `make`-built APK and prove
   that task's whole point in one line. What it must **not** do is go back to a
   form that passes on arm A.
2. **It hard-codes `locked`**, which is the disposition argued for below. If
   LW-M3-04 ever decides the ETP category selector must stay live, the
   disposition becomes `defaultPref` and the `&& $4=="locked"` clause has to go
   in the same change — otherwise the gate contradicts the shipped file.

A better long-term shape is a first-class assertion in the harness — e.g.
`--check-pref browser.contentblocking.category=strict:locked` — so that every
task with a pref claim stops open-coding `awk`. That is `android-smoke.sh`,
which belongs to LW-M2-07, and it is a suggestion, not a dependency of this task.

---

## Board items — for the owners of `board.py`, which this task does not own

### 1. `--check-cfg-split` rule C: **fixed, no action needed**

The first pass of this task reported that rule C errored on any pref present in
two fragments, which made the prescribed fix (`android.cfg` overrides
`common.cfg`) unsatisfiable at the same time as the gate. That has since been
fixed in `board.py:562-588`: an override across fragments is legitimate, the
error is now "the same fragment sets a pref twice", and a target fragment that
restates common's *construct and value* is a warning. `--check-cfg-split` exits 0
with all four promotions in place. Recorded here so nobody re-opens it.

### 2. `_gv_declared_prefs` cannot see the 36 `SafeBrowsingProvider` prefs

`board.py:641-662` matches `Pref<>("literal")`. `SafeBrowsingProvider` builds its
twelve names as `ROOT + mName + "…"` (`ContentBlocking.java:1815-1826`) for three
providers, so **36 GeckoView-declared names are invisible to `--check-policies`**,
and one of them — `browser.safebrowsing.provider.google4.dataSharingURL` — was a
*measured*, wrong, privacy-relevant value that consequently never made it into
`BARE_PREF_BACKLOG`. The ratchet was three names; it should have been four.

Fix: after the literal scan, add the cross-product of the provider names parsed
from `SafeBrowsingProvider.withName("…")` (`ContentBlocking.java:29,51,77`) with
the twelve suffixes at `:1815-1826`.

Worth a look from LW-M3-04 for the same reason: `common.cfg:371-374` ships four of
those names as `defaultPref` with **no `[ANDROID: LOCK]` marker**, and
`--check-policies` has never flagged them. They happen to hold (measured `""` on
all four arms, seven runs), but they held silently.

### 3. `BARE_PREF_BACKLOG` — what can be removed, and what must happen first

`board.py:59-63` holds three names. All three are fixed by this task, and all
three are still **warned about** by `--check-policies`, because that command
inspects `common.cfg` and `android.cfg` independently and cannot see that
`android.cfg` promotes the same name.

| name | fixed by | can leave `BARE_PREF_BACKLOG`? |
|---|---|---|
| `browser.contentblocking.category` | `lockPref` in android.cfg | **yes, once `--check-policies` treats an android.cfg promotion as the fix** |
| `devtools.console.stdout.chrome` | `defaultPref` in android.cfg | same |
| `devtools.debugger.remote-enabled` | `lockPref` in android.cfg | same |
| `browser.safebrowsing.provider.google4.dataSharingURL` | `defaultPref` in android.cfg | was **never in the set** — see item 2 |

Removing the three *without* teaching `--check-policies` about the override would
turn three warnings into three hard **errors** ("… and it is NOT in
`BARE_PREF_BACKLOG`, so it is new debt"), because the bare `pref()` in
`common.cfg` is deliberately still there. Order matters: teach the checker first,
shrink the ratchet second. The suggested one-liner: in the `kind == "pref"`
branch of `cmd_check_policies` (`board.py:745-758`), skip the pref when
`android.cfg` contains a `defaultPref`/`lockPref` for the same name.

---

## Adjacent findings — two that are not this task's, one that is unexplained

All three are outside the 24, and none of them changes a disposition above. The
first two are landmine **L2** — an unlocked `defaultPref` losing to a GeckoView
runtime writer, not L2b — and neither moves between any two arms, so this task
neither caused nor fixed them. The **third is not a consequence of this task's
category lock** — the `A-nokey` arm breaks the correlation the first write-up
claimed — but it is written up here rather than buried in a log precisely so the
unexplained name is on the record. Every value below was
**re-measured on this attempt's arms**, across all seven device runs, and none
is carried over from the first attempt.

### `privacy.trackingprotection.allow_list.convenience.enabled`

Shipped by `common.cfg:119` as `defaultPref(false)` with an `[ANDROID: LOCK]`
marker; reads **`true`** in **all seven runs, on all four arms** — so no
composition of the `.cfg` fixes it and nothing this task did moved it.
`ContentBlocking.java:588` declares it
with a Java default of `true`, and `GeckoProvider.kt:110-111` feeds it from
`settings.strictAllowListConvenienceTrackingProtection`. **Belongs to LW-M3-04**,
which owns the must-lock list; the marker is already on the line.

### `network.lna.block_trackers` — LW-M3-06's own prediction, now confirmed

`android.cfg:218` ships `defaultPref("network.lna.block_trackers", true)`
(`:202` in the first attempt's write-up — the line moved when that file's
comments were corrected; checked against the file as it stands today). On
arms B, C and D — where that very file is being evaluated, proven by
`media.eme.enabled` flipping against arm A — the pref reads **`false`**, in every
run.

The writer: `Core.kt:217` passes `lnaTrackerBlockingEnabled =
settings.isLnaTrackerBlockingEnabled` into `DefaultSettings`; GeckoEngine applies
it to `runtime.settings`, reaching `GeckoRuntimeSettings.setLnaBlockTrackers`
(`:2134`), which is `mLnaBlockTrackers.commit(enabled)` — a runtime
`GeckoView:SetDefaultPrefs`, after autoconfig. Fenix's default for that setting is
off, so our `true` is overwritten every launch.

`android.cfg`'s own comment on that line already said it was "ADVISORY until
LW-M3-08 settles whether autoconfig works". LW-M3-08 settled it, autoconfig
works, and the pref *still* loses — so the answer is a `lockPref`, and the
counter-argument recorded there ("a lockPref here would be STRICTER than desktop,
because the policy does not pass `Locked`") now has to be weighed against the
pref simply not taking effect at all. **This is LW-M3-06's line and LW-M3-04's
list; LW-M3-09 deliberately did not change it.**

### `privacy.restrict3rdpartystorage.url_decorations` — not a consequence of the category lock, and not explained

This one moved between the C and B arms, and the first write-up claimed it was
downstream of the category lock. That claim is **not supported**. The full arm
table, including the `A-nokey` arm that breaks the correlation:

| arm | four promotions | `browser.contentblocking.category` | `url_decorations` |
|---|---|---|---|
| A | — (desktop cfg) | `standard` | `fbclid` |
| **A-nokey** | — (arm-A content) | `standard` | **`""`** |
| C | none | `standard` | `fbclid` |
| C2 | none | `standard` | `fbclid` |
| D | three — **all but** the category lock | `standard` | `fbclid` |
| B, B2, B3 | all four | `strict` | **`""`** |

`A-nokey` is arm-A content — its packaged `librewolf.cfg` is byte-identical to
A's, `ok:true`/`tainted:false` — yet it dumped `url_decorations` **empty** with
`category` reading `standard`: the arm-B outcome on arm-A input. So
`url_decorations` does **not** track
`lockPref("browser.contentblocking.category", "strict")`, and arm D does not
isolate it. It is unexplained, and it is not this task's.

What is known about the mechanism, and it is not enough to call it explained:

- The pref's static default is `""` (`modules/libpref/init/all.js:836`), and the
  only writer is `URLDecorationAnnotationsService.onDataAvailable`
  (`toolkit/components/antitracking/URLDecorationAnnotationsService.sys.mjs:27-40`),
  which sets it on the **default** branch and locks it, from the Remote Settings
  collection `anti-tracking-url-decoration`, in an **async** `client.get({})`
  continuation kicked off at `profile-after-change`.
- That collection's packaged dump is **not in the Android `omni.ja`** — checked
  in arm B's APK, whose `defaults/settings/` holds only `blocklists/gfx`,
  `last_modified`, `main/doh-config`, `main/doh-providers`,
  `main/password-recipes` and `security-state/onecrl`. So `fbclid` cannot have
  come from the build; it can only have come **off the network**, from the live
  Remote Settings service that LW-M4-08 has not yet blocked.
- The value therefore looks like a timing race on that async fetch — but it is
  **not** a clean arm correlation: `A-nokey` shows the arm-B outcome on arm-A
  input, so it does not track the category lock, and the first write-up's
  "correlated perfectly across seven runs" reading is wrong.

Why it is not filed as a regression: the value is Mozilla's Remote Settings list,
not ours; and it will stop being reachable at all once LW-M4-08 lands. But
**the mechanism was not established here**, and this file is not claiming it is
harmless — it is claiming it is out of scope, reproducible, and now written down.
If anyone wants it closed, the experiment is one more arm plus a capture window,
not a rebuild.

---

## What this file does not prove

- **Nothing about a release build.** All four APKs are `debug`. Two of the
  measurements depend on that: `Config.channel.isDebug` makes
  `debugLogging(true)` unconditional, which is what made
  `devtools.console.stdout.chrome` visibly wrong in the first place. On a release
  APK the before-value would have been `false` already — the *fix* is still
  correct there (`defaultPref` on the default branch is unconditional), but the
  before/after delta would not show.
- **Nothing about the ETP screen.** `browser.contentblocking.category` was read
  on a fresh profile that never opened Fenix's tracking-protection settings. The
  claim that an unlocked `defaultPref` would die there is derived from
  `commit()`'s early-return, not observed; the claim that a `lockPref` survives
  it *is* observed, but for `devtools.debugger.remote-enabled` (LW-M3-08), not
  for this pref.
- **Nothing about the shipped build.** See the delivery gap above: `make` still
  puts `common + desktop` on Android. LW-M3-10 owns that.
- **Nothing about the other 158 calls** in `common.cfg`. This file is about the
  24 bare `pref()` calls only. `defaultPref` on a GeckoView-declared pref is
  landmine L2 and belongs to LW-M3-04 — the adjacent findings above are
  evidence that it is a live problem, not a theoretical one.
- **Nothing about a desktop *run*.** "Desktop is unchanged" is proved by input
  identity — the bytes desktop consumes are `cmp`-identical before and after,
  and arm A ships exactly those bytes — not by booting desktop LibreWolf and
  reading `about:config`. No desktop build was made for this task. If the
  project wants an effective-prefs comparison on desktop, that is a different
  experiment and nobody has run it.
- **Nothing about `about:config` as a UI.** Every value here came from
  `Services.prefs` over Marionette in chrome context. The acceptance line says
  "reads LibreWolf's value in about:config on Android"; what was measured is the
  pref service that page renders, on a build where `--check-aboutconfig`
  deliberately refuses to run (`SMOKE.md`: debug APK). Same value, one layer
  down; if someone insists on the page itself, that check is LW-M4-09's.
- **Nothing about a second emulator or a physical device.** One AVD
  (android-30/default, x86_64), one instance, seven runs. The first pass's
  numbers came from a different emulator and are not merged with these; where
  the two agree it is stated as agreement, not as replication.
