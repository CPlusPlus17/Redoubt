# Handover

Written 2026-08-20 for whoever picks this up next, human or agent.

This supersedes [`STATUS.md`](STATUS.md) on every number. That file is a 2026-08-18
snapshot taken at an API outage and its counts (82 tasks, 72 patch files, 2 android
cfg calls) are stale. It is kept because its *narrative* — particularly "landed is
not verified" — is still the single most important thing on this project.

---

## 1. Read these first, in this order

| file | why |
|---|---|
| [`IDENTITY.md`](IDENTITY.md) | what this project may call itself, and what it may not. Read before touching any user-visible string. |
| [`AGENTS.md`](AGENTS.md) | the working agreement: how to claim a task, file ownership, the five landmines, definition of done. |
| this file | current state, open blockers, the ways work has actually failed here. |
| [`tasks.yaml`](tasks.yaml) | the board. 88 tasks. Source of truth. |

Do not start work before reading `AGENTS.md`'s landmine section. Every one of L1–L5
describes a failure that already happened here, not a hypothetical.

---

## 2. Where things are

    Redoubt            github.com/CPlusPlus17/Redoubt
      android-port     b6e4d73   ← all the work
      main             71177a3   ← LibreWolf upstream, unmodified

    Redoubt-settings   github.com/CPlusPlus17/Redoubt-settings
      redoubt          44555dd   ← the cfg split; the submodule points here
      master                     ← LibreWolf's settings, for merging

Both repos carry the tag **`baseline-2026-08-20`** at those commits. Every gate
listed in §3 was green on a fresh `git clone --recursive` at that tag. If a gate is
red, it is something changed after the tag, not something inherited.

Both repos use the same remote layout:

    origin    → the Redoubt fork      (fetch + push)
    upstream  → librewolf.dev         (fetch only)
    upstream  → DISABLED_use_origin   (push URL, deliberately broken)

`upstream`'s push URL is disabled on purpose. It used to be `origin`, and a
reflexive `git push` would send a fork's branches into LibreWolf's repository.
Do not re-enable it.

---

## 3. Gates

Run all of these. They are cheap except the last.

```sh
python3 docs/android/board.py --check           # board integrity
python3 docs/android/board.py --check-scope     # patch lists vs PATCH-SCOPE.md
python3 docs/android/board.py --check-cfg-split # librewolf.cfg regenerates from fragments
python3 docs/android/board.py --diff-mozconfig  # no hardening flag silently dropped
LW_TREE=firefox-153.0.4 python3 docs/android/board.py --check-policies
python3 scripts/lint-patch-scope.py
python3 scripts/check-patch-order.py
./scripts/check-patchfail.sh                    # desktop; needs the tarball, ~minutes
```

Verified green at `baseline-2026-08-20`:

    --check            88 tasks, 17 waves, 0 warnings
    --check-scope      78 patch files — 24 common, 36 desktop, 18 android
    --check-cfg-split  182 common / 85 desktop / 6 android; regenerates exactly
    --diff-mozconfig   hardening parity holds, 0 documented differences
    --check-policies   101 GeckoView-declared prefs, 24 shipped by us, all acknowledged
    lint-patch-scope   76 files, no scope violations
    check-patch-order  11/11 constraints, 51 shared-file pairs classified
    check-patchfail    desktop: all patches applied
    check-patchfail    android --use-desktop-tarball: 40 patches, all applied (indicative)

`--check-policies` emits three warnings. They are the known `BARE_PREF_BACKLOG` in
`board.py` — `browser.contentblocking.category`, `devtools.console.stdout.chrome`,
`devtools.debugger.remote-enabled` — shipped as bare `pref()` on the user branch,
which `GeckoView:ResetUserPrefs` wipes. That is landmine **L2b** and it belongs to
LW-M3-09. Warnings, not failures; do not silence them.

`check-patchfail --targets=android` needs the **ESR** tarball, which is not on this
machine (`make fetch TARGETS=android`, 766 MiB). Without it the script exits 1 with
an explanatory message — that is a missing artefact, not a patch failure. The
indicative form is `--targets=android --use-desktop-tarball`.

---

## 4. The thing to internalise: landed is not verified

A patch that applies, is correctly scoped, and passes every gate has proved only
that it applies, is correctly scoped, and passes every gate. It has **not** proved
that the thing it removes is gone from the built artefact.

This is why M4's acceptance criteria demand a dexdump or a network capture rather
than a grep over sources. Transitive Gradle inclusion survives deleting a
dependency's usages. Honour that; do not substitute source inspection for it.

The sharpest instance so far, and it is worth understanding in full:

