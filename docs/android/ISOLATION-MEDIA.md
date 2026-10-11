# Isolated content with H.264/AAC: the isolation-media prototype

**Owner: LW-M7-50.** Design (e) from the LW-M7-48 study
(`docs/android/ISOLATION-MEDIA-STUDY.md`, on `main` since b5d6ed97). Prototyped
on branch `feature/isolation-media` (cut from `android/firefox-158`, behind a
build overlay, default off); **shipped for Redoubt 158.0-2 on branch
`release/158.0-2-isolation`** (cut from `feature/isolation-media`) as regular
`android.txt` patches with a runtime gate: **ON for Android 12+ (API 31+), OFF
below.** 158.0-1 (2026-10-13) is built from `android/firefox-158` without any of
it.

Owner decisions, verbatim:

| date | question | answer |
|---|---|---|
| 2026-10-10 | plan | "Prototype now, ship ON in a 158 dot release if it tests clean" |
| 2026-10-10 | trade-off | "Keep software codecs in the page process" |
| 2026-10-10 | phone testing | "Yes, separate dev app" |
| 2026-10-11 | phone test result (Pixel 10 Pro, Android 17, dev APK) | "1. worked 2. no problems" (all videos played, no problems) |
| 2026-10-11 | rollout | "158.0-2, Android 12+ only" |

## 0. Rollout in 158.0-2: the runtime gate

**What ships.** Isolated content processes, with the media configuration that
lets them play H.264/HEVC/AAC, are ON by default on **Android 12 (API 31) and
newer**. On **Android 8-11** the app behaves exactly as 158.0-1: no isolated
process, no isolation-media prefs, no codec allowlist.

**Why Android 12+ only.** On the API 30 emulator (OMX codec stack) 9 of 17
media runs failed intermittently, and the same failures reproduce with
upstream's eleven isolated-process prefs on builds without any Redoubt code
(evidence §5); the cause is unknown. API 34 (Codec2) is clean, and the owner's
Pixel 10 Pro (Android 17) played every video with the dev APK. Android 8-11
keep today's behaviour until the API 30 flake is understood. The line at API 31
is the owner's choice; no device between API 31 and 33 has been measured.

**One decision, everything follows it.** The decision is made in exactly one
place, and every other piece reads the result rather than re-deciding:

```
Fenix GeckoProvider.isolatedContentEnabled()   = Build.VERSION.SDK_INT >= 31
  -> GeckoRuntimeSettings.isolatedProcessEnabled(x) / appZygoteProcessEnabled(x)
  -> GeckoRuntime.init(): GeckoProcessManager configured from the settings
       media.redoubt-isolation-media.enabled = pm.isContentIsolated()
         (= GeckoProcessType.determineContentProcessType() != CONTENT,
          the allocator's own choice of content process type)
       added to the initial prefs AFTER the debug-config merge
  -> MOZ_DEFAULT_PREFS (default branch, before prefs.js and autoconfig)
  -> Preferences::GetInstanceForService() (parent, Android only):
       lock media.redoubt-isolation-media.enabled at that value;
       only if true: set + lock the eleven media prefs (section 2a)
  -> Gecko media code reads media.redoubt-isolation-media.enabled:
       RemoteDecoderModule::Supports()      software codecs stay in content
       PDMFactory::CreateDecoder()          RDD/Utility/GPU allowlist
       PDMFactory::AllDecodersAreRemote()   false while isolated
```

| piece | file | follows the decision how |
|---|---|---|
| the decision | `patches/android/isolation-media-process.patch` (Fenix `GeckoProvider.kt`) | `SDK_INT >= 31`, both settings; not readable from Settings or Nimbus |
| gate pref + eleven prefs | `patches/android/isolation-media-prefs.patch` (GeckoView `GeckoRuntime.java`, `GeckoProcessManager.java`; `modules/libpref/Preferences.cpp`) | derived from the process manager GeckoView configured from those settings; locked |
| codec placement and allowlist | `patches/android/isolation-media-codecs-in-content.patch` | every Redoubt line is conditional on the gate pref |
| drain fix | `patches/android/isolation-media-drain-backport.patch` | upstream code (Firefox 159) behind the gate pref: every changed path is taken only while it is true; false gives 158.0's branch, software ffvpx included (section 2d) |

