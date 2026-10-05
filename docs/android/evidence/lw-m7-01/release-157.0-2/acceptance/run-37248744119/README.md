# 157.0-2: device acceptance of CI run 37248744119 (the rebuild), 2026-10-05: **PASS**

**Result: the payload PASSES acceptance. It may go to the owner for signing.** This is the
rebuild made after the first 157.0-2 build (run 37234607054) was rejected because its update-check
switch was never read ([`../README.md`](../README.md), `DISTRIBUTION.md` "The switch defect").
The fix works on the device:
- turning the switch on in Settings writes `pref_key_lw_update_check=true` to `fenix_preferences.xml`;
- the next resume makes exactly one GET of `https://redoubtbrowser.org/update/android/latest.json`;
- the endpoint returns 404, which gives "no update" with no dialog and no crash;
- turning the switch off stops the requests;
- a wrongly signed document served from a local test endpoint is fetched and rejected.

The upgrade from Beta 5 and the pref audit, both skipped in the rejected run, ran and passed.
No product defect was found.

The harness's own `--check-update-privacy` exits 1 twice, but this is a **harness false positive,
not a product fault**. It compares bare TCP SYN destinations by IP address. Fastly rotates the
Remote Settings CDN's address, and redoubtbrowser.org shares GitHub Pages addresses. The SNI on
every flagged address names a host the check already allows (row 9). The request-level probe
(rows 9a-9c) is the authoritative evidence.

## What was tested

