# Video playback: H.264 and AAC do not play in Redoubt 157.0-2 (LW-M7-43)

Owner report, 2026-10-06: "videos dont play, sample redgifs.com, pornhub.com"
(Android 14 or later phone, no further detail).

## Verdict

**This is a Redoubt defect, and it is not a pref.** `patches/android/isolated-process.patch`
(LW-M5-02) forces GeckoView's isolated content processes on. In an isolated content
process Gecko refuses the Android MediaCodec decoder module, so nothing decodes
**H.264** or **AAC**. VP8/VP9/AV1 and Opus still play because ffvpx decodes them inside
the content process. Stock Firefox 157.0 plays every case on the same emulator. The
fixed build pins both GeckoRuntimeSettings arguments to `false`, which is upstream
Fenix's default, and plays every case. Its prefs are identical to 157.0-2's.

The cause is in upstream code, and upstream knows about it (bug 1810736, "Media decoding
is not compatible with isolated process", REOPENED). Redoubt shipped it because it
switched on an upstream feature that is not finished. `docs/android/SANDBOX-SPIKE.md`
§5 and §9(b) had named this as LW-M5-02's acceptance risk. `--check-video` did not
catch it because its fixture is VP8/Opus.

The emulator affects how far this can be generalised (see "Emulator limits" below). The
mechanism does not depend on the device: Gecko never asks MediaCodec at all. So the
owner's phone is affected the same way, whatever hardware decoders it has.

## Root cause in the code (Firefox 157.0 tarball; 158.0b3 is identical)

- `dom/media/platforms/android/AndroidDecoderModule.cpp:349-352`:
  `IsJavaDecoderModuleAllowed()` returns
  `media_android_media_codec_enabled() && !java::GeckoAppShell::IsIsolatedProcess()`.
- `dom/media/platforms/PDMFactory.cpp`, `CreateContentPDMs()`: in content, the Android
  module starts only when `IsJavaDecoderModuleAllowed()` is true. The remote options:
  - The GPU process (`media.gpu-process-decoder`, false on Android) starts only ffvpx
    on Android (`CreateGpuPDMs`).
  - RDD is off on Android (`media.rdd-process.enabled`).
  - The utility process takes audio only (`RemoteMediaManagerChild::GetTrackSupport`).
    It starts the Android module only with `media.utility-android-media-codec.enabled`,
    which defaults to false ("Bug 1771196 - Dont yet enable AndroidDecoderModule on
    Utility").
- Result: `canPlayType('video/mp4; codecs="avc1…"')` returns `""`, and
  `MediaSource.isTypeSupported(avc1)` returns `false`. Logcat shows
  `Decode metadata failed` / `NS_ERROR_DOM_MEDIA_METADATA_ERR` for H.264, and
  `Error no decoder found for audio/mp4a-latm` for AAC (`logcat/`).

## Builds (all x86_64, same API 34 AVD)

| build | file | sha256 |
|---|---|---|
| Redoubt 157.0-2 release, from the GitHub release `android-157.0-2` (matches its `SHA256SUMS.signed`) | `fenix-x86_64-release.apk` | `c4eb178b98c99138504e6dc3e8f4cd672f30df2da1d06bc95ddc436a57022522` |
| the same, re-signed with the throwaway key for the emulator | `redoubt-157.0-2-x86_64-throwaway.apk` | `ef2e520491711e39ffa789e32128071db4d3477b8bd44cb2c395b841e1f62ed1` |
| Firefox for Android 157.0 from `ftp.mozilla.org/pub/fenix/releases/157.0/android/fenix-157.0-android-x86_64/` (apksigner v2: `CN=Release Engineering, O=Mozilla Corporation`, cert SHA-256 `a78b62a5165b4494b2fead9e76a280d22d937fee6251aece599446b2ea319b04`) | `fenix-157.0.multi.android-x86_64.apk` | `85cbd0d56c571b7eec8e34a76a4edebac713aec773491d41c6a5915beb2f9354` |
| **fix**: `fix/video-playback` worktree with this branch's `isolated-process.patch` hunk. `make dir TARGETS=android` on `firefox-157.0.source.tar.xz`, then x86_64-only `android-fat-aar.sh` + `android-apk.sh --variant release`. Image `librewolf-android-build:fx157` (b3f9fc5d6358), MOZ_BUILD_DATE 20261006090000, unsigned | `fenix-x86_64-release-unsigned.apk` | `b9574041027f62b7b1906cc75a5d136f53814f9c8a6ea07b98ed9aea110ac2ab` |
| the fix, re-signed with the throwaway key | `redoubt-fix-x86_64-throwaway.apk` | `2c090576f1332dbef4cede3cf358776139854cd2fd957feb86c1264fd4c6d2fe` |

The APKs are kept outside the repo, in `~/redoubt-artifacts/video-bug/apk/`.
`android-apk.sh` exited 1 after Gradle succeeded. Its universal-APK check expects all
three ABIs, and this build has only x86_64. The x86_64 APK passed the libxul identity
check against its AAR.

Process domains (`local/ps-*.txt`, `adb shell ps -A -Z`):

| build | content processes |
|---|---|
| 157.0-2 | `u:r:isolated_app` `:zygoteTab…` processes (uids `u0_i0..2`), forked by `org.redoubtbrowser_zygote` |
| fix | `u:r:untrusted_app` `:tab…` processes (the app uid) |
| Firefox 157.0 | `u:r:untrusted_app` `:tab…` processes (the app uid) |

## Environment

- **Emulator:** API 34 `google_apis` x86_64 image (rev 14), emulator 37.1.11, `-gpu swangle`, 4 vCPU, 4 GB RAM, audio output on.
- **Profiles:** a fresh profile for every run (`pm clear`). Firefox's first-run "Continue" was tapped. Redoubt's "uBlock Origin was added" sheet was closed with "OK".
- **Driver:** Marionette, opened on the release builds through GeckoView's debug config (`am set-debug-app`, the same door `android-smoke.sh` uses), with `remote.prefs.recommended: false`. The scripts are in `scripts/`. Every page is opened through a VIEW intent, so it is the foreground tab.
- **Local test page:** `scripts/t.html`, served over HTTPS from the host as `https://10.0.2.2:8766`. A throwaway CA is added in chrome context, because Redoubt's HTTPS-only mode upgrades http. `scripts/serve.py` serves byte ranges. The 30 s test media were made with ffmpeg (testsrc2 640x360 at 30 fps, plus a 440 Hz sine tone); their hashes are in `local/media-SHA256SUMS`.
  - `h264.mp4`: H.264 (openh264) + AAC.
  - `h264-noaudio.mp4`: H.264 only.
  - `aac.m4a`: AAC only.
  - `vp9.webm`: VP9 + Opus.
  - `av1.webm`: AV1 (SVT-AV1) + Opus.
  - `av1.mp4`: AV1 + AAC.
  - `hls/` and `hlsf/`: H.264 + AAC as HLS in TS and in fMP4 segments, played through MSE by hls.js 1.5.20. hls.js was pinned from jsdelivr; its sha256 is in the same file.
- **Modes per source:**
  - `muted`: `muted autoplay`.
  - `autoplay`: unmuted `autoplay`, then a trusted Marionette click on PLAY.
  - `click`: no autoplay; a trusted click on PLAY.
- **Pass criterion:** `currentTime` advances by about 2 s between two reads taken 2 s apart, with `paused=false`. `getVideoPlaybackQuality().totalVideoFrames` is recorded alongside.

## Results: local page (`local/local-*.json`)

| source | Firefox 157.0 | Redoubt 157.0-2 | Redoubt fix |
|---|---|---|---|
| H.264 + AAC MP4 | play ×3 | **fail ×3**: error 4 (SRC_NOT_SUPPORTED), `play()` rejected NotSupportedError | play ×3 |
| H.264 MP4, no audio | play ×3 | **fail ×3**: error 4 | play ×3 |
| AAC only (m4a) | play ×3 | **fail ×3**: error 3 (DECODE) | play ×3 |
| VP9 + Opus WebM | play ×3 | play ×3 | play ×3 |
| AV1 + Opus WebM | play ×3 | play ×3 | play ×3 |
| AV1 + AAC MP4 | play ×3 | **fail ×3**: error 3 (the AAC track) | play ×3 |
| hls.js, TS segments (H.264/AAC) | play ×3 | **fail ×3**: hls.js `bufferAddCodecError` | play ×3 |
| hls.js, fMP4 segments (H.264/AAC) | play ×3 | **fail ×3**: `bufferAddCodecError` / `bufferIncompatibleCodecsError` | play ×3 |
| **total** | **24/24** | **6/24** | **24/24** |

Capability probes:

| build | `canPlayType` avc1 | aac | `MediaSource.isTypeSupported(avc1)` |
|---|---|---|---|
| Firefox 157.0 | `probably` | `probably` | `true` |
| 157.0-2 | `""` | `probably` (the decode still fails) | `false` |

Autoplay behaves the same in Firefox and in the fix. Muted autoplay starts by itself, and
unmuted autoplay waits for the click (h264-noaudio has no audio track, so it starts by
itself in both). In 157.0-2, muted VP9/AV1 autoplay starts too, so autoplay policy is not
part of the failure.

Screenshots of the H.264 muted case:
- `screenshots/local-h264-muted-fenix-157.png`: plays.
- `screenshots/local-h264-muted-redoubt-157.png`: error 4, black video.
- `screenshots/local-h264-muted-redoubt-fix.png`: plays.

MediaCodec components allocated (logcat `CCodec allocate(...)`, `logcat/local-*-media.txt`):

| build | components |
|---|---|
| Firefox | 21 `c2.goldfish.h264.decoder`, 27 `c2.android.aac.decoder`, 5 `c2.goldfish.vp9.decoder` |
| 157.0-2 | **none** |
| fix | the same families as Firefox |

## Results: the two sites (`sites/`, titles and media URLs redacted)

| page | Firefox 157.0 | Redoubt 157.0-2 | Redoubt fix |
|---|---|---|---|
| redgifs.com home/browse feed (muted autoplay) | **plays**: MSE `blob:` src, `currentTime` 9.68 → 16.47 s and looping, 1080 px wide | **fails**: with no MSE avc1, the site falls back to a native `…/sd.m3u8` src, error 4, `currentTime` 0, 0 frames | **plays**: MSE `blob:`, 293 → 593 frames |
| pornhub.com video page (age gate "I am 18 or older - Enter", "Accept Only Essential Cookies", tap on the player) | **plays**: an H.264 pre-roll MP4 runs 3.5 → 13.5 s, then the main `blob:` (MSE) source attaches (`site-pornhub-fenix.txt`) | **fails**: the player falls back to a progressive `…480P_2000K….mp4`, `Decode metadata failed` in logcat, `networkState` 3, `currentTime` 0 (`site-pornhub-redoubt2.txt`) | **plays**: MSE `blob:`, 3.4 → 18.4 s, 97 → 547 frames, no pre-roll (uBO) (`site-pornhub-redoubt-fix2.txt`, `site-pornhub-redoubt-fix-interactive.txt`, 43 s / 1297 frames) |

Harness notes, so that nobody re-reads these files as browser results:

- In `site-pornhub-redoubt.txt` and `site-pornhub-redoubt-fix.txt`, the tap only
  closed Redoubt's first-run "uBlock Origin was added" sheet. The script was then changed
  to close that sheet first.
- In `site-pornhub-fenix2.txt`, the computed tap missed the player (a different page
  layout). Firefox's playback is shown by `site-pornhub-fenix.txt`.
- All site runs had `navigator.webdriver === true` (Marionette). Both sites served the
  normal player anyway.
- Screenshots of the two sites are **not committed** because they show explicit
  content. They are in `~/redoubt-artifacts/video-bug/runs/site-*.png` on the build host.

## Bisection: prefs, uBO, patches

1. **Pref differences** between 157.0-2 and Firefox (fresh profiles, read through Marionette): `local/prefdiff.txt`. In the media.\*, autoplay, RFP/FPP, webgl, wasm/jit, dom.workers/serviceWorkers, referer, partitioning, cookie, ETP, gfx/layers, dom.ipc and fission branches there are 17 differences:
   - `media.autoplay.default 5/1`
   - `media.eme.enabled false/true`
   - `media.gmp-gmpopenh264.enabled false/absent`
   - `media.memory_cache_max_size`
   - `media.peerconnection.ice.proxy_only_if_behind_proxy`
   - `privacy.resistFingerprinting` / `fingerprintingProtection` true
   - `network.http.referer.XOriginTrimmingPolicy 2`
   - cookie opt-in partitioning
   - ETP email/social tracking
   - `security.csp.reporting.enabled`
   - `network.IDN_show_punycode`
   - `fission.webContentIsolationStrategy 2/0`

   None of these could explain the failure:
   - No pref can re-enable a decoder module that is compiled to refuse isolated processes.
   - The local page fails with no third-party request, no cookie and no DRM.
   - Muted VP9 autoplay works under the same autoplay prefs.
2. **The fix changes no pref.** All 2568 prefs in those branches have the same values in
   157.0-2 and in the fix. The only differences are two Safe Browsing timestamps and the
   per-profile extension UUIDs (`prefdump.py`, compared on the host). The fix's only
   behavioural change is the content process type.
3. **Pref-level mitigations on 157.0-2**, set in a fresh profile through the GeckoView
   debug config:

   | prefs set | result |
   |---|---|
   | `media.utility-android-media-codec.enabled=true` | AAC plays (utility process, `c2.android.aac.decoder`). H.264 still error 4; hls.js still fails. |
   | the above + `media.gpu-process-decoder=true` | `canPlayType(avc1)` becomes `probably` and MSE accepts avc1. Then **`Error no decoder found for video/avc`** (error 3), because the GPU process has only ffvpx on Android. |

   **No pref combination makes H.264 play under isolation.** That is why this cannot be
   a `settings/android.cfg` fix or a documented user toggle.
4. **uBO.** Turning uBO off through AddonManager makes Redoubt's preinstaller show
   "uBlock Origin setup failed / Browsing is paused" (`site-redgifs-redoubt-noubo.txt`),
   so uBO cannot be toggled that way. It is ruled out for two reasons:
   - The local page, which makes no third-party request, fails the same way.
   - The fix plays both sites **with uBO on**.
5. **Patches.** The only Android patch that touches media, graphics or process isolation
   is `isolated-process.patch`.
   - `fission-isolation.patch` only changes the site-isolation strategy, which the fix
     keeps at 2.
   - `canvas-webgl-permissions.patch` and `webgl-prompt-default.patch` only gate WebGL.
   - The fix, which differs from 157.0-2 only by this one hunk, plays everything.

## Emulator limits

- The API 34 `google_apis` image has host-backed "hardware" decoders
  (`c2.goldfish.h264/hevc/vp8/vp9`), as well as the software `c2.android.*` ones. Firefox
  and the fix used `c2.goldfish.h264.decoder`. So this run says nothing about a given
  phone's vendor decoder quality, hardware-decoder bugs or performance.
- That does not weaken the conclusion. In 157.0-2 Gecko never creates any MediaCodec
  decoder (zero `CCodec allocate` lines), so the failure happens before any codec,
  hardware or software, is chosen. Stock Firefox plays the same streams on the same AVD.
- Not run: a physical device, and arm64/armv7 builds (the fix was built for x86_64
  only). The owner's phone should confirm with the next signed build.

## Cost of the fix

Content processes run under the app's uid in `untrusted_app` again, as in stock Firefox
for Android. A compromised content process can again read the profile directory. Before
the fix, LW-M5-02 measured kernel denials of this access. Site isolation (fission
strategy 2, LW-M5-01) and RLBox are unchanged.

The public claims that relied on isolated processes are corrected in this change:
- `README.md`
- `site/privacy.html`
- `docs/android/play/listing-en-US.md`
- `docs/android/PARITY.md`
- `docs/android/ROADMAP.md`
- `docs/android/TRIAGE.md`

Re-enable isolation when a Firefox release decodes H.264 from an isolated content
process. Check `IsJavaDecoderModuleAllowed()` at every rebase.

## Firefox 158

`dom/media/platforms/android/AndroidDecoderModule.cpp:349-352` is unchanged in 158.0b3
(`~/redoubt-artifacts/ff158/work/buildrepo/librewolf-158.0-1`). The local
`android/firefox-158` branch carries the same `isolated-process.patch`, so 158.0-1 would
have the same defect. This is a patch change, not a settings change, so the 158 branch
was not modified. It picks the fix up when it is rebased onto main, which is already
pending.

## Follow-up

`android-smoke.sh --check-video` should get an H.264+AAC MP4 fixture (and ideally an
MSE case). The VP8/Opus fixture can only see failures that ffvpx would also hit.
