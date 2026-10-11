# LW-M7-50, Redoubt 158.0-2: isolation for Android 12+ with a runtime gate

Owner decision 2026-10-11, verbatim: **"158.0-2, Android 12+ only"**. Isolation
and its media prefs are ON by default for Android 12 (API 31) and newer;
Android 8-11 keep 158.0-1 behaviour. Design: `docs/android/ISOLATION-MEDIA.md`
section 0. Branch `release/158.0-2-isolation`, cut from `feature/isolation-media`
(2fa22e51, unchanged); the code commit is `b78d361d`. Not pushed.

Every hash below comes from `sha256sum` or `git rev-parse` in this session.

## Inputs

| what | value |
|---|---|
| Firefox source | `firefox-158.0.source.tar.xz`, 158.0 RC build2, downloaded again on 2026-10-11 from `archive.mozilla.org/pub/firefox/candidates/158.0-candidates/build2/source/` (`releases/158.0` was still 404), `gpg --verify` good signature, subkey `827E658608679618CD349F93678E455D76767AA3` (primary `14F26682D0916CDD81E37B6D61B7B526D98F0353`), sha256 `fc77f7801d7580a600af683cc367e261eb1ec74647e84a91b4a1e3c1dd5aa2bb` (the pinned value) |
| build image | `localhost/librewolf-android-build:fx158`, id `98e61be72eec` |
| build date | `20261011120000`; `version.android` 158.0, `release.android` 2 in the build copies only (the committed files are untouched) |
| compiler flags | `assets/mozconfig.android` + `ac_add_options --enable-warnings-as-errors` (C/C++ `-Werror`) + `export RUSTFLAGS="--cap-lints warn"`: `--enable-warnings-as-errors` also makes rustc `-Dwarnings`, and the in-tree app-services `remote_settings` crate has dead-code warnings that are not Redoubt's, so Rust lints are capped back to warnings, as for the prototype builds. Java/Kotlin build with the Fenix/GeckoView defaults (Kotlin `-Werror`). |

## 1. Gates (`gates/`)

Against that tarball, tree content of `b78d361d`:

| gate | result |
|---|---|
| `check-patchfail.sh --targets=android` (70 patches) | success (`patchfail-android.out`, rc 0) |
| `check-patchfail.sh --targets=android --overlays=dev-app` | success (`patchfail-android-devapp.out`, rc 0) |
| `check-patchfail.sh --targets=desktop` | success (`patchfail-desktop.out`, rc 0) |
| `check-patch-order.py` | ok: 39/39 declared constraints, 172 shared-file pairs classified |
| `lint-patch-scope.py` | OK, 115 patch files |
| `board.py --check` / `--check-scope` / `--check-cfg-split` / `--diff-mozconfig --strict` | ok (scope: 22 common, 44 desktop, 48 android, 1 overlay patch file) |
| `scripts/tests/test-android-smoke.py` | 132 tests OK (15 new and 1 rewritten for the SDK-dependent `--check-isolation`). Other `scripts/tests`: `gates/scripts-tests.out`; four fail on a pinned hash of patches this branch does not touch, identically on 2fa22e51 (pre-existing) |

