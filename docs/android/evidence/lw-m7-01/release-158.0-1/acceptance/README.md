# 158.0-1 (Firefox 158.0): acceptance of CI run 38432799414, 2026-10-13: **PASS**

**Result: the payload PASSES acceptance and may go to the owner for signing.** After signing it
is published as the new **Latest** stable, over 157.0.1-1. Owner go on 2026-10-13, verbatim:
"yes GO". The build configuration is in
[`../../release-158.0/release-day/`](../../release-158.0/release-day/README.md).

The source is Mozilla's official `releases/158.0` tarball. It is byte-identical to the RC build2
tarball that Beta 2 was built from. Against Beta 2, the build differs only where the build date
goes:
- 11 of 3,278 x86_64 APK entries differ;
- in omni.ja, only `modules/AppConstants.sys.mjs` differs;
- the packaged `librewolf.cfg` is byte-identical.

What the device runs showed:
- **Every Beta 2 row passes again.** The API 34 harness limits are the same.
- **Three new checks pass:** `--check-tls-floor`, `--check-revocation` and
  `--check-rfp-coherence` (LW-M7-49, merged into main with the 158 rebase).
- **WebGL notice (LW-M7-46).** With the no-snackbar assertion, the graphics acceptance passes
  **162/162** twice on API 30. The manual WebGL page shows no notice, and Allow still enables
  WebGL.
- **Shadow-DOM autofill (LW-M7-42).** The probe-service pages give the same counts as Betas 1
  and 2.
- **Upgrades keep the data.** 157.0.1-1 → 158.0-1 and Beta 2 → 158.0-1 with `adb install -r`
  keep it, including the update-check switch.
- **Update check.** It fetches the live, owner-signed **157.0.1-1** document, which is older than
  this build, and offers nothing.
- **The new update document** (signing bundle) offers 158.0-1 to 157.0.1-1, Beta 1 and Beta 2,
  and "up to date" to 158.0-1 itself (host side, throwaway key).

No product defect was found. One known site limit is still there: a direct load of
reddit.com/login on a fresh profile stays blank. It is not new; 157.0.1-1 does the same. See row
RD.

## What was tested

