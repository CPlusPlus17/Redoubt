# LW-M7-48 spike: isolated content with NDK MediaCodec decoding (prefs only)

This spike answers the key question of `docs/android/ISOLATION-MEDIA-STUDY.md`:
with isolated content on, do H.264, AAC and MSE play once upstream's
isolated-process media prefs are set? And in which processes do the codecs run?
Run 2026-10-09, after the Beta 2 acceptance had released the emulator.

## Build and environment

- APK: Redoubt **157.0-2** release, x86_64. It has isolation on (zygote
  `isolatedProcess`), and is re-signed with the throwaway key.
  `redoubt-157.0-2-x86_64-throwaway.apk`, sha256
  `ef2e520491711e39ffa789e32128071db4d3477b8bd44cb2c395b841e1f62ed1`. This is
  the file and hash from `evidence/video-playback/README.md`, re-hashed for
  this run.
  It is Firefox 157 code. The parts this spike exercises (the PDM matrix, the
  ffvpx NDK MediaCodec hwaccel, `IsJavaDecoderModuleAllowed`, `HLSDecoder::IsEnabled`)
  are the same in 158.0 (study §2-§5). Neither 157 nor 158 has the drain fix
  1987001.
- Emulator: a fresh AVD `iso34`, API 34 `google_apis` x86_64, `-gpu swangle`,
  4 vCPU, 4 GB, port 5590, with audio. Fresh profile per run (`pm clear`).
- Driver: LW-M7-43's Marionette harness (`scripts/vb.py`). Changes from that
  copy: serial `emulator-5590`, emulator home, and the runs dir. The page is
  LW-M7-43's `t.html` with one addition, `&native=1`. That sets the `.m3u8` as
  `<video src>` instead of using hls.js. It is served over HTTPS on port 8796
  with LW-M7-43's throwaway CA and media.
- Prefs are applied at startup through the GeckoView debug config
  (`/data/local/tmp/org.redoubtbrowser-geckoview-config.yaml`), the same door
  as LW-M7-43. They are read back through Marionette (`PREFS` in `*.out`).

## Configurations (`scripts/spike.py`, `scripts/spike_cfg.py`)

| config | prefs |
|---|---|
| `iso-base` | none (157.0-2 as shipped) |
| `iso-rdd` | the 11 prefs of bug 1988531 part 1 (`e0286afb5f68`), upstream's isolated-process variant |
| `iso-gpu` | `media.gpu-process-decoder`, `media.ffvpx-hw.enabled`, `media.utility-android-media-codec.enabled` |

## Results

