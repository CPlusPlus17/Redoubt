# 153.4.0esr release candidate 2 (rc2): build and runtime verification, 2026-10-02

## What this candidate is

| | |
| --- | --- |
| Source | `0a134441b77a888f365e81da02beee71d6e3b9c4` (`android/esr-153.4`, clean worktree) |
| Tree | a fresh `make dir TARGETS=android` at that commit. Nothing was hand-edited (`build/commands.log`) |
| Gecko | 3 ABIs built from new objdirs in one `android-fat-aar.sh` run. `MOZ_BUILD_DATE=20261002044800` is pinned and `buildid.h` matches in all three |
| Fat AAR | `geckoview-default-omni-153.4.20261002044800.aar`, sha256 `a7603eb6…bb61` |
| APKs | release variant, R8, unsigned. All four hashes are in `build/SHA256SUMS.apk` |
| x86_64 unsigned | `1ac3b01d9716ed5c53e7510ba8ba609c6bac2bd6dc6988192bdf3770124d95e8` |
| x86_64 installed | `77348e7d72bb4183adfec9cf79236d726280c0cd6a8666e8d507b6d6f495af83`, signed with the stage-C throwaway key (cert `31e9a40f…b760`), not the release key |
| versionCode | 2016187942. Beta 2 is 2016184438; the first 153.4 candidate is 2016187910 |

`apk-identity.txt` has the full record. Every device result below is bound to installed sha256
`77348e7d…af83`; `smoke/exit-status.jsonl` records that hash and the harness hash for every run.

The candidate contains all three fixes made after stage C:

| Fix | Commit | In the APK |
| --- | --- | --- |
| about:config under 153.4's baseline CSP (LW-M4-09) | `1770f028` | `config.js` md5 `749f7860…`, `config.xhtml` md5 `bd20ae6c…` in omni.ja, both equal to upstream. No inline `on*` handler remains |
| uBO readiness across AMO updates and launcher cold starts (LW-M3-07) | `388df549`, `885757d8` | uBO 1.75.0 is pinned, and the bundled xpi sha256 `5b744158…a5287` equals the pin |
| WebGL/canvas session lifetime in the graphics harness | `1d4d87ac` | harness only; `CanvasPermissionTest.kt` is not in the APK |
| `--check-launcher-start` | `0a134441` | harness only |

The tree was compared with the stage B tree, which the uBO fix had edited in place, using
`diff -rq` (`build/tree-vs-stageB.diffq`). In source, only `config.js`, `config.xhtml` and
`CanvasPermissionTest.kt` differ. The rest are build caches and `.orig` files. The repository
gates pass on the source commit (`build/gates/`): `check-patchfail --targets=android`
(153.4.0esr), `lint-patch-scope`, `check-patch-order`, `board.py --check-scope` and `board.py --check`.
`android-brand-check.py` passes on the tree. `test-android-smoke.py` ran 52 tests, all OK.

## Conditions

There is one emulator: emulator-5584, android-30 `default` x86_64 (no GMS), swangle. The harness
booted it from a fresh AVD in `build/rc2/runtime/work` with `-dns-server 9.9.9.9 -tcpdump`.
AMO was reachable. There was **no Retry priming and no iptables**. Every check ran on a fresh
profile, because the harness wipes app data, unless a row below says otherwise. The emulator was
shut down at the end.

## Verdict

> **Later run (same day), [`final-acceptance/`](final-acceptance/README.md):** every check rerun on the same
> rc2 APK with the committed harness (`11fd562e`), fresh profile each. 14 PASS, including the full graphics
> acceptance (161 checks, private grants, frames, lifetimes) twice, `--check-search` and `--check-launcher-start`.
> Beta 2 FAILs `--check-launcher-start` as the negative control. First-run and Remote Settings are expected red (E12).
> `--check-no-suggest` still FAILs, on HTTP/2 keep-alive-sized records on connections opened before typing.
> The section below is the original record.

