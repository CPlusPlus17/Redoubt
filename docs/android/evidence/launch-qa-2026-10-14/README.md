# Launch QA, 2026-10-14: the signed 158.0-2 release on two phones

The first run of a **signed release APK** on physical phones. Everything before
this (the per-release acceptance in `lw-m7-01/`) ran on x86_64 emulators, and the
maintainer's Pixel 10 Pro test in LW-M7-50 used a development build.

Run by an agent over adb with the maintainer's approval. The APK was installed
fresh, tested, and uninstalled again on both phones.

## What was installed

- `fenix-arm64-v8a-release.apk` from the GitHub release `android-158.0-2`, downloaded
  anonymously. `sha256sum -c --ignore-missing SHA256SUMS.signed`: OK. `apksigner`:
  one signer, certificate SHA-256 `6414eb33…1283bd0` (the published key), v2 and v3, no v1.
- versionCode 2016190290, versionName `158.0-2-default`.

| phone | Android | SoC era | RAM |
|---|---|---|---|
| Google Pixel 9a | 17 (API 37) | 2025 | 7.5 GB |
| Xiaomi Mi 8 | LineageOS, Android 15 (API 35) | 2018 | 5.8 GB |

Both are Android 12 or newer, so both take the isolated-content path of 158.0-2.

## Results

| check | Pixel 9a | Mi 8 |
|---|---|---|
| install, first start, uBO sheet | OK | OK |
| content processes (`u:r:isolated_app`) | 4, then 6 as tabs opened; no separate app-zygote process (Android 17 logs `ExecSpawning: skipping Java ZygotePreload`) | 7, then 8, plus the app zygote (`u:r:app_zygote`) |
| 1080p H.264 + AAC, 10 s | 299 frames, 0 dropped | 299 frames, 0 dropped |
| 720p VP9 + Opus | 300, 0 dropped | 300, 0 dropped |
| 1080p VP9 + Opus | 300, 0 dropped | 300, 0 dropped |
| 1080p AV1 + Opus | 300, 0 dropped | 300, 0 dropped |
| YouTube (m.youtube.com, Big Buck Bunny) | page loads, plays after a tap (media session active) | page loads; YouTube's own "Get the best experience" dialog covered the player |
| Wikipedia, GitHub, BBC News, Google, DuckDuckGo, The Guardian | render | render |
| memory, ~15 tabs opened in a row (`dumpsys meminfo`, Redoubt processes) | 1,942 MB PSS over 10 processes | 1,289 MB PSS over 11 processes |
| crash buffer, `FATAL EXCEPTION`, `Fatal signal`, ANR | none | none |
| **reddit.com/login** | **blank** | **blank** |

The video clips are synthetic (ffmpeg `testsrc2` with a sine tone, 30 fps). They
show that decoding works and keeps up on real hardware. They are not a battery
measurement. `mozRequestDebugInfo()` is not exposed to web content, so the page
could not name the decoder; the process layout matches the emulator acceptance
(`lw-m7-01/release-158.0-2/acceptance/`, rows I1-I4).

Files: `video-results.jsonl` (what the test page reported), `<phone>/log.txt` (the
driver's log, with the UI text it saw), `<phone>/processes-*.txt` (SELinux labels),
`<phone>/meminfo-redoubt.txt`, `<phone>/crash-buffer.txt` (empty).

## reddit.com/login stays blank

On both phones, `https://www.reddit.com/login/` stays white:

- on a cold first start straight into the URL, after 30 and 60 seconds;
- after `https://www.reddit.com/` has loaded and rendered;
- `https://old.reddit.com/login` too.

The page's title is "Welcome to Reddit", and Reddit's own script runs in the
isolated content process: with content console output sent to logcat, it logs
`Navigation listeners online` (`reddit/console-stdout.txt`) and no console error.

Changed one after another on the Pixel 9a, cumulatively, in one session. None
of these made the page render:

1. tracking protection off for the site (the panel had blocked one cross-site
   cookie from `www.google.com`);
2. WebGL allowed for www.reddit.com (the page had asked for WebGL, and it was
   blocked silently because "Hide WebGL popup" is on by default);
3. resist-fingerprinting off (`privacy.resistFingerprinting` false in about:config);
4. uBlock Origin disabled;
5. "Desktop site".

Once, right after WebGL was allowed with tracking protection off, Reddit served
its "Prove your humanity" reCAPTCHA page
(`reddit/pixel9a-once-recaptcha-webgl-allowed-etp-off.png`). It did not happen
again with the same settings and fresh URLs. The project's earlier notes
(`lw-m7-42/autofill-shadow-dom/README.md`) record that stock Firefox 157 rendered
the page on the same emulator, so something Redoubt-specific is involved.

Next step: a debuggable build with remote devtools on that page (network panel
and DOM), which the release build does not allow.

## Also seen

- Settings → About lists **"Rate on Google Play"**, a Firefox leftover in an app
  that is not on Google Play.
- The site-information panel ("Redoubt is on guard") shows Firefox's fox
  illustration, which is Mozilla branding; `--check-strings` covers text, not images.
- On the home screen in dark mode, the fort logo next to "Redoubt" is dark grey on
  dark blue and barely visible.

## Harness

`harness/` holds the scripts as run: `drive.sh` (one phone: install, Reddit, process
labels, the local video page, YouTube, six sites, meminfo, crash checks,
uninstall), `server.py` (serves `video.html` and the clips on 127.0.0.1 through
`adb reverse`, records the page's reports), `video.html`, `tap_text.py` and `ui.py`
(uiautomator helpers). The clips were made with:

    SRC="-f lavfi -i testsrc2=s=1920x1080:r=30:d=10 -f lavfi -i sine=f=440:r=48000:d=10"
    ffmpeg $SRC -map 0:v -map 1:a -c:v libopenh264 -b:v 6M -g 30 -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart h264-1080p.mp4
    ffmpeg $SRC -map 0:v -map 1:a -c:v libvpx-vp9 -b:v 4M -deadline realtime -cpu-used 8 -row-mt 1 -g 60 -pix_fmt yuv420p -c:a libopus -b:a 96k vp9-1080p.webm
    ffmpeg $SRC -map 0:v -map 1:a -c:v libsvtav1 -preset 10 -b:v 3M -g 60 -pix_fmt yuv420p -c:a libopus -b:a 96k av1-1080p.webm

(and `vp9-720p.webm` the same at 1280x720, 2M). Full logcats are not kept here:
they contain other apps' logs.
