# Privacy baseline — measured on the shipping release build, 2026-08-21

First baseline measured on a build that **boots** (LW-M6-07 R8 fix) — every figure
this project quoted before was taken on a debug build. This record states what each
number was, what it is now, and which build each came from, and it records one
finding that contradicts the standing record.

## Build measured

- APK: `~/lw-m3-08/out/apk/fenix-x86_64-release.apk` (128,049,850 B, built 2026-08-21 19:23)
- Package: `org.mozilla.firefox`, release (R8), the only release build on this machine that boots
- libxul.so: 172,443,176 B (the "fresh" one the LW-M3-11 record says fixed autoconfig)
- Emulator: x86_64 AVD, `-gpu host`; first-run capture via `emulator -tcpdump` + `LW_SMOKE_PCAP`

## Before / after

| metric | standing claim (old) | old build | measured now | now build |
|---|---|---|---|---|
| first-run network events | 22-24 | debug, cfg never applied | **27** | release `lw-m3-08` |
| first-run hostnames | 4 (all Mozilla) | debug | **4** (all Mozilla) | release `lw-m3-08` |
| GMS dex strings | "removed" | debug | **1659 (PRESENT)** | release `lw-m3-08` |
| Adjust dex strings | "removed" | debug | **206 (PRESENT)** | release `lw-m3-08` |
| Glean | "removed" | debug | **PRESENT** (479 `GleanMetrics` + 610 `Glean`) | release `lw-m3-08` |
| `librewolf.cfg` loading | "loads (LW-M3-11)" | debug, 2026-08-21 | **NOT loading** | release `lw-m3-08` |

## Finding that contradicts the standing record

`docs/android/README.md` (2026-08-21) claims: *"Autoconfig works on Android: the
packaged librewolf.cfg loads… Glean, Adjust, Nimbus, Play Integrity… are removed.
First-run… 22-24 events… a floor that should drop now that LW-M3-11 is resolved."*

Measured on the shipping release build, all three fail:

1. **The cfg does not load.** `librewolf.cfg.version` (a cfg-only `lockPref`, value
   "8.6") is **missing** at runtime; the canary string is absent from the APK and from
   libxul.so. Every pref that *only* the cfg sets shows its default:
   `toolkit.telemetry.server = https://incoming.telemetry.mozilla.org` (cfg wants `data:,`),
   `app.update.auto` missing, `browser.safebrowsing.malware.enabled = true` (cfg wants false),
   `browser.safebrowsing.provider.google4.gethashURL` = Google URL (cfg wants ""),
   `privacy.trackingprotection.enabled = false` (cfg wants true), `dom.push.enabled = true` (cfg wants false).
2. **Glean / Adjust / GMS are not removed** — all present in the release dex (above).
3. **First-run is 27, not ≤22-24**, and it did not drop.

The prefs that *are* correct on this build (`browser.search.suggest.enabled=false`,
`toolkit.telemetry.enabled/unified=false`) are exactly the ones also set by the **code
patches** (`librewolf-0201`, `librewolf-0016/-0020`), not the cfg. So the shipping
build's privacy comes from the patch set, **not** from the configuration.

