# 158.0-1 Beta 2 (Firefox 158.0 RC build2): acceptance of CI run 37960642307, 2026-10-09: **PASS**

**Result: the payload PASSES acceptance and may go to the owner for signing as a GitHub
PRERELEASE.** Owner decision 2026-10-09, verbatim: "Beta 2 from the RC now". Proposed tag
`android-158.0-1-beta.2`, title "Redoubt Android 158.0-1 — Beta 2", created with `--prerelease`
and not `--latest`, so 157.0-3 stays Latest. The in-app update check does not announce it:
`site/update/` is untouched and the signing bundle has no `update/` directory. The final 158.0-1
follows on 2026-10-13 from Mozilla's `releases/158.0` source, with a later build date and so higher
version codes.

On the device (x86_64, throwaway-signed):
- **LW-M7-46 works on the built APK.** A quiet WebGL/canvas request shows **no** "Canvas or WebGL
  was protected" snackbar: the graphics acceptance (now failing on any dump that shows the
  snackbar) passed **162/162** twice on API 30, with 190 normal-tab and 28 private-tab dumps
  checked per run. The manual WebGL page reads `webgl=NULL webgl2=NULL` with no notice, and Allow
  through the site controls gives `webgl=CONTEXT webgl2=CONTEXT`.
- The new pref `librewolf.webgl.prompt.notice` is `false` in every pref dump, matches
  `expected-prefs.txt`, and the pref audit passes.
- Every Beta 1 row passes again, with the same harness limits of the API 34 image.
- The update check fetches the live, owner-signed 157.0-3 document and offers nothing.
- Upgrades Beta 1 → Beta 2 and 157.0-3 → Beta 2 with `adb install -r` keep the data and the
  update-check switch.

No product defect was found.

## What was tested

