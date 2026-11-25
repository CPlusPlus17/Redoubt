# Firefox 161.0 rebase (both targets), 2026-11-25

Branch `rebase/161.0` (worktree `~/redoubt-artifacts/rebase-161.0/repo`), off
main c61d9891. Closes, once a signed release is published: #16 (Firefox
160.0.1), #17 (Firefox 161.0) and #18 (MFSA 2026-131). 160.0.1 is not released
on its own: 161.0 contains every 160.0.1 code fix (see "160.0.1").

## Advisories (REBASE.md §1)

- **MFSA 2026-131** (Firefox 161, 2026-11-24, overall impact high): 110 CVEs,
  CVE-2026-135500 to -135609; 59 high, 30 moderate, 21 low, no critical; none
  marked exploited in the wild. Three are Firefox for Android only, all fixed in
  the 161.0 source: CVE-2026-135561 (moderate, Downloads spoofing, bug 2033297),
  CVE-2026-135589 (low, WebExtensions race, bug 1975663), CVE-2026-135594 (low,
  WebExtensions spoofing, bug 2058722).
- **MFSA 2026-130** (Firefox 160.0.1, 2026-11-17, high): 2 CVEs, both high:
  CVE-2026-130020 (Android CanvasWebGL privilege escalation, bug 2068592) and
  CVE-2026-130021 (Audio/Video playback use-after-free, bug 2088644). The 161
  advisory does not mention them.
- No Firefox for Android advisory of its own in November 2026. As of 2026-11-25
  there is no 161.0.1 (archive.mozilla.org `releases/` and `candidates/`;
  product-details `LATEST_FIREFOX_VERSION` and mobile `version` = `161.0`; next
  release 2026-12-04).

### 160.0.1

The 160.0.1 tarball (signature checked against the pinned primary) was diffed
against pristine 160.0: 558 entries, 109 code files after leaving out strings,
locales and tests. For each file, its 160.0 -> 160.0.1 diff reverse-applies
cleanly to pristine 161.0 for 98 files, so the fix is already there. That
includes all the security-relevant ones: `dom/canvas/WebGL*`, `gfx/gl/GLContext*`,
`gfx/gl/GLBlitHelper.cpp` and `dom/media/ChannelMediaDecoder.cpp`. The other 11
are data dumps, version files and two Fenix files that 161 changed further. The
one code file among them, `gfx/layers/apz/src/InputQueue.cpp`, carries the
160.0.1 hunk at 161.0 `:619-622` and differs only in context. Details:
`dot1-in-161.md`.

## Input

| | |
|---|---|
| tarball | `archive.mozilla.org/pub/firefox/releases/161.0/source/firefox-161.0.source.tar.xz` |
| size, sha256 | 822504084 bytes, `c649de11e4dc6266bc905ce4b33eb8672a1947c2e210ec53dce285cb86296a5a` |
| signature | `make fetch TARGETS=android`: good signature, subkey `827E658608679618CD349F93678E455D76767AA3`, primary `14F26682D0916CDD81E37B6D61B7B526D98F0353` (Mozilla Software Releases); `VALIDSIG` checked against the pinned primary |
| unpacks to | `firefox-161.0/` |

`version`, `version.android` = `161.0`; `release`, `release.android` = `1`.

## Patches (check-patchfail, default fuzz)

| run | before | after |
|---|---|---|
| desktop (common + desktop) | 65 patches, 6 failing | 66 patches, exit 0 |
| android (common + android) | 72 patches, 21 failing | 72 patches, exit 0 |

`patchfail/before-*.out`, `patchfail/after-*.out`. Failing before: on both
targets `disable-data-reporting-common`. On desktop also `clear-alt-svc`,
`ui-patches/add-translate-page-context-menu`, `ui-patches/privacy-preferences`,
`ui-patches/settings-redesign` and `pref-pane/pref-pane-small`. On android also
20 android patches; some of these failures cascade from earlier ones, because
check-patchfail applies the list without stopping.

After: the only fuzzed hunks on both targets are the three that also fuzz on 160,
in patches this rebase did not change: `autoconfig-setEnv`,
`custom-ubo-assets-bootstrap-location` and `profile-directory`. `remove-openai`
(an `aboutInference.js` hunk 297 lines away, placement checked), `rs-blocker`
(taken from upstream 161.0-1, body identical) and
`disable-data-reporting-common`'s `Telemetry.cpp` hunk (fuzz 2: 161 removed
`XRE_IsSocketProcess()`) were refreshed to fuzz 0.