| | |
| --- | --- |
| CI run | <https://github.com/CPlusPlus17/Redoubt/actions/runs/37248744119>, "Android release (unsigned artifacts only)" (`android-release.yaml`), `workflow_dispatch`, job `build-unsigned` on runner `redoubt-ci-boxb`, conclusion `success`. Inputs from the log: `MODE: full`, `UPDATE_CHECK: true`, `BUILD_DATE_IN: 20261005000000` (`ci/run.json`, `ci/run.log.gz`) |
| headSha (from `gh run view --json headSha`) | `27240eb6d0140704f637135c7985c778a9f46e51`. This equals `git rev-parse origin/main` when this branch was cut, and is the commit this branch starts from. It contains the fix `b86c1a0c` (merged in `8280ed84`). Settings gitlink `008b87fddb0fb12084690a40127454a23b8e2e5c` |
| Artifact | `redoubt-android-unsigned`, 616,816,679 bytes, digest `sha256:404eb6093d96cd5b06d5c9b3697710b808d48bd9237176259727002ca04646b4` (`ci/artifacts.json`). `sha256sum -c SHA256SUMS`: all four OK (`ci/SHA256SUMS.check.txt`) |
| Artifact SHA256SUMS | arm64-v8a `1db9bcf7854570908733ea3de45b88f13c572392ba2b959090af8a4806d0c4a1`<br>armeabi-v7a `a959450ff7ed338d4b6162aa32cee8131ef64f834dbe4704178678cd0ce96435`<br>universal `444b4268b33f021820cf126703c837ee076fa38efbd7b0ec93f702769a447c6a`<br>x86_64 `88850c392ff33e462ea0fb39e596534e1bf63b0a14b2944a885790b5aac0591b` |
| Installed (x86_64) | `ee97f58b50789a7dae969785dcef7e6566d58681791c580eb62f82663e9dbfe3`. Signed with the **throwaway** key (cert `31e9a40f…b760`, `CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, v2+v3, apksigner 36.0.0), not the release key. All 3,131 non-META-INF entries equal the unsigned APK's (`device/apk-identity.txt`). Every harness run recorded this hash (`device/smoke/exit-status.jsonl`) |
| Beta 5 (upgrade source) | throwaway-signed `f09c6f4a337d844bea23abfb229f6a44279348134478cb1f65f8b327a5e47ea2`, from unsigned `da72cbbe5d57bc2be0d25aec2032e8282c999292e0befe48ea19d833001768b9` (`keep/beta5-unsigned`). Byte-identical to the signed copies used by the LW-M7-41 candidate and the rejected run |
| `scripts/android-smoke.sh` | `dba0f279e5ca6eec7a51c1ac9d43e320536a88943c7494dca7e33b67a824ce46` (the same as the 157.0-1, Beta 5 and rejected-run acceptances) |
| `scripts/android-graphics-smoke.py` | `ce0072ea63fa3fdd1b183bcab3f7adfed279842c6fe090ef5834eec9e96a4612` (same) |
| `scripts/android-cookie-banner-smoke.py` | `b9c88af618a56d5cb304bd6f1ebd80af9edd1251626d216e49fef4c051a59274` (same) |
| `scripts/update-manifest.py` / `sign-update-manifest.sh` | `deab0f3c…54c7ec` / `5e0820f60ff96b0c5875a0113846ef20c41cb89e7f721a250914b3380193b135` |
| Runner and probes | `scripts/`, copied from the rejected run with paths changed. `update-check-probe.py` gained an OFF half and switch-store reads (commit `6b00f120`), then a free port for the local endpoint (this commit; see 9c). `static-checks.sh` and `batch3.sh` are new. Every harness run recorded HEAD `6b00f120` and 0 uncommitted changes under `scripts/` (`device/smoke/exit-status.jsonl`) |

**Conditions.**
- **Emulator.** One emulator: emulator-5584, android-30 `default` x86_64, no GMS, SwANGLE. The harness booted it with `-dns-server 9.9.9.9 -tcpdump` in the first check. After that it was reused with `--serial`.
- **Network.** AMO was reachable.
- **Profiles.** Every check started from a fresh profile (`pm clear`). The upgrade is the exception: it keeps the profile on purpose.
- **Logging.** Logcat was streamed for every `--serial` run.
- **Other devices.** A second adb device was attached to the host (`10.0.0.156:5555`). Every command named the emulator's serial, so nothing ran on that device.

## Summary

PASS = passed. E12 = red as expected under E12. NEG = a negative control that must fail and did.
H-FP = a harness false positive (explained under the row).

| # | Check | Exit | Result | Evidence |
| --- | --- | --- | --- | --- |
| S1 | versionName / versionCodes | | **PASS.** `157.0-2-default` in all four. Codes: v7a 2016188480, arm64 2016188482, x86_64 2016188486, universal 2016188487. All are above Beta 5's 2016188256-63 and above the rejected run's 2016188448-55. Label `Redoubt`, package `org.redoubtbrowser` | `static/apk-badging.txt` |
| S2 | ELF per ABI | | **PASS.** Each split APK carries only its own ABI's ELF: 14 shared objects + 1 PIE. The universal APK has all three ABIs, each with its `libxul.so` | `static/elf-per-abi.txt` |
| S3 | Unsigned | | **PASS.** 0 META-INF signature files. `apksigner verify` gives "DOES NOT VERIFY / Missing META-INF/MANIFEST.MF", exit 1, for all four | `static/unsigned.txt` |
| S4 | Branding | | **PASS.** omni.ja `brand.ftl` / `brand.properties` say Redoubt. The brand files and the GeckoView branding PNGs are byte-equal to Beta 5's. omni.ja is identical in all four APKs (`46bdecca…b228`) | `static/omni-branding.txt` |
| S5 | uBO | | **PASS.** `ublock_origin.xpi` 1.75.0, sha256 `5b744158…5287` = the `ubo-extension.json` pin, AMO-signed (`META-INF/cose.sig`, `mozilla.rsa`). The same in all four APKs | `static/ubo-and-omni.txt` |
| S6 | Packaged `librewolf.cfg` | | **PASS.** sha256 `73dc32be…f53c`, the same in all four APKs, byte-equal to `settings/common.cfg + settings/android.cfg` at `008b87f`. Contains: the pinned uBO catalog `…/612fac02…/assets/uBOAssets.android.json`; `lockPref browser.ipProtection.enabled false` and `.guardian.endpoint ""`; `network.lna.allow_top_level_navigation false`; `privacy.restrict3rdpartystorage.heuristic.navigation` and `.recently_visited`, both false | `static/librewolf-cfg.txt` |
| S7 | Update-check key and endpoint in the dex | | **PASS.** In all four APKs, `classes2.dex` carries the committed P-256 key `assets/update-check.android.pubkey` (sha256 `8e714075…7de8`) once, `https://redoubtbrowser.org/update/android/latest.json` once, and `Redoubt-UpdateCheck/1`. No old `/updates/android/` path. The Settings row is `android:persistent="false"` in `res/DZ.xml`, as in the fix | `static/update-check-static.txt` |
| S8 | `android-cookie-banner-smoke.py --apk --fetch` | 0 | **PASS**, 5/5 on x86_64 and on universal: catalog, pref, bundled, migration, hosted | `static/cookie-lists-apk-*.out` |
| S9 | `--check-strings --check-no-gms --check-no-adjust` (static) | 0 | **PASS.** 243,650 rows, 0 unexplained | `static/static-strings-nogms-noadjust.*` |
| S10 | Build ID and diff | | `MOZ_BUILDID 20261005000000`, `MOZ_APP_VERSION 157.0-2`. Against Beta 5 x86_64: 15 of 3,273 entries differ, and in omni.ja only `librewolf.cfg` and `AppConstants.sys.mjs`. Against the rejected run's x86_64: 13 entries differ. These are the build-date fallout plus `classes.dex`, `classes2.dex` and `res/DZ.xml`, which are the fix | `static/build-id.txt`, `static/entries-vs-*.txt` |
| 1 | `--check-launcher-start` | 0 | **PASS.** Fresh profile and restart, no setup-failure dialog after 45 s | `device/smoke/check-launcher-start/` |
| 2 | `--check-aboutconfig` | 0 | **PASS.** 30 rows, the edit survived a restart, 52 prefs locked | `device/smoke/check-aboutconfig/` |
| 2a | about:config CSP probe | 0 | **PASS.** 0 CSP errors from about:config, and the positive control was caught | `device/aboutconfig-csp/` |
| 3 | `--check-ubo-preinstall` | 0 | **PASS**, 2/2 | `device/smoke/check-ubo-preinstall/` |
| 4 | `--check-ubo-lifecycle` | 0 | **PASS**, 10/10 | `device/smoke/check-ubo-lifecycle/` |
| 5 | `--check-ubo` | 0 | **PASS** | `device/smoke/check-ubo/` |
| 6 | `--check-search` | 0 | **PASS.** The query went to noai.duckduckgo.com with no partner parameter. 4 engines | `device/smoke/check-search/` |
| 7 | `--check-no-suggest` | 0 | **PASS.** 60 s typing window: 8 keep-alive records, 3 background flows, 0 typing flows. Enter sent 9,128 B | `device/smoke/check-no-suggest/` |
| 7a | `--check-no-suggest --no-suggest-negative-control` | 1 | **NEG, as expected.** Caught `ac.duckduckgo.com` on 5 connections | `device/smoke/check-no-suggest-negative-control/` |
| 8 | baseline, with **full graphics acceptance** | 0 | **PASS**, 8/8. Graphics `acceptanceComplete: true`, **161/161** | `device/smoke/baseline-smoke/` |
| 9 | `--check-update-privacy` (and a rerun) | 1, 1 | **H-FP; the product half passed.** OFF half: the row is present and OFF by default, and there are 0 update-host events. ON half: the switch was tapped on and the app relaunched. **DNS + SNI `redoubtbrowser.org`** appear in the ON window, which is what failed in the rejected run. The check then flags "new hosts" by bare SYN destination IP:<br>• run 1: `151.101.65.91`. Its SNI is `firefox-settings-attachments.cdn.mozilla.net`, which is in the OFF window on `151.101.1.91` (Fastly rotation).<br>• rerun: `151.101.193.91` (same host). Also `185.199.111.153`, whose SNI is `redoubtbrowser.org`: the update host's own address.<br>The harness subtracts update-hit *names*, not their addresses (`android-smoke.sh` around line 4110) | `device/smoke/check-update-privacy*/` |
| **9a** | **update-check probe, live endpoint, ON** | 0 | **PASS (2b).** After the tap, `fenix_preferences.xml` has `pref_key_lw_update_check=true`, and no other file has the key. Home, then a launcher resume, gives **exactly one** request: `GET https://redoubtbrowser.org/update/android/latest.json`. Response **404** (`server: GitHub.com`). **No `.sig` request**, no dialog, no crash, app alive at 45 s. `lw_update_check.xml` gets `last_run_ms` only. A second resume inside 24 h makes 0 requests. Request headers are `User-Agent: Redoubt-UpdateCheck/1`, `Accept: */*`, `Accept-Language: en-US`, `Accept-Encoding`, `Sec-GPC: 1`, `Sec-Fetch-*`, `Connection`. There is no cookie, no query string and no version. `LOAD_ANONYMOUS` and `LOAD_BYPASS_CACHE` are set | `update-check/device-live/probe.json`, `03-*`, `04-*` |
| **9b** | **same probe, OFF half** | 0 | **PASS.** The switch was turned off in Settings, and `fenix_preferences.xml` reads `false`. The app was stopped, the throttle file removed, then relaunched and resumed: **0 requests**, and `lw_update_check.xml` was not recreated, so `maybeRun` returned at `isEnabled`. **Control:** switch back on, next resume: 1 new GET of the same URL, 404 | `update-check/device-live/probe.json` (`off_*`, `control_*`) |
| **9c** | **wrongly signed document, on the device** | 0 | **PASS.** A local TLS endpoint (throwaway CA, reached through `network.dns.localDomains` and `adb reverse`) served `latest.json` (`157.0-99`, `version_code` 2016189999, which **would** be offered if it verified) and a `.sig` from a **throwaway** P-256 key. The app fetched both (server log: 2 GETs, 200). It **offered nothing**: no dialog, `last_offered_version` never written, alive, no crash. The first attempt reached no server because host port 8443 was already taken by a local container; it is kept as `device-local-port-conflict/` and proves nothing | `update-check/device-local/` |
| H | Host-side document checks (throwaway key) | | **PASS.** Details in "Update document" | `update-check/host-verifier.txt` |
| 10 | `--check-https-only` | 0 | **PASS**, 3/3 | `device/smoke/check-https-only/` |
| 11 | `--check-no-gms --check-no-adjust` (device, so the baseline runs again) | 0 | **PASS**, 10/10, including a **second full graphics acceptance**, 161/161 | `device/smoke/static-no-gms-no-adjust/` |
| 12 | `--check-strings` (device) | 0 | **PASS.** 36 screen stops, 0 branded strings shipped. One remote AMO description is reported but not gated | `device/smoke/check-strings/` |
| 13 | `--self-test` | 0 | **PASS** (`SELF-TEST OK`) | `device/smoke/self-test/` |
| 14 | `--first-run-capture` | 1 | **E12.** 103 events, app UID rx +22,643,184 B / tx +432,823 B. Compared with Beta 5 below | `device/smoke/first-run-capture/`, `device/first-run-host-comparison.json` |
| 15 | `--check-no-remote-settings` | 1 | **E12.** The same 3 Remote Settings hosts as before | `device/smoke/check-no-remote-settings/` |
| 16 | **pref audit** (`generate-android-pref-baseline.sh` + `android-pref-audit.sh`) | 0, 0 | **PASS.** A fresh `--pref-dump` on the device: 58 rows, "baseline unchanged", so `expected-prefs.txt` has **no diff** (`baseline-diff.out` is empty). Audit against the committed baseline: 0 violations, 0 non-must-lock diffs. 132 must-lock keys, of which 20 are in the dump's universe | `device/pref-audit/` |
| 17 | **upgrade, Beta 5 → 157.0-2** (`adb install -r`) | 0 | **PASS.** Details below | `device/upgrade/` |

**First-run hosts compared with the Beta 5 candidate's capture** (`device/first-run-host-comparison.json`):
- **Counts.** 103 events here; Beta 5's capture had 124.
- **Named hosts.** None added. `malware-filter.pages.dev` is gone: this capture reached `malware-filter.gitlab.io` and not the pages.dev mirror, which is uBO's choice between mirrors.
- **Unnamed destinations.** All are in the same provider ranges as before.
- **No `redoubtbrowser.org`.** The capture has none, as expected with the switch off by default.
- **DNS.** The emulator used 9.9.9.9 (`-dns-server`), not the host's LAN resolver.

## Upgrade: Beta 5 → 157.0-2

`scripts/upgrade-test.py`, three phases on one profile.

**A. Beta 5 (2016188262) on a fresh install.**
1. Launcher start; the uBO sheet was acknowledged.
2. Search suggestions turned ON through Settings.
3. DNS over HTTPS set to **Max Protection** (radio checked, Quad9). Gecko reads `network.trr.mode=3`.
4. https://example.org/ bookmarked from the main menu.
5. In uBO's own Filter lists pane, "Dan Pollock's hosts file" (`dpollock-0`) ticked, then Apply.

**B. Upgrade.** `adb install -r` (no `-d`, no uninstall):
- `Success`, versionCode 2016188262 → **2016188486**, the same signer, the same `firstInstallTime`;
- two launcher launches, each observed for 45 s: alive, **no alert dialog and no suspicious label** (setup failed / provider changed / What's new / Welcome), empty crash buffer, no FATAL lines.

**C. Read back on the upgraded profile.**
- **Suggestions:** ON.
- **DNS over HTTPS:** row summary "Max Protection", radio checked. Gecko `network.trr.mode=3`, `uri=https://dns10.quad9.net/dns-query`.
- **Bookmark:** "Example Domain" (https://example.org/) present.
- **uBO:** 1.75.0, active, AMO-signed. `selectedFilterLists` is identical to phase A's final list, `dpollock-0` included.
- **Version:** `appinfo` 157.0-2 / `20261005000000`.
- **Update check:** the "Check for updates" row is **present and OFF**. `fenix_preferences.xml` has no `pref_key_lw_update_check`, which reads as off. `lw_update_check.xml` does not exist, so the check never ran. `org.redoubtbrowser_preferences.xml` holds `pref_key_lw_update_check=false`. That stale value most likely comes from Beta 5, whose build carried the row compiled out but still persisting (the androidx default file). 157.0-2 ignores it by design (`b86c1a0c`: "a value … left in the default file is ignored, not migrated"). It is `false` either way.

## Update document (host side; nothing was signed with the owner's key)

- **Generated document.** `scripts/update-manifest.py generate --tag android-157.0-2`, run on this run's
  `output-metadata.json` with `--published 2026-10-05T02:43:22Z` (the generation time). It gives `version_code` **2016188480**
  (the lowest of the four codes) and the `android-157.0-2` release URLs. Its sha256 is
  **`039a38cc2130bcb073b395a36b6f4365b455944aa9786ddbc1ad0c85d97eafcc`**. It is staged in the signing bundle.
- **Throwaway-key signature.** Signed with a **throwaway** P-256 key made for this test
  (`update-check/throwaway-update-test.pubkey`, `throwaway-signed-latest.json.sig`):
  - `update-manifest.py verify` with the committed key: **REJECTED**, exit 1. This is what the app does, and 9c shows it on the device.
  - With the throwaway key: signature OK. The verdict is "up to date" for this build's own code 2016188486, "update offered" for Beta 5's 2016188262, and the `--metadata` cross-check passes.
  - The device document (`update-check/device-local-doc/`) is likewise rejected with the committed key and "update offered" with the throwaway key. That is the positive control: it would have been offered had its key been trusted.
  - `sign-update-manifest.sh` with the throwaway key **refused** and wrote no `.sig`.
- **No positive verification against the owner's key is claimed.** Only the owner can make that signature, and its intake is `DISTRIBUTION.md` step 5.

## Signing bundle

`~/redoubt-artifacts/stable/accept2/signing-bundle/` (not in the repository):
- the four unsigned APKs and `SHA256SUMS` (the CI file, unchanged; `sha256sum -c` OK);
- `sign.sh`, `android-verify-signature.sh`, `SIGNING.md` and `apksigner.jar` (36.0.0, `3716d931…3dec`), with `SHA256SUMS.tools`. All four hashes equal the previous bundle's;
- `update/`, holding `latest.json` (`039a38cc…afcc`), `sign-update-manifest.sh` (`5e0820f6…193b135`), `update-check.android.pubkey` (`8e714075…7de8`) and `SHA256SUMS.update`.

## Not covered

- **Physical devices and other ABIs.** No physical device was used, and only x86_64 ran on a device. arm64-v8a and armeabi-v7a were checked statically only.
- **A positive on-device verification.** It needs the owner's signature on a published document.
- **The probes from the 157.0-1 acceptance** were not repeated: stripped features, cookie online/offline, and the default-browser prompt.
- **Harness fix for row 9.** `--check-update-privacy` should ignore the address of any flow whose SNI names an allowed host. That is a harness change, so it is left for a separate commit.