**Not fully green.** The three product defects that stage C found are fixed on device:
about:config, launcher cold start, and the uBO update race. The pref audit and the Mullvad upgrade
behave as expected. Three device checks still fail on a fresh profile, and the evidence says the
harness causes at least two of them. Whether the third is the product's or the harness's is **not
established**.

| Check | Exit | Result | Evidence |
| --- | --- | --- | --- |
| `--check-launcher-start` | 0 | PASS. Fresh profile ready 5.7 s after START; restart ready 1.4 s after START. No dialog after 45 s. AMO had no newer uBO | `smoke/check-launcher-start/` (logcats and UI dumps for both phases) |
| `--check-aboutconfig` | 0 | PASS. 30 rows; an edit through the page's toggle survives a restart (stage C: 1, 1) | `smoke/check-aboutconfig/` |
| `--check-ubo-preinstall` | 0 | PASS. Bundled-list script blocked on first navigation. 1.75.0, `signedState` 2 | `smoke/check-ubo-preinstall/` |
| `--check-ubo-lifecycle` | 0 | PASS. Disable, restart, remove and APK reinstall all pass | `smoke/check-ubo-lifecycle/` |
| `--check-ubo` | 0 | PASS | `smoke/check-ubo/` |
| `--check-update-privacy` | 0 | PASS. Row compiled out; no update-host traffic | `smoke/check-update-privacy/` |
| `--check-https-only` | 0 | PASS | `smoke/check-https-only/` |
| `--check-strings` | 0 | PASS. 234,764 rows, 0 unexplained; 36 screen stops, 0 branded | `smoke/check-strings/` |
| `--check-no-gms`, `--check-no-adjust` | 1 | Both PASS. The run's exit 1 comes from the baseline it also runs: webgl, as below | `smoke/static-no-gms-no-adjust/` |
| baseline: https-only, page-load http/https, video, getusermedia, extension, pref-dump | 1 | all PASS, in 3 of 3 runs | `smoke/baseline-smoke*/`, `smoke/static-no-gms-no-adjust/` |
| baseline: **webgl** (graphics acceptance) | 1 | **FAIL, 3 of 3 runs.** Harness defect A in 2 runs. The 3rd failed earlier, on a quiet "Review" tap (defect C) | as above, `*-summary.json` + `graphics-acceptance.tar.xz` |
| `--check-search` | 2 | **harness error**: address bar not found (harness defect B) | `smoke/check-search/` |
| `--check-search` after one tap on the uBO notice's OK | 0 | PASS. `noai.duckduckgo.com`, no partner parameter, 4 engines as configured | `smoke/check-search-notice-ack/` |
| `--check-no-suggest` | 2 | **harness error**: same as defect B | `smoke/check-no-suggest/` |
| `--check-no-suggest` after the notice's OK, then 0, 4 and 10 min idle | 1, 1, 1 (and 2, 2 address-bar flakes) | **FAIL**. Every red is uBO filter-list traffic during the typing window (`cdn.jsdelivr.net`, `librewolf.dev`, then `ublockorigin.github.io` alone). No search-suggestion host is contacted, there is no sponsored traffic, the switch reads OFF and the OFF→ON→OFF round trip passes | `smoke/check-no-suggest-*` |
| `--first-run-capture` | 1 | expected red (E12). 91 events | `smoke/first-run-capture/`, `first-run-host-comparison.json` |
| `--check-no-remote-settings` | 1 | expected red (E12). 7 events to the 3 Remote Settings hosts | `smoke/check-no-remote-settings/` |

### Harness defect A: the tab-counter menu selector (webgl)

The graphics acceptance now gets past the lifetime check that stage C failed on: 100 checks pass,
including `remembered-exceptions-survive-process-restart`. It then stops at
`tab_menu("New private tab")`. `scripts/android-graphics-smoke.py:679` clicks
`text="New private tab"`, but Fenix's Compose toolbar menu exposes that item only as
`content-desc`: `PopupToMenuItemsMapper.kt` uses `clearAndSetSemantics { contentDescription }`,
and the file is byte-identical in 153.0 and 153.4. The UI dump shows it
(`content-desc="New private tab"`, `text=""`). No run on any build had reached this step before,
so the defect is older than this rebase. **The harness was not changed.**

