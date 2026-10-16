# 158.0-3 (Firefox 158.0, DRM under isolation, Android 12-13 fix): second acceptance, CI run 38890071792, 2026-10-16: **PASS**

**Result.** The rebuilt 158.0-3 passes every row of the first 158.0-3 acceptance
([`../acceptance/`](../acceptance/README.md)), and the defect found there is gone: **Widevine now
plays the whole 60 s test stream on Android 12 (API 31) and Android 13 (API 33)**, as on 11, 14, 15
and 17. Every DRM session on every device made exactly one license request. Nothing is signed with a
release key, nothing is published.

Owner decision 2026-10-16: "go" = fix first, rebuild, re-accept, then the owner signs 158.0-3. The fix
is `isolation-eme.patch` item 7 (LW-M7-39, [`../../../lw-m7-39/api31-33-fix/`](../../../lw-m7-39/api31-33-fix/README.md)),
merged to main as `e2e41245`. `release.android` stays `3`; the first 158.0-3 build (CI run
38775774781, codes 2016190536-543) was never signed or published and is superseded.

## What was tested

| | |
| --- | --- |
| CI run | <https://github.com/CPlusPlus17/Redoubt/actions/runs/38890071792>, `android-release.yaml`, `workflow_dispatch` on `main`, job `build-unsigned` on box B (`redoubt-ci-boxb`), 10:53:24-12:28:55 UTC, `success` (`ci/run.json`, `ci/run.log.gz`). Inputs: `mode=full`, `update_check=true`, `bundle=false`, `build_date=20261016100000`. The log shows `build overlays: none`, the tarball signature checked against the pinned key (VALIDSIG `14F26682…0353`), and 179 GB free after the cache step. The push-triggered test run 38890065319 was cancelled (as for every release) |
| headSha | `e2e4124533df065b712c27c010076ce2b76d1fa6` = the signed merge of `fix/drm-api31-33` on main, where this branch starts. Settings gitlink `bddc198fbb608de0e460879416a2eb88e5a46f3d` (unchanged) |
| Artifact | `redoubt-android-unsigned`, 624,026,794 bytes, digest `sha256:2e1bbfc98d7777f90ef16fa58e5de50e90faa0f4f44e61cb5ebaea9dbc1af3e4`. `sha256sum -c SHA256SUMS`: 4 OK (`ci/SHA256SUMS.check.txt`) |
| Unsigned APKs | arm64-v8a `fe9b347bdef36213fbaf2cd55fb2b37f20a55be134c598aae4f28f13e22cc1d3`<br>armeabi-v7a `51992cd892467fdc1ec98ae134a63f8d912bd7db75d00549a590a50b5044b7ce`<br>universal `0f31b8fa809d2c45e749c05b2ec9f3d9db6fe7fce2c8cd944a3a84deff5055ff`<br>x86_64 `d4bca27a9096de3496050b1e1c986ff435714b00e970d51cca0767f657add5c4` |
| Installed | x86_64 `f0eccaaf20488e70c4bb63a107468aec3b2423f9df8824b4038b4cad2b6a1ed8` (emulators) and arm64-v8a `dc6e0166a2b1bfba0ac58c61f0877f5ee27e12216031b9e5a94f0c83fb065380` (phones), both re-signed with the **throwaway** key (`CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, cert `31e9a40f…b760`), v2+v3. All 3,278 non-signature entries equal the unsigned APK's (`static/apk-identity.txt`). Every emulator harness run recorded the installed hash `f0eccaaf…`, HEAD `e2e41245` and 0 uncommitted script changes (`device-api*/smoke/exit-status.jsonl`) |
| Upgrade source | 158.0-2 x86_64, throwaway-signed `0080b12f…b3b9` (the file of the 158.0-2 and first 158.0-3 acceptances) |
| Scripts | `scripts/`: the first 158.0-3 acceptance's scripts with paths changed. New or changed: `drive-api33.sh` (API 33), `drm/batch.sh` (the DRM flows now with `MOZ_LOG` EME:5 and `count.py`, which counts license requests per EME session; three whole-stream first plays `Play70` on every level), `drm/phone.sh` (`--check-eme` and `--check-isolation` through a harness copy with `harness-loopback-origin.diff`, then the DRM flows; replaces `phone-harness.sh`), `drm/phone-isolation-control.sh`, `static-checks.sh` (S17, S18), `apk-identity.sh`, `post-ci.sh`, `collect.sh`. `drm-flow.py`, `play.html` (counts license server requests at the page), `count.py`, `trim-logcat.py` from the fix's evidence |

**Devices.** One emulator at a time, booted by the harness: API 34 `google_apis` x86_64 (Wi-Fi off from
batch 2, as before), API 31 `google_apis` (`google/sdk_gphone64_x86_64/…:12/SE1A.220826.008`), API 33
`google_apis` (`…:13/TE1A.240213.009`, new here), API 30 `default` (`generic_x86_64:11/RSR1.210722.013.A2`).
Two of the owner's phones over wireless adb, in parallel with the API 34 emulator: **Pixel 9a**, Android 17
(API 37, user build) and **Xiaomi MI 8**, LineageOS on Android 15 (API 35, userdebug). Redoubt was not
installed on either, so the throwaway-signed arm64 release APK was used; the scripts restored the
settings they changed and uninstalled it (`phones/*/device.txt`: before = after, `installed=` empty). The
Pixel 10 Pro was not in `adb devices` and was not used.

## Static (`static/`)

| # | Check | Result |
| --- | --- | --- |
| S1 | versionName / codes | **PASS.** `158.0-3-default`; v7a **2016190672**, arm64 **2016190674**, x86_64 **2016190678**, universal **2016190679**, all above the first 158.0-3 build (…536-543), 158.0-2 (…288-295) and 158.0-1 (…144-151). Package `org.redoubtbrowser`, label `Redoubt`, targetSdk 37 |
| S2-S7, S11, S12, S14-S16 | ELF, unsigned, branding, uBO 1.75.0 pin, packaged `librewolf.cfg`, update-check key/endpoint, isolation gate, store installers, LW-M7-46 pref, no dev-app overlay, isolation-eme compiled in | **PASS**, the same values as the first 158.0-3 build. `librewolf.cfg` sha256 `374b6578…9ca7` (identical); `isolation-gate-dex.py` exit 0 for all four; manifest 41 isolatedProcess, 1 useAppZygote |
| S10 | Build ID | `MOZ_APP_VERSION 158.0-3`, `MOZ_BUILDID 20261016100000` (`build-id.txt`) |
| **S17** | **Android 12-13 fix compiled in** | **PASS.** The fix's two log lines ("service certificate provided; requesting the", "KEY_REQUIRED after the service certificate") once each in every ABI's `libxul.so`; 0 in the first 158.0-3 build (`eme-fix-static.txt`) |
| **S18** | Against the first 158.0-3 build (x86_64) | 11 of 3,278 APK entries differ: `libxul.so`, `libmozglue.so` and the build-date set (manifest, dex, baseline.prof, five built-in extension manifests, `omni.ja`); in `omni.ja` only `AppConstants.sys.mjs` (`entries-vs-first-158.0-3-x86_64.txt`) |

## Device

PASS = passed. HL = harness limit, no product finding. E12 = red as expected under E12. NEG = a
negative control that must fail, and did.

### DRM (LW-M7-39)

The play rows use Shaka with the public Widevine "Angel One" stream: `play-low` pins the lowest H.264
variant for 60 s, `play` lets ABR choose for 40 s, `play-switch` switches to the highest variant after
10 s, and **`play70` ("first play") is a fresh profile (`pm clear`), DRM Allowed, ABR, reported at 70 s:
the stream is about 60 s, so `t=60` means it played to the end.** `play.html`'s own `ok` needs only 5 s,
so the rows are graded on the reached time, the key status and the license request count. "Lic." =
EME sessions with exactly one license request, from the EME log (`counts.json`), and at the page
(`license-requests=['service-certificate', 'license']` for every play).

| # | Device | Check | Result | Evidence |
| --- | --- | --- | --- | --- |
| D1 | API 34 | `--check-eme` x2 | **PASS, 4/4 each** | `device-api34/smoke/check-eme-{1,2}/` |
| D2 | API 34 | DRM flow + 3 first plays | **PASS.** Default rejected, no prompt; Allowed resolves; play-low 59.95 s, play 39.94 s, play-switch 47.92 s at 768x576; Ask prompt; Blocked rejected; first plays 60/60/60 s. Lic. 6/6; 0 NDK drops (none expected) | `device-api34/drm/` |
| D3 | **API 31** | `--check-eme` x2 | **PASS, 4/4 each** | `device-api31/smoke/` |
| **D4** | **API 31** | DRM flow + 3 first plays | **PASS (was FAIL: every play stopped at 8.2 s).** play-low 59.93 s, play 39.94 s, play-switch 47.94 s at 768x576, first plays **60/60/60 s**, keys `usable`. Lic. 6/6. The NDK still drops the empty event (`invalid event data size=0` 10 times) and the fix's request line appears once per session (6) | `device-api31/drm/` |
| **D4a** | **API 33** | `--check-eme` x2 | **PASS, 4/4 each** (new) | `device-api33/smoke/` |
| **D4b** | **API 33** | DRM flow + 3 first plays | **PASS** (new). play-low 59.94 s, play 39.93 s, play-switch 48.10 s at 768x576, first plays 60/60/60 s. Lic. 6/6. This image already has the AOSP NDK fix: 0 drops, the event arrives and the fix skips it once per session (request line 6, skip line 6) | `device-api33/drm/` |
| D5 | API 30 | `--check-eme` | **PASS, 4/4** (Java path, isolation off) | `device-api30/smoke/check-eme-1/` |
| D6 | API 30 | DRM flow + 3 first plays | **PASS.** play-low 59.75 s, play 39.75 s, play-switch 49.68 s (VP9+AAC, Java path), first plays 60/60/60 s. Lic. 6/6 | `device-api30/drm/` |
| **D7** | **Pixel 9a, Android 17** | DRM flow + 3 first plays | **PASS, on hardware.** play-low 59.78 s, play 39.74 s, play-switch 47.27 s at 768x576, first plays 60/60/60 s, Ask prompt, Blocked rejects. Lic. 6/6; 4 isolated processes (counted before the app is stopped) | `phones/pixel9a/` |
| **D8** | **MI 8, Android 15** | DRM flow + 3 first plays | **PASS, on hardware.** play-low 59.67 s, play 39.76 s, play-switch 47.41 s at 768x576, first plays 60/60/60 s. Lic. 6/6; 4 isolated processes | `phones/mi8/` |
| D9 | both phones | `--check-eme` (harness copy with `harness-loopback-origin.diff`) | **PASS, 4/4 on both.** (In the first acceptance the page rows timed out on phones; the loopback origin makes them reachable) | `phones/*/*-check-eme-1/` |
| D9a | both phones | `--check-isolation` (same copy) | **HL.** Pixel 9a 9/12: `isolation-processes` (no `org.redoubtbrowser_zygote` on API 37), `isolation-denials` (`content_capture`/`performance_hint` lookups outside the emulator baseline), `isolation-profile-dir`. MI 8 8/12: `isolation-denials` and `isolation-profile-dir` as on the Pixel, plus `isolation-decoder-h264-aac` and `isolation-codec-processes`: the harness's small H.264 fixture fails with a decode error in RDD on the MI 8's `OMX.qcom.video.decoder.avc`. **Control: 158.0-2 fails the same four rows on the MI 8** (`phones/mi8-control-158.0-2/`), so it is not new in 158.0-3; real H.264 (the Widevine stream) plays there. Not graded as a product result | `phones/*/*-check-isolation-1/` |
| M | MI 8 | LW-M7-38 menu | **PASS.** No "Report broken site" (0 mentions) | `phones/mi8/menu/` |

Totals over the 24 DRM flows (4 emulators, 2 phones): 36 EME sessions, 36 with exactly one license
request; 0 tab deaths, 0 RDD deaths, 0 fatal lines, 0 Java crypto-query exceptions; every flow exit 0.

### Isolation (LW-M7-50), as in 158.0-2

| # | Check | API | Result |
| --- | --- | --- | --- |
| I1 / I2 | `--check-isolation` x3 / `--check-video` x3 | 34 | **PASS**, 12/12 each ON / 3/3 each |
| I3 / I4 | `--check-isolation` x2 / `--check-video` x2 | 31 | **PASS**, 12/12 each ON / 3/3 each |
| I5 / I6 | `--check-isolation` / `--check-video` | 30 | **PASS**, 12/12 OFF / 3/3 |
| P | process labels | 34 / 31 / 30 | **PASS, as gated.** 34 and 31: content in `isolated_app` (uids 90000-90003) from the app zygote, `:rdd` `untrusted_app`; 30: `:tab_disable_art_image_N` as `untrusted_app` |

### Rows carried over from 158.0-2

| # | Check | API | Exit | Result |
| --- | --- | --- | --- | --- |
| 1 | `--check-launcher-start` | 34 | 0 | **PASS** |
| 2 / 2a | `--check-aboutconfig` / CSP probe | 34 | 0 / 0 | **PASS** (0 about:config CSP errors) |
| 3, 4, 4a, 5 | uBO preinstall (2/2), lifecycle (10/10), user-disable (3/3), `--check-ubo` | 34 | 0 | **PASS** |
| 6 | `--check-search` | 34 | 0 | **PASS** |
| 7 | `--check-no-suggest` | 30 | 0 | **PASS** |
| 7′ | `--check-no-suggest` | 34 | 1 | **HL**, as before: the OS's own `www.google.com` flow in the typing window |
| 7a | negative control | 34 | 1 | **NEG**, caught `ac.duckduckgo.com` on 3 connections |
| 8 | baseline with full graphics acceptance | 30 | 0 | **PASS, 10/10**, graphics `acceptanceComplete: true`, 162 checks |
| 8′ | baseline | 34 | 1 | **HL**, 9/10, only `webgl` (API 34 window-list parser), as before |
| 9 | `--check-update-privacy` | 34 | 1 | **HL**, as before: one IPv6 SYN with 0 bytes to `2606:50c0:8002::153`, a GitHub Pages address (the update host's AAAA) |
| 9″ | `--check-update-privacy` | 30 | 1 | **HL**, the same kind: two IPv6 SYNs with 0 bytes to `2606:50c0:8000::153` and `…8001::153` (GitHub Pages) |
| 9a | update check, live endpoint | 34 | 0 | **PASS.** ON: both files fetched; the live document is the owner-signed **158.0-2** one, older than this build: **nothing offered**, only `last_run_ms` written, app alive. Second resume 0 requests; OFF 0 requests; control 6 records |
| 9b | **update check against a local document** | 34 | 0 | **PASS.** `doc-wrongkey-158` (code 2016199999, above this build, signed with a key that is not the committed one): both files fetched (`server-requests.jsonl`), **nothing offered**, app alive |
| ST | store installer hides the check | 34 | 0 | **PASS** |
| DQ | `--check-delete-on-quit` | 34 | 0 | **PASS** |
| 10 | `--check-https-only` | 34 | 0 | **PASS, 5/5** |
| TLS, RV, RFP | `--check-tls-floor`, `--check-revocation` (3/3), `--check-rfp-coherence` | 34 | 0 | **PASS** |
| AF | shadow-DOM autofill | 34 | 0 | **PASS**, the same counts as before (`shadow-open` 1 request / 3 fields, `plain` 1 / 2, the others 0) |
| RD | reddit.com/login, fresh profile | 34 | 0 | **Known limit, unchanged**: login blank ("Welcome to Reddit" only) at 30 and 60 s; the home page renders |
| 11 | `--check-no-gms --check-no-adjust` + graphics | 30 | 0 | **PASS, 12/12**, a second full graphics acceptance (162 checks) |
| 11′ | the same | 34 | 1 | **HL**, only `webgl` |
| W | manual WebGL page | 30 | 0 | **PASS** (`WEBGL-MANUAL PASS`) |
| 12 | `--check-strings` | 34 | 0 | **PASS.** 244,495 rows, 0 unexplained, 34 screen stops |
| 13 | `--self-test` | 34 | 0 | **PASS** |
| 14 | `--first-run-capture` | 30 | 1 | **E12.** 99 events (first 158.0-3 build: 116). **Named hosts: none added**; `malware-filter.pages.dev` not seen this time (a uBO list mirror, timing) (`device-api30/first-run-host-comparison.json`). No `redoubtbrowser.org` |
| 14′ | `--first-run-capture` | 34 | 1 | **E12**, 102 events (Wi-Fi off; not compared) |
| 15 | `--check-no-remote-settings` | 34 | 1 | **E12**, the same 3 Remote Settings hosts |
| 16 | pref audit | 34 | 0, 0 | **PASS.** Generator diff against the committed `expected-prefs.txt` is empty; audit exit 0 |
| 17 | **upgrade 158.0-2 → 158.0-3** (`adb install -r`) | 34 | 0 | **PASS.** Code 2016190294 → 2016190678, same signer, same `firstInstallTime`; suggestions ON, DoH Max Protection (quad9), the bookmark, uBO 1.75.0 lists and the update-check switch ON all kept. `state-A-final` and `state-C-after-upgrade` differ only in `appinfo` and the TRR build fields |
| 18 | the same upgrade | 30 | 0 | **PASS**, the same result |

**No crash:** no `FATAL EXCEPTION`, `Fatal signal` or `ANR in org.redoubtbrowser` in any of the 67
emulator logcat streams, nor in the phone runs (`fatal=0` in every `counts.json`).

## Update document (host side; nothing signed with the owner's key)

- `scripts/update-manifest.py generate --tag android-158.0-3` on this run's `output-metadata.json`:
  `version_code` **2016190672** (the lowest of the four), the `android-158.0-3` release URLs,
  published `2026-10-16T12:36:00Z`; sha256 **`885fe5cb23874d8193a584d3df058101bad491e8f2c92302ded8230e05b7bf18`**
  (`update-check/latest.json`, the same bytes as the signing bundle's).
- Signed here with the 157.0-2 acceptance's **throwaway** P-256 key (`update-check/host-verifier.txt`):
  with the committed key `update-manifest.py verify` says **REJECTED** (exit 1); with the throwaway key
  the signature verifies and the `--metadata` cross-check passes; "update offered" for all four 158.0-2
  codes, 158.0-1 arm64, 157.0.1-1 x86_64 and the first 158.0-3 build (2016190543); "up to date" for all
  four codes of this build. `sign-update-manifest.sh` refused the throwaway key (exit 2) and wrote no `.sig`.
- `site/update/` is untouched.

## Signing bundle

`~/redoubt-artifacts/release-158.0-3/signing-bundle/` (not in the repository). The first build's bundle
was moved to `signing-bundle.superseded-20261015170000/`. Contents:
- the four unsigned APKs and the CI `SHA256SUMS` (`sha256sum -c`: 4 OK);
- `sign.sh` (`0af4851e…1252`), `android-verify-signature.sh` (`8a251c45…a483`), `SIGNING.md`
  (`1fa16a9d…6c9a`, main's current copy with d76fcf19's YubiKey wording), all byte-equal to main at
  `e2e41245`, and `apksigner.jar` (`3716d931…3dec`), listed in `SHA256SUMS.tools`;
- `RELEASE-NOTES.md` (no internal notes);
- `update/`: `latest.json` (`885fe5cb…bf18`), `sign-update-manifest.sh` (`9c1ad1ef…9f06`),
  `update-check.android.pubkey` (`8e714075…7de8`) and `SHA256SUMS.update`.

## Run notes

- The phones ran their DRM flows in parallel with the API 34 emulator; they share only the page server.
- `phones/`: logcats are cut down before committing: DRM flows to the EME/DRM/death lines
  (`trim-logcat.py`), harness runs to Redoubt, Gecko, isolation and DRM lines. Full captures are in
  `~/redoubt-artifacts/release-158.0-3/accept2/runs-phones/`.
- The Mi 8 refuses `adb install --incremental`; adb falls back to a streamed install (the stack trace in
  `device.txt` is that fallback).

## Not covered

- **License renewals on Android 12-13** (a known limitation in the release notes; the test stream has
  none).
- **An Android 13 image without the AOSP fix**: the SDK's API 33 image already has it, so on API 33 only
  the "event arrives, skip it" path ran; the "event dropped" path ran on API 31.
- **The Pixel 10 Pro** (not in `adb devices`).
- **Real streaming services**: DRM was tested with the public Shaka test stream only.
- **Owner-key signatures**: nothing was signed with a release key.
