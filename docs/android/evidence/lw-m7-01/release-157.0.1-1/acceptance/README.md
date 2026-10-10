# 157.0.1-1 (Firefox 157.0.1): acceptance of CI run 37993605790, 2026-10-10: **PASS**

**Result: the payload PASSES acceptance and may go to the owner for signing.** After signing it
is published as the new **Latest** stable over 157.0-3. The owner decided this on 2026-10-09;
verbatim: "and then let us the the 157 sec fix we did not see".

Firefox 157.0.1 fixes [MFSA 2026-104](https://www.mozilla.org/en-US/security/advisories/mfsa2026-104/):
CVE-2026-106016, "Mitigation bypass in the File Handling component" (moderate, bug 2067465). The
build configuration is in [`../../release-157.0.1/`](../../release-157.0.1/README.md).

What the device runs showed:
- **File picker.** A real tap on an `<input type=file>` opens the Android picker
  (`com.google.android.documentsui/…PickActivity`). Fenix shows the permission prompts and the
  chooser first. A picked file reaches the page with the right name, size and content. Back, and
  denying the permissions, both cancel the request cleanly. Nothing crashed. 157.0-3 behaves the
  same way (row FP).
- **Upgrade.** 157.0-3 → 157.0.1-1 with `adb install -r` keeps the data and the update-check switch
  (row 17).
- **Downgrade guard.** Installing 157.0.1-1 over 158.0-1 Beta 1 **fails** with
  `INSTALL_FAILED_VERSION_DOWNGRADE`, both through `adb install -r` and `pm install -r`. The beta
  is left untouched (row DG). On the host, a 157.0.1-1 update document says "up to date" for
  every beta code (`update-check/host-verifier.txt`). Testers on 158 are never moved back to 157.
- **Update check.** It fetches the live, owner-signed 157.0-3 document, which is older than this
  build, and offers nothing. The request carries no `Accept-Language`.
- **Rows that also passed.** Every 157.0-3 row passes again, and so do the two product changes
  merged since 157.0-3 (LW-M7-44 uBO user disable, LW-M7-45 delete on quit after swipe-away). The
  API 34 harness limits found in the Beta 1 acceptance came up again; they are worked around and
  recorded below.

No product defect was found.

## What was tested

| | |
| --- | --- |
| CI run | <https://github.com/CPlusPlus17/Redoubt/actions/runs/37993605790>, "Android release (unsigned artifacts only)" (`android-release.yaml`), `workflow_dispatch` on `main`, job `build-unsigned` on runner `redoubt-ci-boxb`, 00:31:15-02:21:43 UTC, conclusion `success`. Inputs from the log: `MODE: full`, `UPDATE_CHECK: true`, `BUILD_DATE_IN: 20261006180000`, `BUNDLE: false`. Gate lines: `versionName ['157.0.1-1-default'] versionCodes [2016188816, 2016188818, 2016188822, 2016188823]`, `OK: MOZ_BUILD_DATE 20261006180000` (`ci/run.json`, `ci/run.log.gz`) |
| headSha (`gh run view --json headSha`) | `ff6e15f77c3db481a1846d51bb5684c9a1b27fb3`. It equals `git rev-parse origin/main` and is the commit this acceptance branch starts from. Settings gitlink `008b87fddb0fb12084690a40127454a23b8e2e5c`, the same as 157.0-3 |
| Artifact | `redoubt-android-unsigned`, 616,892,015 bytes, digest `sha256:3df863ee5f0aff4d4b6b165e0be72c324cfc0a4a0ea99c1be7fa1c614f65c5e5` (`ci/artifacts.json`). `sha256sum -c SHA256SUMS`: all four OK (`ci/SHA256SUMS.check.txt`) |
| Artifact SHA256SUMS | arm64-v8a `09c8a2c43a67cb8835bcd46bde0226179bb975e4304b6bc2c132794f70055169`<br>armeabi-v7a `d67e480e03d3bfa98ceb2525652d2a1a9f220c61628cdbdc8d15cf252b33440c`<br>universal `0df273a9948174c63127ac722d7ccafbb4ce7df1b3495678681b714ee5be352b`<br>x86_64 `317f93ad7a7ee94cfe1d40b97b093a4feb5dc11e69f9712ee55642aa3333efb3` |
| Installed (x86_64) | `22d15fdd91c6b063c807816f4941f9a2f9d2508a8378df581171b9ce1d67d153`, signed with the **throwaway** key (`keep/throwaway-keys/throwaway.p12`, cert `31e9a40f…b760`, `CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, apksigner 36.0.0), not the release key. Its 3,273 entries other than the signature files equal the unsigned APK's (`device-api34/apk-identity.txt`). Every harness run recorded this hash (`*/smoke/exit-status.jsonl`) |
| 157.0-3 (upgrade source, file-picker contrast) | throwaway-signed `d4cf46e500bbd30990c29728d0db421d0acc38f90e49b43d7842c9dc169a164b`, the same file as the 157.0-3 acceptance's candidate |
| 158.0-1 Beta 1 (downgrade guard) | throwaway-signed `ebf36ea1bc7f63f35c8b082fc7b9f39b403e9afad06d0317c98827ea70451389`, the Beta 1 acceptance's candidate, same cert |
| `scripts/android-smoke.sh` / `android-graphics-smoke.py` | `ef85ddfb…8f23` / `ce0072ea…4612` at `ff6e15f7`, the same as in the Beta 1 acceptance. Every harness run recorded HEAD `ff6e15f7` and 0 uncommitted changes under `scripts/` |
| Runner and probes | `scripts/`, copied from the Beta 1 acceptance with paths changed and `autofill.sh` dropped (LW-M7-42 is not on main). New: **`filepicker-probe.py`** and **`downgrade-guard.sh`**. `drive.sh` now stops if the first check leaves no emulator. `drive-api30.sh` adds `--check-no-suggest`. `static-checks.sh` compares with 157.0-3 |

**Conditions.**
- **Main session (`device-api34/`).** API 34 `google_apis` x86_64
  (`google/sdk_gphone64_x86_64/emu64xa:14/UE1A.230829.050/12077443`, emulator-5584). The harness
  booted it from an SDK view that holds only `android-34`, with `-dns-server 9.9.9.9 -tcpdump`.
  Every later step reused it with `--serial`.
  - Every check started from a fresh profile, except the upgrade, which keeps its profile on purpose.
  - Logcat was streamed for every harness run.
  - **Wi-Fi was off** from batch 2 on, as in Beta 1.
- **Second session (`device-api30/`).** android-30 `default` x86_64 (no GMS, emulator-5582). It ran
  the graphics acceptance twice, `--check-update-privacy`, `--check-no-suggest` and
  `--first-run-capture`. It started after the API 34 emulator was shut down. Only one emulator
  ran at a time, and none ran while the Beta 2 acceptance held the emulator.
- **Other devices.** Physical devices were attached over wireless adb. Every command named the
  emulator's serial.

## Static (`static/`)

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| S1 | versionName / versionCodes | **PASS.** `157.0.1-1-default` in all four APKs. Codes: v7a **2016188816**, arm64 **2016188818**, x86_64 **2016188822**, universal **2016188823**. All four are **above 157.0-3's highest code, 2016188751, and below Beta 1's lowest, 2016188904**. `android-aab.py versioncode --build-date 20261006180000` gives the same numbers. Beta 2 (build date 20261009160000) starts at 2016189376. Label `Redoubt`, package `org.redoubtbrowser`, targetSdk 37 | `apk-badging.txt` |
| S2 | ELF per ABI | **PASS.** Each split APK carries only its own ABI's ELF: 14 shared objects + 1 PIE. The universal APK has all three ABIs | `elf-per-abi.txt` |
| S3 | Unsigned | **PASS.** 0 META-INF signature files. `apksigner verify` exits 1 for all four | `unsigned.txt` |
| S4 | Branding | **PASS.** The omni.ja brand files and branding PNGs are byte-equal to 157.0-3's. omni.ja is identical in all four APKs | `omni-branding.txt` |
| S5 | uBO | **PASS.** `ublock_origin.xpi` 1.75.0, sha256 `5b744158…5287` = the pin, AMO-signed, in all four | `ubo-and-omni.txt` |
| S6 | Packaged `librewolf.cfg` | **PASS, unchanged.** sha256 `73dc32beb523be4f184164e5819abbc54c00ad3905e14ca6bc79510a5b29f53c` in all four APKs. It is byte-equal to `settings/common.cfg + settings/android.cfg` at `008b87f` **and to 157.0-3's packaged cfg**, so the diff is empty | `librewolf-cfg.txt`, `librewolf-cfg-vs-157.0-3.txt` |
| S7 | Update-check key and endpoint in the dex | **PASS.** In all four APKs, `classes2.dex` carries the committed key (`8e714075…7de8`) once, `https://redoubtbrowser.org/update/android/latest.json` once and `Redoubt-UpdateCheck/1` once. There is no `/updates/android/` path | `update-check-static.txt` |
| S8 | `android-cookie-banner-smoke.py --apk --fetch` | **PASS** on x86_64 and universal (exit 0, 0) | `cookie-lists-apk-*.out` |
| S10 | Build ID and diff | `MOZ_APP_VERSION 157.0.1-1`, `MOZ_BUILDID 20261006180000`. Each ABI's `libxul.so` carries the date. Against 157.0-3 x86_64, 193 of 3,273 APK entries differ: 178 R8-renamed `res/` files, `resources.arsc`, both dex files, `libxul`/`libmozglue`, the manifest, the baseline profile and the built-in extension manifests. Only 3 of 2,304 omni.ja entries differ: `AppConstants.sys.mjs`, `buildconfig.html` and `defaults/settings/last_modified.json` | `build-id.txt`, `entries-vs-157.0-3-x86_64.txt` |
| S11 | Isolation as compiled | **PASS, off.** `GeckoProvider.createRuntime` passes `const/4 v12, #int 0` to both isolation builder calls in all four APKs, as in 157.0-3 | `isolation-static.txt` |
| S12 | Store-installer list in the dex | **PASS.** All six names are present once in each APK | `store-installers-static.txt` |

## Device

PASS = passed. E12 = red, as expected under E12. NEG = a negative control that must fail and did.
HL = a harness limit of the API 34 image (see "Harness limits").

| # | Check | API | Exit | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `--check-launcher-start` | 34 | 0 | **PASS** | `device-api34/smoke/check-launcher-start/` |
| 2 | `--check-aboutconfig` | 34 | 0 | **PASS.** 30 rows; the edit survived a restart; 52 prefs locked | `…/check-aboutconfig/` |
| 2a | about:config CSP probe | 34 | 0 | **PASS**, 0 CSP lines from about:config | `device-api34/aboutconfig-csp/` |
| 3 | `--check-ubo-preinstall` | 34 | 0 | **PASS**, 2/2 | `…/check-ubo-preinstall/` |
| 4 | `--check-ubo-lifecycle` | 34 | 0 | **PASS**, 10/10 | `…/check-ubo-lifecycle/` |
| 4a | `--check-ubo-user-disable` (LW-M7-44) | 34 | 0 | **PASS**, 3/3. A reload during the readiness wait still pauses browsing; a user disable continues unfiltered with no failure dialog | `…/check-ubo-user-disable/` |
| 5 | `--check-ubo` | 34 | 0 | **PASS** | `…/check-ubo/` |
| 6 | `--check-search` | 34 | 0 | **PASS.** noai.duckduckgo.com with no partner parameter; 4 engines | `…/check-search/` |
| 7 | `--check-no-suggest` | 30 | 0 | **PASS.** 60 s typing window: no new connection, no DNS query, 8 keep-alive, 3 background flows. Enter sent 2,404 B to noai.duckduckgo.com | `device-api30/smoke/check-no-suggest/` |
| 7′ | `--check-no-suggest`, three runs | 34 | 1, 1, 1 | **HL, no app traffic shown.** Run 1: the only flagged flow is the OS's DNS-over-TLS connection to the emulator resolver (`10.0.2.3:853`), opened before typing, which sent one 24-byte record (the size of a TLS 1.3 alert). Run 2: quiet typing window; it failed because `adb input` dropped a keystroke (typed `lwsmokeq3076`, URL `q=lwsmokeq306`). Run 3: the OS resolved and reached `www.google.com` over QUIC during the window. Redoubt has no Google endpoint; the google_apis image does. The device-wide capture cannot attribute flows to a uid, which is why row 7 ran on the no-GMS image | `…/check-no-suggest{,-rerun,-rerun2}/` |
| 7a | `--check-no-suggest --no-suggest-negative-control` | 34 | 1 | **NEG, as expected.** Caught `ac.duckduckgo.com` on 3 connections | `…/check-no-suggest-negative-control/` |
| 8 | baseline, with **full graphics acceptance** | 30 | 0 | **PASS**, 10/10, including `video-h264` and `video-mse`. Graphics `acceptanceComplete: true`, **161/161** | `device-api30/smoke/baseline-smoke/` |
| 8′ | baseline | 34 | 1 | **HL.** Every row passes except `webgl` ("No org.redoubtbrowser window is in the input dispatcher's window list"), as in Beta 1 | `device-api34/smoke/baseline-smoke/` |
| 9 | `--check-update-privacy` | 34 | 0 | **PASS.** OFF by default, with no update-host traffic across launch and Settings (107 app events). Switched ON through the UI, the update host was contacted on relaunch and nothing else new | `device-api34/smoke/check-update-privacy/` |
| 9′ | `--check-update-privacy` | 30 | 1 | **HL, analysed: no extra host.** The only flagged flow is `tcp 2606:50c0:8000::153:443`. It carried 0 payload bytes: a SYN 0.2 ms before the IPv4 SYN to `185.199.109.153`, whose SNI is `redoubtbrowser.org` (Happy Eyeballs). `2606:50c0:8000::153` is one of redoubtbrowser.org's own AAAA records (`dig AAAA redoubtbrowser.org @9.9.9.9`: `2606:50c0:8000…8003::153`). The harness named the flow `curbengh.github.io`, a uBO list host on the same GitHub Pages address, because it names flows by DNS answers. This is the same limit as Beta 1's row 9′ | `device-api30/smoke/check-update-privacy/` (`on_window_flows`) |
| **9a** | **update-check probe, live endpoint** | 34 | 0 | **PASS.** After the tap, `fenix_preferences.xml` holds `pref_key_lw_update_check=true`. The next resume made `GET …/update/android/latest.json` → **200**, then `GET …/latest.json.sig` → **200**. The live document is the owner-signed **157.0-3** document (`badc082e…f282`, `version_code` 2016188744), which is older than this build. **Nothing was offered:** there was no dialog, `lw_update_check.xml` holds only `last_run_ms`, and the app was alive at 45 s.<br>Request headers: `Host`, `User-Agent: Redoubt-UpdateCheck/1`, `Accept-Encoding`, `Sec-GPC`, `Connection`, plus `Sec-Fetch-*` at connect. **No `Accept-Language`**, no `Accept`, no cookie; `LOAD_ANONYMOUS` and `LOAD_BYPASS_CACHE` are set.<br>A second resume made 0 requests. OFF half: 0 requests and no `lw_update_check.xml`. Control: switching it on again repeated the GETs.<br>Host side: `update-manifest.py verify` of the live document gives signature OK and "up to date" for 2016188822 | `device-api34/update-check-live/`, `update-check/live-document-verdicts.txt` |
| 9b | wrongly signed document, on the device | 34 | 0 | **PASS.** The local TLS endpoint served the throwaway-key document (`157.0-99`, 2016189999). The server log shows both files fetched with 200. Nothing was offered, and the app stayed alive | `device-api34/update-check-local/` |
| ST | store installer hides the check | 34 | 0 | **PASS.** (2) With `installerPackageName=org.fdroid.fdroid` and the stored value `true`, **the row is absent** and **0 requests** were made. (3) After a hand reinstall the row is back and ON, and the control made both GETs with no `Accept-Language` | `device-api34/store-installer/` |
| P | process labels | 34 | 0 | **PASS.** The parent, `:gpu…` and four `:tab…` processes are all `u:r:untrusted_app:…` under uid 10192. No `isolated_app` or zygote process | `device-api34/process-labels/` |
| V | `--check-video` | 34 | 0 | **PASS**, 3/3: VP8/Opus 13 frames, H.264+AAC 14 frames, MSE 9 frames (and in rows 8 and 11 on API 30) | `…/check-video/` |
| DQ | `--check-delete-on-quit` (LW-M7-45) | 34 | 0 | **PASS.** "recents swipe then cold start: setting on deleted the saved tabs before restore, setting off restored them" | `…/check-delete-on-quit/` |
| **FP** | **file picker** (`filepicker-probe.py`, new) | 34 | 0 | **PASS.** The page is `<input type=file>` covering the viewport on a loopback origin (`adb reverse`), and the tap is a real `input tap`. A file `redoubt-pick-<t>.txt` (36 B) was pushed to Downloads.<br>**Deny:** Fenix asked for camera, microphone and "music and audio". With all three answered "Don't allow", the request was dismissed without a picker, the page received `cancel`, and the app was alive.<br>**Pick:** with all three allowed, Fenix showed the chooser (Camera, Camera, Camcorder, Media). "Media" opened `com.google.android.documentsui/…PickActivity`. Tapping the file gave the page `name` = the file, `size` 36, `type` text/plain and the exact content via `FileReader`.<br>**Back:** the picker opened again, Back closed it, and the page received `cancel`.<br>Crash buffer empty.<br>**157.0-3 contrast** (same probe): the same path and verdict, so the picker flow did not change.<br>Attempts 1-2 (`filepicker-attempt{1,2}/`) were probe-development runs: attempt 1 had no handler for the three prompts and the chooser, and attempt 2 still graded the deny case as "picker expected". In both, the app stayed alive with an empty crash buffer | `device-api34/filepicker/`, `filepicker-157.0-3/` |
| 10 | `--check-https-only` | 34 | 0 | **PASS**, 3/3 | `…/check-https-only/` |
| 11 | `--check-no-gms --check-no-adjust` | 30 | 0 | **PASS**, 12/12, including a **second full graphics acceptance**, 161/161 | `device-api30/smoke/static-no-gms-no-adjust/` |
| 11′ | the same | 34 | 1 | **HL.** `check-no-gms` and `check-no-adjust` pass; only the baseline's `webgl` row fails, as in 8′ | `device-api34/smoke/static-no-gms-no-adjust/` |
| 12 | `--check-strings` | 34 | 0 | **PASS.** 243,784 rows, 0 unexplained; 34 screen stops, 0 branded strings shipped | `…/check-strings/` |
| 13 | `--self-test` | 34 | 0 | **PASS** (`SELF-TEST OK`) | `…/self-test/` |
| 14 | `--first-run-capture` | 30 | 1 | **E12.** 118 events, app uid rx +25,712,345 B / tx +586,094 B. Compared with 157.0-3 below | `device-api30/smoke/first-run-capture/`, `device-api30/first-run-host-comparison.json` |
| 14′ | `--first-run-capture` | 34 | 1 | **E12.** 102 events, rx +24,310,096 B / tx +447,066 B. Not compared, because the google_apis image adds OS traffic | `device-api34/smoke/first-run-capture/` |
| 15 | `--check-no-remote-settings` | 34 | 1 | **E12.** The same 3 Remote Settings hosts as before | `…/check-no-remote-settings/` |
| 16 | pref audit | 34 | 0, 0 | **PASS.** Fresh `--pref-dump`: 58 rows, `baseline-diff.out` empty. Against the committed baseline: 0 violations, 0 non-must-lock diffs | `device-api34/pref-audit/` |
| 17 | **upgrade 157.0-3 → 157.0.1-1** | 34 | 0 | **PASS.** Details below | `device-api34/upgrade/` |
| **DG** | **downgrade guard** (`downgrade-guard.sh`, new) | 34 | 0 | **PASS.** Details below | `device-api34/downgrade-guard/` |

**First-run hosts compared with 157.0-3's capture** (both on android-30 `default`):
- **Counts.** 118 events here; 157.0-3 had 120.
- **Named hosts.** No host added and none gone (`named_hosts_added: []`, `named_hosts_gone: []`).
- **Unnamed destinations.** New: `2606:50c0:8001::153` (GitHub's range) and `2a04:4e42:600::485` (Fastly's range), as before. The ranges are inferred from the prefix.
- **No `redoubtbrowser.org`.** The update check is off by default.

## Upgrade: 157.0-3 → 157.0.1-1, update check ON

`scripts/upgrade-test.py`, three phases on one profile, as in Beta 1.
- **A.** On a fresh install of 157.0-3 (2016188750): the uBO sheet was acknowledged. Suggestions ON, DoH **Max Protection**, **Check for updates ON** (157.0-3 ran its own check), https://example.org/ bookmarked, and `dpollock-0` ticked and applied in uBO.
- **B.** `adb install -r` (no `-d`): `Success`, versionCode 2016188750 → **2016188822**, versionName `157.0.1-1-default`. The signer and `firstInstallTime` (05:15:37 device time) did not change. Two 45 s launcher launches: the app was alive, with no alert dialog and an empty crash buffer.
- **C.** Read back on the upgraded profile:
  - Suggestions ON.
  - DoH "Max Protection", `network.trr.mode=3`, Quad9 URI.
  - The bookmark is present.
  - uBO 1.75.0 is active, and `selectedFilterLists` is identical to phase A's (`dpollock-0` included).
  - `appinfo` reads 157.0.1-1 / `20261006180000`.
  - **The update-check row is present and still ON.** `lw_update_check.xml` keeps phase A's `last_run_ms`.
  - The TRR and uBO state equal phase A's except `appVersion`/`buildID` (`state-A-final.json` vs `state-C-after-upgrade.json`).

## Downgrade guard: 157.0.1-1 over 158.0-1 Beta 1

157.0.1-1's codes sit below the betas' on purpose (build hour 20261006180000 lies between 157.0-3's and
Beta 1's). `scripts/downgrade-guard.sh` ran these steps:
1. **Install Beta 1.** Fresh install of the Beta 1 x86_64 APK (2016188910, `158.0b4-1-default`), then one launch: the app was alive at 25 s.
2. **`adb install -r` of 157.0.1-1.** It returned **`Failure [INSTALL_FAILED_VERSION_DOWNGRADE: Downgrade detected: Update version code 2016188822 is older than current 2016188910]`**, exit 1. PackageManager logged the same line.
3. **`pm install -r`.** The streamed install, as an installer app would do it, gave the same failure.
4. **Beta 1 is untouched.** `versionCode`, `versionName`, `firstInstallTime` and `lastUpdateTime` are unchanged. It starts again, alive at 20 s, with an empty crash buffer.

Both APKs carry the same throwaway cert (`31e9a40f…b760`, printed in the log), so the refusal is
about the version, not the signer. On the host, the 157.0.1-1 document says "up to date" for
2016188904 and 2016188910 (`update-check/host-verifier.txt`), so the update check never offers
157.0.1-1 to a beta either.

## Harness limits of the API 34 image (no product finding)

The first two are the same as in Beta 1. The third is new here.
1. **Graphics parser** (rows 8′, 11′). The graphics acceptance ran on API 30 instead: 161/161, twice.
2. **IPv6 Happy Eyeballs naming** (row 9′, which this time came up on API 30). The flow is analysed above; row 9 is clean.
3. **OS traffic in the typing window** (row 7′). The google_apis image's DNS-over-TLS and Google
   QUIC traffic, plus one dropped `adb input` keystroke, made `--check-no-suggest` fail three times
   on API 34. None of the flagged flows is the app's. The same check passes on the no-GMS API 30
   image (row 7).

Fixing the harness is not part of this acceptance.

## Update document (host side; nothing was signed with the owner's key)

- **Generated.** `scripts/update-manifest.py generate --tag android-157.0.1-1` on this run's
  `output-metadata.json`, with `--published 2026-10-10T02:32:26Z` (the generation time). It picks
  `version_code` **2016188816** (the lowest of the four) and the `android-157.0.1-1` release URLs.
  sha256 **`2d0ea8713521f0167b9c9b9a72fcedca23a30596a3c2e24afb744a085dfaefe1`**. It is staged in
  the signing bundle and copied to `update-check/latest.json`.
- **Throwaway-key signature** (`update-check/throwaway-update-test.pubkey`, the 157.0-2 acceptance's
  test key):
  - With the committed key: **REJECTED**, exit 1.
  - With the throwaway key: OK, and the `--metadata` cross-check passes.
  - Verdicts: "update offered" for 157.0-3's 2016188744, 2016188750 and 2016188751. "Up to date"
    for this build's 2016188822 and for Beta 1's 2016188904 and 2016188910.
  - `sign-update-manifest.sh` refused the throwaway key and wrote no `.sig`.
- **No verification against the owner's key is claimed.**

## Signing bundle

`~/redoubt-artifacts/release-157.0.1-1/signing-bundle/` (not in the repository), laid out like
157.0-3's:
- the four unsigned APKs and `SHA256SUMS` (the CI file, unchanged; `sha256sum -c` OK);
- `sign.sh` (`86c925e1…5888`), `android-verify-signature.sh` (`8a251c45…a483`), `apksigner.jar`
  (`3716d931…3dec`) and `SIGNING.md` (`dc0b9e54…3f35`), all byte-equal to 157.0-3's. `SHA256SUMS.tools`
  is identical;
- `update/`: `latest.json` (`2d0ea871…efe1`), `sign-update-manifest.sh` (`5e0820f6…b135`),
  `update-check.android.pubkey` (`8e714075…7de8`) and `SHA256SUMS.update`.

## Not covered

- **The vulnerability itself.** Row FP smoke-tests the file-picker path that 157.0.1 changed; it
  does not exercise CVE-2026-106016. The fix comes from Mozilla's source (tarball signature checked
  in `../../release-157.0.1/`).
- **Physical devices and other ABIs.** Only x86_64 ran on a device; the ARM APKs were checked
  statically.
- **Real-site video, real password managers, and the 157.0-1 probes:** the same scope as in Beta 1.
- **Owner-key signatures.** Nothing was signed with a release key.