Method: as on 160, `tools/replay.py`. `common.txt` + `android.txt` are replayed
in order, with the android entries at `--fuzz=0`. Each reject was fixed by hand
against 161.0 and the patch regenerated from that step. A fresh replay from the
pristine commit (`android-replay-final.out`, a freshly initialised replay
repository, after every fix in this record) applied all 72 entries, the 50
android ones at fuzz 0. Desktop: the 160 method. Each patch was regenerated
on upstream LibreWolf 161.0-1's version, with Redoubt's own hunks re-applied. A
fresh in-order replay applies all 44 desktop entries at fuzz 0.

### Common

- `disable-data-reporting-common`: `python/sites/mach.txt` pins glean-sdk
  71.0.0. glean-core is vendored as 71.0.0, but `src/core/mod.rs` and
  `src/lib.rs` are byte-identical to 160.0's (pristine sha256 `e2bc0630...`,
  `8b28662a...`, also what `.cargo-checksum.json` lists), so
  `GLEAN_CORE_HASH_FIXUPS` in `scripts/librewolf-patches.py` is unchanged (comment
  updated). Upstream LibreWolf 161.0-1's `scripts/patch.sh` carries the same
  pins.
- `rs-blocker`: upstream 161.0-1's file (same +/- lines as ours; context now
  imports `PushBroadcastService` from `moz-src:///dom/push/`).
- `remove-openai`: the `aboutInference.js` hunks were regenerated at 161's line
  numbers (the openai preset moved from line 382 to 679).

### Desktop

| patch | what 161 changed | what was done |
|---|---|---|
| `clear-alt-svc` | an include next to the hunk is gone | upstream 161.0-1's version |
| `ui-patches/add-translate-page-context-menu` | the ask-chat / create-aitab items next to the hunk became a highlight-menu item | upstream 161.0-1's version |
| `ui-patches/privacy-preferences` | `privacy.css` uses logical properties | upstream 161.0-1's version |
| `ui-patches/settings-redesign` | `createDefaultBrowserConfig` moved from `main.js` to `config/default-browser.mjs` | upstream 161.0-1's version with Redoubt's hunks re-applied (JIT setting removed, JXL toggle kept); the diff to upstream is exactly those hunks; no longer touches `main.js` |
| `pref-pane/pref-pane-small` | `browser.settings-redesign.enabled` is `true, locked` in `firefox.js`; the `main.js` anchor is gone | upstream 161.0-1's version (with its `firefox.js` unlock), Redoubt's JIT item removed; still last |
| `link-preview` | upstream 161.0-1 change: AI key points honour the AI kill switch (`browser.ai.control.*` = `blocked`) | upstream 161.0-1's version |
| `ui-patches/trustpanel`, `ui-patches/website-appearance-ui-rfp` | applied at fuzz 2 | context refreshed to fuzz 0, same placement, no code change |

### Added

- `window-round` (desktop.txt, before `windows-theming-bug`): upstream LibreWolf
  161.0-1's new patch. With `privacy.resistFingerprinting`,
  `AppWindow::ForceRoundedDimensions()` counted the GTK client-side-decoration
  margin as chrome, so the content area missed the rounded size on Linux. The
  hunk is inside `#ifdef MOZ_WIDGET_GTK`, so it has no effect on Windows, macOS or
  Android. Not built or measured.

Not taken: upstream's `about-librewolf.patch` (a LibreWolf-branded easter-egg
page with no privacy value; it edits shared docshell/toolkit files and has a
`dochsell` path typo).

### Android, rewritten for 161's code, same intent