Pass means `currentTime` advances about 2 s in 2 s with `paused=false` (LW-M7-43's criterion).

| case | iso-base | iso-rdd run 1 | iso-rdd run 2 | iso-gpu |
|---|---|---|---|---|
| H.264+AAC MP4, muted / click | **fail** (error 4) / not run | pass / pass | pass / pass | pass / pass |
| H.264 MP4 no audio | not run | pass / pass | pass / pass | pass / pass |
| AAC m4a | **fail** (error 3) / not run | pass / pass | pass / pass | stall¹ / pass |
| VP9+Opus WebM | pass / not run | pass / pass | pass / pass | pass / pass |
| AV1+Opus WebM | not run | stall¹ / pass | pass / pass | pass / pass |
| AV1+AAC MP4 | not run | pass / pass | pass / pass | pass / pass |
| hls.js, TS segments (H.264/AAC, MSE) | not run | pass / pass | pass / pass | pass / pass |
| hls.js, fMP4 segments (MSE) | not run | pass / pass | pass / pass | pass / pass |
| native HLS `<video src=.m3u8>` | not run | **fail** (error 4) ×2 | **fail** (error 4) ×2 | **fail** (error 4) ×2 |
| `canPlayType(avc1)` / `isTypeSupported(avc1)` | `""` / false | probably / true | probably / true | probably / true |

¹ "stall": `loadedmetadata` and `canplay` fired, with no error and 0 frames,
and the element never started the muted autoplay. The same case passed in the
other run and in click mode. This is not a decoder failure (no `error`), but it
is not explained either. The prototype stage must repeat each case at least 3
times (study §7).

Native HLS fails as the source predicts: `HLSDecoder::IsEnabled()` is false in
an isolated process (`HLSDecoder.cpp:360-363`).

### Where the codecs ran

`CCodec allocate(...)` lines in logcat, by the PID of the process that created
the codec (`runs/*-logcat-filtered.txt`, `ccodec_allocate` in `*.json`):

| config | process | codecs |
|---|---|---|
| iso-rdd (run 2) | `:rdd` (`untrusted_app`, app uid) | `c2.goldfish.h264.decoder` ×13, `c2.goldfish.vp9.decoder` ×3 |
| iso-rdd (run 2) | `:utility` (`untrusted_app`, app uid) | `c2.android.aac.decoder` ×16 |
| iso-gpu | `:gpu` | `c2.goldfish.h264.decoder` ×13, `c2.goldfish.vp9.decoder` ×3 |
| iso-gpu | `:media` (Java path, driven from `:utility`) and one process that exited before `ps` | `c2.android.aac.decoder` ×9 + ×7 |
| any | an `isolated_app` process | **none** |

Run 1's json predates a fix to the PID→name mapping, so its `ccodec_allocate`
is empty. Its logcat (`iso-rdd-logcat-filtered.txt`) shows PIDs 4724 (`:rdd`,
13 H.264 + 3 VP9) and 5682 (`:utility`, 16 AAC), matching `iso-rdd-ps.txt`.

Decoder names from `HTMLMediaElement.mozRequestDebugInfo()` with iso-rdd
(`runs/decoders-iso-rdd.json`, `scripts/dbg.py`):

| source | video | audio |
|---|---|---|
| H.264+AAC MP4 | `ffvpx video decoder (RDD remote)`, hw | `ffvpx audio decoder (Utility Generic remote)` |
| VP9+Opus | `ffvpx video decoder (RDD remote)`, hw | `ffvpx audio decoder (Utility Generic remote)` |
| AV1+Opus | `ffvpx video decoder (RDD remote)`, **software** | `ffvpx audio decoder (Utility Generic remote)` |
| hls.js fMP4 | `ffvpx video decoder (RDD remote)`, hw | `ffvpx audio decoder (Utility Generic remote)` |

So under iso-rdd, **no** decoder runs in the isolated content process. Software
AV1 (dav1d through ffvpx) runs in RDD and Opus runs in Utility, both with the
app's uid. That is the trade the study's §6e names.

### Process domains (`runs/*-ps.txt`)

In every configuration, the content processes are
`org.redoubtbrowser:zygoteTab…` in `u:r:isolated_app:s0:c512,c768` with ephemeral uids
(`u0_i1` plus `u0_i4`/`u0_i5` in iso-base, `u0_i20`/`u0_i21` in the others), forked by `org.redoubtbrowser_zygote`
(`u:r:app_zygote`). `:gpu`, `:rdd` (only in iso-rdd), `:utility` and `:media` (only in iso-gpu)
are `u:r:untrusted_app` with the app uid `u0_a192`. No `:tab` process runs with the app uid.

### SELinux denials from isolated content

iso-base, iso-rdd run 2 and iso-gpu show **the same four** `isolated_app`
denials (`isolated_app_denials` in the json):

- `read` on sysfs `product_name`;
- `read` on sysfs `product_sku`;
- `read` on `/proc/filesystems`;
- `read` on the `incremental_prop` property file.

All of them are `permissive=0` (denied). None involves media, a device node or
`app_data_file`. The media prefs add **no** new denial. These four are the
baseline that `--check-isolation` should allow.

## Not covered

- arm64 hardware and a real phone's vendor codecs. The goldfish decoders are
  backed by the host.
- WebRTC (H.264 encode now in RDD).
- Short clips and end-of-stream drain (bug 1987001).
- The Firefox 158 or 159 code itself, and a locked `android.cfg` pref set
  instead of the debug config.

## Files

- `scripts/`: `spike.py`, `spike_cfg.py`, `dbg.py`, `vb.py`, `serve.py`,
  `t.html`. Media are LW-M7-43's (`evidence/video-playback/local/media-SHA256SUMS`).
- `runs/`: per-config `*.json` (rows, prefs read, ps, codec allocations,
  denials), `*.out` (driver output), `*-ps.txt`, `*-logcat-filtered.txt`
  (only `CCodec allocate` and `avc: denied` lines; the full logcats stayed in
  scratch), `decoders-iso-rdd.json`, and `iso-rdd-h264-muted.png` (H.264
  playing in isolated content).