> LW-M4-16 reported a release artefact "provably zero-GMS" because
> `--check-no-gms` exits 0 on it. It does exit 0 — **because R8 deleted the
> classes.** The gate was green on that artefact for precisely the reason the
> artefact cannot ship: it crashes on launch. See LW-M6-07.

---

## 5. Open blockers, ranked

### LW-M6-07 — the R8 release build does not boot. **Release blocker.**

```
FATAL EXCEPTION: main
java.lang.Error: Structure.getFieldOrder() on class
org.mozilla.experiments.nimbus.internal.RustBuffer$ByValue does not provide
enough names [0] ([]) to match declared fields [3] ([capacity, data, len])
  at com.sun.jna.Structure.getFields(r8-map-id-7758…:144)
```

**Root cause, corrected 2026-08-21 by LW-M6-07 and evidenced.** The first
diagnosis in this file said R8 renames the JNA field names. It does not. R8 strips
the `@com.sun.jna.Structure.FieldOrder` *runtime annotation* from the
uniffi-generated `RustBuffer` classes, so `getFieldOrder()` reads it back empty.

The underlying defect is one level deeper:
`third_party/application-services/build-scripts/component-common.gradle` declares
`consumerProguardFiles "$appServicesRootDir/proguard-rules-consumer-jna.pro"`, and
**that file is absent from the Firefox source tarball** — confirmed by `tar -tJf`
against firefox-153.0esr and by a built AAR whose `META-INF/` contains no
`proguard.txt`. So the in-tree Nimbus AAR ships with no consumer ProGuard rules,
R8 runs against it with only fenix's own rules, and the app dies on first
`RustBuffer` use. The fix restores the file the build already points at.

Nobody caught it because **every APK this project has built is
`fenix:assembleDebug`** — `assembleRelease` appears nowhere in
`scripts/android-apk.sh` — and the two release APKs that exist were built with
`-PdisableOptimization`, i.e. R8 off. The configuration we would ship has never
booted, and the smoke harness has never run against it.

Consequence beyond the crash: **every measurement on this project describes a build
we would not ship.** The parity statement, the zero-GMS claim and the first-run
traffic capture all need re-deriving against a booting release build. Treat "the
release variant boots and passes the smoke harness" as the gate before M6 starts.

### LW-M4-16 — the proposed GMS allowlist is broken, twice over

A verifier built an APK from androidx.activity **1.8.2** — the version where
`getGmsPicker` is live code handing off to the Play Services photo picker — and
found that the live path references no `gms` descriptor at all; the two allowlisted
strings are its only trace. So the unmodified gate correctly fails that artefact
while the proposed allowlist passes it. A dependency downgrade would silently turn
GMS back on with the gate green.

Harden it before adopting: assert no `getGmsPicker` member, or pin the
androidx.activity version. The verifier also ran a positive control showing the
allowlist is not vacuous — the blind spot is exactly one case, and it is the
historically real one.

### Three verdicts never read in detail

Batch 9 returned `claims_hold=false` for **LW-M3-03**, **LW-M3-09** and
**LW-M4-12** (majors 1, 1, 2). LW-M4-16 and LW-M6-07 were handled first and these
findings were never opened. Read them before re-running any of the three; the
work may be sound and the claim merely overstated, or not.

### Known-open, not blockers

- **LW-M3-10 — LANDED (75026bc).** The patcher now composes `common.cfg` +
  `android.cfg` for android-only targets; desktop and desktop+android runs keep
  the checked-in composition (byte-identical to `settings/librewolf.cfg`).
  **But see the next item: the cfg is packaged yet never loaded on Android.**
