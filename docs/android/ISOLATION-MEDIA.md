# Isolated content with H.264/AAC: the isolation-media prototype

**Owner: LW-M7-50.** Prototype of design (e) from the LW-M7-48 study
(`docs/android/ISOLATION-MEDIA-STUDY.md`, on `main` since b5d6ed97). Branch
`feature/isolation-media`, cut from `android/firefox-158` so that it can ship in
a 158 dot release and later merge into `main`.

Owner decisions 2026-10-10, verbatim:

| question | answer |
|---|---|
| plan | "Prototype now, ship ON in a 158 dot release if it tests clean" |
| trade-off | "Keep software codecs in the page process" |
| phone testing | "Yes, separate dev app" |

Measured results are in [`evidence/lw-m7-50/README.md`](evidence/lw-m7-50/README.md).

## 1. The build switch

Everything is behind **build overlays**, which are off unless a build names them:

```
make android-dir TARGETS=android OVERLAYS=isolation-media            # the feature
make android-dir TARGETS=android OVERLAYS=isolation-media,dev-app    # + the dev app
python3 scripts/librewolf-patches.py 158.0 1 --targets=android --overlays=isolation-media,dev-app
```

An overlay `NAME` is `assets/patches/overlay-NAME.txt` (a patch list, same syntax
as `android.txt`, applied after it) plus an optional
`assets/patches/overlay-NAME.cfg` (appended to `lw/librewolf.cfg` after
`common.cfg` + `android.cfg`, so its `lockPref` calls run last).

**OFF is today's build.** With `OVERLAYS` empty, the Makefile's stamp name,
patch-list prerequisites and patcher command expand to exactly the strings they
had before (checked with `make -pn`), and the patcher takes exactly the code
path it took before. The patched tree of `feature/isolation-media` without
overlays is byte-identical to `android/firefox-158`'s (evidence §1), and the
x86_64 APK is compared with Beta 2's in evidence §2.

**Only on purpose.** Three guards keep an overlay out of a build that did not
ask for one (review of LW-M7-50):

