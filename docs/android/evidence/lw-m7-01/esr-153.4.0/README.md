# 153.4.0esr runtime verification (LW-M7-01), 2026-10-02

This directory holds emulator evidence for the stage B build of `android/esr-153.4`. The repository
was at `d0ae91de` (settings `3db3803`) when it was taken. Every result here is bound to one x86_64
APK, and the previous beta candidate was rerun under the same conditions for comparison.

**The APK predates later patch-byte changes.** It was built from the stage B tree, made by
`make dir` at `3777a915` (`build/commands.log`). Patch bytes changed after that: `d0ae91de` and
`d91aab7d` (Android Components test hunks in `extension-update-controls`, `firefox-suggest-data`,
`global-privacy-controls`, `firefox-suggest-policy` and `l10n-strings`), `3d801454`
(`session-cleanup.patch` context refresh, no change lines), and, after this evidence, the
about:config, uBO and harness fixes. Results here describe that APK, not a later tree. The rebuilt
candidate, made from a committed tree, is in `rc2/`.

## Verdict

| Area | Result |
| --- | --- |
| Mullvad DoH migration (upgrade from Beta 2) | **Works as designed.** The dialog appears once. Afterwards `network.trr.uri` is `https://dns10.quad9.net/dns-query` and `network.trr.mode` stays 3. Settings shows Max Protection with Quad9 (No Filtering) selected, and Mullvad is gone from the picker. A second launch shows no dialog. A fresh install shows no dialog. |
| Five approved pref changes | **All five confirmed at runtime** (`diag/new-153.4-approved-prefs-runtime.json`). |
| Runtime pref audit (E4) | **Audit exits 0.** The generator also exits 0. The regenerated baseline differs from the committed one in one row, `librewolf.webgl.prompt` false→true. That row predates this rebase: it comes from LW-M7-14 (`canvas-webgl-permissions.patch`, 2026-09-09), which Beta 2 already shipped. Neither the five approved changes nor Gecko 153.0→153.4 explains it, so **the regenerated file was NOT committed** (see below). |
| First-run capture (E11, DNS 9.9.9.9) | Compared with Beta 2 under identical conditions: `codeberg.org` is removed and nothing is added except `curbengh.github.io`, a uBO filter-list mirror. `librewolf.dev` appears in **both** builds. Compared with the 2026-09-08 beta-1 final candidate, 13 hosts are added, all from uBO's first-run list fetch and its AMO update check. That candidate had no uBO. |
| Smoke suite (E3) | **Not green. Four defects were found. Three already exist in Beta 2 and one is a 153.4 regression.** Details below. |

### Defects found (each with a Beta 2 control)

1. **REGRESSION in 153.4: `about:config` renders 0 rows.** `check-aboutconfig` FAILs on the new
   build (`smoke/check-aboutconfig-primed*/`) and PASSes on Beta 2 in the same session and
   environment (`smoke/beta2-check-aboutconfig-primed/`: 30 rows, the edit survives a restart).
   The page shows a permanent spinner (`diag/new-aboutconfig-manual.png`).

   Root cause, measured and read from source: in 153.4 `Document.cpp` (~:3797) applies
   `kBaselineSystemCSP` (`script-src chrome: resource: moz-src:`) to every system-principal
   document. In 153.0 it applied only to `chrome:` URIs. GeckoView's `about:config`
   (`mobile/shared/chrome/geckoview/config.xhtml`, identical in both trees) starts with an inline
   `onload="NewPrefDialog.init(); AboutConfig.init();"`, and the new CSP blocks it.
   `diag/new-153.4-aboutconfig-csp.json` lists all 13 blocked inline handlers, onload included.
   When `AboutConfig.init()` is called by hand, it loads 4,172 prefs.

   This breaks LW-M4-09 (about:config is reachable on a release build). The fix belongs in a
   patch that moves config.xhtml's inline handlers into config.js. No code was changed here.

2. **Already in Beta 2 and time-dependent: uBO first-run readiness fails on a fresh install.**
   On a fresh profile both builds show "uBlock Origin setup failed — Browsing is paused"
   (`diag/new-153.4-fresh-first-run.png`, `diag/old-153.0-fresh-first-run.png`). In the logs,
   `LibreWolfUboPreinstaller` reports `EventDispatcher$QueryException` about 1.2 s after
   `AddonUpdaterWorker` starts updating uBO.

   AMO has served uBO **1.75.0 since 2026-09-16**, and the APK pins 1.74.0. The immediate
   auto-update changes the extension while the version-bound readiness wait is still running.
   Tapping Retry recovers.

   With AMO blocked inside the guest, no update happens, the first run is clean, and the
   harness's own fresh-profile gates pass (`smoke/amoblocked-*`; see "Conditions").