Why this mechanism and not the alternatives:

- **Not static prefs in `librewolf.cfg`** (the prototype's
  `overlay-isolation-media.cfg`): autoconfig cannot see the SDK level or the
  process model, so a cfg would have had to re-implement the SDK rule and could
  drift from it. No Redoubt pref file sets any of the twelve names any more
  (`settings/common.cfg` and `android.cfg` never did), so no `lockPref` fights
  the gate, and `board.py --check-cfg-split` is unchanged.
- **Not `GeckoAppShell::IsIsolatedProcess()` in Gecko**: it answers only inside
  the content process. The allowlist runs in RDD/Utility/GPU and the prefs are
  read by the parent, none of which is isolated; they need the decision as a
  value, and a pref is how Gecko distributes one value to every process.
- **Not a Fenix `Pref.commit()` / `GeckoView:SetDefaultPrefs`**: that runs after
  autoconfig and after Gecko started (AGENTS.md landmine L2, stage 5b), so media
  code could already have read the old values, and it carries no lock.
- **Locked, set before anything reads them**: `MOZ_DEFAULT_PREFS` is parsed in
  `GetInstanceForService()`, before the profile's `prefs.js` and before
  autoconfig (L2 stages 2-4), and the lock beats every later stage. A user value
  in `about:config` for any of the twelve is ignored while locked.
- **The debug config cannot desync it**: GeckoView merges
  `/data/local/tmp/<pkg>-geckoview-config.yaml` (debuggable apps, or
  `am set-debug-app`, which the smoke harness uses) into the prefs before the
  gate pref is added, so the gate always reflects the process model. On the ON
  path the eleven are overwritten and locked after that merge as well.

**Below API 31 nothing changes against 158.0-1, by construction and measured.**
With the gate false: no media pref is set or locked (only the new gate pref
exists, false and locked); `Supports()`, `CreateDecoder()` and
`AllDecodersAreRemote()` take upstream's path (each Redoubt branch starts with
`StaticPrefs::media_redoubt_isolation_media_enabled() &&`); the content process
is plain `:tab` as before. The parent-side allowlist must NOT stay active when
isolation is off: in 158.0-1 the Utility process decodes Opus, Vorbis, FLAC,
MP3 and WAV for content (measured on Beta 2: `ffvpx audio decoder (Utility
Generic remote)`), and an active allowlist would refuse them there. So it is
gated like the rest. So is the drain backport (section 2d): upstream's change
also alters software ffvpx decoding on every Android version, so each changed
path checks the gate and, when it is false, runs 158.0's code. On
the API 30 emulator `--check-isolation` asserts all of this (isolation OFF,
prefs at the 158.0-1 values and unlocked, Java MediaCodec for H.264/AAC, Opus
in Utility, no refusal even with the test hook on), and the same check on
Beta 2 shows the same decoders and processes (evidence `release-158.0-2/`).

**Release builds.** `assets/patches/android.txt` carries the four patches, so a
normal `make android-dir TARGETS=android` (and the release workflow) builds
158.0-2 with the gate; there is no build switch for isolation any more. The
`dev-app` overlay (section 3) remains an overlay, refused for release builds as
before.

Measured results are in [`evidence/lw-m7-50/README.md`](evidence/lw-m7-50/README.md).

## 1. Build overlays (since 158.0-2: `dev-app` only)

In the prototype everything was behind **build overlays**. Since 158.0-2 the
isolation-media patches are regular `android.txt` entries with the runtime gate
of section 0, and `isolation-media` is no longer an overlay
(`KNOWN_OVERLAYS = ("dev-app",)`). The text below describes the overlay
mechanism, which the dev app still uses:

```
make android-dir TARGETS=android OVERLAYS=dev-app
python3 scripts/librewolf-patches.py 158.0 2 --targets=android --overlays=dev-app
```

An overlay `NAME` is `assets/patches/overlay-NAME.txt` (a patch list, same syntax
as `android.txt`, applied after it) plus an optional
`assets/patches/overlay-NAME.cfg` (appended to `lw/librewolf.cfg` after
`common.cfg` + `android.cfg`, so its `lockPref` calls run last).

