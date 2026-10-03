# 157.0-1: device acceptance, 2026-10-03

The candidate that passed is **rc3**, built from **`6202ee6d`**. Two earlier builds failed device
acceptance, each on a product defect. Each defect was fixed in the patch that owns it, and the APKs
were rebuilt each time. Every check below was then run again on rc3.

| Build | Source | Result |
| --- | --- | --- |
| rc1 | `d3bff1a2` | **FAIL.** Graphics acceptance failed 3 of 3 times: after the process restart, the "Canvas and WebGL permissions" list was empty. Fixed in `751f5950` (canvas-webgl-permissions.patch). See `rc1-graphics-defect/` |
| rc2 | `751f5950` | **FAIL.** The graphics fix held: 161/161, and the list rendered 3 of 3 times. The real upgrade test then showed Android's "Set Redoubt as your default browser app?" dialog on the first launch. The dialog also appears in Beta 3 on the 4th cold start of a fresh profile. Fixed in `6202ee6d` (no-onboarding.patch). See `rc2-intermediate/` |
| **rc3** | **`6202ee6d`** | **PASS.** All rows below. The only red rows are the two E12 rows and the two negative controls, as expected |

Also on the branch is `4efb050b`, the regenerated pref baseline (part (c)). It changes docs only.

## What was tested

