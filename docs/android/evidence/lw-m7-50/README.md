# LW-M7-50 evidence: the isolation-media prototype

Design and how to build: [`docs/android/ISOLATION-MEDIA.md`](../../ISOLATION-MEDIA.md).
Branch `feature/isolation-media` (local; cut from `android/firefox-158` 0f2665fe).
Measured 2026-10-10/11 on the build host. Every hash below was printed by
`sha256sum` or `git rev-parse` in this session.

Owner decisions 2026-10-10, verbatim: "Prototype now, ship ON in a 158 dot
release if it tests clean"; "Keep software codecs in the page process"; "Yes,
separate dev app".

## Inputs

| | |
|---|---|
| Firefox source | `firefox-158.0.source.tar.xz`, 158.0 RC build2, sha256 `fc77f7801d7580a600af683cc367e261eb1ec74647e84a91b4a1e3c1dd5aa2bb` (GPG-verified copy from `ff158/rel158/build2`, `GOODSIG 678E455D76767AA3`) |
| overlay commit built | `7cc8aabcaf51301725e7135466039bdfd9703292` (patches and overlay lists unchanged since) |
| build layout | `version`/`version.android` 158.0, `release.android` 1 (as Beta 2), local podman image `librewolf-android-build:fx158` (`98e61be72eec`), `-j10`, `scripts/chain.sh` |
| upstream prefs | bug 1988531 part 1, `e0286afb5f6836d607a3f218a527db69979c0bbd`, patch sha256 `dc8dad375ed6f292e87f21772166616cdc700045e452ac371785a485fb66498f` |
| upstream drain fix | bug 1987001, `5cf346157068a285144cfb2f0409e81a2796ac59`, patch sha256 `8d7cc715260958f792d83a2aa26b3bfb01aa20fef0d4ee19d86683d7f8faa2ec` |

## APKs

| APK | what | sha256 |
|---|---|---|
| `fenix-x86_64-release-unsigned.apk` (ON) | `OVERLAYS=isolation-media,dev-app`, x86_64, build date 20261010220000, no update check | `527b21f62ab8106dbe04eeb8371a50ee72efdebd8eee0af4b4cc2ddc467dd704` |
| `redoubt-dev-iso-x86_64.apk` | the above, signed by `scripts/android-sign-dev.sh` with the dev key (cert sha256 `1dfc331a…55a5`) | `1f0793c2d05697d8b00ac975283dd9a0132cb97d4d0bbef2a64de1d8ad4398a3` |
| `fenix-x86_64-release-unsigned.apk` (OFF) | no overlays, x86_64, Beta 2's build date 20261009160000, `--update-check` | `aa940c7b7c3c41e89a480b0501b5f0270d27f60e9af55f91550817e47e03abdd` |
| `redoubt-off-x86_64-throwaway.apk` | OFF, signed with the throwaway key | `b7c1e72a7cbba490fd7f44a61c289c2ac2f6530c2e524f1913f2d8a27d7c800f` |