- **NEW — the Android cfg is packaged into omni.ja but never applied at
  runtime.** Discovered while verifying LW-M3-10: the built-in `librewolf.cfg`
  (common+android, 59867 B) is present in the APK's omni.ja at
  `defaults/autoconfig/librewolf.cfg`, and `prefcalls.js` is alongside it, but
  the running build's prefs sit at their *built-in* defaults — 72 of 147
  `common.cfg` prefs mismatch a `--pref-dump` (e.g. `app.support.baseURL`
  ships librewolf.net, runs mozilla.org; `browser.cache.disk.enable` ships
  false, runs true), and every android.cfg decision is inert
  (`media.eme.enabled` runs true, not false; `network.lna.block_trackers` runs
  false, not true).
  **Root cause (corrected 2026-08-21, evidenced from running builds):** the
  earlier filing blamed `autoconfig.properties` for a missing `pref.default=`
  entry. That was wrong — `autoconfig.properties` is a *localization* file and
  has no `pref.default=` on any platform. The selector is
  `defaults/pref/local-settings.js`, which IS present in both APKs' omni.ja
  and DOES set `general.config.filename = librewolf.cfg` at runtime. The
  actual failure is one step later: `openAndEvaluateJSFile("librewolf.cfg",
  0, true, true)` returns **`NS_ERROR_FILE_NOT_FOUND` (0x80520012)** on BOTH
  the debug and the release APK. MOZ_LOG=MCD:5 captured from both builds
  (via the GeckoView debug-config `env:` injection) shows the identical three
  lines:
  ```
  D/MCD general.config.filename = librewolf.cfg
  D/MCD evaluating .cfg file librewolf.cfg with obscureValue 0
  D/MCD error evaluating .cfg file librewolf.cfg 80520012
  ```
  followed by the `Autoconfig is sandboxed by default` warning. Notably there
  is **no `opened ...: 0x%` line** — that `MOZ_LOG` sits immediately after
  `channel->Open` in the `resource://` branch of
  `openAndEvaluateJSFile`, so its absence means the code either never reached
  `channel->Open` or took the filesystem branch
  (`NS_NewLocalFileInputStream`, which is the path that produces
  `NS_ERROR_FILE_NOT_FOUND` when the file is absent from the directory
  `NS_GetSpecialDirectory(NS_GRE_DIR)` resolves to on Android). The definitive
  LW-M3-08 proof (`lockPref("librewolf.cfg.version","8.6")` canary +
  `defaultPref` checks) returns `cfg_applied: false` on both builds: the
  canary is unset and no `lockPref` from the `.cfg` is active. This is
  pre-existing (independent of the LW-M3-10 composition) and means **every
  M3 android.cfg / common.cfg decision that depends on the built-in cfg is
  unproven on a running build** — the M4 privacy re-derivation must treat
  cfg-gated prefs as open until this is fixed.
- **LW-M4-08** — Remote Settings still reaches the network. `rs-blocker.patch`
  only touches the JS stack; Fenix uses the Rust `RemoteSettingsService`, so this
  needs a Rust-side change.
- **LW-M4-12** — the UI still says "Firefox".
- **CI does not run.** `.forgejo/workflows/android-test.yaml` is not a path GitHub
  Actions reads, and it also declares `runs-on: epsilon` (LibreWolf's self-hosted
  runner) and a `codeberg.org/librewolf/bsys6` container. It will not fail; it
  will simply never execute. Porting it costs 766 MiB of download per run, which
  is a decision for the repository owner. Two of its comments are stale: the
  patch-scope lint is still wrapped in `|| warning` "until LW-M1-01 lands", and
  LW-M1-01 has landed.

---

## 6. Hard rules

Breaking any of these is expensive or irreversible.

1. **Never push to `upstream`.** Its push URL is deliberately broken. Leave it.
2. **Never bump the settings submodule pointer without pushing the submodule
   commit first.** The parent records a SHA, not content. A pointer to an unpushed
   commit is a repository nobody else can clone.
3. **Never `git submodule update` with uncommitted work in `settings/`.** That is
   how ~1650 lines nearly vanished on 2026-08-20. Commit inside the submodule
   first; it is a real repository with its own branch (`redoubt`).
4. **Do not weaken an acceptance criterion to make a task pass.** `tasks.yaml` is
   both the spec and an editable file, which makes this the cheapest possible
   cheat. Refining a task's `what` is normal; changing its `acceptance` or `verify`
   in the same commit that claims the task done is not. `AGENTS.md` forbids
   softening the parity wording specifically.
5. **Do not rename inherited code identifiers.** `settings/librewolf.cfg`,
   `scripts/librewolf-patches.py`, the `librewolf.*` prefs, the `LW-*` task ids and
   the `librewolf-android-*` build output paths stay. They are code, not branding —
   see `IDENTITY.md`. The output paths are also covered by the existing
   `/librewolf-*` gitignore rule; renaming them would leave build artefacts visible
   as untracked files.
6. **`<PROJECT_ID>` is a one-way door.** Changing an `applicationId` after release
   makes a different app to Android: no upgrade path, no data migration, every user
   reinstalls by hand. It is still a placeholder on purpose.
7. **Do not commit `.nodeterm/`, `__pycache__/`, build trees or tarballs.** They
   are gitignored; keep it that way.

---

## 7. Environment

**Disk is a live constraint.** `/home` is 1.7 T, 570 G free, 66 % full. A Gecko
build tree is ~40 G and there are already about thirty of them.

