# 158.0-2 (Firefox 158.0, content isolation on Android 12+): acceptance of CI run 38549776387, 2026-10-14: **PASS**

**Result: the payload PASSES acceptance and may go to the owner for signing.** After signing it
is published as the new **Latest** stable, over 158.0-1. Owner go on 2026-10-14, verbatim: "go",
for the owner decision of 2026-10-11, verbatim: "158.0-2, Android 12+ only". The isolation work
and its release-day gates are in [`../../../lw-m7-50/release-158.0-2/`](../../../lw-m7-50/release-158.0-2/README.md);
the design is `docs/android/ISOLATION-MEDIA.md`.

158.0-2 is 158.0-1 plus LW-M7-50: a runtime gate, `GeckoProvider.isolatedContentEnabled()` =
`SDK_INT >= 31`, turns GeckoView's isolated content processes on for Android 12 and newer. It also
sets the locked pref `media.redoubt-isolation-media.enabled`, which switches on upstream's eleven
isolated-process media prefs, the codec placement (H.264/HEVC in `:rdd`, AAC in `:utility`, every
other codec in the isolated content process), the decoder-process allowlist and the drain
backport. Below API 31 the gate is off and the build behaves as 158.0-1. Same Firefox 158.0
source tarball, same settings gitlink, so the packaged `librewolf.cfg` is byte-identical to
158.0-1's.

What the runs showed:
- **Every 158.0-1 row passes again**, with the same API 34 harness limits.
- **Isolation ON, API 34 and API 31.** `--check-isolation` passes **3/3** on API 34 and **2/2** on
  API 31, 12 rows each:
  - content runs in `isolated_app` under isolated uids;
  - H.264 is decoded in `:rdd`, AAC in `:utility`;
  - VP8, VP9, AV1 and Opus are decoded in the isolated content process;
  - `:rdd` and `:utility` refuse VP9 and Opus when content asks for them.
  `--check-video` passes **3/3** on API 34 and **2/2** on API 31.
- **Isolation OFF, API 30.** `--check-isolation` passes: the gate pref is false, the eleven prefs
  keep 158.0-1's values unlocked, and the decoders, processes and MediaCodec allocations match
  158.0-1's. `--check-video` passes. The graphics acceptance passes **162/162 twice**; the second
  run needed a re-run after the host's adb server died (see "Run notes").
- **Upgrades keep the data.** 158.0-1 → 158.0-2 with `adb install -r` keeps it on API 34 and on
  API 30, including the update-check switch.
- **Update check.** It fetches the live, owner-signed **158.0-1** document, which is older than
  this build, and offers nothing. A local document **above** this build's code, signed with a key
  other than the owner's, is fetched and refused.
- **The new update document** (signing bundle) offers 158.0-2 to every 158.0-1 code, and "up to
  date" to 158.0-2 itself (host side, throwaway key).

No product defect was found. The known site limit is unchanged: a direct load of reddit.com/login
on a fresh profile stays blank (row RD), as in 158.0-1.

## What was tested

