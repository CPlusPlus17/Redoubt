# 157.0-2: device acceptance of CI run 37234607054, 2026-10-05: **FAIL**

> **Superseded.** The rebuild with the fix, CI run 37248744119 (`27240eb6`, build date
> 20261005000000), passed acceptance: [`run-37248744119/README.md`](run-37248744119/README.md).
> Everything below is the record of the rejected first build.

**Result: the payload FAILS acceptance on a product defect. Do not sign or publish it.** The
in-app update check, which this release exists to ship, cannot be turned on. The Settings switch
looks like it works, but its value goes to a SharedPreferences file that the check never reads. So
no install of this build would ever check for updates. Everything else that ran passed, apart from
the expected-red rows. Following the acceptance rules, nothing was rebuilt: the build is CI's.
The upgrade test (Beta 5 → 157.0-2), the pref audit and the local wrong-signature device test were
**not run**, because acceptance stopped at the defect (see "Not run").

## What was tested

| | |
| --- | --- |
| CI run | <https://github.com/CPlusPlus17/Redoubt/actions/runs/37234607054>, "Android release (unsigned artifacts only)" (`android-release.yaml`), `workflow_dispatch`, job `build-unsigned` on runner `redoubt-ci-boxb`, conclusion `success`. Inputs from the log: `MODE: full`, `UPDATE_CHECK: true`, `BUILD_DATE_IN: 20261004200000` (`ci/run.json`, `ci/run.log.gz`) |
| headSha (from `gh run view --json headSha`) | `0ef74faddc8238203294305a656652fef010e8bf`. This equals `git rev-parse origin/main` and is the commit this branch starts from. Settings gitlink `008b87fddb0fb12084690a40127454a23b8e2e5c` |
| Artifact | `redoubt-android-unsigned`, 616,821,208 bytes, digest `sha256:90d0336e9a38e0b583dcc2220b46baf7a524014bf6204ea8787bd2e720cf988b` (`ci/artifacts.json`). `sha256sum -c SHA256SUMS`: all four OK (`ci/SHA256SUMS.check.txt`) |
| Artifact SHA256SUMS | arm64-v8a `77ed03dc7f694c2b0f445668dca8b53f30a3560a064eb570d006d98b052a2cfa`<br>armeabi-v7a `8405512a357aed900421da659e14a922889f3a37f59fb534efea8d76d3fa23b1`<br>universal `ecf48d5b5d1a13823df8cd21bf27a09a76c8759245eaa785f39cc3b3563b0b8c`<br>x86_64 `d8623f00226e97bc957942e6d2a6ec5378f2e4ac214ad2ef90613bcb6c8a34f5` |
| Installed (x86_64) | `0aeaa4bfce362f17ae89360200d9ee9cdbab56ca97f69b3829e72e7d17626fa9`. Signed with the throwaway key (cert `31e9a40f…b760`, `CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, v2+v3, apksigner 36.0.0), not the release key. All 3,131 non-META-INF entries equal the unsigned APK's (`device/apk-identity.txt`) |
| Beta 5 (staged for the upgrade test, not run) | throwaway-signed `f09c6f4a337d844bea23abfb229f6a44279348134478cb1f65f8b327a5e47ea2`, from unsigned `da72cbbe…68b9`. Byte-identical to the LW-M7-41 candidate's signed copy |
| `scripts/android-smoke.sh` | `dba0f279e5ca6eec7a51c1ac9d43e320536a88943c7494dca7e33b67a824ce46` (same as the 157.0-1 and Beta 5 acceptances) |
| `scripts/android-graphics-smoke.py` | `ce0072ea63fa3fdd1b183bcab3f7adfed279842c6fe090ef5834eec9e96a4612` (same) |
| `scripts/android-cookie-banner-smoke.py` | `b9c88af618a56d5cb304bd6f1ebd80af9edd1251626d216e49fef4c051a59274` |
| Runner and probes | `scripts/` (`run-check.sh`, `batch*.sh` and `aboutconfig-csp-probe.py`, copied from earlier acceptances with paths changed; `update-check-probe.py` and `update-endpoint-server.py` are new). Every harness run recorded HEAD `0ef74fad` and 0 uncommitted changes under `scripts/` (`device/smoke/exit-status.jsonl`) |

**Conditions.** One emulator: emulator-5584, android-30 `default` x86_64, no GMS, swangle. It was
booted by the harness with `-dns-server 9.9.9.9 -tcpdump` in the first check and reused with `--serial`
after that. AMO was reachable. Every check started from a fresh profile (`pm clear`). Logcat was
streamed for every `--serial` run.

## Summary

PASS = passed. **FAIL** = product defect. E12 = red as expected under E12. NEG = a negative control
that must fail and did.

| # | Check | Exit | Result | Evidence |
| --- | --- | --- | --- | --- |
| S1 | versionName / versionCodes | | **PASS.** `157.0-2-default` in all four. Codes: v7a 2016188448, arm64 2016188450, x86_64 2016188454, universal 2016188455. All are above Beta 5's 2016188256-63. Label `Redoubt`, package `org.redoubtbrowser` | `static/apk-badging.txt` |
| S2 | ELF per ABI | | **PASS.** Each split APK carries only its own ABI's ELF: 14 shared objects + 1 PIE each. The universal APK has all three ABIs, with a matching `libxul.so` for each | `static/elf-per-abi.txt` |
| S3 | Unsigned | | **PASS.** No META-INF signature files. `apksigner verify` gives "DOES NOT VERIFY / Missing META-INF/MANIFEST.MF", exit 1, for all four | `static/unsigned.txt` |
| S4 | Branding | | **PASS.** omni.ja `brand.ftl` / `brand.properties` say Redoubt. The brand files and art are byte-equal to Beta 5's. `android-brand-check.py` passes on a tree made with `make dir TARGETS=android` at `0ef74fad` (74 images replaced, no Mozilla mark) | `static/omni-branding.txt`, `static/brand-check-tree.out` |
| S5 | uBO | | **PASS.** `ublock_origin.xpi` 1.75.0, sha256 `5b744158…5287` = `ubo-extension.json` pin, AMO-signed (`META-INF/cose.sig`, `mozilla.rsa`), the same in all four APKs | `static/ubo-and-omni.txt` |
| S6 | Packaged `librewolf.cfg` | | **PASS.** Byte-equal to `settings/common.cfg + settings/android.cfg` at `008b87f`, the same in all four APKs. Contains: the pinned uBO catalog `…/612fac02…/assets/uBOAssets.android.json`; `lockPref browser.ipProtection.enabled false` and `.guardian.endpoint ""`; `network.lna.allow_top_level_navigation false`; both `privacy.restrict3rdpartystorage.heuristic.navigation` and `.recently_visited` false | `static/librewolf-cfg.txt` |
| S7 | Update-check key and endpoint in the dex | | **PASS.** In all four APKs, `classes2.dex` carries the committed P-256 key `assets/update-check.android.pubkey` (sha256 `8e714075…7de8`) once, `https://redoubtbrowser.org/update/android/latest.json` once and `Redoubt-UpdateCheck/1`. The old `/updates/android/` path is not present | `static/update-check-static.txt` |
| S8 | `android-cookie-banner-smoke.py --apk --fetch` | 0 | **PASS**, 5/5 on x86_64 and on universal: catalog, pref, bundled, migration, hosted | `static/cookie-lists-apk-*.out` |
| S9 | `--check-strings --check-no-gms --check-no-adjust` (static) | 0 | **PASS.** 243,650 rows, 0 unexplained | `static/static-strings-nogms-noadjust.*` |
| S10 | Build ID | | `MOZ_BUILDID 20261004200000`, `MOZ_APP_VERSION 157.0-2`. Against Beta 5 x86_64, 14 of 3,273 entries differ, and in omni.ja only `librewolf.cfg` (the two heuristic prefs) and `AppConstants.sys.mjs` | `static/build-id.txt`, `static/entries-vs-beta5-x86_64.txt` |
| 1 | `--check-launcher-start` | 0 | **PASS** | `device/smoke/check-launcher-start/` |
| 2 | `--check-aboutconfig` | 0 | **PASS.** 30 rows, the edit survived a restart, 52 prefs locked | `device/smoke/check-aboutconfig/` |
| 2a | about:config CSP probe | 0 | **PASS.** 0 CSP errors from about:config. The positive control was caught | `device/aboutconfig-csp/` |
| 3 | `--check-ubo-preinstall` | 0 | **PASS**, 2/2 | `device/smoke/check-ubo-preinstall/` |
| 4 | `--check-ubo-lifecycle` | 0 | **PASS**, 10/10 | `device/smoke/check-ubo-lifecycle/` |
| 5 | `--check-ubo` | 0 | **PASS** | `device/smoke/check-ubo/` |
| 6 | `--check-search` | 0 | **PASS.** The query went to noai.duckduckgo.com, 4 engines | `device/smoke/check-search/` |
| 7 | `--check-no-suggest` | 0 | **PASS.** 60 s typing window with 8 keep-alive and 3 background flows and 0 typing flows. Enter sent 9,121 B | `device/smoke/check-no-suggest/` |
| 7a | `--check-no-suggest --no-suggest-negative-control` | 1 | **NEG, as expected.** Caught `ac.duckduckgo.com` on 3 connections | `device/smoke/check-no-suggest-negative-control/` |
| 8 | baseline, with **full graphics acceptance** | 0 | **PASS**, 8/8. Graphics `acceptanceComplete: true`, **161** checks | `device/smoke/baseline-smoke/` |
| **9** | **`--check-update-privacy`** | **1** | **FAIL (product defect).** OFF half: the row is present and OFF by default, and there was no update-host event. ON half: the switch was turned on through the UI and the app relaunched. **No event to redoubtbrowser.org.** The capture was live (Remote Settings DNS, SYN and SNI in the same window) | `device/smoke/check-update-privacy/` |
| **9a** | **update-check probe, live endpoint** | 0 | **Confirms the defect.** Details below | `update-check/device-live/` |
| 10 | `--check-https-only` | 0 | **PASS**, 3/3 | `device/smoke/check-https-only/` |
| 11 | `--check-no-gms --check-no-adjust` (with `--serial`, so the baseline runs again) | 0 | **PASS**, 10/10, including a **second full graphics acceptance**, 161/161 | `device/smoke/static-no-gms-no-adjust/` |
| 12 | `--check-strings` (device) | 0 | **PASS.** 36 screen stops, 0 branded strings shipped. One remote AMO description is reported but not gated | `device/smoke/check-strings/` |
| 13 | `--self-test` | 0 | **PASS** (`SELF-TEST OK`) | `device/smoke/self-test/` |
| 14 | `--first-run-capture` | 1 | **E12.** 113 events, app UID rx +23,397,932 B / tx +519,299 B. Compared with Beta 5 below | `device/smoke/first-run-capture/`, `device/first-run-host-comparison.json` |
| 15 | `--check-no-remote-settings` | 1 | **E12.** 3 Remote Settings hosts, as before | `device/smoke/check-no-remote-settings/` |
| H | Host-side document checks (throwaway P-256 key) | | **PASS.** Details in "Update document" | `update-check/host-verifier.txt` |
| — | pref audit, upgrade from Beta 5, local wrong-signature device test | | **Not run.** Acceptance stopped at row 9 | |

**First-run hosts compared with the Beta 5 candidate's capture** (`device/first-run-host-comparison.json`):
- **Counts.** 113 events here; Beta 5's capture had 124.
- **Named hosts.** The set is identical: no host added and none gone.
- **Unnamed destinations.** `2606:50c0:8001::153` and `::154` are new. They are in GitHub's `2606:50c0::/32` range, the same range as Beta 5's new `8002::153/154` (range inferred from the prefix, not looked up).
- **No `redoubtbrowser.org`.** The capture has none, as expected with the switch off.

## The defect: the update-check switch is never read

**Symptom** (row 9, then probe 9a, which records requests inside Gecko's parent process on a fresh
profile):

1. **Row present.** Settings shows "Check for updates" with the full disclosure summary, OFF by default.
2. **Switch turned on.** One tap, the same way a user does it. The switch then reads ON.
3. **Check triggered.** Home key, then the launcher intent: the next `HomeActivity.onResume`, the only caller of `UpdateCheck.maybeRun`. A second resume followed.
4. **Result.** The `http-on-*` observers saw **0 requests** to redoubtbrowser.org. There was no dialog and no crash.
5. **The check never got past its first line.** `shared_prefs/lw_update_check.xml` was never created. `maybeRun` writes `last_run_ms` there before any fetch, so `isEnabled()` must have returned false.

**Cause** (`update-check/device-live/shared-prefs-after.txt`, read on the device with `su` after the
probe):

    org.redoubtbrowser_preferences.xml:    <boolean name="pref_key_lw_update_check" value="true" />
    fenix_preferences.xml:                 (no pref_key_lw_update_check)

- **The read.** `UpdateCheck.isEnabled` reads `context.components.settings.preferences`, which is `fenix_preferences` (`Settings.kt:178`). In `patches/android/update-check.patch` that is lines 493-497.
- **The write.** The row is a plain `SwitchPreferenceCompat` in `preferences.xml` (patch line 606). `SettingsFragment` does not set `preferenceManager.sharedPreferencesName`, so androidx persists the row to its own default file, `<package>_preferences`.
- **How upstream handles it.** Fenix's other switches on this screen copy the value across in a change listener. For example, `SettingsFragment.kt:662-663` for remote debugging does `settings.preferences.edit { putBoolean(preference.key, newValue) }`. The update-check row has no listener.
- **Why the result is always off.** The switch value goes to `<package>_preferences`, and nothing copies it to `fenix_preferences`. So `isEnabled` is always false, and the check never runs on any install.

**Why nothing caught it before.**
- `UpdateCheckerTest` and `test-update-check-jvm.sh` exercise `UpdateChecker`, the fetch, verify and compare half. Nothing tests the switch-to-`isEnabled` wiring.
- The opt-in half of `--check-update-privacy` had never run on a build with a key (`DISTRIBUTION.md`, "Not yet measured on a device"). This is its first run, and it failed exactly as it should.

**Where the fix belongs.** It belongs in `update-check.patch`, not in this branch. Two options:
- give the row a change listener that writes `settings.preferences`, as the remote-debugging row does;
- make `isEnabled` read the default SharedPreferences.

After the fix, a new CI run is needed (new build date, so higher versionCodes), and this acceptance
has to be repeated on that run. A unit or Robolectric test that drives the row and then reads
`isEnabled` would have caught this.

**Severity.**
- **Privacy:** none. The defect fails closed: nothing is ever sent.
- **Function:** the release's headline feature does not work, and users get no sign of it. The disclosure and the switch suggest a check that never happens. Beta 1-5 users cannot get it either way. A 157.0-2 user would believe they are notified of updates and never would be.

## Update document (host side; nothing was signed with the owner's key)

- **Generated document.** `scripts/update-manifest.py generate --tag android-157.0-2` on this run's
  `output-metadata.json` gives `version_code` 2016188448 (the lowest of the four codes) and the
  `android-157.0-2` release URLs. Its sha256 is `ea990570020d83d9a223c3b5160a4d0456cf7d08cd45a7aa8c9d7e6c83c84d89`
  (staged in the signing bundle, see below).
- **Throwaway-key signature.** Signed with a **throwaway** P-256 key made for this test
  (`update-check/throwaway-update-test.pubkey`, `throwaway-signed-latest.json.sig`):
  - `update-manifest.py verify` with the committed key: **REJECTED**, exit 1. This is what the app would do.
  - With the throwaway key: signature OK. The verdict is "update offered" for Beta 5's code 2016188262 and "up to date" for this build's 2016188454.
  - `sign-update-manifest.sh` with the throwaway key refused and wrote no `.sig`, because it does not verify against the pinned key.
- **No positive verification against the owner's key is claimed.** Only the owner can produce that signature.
- **On-device rejection of a wrongly signed document: not shown.** `update-check-probe.py local`
  serves such a document through a local TLS endpoint. The document would offer an update if
  accepted (`version_code` 2016189999). The probe was not run: with the defect, the check never
  fetches, so a "no dialog" result would prove nothing about signature handling. The probe is
  committed for the next run.

## Signing bundle (prepared, on hold)

`~/redoubt-artifacts/stable/accept/signing-bundle/` contains:
- the four unsigned APKs and `SHA256SUMS` (the CI file, unchanged);
- `sign.sh`, `android-verify-signature.sh`, `SIGNING.md` and `apksigner.jar` (36.0.0, sha256 `3716d931…3dec`, the same as earlier bundles), with `SHA256SUMS.tools`;
- `update/`, holding `latest.json`, `sign-update-manifest.sh` and `update-check.android.pubkey`.

It also has **`DO-NOT-SIGN.txt`**, because this payload failed acceptance.

## Not run

- **Pref audit** (`batch3-pref-audit.sh`, committed). The baseline run's `pref-dump` row passed: 58 prefs, `librewolf.webgl.prompt=True`.
- **Upgrade, Beta 5 → 157.0-2.** `upgrade-test.py` is adapted and committed, and phase C also reads the update-check row and its prefs. Beta 5 was staged and signed.
- **On-device wrong-signature test**, for the reason above.
- **The rest.** The probes from the 157.0-1 acceptance (stripped features, cookie online/offline, default-browser prompt), any physical device, and any ABI other than x86_64 on a device.