**OFF is the normal build.** (Prototype-era measurement; since 158.0-2 the normal
build contains the isolation patches, section 0.) With `OVERLAYS` empty, the Makefile's stamp name,
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
  `lw/librewolf.cfg`, which only a stale prototype tree can carry now, and
  `applicationIdSuffix ".dev"` in Fenix's `build.gradle`), for
  `--variant=release` unless the caller passes **`--allow-overlays`**. The dev
  builds pass it; no release path does.
- `.github/workflows/android-release.yaml` has no input that names an overlay,
  fails if `OVERLAYS` is set in its environment, and fails if the patched tree
  carries the marker or a fingerprint. 158.0-2 does not need that: its
  isolation patches are in `android.txt`, not in an overlay.

The gates know the overlays:

| gate | what it does with them |
|---|---|
| `check-patchfail.sh --targets=android --overlays=dev-app` | applies the overlay list after common + android against the tarball |
| `check-patch-order.py` | models a fourth sequence, common + android + every overlay; a list patch and an overlay patch sharing a file are ordered by construction. Since 158.0-2 the isolation-media patches are list patches: `isolated-process.patch -> isolation-media-process.patch` is a declared constraint, and six new shared-file pairs are recorded order-free (measured on the 158.0 RC build2 tarball) |
| `lint-patch-scope.py` | applies the android scope rules to the overlay lists |
| `board.py --check-scope` | counts overlay patches apart (`PATCH-SCOPE.md`: "**1 overlay patch files**") |

## 2. The isolation-media patches (android.txt since 158.0-2)

| piece | file | what |
|---|---|---|
| process model | `patches/android/isolation-media-process.patch` | `.isolatedProcessEnabled(x)` / `.appZygoteProcessEnabled(x)` in `GeckoProvider.kt`, `x = SDK_INT >= 31` (prototype: literal `true`) |
| media prefs | `patches/android/isolation-media-prefs.patch` | upstream's eleven isolated-process prefs, set and locked by Gecko only while content is isolated (prototype: `overlay-isolation-media.cfg`) |
| codec placement | `patches/android/isolation-media-codecs-in-content.patch` | Redoubt-only Gecko change, conditional on the gate pref |
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
`mobile/android` writes them. Since 158.0-2 they are SDK-dependent (section 0):
on Android 12+ Gecko sets them on the default branch and locks them at startup
(`RedoubtApplyIsolationMediaPrefs()` in `Preferences.cpp`); on Android 8-11
they are not touched. The two sides are recorded in
`docs/android/expected-prefs-isolation-media.txt` (API 31+, locked) and
`docs/android/expected-prefs-no-isolation.txt` (API < 31, the 158.0-1 values,
unlocked), each with the gate pref `media.redoubt-isolation-media.enabled`
(true / false, locked); `expected-prefs.txt` lists none of these names and is
unchanged. `--check-isolation` reads them back (rows `isolation-mode`,
`isolation-prefs`). A unit test keeps the patch's table, both files and the
harness constants equal.

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

| codec | where it decodes when isolated (Android 12+) | with upstream's prefs alone | 157.0-3 / 158.0-1 / 158.0-2 below Android 12 (isolation off) |
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
backport adds that override. It is a separate patch with attribution in its
header. Drop it at the 159 rebase.

**Gated since the 158.0-2 review.** Upstream's change is not limited to the
MediaCodec-backed decoder. On any Android version it also changes software
ffvpx: the video decoder maps `AVERROR_EOF` from `avcodec_send_packet` the other
way round (158 returns `NS_ERROR_NOT_AVAILABLE` there without MediaCodec, 159
`NS_ERROR_DOM_MEDIA_END_OF_STREAM`), the audio decoder stops re-sending the empty
drain packet, and flush/shutdown reject a pending drain promise. The first
158.0-2 build shipped it unconditionally, which broke "Android 8-11 behave as
158.0-1". Now `FFmpegDataDecoder` reads the gate
(`StaticPrefs::media_redoubt_isolation_media_enabled()`, the locked pref of
section 0) once per decoder into `mDrainFixEnabled`, and every changed path
tests it:

