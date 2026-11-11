# 160.0-1 on a Pixel 9a (2026-11-11)

The signed release APK (`fenix-arm64-v8a-release.apk` from CI run 42984990898,
signed by the maintainer; `android-verify-signature.sh --unsigned-dir` PASS for
all four ABIs), on a Pixel 9a (Android 17, API 37) reached through lugh's adb
server. Harness: `docs/android/evidence/launch-qa-2026-10-14/harness/drive.sh`,
unchanged, as for 158.0.1-1 (`lw-m7-52/device/`).

## Fresh install (`pixel9a-drive-log.txt`)

- Installed versionCode 2016195650, versionName 160.0-1-default.
- Isolation on: 4 `isolated_app` content processes after the Reddit pages
  (`processes-after-reddit.txt`).
- YouTube (m.youtube.com, Big Buck Bunny) plays; media session active
  (`pixel9a-youtube-playing.png`, `media-session.txt`).
- Wikipedia, GitHub, BBC, Google, DuckDuckGo, Guardian load.
- Crash buffer empty, 0 FATAL/ANR lines, 0 isolation-media refusals.
- reddit.com/login stays on "Welcome to Reddit" (known limitation, as on
  158.0.1-1 and 159.0.1-1).
- The local codec page (06) fails with "connection was reset": `adb reverse`
  lands on lugh's loopback, not this VM's (same as 158.0.1-1). The H.264 /
  VP9 / AV1 local matrix was not run.

## Upgrade over the published 159.0.1-1 (`pixel9a-upgrade-log.txt`)

- Installed the published `android-159.0.1-1` arm64 APK (sha256 checked against
  its SHA256SUMS.signed), opened Wikipedia, GitHub and BBC, force-stopped.
- `adb install -r` of 160.0-1: Success, versionCode 2016194826 -> 2016195650.
- After launch: 3 tabs, BBC in front (`pixel9a-after-upgrade.png`).
- about:config after the upgrade: `network.lna.enabled`, `network.lna.blocking`,
  `network.lna.block_trackers` true and locked
  (`pixel9a-about-config-lna-enabled.png`);
  `network.http.akamai_waf_telemetry.enabled` false;
  `app.support.baseURL` `https://support.librewolf.net/`.
- Crash buffer empty, 0 FATAL/ANR lines.

## Not done

The emulator acceptance suite (SMOKE.md, `--check-video`, `--check-eme`) and a
real local-network permission prompt were not run.