3. **Already in Beta 2: a cold start to the home screen times out the uBO readiness gate.** This
   applies to launches from the launcher with no URL. After 30 s the log shows
   `TimeoutCancellationException: Timed out waiting for 30000 ms`, and the same "setup failed"
   dialog appears on **every** such launch. It reproduces on:
   - Beta 2 (`upgrade/control-fresh-old/04-*`);
   - the new build (`upgrade/control-fresh-new/04-*`);
   - the new build with uBO still at the pinned 1.74.0, AMO blocked (`diag/amo-blocked-control/02-*`, `03-*`);
   - after the upgrade (`upgrade/run2/11-*`, `15-*`; `upgrade/control-upgrade-doh-off/`).

   A cold start through a URL intent does not trigger it (`diag/amo-blocked-control/04-*`). That
   is why every harness run passed this point: the harness always launches with a URL.

   The cause is not established. The likely explanation is that GeckoView delays extension
   background startup until a page loads. The home screen loads none, so uBO's blocking listener
   never registers before the 30 s barrier expires.

   Separately, on a launcher cold start the uBO dialog stacks over the Mullvad dialog. This is
   visible on the first post-upgrade launch.

4. **Already in Beta 2, a harness/patch mismatch: the `webgl` graphics acceptance FAILs
   identically on both builds.** The record shows "Actual UI choice did not produce the exact
   expected engine value/lifetime" with `value 1, expireType 1`.
   `scripts/android-graphics-smoke.py:888` expects `expireType == 2` (`EXPIRE_TIME`) for a
   choice made without Remember. The patch writes `Services.perms.EXPIRE_SESSION` (= 1 in both
   trees' `nsIPermissionManager.idl`). See `diag/graphics-webgl-failure/` for new-primed,
   new-AMO-blocked-fresh and Beta 2-primed.

## Identity and environment

`apk-identity.txt` records the unsigned inputs and the installed copies:

- **New:** `fenix-x86_64-release-unsigned.apk`, sha256 `59666c2a…3bea3`, versionCode
  2016187910. The installed copy is `2d7db8ee…4f46`.
- **Old:** Beta 2, from `librewolf-android-apk-153.0esr-1-rc-unsigned` (source `764fc91c`, built
  2026-09-14), sha256 `503bfd79…955d`, versionCode 2016184438. The installed copy is
  `9b63f2ed…0427`. The same directory's `SHA256SUMS.signed` matches `~/redoubt-signed/`, the
  published beta.2.
- **Signing:** both installed copies are signed with **one throwaway key** (v2+v3, cert sha256
  `31e9a40f…b760`). Every non-META-INF entry matches its unsigned input. The release key was not
  used, and the throwaway key is not archived.
- **Emulator:** emulator-5584, AVD `lw-smoke`, android-30 `default` x86_64 (no GMS), swangle.
  It started from a fresh AVD in `build/runtime/work`, booted by the harness with
  `-dns-server 9.9.9.9 -tcpdump`. One emulator ran at a time, and it was killed at the end.
- **Harness:** `scripts/android-smoke.sh` sha256 `ee0458ec…ecf4`, unchanged.
  `diag/harness-source.sha256` has the other hashes. `python3 scripts/tests/test-android-smoke.py`
  ran 44 tests, all OK (`diag/harness-unit-tests.out`).
- **Run log:** every harness run is listed in `smoke/exit-status.jsonl` with its command, exit
  code, installed-APK hash and capture byte range. `smoke/run-check.sh` and `smoke/batch*.sh`
  are the exact wrappers used.

### Conditions (read before trusting a "PASS")

Defect 2 means no harness run on a fresh profile can get past the uBO dialog while AMO is
reachable. The checks were therefore run under three labelled conditions:

- **honest** — fresh profile, full network, DNS 9.9.9.9. Used for first-run capture, the Remote
  Settings window, the static APK checks, and the original baseline attempts (exit 2 at the uBO
  dialog).
- **primed** — the profile was prepared once by tapping Retry on the uBO dialog (uBO is then
  1.75.0), and later runs used `--keep-state`. Used for pref-dump, baseline, search,
  no-suggest, update privacy, about:config, strings and ubo, on both builds.
- **amoblocked** — inside the guest (adb root), `iptables` REJECT for 151.101.0.0/16,
  34.160.90.233, 2a04:4e42::/32 and 2600:1901:0:d29a::/64. The rules are in
  `diag/amo-blocked-control/iptables.txt` and were removed afterwards. This also blocks Fastly
  hosts other than AMO, including Remote Settings and jsdelivr, so **no network claim comes
  from this condition**. It was used only to get uBO 1.74.0 fresh profiles for: ubo-preinstall,
  ubo-lifecycle, the fresh baseline, the official pref generator and audit, and the defect-3
  controls.

## 1. Smoke suite, check by check (new build unless noted)

| Check | Condition | Exit / result | Evidence |
| --- | --- | --- | --- |
| baseline (`--emulator`) | honest | 2 — harness stops at the uBO dialog (defect 2) | `smoke/baseline-smoke*/` |
| baseline: https-only-interstitial, page-load-http/https, video, getusermedia, extension, pref-dump | primed, and amoblocked fresh | PASS | `smoke/baseline-smoke-primed/`, `smoke/amoblocked-baseline-smoke/` |
| baseline: webgl | primed, amoblocked; Beta 2 primed | FAIL on all three, identical (defect 4) | `diag/graphics-webgl-failure/` |
| `--check-ubo-preinstall` | honest | 2 (defect 2) | `smoke/check-ubo-preinstall/` |
| `--check-ubo-preinstall` | amoblocked | 0 — bundled-list script blocked on first navigation; pinned AMO-signed 1.74.0 active | `smoke/amoblocked-check-ubo-preinstall/` |
| `--check-ubo-lifecycle` | amoblocked | 0 — disable/restart/remove/reinstall all pass | `smoke/amoblocked-check-ubo-lifecycle/` |
| `--check-ubo` | primed | 0 | `smoke/check-ubo-primed/` |
| `--check-strings` (resource table + running-app traversal) | primed | 0 — 234,764 rows, 0 unexplained; 33 screen stops, 0 branded | `smoke/check-strings-primed/` |
| `--check-search` | primed | 0 — `noai.duckduckgo.com`, no partner parameter; DuckDuckGo No-AI, Startpage, Mojeek, Wikipedia (en) | `smoke/check-search-primed/` |
| `--check-no-suggest` (suggestions OFF→ON→OFF) | primed | first attempt 2 (address bar not found within 8 s); retry **0** | `smoke/check-no-suggest-primed*/` |
| `--check-update-privacy` | primed | 0 — row compiled out, no update-host traffic | `smoke/check-update-privacy-primed/` |
| `--check-aboutconfig` (release about:config edit/restart) | primed | **1, 1** (defect 1); Beta 2: **0** | `smoke/check-aboutconfig-primed*/`, `smoke/beta2-check-aboutconfig-primed/` |
| `--check-no-gms`, `--check-no-adjust` | static | both PASS (the run then exits 2 at the same uBO dialog) | `smoke/static-no-gms-no-adjust/` |
| `--first-run-capture` | honest | 1, expected red (E12) — 97 events | `smoke/first-run-capture/` |
| `--check-no-remote-settings` | honest | 1, expected red (E12) — 6 events to the 3 Remote Settings hosts | `smoke/check-no-remote-settings/` |

Branding: `--check-strings` passed. The running app shows the Redoubt fort and wordmark
(`upgrade/22-*.png`). `scripts/android-brand-check.py` was run in stage B
(`build/brand-check-tree.out`), not here.

## 2. Runtime pref audit (E4)

These are the official scripts, unchanged, run in the amoblocked condition on a fresh profile
(`pref-audit/`):

- `generate-android-pref-baseline.sh` exits 0. It writes one changed row; `baseline-diff.out`
  is the diff.
- `git checkout` restored the committed baseline afterwards. `android-pref-audit.sh` against
  the committed file exits **0**: 0 violations, 1 NOTE for `librewolf.webgl.prompt`, which is
  not a must-lock key. 20 of 137 must-lock keys are in the dump universe.
- The primed dumps of Beta 2 and the new build are **byte-identical**
  (`smoke/beta2-pref-dump-primed/*.out` and `smoke/pref-dump-primed/*.out`). The rebase moved
  none of the 58 audited rows.
- Gecko defaults: for each of the 58 keys, its declaration with 4 lines of context is unchanged
  between the 153.0 and 153.4 trees in `StaticPrefList.yaml`, `all.js`, `geckoview-prefs.js`
  and `mobile.js`.
- None of the five approved prefs is in the harness's 58-key list. They were therefore verified
  separately through Marionette (`diag/new-153.4-approved-prefs-runtime.json`):
  - `doh-rollout.provider-list` has no Mullvad.
  - `toolkit.telemetry.cachedClientID` is `c0ffeec0-ffee-c0ff-eec0-ffeec0ffeec0` and locked.
  - `browser.cache.disk.encryption.enabled` is true.
  - `librewolf.uBO.assetsBootstrapLocation` is the librewolf.dev URL.
  - `app.releaseNotesURL` is `https://github.com/CPlusPlus17/Redoubt/releases`.

**Not committed:** `expected-prefs.txt` stays as it is. Its only stale row belongs to
LW-M7-14, and updating it needs a reviewer's decision outside this rebase.

## 3. First-run network capture (E11)

The new build and Beta 2 were captured on the same AVD, both with DNS 9.9.9.9 and fresh
profiles. The comparison is in `first-run-host-comparison.json`.

| | Events | App UID rx / tx |
| --- | --- | --- |
| New | 97 | +11,438,595 / +223,972 bytes |
| Beta 2 | 102 | +11,072,011 / +247,385 bytes |

Raw windows are `pcap/first-run-capture.pcap.gz` and `pcap/beta2-first-run-capture.pcap.gz`.
Each is carved by byte offset from the run capture and has a global header added; the
`*-pcap-window.json` files record the offsets. The Remote Settings pcap was left out for size.
Its window offsets are in `pcap/check-no-remote-settings-pcap-window.json`, and the parsed
events are in its JSON.

Between the two builds, `codeberg.org` disappears, which is the bootstrap URL change.
`librewolf.dev` is contacted by both. In Beta 2 that contact presumably comes from uBO's own
asset list; the cause was not established.

The large difference from the 09-08 beta-1 final candidate (11 events) comes from uBO, which
that candidate lacked: AMO's update check and download (`services.`, `versioncheck-bg.`,
`addons.mozilla.org`) and roughly ten filter-list hosts. Android's own DNS ran over DoT to the
emulator resolver (tcp/853), so few DNS questions are visible in the pcap; hosts come from SNI.