### Harness defect B: the first-run "uBlock Origin was added" sheet (search, no-suggest)

On a fresh profile the uBO-installed sheet covers the toolbar (`diag/fresh-home/08s.png`).
`check_search` takes a single UI dump and `check_no_suggest` waits a fixed 8 s, and neither
dismisses the sheet. The graphics harness already acknowledges it with `ubo_added_notice()`.
Stage C missed this because it ran these checks on primed profiles. One tap on the sheet's OK,
which is a real user action and not Retry priming, is enough for `--check-search` to pass.

`--check-no-suggest` then fails for another reason. The harness force-stops and restarts the app,
and uBO runs its asset updater `autoUpdateDelayAfterLaunch` = 37 s after every launch (uBO 1.75.0
`js/background.js:49`, `js/start.js:520`). That falls inside the check's 60 s typing window. On a
young profile there is always a list or diff patch to fetch (`ublockorigin.github.io`). The capture
contains no suggestion endpoint, and the only host in the 10 min run is `ublockorigin.github.io`
(`smoke/check-no-suggest-settled/`). The harness counts this traffic as "typing traffic".
Stage C's primed profile happened to pass on retry.

### Defect C, NOT ESTABLISHED: the quiet "Review" snackbar action sometimes opens nothing

> **Later finding (same day), [`defect-c/`](defect-c/README.md):** this is a harness defect, not a product
> defect. The tap landed on a soft keyboard that stayed on screen after the private URL was typed; it covers
> the snackbar but is invisible to uiautomator. With the keyboard closed, Review opens the dialog in private
> tabs on rc2 and on Beta 2. Harness fix `f7f519f6`: graphics acceptance on the rc2 APK passes 3 of 3 runs.
> The section below is the original record.

Defect A was worked around in a **diagnostic-only** copy of the harness
(`diag/graphics-tab-menu-diagnostic.diff`, one line: click by `description=`). The copy was run
from a scratch directory and **not committed**. Three such runs (`smoke/DIAG-baseline-tabmenu-desc*`)
reach 104 checks and then **all three** fail the same way. In the new private tab, the harness taps
the snackbar's "Review" action (`snackbar_action`, text `Review`).
The snackbar disappears and `origin_permissions_dialog_list` never appears. The full logcat of the
third run (`diag/DIAG-r3-logcat.txt.gz`, tap at 09:39:14.45 device time) shows no exception or
fragment error around the tap. The same tap in normal browsing worked 33 times out of 34 across
all six graphics runs. The one failure was in `baseline-smoke`, after "canvas ask".

The action is `OriginBoundPermissionsDialogFragment.show(parentFragmentManager, tab)`
(`canvas-webgl-permissions.patch`, `BaseBrowserFragment.kt` hunk). That function returns silently
when `manager.isStateSaved` or when a fragment with its tag still exists. The snackbar's
`findTabOrCustomTab(tabId)` also does nothing when the tab is gone. Any of the three would give
exactly this silent no-op. It may be a product defect in LW-M7-14's private-browsing quiet path, or
a tap that lands while the snackbar is animating out. This run did not establish which one. Beta 2
cannot be compared here: its fresh profile stops at the uBO dialog, and no earlier run reached this
step.

## Pref audit (E4)

These are the official scripts, run on a fresh profile against the rc2 APK (`pref-audit/`):

- `android-pref-audit.sh` against the committed baseline exits **0**: 0 violations and 1 NOTE,
  `librewolf.webgl.prompt` (false in the baseline, true at runtime; not a must-lock key).
- `generate-android-pref-baseline.sh` exits 0. Its diff from the committed file is exactly that one
  row (`pref-audit/baseline-diff.out`), which is what was expected. `git checkout` restored the
  committed `expected-prefs.txt`. The row belongs to LW-M7-14 and needs a reviewer's decision, so
  it was not committed.

## First-run network capture (E11)