| path | gate true (Android 12+) | gate false (Android 8-11) |
|---|---|---|
| `FFmpegDataDecoder::ProcessDrain` | cancel the drain timer on resolve/reject | 158.0: no timer exists (only gated paths arm it) |
| `FFmpegDataDecoder::ProcessFlush` / `ProcessShutdown` | reject a pending drain promise, cancel the timer | 158.0: neither |
| `FFmpegAudioDecoder` hw init | `mIsMediaCodec` recorded | stays false |
| `FFmpegAudioDecoder::ProcessFlush` (new override) | reset `mHasSentDrainPacket` | only forwards to the base |
| `FFmpegAudioDecoder` send packet | empty drain packet sent once | 158.0: every packet sent, same `switch` |
| `FFmpegAudioDecoder` `EAGAIN` while draining | defer the drain while MediaCodec holds frames | 158.0: no deferral |
| `FFmpegVideoDecoder` `AVERROR_EOF` on send | upstream's fixed mapping | 158.0's mapping, verbatim |
| `FFmpegVideoDecoder` `EAGAIN` on receive | defer while draining | 158.0: `NS_OK` at once |
| `FFmpegVideoDecoder::ResumeDrain` | upstream (via the base) | 158.0's body, verbatim |
| `FFmpegVideoDecoder::MaybeQueueDrain` | upstream (`MaybeDeferDrain`) | 158.0's condition, verbatim |

The new members, the timer helpers and the `virtual` on `ResumeDrain()` exist
on both paths but do nothing unless a gated branch calls them. API 30 runs with
the gated build: evidence `release-158.0-2/README.md`, section 7.

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
  set. Since 158.0-2 the check grades against the device's SDK level, like the
  build's gate: row `isolation-mode` requires the locked gate pref to equal
  `SDK >= 31`, and below API 31 the other rows require isolation OFF and media
  as in 158.0-1 (no RDD, the eleven prefs at their 158.0-1 values and unlocked,
  Java MediaCodec for H.264/AAC, Opus in Utility, no allowlist refusal even with
  the test hook on; row `isolation-allowlist-inactive`). A build without the gate
  (158.0-1, the prototype) fails `isolation-mode`.
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

0. The gate chain of section 0: `GeckoRuntime.init()` still configures
   `GeckoProcessManager` before it builds `GeckoThread.InitInfo`;
   `GeckoProcessType.determineContentProcessType()` is still the only place the
   content process type is chosen; `MOZ_DEFAULT_PREFS` is still parsed in
   `Preferences::GetInstanceForService()`; no Redoubt pref file sets any of the
   twelve names (`grep` `settings/*.cfg`).

1. `RemoteDecoderModule::Supports()` still has the `#ifdef ANDROID` filter
   block the codecs patch extends, and every remote decoder is still created
   through `PDMFactory::CreateDecoder()` (`RemoteVideoDecoderParent` and
   `RemoteAudioDecoderParent::RecvConstruct()`): if upstream adds another
   creation path in RDD/Utility, the allowlist must cover it.
2. Drop the drain backport from 159 on, and with it its gate: from 159 software
   ffvpx behaves as upstream on every Android version.
3. `variants.yml` `geckoview-isolated-process`: still the eleven prefs? Copy
   any change into `isolation-media-prefs.patch`, both expected-prefs files and
   the harness constants (the unit test will insist).
4. The API 30 flake (section 6): if it is understood and fixed, lowering the
   SDK floor is a one-line change in `isolation-media-process.patch` plus
   `ISOLATION_MIN_SDK` in the harness, and needs an owner decision.
5. **`GeckoRuntime.init()` ordering.** The gate pref is computed once, in the
   `init()` that starts Gecko, from the process manager that same call
   configured. `init()` reconfigures the process-manager singleton
   (`setIsolatedProcessEnabled`, `setAppZygoteEnabled`) *before* it learns
   that `GeckoThread.init()` refuses a second start. So a later default
   `GeckoRuntime` (`GeckoRuntime.getDefault()`, whose `GeckoRuntimeSettings`
   leave isolation off) or a second `GeckoRuntime.create()` with other settings
   would switch new content processes back to plain `:tab` while the gate, and
   with it the media prefs and the allowlist, stays true. Fenix 158 never does
   this: `GeckoProvider` creates the one runtime with `GeckoRuntime.create()`
   and passes it to `GeckoEngine` and `GeckoViewFetchClient` explicitly
   (`Core.kt`), so their `getDefault()` default arguments are never evaluated,
   and `fenix/app/src/main` calls `getDefault()` nowhere. At every rebase,
   `grep -rn 'GeckoRuntime.getDefault\|GeckoRuntime.create(' mobile/android/fenix/app/src/main
   mobile/android/android-components/components/*/*/src/main` and confirm that
   still holds (REBASE.md section 6f).