`aapt2 dump badging` of the dev APK: `package: name='org.redoubtbrowser.dev'
versionCode='2016189622' versionName='158.0-1-default'`, `application-label:'Redoubt Dev'`.
The ON build compiled with the Redoubt Gecko change and the drain backport, and
the Fenix Kotlin build (`-Werror`) passed (`build-on`, `fat-aar exit=0`; the
APK pass's only non-zero exit is the known single-ABI universal-APK check).

## 1. Switch OFF is today's build

- **Make variables** (`make -pn TARGETS=android`, before and after the change):
  `targets_stamp`, `patch_lists` and `patcher_cmd` expand to identical strings.
- **Patched tree** (`off-identity/tree-compare.*`): `make android-dir
  TARGETS=android` from `android/firefox-158` (0f2665fe) and from
  `feature/isolation-media` (7cc8aabc), same tarball: `diff -r` exit 0; both
  trees 524,522 files, file-manifest sha256
  `754743ea9a6ea41a1de6755046f4e12cc77929e5062fc628d5bd48312b4e2b5d` for both.
- **APK vs Beta 2** (`off-identity/off-vs-beta2.txt`, `omni-diff.txt`,
  `dex-and-buildconfig.txt`): the local OFF x86_64 APK against Beta 2's CI
  x86_64 unsigned APK (`d04352ef…a0a3`, CI run 37960642307, same build date).
  3,278 entries each; **3,275 byte-identical**, including every native library
  (`libxul.so` and all others). The three that differ:
  - `assets/omni.ja`: one file differs, `buildconfig.html`, whose configure
    line ends `MOZ_ANDROID_FAT_AAR_ARCHITECTURES=x86_64` locally and
    `=armeabi-v7a,arm64-v8a,x86_64` in CI; the CI omni.ja also carries the
    other two ABIs' `greprefs.js`/`geckoview-prefs.js` copies. Both follow from
    building one ABI instead of three.
  - `classes2.dex`: the only `dexdump -d` difference is the order of 124
    locale strings in `org.mozilla.fenix.Config.<clinit>`; the set is identical.
  - `assets/dexopt/baseline.prof`: follows the dex.

  No difference comes from this branch.

## 2. Gates (`gates/`)

Against the 158.0 RC build2 tarball, in a copy with `version.android` 158.0:

| gate | result |
|---|---|
| `check-patchfail.sh --targets=android` | exit 0, 8 fuzz notes (same count as Beta 2's gate run) |
| `check-patchfail.sh --targets=android --overlays=isolation-media,dev-app` | exit 0; the 4 overlay patches apply with no fuzz |
| `check-patchfail.sh --targets=desktop` | exit 0 |
| `check-patch-order.py` | `39/39 declared constraint(s) enforced across 3 target sequence(s); 168 shared-file pair(s)`, 10 of them list-patch/overlay-patch pairs ordered by construction |
| `lint-patch-scope.py` | OK, 114 patch files |
| `board.py --check` / `--check-scope` / `--check-cfg-split` / `--diff-mozconfig --strict` | ok (131 tasks; 110 listed + 4 overlay patch files; cfg split regenerates exactly; 0 hardening differences) |
| other `scripts/tests/*.py` | 12 pass; 6 (`addon-state-durability`, `android-signing`, `android-version-code`, `extension-update-controls`, `global-privacy-controls`, `session-cleanup`) exit non-zero here and equally on `android/firefox-158` 0f2665fe: they need an APK, a Gradle home or an extracted tree |
| `scripts/tests/test-android-smoke.py` | OK, including `IsolationCheckTests` (one test per failure mode, and one that keeps the cfg, `expected-prefs-isolation-media.txt` and the harness constant equal) |

## 3. Device: API 34 (`device-api34/`)

AVD `iso34`, API 34 `google_apis` x86_64, 4 vCPU, 4 GB, `-gpu swangle`, serial
`emulator-5594`, fresh `-wipe-data` boot.

**`--check-isolation`, 3 runs, all PASS (10/10 rows each).** Run 1:

- content: 3 processes `u:r:isolated_app:s0:c512,c768`, uids `u0_i0..u0_i2`,
  forked by `org.redoubtbrowser.dev_zygote`; `:rdd` runs as
  `u:r:untrusted_app`, uid `u0_a193` (not isolated, by design);
- the 11 prefs set and locked;
- H.264+AAC: `ffvpx video decoder (RDD remote)` + `ffvpx audio decoder
  (Utility Generic remote)`; VP8+Opus, VP9+Opus, AV1+Opus: `ffvpx video
  decoder` + `ffvpx audio decoder`, no `remote`, so decoded inside the isolated
  content process;
- MediaCodec allocations: `c2.goldfish.h264.decoder` in `:rdd`,
  `c2.android.aac.decoder` in `:utility`, none in an isolated process;
- 12 `isolated_app` denials, all sysfs `product_name`/`product_sku`
  (the LW-M7-48 baseline), none on media or `app_data_file`;
- `/data/data/org.redoubtbrowser.dev` `drwx------ u0_a193 app_data_file`.

**Negative control:** the same check on Beta 2 (`org.redoubtbrowser`,
isolation off, throwaway-signed `295022…344a`) FAILS: prefs unlocked/default,
content `:tab` processes `untrusted_app` with the app uid, H.264 decoded by the
Java `android decoder (remote)` via `:media`, VP8/VP9 via `:media`.

**`--check-video`, 3 runs, all PASS** (`video`, `video-h264`, `video-mse`).

**Other rows on the dev app:** `--check-delete-on-quit` PASS,
`--check-launcher-start` PASS, `--check-ubo-preinstall` PASS (first navigation
blocked, signature), `--check-ubo` PASS. Default suite: everything PASS except
`webgl`, which the graphics harness cannot drive on API 34 (its
`dumpsys input` parser is written for the API 30 format; the graphics gate is
API 30's, below).

**Autofill (LW-M7-42 rows)** with the LW-M7-42 probe AutofillService
(`autofill/probe-*.txt`, `scripts/af-run.sh`): plain form 1 fill request,
open-shadow login 1, closed-shadow 0, non-login shadow 0. Same as LW-M7-42's
results on a non-isolated build: the GeckoViewAutoFill actor works from an
isolated content process.

**Dev app next to the release app** (`both-apps-ps.txt`,
`both-apps-running.png`): `org.redoubtbrowser` (Beta 2 throwaway-signed) and
`org.redoubtbrowser.dev` installed together, separate data directories and
uids (`u0_a194`, `u0_a193`), different signers, both launched and running at
once. In the same `ps`, the release app's tabs are `untrusted_app` and the dev
app's are `isolated_app`.

## 4. Video matrix (`matrix/`, `scripts/matrix.py`)

LW-M7-48's page and media plus five short clips (`matrix/SHA256SUMS*`), every
case in muted-autoplay and click mode, **3 rounds**, fresh profile per round,
dev APK. Long-clip pass = `currentTime` advances over 2 s with `paused=false`.

| case | muted | click | video decoder | audio decoder |
|---|---|---|---|---|
| H.264+AAC MP4 | 3/3 | 3/3 | RDD remote | Utility remote |
| H.264 MP4, no audio | 3/3 | 3/3 | RDD remote | - |
| AAC m4a | 3/3 | 3/3 | - | Utility remote |
| VP9+Opus WebM | 3/3 | 3/3 | ffvpx, content | ffvpx, content |
| AV1+Opus WebM | 3/3 | 3/3 | ffvpx, content | ffvpx, content |
| AV1+AAC MP4 | 3/3 | 3/3 | ffvpx, content | Utility remote |
| hls.js, TS | 3/3 | 3/3 | RDD remote | Utility remote |
| hls.js, fMP4 | 3/3 | 3/3 | RDD remote | Utility remote |
| native HLS `<video src=.m3u8>` | error 4 ×3 | error 4 ×3 (`play()` NotSupportedError) | - | - |

48/48 long-clip runs played, **including 24 muted-autoplay runs with no stall**
(LW-M7-48 saw two unexplained muted stalls on 157 + debug-config prefs).
Native HLS fails closed exactly as decided. Every round: MediaCodec only in
`:rdd` (H.264) and `:utility` (AAC); the only `isolated_app` denials are sysfs
`product_name`/`product_sku`.

### Short clips and the drain fix

| clip (frames) | dev build, 3 rounds × 2 modes | Beta 2, isolation off, Java MediaCodec | 157.0-2 + upstream prefs, no drain fix |
|---|---|---|---|
| H.264+AAC 0.5 s (15) | ended, 14 frames ×6 | ended, 14 ×6 | ended, 14 ×4, 15 ×2 |
| H.264+AAC 0.3 s (9) | ended, 8 ×5, 9 ×1 | ended, 8 ×6 | ended, 8 ×5, 9 ×1 |
| H.264 0.5 s, no audio (15) | ended, 14 ×6 | ended, 14 ×6 | ended, 14 ×6 |
| AAC 0.5 s | ended ×6 | ended ×6 | ended ×6 |
| VP9+Opus 0.5 s (15) | ended, 15 ×6 | ended, 15 ×5, 1 run "shutdown" | ended, 15 ×6 |

Every short clip reaches `ended` with no error on the dev build; no run showed
the "no frame at all" failure the drain bug describes. On this emulator the
goldfish H.264 decoder reports one frame fewer than the file holds for **every**
decoder path, including the shipping Java MediaCodec path of Beta 2, so the
emulator cannot show the difference the backport makes; the dev build matches
the shipping app. The matrix's strict "all frames" criterion therefore marks
these rows red in `iso-on-dev.json`; read them against the control columns.
The drain fix still needs the phone (real vendor codecs, section 6).

## 5. Device: API 30 (`device-api30/`): passes, with intermittent failures that come from upstream's prefs

Harness-booted AVD, API 30 `default` x86_64 (OMX goldfish codecs, not Codec2),
`-gpu swiftshader`/`swangle` as the harness picks, 3 GB. Fresh boots as
`emulator-5584` and later `emulator-5582`.

**What passed:** the full default suite on the dev APK, including the graphics
acceptance `webgl` row (release UI consent, pixels, revoke, lifetimes, frame
isolation), video rows, getUserMedia, extension and pref dump
(`full-suite-api30-dev-2.*`); `--check-isolation` 10/10 rows in 3 runs
(`-1`, `-5`, `-6`); `--check-video` 3/3 rows in 5 consecutive runs (`-6`..`-10`).
On API 30 the client logs `MediaCodec: [OMX.android.goldfish.h264.decoder]`
instead of `CCodec allocate`; the check reads both (`OMX.android.goldfish.h264.decoder in :rdd`).

**What failed, intermittently.** Of 17 dev-app runs of `--check-isolation`
and `--check-video` on API 30, 9 did not pass:

| failure | dev-app runs |
|---|---|
| bootstrap page never loads (`initial browser document did not finish loading`) | isolation `-3`, video `-1`, `-4`, `-5` |
| `WebDriver:Navigate` timeout to the local https page | isolation `-2`, video `-2` (and the first full-suite run) |
| H.264 decoder created in the right place (`RDD remote` / `Utility Generic remote`) but 0 frames in 30 s | isolation `-4` and one earlier run |
| MSE: data buffered, `readyState 1`, 0 frames | video `-3` |

The failures cluster in time (02:15-03:00 UTC on 10-11) and then stop. To find
out whose they are, the same AVD ran controls in that window and after it:

| build | prefs | result |
|---|---|---|
| OFF (no overlay, Java MediaCodec, not isolated), throwaway-signed | none | **5/5 pass**, including runs between failing ones |
| 157.0-2 (isolated, no media prefs) | none | 3/3 load and play VP8; H.264 has no decoder, as known |
| 157.0-2 (isolated) | upstream's 11 via the debug config | 1 MSE stall, 1 bootstrap failure, 1 pass |
| OFF (not isolated) | upstream's 11 via the debug config | 3 bootstrap failures, then 3 passes |
| OFF | subsets (`rdd-process`; `ffvpx-hw`; both; the two `android-media-codec` prefs; the two encoder prefs; the seven `rdd`/`ffvpx` prefs) | 18 runs: one bootstrap failure (both `android-media-codec` prefs off); otherwise only the expected H.264 failure when Java MediaCodec is off and RDD is not on |

So the API 30 failures reproduce **with upstream's isolated-process prefs alone,
on a non-isolated build and on 157.0-2**, without Redoubt's codec patch or the
drain backport; builds without those prefs never failed on this AVD. They were
not seen on API 34 (Codec2) in any harness run or in the 84 matrix runs. The root
cause is not established: the cluster in time also points at the host (other
VMs ran on it). **This is the one result that is not clean**, and it bears on
devices with OMX-era codec stacks (Android 10/11). See section 7.

## 6. arm64 dev APK for the phone

Built locally (disk allowed it): same commit, `OVERLAYS=isolation-media,dev-app`,
arm64-v8a only, build date 20261010220000.

| file | sha256 |
|---|---|
| `fenix-arm64-v8a-release-unsigned.apk` | `761c6501b04248dff16729f20fc93f446a9a5f71f53460ea120f1312315012d2` |
| `redoubt-dev-iso-arm64-v8a.apk` (dev key, cert `1dfc331a…55a5`) | `9033647bea4c6d656deedc00d98cac6d80c10f3d2f1ec0efaa5af83628a80493` |

`aapt2 dump badging`: `org.redoubtbrowser.dev`, versionCode 2016189618,
`158.0-1-default`, label `Redoubt Dev`, native code `arm64-v8a`. Not run on
any device yet. No CI run and no push were needed.

## 7. Verdict for "ship ON in a 158 dot release if it tests clean"

Clean on API 34 (Codec2), on every check. Not clean on API 30 (OMX), where
upstream's own pref set misbehaves intermittently in this lab. Before a dot
release turns it on: the owner's phone run (Android 14+, real vendor codecs),
and a decision on Android 10/11 devices (for example keep the overlay off for
SDK < 31, which would need a runtime gate this prototype does not have).

## 8. Not covered here

- arm64 hardware and a real phone's vendor codecs; the drain fix on hardware.
- WebRTC H.264 encode (now in RDD by upstream's prefs).
- The root cause of the API 30 failures.
