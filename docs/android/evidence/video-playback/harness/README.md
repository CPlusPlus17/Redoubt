# `--check-video` with H.264 fixtures: fails on 157.0-2, passes on the fix (LW-M7-43)

`scripts/android-smoke.sh --check-video` now reports three rows: `video` (VP8 + Opus
WebM, unchanged), `video-h264` (progressive H.264 + AAC MP4) and `video-mse`
(`MediaSource.isTypeSupported('video/mp4; codecs="avc1.42E01E,mp4a.40.2"')` must be
true, and a fragmented MP4 appended through a SourceBuffer must advance
`currentTime`). See `docs/android/SMOKE.md`, section "`video`, `video-h264`,
`video-mse`".

Measured 2026-10-06, two runs per build, on one API 34 `google_apis` x86_64 emulator
(image rev 14, emulator 37.1.11, `-gpu swangle -no-audio`, serial `emulator-5570`).
The harness was run with `--serial`, so it installed each APK on a freshly uninstalled
package and a fresh profile. The script is the one in the commit that adds this
directory.

```
LW_SMOKE_PACKAGE=org.redoubtbrowser ./scripts/android-smoke.sh --serial emulator-5570 \
  --sdk ~/redoubt-artifacts/android-sdk --apk <apk> --work <dir> --json <file> --check-video
```

| build | apk sha256 | exit | video | video-h264 | video-mse |
|---|---|---|---|---|---|
| 157.0-2 release, throwaway re-sign (`redoubt-157.0-2-x86_64-throwaway.apk`, buildID 20261005000000) | `ef2e520491711e39ffa789e32128071db4d3477b8bd44cb2c395b841e1f62ed1` | 1, 1 | PASS, PASS | **FAIL, FAIL** | **FAIL, FAIL** |
| fix, throwaway-signed (`redoubt-fix-x86_64-throwaway.apk`, buildID 20261006090000) | `2c090576f1332dbef4cede3cf358776139854cd2fd957feb86c1264fd4c6d2fe` | 0, 0 | PASS, PASS | PASS, PASS | PASS, PASS |

On 157.0-2, as the patch comment and `../README.md` describe:

- `video-h264`: `canPlayType` returns `""`, `play()` rejects with `NotSupportedError`,
  and `video.error.code` is 4 (`MEDIA_ERR_SRC_NOT_SUPPORTED`).
- `video-mse`: `isTypeSupported` is `false`, and `addSourceBuffer()` throws
  `NotSupportedError: MediaSource.addSourceBuffer: Can't play type`. The fragment file is
  never fetched.

On the fix, the progressive MP4 decoded 14 frames (currentTime 0.48 s). The MSE case
appended 11963 bytes and decoded 9 frames (currentTime 0.33 s). The VP8 row passes on
both builds, which is how 157.0-2 shipped with a green `video` check.

Files: `run{1,2}-{1570-2,fix}.log` hold the harness's stderr. The `.json` files are its
`--json` result.
