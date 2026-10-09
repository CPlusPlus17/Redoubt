# Can content run isolated again without breaking H.264/AAC video?

**Owner: LW-M7-48.** Feasibility study for the owner's item (2) of 2026-10-09
("lets do 1,2,7"). It is analysis only: no product code, no patch, no pref change
ships with it. It answers one question and makes one recommendation.

**Answer: yes, and upstream has already chosen the route.** Firefox 158 already
contains a second MediaCodec path that does not use GeckoView's Java media
stack: ffvpx drives the **Android NDK MediaCodec** (`AMediaCodec`) from the
**RDD process**, which is not isolated. Mozilla made exactly this the default for
its own isolated-process test configuration on 2026-10-06 (bug 1988531, part 1,
landed for Firefox 159), and it is **only prefs**: no Gecko C++, Java or manifest
change. The prefs are all `mirror: always` static prefs that exist in 158.

**Recommendation: design (e) below, staged behind a pref, not before 159.**
Spike it on 158 now (prefs only), prototype it as a Redoubt pref set tied to the
isolation switch, require `--check-video` (H.264 progressive, MSE and AAC) to pass
with isolation on, and ship it no earlier than Firefox 159, which carries the
upstream draining fix for this decoder (bug 1987001). Effort and the stages are
in [§7](#7-recommendation-staged-plan-and-effort). Section 8 lists the evidence
that would show the security property holds. Section 9 has the spike result.

Every factual claim carries a grade, as in `SANDBOX-SPIKE.md`:

| grade | meaning |
|---|---|
| **S** | source: read in the pristine Firefox 158.0 tarball `firefox-158.0.source.tar.xz` (the 158.0 RC, build2), file:line given |
| **U** | upstream: Bugzilla (read only, through the REST API, 2026-10-09), Phabricator or the GitHub mirror of `mozilla-firefox/firefox` |
| **M** | measured: on our own emulator, with an APK whose sha256 is given |
| **I** | inference: reasoned from S/U/M, stated as such |

---

## 1. The defect being undone

Redoubt 157.0-2 shipped `isolatedProcess` plus the app zygote (LW-M5-02). Its
content processes ran as `u:r:isolated_app` with their own ephemeral uids, so a
compromised content process could not read the profile. No H.264 or AAC played
(LW-M7-43, `evidence/video-playback/README.md`). 157.0-3 turned isolation off
again (owner: "Accept, turn isolation off"), so content now runs as
`untrusted_app` with the app's uid, as in stock Fenix **(M, LW-M7-43)**.

The mechanism, unchanged in 158:

- `AndroidDecoderModule::IsJavaDecoderModuleAllowed()` returns
  `media_android_media_codec_enabled() && !GeckoAppShell::IsIsolatedProcess()`
  (`dom/media/platforms/android/AndroidDecoderModule.cpp:349-352`) **(S)**. That
  check was added on purpose by bug 1988727 ("Disable Java's PDM if isolated
  process", Firefox 145) because the Java path crashed the content process
  **(U)**.
- The Java path cannot work in an isolated process because
  `RemoteManager.connect()` calls `Context.bindService()` on the `:media`
  `MediaManager` service (`mobile/android/geckoview/src/main/java/org/mozilla/gecko/media/RemoteManager.java:62-70`) **(S)**,
  and Android rejects that from an isolated process:
  `SecurityException: Isolated process not allowed to call bindService`
  (bug 1810736 comment 0 and comment 6) **(U)**.
- Content then has no H.264/AAC module: see the matrix in §2.

## 2. The decoder process matrix in Firefox 158

Which decoder modules (PDMs) each process starts on Android, with the default
prefs **(S)**:

| process | where | what it starts on Android | default prefs |
|---|---|---|---|
| content | `PDMFactory::CreateContentPDMs()`, `PDMFactory.cpp:718-806` | a `RemoteDecoderModule` for GPU (`:719-721`, if `media.gpu-process-decoder`), for RDD (`:723-725`, if `media.rdd-process.enabled`), for Utility_Generic (`:727-739`); then ffvpx and Agnostic **in-process** (`:744-786`, the `allow-audio-non-utility` guard is compiled out on Android); then `AndroidDecoderModule` only if `IsJavaDecoderModuleAllowed()` (`:788-794`) | gpu-process-decoder **false** (`StaticPrefList.yaml:12658-12665`), rdd-process **false** on Android (`:12703-12720`), utility-process true (`:12865-12880`) |
| GPU | `CreateGpuPDMs()`, `PDMFactory.cpp:597-608`; `InitGpuPDMs()` `:87-98` | ffvpx only, and only with `media.gpu-process-decoder` | off |
| RDD | `CreateRddPDMs()`, `PDMFactory.cpp:632-670`; `InitRddPDMs()` `:100-113` | ffvpx (with its MediaCodec NDK hwaccel, §3), Agnostic. **Never** `AndroidDecoderModule` | the process is off on Android |
| Utility (generic) | `CreateUtilityPDMs()`, `PDMFactory.cpp:672-716` | ffvpx, Agnostic, and `AndroidDecoderModule` only with `media.utility-android-media-codec.enabled` (`:694-699`) | that pref **false**, comment "Bug 1771196 Dont yet enable AndroidDecoderModule on Utility" (`StaticPrefList.yaml:12898-12903`) |

What the content process may ask each remote process for:
`RemoteMediaManagerChild::GetTrackSupport()` (`dom/media/ipc/RemoteMediaManagerChild.cpp:913-966`) **(S)**:

- GPU: video only (`:917-922`).
- RDD: video, **and audio on Android** (`:923-941`). The `#ifndef ANDROID`
  guard and its comment say this is deliberate: on Android RDD should decode
  audio and video together so they can share a CDM.
- Utility_Generic: **audio only** (`:943-951`).
- `CreateVideoDecoder()` launches the GPU process, the MFMediaEngineCDM utility
  or **RDD** (`:451-458`). There is no branch that would launch a video decoder
  in the generic utility process.

So with the defaults the isolated content process has ffvpx (VP8, VP9, AV1,
Opus, Vorbis, FLAC, MP3, WAV) and nothing for H.264, HEVC or AAC. That is
exactly what LW-M7-43 measured.

## 3. The second MediaCodec path that 158 already has

Bug 1934009 ("Implement Android encoder and decoder backends with NDK, via
ffmpeg", fixed in Firefox 143) added the NDK MediaCodec files to Mozilla's ffvpx
copy **(U)**. In 158 **(S)**:

- `dom/media/platforms/ffmpeg/ffvpx/moz.build:72-73` defines `MOZ_USE_HWDECODE`
  for Android.
- `FFmpegDecoderModule::Init()` (`FFmpegDecoderModule.h:37-145`) runs in RDD,
  Utility and (Android only) the GPU process (`:43-50`). It registers
  `AV_HWDEVICE_TYPE_MEDIACODEC` (`:71-74`) and marks **H.264, HEVC and AAC** as
  decodable through MediaCodec (`:104-110`, "the underlying implementation may be
  software or hardware").
- `IsHWDecodingSupported()` requires `media.ffvpx-hw.enabled`
  (`FFmpegDecoderModule.h:340-349`). That pref is **false** on Android
  (`StaticPrefList.yaml:12676-12685`).
- `FFmpegVideoDecoder::InitHWDecoderIfAllowed()` uses MediaCodec only in RDD or
  GPU (`FFmpegVideoDecoder.cpp:1071-1076`). `InitMediaCodecDecoder()`
  (`:3156-3300`) gets its output Surface from `java::SurfaceAllocator::AcquireSurface`
  (`:3247-3250`) in RDD, or from an `AImageReader` in the GPU process
  (`:3212-3216`).

The Surface plumbing already works across processes. RDD is a GeckoView child
process. It gets its `ISurfaceAllocator` from the parent through
`IProcessManager.getSurfaceAllocator()` (`GeckoServiceChildProcess.java:212-213`,
`GeckoProcessManager.java:70-125`), and that allocator lives in the GPU process.
Frames go from MediaCodec straight into a SurfaceTexture owned by the GPU process.
The content process only receives an image handle (`RemoteImageHolder`). Bug
1706656 (fixed in 111) made the same allocator usable from isolated processes
**(S, U)**.

### What upstream did with it

| bug | status (2026-10-09) | what it means here |
|---|---|---|
| [1810736](https://bugzilla.mozilla.org/show_bug.cgi?id=1810736) Media decoding is not compatible with isolated process | REOPENED, depends on 1981478 and 1706656 | comment 11 (2025-09-16, jnicol): the NDK path "should definitely fix the originally described problem here, as the surface will now be allocated from the RDD process which is not isolated" |
| [1934009](https://bugzilla.mozilla.org/show_bug.cgi?id=1934009) NDK encoder/decoder backends via ffmpeg | FIXED, 143 | the code in §3 |
| [1981478](https://bugzilla.mozilla.org/show_bug.cgi?id=1981478) Flip prefs to switch to NDK decoding/encoding on Android on nightly | **NEW** | not the default yet, not even on Nightly |
| [1988727](https://bugzilla.mozilla.org/show_bug.cgi?id=1988727) Disable Java's PDM if isolated process | FIXED, 145 | the `IsIsolatedProcess()` check in §1 |
| [1988531](https://bugzilla.mozilla.org/show_bug.cgi?id=1988531) Ensure media is working on isolated process | **FIXED 2026-10-06, 159** | part 1, [`e0286afb5f68`](https://github.com/mozilla-firefox/firefox/commit/e0286afb5f68): "Use the MediaCodec NDK via ffmpeg by default for Android isolated process". It changes **only** `taskcluster/test_configs/variants.yml` (the 11 prefs in §6e). Parts 2 and 3 run media mochitests and WPT under that variant on Android emulator debug builds |
| [1987001](https://bugzilla.mozilla.org/show_bug.cgi?id=1987001) Improve draining on Android | FIXED 2026-10-06, 159 | the NDK decoder lost frames at drain (short videos showed none). Not in 158 |
| [2067689](https://bugzilla.mozilla.org/show_bug.cgi?id=2067689), [2075686](https://bugzilla.mozilla.org/show_bug.cgi?id=2075686) | FIXED, 159 | EME on this path. Redoubt ships `media.eme.enabled=false`, so not needed |
| [2038473](https://bugzilla.mozilla.org/show_bug.cgi?id=2038473) heap OOB read in `AllocateH264ExtraData` on Android | FIXED, 152 | already in 158; a reminder that this path parses attacker bytes in RDD |
| [1771196](https://bugzilla.mozilla.org/show_bug.cgi?id=1771196) AAC to Utility | DUPLICATE of 1934009 | upstream dropped "Java PDM in Utility" in favour of NDK |
| [2023367](https://bugzilla.mozilla.org/show_bug.cgi?id=2023367) Videos not playing | NEW, depends on 1981478 | a Nightly user with "isolated content process" on: same symptom as LW-M7-43; jolin: "can be fixed by bug 1981478" |
| [2043165](https://bugzilla.mozilla.org/show_bug.cgi?id=2043165) Media3 `registerReceiver` from isolated process | UNCONFIRMED | native HLS (GeckoHlsPlayer/ExoPlayer) cannot run isolated; see §5 |
| [1962027](https://bugzilla.mozilla.org/show_bug.cgi?id=1962027) Cannot get codec lists on isolated content process | NEW | `MediaCodecList` in content waits on `media.player` and throws |

**(U)** for every row. Bug 1565196 (the isolatedProcess meta) is still NEW.

## 4. Constraints from Android's isolated processes

- **No `bindService`, `startService`, `registerReceiver` or
  `getContentProvider`** from an isolated process. These are the exceptions seen
  in bugs 1810736, 2043165 and 1988727 **(U)**. Isolated content cannot reach
  `:media` on its own.
- **A binder that is handed over does work.** Isolated content already uses two:
  `IProcessManager` (passed in `IChildProcess.start()`) and the GPU
  `ISurfaceAllocator` that the parent returns from
  `IProcessManager.getSurfaceAllocator()`
  (`aidl/org/mozilla/gecko/process/IProcessManager.aidl`,
  `GeckoProcessManager.java:70-89`) **(S)**. Design (b) relies on this.
- `isolated_app` cannot look up most system services in `servicemanager`.
  That is why `MediaCodecList` fails in content (bug 1962027), and why
  `AudioManager.getProperty` does not return (`GeckoAppShell.java:1465-1495`, bug
  1980870) **(S, U)**.
- Manifest: every non-content service (`MediaManager` `:media`, `gpu`, `rdd`,
  `utility`, `socket`) is `isolatedProcess="false"`. Only `isolatedTabN` and
  `zygoteTab` are isolated (`AndroidManifest_overlay.jinja:15-78` all `false`; `:80-95` the two isolated entries)
  **(S)**. A decoder in RDD, GPU, Utility or `:media` therefore runs as
  `untrusted_app` with the app's uid, just like content does today.

## 5. What is lost under isolation even with a decoder

- **Native HLS** (`<video src="….m3u8">`): `HLSDecoder::IsEnabled()` is
  `media_hls_enabled() && !IsIsolatedProcess()` (`dom/media/hls/HLSDecoder.cpp:360-363`)
  **(S)**. With isolation on, `canPlayType("application/vnd.apple.mpegurl")`
  becomes `""`, and a page that only offers a native m3u8 does not play. Stock
  Fenix plays it through ExoPlayer. Sites that feature-detect fall back to
  hls.js/MSE, which works once MSE accepts avc1. Measured in §9: native m3u8
  fails with error 4, and hls.js over TS and fMP4 plays. In LW-M7-43, redgifs fell back to
  native m3u8 only *because* MSE refused avc1 **(M, I)**. This is a measurable
  residual and the spike measures it (§9).
- **Codec capability lists**: under the NDK path, content learns what RDD can
  decode over IPC (`ContentParent::SendUpdateMediaCodecsSupported`,
  `dom/ipc/ContentParent.cpp:1494, 2818`), not from `MediaCodecList`. Bug
  1962027 therefore does not apply **(S, I)**.
- **WebRTC H.264 encode** in content also uses the Java module
  (`PEMFactory.cpp:252, 313`) **(S)**. Upstream's variant moves it to RDD with
  `media.use-remote-encoder.video.platform` + `media.ffmpeg.encoder.enabled`
  **(U)**. The spike does not test WebRTC.

## 6. Candidate designs

### (a) Decode in the Utility or GPU process (Java `AndroidDecoderModule` or NDK)

*Utility + Java module.* `media.utility-android-media-codec.enabled=true` already
moves **AAC** to Utility: LW-M7-43 measured AAC playing on 157.0-2 with that pref
**(M)**. Video is a different matter. Utility is audio-only by design
(`GetTrackSupport`, `:943-951`), and `CreateVideoDecoder` never launches it
(`:451-458`). Making Utility do video means changing `GetTrackSupport`,
`CreateVideoDecoder`, `Supports` and `LaunchUtilityProcessIfNeeded`
(`RemoteMediaManagerChild.cpp:256-330, 414-470, 811-905`). It also needs a
compositor/`KnowsCompositor` path for a process that has never served video, and
an `ImageBridge` connection to it. Upstream has abandoned this direction (1771196
was closed as a duplicate of the NDK bug).

*GPU + NDK.* `media.gpu-process-decoder=true` plus `media.ffvpx-hw.enabled=true`.
ffvpx in the GPU process then has the MediaCodec hwaccel (`FFmpegDecoderModule.h:43-50`,
`FFmpegVideoDecoder.cpp:1071-1076`, `AImageReader` at `:3212`). LW-M7-43 tried
`gpu-process-decoder` **without** `ffvpx-hw` and got "no decoder found for
video/avc" **(M)**, which is consistent with `IsHWDecodingSupported()` (§3). This
is prefs only, and the spike (§9) measured it: with those two prefs plus
`media.utility-android-media-codec.enabled`, H.264 plays from isolated content and
is allocated in `:gpu`. Audio still needs a home: Utility + Java for AAC (above), or RDD.
Windows decodes in its GPU process the same way.

| | |
|---|---|
| changes | Utility video: Gecko C++ in `RemoteMediaManagerChild`, `PDMFactory`, plus compositor plumbing, roughly 400-800 lines. GPU + NDK: prefs only |
| risk | Utility video: high (new IPC topology nobody upstream tests). GPU: medium. It is not the configuration upstream tests, and a codec crash takes the compositor down with it (the GPU process restarts, every tab flashes) |
| keeps the security benefit | yes, content stays `isolated_app`. The bitstream parser moves to a non-isolated process |
| rebase cost | Utility video: high, every media IPC change conflicts. GPU: low |
| upstream direction | Utility video: against. GPU: tolerated, not tested |

### (b) Hand the `:media` `MediaManager` binder to isolated content

Add `IMediaManager getMediaManager()` to `IProcessManager.aidl`. The parent's
`ProcessManagerProxy` (`GeckoProcessManager.java:70-89`) binds `:media` and
returns the binder. `RemoteManager.connect()` uses it when
`Process.isIsolated()`, instead of `bindService`. Then relax
`IsJavaDecoderModuleAllowed()`. Android allows this: it is how the
`ISurfaceAllocator` already gets there. The work does not stop at the binder:

- `AndroidDecoderModule::GetSupportedCodecs()` calls `MediaCodecList` in content
  (`AndroidDecoderModule.cpp:160-185`, `HardwareCodecCapabilityUtils.java:93-113`),
  which fails isolated (bug 1962027). The list must come from the parent over
  IPC, which is new C++.
- `IMediaManager` has no caller check (`MediaManager.java:23-35`). Any content
  process, including a compromised one, could create codecs and
  `createRemoteMediaDrmBridge` objects in `:media`. That is the same exposure as
  today's non-isolated content, so no new hole, but nothing tighter either.
- Death and reconnect handling (`RemoteManager.binderDied`) assumes it can
  re-bind. A handed-over binder needs a re-fetch path through the parent.

| | |
|---|---|
| changes | Java (AIDL, `GeckoProcessManager`, `RemoteManager`), C++ (`AndroidDecoderModule`, codec list IPC). About 150-300 lines over 4-6 files, all in `mobile/android/geckoview` and `dom/media/platforms/android` |
| risk | medium. It reuses the decoder stack stock Fenix ships (the Java path), but in an IPC shape nobody else runs |
| keeps the security benefit | yes. Actual decoding stays in Android's own codec processes (`mediaswcodec`/HAL), and `:media` only proxies |
| rebase cost | **high and permanent**. It is a GeckoView fork on the exact files upstream is retiring (Java PDM → NDK, bug 1981478) |
| upstream direction | against. Upstream deliberately disabled the Java PDM under isolation (1988727) and moved to NDK |

### (c) Hybrid: isolation on, but non-isolated content for sites that need H.264

Not workable. The content process is chosen before the page says which codec it
wants, and a page can start an H.264 `<video>` or MSE buffer at any time. It
would need a reload into another process type, keyed on a site list or a first
failure. That is the inverse of site isolation: an attacker controls whether it
gets the weaker process, simply by including an H.264 video. GeckoView picks
the content service type once per runtime (`GeckoProcessType.java:53-62`), so it
would also need a GeckoView fork. **Rejected.**

### (d) Wait for upstream

Upstream's position is now explicit: the isolated variant decodes through NDK in
RDD (1988531, 159), and the general switch to NDK is 1981478 (NEW). Isolation
itself (1565196) is still a meta bug with open blockers: IME 1989379, crash
reporter 1969818/1989887, audio properties 1980870, Media3/HLS 2043165. So
"wait" means waiting for Mozilla to *ship* isolation in Fenix, which has no date.
It costs nothing and gains nothing in the meantime.

### (e) Upstream's route now: NDK MediaCodec via ffvpx in RDD (prefs only)

Set the 11 prefs from bug 1988531 part 1 (`e0286afb5f68`, `variants.yml:234-246`):

```
media.android-media-codec.enabled=false
media.android-media-codec.preferred=false
media.ffmpeg.encoder.enabled=true
media.ffvpx-hw.enabled=true
media.rdd-ffvpx.enabled=true
media.rdd-opus.enabled=true
media.rdd-process.enabled=true
media.rdd-vorbis.enabled=true
media.rdd-vpx.enabled=true
media.rdd-wav.enabled=true
media.use-remote-encoder.video.platform=true
```

All 11 exist in 158 (`StaticPrefList.yaml:12642, 12676, 12703, 12747, 12780, 12799, 12818, 12837, 12893, 12905, 12948`) **(S)**.
Content then sends compressed samples to RDD. RDD's ffvpx drives `AMediaCodec`
for H.264/HEVC/AAC, and VP9/AV1 run in hardware where the device offers them,
otherwise in software in RDD. The output goes into a GPU-process
SurfaceTexture, and content composites a handle.

| | |
|---|---|
| changes | `settings/android.cfg` (or the GeckoView runtime prefs), locked, plus the existing `isolated-process.patch` literals back to `true`. No Gecko C++/Java/manifest change. About 15 lines |
| risk | medium. This decoder is not the default anywhere in release yet (1981478 NEW). Device-specific MediaCodec quirks reach us before they reach Fenix. Draining is broken in 158 (1987001, fixed in 159): the last frames of a stream, and short clips, may never show. That is a reason to ship on 159, not 158 |
| keeps the security benefit | **yes for the profile**: content is `isolated_app` again. Cost: the codec *parser* moves. ffvpx's MediaCodec wrapper, H.264 extradata handling and **every software decoder (VP8/VP9/AV1 via libvpx/dav1d)** now run in RDD, which on Android is `untrusted_app` with the app's uid and no Gecko sandbox (`MOZ_SANDBOX` is off, SANDBOX-SPIKE §1). Against 157.0-3, where content parses all of it with the app's uid anyway, this is strictly better. Against 157.0-2 it is a little weaker: there, VP9/AV1 decoding sat in isolated content **(I)** |
| rebase cost | low: the pref names are stable, and `board.py` pref audits catch a rename. The rebase check is "does upstream's variant still use these prefs?" |
| upstream direction | **with it**: this is Mozilla's own isolated configuration, tested on every autoland push for Android emulator debug builds since 2026-10-06 |

**Optional tightening, later:** keep software VP8/VP9/AV1 and Opus in isolated
content and send only MediaCodec codecs to RDD. RDD sits first in the content PDM
order (`PDMFactory.cpp:723-725`), so this needs a small C++ change in
`PDMFactory::SupportsMimeType` for `RemoteMediaIn::RddProcess`
(`PDMFactory.cpp:963-1008`), which no pref can express. About 20 lines, but a
Redoubt-only Gecko patch on a hot file. Decide after the prototype.

### Summary

| design | code | effort | keeps isolation | rebase cost | upstream |
|---|---|---|---|---|---|
| (a) Utility video | C++ 400-800 lines | 3-5 weeks | yes | high | against |
| (a) GPU + NDK | prefs | measured working (§9); 5-8 days like (e) | yes | low | untested upstream |
| (b) binder handover | Java + C++ 150-300 lines | 2-3 weeks | yes | high, permanent | against |
| (c) hybrid per site | GeckoView fork | n/a | **no** (attacker chooses) | high | n/a |
| (d) wait | none | 0 | no, not until Fenix ships it | 0 | n/a |
| **(e) NDK in RDD** | **prefs (15 lines)** | **5-8 days to ship** | **yes** | **low** | **with it** |

## 7. Recommendation, staged plan and effort

**Do (e).** Gate it on Firefox 159 for release. Keep (a)-GPU as the fallback if
RDD misbehaves on real devices.

1. **Spike (done, §9: works).** Release APK 157.0-2 (isolation on, throwaway
   re-signed), prefs from §6e through the GeckoView debug config, LW-M7-43's
   local media page. Question: do H.264, AAC, MSE/hls.js play, and where do the
   codecs run? *0.5 day.*
2. **Prototype behind a pref (LW-M7-48 follow-up, 159 rebase).**
   - Add one Redoubt pref, e.g. `redoubt.content.isolated` (default false).
   - When it is true, `isolated-process.patch` passes `true` to both
     GeckoRuntimeSettings calls, and `android.cfg` locks the 11 media prefs.
     Literals stay literals, so neither Nimbus nor Settings can flip it.
   - A runtime pref cannot pick the process type, because the runtime is built
     before prefs load. So "behind a pref" means a build flag for the
     prototype, and the release decision is a one-line literal.
   - Backport 1987001 only if the prototype is wanted on 158 (2 files, draining).
   - *2-3 days.*
3. **Harness.** `android-smoke.sh --check-video` must pass on the prototype with
   **isolation on**: video-h264 (progressive H.264+AAC), video-mse (avc1+mp4a),
   plus two new rows:
   - an **AAC-only** case;
   - a **short-clip** case (under 1 s, which catches the drain bug).

   Add a `--check-isolation` step. It asserts the §8 properties from
   `ps -A -Z`, and it is what keeps the security claim measured rather than
   claimed. Run it on x86_64 emulator and on **at least one arm64 phone** (the
   owner's, with permission; not the release key). *1-2 days.*
4. **Ship** with 159: re-enable isolation by default, restore the public claims
   that LW-M7-43 removed (README, `site/privacy.html`, Play listing, PARITY row
   "Process separation") **only** from the measured `--check-isolation` output.
   *1 day.*

**Total: 5-8 working days from 159 availability**, about half of it device time.
Design (b), for comparison, is 2-3 weeks plus a permanent fork. Design (a)-Utility
is 3-5 weeks.

**What would stop it:** a real device where RDD's NDK MediaCodec fails for a
common profile (H.264 High, or AAC-HE) and stock Fenix plays it. Then fall back
to (a)-GPU (the same decoder code in another process, so probably the same
failure) or wait for upstream 1981478 to sort out the device matrix.

## 8. Evidence that the security property holds

The property: **web content runs isolated and cannot read the profile, and the
codec runs outside content.** It counts as proven only when all of these hold on
a running build with a video playing:

| check | command | pass |
|---|---|---|
| content is isolated | `adb shell ps -A -Z \| grep -E ':(isolatedTab\|zygoteTab)'` | every content process is `u:r:isolated_app:s0:c…` with a `u0_i…` uid; **no** `:tab` process with the app uid |
| zygote | same | content processes have `org.redoubtbrowser_zygote` as parent (PPID) |
| decoder is out of content | `logcat` `CCodec allocate(...)` lines, PID mapped to process name | every H.264/AAC allocation is in `:rdd`, none in an isolated process |
| RDD is what we think it is | `ps -A -Z \| grep :rdd` | `u:r:untrusted_app…` with the app uid (stated, not hidden: it can read the profile) |
| no profile reads from content | static: `adb shell ls -ldZ /data/data/org.redoubtbrowser` is mode `0700`, owner the app uid, label `app_data_file`, and row 1 shows content runs under another uid in `isolated_app` (Android's `isolated_app.te` grants no `app_data_file` access). Dynamic, once per release, in a throwaway debug build: a test-only hook in content opens a file under the profile | the open fails with `EACCES`, and logcat shows `avc: denied … scontext=u:r:isolated_app` or a plain DAC denial; never a successful read |
| no SELinux denials during normal playback | `adb logcat -b events,main \| grep 'avc: denied'` while running `--check-video` no `isolated_app` denial **beyond the measured baseline**: sysfs `product_name`/`product_sku`, `/proc/filesystems` and `incremental_prop` (§9, present with and without the media prefs). Anything that mentions a media service, a device node or `app_data_file` fails the check |
| codec capability via IPC | `canPlayType(avc1)` = `probably`, `MediaSource.isTypeSupported(avc1)` = true, with isolation on | as listed |

Rows 1-4 and 6-7 can be automated in `--check-isolation`. Row 5 is a one-off
device check, recorded once per release.

## 9. Spike result

Measured 2026-10-09 on the emulator (`evidence/lw-m7-48/README.md`, all
**(M)**). The APK is the isolated Redoubt 157.0-2 release, re-signed with the
throwaway key (sha256 `ef2e5204…62ed1`, full hash in the evidence). The prefs
were set at startup through the GeckoView debug config, on a fresh AVD (API 34,
x86_64) with LW-M7-43's local media page. The code is Firefox 157, but every
path involved is identical in 158 (§2-§5).

| | 157.0-2 as shipped | + upstream's 11 prefs (e), 2 runs | + GPU variant (a) |
|---|---|---|---|
| H.264+AAC, H.264-only, AV1+AAC, hls.js TS and fMP4 (MSE) | H.264 error 4, AAC error 3 | **all play** (20/20) | all play (10/10) |
| AAC-only | error 3 | plays (4/4) | 1 of 2 stalled¹ |
| VP9+Opus, AV1+Opus | play | 7/8, 1 stalled¹ | play (4/4) |
| native HLS `<video src=.m3u8>` | not run | **error 4** (4/4), as §5 predicts | error 4 |
| `canPlayType(avc1)`, `isTypeSupported(avc1)` | `""`, false | `probably`, true | `probably`, true |
| content processes | `isolated_app`, `u0_i*`, from the app zygote | same | same |
| where codecs were allocated | nowhere | H.264 and VP9 in **`:rdd`**, AAC in **`:utility`**, none in content | H.264, VP9 in `:gpu`; AAC in `:media` |
| `isolated_app` denials | 4 kinds (sysfs `product_name`/`product_sku`, `/proc/filesystems`, `incremental_prop`) | **the same 4**, nothing media-related | the same 4 |

¹ A stall means `canplay` fired, with no error and no frames, and the muted
autoplay never started. Each case passed in its other run or in click mode.
This is not a decoder error, but it is not explained. The prototype must repeat
every case at least 3 times.

`mozRequestDebugInfo()` names the decoders: video is `ffvpx video decoder (RDD
remote)` for H.264, VP9 (both hardware) and AV1 (**software**), and audio is
`ffvpx audio decoder (Utility Generic remote)` for AAC and Opus. So no decoder
runs in isolated content any more. Software AV1 and Opus run with the app's uid.
This is the parser move that §6e describes, now measured.

**The key question is settled:** on 157/158 code, with isolation on, the 11
prefs alone make H.264, AAC and MSE play, and the codecs run outside the isolated
content process. What the spike does not settle is listed in the evidence
README: arm64 and vendor codecs, WebRTC, short clips/drain (1987001), and a locked
`android.cfg` pref set instead of the debug config.

## 10. Re-verify at every rebase

1. `AndroidDecoderModule.cpp`: is `IsJavaDecoderModuleAllowed()` still
   `&& !IsIsolatedProcess()`? (If upstream drops the check, design (b) became
   upstream's, so re-read this study.)
2. `taskcluster/test_configs/variants.yml`, `geckoview-isolated-process`: is
   the `--setpref` list still the 11 prefs of §6e? Copy its changes.
3. `StaticPrefList.yaml`: did 1981478 flip any of these by default? Then drop
   them from `android.cfg`.
4. `HLSDecoder.cpp`: is native HLS still off under isolation (2043165)?
5. Bug 1565196's open blockers (IME 1989379, audio 1980870): any regression
   that Redoubt users would see.

## Sources

- Firefox 158.0 source, `~/redoubt-artifacts/ff158/rel158/build2/firefox-158.0.source.tar.xz` (file:line as cited).
- Bugzilla, read only, 2026-10-09: 1565196, 1706656, 1771196, 1806129, 1810736, 1934009, 1962027, 1981478, 1987001, 1988531, 1988727, 2023367, 2038473, 2043165, 2067689, 2075686.
- Bug 1988531 commits: [`e0286afb5f68`](https://github.com/mozilla-firefox/firefox/commit/e0286afb5f68) (part 1, the prefs), [`76481521655f`](https://github.com/mozilla-firefox/firefox/commit/76481521655f) (part 2, test kinds).
- `docs/android/SANDBOX-SPIKE.md`, `docs/android/evidence/video-playback/README.md` (LW-M7-43).