## 4. Mullvad migration upgrade test

| Run | Directory | Steps and result |
| --- | --- | --- |
| Run 1 | `upgrade/` | Beta 2 fresh install. Retry on the uBO dialog. In the UI, Settings → DNS over HTTPS → Max Protection → Mullvad (No Filtering) (`15-*.png`). Gecko then reports Mullvad (`16-*.json`: `network.trr.uri` Mullvad on the default branch, mode 3, the DNS service's current TRR is Mullvad). `adb install -r` of the new build (`20-*`, `21-*`: versionCode 2016184438→2016187910, `firstInstallTime` kept). First launch shows "DNS over HTTPS provider changed" naming dns10.quad9.net (`22-*.png`); the log has `Replaced discontinued Mullvad DoH provider; mode MAX kept`. OK was tapped. The second launch shows no DoH dialog (`25-*.png`/`.xml`; but see defect 3, it was dumped at 20 s). Its logcat, `25-new-second-launch.logcat`, is **empty** (the capture caught nothing), so it is no evidence either way; the absence of the migration line on a second launch is shown by Run 2's `run2/16-new-second-launch.logcat` (369 lines, no `DohProviderMigration` line). The `trr.js` read (`26-*.json`) shows `network.trr.uri` = `https://dns10.quad9.net/dns-query` on the default branch with no user value, `network.trr.mode` = 3, and `example.org` loads. DoH Settings shows Max Protection with Quad9 (No Filtering) (`28-*.png`), and the picker no longer lists Mullvad (`29a-c`). |
| Run 2 | `upgrade/run2/` | Repeated with full logcat. The migration log line appears exactly once (`12-*.logcat`) and is absent on the second launch (`16-*.logcat`). The dialog appears once, and the second launch shows no DoH dialog (`15-*.xml`). The uBO timeout (defect 3) stacks over the DoH dialog on launcher cold starts. |
| Fresh install | `upgrade/control-fresh-new/` | No migration log line and no DoH dialog (`01.logcat`, `03-no-doh-dialog.*`). |

Gecko prefs were read through Marionette over GeckoView's debug config, the same mechanism the
harness uses (`smoke/mn.py`, `smoke/trr.js`). `about:config` was not used because of defect 1.
Fenix's `fenix_preferences` could not be read: release builds are not debuggable, so `run-as`
is refused. The UI and Gecko state stand in for it.

## What was NOT run or not shown

- No physical device; no ABI other than x86_64; no release-key signing.
- No `--self-test` negative controls and no `--strings-locale` sweep.
- No upgrade test with Increased Protection, a Default/Off mode while Mullvad was stored, or a
  custom Mullvad URI.
- Whether the dialog reappears after rotation was not tested. Only the Robolectric tests cover
  the recreation logic.
- Mullvad DoH was not verified to resolve after the upgrade (it is no longer used). Before the
  upgrade, `example.org` resolved through Mullvad in mode 3.
- The root cause of defect 3 is a hypothesis, not established.
- E12's effective allowlist comparison and the Fenix unit tests (stage B) were not repeated.
- A smoke-green run on a fresh profile with AMO reachable does not exist, for either build.
