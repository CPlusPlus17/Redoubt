# 161.0-1 on a Pixel 9a (2026-11-25)

The signed release APK (`fenix-arm64-v8a-release.apk` from CI run 45650986628,
signed by the maintainer; `android-verify-signature.sh` PASS for all four ABIs,
every zip entry and CRC equal to the unsigned CI APK's, `latest.json.sig`
verified against `assets/update-check.android.pubkey`), on a Pixel 9a
(Android 17, API 37) reached through lugh's adb server. Harness:
`docs/android/evidence/launch-qa-2026-10-14/harness/drive.sh`, unchanged, as for
160.0-1.

## Static (`static-no-gms-no-adjust.json`)

`android-smoke.sh --check-no-gms --check-no-adjust` on the signed arm64 APK:
both PASS. 161's new Google Block Store dependency (`play-services-auth-blockstore`)
is not in the APK.

## Fresh install (`pixel9a-drive-log.txt`)

- Installed versionCode 2016198402, versionName 161.0-1-default.
- Isolation on: 4 `isolated_app` content processes after the Reddit pages
  (`processes-after-reddit.txt`).
- YouTube (m.youtube.com, Big Buck Bunny) plays: media session PLAYING with the
  position advancing (`youtube-playing.txt`, `media-session.txt`).
- Wikipedia, GitHub, BBC, Google, DuckDuckGo, Guardian load.
- Crash buffer empty, 0 FATAL/ANR lines, 0 isolation-media refusals.
- reddit.com/login stays on "Welcome to Reddit" (known limitation, as before).
- The local codec page (06) fails with "connection was reset": `adb reverse`
  lands on lugh's loopback (as for 158.0.1-1 to 160.0-1). Not run.

## Upgrade over the published 160.0-1 (`pixel9a-upgrade-quit-log.txt`)

- Installed the published `android-160.0-1` arm64 APK (sha256 checked against
  the release's SHA256SUMS.signed), opened Wikipedia, GitHub and BBC,
  force-stopped.
- `adb install -r` of 161.0-1: Success, versionCode 2016195650 -> 2016198402.
- After launch: 3 tabs, BBC in front (`pixel9a-after-upgrade.png`).

## Quit with "Delete browsing data on quit" (`delete-on-quit-logcat.txt`)

161 makes `MenuFragment` the only menu; `delete-on-quit-swipe` gained a hunk for
it (REBASE.md). The setting was on after the upgrade (cookies + cache, the
default); open tabs and browsing history were added
(`pixel9a-delete-on-quit-setting.png`). Then menu -> Quit Redoubt, three times:

- Every Quit logs `quit: deleting TABS,HISTORY,COOKIES,CACHE`, so the Quit path
  reaches `DeleteOnQuitGuard` on 161.
- Runs 2 and 3: `quit: deletion confirmed; marked clean`.
- Run 1, the first Quit after the upgrade: the engine's
  `tracking-protection-data` clear failed
  (`GeckoView:TrackingDB:ClearAll` QueryException), so Quit logged
  `deletion incomplete (app=true engine=false); marker stays unclean`. The
  task-removal pass that `finishAndRemoveTask()` triggers 0.1 s later cleared
  everything, tracking data included, and wrote `marked clean`. Had it not, the
  next cold start would have repeated the deletion (fail-safe direction).
- Every following cold start: `cold start: no deletion (last session ended with
  Quit); marker was clean/0`, and 0 tabs (`pixel9a-after-quit-cold-start.png`).

## Widevine (`widevine-log.txt`, `pixel9a-widevine-playing.png`)

DRM-controlled content was Blocked by default and set to Allowed in Site
settings. Shaka Player demo (v5.3.6, shaka-project.github.io), Angel One
(Widevine): the CDM is created from Redoubt's RDD process on the L1 (Trusty)
Widevine HAL, and the stream plays to the end of the clip, media session
PLAYING from 1.0 s to 58.1 s, then ended at 59.8 s. One run, not the 158.0-3
DRM flow (Ask/Blocked/first-play matrix).

Crash buffer empty and 0 FATAL/ANR lines over the upgrade, Quit and Widevine
session (`upgrade-crash-buffer.txt`). Redoubt was uninstalled afterwards.

## Not done

The emulator acceptance suite (SMOKE.md, `--check-video`, `--check-eme`), the
158.0-3 DRM matrix on API 31-34 and a real local-network permission prompt were
not run.
