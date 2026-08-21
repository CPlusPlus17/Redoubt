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

## Bottom line for the rest of the run

Step 2 (LW-M4-05, strip GMS) and Step 3 (LW-M4-16, allowlist) must be done at the
**code/packaging** level — the cfg will not close these gaps because it is not loading.
