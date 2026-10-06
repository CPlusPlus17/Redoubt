# 157.0-3: device acceptance of CI run 37441476096, 2026-10-06: **PASS**

**Result: the payload PASSES acceptance. It may go to the owner for signing.** 157.0-3 is the
H.264/AAC video hotfix (LW-M7-43, owner decision 2026-10-06, verbatim: "Accept, turn isolation
off"). On the device:
- H.264 + AAC play, both as a progressive MP4 and through MSE. 157.0-2 plays neither (`--check-video`, rows V1-V3).
- Web content runs in `untrusted_app` `:tab` processes under the app's uid, and no app process is `isolated_app`. 157.0-2 on the same AVDs shows `isolated_app` `zygoteTab` processes (row P).
- The compiled code passes the literal `false` to both isolation builder calls, where 157.0-2 passes `true` (S11).

The two other product changes since 157.0-2 work on the device too. Neither had been tested on a built APK before this run:
- The update request carries **no `Accept-Language`** (rows 9a, ST).
- With F-Droid as the installer of record, the update-check row is **hidden** and nothing is sent, although the stored switch value is `true`. A hand reinstall brings the row back, still ON (row ST, on API 30 and API 34).

The packaged `librewolf.cfg` is byte-identical to 157.0-2's. The upgrade from 157.0-2, with the update check ON, keeps the data and the switch state (row 17). No product defect was found.

## What was tested

| | |
| --- | --- |
| CI run | <https://github.com/CPlusPlus17/Redoubt/actions/runs/37441476096>, "Android release (unsigned artifacts only)" (`android-release.yaml`), `workflow_dispatch` on `main`, job `build-unsigned` on runner `redoubt-ci-boxb`, 09:16:48-11:09:24 UTC, conclusion `success`. Inputs from the log: `MODE: full`, `UPDATE_CHECK: true`, `BUILD_DATE_IN: 20261006090000` (`ci/run.json`, `ci/run.log.gz`) |
| headSha (from `gh run view --json headSha`) | `19f866ea81aee14352b1c041108eb180b47f4848`. This equals `git rev-parse origin/main` and is the commit this branch starts from. Settings gitlink `008b87fddb0fb12084690a40127454a23b8e2e5c`, the same as 157.0-2 |
| Artifact | `redoubt-android-unsigned`, 616,820,345 bytes, digest `sha256:bd897a7111ea948202446ae33bf48c5a37c42a0ba85f765b52c199f35789358b` (`ci/artifacts.json`). `sha256sum -c SHA256SUMS`: all four OK (`ci/SHA256SUMS.check.txt`) |
| Artifact SHA256SUMS | arm64-v8a `892e1074217b0d86186cf219f6d4c19e84fc3fb304b183a172650e6ee04a8eeb`<br>armeabi-v7a `1d3f45cd264d084a0c5698fa3f9a2c778d90d857e9cd900ff40c126321925eb4`<br>universal `01735f67de2b43867ef4699b38cef745bb4f7e372534bf1f8f68d7b0b4eb54e5`<br>x86_64 `fd2f263431d7705850ca4d8f37d7e0df8c4b31edd61dd928bcc1df94b0fb581e` |
| Installed (x86_64) | `d4cf46e500bbd30990c29728d0db421d0acc38f90e49b43d7842c9dc169a164b`. Signed with the **throwaway** key (cert `31e9a40f…b760`, `CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, v2+v3, apksigner 36.0.0), not the release key. All 3,131 non-META-INF entries equal the unsigned APK's (`device/apk-identity.txt`). Every harness run recorded this hash (`device/smoke/exit-status.jsonl`) |
| 157.0-2 (upgrade source and contrast) | throwaway-signed `ee97f58b50789a7dae969785dcef7e6566d58681791c580eb62f82663e9dbfe3`, the same file as the 157.0-2 acceptance's candidate |
| `scripts/android-smoke.sh` | `a69126f1ccbb3c024ba8512408a89e5f48bc7af91682175d923505fc060a3a19`. This is new since 157.0-2: it adds the H.264/MSE video rows (LW-M7-43) and the per-connection `--check-update-privacy` grading (`e62246fc`) |
| `scripts/android-graphics-smoke.py` / `android-cookie-banner-smoke.py` | `ce0072ea…4612` / `b9c88af6…9274`, both unchanged since 157.0-2 |
| Runner and probes | `scripts/`, copied from the 157.0-2 run-2 acceptance with paths changed. New: `store-installer-probe.py`, `process-labels.py`, `isolation-dex.py`, `drive-api34.sh`. `upgrade-test.py` now upgrades 157.0-2 → 157.0-3 with the update check ON. `batch2.sh` adds `--check-video`. Every harness run recorded HEAD `bff7583b` (the scripts commit on this branch) and 0 uncommitted changes under `scripts/` |

**Conditions.**
- **Main suite (`device/`).** emulator-5582, android-30 `default` x86_64: no GMS, SwANGLE, booted by the harness with `-dns-server 9.9.9.9 -tcpdump`. This is the harness's own image choice and the same AVD type as the 157.0-2 acceptance, so the first-run comparison stays like for like. After the first check the emulator was reused with `--serial`. Every check started from a fresh profile (`pm clear`), except the upgrade, which keeps its profile on purpose. Logcat was streamed for every `--serial` run.
- **API 34 session (`device-api34/`).** A second, separate session on API 34 `google_apis` x86_64 (`sdk_gphone64_x86_64`, Android 14, emulator-5584). This is the image LW-M7-43 and LW-M6-03 measured on. The harness booted it from an SDK view that holds only `android-34`. It ran `--check-video` twice, the store-installer probe, and the process labels for 157.0-3 and 157.0-2. Only one emulator ran at a time.
- **Other devices.** A physical device (`10.0.0.156:5555`) was attached to the host. Every command named the emulator's serial.

## Summary

PASS = passed. E12 = red as expected under E12. NEG = a negative control that must fail and did.

| # | Check | Exit | Result | Evidence |
| --- | --- | --- | --- | --- |
| S1 | versionName / versionCodes | | **PASS.** `157.0-3-default` in all four APKs. Codes: v7a 2016188744, arm64 2016188746, x86_64 2016188750, universal 2016188751. They come from the same 8-code block per build hour as 157.0-2's 480/482/486/487, so they are not consecutive integers. All are above 157.0-2's highest code, 2016188487. Label `Redoubt`, package `org.redoubtbrowser` | `static/apk-badging.txt` |
| S2 | ELF per ABI | | **PASS.** Each split APK carries only its own ABI's ELF: 14 shared objects + 1 PIE. The universal APK has all three ABIs, each with its own `libxul.so` | `static/elf-per-abi.txt` |
| S3 | Unsigned | | **PASS.** 0 META-INF signature files. `apksigner verify` gives "DOES NOT VERIFY / Missing META-INF/MANIFEST.MF", exit 1, for all four | `static/unsigned.txt` |
| S4 | Branding | | **PASS.** omni.ja `brand.ftl` / `brand.properties` say Redoubt. Brand files and branding PNGs are byte-equal to 157.0-2's (0 differ). omni.ja is identical in all four APKs (`f81b81e6…8d84`) | `static/omni-branding.txt` |
| S5 | uBO | | **PASS.** `ublock_origin.xpi` 1.75.0, sha256 `5b744158…5287` = the `ubo-extension.json` pin, AMO-signed. The same in all four APKs | `static/ubo-and-omni.txt` |
| S6 | Packaged `librewolf.cfg` | | **PASS, unchanged.** sha256 `73dc32beb523be4f184164e5819abbc54c00ad3905e14ca6bc79510a5b29f53c` in all four APKs. Byte-equal to `settings/common.cfg + settings/android.cfg` at `008b87f` **and to 157.0-2's packaged cfg** (same sha256). LW-M7-43 changes no pref | `static/librewolf-cfg.txt`, `static/librewolf-cfg-vs-157.0-2.txt` |
| S7 | Update-check key and endpoint in the dex | | **PASS.** In all four APKs, `classes2.dex` carries the committed key (`8e714075…7de8`) once, `https://redoubtbrowser.org/update/android/latest.json` once, and `Redoubt-UpdateCheck/1`. No old `/updates/android/` path | `static/update-check-static.txt` |
| S8 | `android-cookie-banner-smoke.py --apk --fetch` | 0, 0 | **PASS**, 5/5 on x86_64 and on universal | `static/cookie-lists-apk-*.out` |
| S9 | `--check-strings --check-no-gms --check-no-adjust` (static) | 0 | **PASS.** 243,650 rows, 0 unexplained | `static/static-strings-nogms-noadjust.*` |
| S10 | Build ID and diff | | `MOZ_BUILDID 20261006090000`, `MOZ_APP_VERSION 157.0-3`. `libxul.so` carries the date in each ABI. Against 157.0-2 x86_64: 13 of 3,273 entries differ (manifest, baseline profile, the five built-in extension manifests, omni.ja, both dex files, libmozglue, libxul). In omni.ja only `AppConstants.sys.mjs` differs | `static/build-id.txt`, `static/entries-vs-157.0-2-x86_64.txt` |
| **S11** | **Isolation as compiled** | | **PASS.** `dexdump -d` of `GeckoProvider.createRuntime` in all four APKs: `isolatedProcessEnabled` and `appZygoteProcessEnabled` both take `v12`, whose last write is `const/4 v12, #int 0` (false). The same reader on 157.0-2's x86_64 dex gives `const/4 v3, #int 1` (true), which is the negative control. The manifest still declares upstream's isolated services: 41 `isolatedProcess=true`, 1 `useAppZygote=true`, unchanged from 157.0-2. GeckoView emits them unconditionally, and the runtime setting chooses whether to use them (see P) | `static/isolation-static.txt`, `scripts/isolation-dex.py` |
| S12 | Store-installer list in the dex | | **PASS.** All six `UpdateCheck.STORE_INSTALLERS` package names are present once in each APK's `classes2.dex` | `static/store-installers-static.txt` |
| 1 | `--check-launcher-start` | 0 | **PASS** | `device/smoke/check-launcher-start/` |
| 2 | `--check-aboutconfig` | 0 | **PASS.** 30 rows, the edit survived a restart, 52 prefs locked | `device/smoke/check-aboutconfig/` |
| 2a | about:config CSP probe | 0 | **PASS.** 0 CSP errors from about:config, and the positive control was caught in the console | `device/aboutconfig-csp/` |
| 3 | `--check-ubo-preinstall` | 0 | **PASS**, 2/2 | `device/smoke/check-ubo-preinstall/` |
| 4 | `--check-ubo-lifecycle` | 0 | **PASS**, 10/10 | `device/smoke/check-ubo-lifecycle/` |
| 5 | `--check-ubo` | 0 | **PASS** | `device/smoke/check-ubo/` |
| 6 | `--check-search` | 0 | **PASS.** noai.duckduckgo.com with no partner parameter, 4 engines | `device/smoke/check-search/` |
| 7 | `--check-no-suggest` | 0 | **PASS.** 60 s typing window: 8 keep-alive, 3 background flows, 0 typing flows. Enter sent 9,123 B | `device/smoke/check-no-suggest/` |
| 7a | `--check-no-suggest --no-suggest-negative-control` | 1 | **NEG, as expected.** Caught `ac.duckduckgo.com` on 5 connections | `device/smoke/check-no-suggest-negative-control/` |
| 8 | baseline, with **full graphics acceptance** | 0 | **PASS**, 10/10, including the new `video-h264` and `video-mse` rows. Graphics `acceptanceComplete: true`, **161/161** | `device/smoke/baseline-smoke/` |
| 9 | `--check-update-privacy` | 0 | **PASS**, now graded per connection by name (`e62246fc`). OFF half: OFF by default, no update-host traffic across launch and Settings (105 app events). ON half: switched on through the UI, the update host is contacted on relaunch and nothing else new. The 157.0-2 run's IP-based false positive did not recur | `device/smoke/check-update-privacy/` |
| **9a** | **update-check probe, live endpoint** | 0 | **PASS.** After the tap, `fenix_preferences.xml` holds `pref_key_lw_update_check=true`. The next resume makes `GET …/update/android/latest.json` → **200** and then `GET …/latest.json.sig` → **200**: the live document is the owner-signed 157.0-2 document. The check offers nothing, because 2016188480 < 2016188750. There was no alert dialog and no crash, and the app was alive at 45 s. Request headers (`http-on-before-connect`): `Host`, `User-Agent: Redoubt-UpdateCheck/1`, `Accept-Encoding`, `Sec-GPC`, `Connection`, `Sec-Fetch-Dest/Mode/Site`. **No `Accept-Language`, no `Accept`**, no cookie. `LOAD_ANONYMOUS` and `LOAD_BYPASS_CACHE` are set. A second resume within 24 h made 0 requests. OFF half: switch off, throttle file removed, relaunch and resume gave 0 requests and no `lw_update_check.xml`. Control: switch back on gave the same two GETs | `update-check/device-live/` |
| 9b | wrongly signed document, on the device | 0 | **PASS.** The local TLS endpoint served the 157.0-2 acceptance's throwaway-key document (`157.0-99`, `version_code` 2016189999, which would be offered if it verified). The server log shows 2 GETs → 200. **Nothing was offered:** no dialog, no `last_offered_version`, the app alive | `update-check/device-local/` |
| **ST** | **store installer hides the check** (`store-installer-probe.py`, API 30 and API 34) | 0, 0 | **PASS on both images.** F-Droid 2.0.1 (sha256 `83d3fe52…3778`, the LW-M6-03 file) was installed first; without it, Android records no installer for `pm install -i`. The probe then ran three steps:<br>(1) Hand install: `installerPackageName` null. The row is present and OFF; tapping it ON writes `true` to `fenix_preferences.xml`.<br>(2) `pm install -r -i org.fdroid.fdroid`: `installerPackageName=org.fdroid.fdroid`, data kept, stored value still `true`. **The row is absent.** The deep link to Settings, a new session and a Home + launcher resume made **0 requests** and created **no `lw_update_check.xml`**.<br>(3) `adb install -r` by hand: installer back to null, **row back and ON**. The observed control (off, stop, throttle file removed, on) made `GET latest.json` → 200 and `.sig` → 200, with **no `Accept-Language`**.<br>**Negative control** (API 34, the same probe on 157.0-2, which predates `a06577dd`): with F-Droid as installer, the row is still shown and the check runs. Its request carries `Accept-Language` | `device/store-installer/`, `device-api34/store-installer/`, `device-api34/negative-control-157.0-2/` |
| **P** | **process labels** (`process-labels.py`, two tabs open, API 30 and API 34) | 0 | **PASS on both images.** 157.0-3: the parent, `:gpu…` and four `:tab_disable_art_image_N` content processes are all `u:r:untrusted_app:…` under the app uid (10130 on API 30, 10193 on API 34). There is no `isolated_app`, `app_zygote` or `zygoteTab` process. **157.0-2 contrast** on the same AVDs: `org.redoubtbrowser_zygote` (`app_zygote`) and four `zygoteTab…GeckoChildProcessService` processes in `u:r:isolated_app:…` under isolated uids 90000-90003 | `device/process-labels/`, `device-api34/process-labels/` |
| **V** | **`--check-video`** (API 30 once; API 34 twice) | 0, 0, 0 | **PASS, all three rows each time.** `video` (VP8/Opus WebM): 13-15 frames. `video-h264` (progressive H.264+AAC MP4): 14 frames, currentTime 0.48-0.49 s. `video-mse` (`isTypeSupported('video/mp4; codecs="avc1.42E01E,mp4a.40.2"')` = true, `addSourceBuffer` ok, 11,963 bytes appended): 10 frames, currentTime 0.35-0.36 s. The same rows also passed in baseline (8) and in 11. 157.0-2 fails `video-h264` and `video-mse` with this harness (`docs/android/evidence/video-playback/harness/`) | `device/smoke/check-video/`, `device-api34/check-video-{1,2}.*` |
| 10 | `--check-https-only` | 0 | **PASS**, 3/3 | `device/smoke/check-https-only/` |
| 11 | `--check-no-gms --check-no-adjust` (device, so the baseline runs again) | 0 | **PASS**, 12/12, including a **second full graphics acceptance**, 161/161 | `device/smoke/static-no-gms-no-adjust/` |
| 12 | `--check-strings` (device) | 0 | **PASS.** 36 screen stops, 0 branded strings shipped. One remote AMO description is reported but not gated | `device/smoke/check-strings/` |
| 13 | `--self-test` | 0 | **PASS** (`SELF-TEST OK`). The forced-failure pass now includes `video-h264` and `video-mse` | `device/smoke/self-test/` |
| 14 | `--first-run-capture` | 1 | **E12.** 120 events, app UID rx +23,857,898 B / tx +493,719 B. Compared with 157.0-2 below | `device/smoke/first-run-capture/`, `device/first-run-host-comparison.json` |
| 15 | `--check-no-remote-settings` | 1 | **E12.** The same 3 Remote Settings hosts as before | `device/smoke/check-no-remote-settings/` |
| 16 | **pref audit** (`generate-android-pref-baseline.sh` + `android-pref-audit.sh`) | 0, 0 | **PASS.** A fresh `--pref-dump` on the device: 58 rows, "baseline unchanged" (`baseline-diff.out` is empty). Against the committed baseline: 0 violations, 0 non-must-lock diffs | `device/pref-audit/` |
| 17 | **upgrade, 157.0-2 → 157.0-3** (`adb install -r`) | 0 | **PASS.** Details below | `device/upgrade/` |

**First-run hosts compared with the 157.0-2 capture** (`device/first-run-host-comparison.json`):
- **Counts.** 120 events here; 157.0-2's capture had 103.
- **Named hosts.** None gone. One added: `malware-filter.pages.dev`. This is uBO's choice between the `malware-filter` mirrors: 157.0-2 reached the `gitlab.io` mirror, and Beta 5's capture had `pages.dev`.
- **Unnamed destinations.** The new ones are `2606:50c0:8000::154`, `2606:50c0:8002::153` (GitHub's range, as before) and `2a04:4e42::485` (Fastly's range, as before). The ranges are inferred from the prefix, not looked up.
- **No `redoubtbrowser.org`.** The switch is off by default.

## Upgrade: 157.0-2 → 157.0-3, update check ON

`scripts/upgrade-test.py`, three phases on one profile.

**A. 157.0-2 (2016188486) on a fresh install.**
1. Launcher start; the uBO sheet was acknowledged.
2. Search suggestions ON.
3. DNS over HTTPS **Max Protection**: Gecko `network.trr.mode=3`.
4. **Check for updates ON** through the Settings row: `fenix_preferences.xml` reads `pref_key_lw_update_check=true`.
5. https://example.org/ bookmarked.
6. "Dan Pollock's hosts file" (`dpollock-0`) ticked in uBO's Filter lists pane and applied.

**B. Upgrade.** `adb install -r` (no `-d`, no uninstall):
- `Success`, versionCode 2016188486 → **2016188750**, versionName `157.0-3-default`, the same signer, the same `firstInstallTime` (14:18:42 device time);
- two launcher launches, each 45 s: alive, no alert dialog and no suspicious label, empty crash buffer, no FATAL lines.

**C. Read back on the upgraded profile.**
- **Suggestions:** ON.
- **DNS over HTTPS:** "Max Protection", `network.trr.mode=3`, `uri=https://dns10.quad9.net/dns-query`.
- **Bookmark:** "Example Domain" present.
- **uBO:** 1.75.0 active, AMO-signed. `selectedFilterLists` is identical to phase A's, `dpollock-0` included.
- **Version:** `appinfo` 157.0-3 / `20261006090000`.
- **Update check: row present and still ON.** `fenix_preferences.xml` keeps `pref_key_lw_update_check=true`, and `lw_update_check.xml` keeps its `last_run_ms` from 157.0-2's own check in phase A.

## Update document (host side; nothing was signed with the owner's key)

- **Generated document.** `scripts/update-manifest.py generate --tag android-157.0-3` on this run's `output-metadata.json` with `--published 2026-10-06T11:20:56Z` (the generation time). It gives `version_code` **2016188744** (the lowest of the four) and the `android-157.0-3` release URLs. sha256 **`badc082e541205f0b3fd13b2c46044550125c5e107f3b602c1b06ce61d45f282`**. It is staged in the signing bundle.
- **Throwaway-key signature** (the 157.0-2 acceptance's test key, `update-check/throwaway-update-test.pubkey`):
  - With the committed key: **REJECTED**, exit 1.
  - With the throwaway key: OK, and `--metadata` cross-check passes.
  - Verdicts: "update offered" for 157.0-2's x86_64 code 2016188486 and for its lowest code 2016188480; "up to date" for 157.0-3's own 2016188750.
  - `sign-update-manifest.sh` with the throwaway key refused and wrote no `.sig`.
- **No positive verification against the owner's key is claimed.** Only the owner can make that signature.

## Signing bundle

`~/redoubt-artifacts/release-157.0-3/signing-bundle/` (not in the repository), laid out like 157.0-2's:
- the four unsigned APKs and `SHA256SUMS` (the CI file, unchanged; `sha256sum -c` OK);
- `sign.sh` (`86c925e1…5888`), `android-verify-signature.sh` (`8a251c45…a483`) and `apksigner.jar` (36.0.0, `3716d931…3dec`), all three equal to 157.0-2's;
- `SIGNING.md` at this commit (`dc0b9e54…3f35`). It differs from 157.0-2's (`1f4b6453…ce6a`): the Google Play and F-Droid key sections were added since. `android-verify-signature.sh --signing-doc` with this file still verifies the published 157.0-2 x86_64 APK against the release fingerprint (PASS);
- `SHA256SUMS.tools` with those four;
- `update/`: `latest.json` (`badc082e…f282`), `sign-update-manifest.sh` (`5e0820f6…b135`), `update-check.android.pubkey` (`8e714075…7de8`) and `SHA256SUMS.update`.

## Not covered

- **Physical devices and other ABIs.** No physical device was used. Only x86_64 ran on a device; arm64-v8a and armeabi-v7a were checked statically.
- **Real-site video.** The owner's sites were not opened in this acceptance. The harness fixtures cover the codecs and MSE. Site-level evidence (HLS, redgifs-style players) is in `docs/android/evidence/video-playback/` for the fix build.
- **Positive on-device verification against the owner's key.** The live probe fetched the owner-signed 157.0-2 document, and the app showed nothing, which is correct for an older version_code. That outcome does not distinguish "verified, up to date" from "rejected". The owner-signed 157.0-3 document on a 157.0-2 install is the real test, after publication.
- **The 157.0-1 probes** were not repeated: stripped features, cookie online/offline, default-browser prompt.