| patch | what 161 changed | what was done |
|---|---|---|
| `no-gms` | **new GMS dependency**: android-components `lib-installation-blockstore` (`play-services-auth-blockstore` 16.4.0 + `play-services-base`) and Fenix `InstallationMetricsService` / `InstallationWorker` behind the new Nimbus feature `installation` (release default **true**). It keeps an install counter and last-seen date in Google Block Store, which survives reinstalls, and sends a new Glean `installation` ping that carries the client id | module removed from both `.buildconfig.yml`, `app/build.gradle` and `libs.versions.toml`; Fenix service, worker and their tests deleted; the `Analytics.kt` call site removed; the `installation` ping (`pings.yaml`) and its two metrics (`metrics.yaml`) removed, so nothing is generated. `play-services-auth-blockstore` has 0 hits in the patched tree. Also `lazyMonitored` -> `by lazy`, import moves |
| `search-config` | 161 now **reads** `Settings.useSearchConfigV3` (Core.kt switches the selector to search-config-v3, Mozilla's Google-default set), and `SecretSettingsFragment` looks up the debug row the patch removes | that lookup is removed (it would throw when Secret Settings opens); the constant `false` from 160 is now what keeps Redoubt's engine list |
| `no-default-shortcuts` | the pinned seed holds only Google; Wikipedia and the JP sites moved to `default_shortcuts.json`, which gained 47 regional tiles behind Nimbus `regional-default-shortcuts` (release default **true**); the pinned-shortcut limit dialog is gone | seed still emptied; `Settings.enableRegionalDefaultShortcuts` pinned to constant `false` |
| `no-webcompat-reporter` | `MenuConfigurations.kt` is gone; the menu moved to `components/menu/configuration/` and the customizable menu is the only one | ReportBrokenSite removed from `BrowserMenuConfiguration`; the test moved with it |
| `global-privacy-controls` | `mobile/shared/components/geckoview` moved from `EXTRA_JS_MODULES` to `MOZ_SRC_FILES` | both importers use `moz-src:///mobile/shared/components/geckoview/GeckoViewGlobalPrivacy.sys.mjs` (with only the fuzz-applied moz.build hunk the module would not load) |
| `no-onboarding` | `privateModeAndStoriesEntryPointEnabled` removed; `PocketMiddleware` changed | same overrides; `PocketMiddlewareTest` no longer mocks the removed setting |
| `no-glean` | deleted files changed upstream (Nimbus targeting-context ping registration) | deletions regenerated |
| `no-crashreporter` | `lazyMonitored` gone; `Analytics` gained `buildMetadata` | parameter kept, constructor call updated |
| `no-adjust` | Adjust 5.8.1; `Analytics.kt` context | regenerated |
| `ubo-preinstall` | `lazyMonitored` gone | `by lazy` |
| `branding` | release/beta manifests gained `android:sharedUserMaxSdkVersion` beside `sharedUserId` | both attributes removed |
| `rs-blocker-android` | `Error::response_error()` takes the whole `viaduct::Response` | same two network block points |
| `extension-update-controls` | add-on update permission flow rewritten (pending updates in memory, worker rewritten) | automatic/manual split re-placed; tests rewritten in upstream's style, 161's two new tests covered |
| `session-cleanup` | nsFrameLoader cycle-collection macro changed | `mDestroyedPromise` added to the same member list |
| `disable-157-cloud-features` | IP Protection starts from one `IPProtection.initialize()` | that call stays deleted |
| `isolation-media-codecs-in-content` | `Supports()`' Android block restructured | filter still inside the Android block (checked by hand) |
| `build-fixes` | the Gradle `kotlin { jvmToolchain }` block moved (AGP 9 built-in Kotlin) | ported as a mozconfig-only block that does nothing if the `kotlin` extension is missing; it sets `compilerOptions.freeCompilerArgs` by property access, not a configure closure, so it does not depend on Gradle decorating the extension (review follow-up) |

| `delete-on-quit-swipe` | `Settings.isMenuCustomizationEnabled` is a constant `true`, so every menu is `MenuFragment` and Quit runs `QuitMenuItemProvider` -> `clearBrowsingDataOnQuit(onDeletionComplete = quitApplicationDelegate)`; the patch's `MenuDialogFragment` hook still applied at fuzz 0 but is unreachable | **found in review** (the patch applied cleanly): new `MenuFragment.kt` hunk, the quit delegate calls `DeleteOnQuitGuard.onSessionEnding("quit")` before `finishAndRemoveTask()`, as the old hook did. Without it Quit ran upstream's category deletion only, skipped Redoubt's app-side deletion (session file, recently closed, thumbnails, downloads DB, HISTORY purge) and left the marker unclean, so the data stayed until the next cold start. The `MenuDialogFragment` hunk is kept. `tasks.yaml` LW-M7-45 `tree_paths` and `PATCH-SCOPE.md` list the new file. No other patch touches `MenuFragment.kt` |

Context only, no code change: `privacy-defaults`, `canvas-webgl-permissions`,
`sync-opt-in`, `doh-mullvad-migration`, `gradle-no-config-cache`.

### Reduced

- `isolation-eme`: the hunk that passed a failed provisioning on is dropped.
  161 rewrote `MediaDrmRemoteCDMParent` provisioning (no sticky errors, one
  retry, then reject), which fixes the endless retries the hunk was for. The
  rest is unchanged.

Counts: 22 common / 50 android / 44 desktop-only = 116 (`board.py --check-scope`;
`PATCH-SCOPE.md` has a 161 section and a `window-round` row).

### Patch order

`scripts/check-patch-order.py` found 13 new or changed shared-file pairs. They
were measured on the pristine 161.0 tree with `tools/ordering-swap.py`: for each
shared file, the hunks of every list entry that touches it are replayed at fuzz
0, once in list order and once with the later patch moved directly before the
earlier one. Output: `ordering-swap.txt`.

- `no-default-shortcuts` now edits `fenix/utils/Settings.kt`. For its 8 partners
  (`firefox-suggest-policy`, `disable-157-cloud-features`,
  `drm-permission-default`, `no-gms`, `no-onboarding`, `no-suggest`,
  `privacy-defaults`, `search-config`) the file is byte-identical in both orders
  (sha256 `86db8ca35da2...`, equal to the replay tree). Recorded in
  `REVIEWED_ORDER_FREE`.
- `no-gms` now edits `fenix/components/Analytics.kt`. With the later patch moved
  first, `Analytics.kt` rejects for `no-adjust`/`no-gms`, `no-glean`/`no-gms` and
  `no-gms`/`no-crashreporter`. The file is added to those three declared
  constraints, whose direction is unchanged.
- `settings-redesign` no longer touches `main.js`, which is dropped from its two
  grandfathered pairs.

## Review (source reading, two independent reviewers)

- Compile and run: no build or runtime break found. They checked every symbol
  the patches remove, using greps over the patched files plus pristine 161.0,
  every `libs.*` alias, all call-site signatures, the `moz-src:///` URL, the C++
  macro use, and that the changed XML, JSON and YAML parse. Follow-ups made:
  the `build-fixes` Gradle access above, and `isolation-eme`'s header item 6
  rewritten for the dropped hunk. Left alone: the unused `installation`
  declaration in `nimbus.fml.yaml` (nothing reads it) and the
  `MenuDialogFragment` / `MoreSettingsSubmenu` hunks, which are unreachable on
  161 but harmless.
- Privacy coverage: they found one regression, the Quit path of
  `delete-on-quit-swipe` (fixed, see the table), and the Wikipedia default tile
  (owner decision, below). Checked and found covered: the `installation` / Block
  Store removal; the only new Glean ping; Nimbus; the Google Lens entry points
  (`googleLensIntegrationEnabled` constant false); search-config-v3; Remote
  Settings (no new consumers, the allowlists intact); the ads client's new
  worker (never started); IP Protection (`initialize()` never called);
  Report broken site; Merino; extension data-collection consent; the moved
  JS modules; pref names; crash reporting; the socket process removal.

## Brand images (LW-M4-07)

161 adds, resizes or renames no brand image. `android-brand-check.py` exits 0 on
a copy of the patched tree with the `assets/android-brand/` copy applied. On the
bare tree it fails on the Gecko branding layer only, as on 160.

## Settings (Redoubt-settings, branch `rebase/161.0`, commit `3982f7e`, signed)

Upstream LibreWolf 161.0-1's cfg delta, 6 calls, all desktop-only (every reader
is under `browser/`), goes into `desktop.cfg`:

- `browser.smartwindow.location.enabled` false: 161 defaults it to true, which
  gives Smart Window an approximate location from Mozilla's Merino geolocation.
- `browser.widgets.generated.enabled` false: ML widget generation.
- `...widgets.system.wrexhamAFC.enabled` and `...widgets.wrexhamAFC.enabled`
  false.
- `sidebar.verticalTabs.dragToPinPromo.dismissed` and
  `browser.highlightToSearch.callout.seen` true.

`librewolf.cfg` is regenerated as `common.cfg + desktop.cfg`. Totals for common
+ desktop: 289 defaultPref, 83 lockPref (283 / 83 before). `board.py`
`CFG_EXPECTED`, `ROADMAP.md` and `tasks.yaml` carry the new numbers.
`common.cfg` and `android.cfg` are unchanged.

No Redoubt-specific additions. The GeckoView pref surface did not change: no new
`Pref<>` in `GeckoRuntimeSettings.java` / `ContentBlocking.java`, and
`GeckoRuntime.java` and `geckoview-prefs.js` are identical. Fenix's runtime pref
writes and its Nimbus pref bindings are unchanged. 161 adds 4 Remote Settings
collections, and `rs-blocker`'s `allowedCollections` allowlist keeps them out.

## Section 6, pref drift (160.0 vs 161.0)