**~700 GB of agent working directories live in `~/lw-*` and none of it is in git.**
Most is regenerable build trees — expensive in hours, not irreplaceable. The small
ones are the *evidence* behind the board's claims and cannot be regenerated without
redoing the work:

    ~/lw-m4-09/evidence   2.1 G   the R8 release-crash logcat — the only record of LW-M6-07
    ~/lw-m4-16/evidence    70 M   the 63,646-class dexdump behind the GMS analysis
    ~/lw-m4-15/evidence   279 M
    ~/lw-integ-parity      56 K
    ~/lw-m3-08-verify     224 K
    ~/lw-m4-16b            52 K

A `make clean`, a `rm -rf ~/lw-*`, or two more Gecko builds filling the remaining
570 G would destroy them. Claims like "provably zero-GMS" currently have no durable
citation anywhere in the repository.

**No signing key exists on this machine** — no GPG secret key, no SSH key — against
a global `commit.gpgsign = true`. Every commit in both repositories is therefore
unsigned, made with `git -c commit.gpgsign=false` rather than by persisting a
repo-local override. The author is `Manuel Gysin <manuel.gysin@protonmail.com>`,
where the name was inferred from the email address and has not been confirmed.

**Build inputs present:** `firefox-153.0.4.source.tar.xz` (767 M) and the extracted
`firefox-153.0.4/` (4.7 G) — the *desktop release* tree. The **ESR** tarball that
`--targets=android` wants is not here.

---

## 8. Decisions that need the human

Five tasks are marked `agent_safe: false` and must not be executed autonomously:

    LW-M4-07  Apply Redoubt branding and choose the applicationId
    LW-M6-01  Generate the Android signing key and write the custody policy
    LW-M6-03  Set up the Redoubt F-Droid repository
    LW-M6-04  Publish to Accrescent and provide direct APK plus Obtainium metadata
    LW-M7-06  Run a closed beta before the public release

Two placeholders remain unresolved and are greppable:

    <PROJECT_ID>       the Android applicationId — one-way, needed before the first public build
    <PROJECT_DOMAIN>   the download and parity-statement site

The current build still ships as `org.mozilla.fenix.debug`. That is Mozilla's
namespace *and* it collides with a real Firefox install on device. It must change
before anything is published.

---

## 9. How work has actually failed here

Not hypotheticals. Each of these happened, and the pattern repeats.

- **Verify commands that cannot fail.** Five M1 tasks used `grep -qv`, which
  succeeds on the first non-matching line and therefore always passes. If you write
  a `verify`, run it against a tree where it *should* fail and confirm that it does.
- **Gates that fail open.** `check-patchfail.sh` discarded the patch exit code and
  detected only `.rej` files, so it reported success when a patch's target file was
  missing entirely. That is landmine L5, and it was live in LibreWolf's release
  builds. Fixed here; see [`UPSTREAM-REPORTS.md`](UPSTREAM-REPORTS.md).
- **Error paths that were never executed.** `board.py` twice shipped
  `NameError: name 'warns' is not defined` in branches that had never run — in the
  very tool whose job is catching that class of bug.
- **Escape hatches wide enough to drive through.** `--diff-mozconfig` once accepted
  a missing hardening flag if its name appeared in any comment; deleting `-fwrapv`
  merely warned. It now requires an explicit `MOZCONFIG-OMIT:` marker.
- **Confidently wrong conclusions from green gates.** See §4.
- **Remedies broken by the first real artefact.** LW-M4-16's proposed allowlist has
  now been broken twice, both times by building an actual APK rather than reasoning
  about it.
- **Documentation drifting from the checker it describes.** `AGENTS.md` claimed
  "five pairs" while the checker enforced nine; `check-patch-order.py`'s header
  claimed rows were missing that were present, so acting on it would have added
  duplicates. Both are now synced — keep them so.

The common thread: on this project the failures are quiet. A build with the WebGL
bug (landmine L1) installs, browses, and passes any smoke test that does not
specifically check for a live WebGL context. Assume anything unmeasured is broken.

---

## 10. Suggested next steps

1. Read the three unread batch-9 verdicts (LW-M3-03, LW-M3-09, LW-M4-12).
2. LW-M6-07 — teach `scripts/android-apk.sh` to build a release variant, add the
   JNA/uniffi keep rules, boot it, run the smoke harness against it.
3. Re-derive the M4 measurements against that booting release build.
4. Harden LW-M4-16's allowlist, or reject it.
5. LW-M3-10 — wire the cfg fragments into `librewolf-patches.py` so Android stops
   shipping the desktop pref composition.

Before any of it: run the gates in §3 and confirm you are starting from green.