## 6. Status (2026-10-11) and the phone test

Clean on the API 34 emulator (Codec2): `--check-isolation`, `--check-video`, the
3-round video matrix, delete-on-quit, launcher, uBO and autofill. On the API 30
emulator (OMX) the full suite incl. graphics passes, but 9 of 17 media/isolation
runs failed intermittently (page never loads, or H.264/MSE stalls), and the same
failures reproduce with upstream's eleven prefs on builds **without** this
overlay's Gecko code. Details: evidence §5. (Prototype status; the phone test and
the 158.0-2 results are below and in section 8.)

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

## 8. Redoubt 158.0-2 (2026-10-11)

Built from `release/158.0-2-isolation` (`b78d361d`) against the GPG-verified
158.0 RC build2 tarball, C/C++ `-Werror` (Rust lints capped to warnings, as
before). Evidence: `evidence/lw-m7-50/release-158.0-2/README.md`.

| where | result |
|---|---|
| gates | `check-patchfail` android, android + `dev-app`, desktop; `check-patch-order`; `lint-patch-scope`; `board.py --check/--check-scope/--check-cfg-split/--diff-mozconfig --strict`; 132 harness unit tests: all pass |
| API 34 (isolation ON) | `--check-isolation` 3/3 (gate true and locked, H.264 in `:rdd`, AAC in `:utility`, software codecs in isolated content, RDD/Utility refuse VP9/Opus); `--check-video` 3/3; full suite all rows but `webgl` (the API 34 graphics-harness limitation) |
| API 30 (isolation OFF) | `--check-isolation` 3/3 (gate false and locked, the eleven at 158.0-1 values and unlocked, Java MediaCodec, Opus in Utility, no refusal with the test hook); Beta 2 on the same AVD gives the same rows except `isolation-mode`; `--check-video` 3/3; full suite 10/10 including graphics acceptance |
| dev variant | x86_64 `--check-isolation` passes on both levels; arm64 APK built and signed, not yet on the phone (it was offline) |

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
process and the GPU process. None of that is new with isolation; under
isolation it is the set of doors out of the isolated process.

**Compared with today.** The released Redoubt (157.0.1-1, and 158.0-1) has **no
content isolation at all**: since 157.0-3, web content runs as `untrusted_app`
with the app uid, like Firefox. There, a bug in any content-process parser
(HTML, JavaScript and its JIT, images, fonts, every codec decoded in content) is
already code execution with profile access; VP8/VP9 go to Java MediaCodec via
`:media` where the device offers it, and Opus/Vorbis/FLAC/MP3/WAV to `:utility`,
all app uid. With isolation (158.0-2 on Android 12+), a content-process bug alone gives an `isolated_app` process with an
isolated uid that cannot open the profile; reaching the profile takes a second
bug, in the H.264/HEVC/AAC path above, in the remaining RDD/Utility IPC, or in
the parent or GPU process.

| | 157.0.1-1 / 158.0-1, and 158.0-2 on Android 8-11 (isolation off) | 158.0-2 on Android 12+ (isolated) |
|---|---|---|
| web content process | `untrusted_app`, app uid: profile readable | `isolated_app`, isolated uid: profile not readable |
| H.264, HEVC, AAC parsed by | content (app uid), Java MediaCodec via `:media` | `:rdd` / `:utility` (app uid), NDK MediaCodec |
| VP8, VP9, AV1 parsed by | content or `:media` (app uid) | isolated content only (RDD/Utility refuse them) |
| Opus, Vorbis, FLAC, MP3, WAV parsed by | `:utility` (app uid) | isolated content only (Utility refuses them) |
| bugs needed from a web page to the profile | one, in any content parser | two: one in content, one in a door out of it |
