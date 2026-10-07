# 158.0-1 Beta 1 (Firefox 158.0b4): acceptance of CI run 37576802707, 2026-10-07: **PASS**

**Result: the payload PASSES acceptance and may go to the owner for signing as a GitHub
PRERELEASE** (owner request 2026-10-07, verbatim: "can we do a prerelease of it?"). Proposed tag
`android-158.0-1-beta.1`, title "Redoubt Android 158.0-1 — Beta 1", created with `--prerelease`
and not `--latest`, so 157.0-3 stays Latest. The in-app update check does not announce it:
`site/update/` is untouched and the signing bundle has no `update/` directory.

On the device (x86_64, throwaway-signed):
- The three product changes since 157.0-3 work on the built APK: shadow-DOM login autofill
  (LW-M7-42, same results as its own evidence), uBO switched off during the startup wait
  (LW-M7-44, `--check-ubo-user-disable` 3/3) and delete on quit after a swipe-away
  (LW-M7-45, `--check-delete-on-quit` PASS).
- Every 157.0-3 row passes again, with two harness limits of the API 34 image worked around and
  recorded below (capture over Wi-Fi, graphics parser).
- The update check fetches the live, owner-signed 157.0-3 document with no `Accept-Language`, and
  offers nothing, because 157.0-3's version_code is lower than the beta's.
- The upgrade 157.0-3 → beta with `adb install -r` keeps the data and the update-check switch.

No product defect was found.

## What was tested

