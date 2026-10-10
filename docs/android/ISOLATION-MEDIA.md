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
  directory 0700 `app_data_file`. It fails on a build without the overlay.
- `--check-video` with isolation on, repeated.
- The video matrix from LW-M7-48 (`evidence/lw-m7-50/scripts/matrix.py`):
  long clips, short clips (0.3 s and 0.5 s, the drain bug's case), AAC-only,
  muted autoplay and click, hls.js over TS and fMP4, native HLS; 3 rounds, fresh
  profile per round.

## 5. Re-verify at every rebase

Everything in study §10, plus:

1. `RemoteDecoderModule::Supports()` still has the `#ifdef ANDROID` filter
   block the codecs patch extends.
2. Drop the drain backport from 159 on.
3. `variants.yml` `geckoview-isolated-process`: still the eleven prefs? Copy
   any change into `overlay-isolation-media.cfg`, the expected-prefs file and
   the harness constant (the unit test will insist).