The capture has 91 events, and the app UID moved +23,648,813 B rx / +432,232 B tx
(`first-run-host-comparison.json`). Compared with the first 153.4 candidate, **no host is added**.
`addons.mozilla.org` is gone, because the pin now equals AMO's current uBO and nothing is
downloaded. `curbengh.github.io` is gone too. Compared with Beta 2, no host is added, and
`addons.mozilla.org` and `codeberg.org` are gone. `versioncheck-bg.addons.mozilla.org` and
`services.addons.mozilla.org` (the update check) remain. The rx bytes are twice stage C's. The
host list is not larger, so the extra bytes are attributed to uBO filter lists; this was not
measured per host.

## Mullvad DoH migration: Beta 2 → rc2 (`upgrade/`)

| Step | Result |
| --- | --- |
| Beta 2 fresh install (`01-*`, versionCode 2016184438) and launcher start | "uBlock Origin setup failed" (the Beta 2 defect; `02-*`), then Retry and OK on the uBO sheet |
| Settings → DNS over HTTPS → Max Protection → Mullvad (No Filtering) | `08-*` to `13-*`. Marionette: `network.trr.uri` is `https://dns.mullvad.net/dns-query` on the default branch, mode 3, and the DNS service's current TRR is Mullvad (`14-*.json`) |
| `adb install -r` rc2 | `20-*`, `21-*`: versionCode 2016184438 → 2016187942, and `firstInstallTime` is kept |
| First launcher start | The "DNS over HTTPS provider changed" dialog names dns10.quad9.net, at 15 s and still at 45 s (`22-*`, `23-*`). The log has `Replaced discontinued Mullvad DoH provider; mode MAX kept` once, and `uBlock Origin startup ready` 0.9 s after it (`24-*.logcat`). **No uBO dialog stacks over the DoH dialog**, which stage C's run 2 showed |
| OK, then a second launcher start | No dialog at 15 s or 45 s (`26-*`, `27-*`). `28-rc2-second-launch.logcat` has 438 lines and **no** `DohProviderMigration` line. uBO is ready 0.9 s after START |
| Gecko state after the upgrade (`29-*.json`) | `network.trr.uri` is `https://dns10.quad9.net/dns-query` on the default branch with no user value; `network.trr.mode` is 3; the current TRR is Quad9; mode 3. `example.org` loads (`30-*`) |
| DoH Settings (`34-*`, `35a-c`) | Max Protection is selected with Quad9 (No Filtering). The provider picker lists LibreDNS ×2, Quad9 ×2, DNS4All (default), Wikimedia DNS and Custom, with **no Mullvad** |

## Files

- `build/`: the command log, `make dir`, fat-AAR and APK logs, hashes, badging, the config-layer
  report, the tree diff, the brand check and the gate outputs.
- `smoke/`: one directory per harness run (`.err`/`.out`/`.json`). Each graphics acceptance
  artefact is packed into `graphics-acceptance.tar.xz`, with raw `.rgba` pixel dumps dropped; its
  summary and the tail of its runner log sit next to it. `exit-status.jsonl` records every run.
  `run-check.sh`, `batch1.sh`, `nosuggest-settled.sh`, `diag-run-check.sh`, `mn.py`, `trr.js` and
  `ui.sh` are the exact wrappers used.
- `diag/`: fresh-profile home-screen dumps, the diagnostic one-line harness diff, the harness
  unit-test output and source hashes, and the defect C logcat.
- `pref-audit/`, `upgrade/`, `first-run-host-comparison.json`.

## Not run or not shown

- No physical device, no ABI other than x86_64 on a device, no release-key signing.
- No `--self-test`, no `--strings-locale` sweep, and no Fenix unit-test run on this tree. The uBO
  fix's own run covered `fenix:testDebugUnitTest` on the same sources.
- The graphics acceptance never completed, so private-browsing grants, frames, and lifetimes after
  the restart step are unverified on rc2.
- No fresh-profile `--check-no-suggest` pass exists. A pass needs harness defect B fixed: dismiss
  the sheet, and leave uBO's post-launch updater out of the typing window or attribute its traffic.