Source-level checks only; `android-pref-audit.sh` was not run on a device.

- 6a: no new orphan. Android: 8 of 202 names, the same set as on 160. Desktop:
  42 of 405, the same set as on 160.
- 6b: 99 names drifted. None is a pref we set, except the three new 161 prefs
  the upstream port adds. None of ours was removed.
- 6c: 209 `mirror: once` entries, 209 names (fixed awk); none is ours.
- 6d: `--check-policies` ok (132 GeckoView prefs, 25 shipped by us).
- 6e: not run (needs a build).
- 6f.1: the isolation-media gate holds. There is one `GeckoRuntime.create()`
  (`GeckoProvider.kt:73`). `getDefault()` appears only as the default argument
  of `GeckoEngine.kt:117` and `GeckoViewFetchClient.kt:33`, and `Core.kt` passes
  the one runtime to both. `GeckoRuntime.java` is identical, so `init()` still
  sets the process manager before `InitInfo` is built.
- Nimbus release defaults (Fenix 160 -> 161): added `installation` (true,
  removed by `no-gms`) and `regional-default-shortcuts` (true, pinned off by
  `no-default-shortcuts`); also added, all false: `automotive-sensitive-data`,
  `browser-first` and `homepage-wrexham-widget`. Three edge-to-edge and
  entry-point features were removed. No existing feature changed its release
  value (`listen-to-page` and the `pdfjs` buttons changed for nightly and
  developer only; Redoubt builds release), and none drives a Gecko pref.

## Gates

`gates.txt`: `board.py --check`, `--check-scope`, `--diff-mozconfig --strict`,
`--check-policies` (pristine 161.0), `--check-cfg-split`, `lint-patch-scope.py`,
`check-patch-order.py` and `gen-ubo-assets-android.py --check` all exit 0.

`scripts/tests`: every file exits with the same code as on main c61d9891 (run
from a `git archive` of main on this VM). The failing tests also fail the same
way on main, with one exception: `test-ubo-cookie-lists`
`test_pin_is_a_commit_that_serves_the_current_catalog` fails on the branch but
cannot run in the `git archive` copy, which has no `.git`. It is the open re-pin
reminder from the 160 record: pinned commit 612fac02 still serves the 159
catalog. This rebase does not change `assets/uBOAssets*.json`, because upstream
161.0-1's catalog equals ours.

## Other upstream and toolchain deltas

- `l10n/fi`: upstream 161.0-1's 13 new messages, without the JIT and updater
  ones; `librewolf-JXL` kept. Upstream's `aboutLibreWolf.ftl` (not taken, see
  Added) and the container-tab `customkeys` string are skipped.
- Upstream replaced its patcher and CI (`scripts/patch.sh`, new docker files, a
  bundled Mozilla key) and set `--with-distribution-id='net.librewolf'` in its
  mozconfig. None of this is taken.
- `assets/Dockerfile.android`: Rust 1.94.1 -> **1.95.0**. 161 raised the floor
  (`python/mozboot/mozboot/util.py:18` `MINIMUM_RUST_VERSION`, `Cargo.toml:160`
  `rust-version`) from 1.90.0 to 1.95.0. The first CI runs (45635365848,
  45645657463) died in configure after 29 s with "Rust compiler 1.94.1 is too
  old". Mozilla's own Android toolchain, `linux64-rust-android-1.95`
  (`taskcluster/kinds/toolchain/rust.yml:214-236`), has been 1.95.0 since at
  least 157, so the image was behind it before this rebase too. The target list
  is unchanged. Every other gating row was re-read on 161.0 and is unchanged:
  NDK r30, cmdline-tools 23.0 / 16111833, build-tools 37.0.0, android-37.2,
  bundletool 1.18.3, Node 22.16.0 (floor 12.22.12), cbindgen 0.29.4, and the
  wasi-clang-21 sysroot / compiler-rt (still listed in 161's `sysroot.yml` and
  `compiler-rt.yml`). CI rebuilds the image because the file's sha256 changed.
  `scripts/android-fat-aar.sh` now prints the failing pass's log errors and
  tail, as `android-apk.sh` does since c1f73826; before that, the per-ABI log
  stayed on the runner.