The six new shared-file pairs (the isolation patches are list patches now) were
replayed with `gates/measure.py` (`gates/order-measure.out`): the hunks of every
common + android entry for the shared file, in list order and with the later
patch moved directly before the earlier one. All six give byte-identical results
(GeckoProvider.kt `e0bb4847…c839`, Preferences.cpp `aef1f2a5…afe6d`,
StaticPrefList.yaml `91b48814…9a26`, each equal to the patched tree's file) and
are recorded in `REVIEWED_ORDER_FREE`. `isolated-process -> isolation-media-process`
stays a declared constraint: the swap rejects.

## 2. Builds

| build | tree | APK | sha256 |
|---|---|---|---|
| x86_64 release variant | no overlay (the 158.0-2 patch set) | `redoubt-158.0-2-x86_64-throwaway.apk`, `org.redoubtbrowser` 158.0-2, versionCode 2016189734, signed with the throwaway key (cert sha256 `31e9a40f…b760`) | `e3b30a892e20d4b78a36677457c0b4046cafa96e7487a5f895a0a54809dac0cc` |
| (unsigned) | | `fenix-x86_64-release-unsigned.apk` | `95c4319c38332d69eb4ff5e9ff5d43cfa5eab56c62466bb8f14f65e45c74ac27` |
| arm64-v8a dev variant | `OVERLAYS=dev-app` | `redoubt-dev-158.0-2-arm64-v8a.apk`, `org.redoubtbrowser.dev` 158.0-2, versionCode 2016189730, signed by `scripts/android-sign-dev.sh` with the dev key (cert sha256 `1dfc331a114e241a994ea9a0eba56e5b13a24553a277bf009bf38224483655a5`) | `58edf016dfb3faf1bec5567c113f553c9ef42376245a12d40551129d7a84bf85` |
| (unsigned) | | `fenix-arm64-v8a-release-unsigned.apk` | `28bc59734875de6f8f6c4b68027b52778d010e2cfebfb3040ade670225d25800` |
| x86_64 dev variant | `OVERLAYS=dev-app` | `redoubt-dev-158.0-2-x86_64.apk`, `org.redoubtbrowser.dev`, dev key | `8d05379c6f5692cc03a663f8a45ee539ed38069eb3b469ee277cb500c25ee358` |
| (unsigned) | | `fenix-x86_64-release-unsigned.apk` | `0c8bcbdbedcca2cf764756247721f449137fe26cf2e681df8dfc2f670d54e1ef` |

All Gecko compiles passed with C/C++ `-Werror` (`MACH_EXIT=0` for both ABIs).
The first x86_64 APK step died with "Gradle build daemon disappeared
unexpectedly" while the arm64 APK step and a third build ran on the same host
(memory); the APK step alone was re-run on the same tree and AAR and passed
(`apkonly.sh`). The x86_64 dev variant's first APK step failed on a transient
HTTP 500 from maven.mozilla.org while resolving a Compose artifact; the re-run
passed. Build logs: `build-*-commands.log`.

## 3. API 34 emulator, isolation ON (`device-api34/`)

AVD `iso34`, API 34 `google_apis` x86_64, 4 vCPU, 4 GB, `-gpu swangle`,
`-wipe-data`, serial `emulator-5594`; the x86_64 release-variant APK.

- `--check-isolation` **3/3 PASS**, 12 rows each (`check-isolation-{1,2,3}`):
  `isolation-mode` "API 34: isolation expected ON (gate: SDK >= 31);
  media.redoubt-isolation-media.enabled=true, locked"; the eleven prefs set and
  locked; H.264 `ffvpx video decoder (RDD remote)`, AAC `ffvpx audio decoder
  (Utility Generic remote)`; VP8/VP9/AV1/Opus decoded in content; content
  processes `isolated_app` with isolated uids forked by the app zygote;
  `c2.goldfish.h264.decoder` in `:rdd`; only baseline `isolated_app` denials;
  `isolation-remote-refusal`: `:rdd` refused `video/vp9`, `:utility` refused
  `audio/opus` with the test hook on, and the clip still played in content.
- `--check-video` **3/3 PASS** (`video`, `video-h264`, `video-mse`).
- Full default suite (`full-suite-1`): 9 of 10 rows PASS; `webgl` fails with "No
  org.redoubtbrowser window is in the input dispatcher's window list", the known
  API 34 limitation of the graphics harness (its `dumpsys input` parser is
  written for API 30; the prototype's API 34 run failed the same way,
  `../device-api34/full-suite-api34-dev.out`). Graphics acceptance is the API 30
  run below. `full-suite-1-prefs.txt`: the 59-pref dump.

## 4. API 30 emulator, isolation OFF (`device-api30/`)

AVD `iso30`, API 30 `default` x86_64 (OMX codecs), 4 vCPU, 3 GB, `-gpu swangle`,
`-wipe-data`, serial `emulator-5584`; the same APK.

- `--check-isolation` **3/3 PASS**, 12 rows each: `isolation-mode` "API 30:
  isolation expected OFF (gate: SDK >= 31); media.redoubt-isolation-media.enabled=false,
  locked"; the eleven at their 158.0-1 values and unlocked; H.264/AAC `android
  decoder (remote)`; VP8/VP9 `android decoder (remote)`, AV1 `ffvpx video
  decoder`, Opus `ffvpx audio decoder (Utility Generic remote)`; native HLS
  `canPlayType` `maybe`; content `untrusted_app` with the app uid, no app zygote,
  no `:rdd`; MediaCodec allocations (OMX goldfish H.264/VP8/VP9, AAC) all in
  `:media`; no `isolated_app` denial; `isolation-allowlist-inactive`: with the
  test hook on, VP9+Opus played with Opus in Utility and nothing was refused.
- **Control, Beta 2 (158.0-1 code) on the same AVD**
  (`control-beta2-check-isolation`, `fenix-x86_64-158.0-1-beta2-throwaway.apk`):
  11 of 12 rows PASS with the same decoder names, the same processes and the
  same allocations; only `isolation-mode` fails, because Beta 2 has no gate pref
  (value `None`). So below API 31, 158.0-2 shows the media behaviour of 158.0-1.
- `--check-video` **3/3 PASS**.
- Full default suite (`full-suite-1`) **10/10 PASS**, including the graphics
  acceptance `webgl` row ("Real release UI consent, pixels, revoke, lifetimes and
  frame isolation passed"). Its 59-pref dump is byte-identical to the API 34 one
  (`diff` exit 0): the SDK-dependent names are not in `expected-prefs.txt`.

No flaky run in this session on API 30 (7 runs of the 158.0-2 APK, 1 control),
which says nothing about the prototype's flake: that was measured with
isolation ON, which 158.0-2 does not do on API 30.

## 5. Dev variant and the phone

- x86_64 dev variant, `--check-isolation` once on each emulator: API 30
  (`device-api30/dev-check-isolation-1`) 12/12 PASS, isolation OFF, installed
  next to `org.redoubtbrowser` 158.0-2 (`pm list packages` shows both); API 34
  (`device-api34/dev-check-isolation-1`) 12/12 PASS, isolation ON.
- arm64 dev APK for the owner's phone: built and signed, **not installed**: the
  phone was not reachable over adb when the APK was ready (`phone/README.md`).

## 7. Review fix: drain backport behind the gate (`956b05ea`)

Review finding (MEDIUM): `isolation-media-drain-backport.patch` changed software
ffvpx on every Android version (video `AVERROR_EOF`-on-send mapping, audio
drain-packet handling, flush/shutdown rejecting a pending drain), so Android
8-11 did not behave as 158.0-1. Fix in `956b05ea`: every changed path reads
`FFmpegDataDecoder::mDrainFixEnabled`, taken once per decoder from the locked
gate pref; gate false runs 158.0's code. Path-by-path reading in the patch
header and `ISOLATION-MEDIA.md` section 2d. The gated tree was checked by
applying the patch to the 158.0 sources and diffing against a hand-edited copy
(identical). Evidence in `review-drain-gate/`.

**Gates** (`review-drain-gate/gates/`, tree of `956b05ea`, same tarball):
`check-patchfail.sh` android (70 patches), android + `dev-app`, desktop (66):
success, rc 0. `check-patch-order.py` ok (39/39, 172 pairs); `lint-patch-scope.py`
OK (115); `board.py --check` / `--check-scope` / `--check-cfg-split` /
`--diff-mozconfig --strict` ok; `test-android-smoke.py` 132 tests OK.

**Builds** (`chain2.sh` = `chain.sh` with the Gradle step serialised by a lock;
build date `20261011180000`, C/C++ `-Werror`, Rust lints capped as before):
both Gecko builds `exit=0` (`build-*-commands.log`).

| build | APK | sha256 |
|---|---|---|
| x86_64 release variant, no overlay | `redoubt-158.0-2r2-x86_64-throwaway.apk`, `org.redoubtbrowser`, versionCode 2016189782, throwaway key (cert `31e9a40f…b760`) | `3fa213a5e3a680b72fe0571010199cf3dbb084d50cd17d809d13f07e261be16e` |
| (unsigned) | `fenix-x86_64-release-unsigned.apk` | `d1023160e4b759b578c8f03a6b447e18ac90c719bec7b18a033e55e7e3a30304` |
| arm64-v8a dev variant, `OVERLAYS=dev-app` | `redoubt-dev-158.0-2r2-arm64-v8a.apk`, `org.redoubtbrowser.dev`, versionCode 2016189778, dev key (cert `1dfc331a…55a5`) | `b00b29c8125f687fe1e798c634726f59acee3ce92d98f4a7eefc413b120a3685` |
| (unsigned) | `fenix-arm64-v8a-release-unsigned.apk` | `76c131be7b8486a0cb6c81e299512b2749e1ded435b822fd17891ae3a66350a0` |

The section 2 APKs (`b78d361d`) are superseded.

**API 31 emulator, isolation ON** (`review-drain-gate/device-api31/`): first
measurement between API 31 and 33. Image `system-images;android-31;google_apis;x86_64`
installed with `sdkmanager` (cmdline-tools 16111833, zip sha1 matching
Google's `repository2-3.xml`), `Pkg.Revision=12`, fingerprint
`google/sdk_gphone64_x86_64/emulator64_x86_64_arm64:12/SE1A.220826.008/10564458:userdebug/dev-keys`,
`system.img` sha256 `e4a4b343…1cf3`. AVD `iso31` (`emu31.sh`), 4 vCPU, 4 GB,
`-gpu swangle`, `-wipe-data`, serial `emulator-5574`; the x86_64 APK above.

- `--check-isolation` **2/2 PASS**, 12 rows each: "API 31: isolation expected
  ON (gate: SDK >= 31); media.redoubt-isolation-media.enabled=true, locked";
  eleven prefs set and locked; H.264 `ffvpx video decoder (RDD remote)`, AAC
  `ffvpx audio decoder (Utility Generic remote)`; VP8/VP9/AV1/Opus in content;
  3 content processes `isolated_app` (`u0_i0..2`) from the app zygote;
  `c2.goldfish.h264.decoder` in `:rdd`, `c2.android.aac.decoder` in `:utility`;
  14 `isolated_app` denials, all in the platform baseline; `:rdd` refused
  `video/vp9` and `:utility` `audio/opus` with the test hook on.
- `--check-video` **2/2 PASS**.

**API 30 emulator, isolation OFF** (`review-drain-gate/device-api30/`, AVD
`iso30` as in section 4, same APK): `--check-isolation` **1/1 PASS** (gate false
and locked; the eleven at 158.0-1 values, unlocked; H.264/AAC `android decoder
(remote)`; Opus `ffvpx audio decoder (Utility Generic remote)` and AV1 `ffvpx
video decoder` in content, i.e. the software ffvpx decoders whose drain paths
the gate now holds at 158.0's code, play; no `:rdd`; no refusal with the test
hook); `--check-video` **1/1 PASS**. Same rows and decoders as section 4 and as
the Beta 2 control.

**Phone**: not installed; `10.0.0.168` did not answer ping and `adb mdns
services` listed nothing (see `phone/README.md`). No other adb device touched.