| | |
| --- | --- |
| CI run | <https://github.com/CPlusPlus17/Redoubt/actions/runs/38549776387>, "Android release (unsigned artifacts only)" (`android-release.yaml`), `workflow_dispatch` on `main`, job `build-unsigned` on box B, 10:29:34-12:09 UTC, conclusion `success` (`ci/run.json`, `ci/run.log.gz`).<br>Inputs from the log: `MODE: full`, `UPDATE_CHECK: true`, `BUILD_DATE_IN: 20261014100000`.<br>The log also shows: the tarball's `.asc` checked against the pinned key (`VALIDSIG … 14F26682D0916CDD81E37B6D61B7B526D98F0353`); `build overlays: none`; the new cache step keeping `tree-158.0-1`, with 0 trees removed and 181 GB free |
| headSha (`gh run view --json headSha`) | `255c87aabbf8e0f831f83d1bf6f3e309833b0d6d`, which equals `git rev-parse origin/main` and is the commit this acceptance branch starts from. Settings gitlink `008b87fddb0fb12084690a40127454a23b8e2e5c`, the same as 158.0-1 |
| CI gates (log) | All four APKs unsigned (no v1 block, no v2/v3 block); `versionName ['158.0-2-default'] versionCodes [2016190288, 2016190290, 2016190294, 2016190295]`; `OK: MOZ_BUILD_DATE 20261014100000`; update check compiled in for all four |
| Artifact | `redoubt-android-unsigned`, 624,023,742 bytes, digest `sha256:9a16c6efee50fb823ecc463553455ce073defecc9187e93d7a83fa91f24880dd` (`ci/artifacts.json`). `sha256sum -c SHA256SUMS`: all four OK (`ci/SHA256SUMS.check.txt`) |
| Artifact SHA256SUMS | arm64-v8a `f0d0c2e968c2a78fd14a0991ddc84c404949f1f4f50f76c5d9484024083537ed`<br>armeabi-v7a `a132b2d6d844eaf44d91a9817f35414ffc79385f361c4eb78d9ebd4cf37adb39`<br>universal `78f921260d738d03bde7e3a506d448c2677327587d4fbed63019fa48284cc0da`<br>x86_64 `069a49dbfc6e62144cb69ffe083b122a586de8a82d6b0d3076924d2fdd87fec8` |
| Installed (x86_64) | `0080b12ffdef57cff087aee2b5a492f4678cf6aafb53459ae6ca3c5e925cb3b9`, signed with the **throwaway** key (`keep/throwaway-keys/throwaway.p12`, cert `31e9a40f…b760`, `CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, apksigner 36.0.0), not the release key. All 3,278 non-signature entries equal the unsigned APK's (`device-api34/apk-identity.txt`). Every harness run, on all three images, recorded this hash (`*/smoke/exit-status.jsonl`) |
| Upgrade source | 158.0-1, throwaway-signed `c91d7fa972ba2c27f8eb4460a310357b56960e5d750ee98a15a0f1e69b67afb5`, the same file as in 158.0-1's own acceptance, with the same cert |
| `scripts/android-smoke.sh` / `android-graphics-smoke.py` | `2212781c…0d2d` / `415c7254…ecd3` at `255c87aa`. The smoke harness gained LW-M7-50's SDK-dependent `--check-isolation` since 158.0-1; the graphics harness is unchanged. Every harness run recorded HEAD `255c87aa` and 0 uncommitted changes under `scripts/` |
| Runner and probes | `scripts/`, copied from the 158.0-1 acceptance with paths changed.<br>**Changed:** `batch2.sh` adds `--check-video` twice more and `--check-isolation` three times. `batch3.sh` upgrades from 158.0-1, and its local update probe serves `doc-wrongkey-158`. `drive-api30.sh` adds `--check-isolation`, `--check-video`, the process labels and the upgrade. `static-checks.sh` compares with 158.0-1, reads the gate in S11 and adds S15.<br>**New:** `drive-api31.sh`, `isolation-gate-dex.py`, `drive-api30-rerun.sh`.<br>**Not re-run:** `reddit-warm.sh` (row RD ran the cold script only) |

**Conditions.**
- **Main session (`device-api34/`).** API 34 `google_apis` x86_64, emulator-5584, booted by the
  harness from the android-34-only SDK view with `-dns-server 9.9.9.9 -tcpdump`. Every later step
  reused it with `--serial`.
  - Every check started from a fresh profile, except the upgrade, which keeps its profile on
    purpose.
  - Logcat was streamed for every harness run.
  - **Wi-Fi was switched off** at the start of batch 2, as in 158.0-1.
- **Second session (`device-api31/`).** API 31 `google_apis` x86_64, emulator-5582,
  `google/sdk_gphone64_x86_64/emulator64_x86_64_arm64:12/SE1A.220826.008/10564458:userdebug/dev-keys`.
  This is the system image installed for LW-M7-50 (`iso-158-2/sdkdl`, through the android-31-only
  view `iso-158-2/sdk31`), reused. The harness booted it.
- **Third session (`device-api30/`).** android-30 `default` x86_64 (no GMS), emulator-5584,
  `generic_x86_64:11/RSR1.210722.013.A2`. A fourth boot of the same image ran the graphics re-run.
- **One emulator at a time.** Each session started after the previous emulator was shut down.
- **Other devices.** Physical devices were attached to the host over adb. Every command named the
  emulator's serial, and nothing touched them.

## Static (`static/`)

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| S1 | versionName / versionCodes | **PASS.** `158.0-2-default` in all four APKs. Codes: v7a **2016190288**, arm64 **2016190290**, x86_64 **2016190294**, universal **2016190295**. All are above 158.0-1's highest (2016190151), Beta 2's (2016189383) and 157.0.1-1's (2016188823). Label `Redoubt`, package `org.redoubtbrowser`, targetSdk 37 | `apk-badging.txt` |
| S2 | ELF per ABI | **PASS.** Each split APK carries only its own ABI's ELF; the universal APK has all three ABIs | `elf-per-abi.txt` |
| S3 | Unsigned | **PASS.** 0 META-INF signature files; `apksigner verify` exits 1 for all four | `unsigned.txt` |
| S4 | Branding | **PASS.** omni.ja brand files and branding PNGs are byte-equal to 158.0-1's (0 differ) | `omni-branding.txt` |
| S5 | uBO | **PASS.** `ublock_origin.xpi` 1.75.0, sha256 `5b744158…5287` = the pin, AMO-signed, in all four | `ubo-and-omni.txt` |
| S6 | Packaged `librewolf.cfg` | **PASS, identical.** sha256 `73dc32beb523be4f184164e5819abbc54c00ad3905e14ca6bc79510a5b29f53c` in all four APKs. It is byte-equal to `settings/common.cfg + settings/android.cfg` at `008b87f`, **and byte-equal to 158.0-1's packaged cfg**, so the diff is empty. The isolation prefs are not in the cfg: Gecko sets and locks them at startup from the gate (`isolation-media-prefs.patch`), and only on API 31+ | `librewolf-cfg.txt`, `librewolf-cfg-vs-158.0-1.txt` |
| S7 | Update-check key and endpoint in the dex | **PASS.** `classes2.dex` of all four APKs: committed key (`8e714075…7de8`) once, `https://redoubtbrowser.org/update/android/latest.json` once, `Redoubt-UpdateCheck/1` once, no `/updates/android/` | `update-check-static.txt` |
| S8 | `android-cookie-banner-smoke.py --apk --fetch` | **PASS** on x86_64 and universal (exit 0, 0) | `cookie-lists-apk-*.out` |
| S10 | Build ID and diff | `MOZ_APP_VERSION 158.0-2`, `MOZ_BUILDID 20261014100000`, `MOZ_UPDATE_CHANNEL default`; each ABI's `libxul.so` carries the date. **Against 158.0-1 x86_64: 14 of 3,278 APK entries differ.** These are 158.0-1's eleven rebuild entries plus `assets/dexopt/baseline.profm`, `classes.dex` and `classes3.dex`; the Java/Kotlin side of the change is in GeckoView and Fenix. **In omni.ja, 1 of 2,310 entries differs** (`modules/AppConstants.sys.mjs`): the isolation change is in C++ and Java only | `build-id.txt`, `entries-vs-158.0-1-x86_64.txt` |
| **S11** | **Isolation gate as compiled** | **PASS, the gate.** In `GeckoProvider.createRuntime` of all four APKs (R8 inlined `isolatedContentEnabled()` there):<br>`isolatedProcessEnabled` and `appZygoteProcessEnabled` take the same register, `v2`. `v2` is written only by `sget SDK_INT`, by `const/4 #int 1` after `if-lt v2, v3` with `v3 = 31`, and else by `move` from a register holding 0. So both calls take `SDK_INT >= 31` (`isolation-gate-dex.py`, exit 0 ×4). The 158.0-1 reference still passes the literal false (`isolation-dex.py`).<br>The gate pref `media.redoubt-isolation-media.enabled` is in each ABI's `libxul.so` (×1) and in each APK's `classes2.dex` (×1); it is absent from 158.0-1's libxul.<br>The manifest is unchanged against 158.0-1 (41 `isolatedProcess=true` attributes, 1 `useAppZygote`): the services were always declared, and only the runtime choice changed | `isolation-static.txt` |
| S12 | Store-installer list in the dex | **PASS.** All six names, once in each APK | `store-installers-static.txt` |
| S14 | LW-M7-46 compiled in | **PASS.** `librewolf.webgl.prompt.notice` once in each ABI's `libxul.so` and once in each APK's `classes2.dex` | `webgl-notice-static.txt` |
| **S15** | **No build overlay** (`dev-app`) | **PASS.** All four APKs: package `org.redoubtbrowser` (no `.dev` suffix), label `Redoubt`. 0 resource strings `Redoubt Dev` or `redoubt-dev`. `ic_launcher_background` is `@color/photonInk80`, not the overlay's amber. 0 `org.redoubtbrowser.dev` in any dex. 0 `OVERLAY` lines in `librewolf.cfg`. The CI log has the workflow's own guard line `build overlays: none` | `overlays-absent.txt` |

## Device

PASS = passed. E12 = red, as expected under E12. NEG = a negative control that must fail, and did.
HL = a harness limit (see "Harness limits"); no product finding.

### Isolation (LW-M7-50), new for 158.0-2

| # | Check | API | Exit | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| **I1** | **`--check-isolation`** ×3 | 34 | 0, 0, 0 | **PASS, 12/12 each, isolation ON.**<br>`isolation-mode`: "API 34: isolation expected ON (gate: SDK >= 31); media.redoubt-isolation-media.enabled=true, locked". `isolation-prefs`: the eleven set and locked.<br>H.264+AAC played (10/9/9 frames): video `ffvpx video decoder (RDD remote)`, audio `ffvpx audio decoder (Utility Generic remote)`. VP8, VP9 and AV1, each with Opus, played and were decoded by `ffvpx` in content.<br>`canPlayType(avc1)`=`probably`, MSE avc1+mp4a supported; native HLS `canPlayType`=`""` (off, as designed).<br>3 content processes, all `u:r:isolated_app` with isolated uids `u0_i0..2`, forked by the app zygote. `:rdd` runs as `untrusted_app` with the app uid. MediaCodec: `c2.goldfish.h264.decoder` in `:rdd`, `c2.android.aac.decoder` in `:utility`, none in an isolated process.<br>18-20 `isolated_app` denials, all in the measured platform baseline; none involves media or `app_data_file`. The profile dir is 0700, owned by the app uid.<br>`isolation-remote-refusal`: with the test hook on, `:rdd` refused `video/vp9` and `:utility` refused `audio/opus`, and the clip still played in content | `device-api34/smoke/check-isolation-{1,2,3}/` |
| **I2** | **`--check-video`** ×3 | 34 | 0, 0, 0 | **PASS, 3/3 each.** VP8/Opus 13 frames, H.264+AAC 14 frames, MSE 10 frames | `device-api34/smoke/check-video{,-2,-3}/` |
| **I3** | **`--check-isolation`** ×2 | 31 | 0, 0 | **PASS, 12/12 each, isolation ON.** "API 31: isolation expected ON …=true, locked". The same rows as on API 34: H.264 in `:rdd`, AAC in `:utility` (`c2.goldfish.h264.decoder`, `c2.android.aac.decoder`), software codecs in the isolated content process, `isolated_app` content with isolated uids, 12 and 14 baseline denials, refusals by `:rdd` and `:utility` | `device-api31/smoke/check-isolation-{1,2}/` |
| **I4** | **`--check-video`** ×2 | 31 | 0, 0 | **PASS, 3/3 each.** VP8/Opus 13 frames, H.264+AAC 14 frames, MSE 9 and 11 frames | `device-api31/smoke/check-video-{1,2}/` |
| **I5** | **`--check-isolation`** | 30 | 0 | **PASS, 12/12, isolation OFF, media as in 158.0-1.**<br>"API 30: isolation expected OFF (gate: SDK >= 31); media.redoubt-isolation-media.enabled=false, locked"; the eleven keep their 158.0-1 values, unlocked.<br>H.264/AAC: `android decoder (remote)`. VP8/VP9: `android decoder (remote)`. AV1: `ffvpx video decoder`. Opus: `ffvpx audio decoder (Utility Generic remote)`. Native HLS `canPlayType`=`maybe`.<br>3 content processes as `untrusted_app` with the app uid, no app zygote, no `:rdd`. MediaCodec (OMX goldfish H.264/VP8/VP9, `c2.android.aac.decoder`) all in `:media`. No `isolated_app` denial.<br>`isolation-allowlist-inactive`: with the test hook on, VP9+Opus played, Opus in Utility, nothing refused.<br>These are the decoder names and processes that 158.0-1's code (Beta 2) showed on the same image in LW-M7-50's control run (`../../../lw-m7-50/release-158.0-2/device-api30/control-beta2-check-isolation.{json,out}`) | `device-api30/smoke/check-isolation-1/` |
| **I6** | **`--check-video`** | 30 | 0 | **PASS, 3/3** (also in rows 8 and 11) | `device-api30/smoke/check-video/` |
| **P** | process labels (`process-labels.py`, example.org + example.com) | 34 / 31 / 30 | 0 | **PASS, as gated.**<br>**API 34:** the parent, `:gpu…` and `:rdd…` are `untrusted_app` under uid 10192. The app zygote is `app_zygote`. Four `zygoteTab…GeckoChildProcessService` content processes are `u:r:isolated_app:s0:c512,c768` under uids 90000-90003.<br>**API 31:** the same picture under uid 10145.<br>**API 30:** the parent, `:gpu…` and four `:tab_disable_art_image_N` are `untrusted_app` under uid 10131; no `isolated_app`, no zygote (158.0-1's picture) | `device-api{34,31,30}/process-labels/` |

### Rows carried over from 158.0-1

| # | Check | API | Exit | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `--check-launcher-start` | 34 | 0 | **PASS** | `device-api34/smoke/check-launcher-start/` |
| 2 | `--check-aboutconfig` | 34 | 0 | **PASS.** 30 rows; the edit survived a restart. **64 prefs locked**: 158.0-1's 52 plus the gate pref and the eleven media prefs, which are locked on API 31+ | `…/check-aboutconfig/` |
| 2a | about:config CSP probe | 34 | 0 | **PASS.** 0 CSP lines from about:config; the control marker was seen | `device-api34/aboutconfig-csp/` |
| 3 | `--check-ubo-preinstall` | 34 | 0 | **PASS**, 2/2 | `…/check-ubo-preinstall/` |
| 4 | `--check-ubo-lifecycle` | 34 | 0 | **PASS**, 10/10 | `…/check-ubo-lifecycle/` |
| 4a | `--check-ubo-user-disable` | 34 | 0 | **PASS**, 3/3 | `…/check-ubo-user-disable/` |
| 5 | `--check-ubo` | 34 | 0 | **PASS** | `…/check-ubo/` |
| 6 | `--check-search` | 34 | 0 | **PASS.** noai.duckduckgo.com with no partner parameter; 4 engines | `…/check-search/` |
| 7 | `--check-no-suggest` | 30 | 0 | **PASS.** 60 s typing window: no new connection, no DNS query, 8 keep-alive, 3 background flows. Enter sent 9,227 B to noai.duckduckgo.com | `device-api30/smoke/check-no-suggest/` |
| 7′ | `--check-no-suggest` | 34 | 1 | **HL.** The flagged flows are the OS's own `www.google.com` connections and two DNS-over-TLS connections (port 853) to the emulator resolver `10.0.2.3`, one of them opened 0.1 s before the `www.google.com` connections. Port 853 is DNS over TLS, which Android's Private DNS uses; Gecko's DNS over HTTPS uses port 443. Redoubt has no Google endpoint; the google_apis image does. This is 158.0-1's row 7′; row 7 grades the check on the no-GMS image | `device-api34/smoke/check-no-suggest/` |
| 7a | `--check-no-suggest --no-suggest-negative-control` | 34 | 1 | **NEG, as expected.** Caught `ac.duckduckgo.com` on 5 connections | `…/check-no-suggest-negative-control/` |
| **8** | **baseline, with full graphics acceptance** | 30 | 0 | **PASS**, 10/10, including `video-h264` and `video-mse`. Graphics `acceptanceComplete: true`, **162/162** | `device-api30/smoke/baseline-smoke/` |
| 8′ | baseline | 34 | 1 | **HL.** Every row passes except `webgl` ("No org.redoubtbrowser window is in the input dispatcher's window list"), as in 158.0-1. The video rows pass with isolation on | `device-api34/smoke/baseline-smoke/` |
| 9 | `--check-update-privacy` | 34 | 0 | **PASS.** OFF by default, with no update-host traffic across launch and Settings (106 app events). Switched ON through the UI, the update host was contacted on relaunch and nothing else new | `device-api34/smoke/check-update-privacy/` |
| 9″ | `--check-update-privacy` | 30 | 0 | **PASS** (107 app events). 158.0-1's IPv6 harness limit (row 9′ there) did not occur in this run | `device-api30/smoke/check-update-privacy/` |
| **9a** | **update-check probe, live endpoint** | 34 | 0 | **PASS.** After the tap, `pref_key_lw_update_check=true`. The next resume made `GET …/update/android/latest.json` → 200, then `GET …/latest.json.sig` → 200. The live document is the owner-signed **158.0-1** document (`version_code` 2016190144, sha256 `17cef555…6b31` = `site/update/android/latest.json` on main), which is older than this build. **Nothing was offered:** no dialog, `lw_update_check.xml` holds only `last_run_ms`, and the app was alive.<br>Request headers: `Host`, `User-Agent: Redoubt-UpdateCheck/1`, `Accept-Encoding`, `Sec-GPC`, `Connection`, plus `Sec-Fetch-*` at connect. **No `Accept-Language`**, no cookie; load flags 16896.<br>A second resume made 0 requests. OFF half: 0 requests and no `lw_update_check.xml`. Control: 6 new records.<br>Host side: `update-manifest.py fetch` of the live document gives signature OK and "up to date" for 2016190288, 2016190294 and 158.0-1's 2016190150 | `device-api34/update-check-live/`, `update-check/live-document-verdicts.txt`, `update-check/live-latest.json{,.sig}` |
| **9b** | **wrongly signed document above this build, on the device** | 34 | 0 | **PASS, stronger than in 158.0-1.** The local TLS endpoint served `doc-wrongkey-158`: `158.0-99`, `version_code` **2016199999**, which is above all four of this build's codes. It is signed with the throwaway update key; with that key, `update-manifest.py verify` says "update offered", and with the committed key it says REJECTED.<br>In 158.0-1 the served document's 2016189999 was below the build's own code, so no offer was possible whatever the signature; this document isolates the signature check.<br>The server log shows both files fetched (`server-requests.jsonl`, 2 GETs), and Gecko saw 200 for both. **Nothing was offered**, only `last_run_ms` was written, and the app stayed alive. The test CA renewed for 158.0-1 is valid until 2026-10-27 | `device-api34/update-check-local/`, `update-check/local-wrongkey-doc/` |
| ST | store installer hides the check | 34 | 0 | **PASS.** (2) With `installerPackageName=org.fdroid.fdroid` and the stored value `true`, **the row is absent** and **0 requests** were made. (3) After an `adb install -r`, the row is back and ON, and the control made both GETs with no `Accept-Language` | `device-api34/store-installer/` |
| V | `--check-video` | 34 | 0 | see I2 | |
| DQ | `--check-delete-on-quit` | 34 | 0 | **PASS.** "recents swipe then cold start: setting on deleted the saved tabs before restore, setting off restored them" | `…/check-delete-on-quit/` |
| 10 | `--check-https-only` | 34 | 0 | **PASS**, 5/5, including `https-only-upgrade` and `https-only-exception-scope` (`expireType=1`; another port still gets the interstitial) | `…/check-https-only/` |
| TLS | `--check-tls-floor` | 34 | 0 | **PASS.** TLS 1.0 and 1.1 refused (`SSL_ERROR_PROTOCOL_VERSION_ALERT`), 1.2 and 1.3 connect; `security.tls.version.min=3` | `…/check-tls-floor/` |
| RV | `--check-revocation` | 34 | 0 | **PASS.** `OCSP.enabled=0`, `crlite_mode=2`, 0 OCSP requests; a stapled "revoked" response is refused with `SEC_ERROR_REVOKED_CERTIFICATE`; `revocation-observed` recorded only | `…/check-revocation/` |
| RFP | `--check-rfp-coherence` | 34 | 0 | **PASS**, 17/17 coherence items (RFP on; device time zone Europe/Zurich) | `…/check-rfp-coherence/` |
| AF | shadow-DOM autofill (LW-M7-42 pages, probe service) | 34 | 0 | **PASS**, the same counts as 158.0-1, now **with the page in an isolated process**. Fill requests per page: `shadow-email-only` 0, `shadow-nonlogin` 0, `shadow-closed` 0, `shadow-open` **1** (3 EditText), `plain` **1** (2 EditText), `shadow-email-only` again 0 | `device-api34/autofill/` |
| RD | reddit.com/login on a fresh profile (`reddit-cold.sh`) | 34 | 0 | **Known limit, still there, not new.** A first start straight into the login URL stays blank at 30 s and 60 s (only "Welcome to Reddit" in the UI dump). `https://www.reddit.com/` renders. The login URL opened afterwards also stays blank. This is the same result as 158.0-1's row RD | `device-api34/reddit-cold/` |
| 11 | `--check-no-gms --check-no-adjust` | 30 | 0 | **PASS**, 12/12, including a **second full graphics acceptance**, 162/162 (re-run; see "Run notes") | `device-api30/smoke/static-no-gms-no-adjust/` (first attempt: `…/static-no-gms-no-adjust-attempt1/`) |
| 11′ | the same | 34 | 1 | **HL.** `check-no-gms` and `check-no-adjust` pass; only `webgl` fails, as in 8′ | `device-api34/smoke/static-no-gms-no-adjust/` |
| W | manual WebGL page (`webgl-manual.py`) | 30 | 0 | **PASS.** Fresh install: `webgl=NULL webgl2=NULL`, no notice. After Allow (session) the list shows "WebGL — http://127.0.0.1:8466 / Allowed · This browser session", and the page reads `webgl=CONTEXT webgl2=CONTEXT`, no notice. `canvas.html` reads `readback=PROTECTED`, no notice | `device-api30/webgl-manual/` |
| 12 | `--check-strings` | 34 | 0 | **PASS.** 244,495 rows, 0 unexplained; 34 screen stops, 0 branded strings shipped | `…/check-strings/` |
| 13 | `--self-test` | 34 | 0 | **PASS** (`SELF-TEST OK`) | `…/self-test/` |
| 14 | `--first-run-capture` | 30 | 1 | **E12.** 120 events, app UID rx +25,465,762 B / tx +501,158 B. Compared with 158.0-1 below | `device-api30/smoke/first-run-capture/`, `device-api30/first-run-host-comparison.json` |
| 14′ | `--first-run-capture` | 34 | 1 | **E12.** 102 events, rx +25,517,587 B / tx +415,278 B (Wi-Fi off; not compared) | `device-api34/smoke/first-run-capture/` |
| 15 | `--check-no-remote-settings` | 34 | 1 | **E12.** The same 3 Remote Settings hosts as before | `…/check-no-remote-settings/` |
| 16 | pref audit | 34 | 0, 0 | **PASS.** Fresh `--pref-dump`: `baseline-diff.out` is empty against the committed `expected-prefs.txt`. Audit: exit 0. The SDK-dependent isolation names are deliberately not in `expected-prefs.txt` (LW-M7-50; `--check-isolation` grades them) | `device-api34/pref-audit/` |
| **17** | **upgrade 158.0-1 → 158.0-2** (`adb install -r`) | 34 | 0 | **PASS, isolation turns on over an existing profile.** Details below | `device-api34/upgrade-from-158.0-1/` |
| **18** | **upgrade 158.0-1 → 158.0-2** (`adb install -r`) | 30 | 0 | **PASS, isolation stays off.** Details below | `device-api30/upgrade-from-158.0-1/` |

**First-run hosts compared with 158.0-1's capture** (both on android-30 `default`):
- **Counts.** 120 events here; 158.0-1's capture had 102.
- **Named hosts.** One added, none gone. The added host, `malware-filter.pages.dev`, is a uBO
  filter-list mirror named in the pinned catalog `assets/uBOAssets.android.json`. uBO picks among
  the mirrors.
- **Unnamed destinations.** Three new addresses, in GitHub's (`2606:50c0:8001::153`, `::154`) and
  Fastly's (`2a04:4e42:600::485`) ranges, as before; the ranges are inferred from the prefix.
- **No `redoubtbrowser.org`.** The update check is off by default.

## Upgrades: 158.0-1 → 158.0-2, update check ON (API 34 and API 30)

`scripts/upgrade-test.py` runs three phases on one profile, on each image.

**A. 158.0-1 on a fresh install** (x86_64, 2016190150, `158.0-1-default`):
- launcher start, and the uBO sheet acknowledged;
- search suggestions ON;
- DNS over HTTPS **Max Protection**;
- **Check for updates ON** through the Settings row;
- https://example.org/ bookmarked;
- "Dan Pollock's hosts file" (`dpollock-0`) ticked in uBO and applied.

**B. The upgrade.** `adb install -r` (no `-d`, no uninstall) returned `Success`. The versionCode went
to **2016190294** and the versionName is `158.0-2-default`. The signer (`1e14b3e1`) and
`firstInstallTime` did not change. There were two launcher launches of 45 s each: the app was
alive, with no alert dialog.

**C. Read back.** Both images gave the same result:
- suggestions ON;
- DoH "Max Protection", `network.trr.mode=3`, `uri=https://dns10.quad9.net/dns-query`;
- the bookmark is present;
- uBO 1.75.0 is active, with `dpollock-0` still selected;
- `appinfo` reads 158.0-2 / `20261014100000`;
- **the update-check row is present and still ON**;
- `state-A-final.json` and `state-C-after-upgrade.json` differ only in `appinfo` and the TRR
  `buildID`/`appVersion`.

On API 34 the same profile, written by a non-isolated 158.0-1, is now served by isolated content
processes. Rows I1 and P show that state on fresh profiles; this row shows the profile data
survives the switch.

## Harness limits (no product finding)

1. **Graphics parser (API 34)** (rows 8′, 11′). The graphics acceptance and the manual WebGL page
   ran on API 30.
2. **OS traffic in the typing window (API 34)** (row 7′). Row 7 grades the check on the no-GMS image.

No crash: no `FATAL EXCEPTION`, `Fatal signal` or `ANR in org.redoubtbrowser` in any of the 44
logcat streams.

## Run notes

- **adb server died during the second API 30 graphics run (row 11).** The first attempt
  (`static-no-gms-no-adjust-attempt1/`) passed all 162 graphics checks. It then ended with
  `acceptanceComplete: false`, "Harness cleanup failed after checks", and exit 2.
  - The recorded cleanup error: `adb reverse --remove … protocol fault` and `* daemon not running;
    starting now at tcp:5037`. The host's adb server was restarted under the harness, and its
    next step found the local test server unreachable.
  - This is an infrastructure fault, not a product one. The check was re-run unchanged on a fresh
    boot of the same image (`drive-api30-rerun.sh`) and passed 12/12 with 162/162.
- **Box B.** Run 38549776387 was dispatched by the release-day step (see
  `../../../lw-m7-50/release-158.0-2/release-day/`); this acceptance only read it. Its new cache
  step (`scripts/ci-vm-boxb/prune-tree-cache.py`) kept `tree-158.0-1` and removed nothing; the
  older trees had already gone in the push preflight 38549725103.

## Update document (host side; nothing was signed with the owner's key)

- **Generated.** `scripts/update-manifest.py generate --tag android-158.0-2` on this run's
  `output-metadata.json`, published `2026-10-14T12:14:38Z` (the generation time).
  - It picks `version_code` **2016190288** (the lowest of the four) and the `android-158.0-2`
    release URLs.
  - sha256 **`4c654fa243cb75fe57c98dba2974f0d04d556ffb1d1f080ce1fa3b5f955f6f31`**.
  - It is staged in the signing bundle and copied to `update-check/latest.json`.
- **Throwaway-key signature** (`update-check/throwaway-update-test.pubkey`, the 157.0-2 acceptance's
  test key; `update-check/host-verifier.txt`):
  - With the committed key: **REJECTED**, exit 1.
  - With the throwaway key: OK, and the `--metadata` cross-check passes.
  - "Update offered" for 158.0-1 (2016190144, …146, …150, …151), Beta 2 (2016189382) and
    157.0.1-1 (2016188822).
  - "Up to date" for all four of this build's codes.
  - `sign-update-manifest.sh` refused the throwaway key (exit 2) and wrote no `.sig`.
- **No verification against the owner's key is claimed.** `site/update/` is untouched.

## Signing bundle

`~/redoubt-artifacts/release-158.0-2/signing-bundle/` (not in the repository), laid out like
158.0-1's:
- the four unsigned APKs and `SHA256SUMS` (the CI file, unchanged; `sha256sum -c` OK);
- `sign.sh` (`86c925e1…5888`), `android-verify-signature.sh` (`8a251c45…a483`), `apksigner.jar`
  (`3716d931…3dec`) and `SIGNING.md` (`dc0b9e54…3f35`). All are byte-equal to 158.0-1's bundle,
  `SHA256SUMS.tools` checks OK, and all but `apksigner.jar` are byte-equal to the repository files;
- `update/`: `latest.json` (`4c654fa2…6f31`), `sign-update-manifest.sh` (`5e0820f6…b135`),
  `update-check.android.pubkey` (`8e714075…7de8`) and `SHA256SUMS.update`.

## Not covered

- **Physical devices and other ABIs.** Only x86_64 ran on a device; arm64-v8a and armeabi-v7a
  were checked statically. Isolation on real hardware was last tested on the owner's Pixel 10 Pro
  (Android 17) with the dev-app prototype `2fa22e51` (LW-M7-50). The arm64 dev APK of the final
  code (`b00b29c8…3685`) has not been installed on the phone: it was offline when the
  release-day step tried, at 10:28-10:39 UTC.
- **API 32 and 33** were not run. The gate is one comparison (`SDK_INT >= 31`), and 31 and 34
  both pass.
- **Real video sites, and native HLS end to end.** The isolation rows use the harness's own clips.
  Native HLS is graded only by `canPlayType`. hls.js and real sites were covered by LW-M7-50's
  prototype tests, not here.
- **Real password managers.** As in 158.0-1.
- **An upgrade from 157.x or a beta.** Only the codes were checked: all are lower than this build's.
- **Owner-key signatures.** Nothing was signed with a release key.