| | |
| --- | --- |
| CI run | <https://github.com/CPlusPlus17/Redoubt/actions/runs/38432799414>, "Android release (unsigned artifacts only)" (`android-release.yaml`), `workflow_dispatch` on `main`, job `build-unsigned` on box B, 16:43:15-18:34:27 UTC, conclusion `success` (`ci/run.json`, `ci/run.log.gz`).<br>Inputs from the log: `MODE: full`, `UPDATE_CHECK: true`, `BUILD_DATE_IN: 20261013160000`, `BUNDLE: false`.<br>The log shows the tarball fetched from `releases/158.0/source/` and its `.asc` checked against the pinned key (`VALIDSIG … 14F26682D0916CDD81E37B6D61B7B526D98F0353`). |
| headSha (`gh run view --json headSha`) | `cc65058138e8f2f4836ed71f57e2044ac389bbb1`, which equals `git rev-parse origin/main` and is the commit this acceptance branch starts from. Settings gitlink `008b87fddb0fb12084690a40127454a23b8e2e5c`, the same as Beta 2 and 157.0.1-1 |
| CI gates (log) | All four APKs unsigned (no v1 block, no v2/v3 block); `versionName ['158.0-1-default'] versionCodes [2016190144, 2016190146, 2016190150, 2016190151]`; `OK: MOZ_BUILD_DATE 20261013160000`; update check compiled in for all four |
| Artifact | `redoubt-android-unsigned`, 624,013,934 bytes, digest `sha256:53a0c58c96e1c1a2f4c6024341524121ad5ba58d0694c4bec43b3d95b8671376` (`ci/artifacts.json`). `sha256sum -c SHA256SUMS`: all four OK (`ci/SHA256SUMS.check.txt`) |
| Artifact SHA256SUMS | arm64-v8a `9f2fb9ea738a28cc2bfd109b3b23c6a8f2dea55027bb57bb90f26abb4782902a`<br>armeabi-v7a `140dd4e7a33becc12f6f703e9c93915da4baad657626878e028e549df2746255`<br>universal `178b18ecd7b79e2567651269177cd82c5457a80ffd9c94dab7b9a2357ed17ac2`<br>x86_64 `ad72ece6bd1237235c6770fcef7ff3ac99688a18c30eff544b8ea4de129cffb2` |
| Installed (x86_64) | `c91d7fa972ba2c27f8eb4460a310357b56960e5d750ee98a15a0f1e69b67afb5`, signed with the **throwaway** key (`keep/throwaway-keys/throwaway.p12`, cert `31e9a40f…b760`, `CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, apksigner 36.0.0), not the release key. All 3,278 entries other than the signature files equal the unsigned APK's (`device-api34/apk-identity.txt`). Every harness run recorded this hash (`*/smoke/exit-status.jsonl`) |
| Upgrade sources | 157.0.1-1, throwaway-signed `22d15fdd91c6b063c807816f4941f9a2f9d2508a8378df581171b9ce1d67d153`, and Beta 2, throwaway-signed `295022296a3586e13efca91b09bd887fa36f90f96ac7ac9d5ee5501c883f344a`. Both are the same files as in their own acceptances, with the same cert |
| `scripts/android-smoke.sh` / `android-graphics-smoke.py` | `a062f091…3a03` / `415c7254…ecd3` at `cc650581`. The smoke harness gained LW-M7-49's three checks since Beta 2; the graphics harness is unchanged. Every harness run recorded HEAD `cc650581` and 0 uncommitted changes under `scripts/` |
| Runner and probes | `scripts/`, copied from the Beta 2 acceptance with paths changed.<br>**Changed:** `batch2.sh` adds `--check-tls-floor`, `--check-revocation` and `--check-rfp-coherence`. `batch3.sh` upgrades from 157.0.1-1 and Beta 2. `static-checks.sh` compares with Beta 2. `drive-api30.sh` adds `--check-no-suggest`, as in 157.0.1-1.<br>**New:** `reddit-cold.sh` and `reddit-warm.sh` (row RD) |

**Conditions.**
- **Main session (`device-api34/`).** API 34 `google_apis` x86_64 (emulator-5584). The harness
  booted it from the android-34-only SDK view with `-dns-server 9.9.9.9 -tcpdump`, and every
  later step reused it with `--serial`.
  - Every check started from a fresh profile, except the upgrades, which keep their profile on
    purpose.
  - Logcat was streamed for every harness run.
  - **Wi-Fi was switched off** at the start of batch 2, as in Beta 2.
- **Second session (`device-api30/`).** android-30 `default` x86_64 (no GMS, emulator-5582,
  `generic_x86_64:11/RSR1.210722.013.A2`). It started after the API 34 emulator was shut down, so
  only one emulator ran at a time.
- **Other devices.** Physical devices were attached to the host over adb. Every command named the
  emulator's serial, and nothing touched them.

## Static (`static/`)

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| S1 | versionName / versionCodes | **PASS.** `158.0-1-default` in all four APKs. Codes: v7a **2016190144**, arm64 **2016190146**, x86_64 **2016190150**, universal **2016190151**. All are above Beta 2's highest (2016189383), Beta 1's (2016188911) and 157.0.1-1's (2016188823). They match `android-aab.py versioncode` for 20261013160000 (release-day README). Label `Redoubt`, package `org.redoubtbrowser`, targetSdk 37 | `apk-badging.txt` |
| S2 | ELF per ABI | **PASS.** Each split APK carries only its own ABI's ELF: 14 shared objects + 1 PIE. The universal APK has all three ABIs | `elf-per-abi.txt` |
| S3 | Unsigned | **PASS.** 0 META-INF signature files; `apksigner verify` exits 1 for all four | `unsigned.txt` |
| S4 | Branding | **PASS.** omni.ja brand files and branding PNGs are byte-equal to Beta 2's; omni.ja is identical in all four APKs | `omni-branding.txt` |
| S5 | uBO | **PASS.** `ublock_origin.xpi` 1.75.0, sha256 `5b744158…5287` = the pin, AMO-signed, in all four | `ubo-and-omni.txt` |
| S6 | Packaged `librewolf.cfg` | **PASS, identical.** sha256 `73dc32beb523be4f184164e5819abbc54c00ad3905e14ca6bc79510a5b29f53c` in all four APKs, byte-equal to `settings/common.cfg + settings/android.cfg` at `008b87f` **and byte-equal to Beta 2's packaged cfg**, so the diff is empty (the gitlink did not move). It is also 157.0.1-1's cfg hash. The Firefox 158 overrides are still in it: `heuristic.navigation` and `heuristic.recently_visited` false, IP Protection locked off, `network.lna.allow_top_level_navigation` false | `librewolf-cfg.txt`, `librewolf-cfg-vs-beta2.txt` |
| S7 | Update-check key and endpoint in the dex | **PASS.** `classes2.dex` of all four APKs: committed key (`8e714075…7de8`) once, `https://redoubtbrowser.org/update/android/latest.json` once, `Redoubt-UpdateCheck/1` once, no `/updates/android/` | `update-check-static.txt` |
| S8 | `android-cookie-banner-smoke.py --apk --fetch` | **PASS** on x86_64 and universal (exit 0, 0) | `cookie-lists-apk-*.out` |
| S10 | Build ID and diff | `MOZ_APP_VERSION 158.0-1`, `MOZ_BUILDID 20261013160000`, `MOZ_UPDATE_CHANNEL default`; each ABI's `libxul.so` carries the date. **Against Beta 2 x86_64: 11 of 3,278 APK entries differ** (`AndroidManifest.xml`, `baseline.prof`, five built-in extension manifests, `omni.ja`, `classes2.dex`, `libmozglue.so`, `libxul.so`), and **1 of 2,310 omni.ja entries** (`modules/AppConstants.sys.mjs`). That is the profile of a rebuild of the same source with a new build date | `build-id.txt`, `entries-vs-beta2-x86_64.txt` |
| S11 | Isolation as compiled | **PASS, off.** `GeckoProvider.createRuntime` in all four APKs: `isolatedProcessEnabled` and `appZygoteProcessEnabled` take `v12`, last written by `const/4 v12, #int 0`. Same as Beta 2. 158.0-1 has no isolation work (that is 158.0-2) | `isolation-static.txt` |
| S12 | Store-installer list in the dex | **PASS.** All six names, once in each APK | `store-installers-static.txt` |
| S14 | LW-M7-46 compiled in | **PASS.** `librewolf.webgl.prompt.notice` once in each ABI's `libxul.so` and once in each APK's `classes2.dex` | `webgl-notice-static.txt` |

## Device

PASS = passed. E12 = red, as expected under E12. NEG = a negative control that must fail, and did.
HL = a harness limit (see "Harness limits"); no product finding.

| # | Check | API | Exit | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `--check-launcher-start` | 34 | 0 | **PASS** | `device-api34/smoke/check-launcher-start/` |
| 2 | `--check-aboutconfig` | 34 | 0 | **PASS.** 30 rows; the edit survived a restart; 52 prefs locked | `…/check-aboutconfig/` |
| 2a | about:config CSP probe | 34 | 0 | **PASS.** 0 CSP lines from about:config; the control marker was seen | `device-api34/aboutconfig-csp/` |
| 3 | `--check-ubo-preinstall` | 34 | 0 | **PASS**, 2/2 | `…/check-ubo-preinstall/` |
| 4 | `--check-ubo-lifecycle` | 34 | 0 | **PASS**, 10/10 | `…/check-ubo-lifecycle/` |
| 4a | `--check-ubo-user-disable` | 34 | 0 | **PASS**, 3/3 | `…/check-ubo-user-disable/` |
| 5 | `--check-ubo` | 34 | 0 | **PASS** | `…/check-ubo/` |
| 6 | `--check-search` | 34 | 0 | **PASS.** noai.duckduckgo.com with no partner parameter; 4 engines | `…/check-search/` |
| 7 | `--check-no-suggest` | 30 | 0 | **PASS.** 60 s typing window: no new connection, no DNS query, 8 keep-alive, 3 background flows. Enter sent 9,223 B to noai.duckduckgo.com | `device-api30/smoke/check-no-suggest/` |
| 7′ | `--check-no-suggest` | 34 | 1 | **HL.** The only flagged flow is the OS's own `www.google.com` connection (210 B) in the typing window. Redoubt has no Google endpoint; the google_apis image does. This is 157.0.1-1's row 7′; row 7 grades the check on the no-GMS image | `device-api34/smoke/check-no-suggest/` |
| 7a | `--check-no-suggest --no-suggest-negative-control` | 34 | 1 | **NEG, as expected.** Caught `ac.duckduckgo.com` on 5 connections | `…/check-no-suggest-negative-control/` |
| **8** | **baseline, with full graphics acceptance (no-snackbar assertion)** | 30 | 0 | **PASS**, 10/10, including `video-h264` and `video-mse`. Graphics `acceptanceComplete: true`, **162/162**, including `quiet-no-notice` and `no-quiet-notice-in-normal-and-private-tabs` (190 normal-tab and 28 private-tab dumps, no notice in any) | `device-api30/smoke/baseline-smoke/` |
| 8′ | baseline | 34 | 1 | **HL.** Every row passes except `webgl` ("No org.redoubtbrowser window is in the input dispatcher's window list"), as in Beta 2 | `device-api34/smoke/baseline-smoke/` |
| 9 | `--check-update-privacy` | 34 | 0 | **PASS.** OFF by default, with no update-host traffic across launch and Settings (145 app events). Switched ON through the UI, the update host was contacted on relaunch and nothing else new | `device-api34/smoke/check-update-privacy/` |
| 9′ | `--check-update-privacy` | 30 | 1 | **HL, analysed: no extra host.** The only flagged flow is `tcp 2606:50c0:8003::153:443 (no name)`, with 0 payload bytes. It is a single SYN sent 4.7 ms before the IPv4 SYN to `185.199.108.153`, whose SNI is `redoubtbrowser.org` (Happy Eyeballs). `2606:50c0:8003::153` is one of redoubtbrowser.org's own AAAA records. This is Beta 2's row 9 | `device-api30/smoke/check-update-privacy/`, `device-api30/update-privacy-ipv6-analysis.txt` |
| **9a** | **update-check probe, live endpoint** | 34 | 0 | **PASS.** After the tap, `pref_key_lw_update_check=true`. The next resume made `GET …/update/android/latest.json` → **200**, then `GET …/latest.json.sig` → **200**. The live document is the owner-signed **157.0.1-1** document (`version_code` 2016188816, sha256 `2d0ea871…efe1` = `site/update/android/latest.json` on main), which is older than this build. **Nothing was offered:** no dialog, `lw_update_check.xml` holds only `last_run_ms`, and the app was alive.<br>Request headers: `Host`, `User-Agent: Redoubt-UpdateCheck/1`, `Accept-Encoding`, `Sec-GPC`, `Connection`, plus `Sec-Fetch-*` at connect. **No `Accept-Language`**, no cookie; load flags 16896.<br>A second resume made 0 requests. OFF half: 0 requests and no `lw_update_check.xml`. Control: 6 new records.<br>Host side: `update-manifest.py fetch` of the live document gives signature OK and "up to date" for 2016190144, 2016190150 and Beta 2's 2016189382 | `device-api34/update-check-live/`, `update-check/live-document-verdicts.txt`, `update-check/live-latest.json{,.sig}` |
| 9b | wrongly signed document, on the device | 34 | 0 | **PASS (re-run).** The local TLS endpoint served the throwaway-key document (`157.0-99`, 2016189999). The server log shows both files fetched (`server-requests.jsonl`, 2 GETs) and Gecko saw 200 for both. Nothing was offered, only `last_run_ms` was written, and the app stayed alive. See "Run notes" for the first attempt | `device-api34/update-check-local-rerun/` (first attempt: `device-api34/update-check-local/`) |
| ST | store installer hides the check | 34 | 0 | **PASS.** (2) With `installerPackageName=org.fdroid.fdroid` and the stored value `true`, **the row is absent** and **0 requests** were made. (3) After an `adb install -r` the row is back and ON, and the control made both GETs with no `Accept-Language` | `device-api34/store-installer/` |
| P | process labels | 34 | 0 | **PASS.** The parent, `:gpu…` and four `:tab_disable_art_image_N` processes are all `u:r:untrusted_app:…` under uid 10192. No `isolated_app` process | `device-api34/process-labels/` |
| V | `--check-video` | 34 | 0 | **PASS**, 3/3: VP8/Opus 13 frames, H.264+AAC 14 frames, MSE 8 frames (and in rows 8 and 11 on API 30) | `…/check-video/` |
| DQ | `--check-delete-on-quit` | 34 | 0 | **PASS.** "recents swipe then cold start: setting on deleted the saved tabs before restore, setting off restored them" | `…/check-delete-on-quit/` |
| 10 | `--check-https-only` | 34 | 0 | **PASS**, 5/5. This includes the LW-M7-49 rows `https-only-upgrade` and `https-only-exception-scope`: the exception is session-scoped (`expireType=1`), and another port still gets the interstitial | `…/check-https-only/` |
| **TLS** | **`--check-tls-floor`** (LW-M7-49) | 34 | 0 | **PASS.** TLS 1.0 and 1.1 refused (`SSL_ERROR_PROTOCOL_VERSION_ALERT`), 1.2 and 1.3 connect; `security.tls.version.min=3` | `…/check-tls-floor/` |
| **RV** | **`--check-revocation`** (LW-M7-49) | 34 | 0 | **PASS.**<br>`revocation-ocsp-off`: `OCSP.enabled=0`, `crlite_mode=2`, 0 OCSP requests.<br>`revocation-stapled`: a stapled "revoked" response is refused with `SEC_ERROR_REVOKED_CERTIFICATE`.<br>`revocation-observed` (recorded only, not graded): must-staple without a staple is refused; no CRLite filters had synced yet in this short run | `…/check-revocation/` |
| **RFP** | **`--check-rfp-coherence`** (LW-M7-49) | 34 | 0 | **PASS**, 17/17 coherence items (RFP on; device time zone Europe/Zurich) | `…/check-rfp-coherence/` |
| AF | shadow-DOM autofill (LW-M7-42 pages, probe service) | 34 | 0 | **PASS**, the same as Betas 1 and 2. Fill requests per page: `shadow-email-only` 0, `shadow-nonlogin` 0, `shadow-closed` 0, `shadow-open` **1** (3 EditText), `plain` **1** (2 EditText), `shadow-email-only` again 0 | `device-api34/autofill/` |
| **RD** | **reddit.com/login on a fresh profile** (`reddit-cold.sh`, `reddit-warm.sh`, new, diagnostic) | 34 | 0 | **Known limit, still there, not new.**<br>A first start straight into `https://www.reddit.com/login/` stays blank at 30 s and 60 s. The UI dump holds only the title "Welcome to Reddit".<br>`https://www.reddit.com/` renders.<br>In both scripts, opening the login URL afterwards (a new tab, 30 s and 90 s after reddit.com/ had rendered) **also** stayed blank, so the workaround recorded in LW-M7-42 ("open reddit.com first") was **not** confirmed here.<br>**157.0.1-1 contrast:** `reddit-warm.sh` with the 157.0.1-1 APK on the same emulator gives the same result (blank), so this is not a regression of 158.0-1. The app stayed alive with an empty crash buffer in all three runs | `device-api34/reddit-cold/`, `reddit-warm/`, `reddit-warm-157.0.1-1/` |
| 11 | `--check-no-gms --check-no-adjust` | 30 | 0 | **PASS**, 12/12, including a **second full graphics acceptance**, 162/162 | `device-api30/smoke/static-no-gms-no-adjust/` |
| 11′ | the same | 34 | 1 | **HL.** `check-no-gms` and `check-no-adjust` pass; only `webgl` fails, as in 8′ | `device-api34/smoke/static-no-gms-no-adjust/` |
| **W** | **manual WebGL page** (`webgl-manual.py`) | 30 | 0 | **PASS.**<br>Fresh install. `http://127.0.0.1:8466/webgl.html` reads `webgl=NULL webgl2=NULL`, with no notice in 6 dumps.<br>Site controls → *Canvas and WebGL permissions* → Allow (session): the list shows "WebGL — http://127.0.0.1:8466 / Allowed · This browser session". After the reload the page reads `webgl=CONTEXT webgl2=CONTEXT`, with no notice.<br>`canvas.html` reads `readback=PROTECTED`, with no notice | `device-api30/webgl-manual/` |
| 12 | `--check-strings` | 34 | 0 | **PASS.** 244,495 rows, 0 unexplained; 34 screen stops, 0 branded strings shipped | `…/check-strings/` |
| 13 | `--self-test` | 34 | 0 | **PASS** (`SELF-TEST OK`) | `…/self-test/` |
| 14 | `--first-run-capture` | 30 | 1 | **E12.** 102 events, app UID rx +23,647,460 B / tx +438,417 B. Compared with Beta 2 below | `device-api30/smoke/first-run-capture/`, `device-api30/first-run-host-comparison.json` |
| 14′ | `--first-run-capture` | 34 | 1 | **E12.** 123 events, rx +25,589,272 B / tx +407,527 B (Wi-Fi off; not compared) | `device-api34/smoke/first-run-capture/` |
| 15 | `--check-no-remote-settings` | 34 | 1 | **E12.** The same 3 Remote Settings hosts as before | `…/check-no-remote-settings/` |
| 16 | pref audit | 34 | 0, 0 | **PASS.** Fresh `--pref-dump`: `baseline-diff.out` empty against the committed `expected-prefs.txt` (`librewolf.webgl.prompt.notice bool false`). Audit: 0 violations, 0 non-must-lock diffs | `device-api34/pref-audit/` |
| **17** | **upgrade 157.0.1-1 → 158.0-1** (`adb install -r`) | 34 | 0 | **PASS.** Details below | `device-api34/upgrade-from-157.0.1-1/` |
| **18** | **upgrade Beta 2 → 158.0-1** (`adb install -r`) | 34 | 0 | **PASS.** Details below | `device-api34/upgrade-from-beta2/` |

**First-run hosts compared with Beta 2's capture** (both on android-30 `default`):
- **Counts.** 102 events here; Beta 2's capture had 83.
- **Named hosts.** One added and one gone, both uBO filter-list mirrors from the pinned catalog
  `assets/uBOAssets.android.json`:
  - added: `cdn.jsdelivr.net`, which the catalog names 30 times and 157.0.1-1's first run also
    contacted;
  - gone: `curbengh.github.io`.
  uBO picks among the mirrors.
- **Unnamed destinations.** The new ones are in GitHub's (`2606:50c0:…`) and Fastly's
  (`2a04:4e42:…`) ranges, as before; the ranges are inferred from the prefix.
- **No `redoubtbrowser.org`.** The update check is off by default.

## Upgrades: 157.0.1-1 → 158.0-1 and Beta 2 → 158.0-1, update check ON

`scripts/upgrade-test.py` runs three phases on one profile, once per source.

**A. The source on a fresh install** (157.0.1-1 2016188822 `157.0.1-1-default`; Beta 2 2016189382
`158.0-1-default`):
- launcher start, and the uBO sheet acknowledged;
- search suggestions ON;
- DNS over HTTPS **Max Protection**;
- **Check for updates ON** through the Settings row;
- https://example.org/ bookmarked;
- "Dan Pollock's hosts file" (`dpollock-0`) ticked in uBO and applied.

**B. The upgrade.** `adb install -r` (no `-d`, no uninstall) returned `Success`. The versionCode went
to **2016190150** and the versionName is `158.0-1-default`. The signer (`1e14b3e1`) and
`firstInstallTime` did not change. There were two launcher launches of 45 s each: the app was
alive, with no alert dialog, an empty crash buffer and no FATAL lines.

**C. Read back.** Both upgrades gave the same result:
- suggestions ON;
- DoH "Max Protection", `network.trr.mode=3`, `uri=https://dns10.quad9.net/dns-query`;
- the bookmark is present;
- uBO 1.75.0 is active, with `dpollock-0` still selected;
- `appinfo` reads 158.0-1 / `20261013160000`;
- **the update-check row is present and still ON**;
- `state-A-final.json` and `state-C-after-upgrade.json` differ only in `appinfo`/TRR `buildID`
  (and the version, for 157.0.1-1).

Beta 2 and this build share the versionName; Android installs this one over Beta 2 because its
versionCode is higher.

## Harness limits (no product finding)

1. **Graphics parser (API 34)** (rows 8′, 11′). The graphics acceptance and the manual WebGL page
   ran on API 30.
2. **Update privacy and IPv6** (row 9′). A SYN-only IPv6 attempt to the update host's own AAAA
   record has no name the grader can use.
3. **OS traffic in the typing window (API 34)** (row 7′). Row 7 grades the check on the no-GMS image.

## Run notes

- **Expired test certificate (row 9b).** The first local run (`update-check-local/`) made both
  GETs inside Gecko, but no request reached the local server. The cause: the throwaway CA and
  leaf certificate this probe has used since the 157.0-2 acceptance expired on 2026-10-11
  (`notAfter=Oct 11 23:35:11 2026 GMT`); `curl` on the host failed with "certificate has
  expired".
  - So Gecko refused the TLS connection, and the app offered nothing and stayed alive. That is
    the correct behaviour, but it is not what row 9b tests.
  - A new throwaway CA and leaf (`O=NOT A REAL CA`, valid 14 days) were made in the acceptance
    scratch area. The probe was re-run unchanged (`update-check-local-rerun/`).
  - The public certificates, new and expired, are in `update-check/local-fixture-renewed/`. No
    private key is committed.
- **Box B.** Run 38432799414 was dispatched by the release-day step (see
  `../../release-158.0/release-day/`); this acceptance only read it.

## Update document (host side; nothing was signed with the owner's key)

- **Generated.** `scripts/update-manifest.py generate --tag android-158.0-1` on this run's
  `output-metadata.json` (published `2026-10-13T18:41:29Z`, the generation time). It picks
  `version_code` **2016190144** (the lowest of the four) and the `android-158.0-1` release URLs.
  sha256 **`17cef5557c0b90c708249cc0ad4d36848058f7184e8277eee70d667ee0f36b31`**. It is staged in
  the signing bundle and copied to `update-check/latest.json`.
- **Throwaway-key signature** (`update-check/throwaway-update-test.pubkey`, the 157.0-2 acceptance's
  test key; `update-check/host-verifier.txt`):
  - With the committed key: **REJECTED**, exit 1.
  - With the throwaway key: OK, and the `--metadata` cross-check passes.
  - "Update offered" for 157.0.1-1 (2016188816, …822, …823), Beta 1 (2016188910) and Beta 2
    (2016189376, …382, …383).
  - "Up to date" for this build (2016190144, 2016190150).
  - `sign-update-manifest.sh` refused the throwaway key and wrote no `.sig`.
- **No verification against the owner's key is claimed.** `site/update/` is untouched.

## Signing bundle

`~/redoubt-artifacts/release-158.0-1/signing-bundle/` (not in the repository), laid out like
157.0.1-1's:
- the four unsigned APKs and `SHA256SUMS` (the CI file, unchanged; `sha256sum -c` OK);
- `sign.sh` (`86c925e1…5888`), `android-verify-signature.sh` (`8a251c45…a483`), `apksigner.jar`
  (`3716d931…3dec`) and `SIGNING.md` (`dc0b9e54…3f35`). All are byte-equal to 157.0.1-1's, and
  `SHA256SUMS.tools` is identical;
- `update/`: `latest.json` (`17cef555…6b31`), `sign-update-manifest.sh` (`5e0820f6…b135`),
  `update-check.android.pubkey` (`8e714075…7de8`) and `SHA256SUMS.update`.

## Not covered

- **Physical devices and other ABIs.** Only x86_64 ran on a device; arm64-v8a and armeabi-v7a
  were checked statically.
- **Real password managers.** Autofill ran with the probe service and local pages only. On
  reddit.com/login, autofill was not tried, because the page did not render (row RD).
- **`librewolf.webgl.prompt.notice=true`** was not tried on the device; as in Beta 2.
- **An upgrade directly from Beta 1 or 157.0-3.** Only the codes were checked: all are lower than
  this build's. Beta 2's acceptance covered Beta 1 → Beta 2 and 157.0-3 → Beta 2.
- **Owner-key signatures.** Nothing was signed with a release key.