This does not touch the dated snapshots (HANDOVER §3 baseline-2026-08-20, the
README's 2026-08-21 lines); it records a new measurement that disagrees with them.
The LW-M3-11 "resolution" (`301bf26`) is contradicted here; the project's own
`8adb019` (14:58 that day) had already recorded `cfg_applied=false`,
`NS_ERROR_FILE_NOT_FOUND`, and "the README's claim that autoconfig works on Android
was wrong." A fresh build from current HEAD was **not** run this pass (time budget);
lw-m3-08 is already a same-day build made after the cfg/R8 fix commits, and it does
not package the cfg.

## Reproducing the numbers (rule 3)

Static (GMS / Adjust), no device needed:
```sh
./scripts/android-smoke.sh --check-no-gms --check-no-adjust \
  --sdk /home/mgysin/lw-m2-04/sdk --serial emulator-5556 \
  --apk /home/mgysin/lw-m3-08/out/apk/fenix-x86_64-release.apk
```
Glean (dex scan, same APK):
```sh
python3 /tmp/glean_scan.py   # needs driver.py on sys.path; needles GleanMetrics/Glean
```
First-run network capture (emulator must be started with `-tcpdump`):
```sh
LW_SMOKE_PCAP=/tmp/lw-firstrun-capture.pcap ANDROID_SDK_ROOT=/home/mgysin/lw-m2-04/sdk \
./scripts/android-smoke.sh --first-run-capture --serial emulator-5556 \
  --sdk /home/mgysin/lw-m2-04/sdk \
  --apk /home/mgysin/lw-m3-08/out/apk/fenix-x86_64-release.apk \
  --capture-seconds 90 --json /tmp/step1-firstrun.json
```
Runtime pref state incl. the cfg canary (Marionette, release app via `set-debug-app`):
```sh
python3 /tmp/cfg_probe3.py   # reads librewolf.cfg.version + cfg-only prefs, type/locked
```

## Refinement (later in the same run): the build ships a partial patch set

A follow-up pass established that lw-m3-08 is **not** built from the current
`assets/patches/android.txt`. It is self-consistent (the source tree and the APK
agree on every marker) but it applied a *partial* M4 set. So the "PRESENT" readings
above measure that build, not the current patch list:

| marker in the shipping APK dex | count | means |
|---|---|---|
| `GleanHelper` (Fenix Glean integration, no-glean's target) | **0** | no-glean **applied** |
| `com/adjust/sdk` (no-adjust's target) | 201 | no-adjust **not applied** |
| `com/android/installreferrer` (no-adjust's target) | 18 | no-adjust **not applied** |
| `com/google/android/gms` (no-gms's target) | 904 (1659 across all descriptor forms) | no-gms **not applied** |
| `com/google/android/gms/internal/fido` | 477 | the dominant GMS source is **FIDO/WebAuthn** |
| `com/google/firebase` | 182 | Firebase present |
| `com/google/android/play` | 84 | Play Integrity / Review present |

Consequences that change how the table above should be read:

1. **Glean:** "PRESENT" is the Glean *SDK* (`GleanMetrics`, glean-core), which
   `no-glean.patch` deliberately leaves in the dex — it removes the Fenix
   integration, not the SDK. `GleanHelper = 0` confirms **no-glean is effective**.
   This is not a no-glean failure.
2. **GMS / Adjust:** present because **no-gms / no-adjust were not in this build's
   patch set**, not because those patches are broken. This build therefore **cannot
   validate LW-M4-05 or LW-M4-02**, and it is a *different* build state than the "2
   residual GMS strings" that LW-M4-16 works from (here it is 904+/1659,
   FIDO-dominant, with `internal/fido` alone at 477).
3. **The cfg still does not load.** `librewolf.cfg.version` ("8.6") is a real
   `lockPref` in `settings/common.cfg:68` (and `settings/librewolf.cfg:68`), and it
   is absent at runtime. That finding stands on its own, independent of the
   partial-patch-set issue.

Reproduce the partial-set table (static, no device):
```sh
python3 - <<'PY'
import sys; sys.path.insert(0, "/home/mgysin/.cache/librewolf-android-smoke/harness")
import driver
apk = "/home/mgysin/lw-m3-08/out/apk/fenix-x86_64-release.apk"
s = list(driver.apk_dex_strings(apk))
for n in ["GleanHelper", "com/adjust/sdk", "com/android/installreferrer",
          "com/google/android/gms", "internal/fido", "com/google/firebase",
          "com/google/android/play"]:
    print(n, sum(1 for x in s if n in x))
PY
```

Net: the only booting build is (a) a partial patch set and (b) missing the cfg.
Establishing the true baseline and validating the GMS/Adjust removal tasks both
require a **fresh release build from current HEAD** (full `assets/patches/android.txt`
plus a working cfg). That build was not run in this pass.

## Bottom line for the rest of the run

Step 2 (LW-M4-05, strip GMS) and Step 3 (LW-M4-16, allowlist) must be done at the
**code/packaging** level, and the cfg will not close these gaps because it is not
loading. Both the GMS/Adjust readings and the cfg result were measured on a
partial-patch-set build, so **a fresh release build from current HEAD is the
prerequisite for validating any of them** — that build is the single highest-value
next step and is the one thing this pass did not produce.