| | |
| --- | --- |
| CI run | <https://github.com/CPlusPlus17/Redoubt/actions/runs/37576802707>, "Android release (unsigned artifacts only)" (`android-release.yaml`), `workflow_dispatch` on `android/158-beta1`, job `build-unsigned` on box B, 05:35:35-07:17:40 UTC, conclusion `success`. Inputs from the log: `MODE: full`, `UPDATE_CHECK: true`, `BUILD_DATE_IN: 20261007050000`, `BUNDLE: false` (`ci/run.json`, `ci/run.log.gz`). The log shows the tarball fetched from `releases/158.0b4/source/` and checked against the pinned key `14F26682…0353` |
| headSha (`gh run view --json headSha`) | `6d146b418962b95631bd4f6da3d9cdbac65b081e`, which equals `git rev-parse origin/android/158-beta1` and is the commit this acceptance branch starts from. Settings gitlink `008b87fddb0fb12084690a40127454a23b8e2e5c`, the same as 157.0-3 |
| CI gates (log) | `versionName ['158.0b4-1-default'] versionCodes [2016188904, 2016188906, 2016188910, 2016188911]`, `OK: MOZ_BUILD_DATE 20261007050000`, update check compiled in for all four APKs, artifact unsigned |
| Artifact | `redoubt-android-unsigned`, 623,984,285 bytes, digest `sha256:545eb3b38db727d11608897df72a1fcab41e2bbb5ef0ad05b1379c67f788c455` (`ci/artifacts.json`). `sha256sum -c SHA256SUMS`: all four OK (`ci/SHA256SUMS.check.txt`) |
| Artifact SHA256SUMS | arm64-v8a `edcff327ede5f6e46568bfa49025406bf372d119848fbea37fed2a57bd882437`<br>armeabi-v7a `5e19d7c97bd515d209a9164171d07a5b77344108b4e7620c2ebe88a05ac19e6c`<br>universal `1034b3119d42430ac4b006433824a91f80acce642118509a64514ef9667af5a5`<br>x86_64 `f86813bdbb26eb6d9a96f69794876516dbe7ac66901511586b19a5406ab83292` |
| Installed (x86_64) | `ebf36ea1bc7f63f35c8b082fc7b9f39b403e9afad06d0317c98827ea70451389`, signed with the **throwaway** key (`keep/throwaway-keys/throwaway.p12`, cert `31e9a40f…b760`, `CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, apksigner 36.0.0), not the release key. All 3,278 entries other than the signature files equal the unsigned APK's (`device-api34/apk-identity.txt`). Every harness run recorded this hash (`*/smoke/exit-status.jsonl`) |
| 157.0-3 (upgrade source) | throwaway-signed `d4cf46e500bbd30990c29728d0db421d0acc38f90e49b43d7842c9dc169a164b`, the same file as the 157.0-3 acceptance's candidate, same cert |
| `scripts/android-smoke.sh` / `android-graphics-smoke.py` | `ef85ddfb…8f23` / `ce0072ea…4612` at `6d146b41`, unchanged by this branch. Every harness run recorded HEAD `6d146b41` and 0 uncommitted changes under `scripts/` |
| Runner and probes | `scripts/`, copied from the 157.0-3 acceptance with paths changed. New: `autofill.sh` (LW-M7-42 pages and probe), `drive-api30.sh`, `resume.sh`; `batch2.sh` adds `--check-ubo-user-disable` and `--check-delete-on-quit` and turns Wi-Fi off; `upgrade-test.py` now upgrades 157.0-3 → beta; `static-checks.sh` compares with 157.0-3 |

**Conditions.**
- **Main session (`device-api34/`).** API 34 `google_apis` x86_64 (`google/sdk_gphone64_x86_64/emu64xa:14/UE1A.230829.050`, 1080×1920, emulator-5584). The harness booted it from an SDK view that holds only `android-34`, with `-dns-server 9.9.9.9 -tcpdump`, and every later step reused it with `--serial`. Every check started from a fresh profile, except the upgrade, which keeps its profile on purpose. Logcat was streamed for every harness run. **Wi-Fi was switched off** before batch 2 (see "Harness limits").
- **Second session (`device-api30/`).** android-30 `default` x86_64 (no GMS, emulator-5582), the image of the 157.0-3 main suite. It ran the graphics acceptance twice, `--check-update-privacy` and `--first-run-capture`. It started after the API 34 emulator was shut down; only one emulator ran at a time.
- **Other devices.** A physical device was attached to the host over wireless adb. Every command named the emulator's serial.

## Static (`static/`)

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| S1 | versionName / versionCodes | **PASS.** `158.0b4-1-default` in all four APKs (About shows 158.0b4-1). Codes: v7a 2016188904, arm64 2016188906, x86_64 2016188910, universal 2016188911. All are above 157.0-3's highest code, 2016188751 (the CI build-hour block, 20 hours after 157.0-3's). Label `Redoubt`, package `org.redoubtbrowser`, targetSdk 37 as in 157.0-3 | `apk-badging.txt` |
| S2 | ELF per ABI | **PASS.** Each split APK carries only its own ABI's ELF: 14 shared objects + 1 PIE. The universal APK has all three ABIs, each with its own `libxul.so` | `elf-per-abi.txt` |
| S3 | Unsigned | **PASS.** 0 META-INF signature files. `apksigner verify`: "DOES NOT VERIFY / Missing META-INF/MANIFEST.MF", exit 1, for all four | `unsigned.txt` |
| S4 | Branding | **PASS.** omni.ja brand files say Redoubt and are byte-equal to 157.0-3's, as are the branding PNGs. omni.ja is identical in all four APKs (`03d77116…f966`) | `omni-branding.txt` |
| S5 | uBO | **PASS.** `ublock_origin.xpi` 1.75.0, sha256 `5b744158…5287` = the `ubo-extension.json` pin, AMO-signed, in all four APKs | `ubo-and-omni.txt` |
| S6 | Packaged `librewolf.cfg` | **PASS, unchanged.** sha256 `73dc32beb523be4f184164e5819abbc54c00ad3905e14ca6bc79510a5b29f53c` in all four APKs. Byte-equal to `settings/common.cfg + settings/android.cfg` at `008b87f` **and to 157.0-3's packaged cfg**. **The diff against 157.0-3 is empty** because the settings gitlink did not move. The Firefox 158 default flips that Redoubt overrides were pinned in settings before 157.0-2 shipped, and they are in this file: `heuristic.navigation` and `heuristic.recently_visited` false, IP Protection locked off, `network.lna.allow_top_level_navigation` false | `librewolf-cfg.txt`, `librewolf-cfg-vs-157.0-3.txt` |
| S7 | Update-check key and endpoint in the dex | **PASS.** In all four APKs, `classes2.dex` carries the committed key (`8e714075…7de8`) once, `https://redoubtbrowser.org/update/android/latest.json` once, and `Redoubt-UpdateCheck/1`. There is no old `/updates/android/` path | `update-check-static.txt` |
| S10 | Build ID and diff | `MOZ_APP_VERSION 158.0b4-1`, `MOZ_BUILDID 20261007050000`, `MOZ_UPDATE_CHANNEL default`. Each ABI's `libxul.so` carries the date. Against 157.0-3 x86_64: 493 of 3,278 APK entries differ, and 184 of 2,310 omni.ja entries (a Firefox major) | `build-id.txt`, `entries-vs-157.0-3-x86_64.txt` |
| **S11** | **Isolation as compiled** | **PASS, off.** `dexdump -d` of `GeckoProvider.createRuntime` in all four APKs: `isolatedProcessEnabled` and `appZygoteProcessEnabled` both take `v12`, whose last write is `const/4 v12, #int 0` (false). This is the same as 157.0-3 (reference row). The manifest still declares upstream's isolated services (41 `isolatedProcess=true`, 1 `useAppZygote=true`), as in 157.0-3. The runtime setting chooses whether to use them (row P) | `isolation-static.txt` |
| S12 | Store-installer list in the dex | **PASS.** All six `UpdateCheck.STORE_INSTALLERS` names, once in each APK | `store-installers-static.txt` |
| S13 | LW-M7-42 actor | **PASS.** The packaged `actors/GeckoViewAutoFillChild.sys.mjs` has sha256 `8e799ac0…c03a`, the same bytes LW-M7-42 tested on its own build (`evidence/lw-m7-42/autofill-shadow-dom/README.md`) | `static/` extraction, checked by hand |

## Device

PASS = passed. E12 = red as expected under E12. NEG = a negative control that must fail and did.
HL = harness limit of the API 34 image, re-run on API 30 (see "Harness limits").

| # | Check | API | Exit | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `--check-launcher-start` | 34 | 0 | **PASS** | `device-api34/smoke/check-launcher-start/` |
| 2 | `--check-aboutconfig` | 34 | 0 | **PASS.** 30 rows, the edit survived a restart, 52 prefs locked | `…/check-aboutconfig/` |
| 2a | about:config CSP probe | 34 | 0 | **PASS.** 0 CSP errors from about:config; the positive control was seen in the console | `device-api34/aboutconfig-csp/` |
| 3 | `--check-ubo-preinstall` | 34 | 0 | **PASS**, 2/2 | `…/check-ubo-preinstall/` |
| 4 | `--check-ubo-lifecycle` | 34 | 0 | **PASS**, 10/10 | `…/check-ubo-lifecycle/` |
| **4a** | **`--check-ubo-user-disable`** (LW-M7-44) | 34 | 0 | **PASS**, 3/3. A reload during the readiness wait still pauses browsing; a user disable continues unfiltered with no failure dialog | `…/check-ubo-user-disable/` |
| 5 | `--check-ubo` | 34 | 0 | **PASS** | `…/check-ubo/` |
| 6 | `--check-search` | 34 | 0 | **PASS.** noai.duckduckgo.com with no partner parameter; 4 engines, default DuckDuckGo No-AI | `…/check-search/` |
| 7 | `--check-no-suggest` | 34 | 0 | **PASS.** 60 s typing window: 8 keep-alive, 3 background flows, no new connection, no DNS query. Enter sent 9,233 B to noai.duckduckgo.com | `…/check-no-suggest/` |
| 7a | `--check-no-suggest --no-suggest-negative-control` | 34 | 1 | **NEG, as expected.** Caught `ac.duckduckgo.com` on 5 connections | `…/check-no-suggest-negative-control/` |
| 8 | baseline, with **full graphics acceptance** | 30 | 0 | **PASS**, 10/10, including `video-h264` and `video-mse`. Graphics `acceptanceComplete: true`, **161/161** | `device-api30/smoke/baseline-smoke/` |
| 8′ | baseline | 34 | 1 | **HL.** Every row passes except `webgl`: "No org.redoubtbrowser window is in the input dispatcher's window list", a parser failure before any GL check ran | `device-api34/smoke/baseline-smoke/` |
| 9 | `--check-update-privacy` | 30 | 0 | **PASS.** OFF by default, no update-host traffic across launch and Settings (121 app events). Switched ON through the UI, the update host was contacted on relaunch and nothing else new | `device-api30/smoke/check-update-privacy/` |
| 9′ | `--check-update-privacy` | 34 | 1 | **HL, analysed: no extra host.** OFF half clean. ON half: the only flagged flow is `tcp 2606:50c0:8003::153:443 (no name)`, a single SYN with 0 payload bytes 30 ms before the IPv4 connection to `185.199.109.153` with SNI `redoubtbrowser.org` (Happy Eyeballs). `2606:50c0:8003::153` is one of redoubtbrowser.org's own AAAA records (`dig AAAA redoubtbrowser.org @9.9.9.9`: `2606:50c0:8000…8003::153`). The harness names a flow by SNI or by a DNS answer it sees, and neither happened for a SYN-only IPv6 attempt. The API 30 run (row 9) had no IPv6 attempt and passes | `device-api34/smoke/check-update-privacy/` (`on_window_flows`) |
| **9a** | **update-check probe, live endpoint** | 34 | 0 | **PASS.** After the tap, `fenix_preferences.xml` holds `pref_key_lw_update_check=true`. The next resume made `GET …/update/android/latest.json` → **200** and then `GET …/latest.json.sig` → **200**. The live document is the owner-signed **157.0-3** document (`version_code` 2016188744, sha256 `badc082e…f282`), which is **older** than the beta. **Nothing was offered:** no dialog, `lw_update_check.xml` holds only `last_run_ms` (no `last_offered_version`), and the app was alive at 45 s. Request headers: `Host`, `User-Agent: Redoubt-UpdateCheck/1`, `Accept-Encoding`, `Sec-GPC`, `Connection`, plus `Sec-Fetch-*` at connect. **No `Accept-Language`**, no `Accept`, no cookie; `LOAD_ANONYMOUS` and `LOAD_BYPASS_CACHE` set. A second resume within 24 h made 0 requests. OFF half: switch off, throttle file removed, relaunch and resume gave 0 requests and no `lw_update_check.xml`. Control: switch on again gave the same GETs. Host side, `update-manifest.py verify` on the same document: signature OK, "up to date" for all four beta codes, "update offered" for 157.0-2's 2016188486 (control) | `device-api34/update-check-live/`, `update-check/live-document-verdicts.txt` |
| 9b | wrongly signed document, on the device | 34 | 0 | **PASS.** The local TLS endpoint served the 157.0-2 acceptance's throwaway-key document (`157.0-99`, `version_code` 2016189999, which would be offered if it verified). Both files were fetched with 200; **nothing was offered**, no `last_offered_version`, the app alive | `device-api34/update-check-local/` |
| **ST** | **store installer hides the check** (`store-installer-probe.py`) | 34 | 0 | **PASS.** F-Droid 2.0.1 installed first. (1) Hand install: installer null, row present and OFF; tapped ON. (2) `pm install -r -i org.fdroid.fdroid`: installer `org.fdroid.fdroid`, stored value still `true`, **row absent**, **0 requests**, no `lw_update_check.xml`. (3) `adb install -r`: installer null, **row back and ON**; the observed control made `GET latest.json` and `.sig` with **no `Accept-Language`** | `device-api34/store-installer/` |
| **P** | **process labels** (`process-labels.py`, two tabs) | 34 | 0 | **PASS.** The parent, `:gpu…` and the `:tab_disable_art_image_N` content processes are all `u:r:untrusted_app:…` under the app uid 10192. No `isolated_app` process | `device-api34/process-labels/` |
| **V** | **`--check-video`** | 34 | 0 | **PASS**, 3/3: VP8/Opus 13 frames; progressive H.264+AAC 14 frames; MSE `avc1.42E01E,mp4a.40.2` 9 frames. The same rows also passed in rows 8 and 11 on API 30 | `…/check-video/` |
| **DQ** | **`--check-delete-on-quit`** (LW-M7-45) | 34 | 0 | **PASS.** "recents swipe then cold start: setting on deleted the saved tabs before restore, setting off restored them" | `…/check-delete-on-quit/` |
| **AF** | **shadow-DOM autofill** (LW-M7-42 pages, probe `AutofillService`) | 34 | 0 | **PASS**, the same as LW-M7-42's narrowed run. Fresh install, force-stop before each case, negative cases first. Fill requests: `shadow-email-only` **0**, `shadow-nonlogin` **0**, `shadow-closed` **0**, `shadow-open` **1** (3 EditText, username `hints=[username] focused=true`), `plain` **1** (2 EditText), `shadow-email-only` again **0**. The screenshots show the tapped field focused in each negative case | `device-api34/autofill/` |
| 10 | `--check-https-only` | 34 | 0 | **PASS**, 3/3 | `…/check-https-only/` |
| 11 | `--check-no-gms --check-no-adjust` (device) | 30 | 0 | **PASS**, 12/12, including a **second full graphics acceptance**, 161/161 | `device-api30/smoke/static-no-gms-no-adjust/` |
| 11′ | the same | 34 | 1 | **HL.** `check-no-gms` and `check-no-adjust` PASS; the baseline's `webgl` row fails as in 8′ | `device-api34/smoke/static-no-gms-no-adjust/` |
| 12 | `--check-strings` (device) | 34 | 0 | **PASS.** 244,466 resource rows, 0 unexplained; 35 screen stops, 0 branded strings shipped. One remote string is reported but not gated | `…/check-strings/` |
| 13 | `--self-test` | 34 | 0 | **PASS** (`SELF-TEST OK`) | `…/self-test/` |
| 14 | `--first-run-capture` | 30 | 1 | **E12.** 91 events, app UID rx +24,635,330 B / tx +480,527 B. Compared with 157.0-3 below | `device-api30/smoke/first-run-capture/`, `device-api30/first-run-host-comparison.json` |
| 14′ | `--first-run-capture` | 34 | 1 | **E12.** 110 events, rx +23,417,959 B / tx +379,532 B (Wi-Fi off; the google_apis image adds its own OS traffic, so this run is not compared) | `device-api34/smoke/first-run-capture/` |
| 15 | `--check-no-remote-settings` | 34 | 1 | **E12.** The same 3 Remote Settings hosts as before | `…/check-no-remote-settings/` |
| 16 | **pref audit** (`generate-android-pref-baseline.sh` + `android-pref-audit.sh`) | 34 | 0, 0 | **PASS.** Fresh `--pref-dump`: 58 rows, `baseline-diff.out` empty. Against the committed baseline: 0 violations, 0 non-must-lock diffs | `device-api34/pref-audit/` |
| 17 | **upgrade 157.0-3 → beta** (`adb install -r`) | 34 | 0 | **PASS.** Details below | `device-api34/upgrade/` |

**First-run hosts compared with the 157.0-3 capture** (both android-30 `default`,
`device-api30/first-run-host-comparison.json`):
- **Counts.** 91 events here; 157.0-3's capture had 120.
- **Named hosts.** No new host. Two are gone: `cdn.jsdelivr.net` and `malware-filter.pages.dev`. These are uBO's choices between list mirrors; this run reached `malware-filter.gitlab.io`.
- **Unnamed destinations.** The new ones are `2606:50c0:8000::153`, `2606:50c0:8001::153` and `2606:50c0:8002::154`, all in GitHub's range, as before. The range is inferred from the prefix, not looked up.
- **No `redoubtbrowser.org`.** The switch is off by default.

## Upgrade: 157.0-3 → 158.0-1 Beta 1, update check ON

`scripts/upgrade-test.py`, three phases on one profile.

**A. 157.0-3 (2016188750) on a fresh install.**
1. Launcher start; the uBO sheet was acknowledged.
2. Search suggestions ON.
3. DNS over HTTPS **Max Protection**: Gecko `network.trr.mode=3`.
4. **Check for updates ON** through the Settings row: `fenix_preferences.xml` reads `pref_key_lw_update_check=true`. 157.0-3 ran its own check right away (`last_run_ms`).
5. https://example.org/ bookmarked.
6. "Dan Pollock's hosts file" (`dpollock-0`) ticked in uBO's Filter lists pane and applied.

**B. Upgrade.** `adb install -r` (no `-d`, no uninstall; adb chose an incremental install):
- `Success`, versionCode 2016188750 → **2016188910**, versionName `158.0b4-1-default`, the same signer, the same `firstInstallTime` (10:21:23 device time);
- two launcher launches, each 45 s: alive, no alert dialog and no suspicious label, empty crash buffer, no FATAL lines.

**C. Read back on the upgraded profile.**
- **Suggestions:** ON.
- **DNS over HTTPS:** "Max Protection", `network.trr.mode=3`, `uri=https://dns10.quad9.net/dns-query`.
- **Bookmark:** "Example Domain" present.
- **uBO:** 1.75.0 active, AMO-signed. `selectedFilterLists` is identical to phase A's, `dpollock-0` included.
- **Version:** `appinfo` 158.0b4-1 / `20261007050000`.
- **Update check: row present and still ON.** `fenix_preferences.xml` keeps `pref_key_lw_update_check=true`, and `lw_update_check.xml` keeps the `last_run_ms` of 157.0-3's own check in phase A.

## Harness limits of the API 34 image (no product finding)

1. **Packet capture over Wi-Fi.** On the API 34 `google_apis` image the default network is netsim
   Wi-Fi (`wlan0`, `dumpsys connectivity`: "Active default network" = the WIFI agent), and the
   emulator's `-tcpdump` does not see it. In the first batch-2 attempt (`device-api34/attempt1-wifi/`) the capture
   file grew by 1,266 bytes between the end of `check-launcher-start` and the end of
   `check-no-suggest` (`capture_pcap_bytes` in `smoke/exit-status.jsonl` and `attempt1-wifi/exit-status.jsonl`), and `check-no-suggest` failed with "0 total capture bytes"
   although the logcat shows the search `LoadUrlAction`. The checks that passed in that attempt
   (uBO preinstall, lifecycle, user-disable, uBO, search) do not depend on the capture. The batch
   was stopped and run again from the start after `svc wifi disable`. The default network was then
   the emulated LTE link on `eth0`, which the capture sees (`exit-status.jsonl`: the capture grows
   in every check). All rows above are from that second run.
2. **Graphics parser.** `android-graphics-smoke.py` reads the window list of `dumpsys input` in
   API 30's format. API 34 prints `inputConfig=` instead of `visible=`/`flags=` and a `transform`
   line after each window, so the parser stops after the first window and the `webgl` row fails
   before any GL check (rows 8′, 11′). The graphics acceptance ran on API 30 instead (rows 8, 11,
   161/161 twice).
3. **Update privacy and IPv6.** Row 9′ is a grading limit for SYN-only IPv6 attempts. It is
   analysed above, and row 9 is the clean API 30 run.

Fixing the harness is not part of this acceptance.

## Signing bundle

`~/redoubt-artifacts/beta-158.0-1-b1/signing-bundle/` (not in the repository), laid out like
157.0-3's **without** `update/` (a prerelease is not announced by the update check):
- the four unsigned APKs and `SHA256SUMS` (the CI file, unchanged; `sha256sum -c` OK);
- `sign.sh` (`86c925e1…5888`), `android-verify-signature.sh` (`8a251c45…a483`), `apksigner.jar`
  (36.0.0, `3716d931…3dec`) and `SIGNING.md` (`dc0b9e54…3f35`), all four byte-equal to 157.0-3's
  bundle (`SHA256SUMS.tools` is identical).

## Not covered

- **Physical devices and other ABIs.** No physical device was used. Only x86_64 ran on a device;
  arm64-v8a and armeabi-v7a were checked statically.
- **Real password managers and reddit.com/login.** Autofill ran with the probe service and the
  local pages. reddit.com/login with this build was not repeated; LW-M7-42 has it on 158.0b3 with
  the same actor bytes.
- **Real-site video.** Covered by the harness fixtures only, as in 157.0-3.
- **The 157.0-1 probes** (stripped features, cookie online/offline, default-browser prompt) and the
  LW-M7-45 multi-task cases (PWA, custom tab) were not repeated here; the latter are in
  `evidence/lw-m7-45/` and PREBASE.md section 10 on 158.0b4.
- **Owner-key signature.** Nothing was signed with a release key.
