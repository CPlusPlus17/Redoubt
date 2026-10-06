# Firefox 158 pre-rebase, against 158.0b3

Branch `android/firefox-158` (worktree `~/redoubt-artifacts/ff158/repo`),
scratch `~/redoubt-artifacts/ff158/work/`. One agent did this on the build
host on 2026-10-04. The goal is that release day (Firefox 158.0, 2026-10-09)
needs only a tarball swap, a re-check and a build, not a rebase.

**The version files still read `157.0`.** The patch texts on this branch
target 158 and no longer apply to 157. The bump to 158.0 happens on release
day, with the real 158.0 tarball. The steps are at the end of this file.

**Updated 2026-10-05** (section 6): main (157.0-2 stable, with the update
check's Settings-switch fix) and the two fix branches `fix/harness-sni` and
`fix/update-accept-language` are merged in; 158.0b3 is still the newest 158
source; check-patchfail, the fuzz-0 replay and the x86_64 compile and unit
tests were re-run on the merged branch. **`release.android` now reads `2`**
(from main's 157.0-2) and must go back to `1` on release day (section 5,
step 2).

**Updated again 2026-10-05** (section 7): a new Android patch,
`autofill-shadow-dom` (LW-M7-42), exists only on this branch. Android goes
from 42 to 43 entries and the total from 108 to 109 patch files.

**Updated 2026-10-06** (section 8): main 84a2015b is merged in. It brings the
video hotfix (isolation off), 157.0-3 and LW-M7-44. The newest 158 source is
now **158.0b4**. One android patch, `disable-157-cloud-features`, was
regenerated for b4. Both targets apply cleanly to b4, and an x86_64 build of
this branch on b4 passes `--check-video` (H.264 and MSE included) and
`--check-ubo-user-disable`. **`release.android` now reads `3`**, from main's
157.0-3. Release day still resets it to `1`.

Supporting files are in [`prebase/`](prebase/). Each claim below names the
file or command it rests on.

## Input

| | |
|---|---|
| tarball | `archive.mozilla.org/pub/firefox/releases/158.0b3/source/firefox-158.0b3.source.tar.xz` |
| size, sha256 | 809428684 bytes, `bbec367c0a3979f0a2e2f474c0dc1b76cb93ae970d7ed36cea217831e11feb39` |
| signature | `gpg --verify` against the `.asc`: good signature, made 2026-10-02 15:13:45 CEST, subkey `827E658608679618CD349F93678E455D76767AA3`, primary key `14F26682D0916CDD81E37B6D61B7B526D98F0353` (Mozilla Software Releases) |
| unpacks to | `firefox-158.0/`, where `config/milestone.txt` reads `158.0` |

`check-patchfail` ran in a scratch copy of the branch with `version` and
`version.android` set to `158.0b3`. The compile check below ran in another
scratch copy, with both files set to `158.0` and
`firefox-158.0.source.tar.xz` symlinked to the b3 tarball. That copy is
release day's layout with the beta's bytes in it. Nothing with a beta
version was committed.

## 1. What failed (check-patchfail, before)

Default fuzz, the gate the build uses (`prebase/patchfail-before/`):

| run | patches | rejected |
|---|---|---|
| `--targets=desktop` (common + desktop) | 68 | **11**: common `remove-openai`, `ui-patches/neterror-common`, `disable-data-reporting-common`, `xmas-common`; desktop `add-mojeek`, `hide-disabled-urlbar-suggests`, `pip-hide-ui`, `refresh`, `remove-pingsender-desktop`, `ui-patches/remove-branding`, `webgl-permission-desktop` |
| `--targets=android` (common + android) | 64 | **19**: the same four common, plus `no-adjust`, `no-onboarding`, `no-glean`, `no-gms`, `no-crashreporter`, `rs-blocker-android`, `no-suggest`, `ubo-preinstall`, `canvas-webgl-permissions`, `home-section-defaults`, `addon-state-durability`, `sync-opt-in`, `no-default-shortcuts`, `firefox-suggest-data`, `session-cleanup` |

`--fuzz=0` rejected 31 (desktop) and 29 (android) entries. That number
includes every patch that only needs fuzz, and cascades: a common patch that
rejects at fuzz 0 there also breaks the android entries after it.
`canvas-webgl-permissions` was in the android list only as a cascade. It
applied once `no-adjust` and its neighbours were rebased.

## 2. What changed

**Method** (the 157 rebase's): a scratch git repository of the pristine 158.0b3
tree, holding every file any patch touches (`prebase/tools/replay.py`). The lists
are replayed in order: common and desktop entries at patch's default fuzz,
android entries at `--fuzz=0`, the way `librewolf-patches.py` and the 157
rebase treated them. At each failing entry the patch was applied with fuzz,
the rejects were fixed by hand in the tree, and the patch was regenerated
from `git diff` of that one step. The header is kept and a "158 rebase" note
is added. Files with a `diff --git` style keep it; files without keep the
plain style. `/dev/null` deletions stay deletions.

| patch | what 158 changed | what the rebase did |
|---|---|---|
| `remove-openai` (common) | `toolkit/content/license.html` is gone; about:license is generated from `LICENSED_UNDER`, and the OpenAI paths are declared in `toolkit/components/ml/moz.build` | the license.html hunk became a moz.build hunk that comments out both paths. It still names them verbatim (the tripwire for `delete_from_tree`); the comment in `librewolf-patches.py` was updated |
| `ui-patches/neterror-common` | illustration wrapped in `ILLUSTRATION_ENABLED ? … : null` | same `src &&` and l10n change inside the new wrapper |
| `disable-data-reporting-common` | Stopwatch / TelemetryUserInteraction change is upstream verbatim; glean-sdk 70.2.0; glean-core 70.2.0 | the hunks for those three files dropped as already applied; mach.txt pin updated; `GLEAN_CORE_HASH_FIXUPS` carries the 158.0b3 pristine and patched sha256 (the fail-closed assert in the patcher passed on `make dir`) |
| `xmas-common` | `moz.build` now continues after `include("build/templates.mozbuild")` with a `MOZ_GENERATE_SBOM` block | `DIRS += ["lw"]` directly after the include; `lw/moz.build` hunk byte-identical |
| `add-mojeek` | icon `2cb3ddd3` added after `2bbe48f4` | same lines, same sorted place |
| `pip-hide-ui` | `player.xhtml` dropped `tabindex`, orders buttons by DOM in an `#ifdef XP_MACOSX` block | `piphide` inserted where its old tabindex put it |
| `remove-pingsender-desktop` | `shared.nsh` list moved, gained `notification-helper.exe` | same line removed |
| `ui-patches/remove-branding` | app-menu promo gained `closemenu="none"` | same image removed from both promos |
| `webgl-permission-desktop` | the CFR doorhanger after the canvas prompt was removed | WebGL prompt directly after the canvas prompt; fuzz-1/2 hunks regenerated at 0 |
| `hide-disabled-urlbar-suggests` | all three hunks upstream verbatim | **retired** (file and desktop.txt line deleted) |
| `refresh` | migrators keyed on `AppConstants.MOZ_APP_NAME`; string renamed `…-display-name-self = { -brand-product-name }` | **retired** |
| `no-adjust` | `InstallReferrerHandlingService(+Test)` gained a pairing-campaign check (`isUserPairingCampaignAttributed`) | both still deleted whole; the new pref stays, default false, with no reader in main/ |
| `no-onboarding` | `ContentRecommendationsFeatureHelper` lost its locale list to AC's `isContentRecommendationsLocaleSupported()` (adds en-IE, pl-PL) | helpers stay constant false; LW-M4-14's literal locale list gains en-IE, pl-PL |
| `no-glean` | import blocks moved (`HomeActivityTestRule`, `FenixOverlay`) | same imports removed, each checked unused |
| `no-gms` | `RequestHashProvider` moved to concept-integrity; `ClientUUID` → `ClientUuid`; `Llm.kt` already concept-typed; integrity files, `Push.kt`, Firebase doc edited | ClientUuid/FakeClientUuid/ClientUuidTest no longer touched (they no longer reference the deleted module); `Llm` gets the no-op client directly; deletions regenerated; `applicationScope` still dropped from `BackgroundServices`; Advertising-ID helpers removed before 158's new `TabGroupAccessPoint` enum. Test fix: 158's `BackgroundServicesTest.createBackgroundServices()` no longer passes the two removed parameters (section 4) |
| `no-crashreporter` | six deleted crash-service files edited; `Analytics.kt` builds a `gleanServerEndpoint` for the Glean crash service | deletions regenerated; endpoint block removed with the service. Compile fix: 158's `CrashContentView.bindCheckboxState()` goes with the checkbox. Test fix: 158's `CrashReporterControllerTest` Auto/Ask cases now assert nothing is shown or submitted (section 4) |
| `rs-blocker-android` | `make_request()` split into a logging wrapper and `_make_request()` | block moved into `_make_request()` |
| `no-suggest` | `defaultTopSitesBinding` → `defaultPinnedSitesBinding` | same `TopSitesRefresher` removal |
| `ubo-preinstall` | new reader-mode strings at the end of strings.xml | strings appended after them |
| `home-section-defaults` | `bookmarks` / `recent-explorations` gone from `sections-enabled`; Settings defaults both to false | only top-sites and jump-back-in flipped; `HomeSectionDefaultsTest` unchanged |
| `addon-state-durability` | comment in `uninstallAddon()` shortened | same change |
| `sync-opt-in` | `FxaAccountManager.start()` calls `syncManager?.initialize()` first | services guard put before it |
| `no-default-shortcuts` | `raw/initial_shortcuts.json` → `raw/default_pinned_shortcuts.json` (same bytes, blob `e318e7c`) | same emptying on the renamed file; LW-M7-30 `tree_paths` follows |
| `firefox-suggest-data` | Fenix dropped its `mozilla_appservices_merino` line; uniffi 0.31 → 0.32 | suggest dependency after the syncmanager line; the `remote_settings.kt` binding hunk regenerated with the uniffi 0.32 generator (section 4) |
| `session-cleanup` | `nsICookieManager.runInTransaction()` and `CookieStorage::RunInTransaction()` removed | the guard, its flag, the AutoRestore include and the xpcshell task that drove it removed |
| `disable-157-cloud-features` | — (fuzz 2 in Settings.kt) | regenerated at fuzz 0 |
| `search-config`, `canvas-webgl-permissions`, `global-privacy-controls` | — (fuzz 0, but at an offset inside res/) | hunk headers moved to in-order line numbers: an offset leaves `strings.xml.orig`, `secret_settings_preferences.xml.orig` and `nav_graph.xml.orig` in res/, and `packageReleaseResources` rejects them |
| `extension-update-controls` | — (offsets) | hunk headers moved to in-order line numbers, which the receipt replay of this hash-pinned patch requires |

Outside the patches: `assets/Dockerfile.android` (NDK r30, cmdline-tools
23.0/16111833, platform android-37.2, Temurin 17.0.20.1+1, no separate
`sdkmanager --licenses` layer, see its commit), `PATCH-SCOPE.md` (22 common
/ 42 android / 44 desktop-only = 108; `board.py --check-scope` agrees),
`tasks.yaml` (LW-M7-30 tree path), `librewolf-patches.py` (glean-core hashes,
one comment).

### After

| check | result |
|---|---|
| `check-patchfail.sh --targets=desktop` | exit 0, 66 patches, 30 hunks with fuzz, all in common/desktop entries, which the build applies at default fuzz (157.0 had 27) |
| `check-patchfail.sh --targets=android` | exit 0, 64 patches, 8 hunks with fuzz, all in common entries |
| `--fuzz=0` | desktop: 20 entries need fuzz (8 common, 12 desktop); android: 10 (the same 8 common, plus `webgl-prompt-default` and `canvas-webgl-permissions`, which fail only because `webgl-permission-common` is not applied before them in a fuzz-0 run) |
| in-order replay, android at `--fuzz=0` (fresh scratch repo) | all 42 android entries apply; none needs fuzz; 14 apply at an offset, none in res/ and none hash-pinned (`prebase/replay-android-final.log`) |
| `make dir TARGETS=android` (158.0 layout, b3 bytes) | exit 0; every fail-closed check in `librewolf-patches.py` passed (among them the OpenAI deletions and the glean-core hashes); no `.orig` under any res/ |
| `scripts/check-patch-order.py` | `patch order ok: 36/36 declared constraint(s) enforced across 2 target sequence(s); 148 shared-file pair(s) derived and classified.` No new shared-file pair. |
| `board.py --check`, `--check-scope` | ok (124 tasks; 108 patch files) |

### check-patch-order, re-measured

The checker derives which pairs share a file. It does not replay them. So
every one of the 148 pairs was replayed per shared file on pristine 158.0b3,
the way `_M157_ANDROID` was measured: list order, B moved directly before A,
and A moved directly after B (`prebase/tools/measure_order.py`, results in
`prebase/order-158b3.json`).

- Every pair applies in list order.
- 26 Android pairs are pair-sensitive (neither swap reproduces the list-order
  bytes). All 26 are declared `CONSTRAINTS` rows.
- 10 declared constraints are textually order-free on 158. Four of them were
  already order-free on 157 and are kept for their semantic reasons, as
  `check-patch-order.py` records. The others are `autoconfig-setEnv →
  profile-directory`, `firefox-in-ua → moz-configure`, `fpp-canvas-fix →
  webgl-permission-common` and `mozilla_dirs → xdg-dir` (all order-free here
  only because common/desktop apply at default fuzz), plus `no-glean →
  disable-157-cloud-features` and `ubo-preinstall → disable-157-cloud-features`.
  For those last two, LW-M7-40 declared a constraint because moving B before
  A rejects. That still holds on 158; only "A after B" is clean. No row was
  changed.
- One declared order-free desktop pair, `ui-patches/settings-redesign →
  ui-patches/website-appearance-ui-rfp` (`appearance.mjs`), produces
  different bytes when swapped. It does the same on **157**: list order and
  the swap give the same two hashes on 157 as on 158, so this rebase did not
  cause it. It is
  reported here and left alone. Neither patch was touched.

## 3. Newly default-on in Firefox 158 (release channel): reported, not decided

Method: every `*.fml.yaml` under mobile/android, with variable defaults
overlaid by `defaults` entries whose channel is release or unset, compared
between 157.0 and 158.0b3 (`prebase/tools/fmldiff.py`,
`prebase/nimbus-release-defaults-157-vs-158b3.txt`). Also Fenix
`Settings.kt` (`prebase/settings-kt-157-vs-158b3.diff`), `StaticPrefList.yaml`
(`prebase/staticpref-157-vs-158b3.txt`, made by `prebase/tools/spl.py`), `all.js` / `firefox.js`, URL
literals in mobile/android main sources (`prebase/new-urls-mobile-android-158b3.txt`),
Glean `pings.yaml` (no new ping) and the 111 new Kotlin main-source files
(`prebase/new-main-kt-158b3.txt`).

Fenix / android-components (Nimbus release values and Settings.kt):

| what | 157 → 158 | covered by our patches? |
|---|---|---|
| Nimbus `show-more-shortcuts.enabled` | false → **true** | **no**. Local UI: the shortcuts row shows an expand toggle instead of the "shortcuts library" button (`TopSiteState.kt`); no network use found there. `disable-157-cloud-features` already pins `enableAddShortcutsImprovement` (the Merino-icon sheet) to false. |
| Nimbus `merino-client` | feature removed | Pocket content recommendations now always go through the app-services Rust Merino client (`MerinoContentRecommendationsProvider`). **Covered**: `no-onboarding` keeps `isContentRecommendationsFeatureEnabled` false and the periodic refresh deleted. The only start call left is `HomeSettingsFragment`'s, behind the same false flag (`DummyProperty`), as on 157. |
| Nimbus `media-notification-improvements` | feature definition removed (release had it on) | media-notification UI; no privacy angle found |
| Nimbus `tab-reload-cover` | new, default false | n/a |
| `homescreen.sections-enabled` | bookmarks, recent-explorations removed; Settings defaults both false | **covered**, see `home-section-defaults` |
| `Settings.isUserPairingCampaignAttributed` | new, default false | writer deleted by `no-adjust` |
| `Settings.shouldUseBottomTabStrip`, `isMenuCustomizationEnabled`, `showTabGroupsInMenu` | new, all default false | n/a |
| Wayback Machine "View archived version" on error pages (`archive.org/wayback/available` from `lowMediumErrorPages.js`) | present on 157 too, `isWaybackMachineEnabled` default false, Nightly-only toggle | not default-on |

Gecko prefs whose release value changed to on, or changed on Android (from
`StaticPrefList.yaml`, `all.js`):

| pref | 157 → 158 | in our settings? |
|---|---|---|
| `privacy.restrict3rdpartystorage.heuristic.navigation` | Android false → **true** (no longer per-platform) | **yes**, decided: kept off on Android (owner decision 2026-10-04), `android.cfg` `defaultPref(..., false)`, Redoubt-settings `990c367` |
| `privacy.restrict3rdpartystorage.heuristic.recently_visited` | Android true → false | **no** (restricts more); pinned false anyway by owner decision 2026-10-04, Redoubt-settings `008b87f` |
| `image.jxl.enabled` | Nightly-only → **true** | **no** (new image decoder exposed to the web) |
| `dom.webnotifications.navigate.enabled` | false → **true** | no |
| `dom.performance.deliverytype.enabled` | false → **true** | no |
| `webgl.out-of-process.enable-ahardwarebuffer` | false → **true** (Android) | no |
| `network.dns.mru_to_tail`, `layout.css.calc-typed-arithmetic.enabled`, `layout.disable-pixel-alignment`, `print.experimental.skpdf`, `accessibility.tagged_pdf_output.enabled` | Nightly-only → true | no (no privacy angle found) |
| new: `dom.document.domcontentloaded.synchronous.enabled`, `network.ipc.reparse_deserialized_uri`, `layout.css.quirks.final-uri-check`, `browser.contentanalysis.interception_point.clipboard_copy.plain_text_only` | — → true | no |
| `media.webrtc.send_mlkem_keyshare` | true → false | (less, not more) |
| `extensions.formautofill.creditCards.cvv.enabled` | false → true | covered: `common.cfg` sets `extensions.formautofill.creditCards.enabled` false |
| `browser.pageextractor.youtube.enabled` (all.js) | false → **true** | **no**. It is a page-extractor knob for the AI features; whether Android reaches it was not traced |

Desktop only, from `firefox.js`, for the desktop maintainer:
`browser.smartwindow.smartformfill.enabled` false → true (covered:
`desktop.cfg` sets it false), `browser.smartwindow.agent.toolbar.enabled`
false → true (not covered, behind `browser.smartwindow.enabled` = false),
and the New Tab discovery-stream sections are opened to 9 more regions and 5
more locales (`discoverystream.sections.region/locale-content-config`).

New endpoints: no new URL literal in mobile/android main sources apart from
`web.archive.org` (the off-by-default Wayback page above) and test-only or
comment links. No new Glean ping (`pings.yaml` names are identical). Of the
111 new Kotlin main files, a grep for request/fetch/HTTP constructs hits only
`browser/reloadcover/TabReloadCoverFeature.kt`, and that hit is an
`ImageLoadRequest` for a local thumbnail, behind `tab-reload-cover` (default
false). This is a grep, not a capture; the release-day first-run capture is
the check.

## 4. Compile check

Run once, from a fresh `make dir TARGETS=android` of this branch. The tree was
under `work/buildrepo/librewolf-158.0-1`, built with version 158.0 in the
scratch copy and the b3 tarball. Image `localhost/librewolf-android-build:fx158`
(`98e61be72eec`) was built from this branch's `assets/Dockerfile.android`.
158's configure requires exactly NDK r30 (`android-ndk.configure`), which the
`fx157` image does not carry; `fx157` was not tried. The run
used `MOZ_BUILD_DATE` 20261004120000 and `-j8`. memguard paused the `lw-*`
containers whenever MemAvailable fell below 8.25 GB; other CI on the host
pushed it as low as 0.3 GB once, while our container was paused
(`prebase/build/memguard.log`, `commands.log`).

| step | result |
|---|---|
| `android-fat-aar.sh --abis x86_64 --fat-host-abi x86_64` | ok: x86_64 Gecko 2180 s (peak 18.4 GB), merge pass 992 s |
| `android-apk.sh … --variant release` (`fenix:assembleRelease`, Kotlin `-Werror`), run 1 | **failed** in `:fenix:compileReleaseKotlin`: `CrashContentView.kt:98:17 Unresolved reference 'sendCrashCheckbox'` (`prebase/build/compile-1-kotlin-errors.txt`). This was the only diagnostic. Every other module, including the app-services Kotlin and the hand-placed uniffi bindings, compiled. |
| fix | `no-crashreporter`: 158's new `bindCheckboxState()` and its test go with the checkbox (commit "no-crashreporter: drop 158's crash-report checkbox state …") |
| run 2 (`--skip-gecko`) | `:fenix:compileReleaseKotlin` passes; `fenix-x86_64-release-unsigned.apk` produced. Its `libxul.so` is sha256-identical to the AAR input. |
| uniffi | `firefox-suggest-data`'s `remote_settings.kt` hunk regenerated with the 0.32 generator (`prebase/uniffi-regeneration.txt`). The other 21 checked-in binding files came out byte-identical to 158's. |
| run 3 (`--skip-gecko`, generated bindings) | `:remotesettings:compileReleaseKotlin` and `:fenix:compileReleaseKotlin` pass; APKs in `prebase/build/SHA256SUMS.apk` |

Runs 2 and 3 end with `android-apk.sh` exit 1 *after* Gradle succeeded:
the universal APK has `arm64-v8a`/`armeabi-v7a` directories (three AndroidX/JNA
`.so` files from prebuilt AARs) but `libxul.so` only for x86_64. That check
exists for 3-ABI release builds; on an x86_64-only compile check it is
expected. The x86_64 APK passed its own check.

Not run: armeabi-v7a/arm64-v8a, R8/minified release on device, the smoke
suite, the pref audit, the full Fenix suite and `board.py --check-fenix-tests`,
and any device or emulator test. This was a compile check.

### Targeted unit tests

`./mach gradle fenix:testDebugUnitTest --tests …` over every Fenix test class
the android patches touch and that exist after patching (41), plus
`CrashReporterControllerTest` and `ClientUuidTest`. That is 43 requested and
42 reported: `MetricsUtilsTest` has no `@Test` left by design (no-gms). Also
`:components:service-firefox-accounts:testDebugUnitTest` (sync-opt-in) and
`:components:feature-fxsuggest:testDebugUnitTest` (firefox-suggest-data):

| run | result |
|---|---|
| 1 | `:fenix:compileDebugUnitTestKotlin` failed: 158's new `BackgroundServicesTest.createBackgroundServices()` passes `push =` / `applicationScope =`, which `no-gms` removes (`prebase/build/unittest-1-kotlin-errors.txt`) |
| 2 | 530 tests, 4 failed: `CrashReporterControllerTest` (158 uses a real `Settings` with an Auto/Ask crash-report choice, which `no-crashreporter` turns into Never) |
| 3, after fixing both in their owning patches | **Fenix 42 classes / 530 tests / 0 failures; service-firefox-accounts 17 / 145 / 0; feature-fxsuggest 12 / 73 / 0** (`prebase/build/unit-tests.json`, JUnit timestamps included) |

### Receipt tests (hash-pinned patches)

`scripts/tests/test-{addon-state-durability,global-privacy-controls,session-cleanup}.py`
**fail on this branch**, as expected. `version.android` reads 157.0, so they
replay the 157.0 receipts against patch texts that are now 158 texts.
Release-day step 4 replaces those receipts. As a dry run, all six receipts were
recaptured with `release-157.0/receipts/recapture.py` into a scratch copy with
`version.android` 158.0 and the b3 tarball. All six replay exactly at
`--fuzz=0` and match the built tree (`prebase/receipts-trial-recapture.log`),
and all six receipt tests pass there. Getting there needed one test change:
`test-session-cleanup.py` now expects 8 cookie tasks, not 9.

Also seen, and not caused by this branch: `docs/android/evidence/lw-m7-30/check-source.py`
fails with "patch hash mismatch" on `main` as well (its pinned patch hash
predates the current `no-default-shortcuts.patch`; not investigated further). `test-android-signing.py` and
`test-android-version-code.py` exit 2 on both `main` and this branch.

## 5. Release day (158.0, 2026-10-09)

Firefox 158.0 is due on 2026-10-09. The release watcher opens the issue once
the source tarball is on archive.mozilla.org.

1. **Fetch and verify** `releases/158.0/source/firefox-158.0.source.tar.xz`
   and its `.asc` (REBASE.md §3). Check the primary key fingerprint is
   `14F26682D0916CDD81E37B6D61B7B526D98F0353`. Record size and sha256.
2. **Bump** `version` and `version.android` to `158.0`, and **reset
   `release.android` from `3` to `1`** (it came in as `3` with main's 157.0-3,
   and before that as `2` with 157.0-2;
   158.0-1 is the first build of 158). `release` stays `1`. The versionCode is
   derived from the build date, so the reset does not make it go down; the
   build date in step 7 does that job.
3. **Re-check the patches** against the real tarball:
   `./scripts/check-patchfail.sh --targets=desktop` and `--targets=android`
   (both must exit 0), plus the `--fuzz=0` runs. Compare their reject lists
   with section 2's "After" table (section 8 confirms them on b4). Anything new between b3 and 158.0 gets the
   same in-order fuzz-0 treatment (`prebase/tools/replay.py`). Then run
   `python3 scripts/check-patch-order.py`,
   `python3 docs/android/board.py --check` and `--check-scope`. Diff
   `third_party/rust/glean-core/src/{lib.rs,core/mod.rs}` and
   `.cargo-checksum.json` between b3 and 158.0. If glean-core moved,
   `GLEAN_CORE_HASH_FIXUPS` must move with it; `make dir` fails closed if it
   does not.
4. **Receipts**: create `docs/android/evidence/lw-m7-01/release-158.0/receipts/`
   with `recapture.py` (the command in `release-157.0/receipts/README.md`,
   with `--objdir` pointing at the 158.0 `make dir` tree). Then all six
   `scripts/tests/test-*.py` receipt tests must pass. Also re-run
   `scripts/tests/*.py` as a whole.
5. **uniffi**: if app-services changed between b3 and 158.0, regenerate
   `firefox-suggest-data`'s `remote_settings.kt` hunk the same way (the
   command is in that patch's header and in `prebase/uniffi-regeneration.txt`).
   The 21 other binding files must come out byte-identical.
6. **Build image**: `localhost/librewolf-android-build:fx158` from
   `assets/Dockerfile.android`. Re-read its four 158 pins against the 158.0
   tree (`python/mozboot/mozboot/android.py`, `android-packages.txt`).
7. **Release build in CI on box B.** This is how 157.0-2 was built
   (`release-157.0-2/acceptance/run-37248744119/`). The workflow builds from
   `--ref main`, so the owner first merges this branch into `main` and pushes
   it; this branch is local-only until then. Dispatch:

       gh workflow run android-release.yaml --repo CPlusPlus17/Redoubt --ref main \
         -f mode=full -f update_check=true -f build_date=<YYYYMMDDHHMMSS UTC>

   `update_check=true` compiles the update check in with the committed
   `assets/update-check.android.pubkey` (the direct-APK shape). `build_date`
   must be **new and later than 157.0-3's `20261006090000`** (CI run
   37441476096; 157.0-2's was `20261005000000`), so the versionCodes go up, and not in the future (the workflow refuses that).
   Use one value for all ABIs; the workflow passes it to the fat AAR and the
   APK pass. Record the run id and inputs as for 157.0-2.

   A local build (optional cross-check) works the same way: fresh
   `make dir TARGETS=android`, then
   `make android-build` and `make android-package TARGETS=android` with
   `android_build_image=localhost/librewolf-android-build:fx158`,
   `--variant=release --disable-debug-signing --update-check`, one `--build-date` for all
   ABIs, and memguard running (the Beta 5 `build.sh` pattern,
   `evidence/lw-m7-41/migration/build/`). The universal-APK ABI check must
   pass this time.
8. **Tests**: the full `fenix:testDebugUnitTest` and
   `python3 docs/android/board.py --check-fenix-tests` (not run in the
   pre-rebase); the targeted classes of section 4 again.
9. **Acceptance**, as for 157.0-1 (`evidence/lw-m7-01/release-157.0/acceptance/`):
   `android-smoke.sh` on an emulator, the pref audit
   (`android-pref-audit.sh`, `must-lock.txt` regenerated against 158), and a
   first-run capture. The capture is where the section 3 items show whether
   anything is newly on the wire. Then the owner's decisions on section 3, then
   signing and publishing (SIGNING.md: the owner signs offline; nothing on
   this host signs a release). The acceptance should also check from the
   local update server's request log (`update-check/device-local/server-requests.jsonl`
   as in run 37248744119) that the update check sends **no `Accept-Language`
   and no `Accept`** (the `fix/update-accept-language` change; the existing
   probe does not assert this yet). `--check-update-privacy` now grades each
   connection by name (`fix/harness-sni`); this will be its first live run.
   Also run `--check-video`, which covers H.264, AAC and MSE since LW-M7-43, and
   `--check-ubo-user-disable` (LW-M7-44). Both passed on the b4 build in
   section 8. In the 158.0 tree, check again that
   `AndroidDecoderModule::IsJavaDecoderModuleAllowed()` still refuses isolated
   processes. Isolation stays off until it does not.
10. **Publish the update document after the release** (DISTRIBUTION.md,
    "Publishing an update document", steps 2-8). Only after the GitHub release
    `android-158.0-1` is public: `scripts/update-manifest.py generate` from the
    CI build's `output-metadata.json`, sign `latest.json` on the key machine with
    `sign-update-manifest.sh` (update-signing key, not the APK keystore),
    `update-manifest.py verify` on the build host, copy `latest.json` and
    `latest.json.sig` into `site/update/android/`, commit signed and push, then
    `update-manifest.py fetch --expect-tag android-158.0-1`. Until then, 157.0-2
    installs that turned the check on keep being told they are up to date.
    Keep the evidence as in `release-157.0-2/stable/`.
11. Desktop: the same tarball and steps 1-3 for `TARGETS=desktop`. This
    pre-rebase did not compile desktop.

## 6. Update, 2026-10-05: main and the two fix branches merged

**Source.** 158.0b3 is still the newest 158 source. On 2026-10-05
`archive.mozilla.org/pub/firefox/candidates/` lists `158.0b1`..`158.0b3`
candidates and no `158.0-candidates`; `/pub/firefox/releases/` lists
`158.0b1`..`158.0b3`. The b3 tarball was re-verified against the pinned
`assets/mozilla-release-key.asc` (main's, now on this branch): `VALIDSIG
827E658608679618CD349F93678E455D76767AA3 … 14F26682D0916CDD81E37B6D61B7B526D98F0353`.
Nothing changed between b3 and what this branch was rebased against, so
sections 1-4 stand.

**Merges** (signed merge commits, no conflicts):

| merged | what it brings | effect on the 158 patches |
|---|---|---|
| `origin/main` (157.0-2 stable) | update check: signed endpoint, versionCode rule, the Settings-switch fix (`b86c1a0c`); release watcher; box B CI; pinned Mozilla key; Makefile `fetch` verifies against it | the only patch main changed since the branch point (`39d159ca`) is `update-check.patch`; this branch had not touched it. `canvas-webgl-permissions`, `addon-state-durability`, `no-onboarding` and the other 158-rebased patches have no change on main since the branch point, so they keep their 158 text |
| `fix/harness-sni` | `--check-update-privacy` judges connections by name | scripts and docs only |
| `fix/update-accept-language` | `update-check.patch` sends `Accept-Language: ""` / `Accept: ""` so Gecko drops both | Fenix-only |

One patch fix after the merge: main's `update-check.patch` put its
`HomeActivity.kt` hunk at 855; in order on 158 it lands at 862 (the 158 text
of that file has 7 more lines above `onResume`). The header was moved, the
content is unchanged, and a "158 REBASE" note was added to the patch header.
It applied at an offset before; now it applies exactly.

**Re-checks on the merged branch, 158.0b3** (`prebase/merge-2026-10-05/`):

| check | result |
|---|---|
| `check-patchfail.sh --targets=desktop` | exit 0, 30 hunks with fuzz (as in section 2) |
| `check-patchfail.sh --targets=android` | exit 0, 8 hunks with fuzz, all in common entries (as in section 2) |
| `--fuzz=0`, both targets | the same 20 desktop / 10 android entries as section 2's "After", byte-for-byte the same reject list |
| in-order replay, android at `--fuzz=0` (`replay.py`, fresh tree) | all 42 android entries apply, none needs fuzz; 13 at an offset (was 14; `update-check` is now exact), none in res/ |
| `check-patch-order.py` | `patch order ok: 36/36 … 148 shared-file pair(s)` |
| `board.py --check`, `--check-scope`, `lint-patch-scope.py` | ok (124 tasks; 108 patch files) |
| `scripts/tests/test-android-smoke.py`, `test-update-manifest.py`, `test-firefox-release-watch.py` | 89, 15 and 67 tests, OK |

**Compile check (incremental).** The merge changes no Gecko file: comparing
the merged replay tree with the section 4 build tree over every file a patch
touches or deletes differs in exactly the 7 update-check files
(`replay-vs-build-tree.txt`). Those 7 were copied from the replay into the
section 4 tree, together with main's `android-apk.sh` (new `--update-check`),
and `fenix:assembleRelease` was re-run with `--skip-gecko --update-check`
(image `fx158` `98e61be72eec`, build date 20261004120000, memguard on;
`build-apk-merge.sh`):

| step | result |
|---|---|
| run 4, `--skip-gecko --update-check` | `:fenix:compileReleaseKotlin` and `BUILD SUCCESSFUL in 17m 47s` (Kotlin `-Werror`). `libxul.so` sha256-identical to the AAR input and to run 3. The committed update-check public key is in `classes2.dex` (1 hit), so the check is compiled in. `android-apk.sh` exits 1 afterwards on the expected universal-APK ABI check (section 4). APKs: `SHA256SUMS.apk` |
| targeted unit tests (`test-merge.sh`): section 4's list with `org.mozilla.fenix.lw.*` and `SettingsFragmentTest` added | `:fenix:compileDebugUnitTestKotlin` passes; **Fenix 44 classes / 563 tests / 0 failures**, run 2026-10-05, among them `UpdateCheckerTest` 12, `UpdateCheckSwitchTest` 4, `DohProviderMigrationTest` 9, `SettingsFragmentTest` 25. `service-firefox-accounts` and `feature-fxsuggest` were Gradle UP-TO-DATE (no input changed); their results are run 3's (17 / 145 / 0 and 12 / 73 / 0). `unit-tests.json`, `unit-tests-gradle.txt` |

Not run here: the JVM harness `test-update-check-jvm.sh` (it builds against a
patched 157 tree; the Robolectric run above covers the same tests on 158), any
device or emulator run, desktop.

## 7. New patch on this branch, 2026-10-05: `autofill-shadow-dom` (LW-M7-42)

`patches/android/autofill-shadow-dom.patch` is the last `android.txt` entry.
It makes login fields inside open shadow roots, such as reddit.com/login's,
reach Android Autofill. The fix is a fallback in
`GeckoViewAutoFillChild.onFocus`: GeckoView JS, packaged in omni.ja. The
patch was written against 158.0b3, and **157 / `main` has no such entry**.
Whether to backport it is a separate decision.

A follow-up the same day narrowed the patch after an independent review. The
first version also registered email fields in open shadow roots with no
password field anywhere (newsletter, checkout), which upstream never does in
the light DOM. Now a non-password field qualifies only if its
shadow-inclusive FormLike holds a password field. The table is for the
narrowed patch.

| check (158.0b3) | result |
|---|---|
| `check-patchfail.sh` android / desktop | exit 0 / exit 0; the new patch applies exactly; 8 / 30 hunks with fuzz overall, as in section 6 |
| fuzz 0 | applies to pristine 158.0b3; no other patch touches the file |
| `check-patch-order.py`, `lint-patch-scope.py`, `board.py --check-scope`, `--check` | ok (109 patch files; 125 tasks) |
| Gecko pass, `android-fat-aar.sh --abis x86_64`, section 4's objdir and build date | ok, per-ABI pass 856 s + merge 1158 s; the AAR's and the APK's omni.ja carry the patched actor byte-for-byte (`8e799ac0…c03a`) |
| `fenix:assembleRelease --skip-gecko --update-check` | `BUILD SUCCESSFUL in 1m 26s`; the script exits 1 afterwards on the expected universal-APK ABI check (section 4) |
| emulator, API 34, probe AutofillService, force-stop before each case | plain form 1 fill request (unchanged); open-shadow login page 1; closed roots 0; non-login shadow inputs 0; new email-only shadow page 0; reddit.com/login (after reddit.com/) 1, with `webDomain` and username/password hints |
| same, unpatched 158.0b3 (run 4 APK, actor = pristine) | open-shadow login page 0, email-only 0, plain 1: the bug is present on 158 without the patch |

Details and logs: `docs/android/evidence/lw-m7-42/autofill-shadow-dom/README.md`.

On release day, step 3's `check-patchfail` and `check-patch-order` runs cover
this entry like any other. If the 158.0 text of `GeckoViewAutoFillChild.sys.mjs`
differs from b3, rebase the patch against it. A Gecko pass is needed in any
case, because the change is in omni.ja and `--skip-gecko` does not rebuild it.

Seen in passing, and not caused by this patch: on a fresh profile, a direct
load of `https://www.reddit.com/login/` stays blank on both Redoubt 157.0-2
and 158 (unpatched or patched). Stock Fenix 157 renders it. Visiting
`reddit.com/` first works around it. Not investigated.

## 8. Update, 2026-10-06: main 84a2015b merged; re-checked on 158.0b4

**Source.** On 2026-10-06, `archive.mozilla.org/pub/firefox/releases/` listed
`158.0b1` to `158.0b4`, and `candidates/` listed `158.0b1` to
`158.0b4-candidates`. There was no `158.0-candidates` yet. **158.0b4** is
`releases/158.0b4/source/firefox-158.0b4.source.tar.xz`:

- 812620004 bytes, sha256
  `6e8c17884180287eb31269bd7ada0b6c92440434caa285986101835373e2111a`.
- Verified against the pinned `assets/mozilla-release-key.asc`: `GOODSIG`,
  `VALIDSIG 827E658608679618CD349F93678E455D76767AA3 2026-10-05 … 14F26682D0916CDD81E37B6D61B7B526D98F0353`
  (`prebase/merge-2026-10-06/tarball-158.0b4.txt`).

Every check below used b4. The b3 tarball is still in `~/redoubt-artifacts/ff158/`.

**Merge.** `origin/main` at 84a2015b was merged in a signed merge commit. Everything
main gained since this branch's last merge base (`e418bbcb`) came in:

- the H.264/AAC video hotfix (LW-M7-43). `isolated-process.patch` now passes
  `false` to both `isolatedProcessEnabled` and `appZygoteProcessEnabled`, and
  this branch had never changed that patch, so main's text is used unchanged;
- the harness rows `video-h264` and `video-mse`;
- the F-Droid repository (own and Hetzner) and the Google Play channel work;
- the passkey/password-manager docs;
- `fix/harness-sni` and `fix/update-accept-language`, as main merged them;
- the 157.0-3 release bump, its acceptance and update document;
- LW-M7-44: a user disable of uBO during its startup wait no longer pauses
  browsing. Owner decision 2026-10-06, verbatim: "yes, put it in 158, no
  warning needed".

Conflicts, resolved by hand:

| file | conflict | resolution |
|---|---|---|
| `docs/android/tasks.yaml` | LW-M7-42 (this branch) and LW-M7-43/44 (main) were added at the same place | all three kept, in id order |
| `patches/android/ubo-preinstall.patch` | only the `index` lines of the two new Kotlin files (`LibreWolfUboPreinstaller.kt` and its test) | main's taken. The new-file bodies are main's LW-M7-44 text. The 158 `strings.xml` rebase and its "158 rebase" header note are kept, and so are this branch's other hunk offsets. `git diff origin/main` on the patch shows only those 158 changes |

`release.android` came in as `3`, and `version` and `version.android` stay
`157.0`. Section 5 step 2 now resets `release.android` from `3` to `1`.
`assets/patches/android.txt` and `PATCH-SCOPE.md` merged without conflicts: 22
common, 43 android and 44 desktop-only, 109 in all. `board.py --check-scope`
agrees.

**One patch regenerated for b4.** On b4, `check-patchfail --targets=android`
**failed** in `disable-157-cloud-features` (LW-M7-40), at
`SecretSettingsFragment.kt` hunk 3 (`patchfail-android-before-fix.out.gz`).
158.0b4 removed the IP Protection "locations" secret setting: its
`SecretSettingsFragment.kt` block and `Settings.isIPProtectionLocationsEnabled`.
That block was the trailing context of two of the patch's hunks:

- the hunk that removes the IP Protection switch, which rejected;
- the `isIPProtectionAvailable` hunk in `Settings.kt`, which needed fuzz 1.

Main had not changed this patch since the branch point, so the failure is
b3 → b4, not the merge. Both hunks were regenerated at fuzz 0 on an in-order
b4 replay (`replay.py`; log `replay-android-b4.log`), and the removed and added
lines are unchanged. No other patch names the removed setting. That patch text
no longer applies to b3. A diff of every file this patch touches between b3 and
b4 shows only those two files changed.

**Checks on the merged branch (890043b4), 158.0b4** (`prebase/merge-2026-10-06/`):

| check | result |
|---|---|
| `check-patchfail.sh --targets=android` | exit 0, 65 patches, 8 hunks with fuzz, all in common entries (as in section 6) |
| `check-patchfail.sh --targets=desktop` | exit 0, 66 patches, 30 hunks with fuzz (as in section 6) |
| `--fuzz=0`, both targets | the same 10 android and 20 desktop entries as section 6, identical to b3's reject lists |
| in-order replay, android at `--fuzz=0` (fresh b4 tree) | all 43 android entries apply with no fuzz. 15 apply at an offset (13 on b3). The two new ones are `no-onboarding` and `no-gms`, one hunk each, in `SecretSettingsFragment.kt` and `Settings.kt` (b4's removal). None of the offsets is in res/ or in a hash-pinned patch. `isolated-process`, `update-check` and `ubo-preinstall` apply exactly |
| `make android-dir` (158.0 layout, b4 bytes, `release.android` 1) | exit 0. Every fail-closed check in `librewolf-patches.py` passed, including the glean-core hashes, so glean-core did not move between b3 and b4 |
| `check-patch-order.py` | `patch order ok: 36/36 … 148 shared-file pair(s)` |
| `lint-patch-scope.py`, `board.py --check`, `--check-scope`, `--check-cfg-split`, `--diff-mozconfig --strict` | ok (128 tasks; 109 patch files) |
| `site-check.py` | PASS, 8 pages |
| `scripts/tests/*.py` (18) | 12 ok. The four receipt tests (`addon-state-durability`, `extension-update-controls`, `global-privacy-controls`, `session-cleanup`) fail on "changed since its 157.0 receipt", as section 4 expects until release-day step 4. `test-android-signing.py` and `test-android-version-code.py` exit 2 because their inputs are missing, as on main |

**Build and device check (x86_64, optional).** This build ran in a scratch
copy of 890043b4 with `version` and `version.android` set to `158.0` and
`release.android` to `1`. `firefox-158.0.source.tar.xz` was symlinked to the
b4 tarball, giving release day's layout with b4's bytes. Image `fx158`
(`98e61be72eec`), build date 20261006200000 (`prebase/merge-2026-10-06/build/`):

| step | result |
|---|---|
| `android-fat-aar.sh --abis x86_64` | ok, 32 min (per-ABI pass and merge) |
| `android-apk.sh --variant release` | `:fenix:compileReleaseKotlin`, `BUILD SUCCESSFUL in 13m 28s` (Kotlin `-Werror`), so LW-M7-44's preinstaller compiles against 158. The script's exit 1 afterwards is the expected single-ABI universal-APK check (section 4) |
| built tree | `GeckoProvider.kt` reads `.isolatedProcessEnabled(false)` and `.appZygoteProcessEnabled(false)`, and the preinstaller carries the settle rule |

The x86_64 APK was signed with the throwaway key, cert `31e9a40f…b760`. Its
sha256 is `88585f1f…c2`; both hashes are in `build/SHA256SUMS`. The test device
was an emulator, API 34 `google_apis` x86_64, which reported "Redoubt 158.0-1
buildID=20261006200000":

| check | result |
|---|---|
| `--check-video` | **3/3 PASS**: `video` (VP8/Opus) 13 frames; `video-h264` (H.264 + AAC progressive MP4) 14 frames; `video-mse` (`isTypeSupported(avc1.42E01E,mp4a.40.2)` true, 15 frames). This is the LW-M7-43 fix on 158 (`device/video/`) |
| `--check-ubo-user-disable` | **PASS** on the second run (`device/ubo-user-disable/`). Reload-control: the dialog was shown and "startup failed" logged. User-disable: "disabled by the user during startup", `Ready(installed=true, enabled=false)`, and the held page loaded unfiltered with no dialog. The first run (`device/ubo-user-disable-harness-error/`) ended with a harness error before the second phase: "initial browser document did not finish loading before about:config". That is the provisioning timeout already seen once on 157.0-2 (`evidence/lw-m7-44/device/old-provision-timeout/`), not a result |

Not run here: armeabi-v7a/arm64-v8a, Fenix unit tests, the rest of the smoke
suite, desktop, and the release-day receipt recapture. Section 5 still holds
for 158.0 itself. If 158.0 (or a b5/RC) changes `SecretSettingsFragment.kt` or
`Settings.kt` again, `disable-157-cloud-features` is the first place to look.
