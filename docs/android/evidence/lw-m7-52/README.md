# LW-M7-52: release 158.0.1-1 (Firefox 158.0.1 + the Android 158.0.2 OneCRL fix)

Owner, 2026-10-26: "Release 158.0.2 (OneCRL backport) can go now: a preflight first,
then mode=full with a build_date later than the last release's."

## What Mozilla released

| Release | Date | Advisory | Watcher issues |
|---|---|---|---|
| Firefox 158.0.1 | 2026-10-20 | MFSA 2026-111: CVE-2026-113399 (high, SVG), CVE-2026-113470 (high, OneCRL), CVE-2026-113400 (moderate, cubeb), CVE-2026-113401 (low, PDF viewer) | #6, #7 |
| Firefox for Android 158.0.2 | 2026-10-21 | MFSA 2026-116: CVE-2026-113470 (high) | #8, #9 (duplicate) |

`firefox-158.0.2.source.tar.xz` does not exist (404 on 2026-10-26, as when #8 was
opened). GitHub compare `FIREFOX_158_0_1_RELEASE...FIREFOX-ANDROID_158_0_2_RELEASE`
in mozilla-firefox/firefox: ahead 2, behind 0, namely the version bump (6858d1b262)
and bug 2084311 (`08d23041955657e661eef22c8fdc967735300233`, "ensure OneCRL bundle
is loaded at init"): `security/manager/ssl/RemoteSecuritySettings.sys.mjs` (+22) and
an xpcshell test. Redoubt keeps `security-state/*` remote settings
(`settings/android.cfg`), and no Redoubt patch touches the file, so the fix reaches
Redoubt.

## What this release does

- `version.android` / `version` 158.0 -> 158.0.1, `release.android` 3 -> 1 (desktop
  `release` stays 1).
- `patches/android/onecrl-bundle-backport.patch`: the code hunk of bug 2084311,
  byte-identical to upstream's (`diff` of the patch body against the code part of
  `upstream-bug2084311.patch`: no difference). Upstream patch sha256
  `2ecebdafe90b8682924a481e49c9da8456333813ecccc88e4cb1c6f44f92857c`.
- The versionName is 158.0.1-1 (the tree is 158.0.1); the notes say it carries the
  158.0.2 fix. 158.0-3 (DRM, accepted 2026-10-16) was never published, so its work
  ships here first.

## Gates (release VM, 2026-10-26)

- Tarball `firefox-158.0.1.source.tar.xz`, sha256
  `b5beff55fa73a29a674a867da5922f5d7699f51e351e6bbe4405fcc4ba55a824`, `VALIDSIG`
  by `14F26682D0916CDD81E37B6D61B7B526D98F0353` (same sha as the watcher's patch check
  on #6).
- `check-patchfail.sh --targets=android`: 74 patches, all apply
  (`gates/patchfail-android.out.gz`); desktop: all apply
  (`gates/patchfail-desktop.out.gz`).
- `board.py --check`, `--check-scope` (118 listed: 22 common, 44 desktop,
  52 android), `check-patch-order.py` (40/40), `lint-patch-scope.py` (119 files): OK.
- `scripts/tests`: 9 of 19 pass. The other 10 fail identically on unchanged main
  e2512252 on this VM: no `node`, no local APK/gradle outputs, and the same 7
  `PatchcheckEndToEnd` failures in `test-firefox-release-watch.py`. Not caused by
  this change; not run here.
- Builder preflight: run 40329983075, green.
- Not done on this VM: compile (the CI build is the compile gate) and device
  acceptance (no SDK/emulator).

## Device check after publishing (2026-10-26, Pixel 9a, Android 17, USB)

Owner: "go" (device test of the published build). Phone reached through the
adb server on lugh. Files: `device/`.

- **Fresh install** of the published arm64 APK (sha256 `c9b51a8c…e227`, the same
  file F-Droid serves), with the 2026-10-14 harness (`launch-qa-2026-10-14/harness/drive.sh`):
  versionName `158.0.1-1-default`, versionCode 2016192618. Content runs as
  `isolated_app` (5 processes). Reddit, YouTube, Wikipedia, GitHub, BBC, Google,
  DuckDuckGo and the Guardian load. On YouTube the video plays (a mid-film frame of
  Big Buck Bunny, media session active). Crash buffer empty; 0 FATAL/ANR lines.
- **Not run:** the local codec page (H.264/VP9/AV1 frame counts). `adb reverse`
  points at lugh's loopback, not this VM's, and the phone cannot reach the VM over
  Wi-Fi, so the page got "connection was reset".
- **Upgrade:** published 158.0-2 (arm64, checked against its SHA256SUMS.signed),
  two tabs opened, then 158.0.1-1 installed over it with `install -r`:
  firstInstallTime kept, both tabs restored, no crash.
- Uninstalled afterwards; the phone has no Redoubt installed, as before.