- `assets/Dockerfile.android`: WASI sysroot and wasm32 compiler-rt sha256
  **re-pinned**. Run 45646362717, the first image build since the pins were
  set, stopped with `sysroot-wasm32-wasi.tar.zst: FAILED` because the bytes
  behind the same Taskcluster index changed. Taskcluster re-ran both cached
  toolchain tasks on 2026-11-23 under the unchanged input-hash namespaces
  (`...sysroot-wasm32-wasi-clang-21.hash.9331ced3...`,
  `...wasm32-wasi-compiler-rt-21.hash.b6dd1a27...`). The year-old tasks had
  expired, so the old bytes cannot be fetched for a diff. What was checked:
  - the new tasks `BXmGCuhxTHKp4gOJb_tl9Q` and `YVF-ATf1RzyxeabvrLGqGw` are
    `gecko-level-3` tasks in decision group `bGaYt9iGR2a9HxdUhHSUHw`
    (mozilla-esr153 `2cf1a2589c88`);
  - each download's sha256 (sysroot `86c876ed...ce29`, compiler-rt
    `824a4600...f175`) equals the one in the task's
    `public/chain-of-trust.json`;
  - that file's `.sig` verifies (openssl ed25519) with Mozilla's docker-worker
    key `Kz/aZIVeR6NP8gQU1U+2CCIZqvbd+4QCP6J63lflwik=` (scriptworker
    `constants.py` at e6c6555c, "Dec 2023 rotation - d2g");
  - the layout is what the Dockerfile expects: `sysroot-wasm32-wasi/`
    (`libc.a`, `libc++.a` and headers, 2175 entries) and
    `compiler-rt-wasm32-wasi/lib/wasi/libclang_rt.builtins-wasm32.a`.

  Expect the same around 2027-11-23, when these tasks expire.
- `assets/l10n-pin.txt` is unchanged, as on 160.

## Not done here

This VM has no Android SDK, emulator, node or Gecko build environment. None of
the following was run:

- the build;
- Fenix / android-components unit tests, including the edited
  `PocketMiddlewareTest`, `BackgroundServicesTest`, `AddonUpdaterWorkerTest` and
  `BrowserMenuConfigurationTest`;
- lint, detekt and ktfmt;
- the smoke, including `--check-no-gms` on the 161 APK;
- device acceptance, including the DRM checks on API 31-34 from 158.0-3, because
  upstream changed what happens when provisioning fails.

Every Kotlin, C++, JS and Gradle edit was checked by reading the 161.0 source
only.

Owner decisions (nothing changed for these):

- Wikipedia default tile, **new visible behaviour in 161**: 160 never passed
  `defaultTopSitesProvider` to `DefaultTopSitesStorage` (160 `Core.kt:665-669`,
  161 `:670-675`), so `default_shortcuts.json` was bundled but never shown. On
  161 its one experiment-independent entry (Wikipedia, all regions but CN/JP)
  fills empty slots once the user turns Shortcuts on, upgrades from 160
  included. No network request (letter icon, no icon preparer). Matching
  LW-M7-30's empty seed means emptying the file and rewriting
  `DefaultShortcutsTest` (13 tests read the bundled data), or not wiring the
  provider, which has five consumers. Left for the owner.
- `build-fixes` section 2: propose retiring it. The generated UniFFI code it
  works around has not existed since 159 (0 of 22 files). It is kept as a no-op
  until a build confirms nothing else needs it.
- `network.http.dictionaries.enable` (compression dictionaries) is now on in
  release on both targets, partitioned like the HTTP cache; upstream does not
  set it. Turning it off would change `Accept-Encoding` from stock Firefox.
  Recommended: leave it.
- `dom.clipboard.customFormatSupport.enabled` is now on in release (Async
  Clipboard web custom formats); not set by us or upstream.
- Upstream's isolated-process test configuration now also enables
  `media.gpu-process-decoder` / `-encoder`; `isolation-media-prefs` locks only
  the original eleven prefs. The GPU-process decoder is `@IS_NIGHTLY_BUILD@` on
  Android, so this has no effect on release.
- The older l10n gap: about 18 locales lack strings upstream already had in
  160.0-1, among them the Mullvad DNS shutdown notice and the whole `pt` locale.
  Not part of the 160 -> 161 delta.
- Still open from 160: the uBO catalog re-pin, regenerating the
  `firefox-suggest-data` uniffi hunk, the l10n pin, and the `expected-prefs.txt`
  regeneration after a device run.