- The Makefile takes `OVERLAYS` **only from its command line**. A non-empty
  value from the environment (`export OVERLAYS=...`, a runner's env, `make -e`)
  stops make with an error; an empty one is dropped; any other origin is reset to
  empty. (Before, `OVERLAYS ?=` let an exported variable switch overlays on
  without a word.)
- The patcher writes `redoubt-overlays.txt` (one overlay per line) at the root of
  an overlay tree, and only there. `scripts/android-apk.sh` refuses a tree that
  has it, or either overlay fingerprint (`OVERLAY isolation-media` in
  `lw/librewolf.cfg`, `applicationIdSuffix ".dev"` in Fenix's `build.gradle`), for
  `--variant=release` unless the caller passes **`--allow-overlays`**. The dev
  builds pass it; no release path does.
- `.github/workflows/android-release.yaml` has no input that names an overlay,
  fails if `OVERLAYS` is set in its environment, and fails if the patched tree
  carries the marker or a fingerprint. Shipping an overlay ON in a dot release
  needs a new, explicit dispatch input there and a change to that check; that
  is deliberately not in place.

The gates know the overlays:

| gate | what it does with them |
|---|---|
| `check-patchfail.sh --targets=android --overlays=isolation-media,dev-app` | applies the overlay lists after common + android against the tarball |
| `check-patch-order.py` | models a fourth sequence, common + android + every overlay; a list patch and an overlay patch sharing a file are ordered by construction; `isolated-process.patch -> isolation-media-process.patch` is a declared constraint |
| `lint-patch-scope.py` | applies the android scope rules to the overlay lists |
| `board.py --check-scope` | counts overlay patches apart (`PATCH-SCOPE.md`: "**4 overlay patch files**") |

## 2. Overlay `isolation-media`

| piece | file | what |
|---|---|---|
| process model | `patches/android/isolation-media-process.patch` | `.isolatedProcessEnabled(true)` / `.appZygoteProcessEnabled(true)` in `GeckoProvider.kt`; still literals |
| media prefs | `assets/patches/overlay-isolation-media.cfg` | upstream's eleven isolated-process prefs, locked (below) |
| codec placement | `patches/android/isolation-media-codecs-in-content.patch` | Redoubt-only Gecko change, ~20 lines |
| drain fix | `patches/android/isolation-media-drain-backport.patch` | backport of upstream bug 1987001 (Firefox 159) |

### 2a. The eleven prefs

Name for name and value for value from bug 1988531 part 1, mozilla-firefox
commit `e0286afb5f6836d607a3f218a527db69979c0bbd` (2026-10-06, Firefox 159),
`taskcluster/test_configs/variants.yml`, variant `geckoview-isolated-process`:

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

All eleven are `mirror: always` static prefs in 158.0 and nothing under
`mobile/android` writes them, so they go in through the pref-locking model the
rest of Redoubt uses: autoconfig `lockPref`, in a fragment that only overlay
builds append. `docs/android/expected-prefs-isolation-media.txt` records them
for the switched build (on top of `expected-prefs.txt`, which is unchanged), and
`--check-isolation` reads them back (row `isolation-prefs`). A unit test keeps
the cfg, the expected-prefs file and the harness constant equal.

### 2b. Software codecs stay in the page process

Upstream sends every codec to RDD/Utility once these prefs are on (study §9:
software AV1 in RDD, Opus in Utility, both with the app uid). The owner chose to
keep software decoding in the isolated content process. The change is in
`RemoteDecoderModule::Supports()`, inside the Android block that already narrows
remote support: a non-CDM request is supported remotely only for H.264, HEVC and
AAC. Everything else is refused, so `PDMFactory` falls through to the in-process
ffvpx/Agnostic modules, as it did in 157.0-2. `PDMFactory::AllDecodersAreRemote()`
returns false on Android to match (its one Android consumer keeps initialising
content-side media devices, as every Android build does today).

| codec | where it decodes with the overlay | with upstream's prefs alone | 157.0-3 (isolation off) |
|---|---|---|---|
| H.264, HEVC | `:rdd`, NDK MediaCodec | `:rdd` | content, Java MediaCodec via `:media` |
| AAC | `:utility`, NDK MediaCodec | `:utility` | content, Java MediaCodec via `:media` |
| VP8, VP9, AV1 | **isolated content**, software | `:rdd` (VP9 in hardware where offered) | content (Java MediaCodec for VP8/VP9 where offered) |
| Opus, Vorbis, FLAC, MP3, WAV | **isolated content**, software | `:utility` | `:utility` |

Cost: VP9/AV1 are not hardware-decoded under isolation (as in 157.0-2). Gain:
attacker-controlled VP9/AV1/Opus bitstreams are parsed in a process that cannot
read the profile.

**Enforced in the decoder processes too.** `Supports()` runs in the isolated
content process, the one this design assumes an attacker may control, so on its
own it only routes. The same patch makes the decoder processes enforce the
allowlist: `PDMFactory::CreateDecoder()`, which `RemoteVideoDecoderParent` and
`RemoteAudioDecoderParent::RecvConstruct()` both call, refuses in the RDD, Utility
and GPU processes every decoder whose mime type is not H.264 (`video/avc`,
`video/mp4`), HEVC (`video/hevc`) or AAC (`audio/mp4a-latm`), with or without a
CDM. Content gets `NS_ERROR_DOM_MEDIA_FATAL_ERR`, and the refusing process logs
(logcat tag `Gecko`):

```
Redoubt isolation-media: RDD process refused a decoder for 'video/vp9' (allowlist: H.264, HEVC, AAC)
```

On the honest path content never asks, so the line never appears. A test hook
proves the refusal on a device: the static pref
`media.redoubt-test.skip-content-codec-filter` (default false, set by no Redoubt
pref file, not locked) makes `Supports()` skip its filter, so content asks
RDD/Utility for VP9 and Opus as a compromised content process could. Both refuse;
the remote `Construct()` is part of decoder creation, so content's `PDMFactory`
falls through to its own ffvpx and the clip still plays, decoded in the isolated
process. Turning the pref on therefore moves no decoding out of the isolated
process, which is why it can stay in a shipping build. `--check-isolation` row
`isolation-remote-refusal` sets it, checks the refusals and the fallback, and
clears it again.

### 2c. Native HLS: fail closed

`HLSDecoder::IsEnabled()` is false in an isolated process
(`dom/media/hls/HLSDecoder.cpp:360-363`; ExoPlayer cannot bind services there,
bug 2043165). Decision: **fail closed, no workaround.**
`canPlayType("application/vnd.apple.mpegurl")` is `""`, and a page whose only
source is a native `.m3u8` gets `MEDIA_ERR_SRC_NOT_SUPPORTED` (error 4). Pages
that feature-detect (hls.js, video.js, Shaka, every major site player) fall back
to MSE, which plays. Re-enabling native HLS would need ExoPlayer in a
non-isolated process, which is the study's rejected design (b).

### 2d. The drain fix (bug 1987001)

The NDK MediaCodec decoder in 158 completes a drain while MediaCodec still holds
frames, so the end of a stream is lost and a short clip may show no frame.
Upstream fixed it in 159 (`5cf346157068a285144cfb2f0409e81a2796ac59`). It
backports to 158 almost cleanly: 14 of 15 hunks apply with offsets only; one adds
a line to an `FFmpegAudioDecoder::ProcessFlush()` override that 158 lacks, so the
backport adds that override. It is a separate patch, behind the same switch,
with attribution in its header. Drop it at the 159 rebase.

## 3. Overlay `dev-app`

`patches/android/dev-app.patch`: release build type gets `applicationIdSuffix
".dev"` (**org.redoubtbrowser.dev**), deep-link scheme `redoubt-dev`, app name
**"Redoubt Dev"**, amber adaptive-icon background. The release variant is not
touched by a build without the overlay.

- **No update check.** `scripts/android-apk.sh` refuses `--update-check`,
  `LW_UPDATE_CHECK_PUBKEY` and `LW_UPDATE_CHECK_ENDPOINT` for a tree with the
  overlay, so the check is compiled out.
- **Never the release key.** `scripts/android-sign-dev.sh` signs only an unsigned
  APK whose package is `org.redoubtbrowser.dev`, reads the keystore password from
  a file outside the repository, refuses a keystore named like the release one,
  and deletes its output if the certificate is the release fingerprint published
  in `SIGNING.md`. The dev key lives in `~/redoubt-artifacts/keep/dev-keys/`
  (`redoubt-dev.p12`, password in `redoubt-dev.pass`, both mode 0600; certificate
  SHA-256 `1D:FC:33:1A:11:4E:24:1A:99:4E:A9:A0:EB:A5:6E:5B:13:A2:45:53:A2:77:BF:00:9B:F3:82:24:48:36:55:A5`).
- versionCodes do not matter: a different applicationId never competes with the
  release app's codes.

```
scripts/android-sign-dev.sh --ks ~/redoubt-artifacts/keep/dev-keys/redoubt-dev.p12 \
    --ks-pass-file ~/redoubt-artifacts/keep/dev-keys/redoubt-dev.pass \
    --out redoubt-dev-x86_64.apk fenix-x86_64-release-unsigned.apk
```

## 4. Tests

- `scripts/android-smoke.sh --check-isolation` (new, `SMOKE.md`): content
  processes `isolated_app` with isolated uids, forked by the app zygote; an
  `:rdd` process; the 11 prefs locked; H.264+AAC decoded in RDD/Utility and
  VP8/VP9/AV1/Opus in content (decoder names from `mozRequestDebugInfo()`); every
  `CCodec allocate` outside isolated processes and H.264 in `:rdd`; no
  `isolated_app` SELinux denial outside the LW-M7-48 baseline; the profile
  directory 0700 `app_data_file`; and (`isolation-remote-refusal`) with the test
  hook on, `:rdd` refuses `video/vp9` and `:utility` refuses `audio/opus` while
  the clip still plays from content, and no refusal appeared before the hook was
  set. It fails on a build without the overlay.
  A gtest was not used: `dom/media/gtest` exists, but the check is Android-only
  (`MOZ_WIDGET_ANDROID`) and needs real RDD/Utility processes, and no gtest
  binary is built or run for Android here; the device row exercises the real
  IPC path instead.
- `--check-video` with isolation on, repeated.
- The video matrix from LW-M7-48 (`evidence/lw-m7-50/scripts/matrix.py`):
  long clips, short clips (0.3 s and 0.5 s, the drain bug's case), AAC-only,
  muted autoplay and click, hls.js over TS and fMP4, native HLS; 3 rounds, fresh
  profile per round.

## 5. Re-verify at every rebase

Everything in study §10, plus:

1. `RemoteDecoderModule::Supports()` still has the `#ifdef ANDROID` filter
   block the codecs patch extends, and every remote decoder is still created
   through `PDMFactory::CreateDecoder()` (`RemoteVideoDecoderParent` and
   `RemoteAudioDecoderParent::RecvConstruct()`): if upstream adds another
   creation path in RDD/Utility, the allowlist must cover it.
2. Drop the drain backport from 159 on.
3. `variants.yml` `geckoview-isolated-process`: still the eleven prefs? Copy
   any change into `overlay-isolation-media.cfg`, the expected-prefs file and
   the harness constant (the unit test will insist).

## 6. Status (2026-10-11) and the phone test

Clean on the API 34 emulator (Codec2): `--check-isolation`, `--check-video`, the
3-round video matrix, delete-on-quit, launcher, uBO and autofill. On the API 30
emulator (OMX) the full suite incl. graphics passes, but 9 of 17 media/isolation
runs failed intermittently (page never loads, or H.264/MSE stalls), and the same
failures reproduce with upstream's eleven prefs on builds **without** this
overlay's Gecko code. Details: evidence §5. Not yet run on a real device.

After the review fixes (evidence §9): RDD/Utility refuse every decoder but
H.264/HEVC/AAC on their own, measured on API 34 with the test hook
(`isolation-remote-refusal`, 3 of 3 runs; it fails on the previous build), and
`--check-video` 3 of 3. The phone APKs below are the rebuilt ones.

**Phone test (owner, Android 14+ arm64).** The dev APK is
`redoubt-dev-iso-arm64-v8a.apk` (sha256 in evidence §9; the §6 one is
superseded), signed with the dev key.
It installs next to the release Redoubt and does not touch its data.

1. Copy it to the phone and open it, or run `adb install redoubt-dev-iso-arm64-v8a.apk`.
   It is a separate app (new applicationId, own signer), so it never replaces
   or updates the release app.
2. Allow "install unknown apps" for the file manager if asked; Android shows
   "Redoubt Dev" with an amber icon.
3. Check before trusting it: `apksigner verify --print-certs` shows SHA-256
   `1dfc331a114e241a994ea9a0eba56e5b13a24553a277bf009bf38224483655a5`, which is
   NOT the release fingerprint in `SIGNING.md`.
4. Try the sites from LW-M7-43 (redgifs.com, pornhub.com), YouTube, a few short
   clips (GIF-style MP4s), and an audio-only page. Report any video that plays
   in release Redoubt and not in Redoubt Dev.
5. Optional, with USB debugging:
   `adb shell ps -A -o LABEL,USER,NAME | grep redoubtbrowser.dev` must show the
   tab processes as `isolated_app` with `u0_i…` users.
6. Uninstall when done: `adb uninstall org.redoubtbrowser.dev`.

## 7. Attack surface

What an attacker who controls an isolated content process can still reach, and
what changes against the release Redoubt.

**Still reachable: H.264, HEVC and AAC parsing outside the isolated process.**
Isolated content can make the RDD process (`:rdd`) parse attacker-controlled
H.264 and HEVC, and the Utility process (`:utility`) parse attacker-controlled
AAC. Both run as `untrusted_app` with the **app uid**, so they can read and write
the profile, and Android builds of Gecko have **no Gecko sandbox** (`MOZ_SANDBOX`
is not built); only the platform's per-app SELinux domain and seccomp filter
apply. The bytes are handled there by ffvpx in its hardware mode (FFmpeg's
MediaCodec wrapper, which among other things parses the H.264/HEVC parameter
sets in the `avcC`/`hvcC` extradata) and by Gecko's remote-decoder glue, then
handed to the NDK MediaCodec. MediaCodec itself decodes in the platform's media server
processes (`media.swcodec` for Android's software codecs, the vendor Codec2/OMX
HAL for hardware ones), outside Redoubt, as for every Android app that plays
video. A memory-safety bug in that H.264/HEVC/AAC path is a way from the
isolated process to the profile.

**After the decoder-process allowlist (section 2b): no other decoder.** RDD,
Utility and GPU refuse every other decoder whatever content asks for: VP8, VP9,
AV1, Opus, Vorbis, FLAC, MP3, WAV and the rest are parsed only inside the
isolated content process. `--check-isolation` row `isolation-remote-refusal`
measures this on the device by making content ask.

What the allowlist does not narrow, stated so that nobody reads more into it:
it limits which **decoders** can be created, not the IPC protocols themselves.
Isolated content still talks to RDD and Utility over `PRemoteMediaManager` and
the decoder actors (sample buffers in shared memory, flush/drain, readback),
can ask RDD for a platform video **encoder** (the locked
`media.use-remote-encoder.video.platform`; its input is raw frames, not a
compressed bitstream), and can construct the MediaDrm CDM actor even though EME
is off by pref. And, as in every Gecko build, it still talks to the parent
process and the GPU process. None of that is new with this overlay; under
isolation it is the set of doors out of the isolated process.

**Compared with today.** The released Redoubt (157.0.1-1, and 158.0-1) has **no
content isolation at all**: since 157.0-3, web content runs as `untrusted_app`
with the app uid, like Firefox. There, a bug in any content-process parser
(HTML, JavaScript and its JIT, images, fonts, every codec decoded in content) is
already code execution with profile access; VP8/VP9 go to Java MediaCodec via
`:media` where the device offers it, and Opus/Vorbis/FLAC/MP3/WAV to `:utility`,
all app uid. With this
overlay, a content-process bug alone gives an `isolated_app` process with an
isolated uid that cannot open the profile; reaching the profile takes a second
bug, in the H.264/HEVC/AAC path above, in the remaining RDD/Utility IPC, or in
the parent or GPU process.

| | 157.0.1-1 / 158.0-1 (isolation off) | isolation-media overlay |
|---|---|---|
| web content process | `untrusted_app`, app uid: profile readable | `isolated_app`, isolated uid: profile not readable |
| H.264, HEVC, AAC parsed by | content (app uid), Java MediaCodec via `:media` | `:rdd` / `:utility` (app uid), NDK MediaCodec |
| VP8, VP9, AV1 parsed by | content or `:media` (app uid) | isolated content only (RDD/Utility refuse them) |
| Opus, Vorbis, FLAC, MP3, WAV parsed by | `:utility` (app uid) | isolated content only (Utility refuses them) |
| bugs needed from a web page to the profile | one, in any content parser | two: one in content, one in a door out of it |