| | |
| --- | --- |
| CI run | <https://github.com/CPlusPlus17/Redoubt/actions/runs/37960642307>, "Android release (unsigned artifacts only)" (`android-release.yaml`), `workflow_dispatch` on `android/158-beta2`, job `build-unsigned` on box B (runner `redoubt-ci-boxb`), 16:51:08-19:39:26 UTC, conclusion `success`. Inputs from the log: `MODE: full`, `UPDATE_CHECK: true`, `BUILD_DATE_IN: 20261009160000`, `BUNDLE: false` (`ci/run.json`, `ci/run.log.gz`). The log shows the tarball fetched from `candidates/158.0-candidates/build2/source/` and checked against the pinned key `14F26682…0353` |
| headSha (`gh run view --json headSha`) | `23ba08f719fd81ad45c24e49d5a910c837636f2a`, which equals `git rev-parse origin/android/158-beta2` and is the commit this acceptance commit sits on. Settings gitlink `008b87fddb0fb12084690a40127454a23b8e2e5c`, the same as Beta 1 and 157.0-3 |
| CI gates (log) | All four APKs unsigned (no v1 block, no v2/v3 block); `versionName ['158.0-1-default'] versionCodes [2016189376, 2016189378, 2016189382, 2016189383]`; `OK: MOZ_BUILD_DATE 20261009160000`; update check compiled in for all four APKs |
| Artifact | `redoubt-android-unsigned`, 624,014,751 bytes, digest `sha256:fc5e54d8a20114334bc4eea9f71af5490c52c55c3660e2c6021e024f7cb9aab3` (`ci/artifacts.json`). `sha256sum -c SHA256SUMS`: all four OK (`ci/SHA256SUMS.check.txt`) |
| Artifact SHA256SUMS | arm64-v8a `9183258c68185ee406e578ef64b82638e9a0567f42fedf3a9a26f23822144b4d`<br>armeabi-v7a `91c78762bf01c0a5768dade0acbd5bd21d3f64b5cf6f49c5b0c53c1a7f2646ec`<br>universal `aaee9ea95434c6eb0ca897b5c95f9b47c4e0ee9f7cd0b45fbd7176f39eeb96c3`<br>x86_64 `d04352ef7bef331bf8653588c9523b6c1dd724c95e499acbc0f276743441a0a3` |
| Installed (x86_64) | `295022296a3586e13efca91b09bd887fa36f90f96ac7ac9d5ee5501c883f344a`, signed with the **throwaway** key (`keep/throwaway-keys/throwaway.p12`, cert `31e9a40f…b760`, `CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, apksigner 36.0.0), not the release key. All 3,278 entries other than the signature files equal the unsigned APK's (`device-api34/apk-identity.txt`). Every harness run recorded this hash (`*/smoke/exit-status.jsonl`) |
| Upgrade sources | Beta 1 throwaway-signed `ebf36ea1bc7f63f35c8b082fc7b9f39b403e9afad06d0317c98827ea70451389` and 157.0-3 throwaway-signed `d4cf46e500bbd30990c29728d0db421d0acc38f90e49b43d7842c9dc169a164b`, the same files as in the Beta 1 acceptance, same cert |
| `scripts/android-smoke.sh` / `android-graphics-smoke.py` | `8cafa253…b684` / `415c7254…ecd3` at `23ba08f7`. Both changed since Beta 1 only by LW-M7-46 (`librewolf.webgl.prompt.notice` in the pref list; the graphics harness fails on any dump that shows the quiet snackbar and opens permissions through the site controls). Every harness run recorded HEAD `23ba08f7` and 0 uncommitted changes under `scripts/` |
| Runner and probes | `scripts/`, copied from the Beta 1 acceptance with paths changed. New: `webgl-manual.py` (the manual WebGL page, below). Changed: `static-checks.sh` compares with Beta 1 and adds S14; `upgrade-test.py` takes the source APK from `UPGRADE_SOURCE`, and `batch3.sh` runs it twice (Beta 1, then 157.0-3); `drive-api30.sh` adds the manual WebGL page; each batch now stops when it finds no `emulator-*` serial (see "Run notes") |

**Conditions.**
- **Main session (`device-api34/`).** API 34 `google_apis` x86_64 (emulator-5584, 1080×1920), booted by the harness from an SDK view that holds only `android-34`, with `-dns-server 9.9.9.9 -tcpdump`; every later step reused it with `--serial`. Every check started from a fresh profile, except the upgrades, which keep their profile on purpose. Logcat was streamed for every harness run. **Wi-Fi was switched off** at the start of batch 2, as in Beta 1, so the capture sees the traffic (`batch2.log`: "Active default network: 101", and the capture grows in every check, `exit-status.jsonl`).
- **Second session (`device-api30/`).** android-30 `default` x86_64 (no GMS, emulator-5582, `generic_x86_64:11/RSR1.210722.013.A2`), the image of the 157.0-3 and Beta 1 graphics runs. It ran the graphics acceptance twice, `--check-update-privacy`, `--first-run-capture` and the manual WebGL page. It started after the API 34 emulator was shut down.
- **Other devices.** Physical devices were attached to the host over wireless adb. Every command named the emulator's serial.

## Static (`static/`)

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| S1 | versionName / versionCodes | **PASS.** `158.0-1-default` in all four APKs, the same versionName the final 158.0-1 will have. Codes: v7a 2016189376, arm64 2016189378, x86_64 2016189382, universal 2016189383. All are above Beta 1's highest (2016188911) and 157.0-3's (2016188751). Label `Redoubt`, package `org.redoubtbrowser`, targetSdk 37. On the device, *Settings → About Redoubt* shows `158.0-1-default (Build #2016189382)` and `GV: 158.0-1-20261009160000`, so users can tell this beta from the final release by the build number | `apk-badging.txt`, `device-api34/about-page.png` |
| S2 | ELF per ABI | **PASS.** Each split APK carries only its own ABI's ELF: 14 shared objects + 1 PIE. The universal APK has all three ABIs, each with its own `libxul.so` | `elf-per-abi.txt` |
| S3 | Unsigned | **PASS.** 0 META-INF signature files. `apksigner verify`: "DOES NOT VERIFY / Missing META-INF/MANIFEST.MF", exit 1, for all four | `unsigned.txt` |
| S4 | Branding | **PASS.** omni.ja brand files and branding PNGs are byte-equal to Beta 1's. omni.ja is identical in all four APKs (`191325dd…4b3b`) | `omni-branding.txt` |
| S5 | uBO | **PASS.** `ublock_origin.xpi` 1.75.0, sha256 `5b744158…5287` = the `ubo-extension.json` pin, AMO-signed, in all four APKs | `ubo-and-omni.txt` |
| S6 | Packaged `librewolf.cfg` | **PASS, unchanged.** sha256 `73dc32beb523be4f184164e5819abbc54c00ad3905e14ca6bc79510a5b29f53c` in all four APKs, byte-equal to `settings/common.cfg + settings/android.cfg` at `008b87f`, **and byte-equal to Beta 1's packaged cfg** (and so to 157.0-3's). **Why the diff against Beta 1 is empty:** the settings gitlink did not move, and LW-M7-46's new pref is not a cfg pref: `librewolf.webgl.prompt.notice` is a Gecko static pref with default `false`, compiled into libxul by `canvas-webgl-permissions.patch` (S14). The Firefox 158 default flips Redoubt overrides are still pinned in the cfg: `heuristic.navigation` and `heuristic.recently_visited` false, IP Protection locked off, `network.lna.allow_top_level_navigation` false | `librewolf-cfg.txt`, `librewolf-cfg-vs-beta1.txt` |
| S7 | Update-check key and endpoint in the dex | **PASS.** In all four APKs, `classes2.dex` carries the committed key (`8e714075…7de8`) once, `https://redoubtbrowser.org/update/android/latest.json` once, and `Redoubt-UpdateCheck/1`. There is no old `/updates/android/` path | `update-check-static.txt` |
| S10 | Build ID and diff | `MOZ_APP_VERSION 158.0-1`, `MOZ_BUILDID 20261009160000`, `MOZ_UPDATE_CHANNEL default`. Each ABI's `libxul.so` carries the date. Against Beta 1 x86_64: 18 of 3,278 APK entries differ (libxul, libmozglue, the dex files, resources, omni.ja and extension manifests), and 11 of 2,310 omni.ja entries (b4 → RC; among them `AppConstants`, `onecrl.json`, the Remote Settings dump date) | `build-id.txt`, `entries-vs-beta1-x86_64.txt` |
| S11 | Isolation as compiled | **PASS, off.** `dexdump -d` of `GeckoProvider.createRuntime` in all four APKs: `isolatedProcessEnabled` and `appZygoteProcessEnabled` take `v12`, whose last write is `const/4 v12, #int 0`. Same as Beta 1 (reference row). The manifest still declares upstream's isolated services (41 `isolatedProcess=true`, 1 `useAppZygote=true`), as in Beta 1 | `isolation-static.txt` |
| S12 | Store-installer list in the dex | **PASS.** All six `UpdateCheck.STORE_INSTALLERS` names, once in each APK | `store-installers-static.txt` |
| **S14** | **LW-M7-46 compiled in** | **PASS.** `librewolf.webgl.prompt.notice` once in each ABI's `libxul.so` (Beta 1: 0) and once in each APK's `classes2.dex` (`QUIET_NOTICE_PREF`). The snackbar string is still in the resources (1); it is gated by the pref, not removed | `webgl-notice-static.txt` |

## Device

PASS = passed. E12 = red as expected under E12. NEG = a negative control that must fail and did.
HL = harness limit (see "Harness limits"); no product finding.

| # | Check | API | Exit | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `--check-launcher-start` | 34 | 0 | **PASS** | `device-api34/smoke/check-launcher-start/` |
| 2 | `--check-aboutconfig` | 34 | 0 | **PASS.** 30 rows, the edit survived a restart, 52 prefs locked | `…/check-aboutconfig/` |
| 2a | about:config CSP probe | 34 | 0 | **PASS.** 0 CSP errors from about:config; the positive control was seen in the console | `device-api34/aboutconfig-csp/` |
| 3 | `--check-ubo-preinstall` | 34 | 0 | **PASS**, 2/2 | `…/check-ubo-preinstall/` |
| 4 | `--check-ubo-lifecycle` | 34 | 0 | **PASS**, 10/10 | `…/check-ubo-lifecycle/` |
| 4a | `--check-ubo-user-disable` | 34 | 0 | **PASS**, 3/3 | `…/check-ubo-user-disable/` |
| 5 | `--check-ubo` | 34 | 0 | **PASS** | `…/check-ubo/` |
| 6 | `--check-search` | 34 | 0 | **PASS.** noai.duckduckgo.com with no partner parameter; 4 engines, default DuckDuckGo No-AI | `…/check-search/` |
| 7 | `--check-no-suggest` | 34 | 0 | **PASS.** 60 s typing window: 5 keep-alive, 3 background flows, no new connection, no DNS query. Enter sent 9,213 B to noai.duckduckgo.com | `…/check-no-suggest/` |
| 7a | `--check-no-suggest --no-suggest-negative-control` | 34 | 1 | **NEG, as expected.** Caught `ac.duckduckgo.com` on 5 connections | `…/check-no-suggest-negative-control/` |
| **8** | **baseline, with full graphics acceptance (no-snackbar assertion)** | 30 | 0 | **PASS**, 10/10, including `video-h264` and `video-mse`. Graphics `acceptanceComplete: true`, **162/162**, including `quiet-no-notice` and `no-quiet-notice-in-normal-and-private-tabs` (190 normal-tab and 28 private-tab dumps, no notice in any) | `device-api30/smoke/baseline-smoke/` |
| 8′ | baseline | 34 | 2, then 1 | **HL.** First run: harness error before any check ("initial browser document did not finish loading before about:config", `about:blank`). Re-run on the same emulator after batch 3 (`baseline-smoke-rerun`): every row passes except `webgl`, "No org.redoubtbrowser window is in the input dispatcher's window list", the parser limit Beta 1 also had. Pref dump: 59 prefs, `librewolf.webgl.prompt.notice false` | `device-api34/smoke/baseline-smoke/`, `…/baseline-smoke-rerun/` |
| 9 | `--check-update-privacy` | 30 | 1 | **HL, analysed: no extra host.** OFF half clean. ON half: the update host was contacted (SNI `redoubtbrowser.org` on `185.199.109.153`); the only flagged flow is `tcp 2606:50c0:8000::153:443 (no name)`, a single SYN with 0 payload bytes sent 0.6 ms before the IPv4 SYN to `185.199.109.153` (Happy Eyeballs). `2606:50c0:8000::153` is one of redoubtbrowser.org's own AAAA records (`dig AAAA redoubtbrowser.org @9.9.9.9`: `2606:50c0:8000…8003::153`). This is Beta 1's row 9′, now seen on API 30 too | `device-api30/smoke/check-update-privacy/` (`on_window_flows`), `device-api30/update-privacy-ipv6-analysis.txt` |
| 9″ | `--check-update-privacy` re-run | 30 | 1 | **Not graded (invalid run).** Started 15 s after an emulator of another session (`-avd iso34`, port 5590) had booted on this host, so two emulators ran at once; the run was stopped and its emulator killed. In its ON window no update-host event was seen ("the check did not run"). Its boot also replaced the capture of row 9, so row 9's analysis file was written before it. Rows 9, 9′ and 9a show the check running | `device-api30/smoke/check-update-privacy-rerun/` |
| 9′ | `--check-update-privacy` | 34 | 1 | **HL, the same IPv6 SYN pattern** (`tcp 2606:50c0:8003::153:443 (no name)`, 0 payload bytes) | `device-api34/smoke/check-update-privacy/` |
| **9a** | **update-check probe, live endpoint** | 34 | 0 | **PASS.** After the tap, `pref_key_lw_update_check=true`. The next resume made `GET …/update/android/latest.json` → **200** and `GET …/latest.json.sig` → **200**. The live document is the owner-signed **157.0-3** document (`version_code` 2016188744, sha256 `badc082e…f282`), older than the beta. **Nothing was offered:** no dialog, `lw_update_check.xml` holds only `last_run_ms`, the app alive. Request headers: `Host`, `User-Agent: Redoubt-UpdateCheck/1`, `Accept-Encoding`, `Sec-GPC`, `Connection` (+ `Sec-Fetch-*` at connect); **no `Accept-Language`**, no cookie; `LOAD_ANONYMOUS` and `LOAD_BYPASS_CACHE`. A second resume within 24 h: 0 requests. OFF half: 0 requests, no `lw_update_check.xml`. Control: 6 new records. Host side, `update-manifest.py verify` on the same document: signature OK, "up to date" for all four Beta 2 codes and for Beta 1's 2016188910, "update offered" for 157.0-2's 2016188486 (control) | `device-api34/update-check-live/`, `update-check/live-document-verdicts.txt` |
| 9b | wrongly signed document, on the device | 34 | 0 | **PASS.** The local endpoint served the throwaway-key document (`157.0-99`, `version_code` 2016189999). Both files fetched with 200; **nothing was offered**, only `last_run_ms`, the app alive | `device-api34/update-check-local/` |
| ST | store installer hides the check | 34 | 0 | **PASS.** As in Beta 1: hand install shows the row; `pm install -r -i org.fdroid.fdroid` hides it with 0 requests; `adb install -r` brings it back ON; the control made `GET latest.json` and `.sig` with no `Accept-Language` | `device-api34/store-installer/` |
| P | process labels | 34 | 0 | **PASS.** Parent, `:gpu…` and `:tab_disable_art_image_N` processes all `u:r:untrusted_app:…` under uid 10192; no `isolated_app` process | `device-api34/process-labels/` |
| V | `--check-video` | 34 | 0 | **PASS**, 3/3: VP8/Opus 13 frames; H.264+AAC 13 frames; MSE `avc1.42E01E,mp4a.40.2` 11 frames | `…/check-video/` |
| DQ | `--check-delete-on-quit` | 34 | 0 | **PASS.** "recents swipe then cold start: setting on deleted the saved tabs before restore, setting off restored them" | `…/check-delete-on-quit/` |
| AF | shadow-DOM autofill (LW-M7-42 pages, probe service) | 34 | 0 | **PASS**, the same as Beta 1: `shadow-email-only` 0, `shadow-nonlogin` 0, `shadow-closed` 0, `shadow-open` **1** (3 EditText), `plain` **1** (2 EditText), `shadow-email-only` again 0 | `device-api34/autofill/` |
| **W** | **manual WebGL page** (`webgl-manual.py`, LW-M7-46's pages) | 30 | 0 | **PASS.** Fresh install. `http://127.0.0.1:8466/webgl.html`: 6 dumps over 6 s, page `webgl=NULL webgl2=NULL`, **no notice** in any. Site controls → *Canvas and WebGL permissions* → the pending WebGL row → Allow (session): the list shows "WebGL — http://127.0.0.1:8466 / Allowed · This browser session"; after the reload `webgl=CONTEXT webgl2=CONTEXT` (readback randomized, `pixel=47,184,63,104`), no notice. `http://localhost:8466/canvas.html`: `readback=PROTECTED`, no notice. 32 UI dumps were checked for the notice, none showed it | `device-api30/webgl-manual/` (`0012-webgl-blocked-6s.png`, `0023-after-allow.png`, `0035-webgl-allowed-6s.png`) |
| 10 | `--check-https-only` | 34 | 0 | **PASS**, 3/3 | `…/check-https-only/` |
| 11 | `--check-no-gms --check-no-adjust` | 30 | 0 | **PASS**, 12/12, including a **second full graphics acceptance**, 162/162 (190 normal, 28 private dumps, no notice) | `device-api30/smoke/static-no-gms-no-adjust/` |
| 11′ | the same | 34 | 1 | **HL.** `check-no-gms` and `check-no-adjust` PASS; `webgl` fails as in 8′ | `device-api34/smoke/static-no-gms-no-adjust/` |
| 12 | `--check-strings` | 34 | 0 | **PASS.** 244,495 resource rows, 0 unexplained; 35 screen stops, 0 branded strings shipped | `…/check-strings/` |
| 13 | `--self-test` | 34 | 0 | **PASS** (`SELF-TEST OK`) | `…/self-test/` |
| 14 | `--first-run-capture` | 30 | 1 | **E12.** 83 events, app UID rx +23,375,565 B / tx +470,156 B. Compared with Beta 1 below | `device-api30/smoke/first-run-capture/`, `device-api30/first-run-host-comparison.json` |
| 14′ | `--first-run-capture` | 34 | 1 | **E12.** 108 events, rx +21,330,089 B / tx +419,430 B (Wi-Fi off; not compared) | `device-api34/smoke/first-run-capture/` |
| 15 | `--check-no-remote-settings` | 34 | 1 | **E12.** The same 3 Remote Settings hosts as before | `…/check-no-remote-settings/` |
| 16 | pref audit | 34 | 0, 0 | **PASS.** Fresh `--pref-dump`: `baseline-diff.out` empty against the committed `expected-prefs.txt`, which has `librewolf.webgl.prompt.notice bool false` since LW-M7-46. Audit: 0 violations, 0 non-must-lock diffs | `device-api34/pref-audit/` |
| **17** | **upgrade Beta 1 → Beta 2** (`adb install -r`) | 34 | 0 | **PASS.** Details below | `device-api34/upgrade-from-beta1/` |
| **18** | **upgrade 157.0-3 → Beta 2** (`adb install -r`) | 34 | 0 | **PASS.** Details below | `device-api34/upgrade-from-157.0-3/` |

**First-run hosts compared with Beta 1's capture** (both android-30 `default`):
- **Counts.** 83 events here; Beta 1's capture had 91.
- **Named hosts.** One added, none gone: `curbengh.github.io`, a uBO filter-list mirror that is in the pinned catalog `assets/uBOAssets.android.json` (urlhaus and phishing filters); the 153.4.0esr acceptance saw it too.
- **Unnamed destinations.** The new ones are `2606:50c0:8001::154`, `2606:50c0:8002::153` and `2606:50c0:8003::154`, in GitHub's range (inferred from the prefix), as before.
- **No `redoubtbrowser.org`.** The switch is off by default.

## Upgrades: Beta 1 → Beta 2 and 157.0-3 → Beta 2, update check ON

`scripts/upgrade-test.py`, three phases on one profile, once per source.

**A. Source on a fresh install** (Beta 1 2016188910 `158.0b4-1` / `20261007050000`; 157.0-3 2016188750 `157.0-3` / `20261006090000`). Launcher start and the uBO sheet; search suggestions ON; DNS over HTTPS **Max Protection**; **Check for updates ON** through the Settings row; https://example.org/ bookmarked; "Dan Pollock's hosts file" (`dpollock-0`) ticked in uBO and applied.

**B. Upgrade.** `adb install -r` (no `-d`, no uninstall): `Success`, versionCode → **2016189382**, versionName `158.0-1-default`, same signer, same `firstInstallTime`. Two launcher launches, each 45 s: alive, no alert dialog, no suspicious label, empty crash buffer, no FATAL lines.

**C. Read back** (both upgrades the same): suggestions ON; DoH "Max Protection", `network.trr.mode=3`, `uri=https://dns10.quad9.net/dns-query`; bookmark present; uBO 1.75.0 active, AMO-signed, `selectedFilterLists` identical to phase A's (`dpollock-0` included); `appinfo` 158.0-1 / `20261009160000`; **update check row present and still ON** (`pref_key_lw_update_check=true`, `lw_update_check.xml` keeps `last_run_ms`).

## Harness limits (no product finding)

1. **Packet capture over Wi-Fi (API 34).** Handled as in Beta 1: Wi-Fi off before batch 2.
2. **Graphics parser (API 34).** `android-graphics-smoke.py` reads API 30's `dumpsys input` window
   format; on API 34 the `webgl` row fails before any GL check (rows 8′, 11′). The graphics
   acceptance and the manual WebGL page ran on API 30 (rows 8, 11, W).
3. **Update privacy and IPv6.** The grader names a flow by SNI or by a DNS answer it sees; a
   SYN-only IPv6 attempt to the update host's own AAAA has neither (rows 9, 9′). Beta 1 saw this
   only on API 34; here it happened on both images. Fixing the grader is not part of this
   acceptance.

## Run notes

- **First drive attempt (no device touched).** The first start of `drive.sh` failed at once
  because `apk/output-metadata.json` was missing (`check-launcher-start` exit 2, "cannot determine
  the applicationId"), and the batches then ran with an empty serial for a few seconds. They
  reached no device: every adb command failed to parse ("unknown command"), and the one probe
  still waiting ("waiting for device", with a path as its serial) was killed. The run directory
  was deleted and the drive started again from the beginning; all rows above are from that second
  start. The batch scripts now stop when they find no `emulator-*` serial.
- **Box B start.** The on-demand poller on box A could not start box B's VM: its SSH session on
  box B gets no `XDG_RUNTIME_DIR`, because logind there lists 8,192 sessions, almost all
  `background` sessions of the other project's CI accounts. The VM was started (and stopped after
  the run) by calling `boxb-ctl.sh start` / `stop` with `XDG_RUNTIME_DIR=/run/user/1000`; the
  memory gate passed (room 35,593 MiB, need 26,112 MiB). Nothing of the other project was touched.

## Signing bundle

`~/redoubt-artifacts/beta-158.0-1-b2/signing-bundle/` (not in the repository), laid out like
Beta 1's **without** `update/`:
- the four unsigned APKs and `SHA256SUMS` (the CI file, unchanged; `sha256sum -c` OK);
- `sign.sh` (`86c925e1…5888`), `android-verify-signature.sh` (`8a251c45…a483`), `apksigner.jar`
  (36.0.0, `3716d931…3dec`) and `SIGNING.md` (`dc0b9e54…3f35`), byte-equal to Beta 1's and
  157.0-3's bundles (`SHA256SUMS.tools` is identical).

## Not covered

- **Physical devices and other ABIs.** Only x86_64 ran on a device; arm64-v8a and armeabi-v7a
  were checked statically.
- **Real password managers and reddit.com/login.** Autofill ran with the probe service and local
  pages only.
- **`librewolf.webgl.prompt.notice=true`** (the snackbar turned back on in about:config) was not
  tried on the device; LW-M7-46 covers it by unit test only.
- **The 157.0-1 probes** and the LW-M7-45 multi-task cases (PWA, custom tab) were not repeated.
- **Owner-key signature.** Nothing was signed with a release key.