| | |
| --- | --- |
| Source commit | `6202ee6d4e7f8ce49b4ed35d4ef7ac93c6c9d67d` (settings gitlink `8a69936`, unchanged since `d3bff1a2`). Every run recorded this HEAD with 0 uncommitted changes under `scripts/` (`rc3/smoke/exit-status.jsonl`) |
| x86_64 unsigned | `2a7d279fdf4e05b4260ed55ee9d79d488718a54290ff83b9505f6cb70d70308f` |
| x86_64 installed | `0af21064df36b5b966ef7a60f6214fdba207b2f2fa7dac8a471e44dd2fcabff0`. Signed with the throwaway key (cert `31e9a40f…b760`, `CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, v2+v3), not the release key. All 3,131 non-META-INF entries equal the unsigned APK's (`rc3/apk-identity.txt`) |
| Other rc3 APKs | arm64-v8a `0eabc358…a666`, armeabi-v7a `9d7bb192…c6c9`, universal `c653b7aa…122b` (`build-rc3/SHA256SUMS.apk`). versionName `157.0-1-default`, versionCode 2016188072/74/78/79 |
| Beta 3 (upgrade start point, negative controls) | installed `77348e7d…af83`, the same throwaway-signed copy the 153.4 acceptance used (unsigned `1ac3b01d…95e8`, source `0a134441`) |
| `scripts/android-smoke.sh` | sha256 `dba0f279e5ca6eec7a51c1ac9d43e320536a88943c7494dca7e33b67a824ce46` (same as the 153.4 final acceptance) |
| `scripts/android-graphics-smoke.py` | sha256 `ce0072ea63fa3fdd1b183bcab3f7adfed279842c6fe090ef5834eec9e96a4612` (same) |
| `scripts/android-cookie-banner-smoke.py` | sha256 `c49b4aaca8dbbe0390755f1c8a4237b21792b0d044dab50dfd7165f6a0a228f7` |
| Probes (not gates) | `rc3/scripts/`. These reuse the harness's own client (`work/harness/driver.py`) |

**How rc2 and rc3 were built** (`build-rc2/`, `build-rc3/`). Both fixes change Kotlin only. A fresh
`make dir TARGETS=android` at each fix commit was compared with the rc1 build tree after the changed
files had been copied in. The two trees differ only in build byproducts (`fix/tree-diff-*.txt`). No
Gecko input changed since `d3bff1a2`, so the rc1 fat AAR (build date `20261002210000`) is reused, and
only `make android-package` ran. It took about 5 minutes, and MemAvailable stayed at or above 18,782,180 kB. In all
four APKs, only `classes.dex`, `classes2.dex` and the derived `assets/dexopt/baseline.prof(m)` differ
from rc1 (`build-rc3/rc1-vs-rc3-entries.txt`). `omni.ja`, the native libraries and the resources are
byte-identical. `verify_apks.py` gives the same result as for rc1, apart from APK sizes and hashes.
Because the build date is the same, the versionCodes equal rc1's. Neither rc1 nor rc2 left the build
host.

## Conditions

- **Emulator.** One emulator, emulator-5584, android-30 `default` x86_64 (no GMS), swangle. The
  harness booted a new AVD (`lw-smoke`, under `acceptance/rc3/work` on the build host) with
  `-dns-server 9.9.9.9 -tcpdump` in the first check. Every later check reused it with `--serial`.
- **Network and profile.** AMO was reachable. There was no priming and no iptables. Every harness
  check and every probe started from a fresh profile (`pm clear`). The upgrade test is the exception:
  it keeps its profile by design.
- **Logcat.** Each `--serial` run streamed `logcat -v threadtime` to `<check>.logcat.gz`.
- **Memory.** The host is shared with other CI. MemAvailable minimums were 18,902,620 kB (rc2) and
  18,782,180 kB (rc3) (`build-*/memavail-min.txt`). The memory guard never paused a build container.

## Results on rc3

PASS = passed. E12 = expected red under E12. NEG = a negative control that must fail and did.

| # | Check | Exit | Result | Evidence |
| --- | --- | --- | --- | --- |
| 1 | `--check-launcher-start` | 0 | **PASS.** Both launcher cold starts (fresh profile, restart) reached uBO readiness, with no setup-failure dialog after 45 s | `rc3/smoke/check-launcher-start/` |
| 2 | `--check-aboutconfig` | 0 | **PASS.** 30 rows, `general.aboutConfig.enable=true` on the default branch, the edit survived a restart, 52 prefs locked | `rc3/smoke/check-aboutconfig/` |
| 2a | about:config CSP probe (diagnostic) | 0 | **PASS.** 0 CSP / script-src-attr errors from about:config in the console service. The positive control was caught. As on 153.4, logcat does not carry console errors, so it is not a witness | `rc3/aboutconfig-csp/` |
| 3 | `--check-ubo-preinstall` | 0 | **PASS.** The bundled-list script is blocked on first navigation. The pinned AMO-signed 1.75.0 add-on is active | `rc3/smoke/check-ubo-preinstall/` |
| 4 | `--check-ubo-lifecycle` | 0 | **PASS**, 10 of 10 rows: disable, restart, remove, APK reinstall | `rc3/smoke/check-ubo-lifecycle/` |
| 5 | `--check-ubo` | 0 | **PASS** | `rc3/smoke/check-ubo/` |
| 6 | `--check-search` | 0 | **PASS.** The query went to `noai.duckduckgo.com` with no partner parameter. 4 engines, default DuckDuckGo No-AI | `rc3/smoke/check-search/` |
| 7 | `--check-no-suggest` | 0 | **PASS.** 60 s typing window with 8 keep-alive and 3 background flows and 0 typing flows. Enter produced 9,120 B to noai.duckduckgo.com. The switch is OFF and the round trip works | `rc3/smoke/check-no-suggest/` |
| 7a | `--check-no-suggest --no-suggest-negative-control` | 1 | **NEG, as expected.** Suggestions ON caught `ac.duckduckgo.com` on 4 connections | `rc3/smoke/check-no-suggest-negative-control/` |
| 8 | baseline suite, including the **full graphics acceptance** | 0 | **PASS**, 8 of 8. Graphics `acceptanceComplete: true`, **161 checks**, including `session-exceptions-expire-on-process-restart` and `remembered-exceptions-survive-process-restart`. rc1 failed exactly here | `rc3/smoke/baseline-smoke/` |
| 9 | `--check-update-privacy` | 0 | **PASS.** The row is compiled out, and there was no update-host traffic in 121 app events | `rc3/smoke/check-update-privacy/` |
| 10 | `--check-https-only` | 0 | **PASS** | `rc3/smoke/check-https-only/` |
| 11 | `--check-no-gms --check-no-adjust` (with `--serial`, so the baseline runs again) | 0 | **PASS.** Both static checks pass, and the whole baseline passes again, including a **second full graphics acceptance**, 161/161 | `rc3/smoke/static-no-gms-no-adjust/` |
| 12 | `--check-strings` | 0 | **PASS.** 243,650 rows, 0 unexplained. 36 screen stops, 0 branded strings shipped. One remote AMO description is reported but not gated | `rc3/smoke/check-strings/` |
| 13 | `--self-test` | 0 | **PASS** (`SELF-TEST OK`). Every probe reported FAIL when fed a wrong expectation. In this run the graphics row failed on an adb `input swipe` timeout, not on the forced expectation. Rows 8 and 11 show full graphics acceptance passing twice on this emulator | `rc3/smoke/self-test/` |
| 14 | `--first-run-capture` | 1 | **E12.** 108 events, app UID rx +22,969,037 B / tx +462,310 B. Host differences from Beta 3 are listed in (d) | `rc3/smoke/first-run-capture/`, `rc3/first-run-host-comparison.json` |
| 15 | `--check-no-remote-settings` | 1 | **E12.** 4 events to the 3 Remote Settings hosts, as on Beta 3 | `rc3/smoke/check-no-remote-settings/` |
| a1 | uBO cookie lists, online first run | 0 | **PASS.** Details in (a) | `rc3/probes/ubo-cookie-online/` |
| a2 | uBO cookie lists, Beta 3 (negative control) | 0 | **NEG, as expected.** Neither list is selected, both elements stay visible, and the `cookie-script.com` fetch resolves | `rc2-intermediate/ubo-cookie-beta3-control/` |
| a3 | `android-cookie-banner-smoke.py --apk <rc3 x86_64> --fetch` | 0 | **PASS**, 4 of 4: catalog, pref, bundled, and the hosted catalog matches the repository | `rc3/static-cookie-lists-apk-x86_64.out` |
| a4 | uBO cookie lists, offline first run | 0 | **Documented, not a pass/fail row.** See (a) | `rc3/probes/ubo-cookie-offline/` |
| b | Stripped features absent at runtime | 0 | **PASS.** Details in (b) | `rc3/probes/stripped-features/` |
| c | Pref audit | 0 | **PASS.** The generator exits 0 with a 0-line diff against the committed baseline (`4efb050b`). The audit exits 0: 0 violations, 0 notes | `rc3/pref-audit/` |
| d | First-run hosts compared with Beta 3 | n/a | **Explained.** See (d) | `rc3/first-run-host-comparison.json` |
| e | REAL upgrade Beta 3 → rc3 (`adb install -r`) | 0 | **PASS.** Details in (e) | `rc3/upgrade/` |
| f | Add-on re-enable without restart (LW-M7-19) | 0 | **PASS.** Details in (f) | `rc3/probes/ubo-cookie-online/` (`reenable`) |
| F1 | Fix check, rc1 defect: quiet-notice Review right after a cold start | 0 | **PASS**, 3 of 3. The list renders with the pending WebGL row, and there are 0 "No listener" lines. On rc1 it was 0 of 2 | `rc3/probes/review-race-rc3/` |
| F2 | Fix check, rc2 defect: default-browser prompt on cold starts | 0 | **PASS.** 0 prompts in 7 launcher cold starts. rc2 and Beta 3 both prompted on the 4th | `rc3/probes/default-browser-prompt-rc3/` |

**Tally.** Every row passed, apart from the two E12 rows (14, 15), which are red as expected, and the two
negative controls (7a, a2), which failed as they should. No row failed.

### (a) uBO cookie-notice lists

- **Online first run** (`probe-online.json`). Probe: on `https://example.org/` it inserts
  `#AcceptCookieContainer` and `.accept-cookies-banner`, plus a control `.lw-control`, and fetches
  `https://cdn.cookie-script.com/…` (no-cors).
  - **Rules used.** The generic rules `###AcceptCookieContainer` and `##.accept-cookies-banner`, and the
    network rule `||cookie-script.com^$third-party`, are all in EasyList Cookie Notices. The probe
    checked on the host that no other list uBO enables by default contains them.
  - **Result.** Both elements are `display: none`, the control is `block`, and the fetch is rejected.
    This was already true on the first load, 4.5 s into the session.
  - **uBO storage.** `selectedFilterLists` contains `fanboy-cookiemonster` and `ublock-cookies-easylist`.
    Both have `cache/` and `cache/compiled/` entries. The bootstrap pref is the pinned
    `…/612fac02…/assets/uBOAssets.android.json`.
  - **uBO's own Filter lists pane.** Both entries read `checked isDefault cached recent`, and "Ignore
    generic cosmetic filters" is off (screenshot `pane-3p-filters-online.png`).
- **Why example.org, not a local fixture or a real cookie banner.** uBO applies no cosmetic filtering
  on loopback pages: EasyList's generic ad rules stay visible on `127.0.0.1` and `localhost`, while the
  same rules hide the same elements on example.org (`probes/cosmetic-loopback-vs-real-origin/`).
  - **That run's profile.** It was the upgraded Beta 3 profile, which has no cookie lists. So on
    example.org it also shows the cookie rules not applying while the EasyList rules do, which is the
    upgraded-profile behaviour in (e).
  - **Stack Overflow.** A first attempt with Stack Overflow's site-specific rule
    (`##.js-consent-banner`, in both lists) found no consent banner rendered for this host, with or
    without uBO. That was a development run on rc1 and is not archived.
- **Negative control** (row a2). Beta 3 with the same probe: neither list selected, both elements
  visible, and the fetch resolves. So the probe can tell the difference.
- **Offline first run** (`probe-offline.json`). Airplane mode was on before the first launch.
  - **While offline.** uBO started (1.75.0 active). It could not fetch the pinned catalog, so it used
    the catalog inside its XPI, which has stock defaults: **neither cookie list was selected**.
  - **After the network returned** (airplane mode off, app relaunched, checked for 300 s): the
    selection did not change, and the rules were still not applied.
  - **Why.** This is the behaviour `android-cookie-banner-smoke.py` describes: uBO reads the bootstrap
    location only on its first run. A user whose first launch is offline does not get the lists until
    they tick them in uBO's settings. The same applies to an upgraded Beta profile (see (e)). Recorded
    as an owner question, not as a defect.

### (b) The four stripped features

The probe (`probes/stripped-features/probe.json`, with every screen's XML and PNG) collects every label on:

- the browser main menu, including its expanded "More" section;
- the long-press menu of an image;
- the address bar in edit mode;
- the Settings root, scrolled to the end;
- Settings > AI controls and Settings > Redoubt Labs.

It matches the labels against the strings the APK carries for these features, such as "Summarize page",
"Search with Google Lens", "VPN" / "Built-in VPN" and "IP protection".

- **Result.** 0 hits on any screen, and every screen's positive control was present. AI controls lists
  only Translations and Voice search. Labs says "No experimental features to try right now".
- **Merino.** The first-run capture names no `merino.services.mozilla.com`,
  `prod-images.merino…mozgcp.net`, `ohttp-merino…`, `mlpa-…`, `vpn.mozilla.com`, guardian or
  `lens.google.com` host (`first-run-host-comparison.json`).

### (c) Pref audit and the regenerated baseline

On rc2, `generate-android-pref-baseline.sh` changed 2 of 58 rows
(`rc2-intermediate/pref-audit-rc2/baseline-diff.out`). `android-pref-audit.sh` against the old baseline
exited 1, on one must-lock violation. The baseline was regenerated, unedited, in `4efb050b`, whose
message cites both rows:

- `privacy.fingerprintingProtection` false → true (must-lock). This is an upstream 157 change: Android
  Components' `TrackingProtectionPolicy.strict()` now sets `fingerprintingProtection = true` (and the
  same for private browsing). GeckoEngine applies the policy's value, and Redoubt locks Strict. No pref
  file declares a new value.
- `librewolf.webgl.prompt` false → true. This is our own default since LW-M7-14, already shipped in
  Beta 2 and Beta 3.

None of the 58 keys' declarations differ between the 153.4.0esr and 157.0 trees. On rc3 the generator
produced a byte-identical file, and the audit exits 0.

### (d) First-run capture compared with Beta 3's rc2 capture

| | Beta 3 (153.4 final acceptance) | rc3 |
| --- | --- | --- |
| Events | 107 | 108 |
| App UID rx / tx | 20.7 MB / 422 kB | 23.0 MB / 462 kB |
| Named hosts added | | `secure.fanboy.co.nz`, `curbengh.github.io` |
| Named hosts gone | `librewolf.dev`, `malware-filter.pages.dev` | |

- `librewolf.dev` is gone because Beta 3 bootstrapped uBO's catalog from it. 157 bootstraps from the
  pinned `raw.githubusercontent.com/CPlusPlus17/Redoubt/612fac02…/assets/uBOAssets.android.json`.
  `raw.githubusercontent.com` is present in both runs, since Beta 3 already used it for other lists.
  So it is not a new host name, only a new path. The probe's storage read confirms which catalog
  was used.
- `secure.fanboy.co.nz` is a listed mirror of EasyList Cookie Notices, which is now on by default.
- `curbengh.github.io` and `malware-filter.pages.dev` are alternative mirrors of uBO's URLhaus list.
  uBO chooses among them per run. `curbengh.github.io` was already seen in the 153.4 E11 capture.
- Everything else is the same set: Remote Settings, AMO, uBO's list hosts, `publicsuffix.org`.

### (e) Real upgrade, Beta 3 → rc3

`rc3/upgrade/`: `phase-A.json`, `phase-B.json`, `phase-C.json`, `state-*.json`, `pkg-*.txt`, and every
step's XML and PNG.

**A. Beta 3, fresh install.** After the first launcher start and acknowledging the uBO sheet, these
were set through the real UI:

- "Show search suggestions" ON;
- DNS over HTTPS "Max Protection" (Gecko: `network.trr.mode` 3, Quad9 `dns10`);
- `https://example.org/` bookmarked from the main menu (verified in Bookmarks);
- "Dan Pollock's hosts file" ticked in uBO's own Filter lists pane, then Apply.

The GeckoView debug config was then removed.

**B. Upgrade.**

- `adb install -r` succeeded: versionCode 2016187942 → 2016188078, `firstInstallTime` kept, same
  signer.
- First launcher launch, observed for 45 s: no dialog, no crash, `uBlock Origin startup ready:
  Ready(installed=true, enabled=true)`.
- Force-stop, then a second launch: the same, clean.

**C. After the upgrade:**

- the suggestions switch is ON;
- DoH shows Max Protection with Quad9 (No Filtering), and Gecko has mode 3 with the Quad9 URI;
- the bookmark is present;
- uBO 1.75.0 is active and AMO-signed, and its selection still includes `dpollock-0`;
- the app reports 157.0-1, build 20261002210000.

The upgraded profile keeps Beta 3's uBO selection, so the cookie lists are not turned on (see (a)).

On rc2 the same test failed in phase B: the default-browser system dialog appeared
(`rc2-intermediate/upgrade-rc2/32-B-first-launch-45s.png`).

### (f) Add-on re-enable (LW-M7-19)

On the same profile and in the same app process (pid unchanged):

- **Disable.** uBO was disabled through AddonManager. Afterwards `isActive` was false, the policy was
  inactive, and on example.org both elements were visible and the fetch resolved.
- **Enable, no restart.** `isActive` and the policy were true, and the rules applied again within 7.1 s.

The bug was `_updateAddonDisabledState` in addon-state-durability (`isDisabled = undefined` for an ordinary add-on), fixed in `7dc5204f`. The stale 157 build from `d0c4e13d` lacked the fix (`../unit-tests/README.md`). rc1 to rc3 all contain it, and this is the first on-device confirmation.

## The two defects

### rc1: empty WebGL/canvas permissions list after a cold start (fixed in `751f5950`)

Graphics acceptance failed at `Visible Fenix control did not appear: origin_permission_pending_webgl`,
3 of 3 times. Three runs are in `rc1-graphics-defect/runs/`, plus one direct runner run.

- **Symptom.** After the harness's process restart, the quiet notice's Review opened the dialog with no
  rows at all (`0237-failure-ui.png`), behind an error toast. rc2 of 153.4 passed the same step.
- **The tap.** At the tap the app logged `No listener for GeckoView:GetAllPermissions`.
- **Same process, later.** Opening the list from the site controls rendered it correctly
  (`diag/direct1-site-controls-list-populated.*`). So did any cold-start delay on that path
  (`diag/coldstart-permissions-list-rc1.json`).
- **Mechanism.** `GeckoViewStorageController.sys.mjs` is not loaded on a cold start
  (`Cu.isESModuleLoaded` false). GeckoViewUtils' lazy listener unregisters itself, imports the module,
  and only then registers the real handler. The dialog sent two `GetAllPermissions` in the same
  millisecond, and the second one found no listener.
- **Decisive test** (`diag/review-race-probe-rc1/results.json`). Without an extra permanent Gecko
  listener, the list stayed empty 2 of 2 times. With one injected through Marionette, it rendered
  2 of 2 times.
- **Fix.** The dialog loads one query at a time (`SerialRefresh`) and retries a failed load twice
  (`retryTransient`). There are 5 new unit tests; the dialog class passes 9/9 and the feature class 8/8
  (`fix/unit-tests/`).
- **Open.** Why 153.4 did not hit the window is not established. On Beta 3 the module is not loaded at
  session start either (`rc3/upgrade/phase-A.json`).

### rc2: default-browser system prompt (fixed in `6202ee6d`)

- **Not caused by the upgrade.** On a fresh profile, Beta 3 and rc2 both raise Android's role request
  on the 4th launcher cold start into a tab (`rc2-intermediate/default-browser-prompt-*`).
- **Source.** `HomeActivity.maybeShowSetAsDefaultBrowserPrompt()`, gated only by the
  `default-browser-prompt` FML defaults. `no-onboarding.patch` had said that onboarding was the only
  caller.
- **Fix.** `Settings.shouldShowSetAsDefaultPrompt()` is now constant false, and the four upstream
  "true" tests are inverted. `SettingsTest` passes 125/125 and `HomeActivityTest` 31/31.
- **Still available.** Settings > Set as default browser, which is a user action.

## Gates for the two patch fixes

For each fix commit, `check-patchfail.sh --targets=android`, `lint-patch-scope`, `check-patch-order`
and `board.py --check` / `--check-scope` all pass (`fix/gates-751f5950/`, `fix/gates-6202ee6d/`). The
unit tests ran in the build image against the rc build tree.

## Not run or not shown

- No physical device, no ABI other than x86_64, and no release-key signing.
- No `--strings-locale` sweep, and no full Fenix unit suite. Only the four affected test classes ran.
- No real-site cookie banner: the reason is in (a).
- The pcaps and AVDs are not archived. They remain on the build host under
  `~/redoubt-artifacts/release-157/acceptance/{runtime,final,rc3}/work/`.
- rc2's full harness run (`rc2-intermediate/exit-status-rc2.jsonl`) is kept only as a summary. Every
  check was repeated on rc3.
