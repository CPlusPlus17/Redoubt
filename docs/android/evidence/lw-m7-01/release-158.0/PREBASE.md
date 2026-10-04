# Firefox 158 pre-rebase, against 158.0b3

Branch `android/firefox-158` (worktree `~/redoubt-artifacts/ff158/repo`),
scratch `~/redoubt-artifacts/ff158/work/`. One agent did this on the build
host on 2026-10-04. The goal is that release day (Firefox 158.0, 2026-10-09)
needs only a tarball swap, a re-check and a build, not a rebase.

**The version files still read `157.0`.** The patch texts on this branch
target 158 and no longer apply to 157. The bump to 158.0 happens on release
day, with the real 158.0 tarball. The steps are at the end of this file.

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
| `privacy.restrict3rdpartystorage.heuristic.recently_visited` | Android true → false | **no** (this one restricts more) |
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
2. **Bump** `version` and `version.android` to `158.0` (`release`,
   `release.android` stay `1`) on this branch.
3. **Re-check the patches** against the real tarball:
   `./scripts/check-patchfail.sh --targets=desktop` and `--targets=android`
   (both must exit 0), plus the `--fuzz=0` runs. Compare their reject lists
   with section 2's "After" table. Anything new between b3 and 158.0 gets the
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
7. **Full build, 3 ABIs**: fresh `make dir TARGETS=android`, then
   `make android-build` and `make android-package TARGETS=android` with
   `android_build_image=localhost/librewolf-android-build:fx158`,
   `--variant=release --disable-debug-signing`, one `--build-date` for all
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
   this host signs a release).
10. Desktop: the same tarball and steps 1-3 for `TARGETS=desktop`. This
    pre-rebase did not compile desktop.
