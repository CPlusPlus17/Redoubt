# Firefox 160.0 rebase (both targets), 2026-11-11

Branch `rebase/160.0` (worktree `~/redoubt-artifacts/rebase-160.0/repo`),
off main 99478169. Closes, once a signed release is published: #14 and #15
(Firefox 160.0, MFSA 2026-125).

## Advisory (REBASE.md §1)

MFSA 2026-125 (overall impact high): 99 CVEs, CVE-2026-124852 to -124951
without -124916; 57 high, 24 moderate, 18 low; none marked exploited in the
wild. Two are Firefox for Android only, and both are fixed in the 160.0 source
(no backport needed): CVE-2026-124911 (moderate, Autofill clickjacking, bug
1991276) and CVE-2026-124937 (low, Media, bug 2074123). As of 2026-11-11 there
is no 160.0.1, no Android-only 160.0.x and no newer Firefox or Firefox for
Android advisory: archive.mozilla.org releases and candidates, product-details
and the advisories index were checked for `reports/decide-160.md` (scratch;
the advisory page and listings were fetched there, not re-fetched for this
record).

## Input

| | |
|---|---|
| tarball | `archive.mozilla.org/pub/firefox/releases/160.0/source/firefox-160.0.source.tar.xz` |
| size, sha256 | 824465620 bytes, `2b23d2bf6716ea16b45c10aa5c275c78a1d7ff50ad53150809ab27424c58fd81` |
| signature | `make fetch`: good signature, made 2026-11-04 22:30:12 CET, subkey `827E658608679618CD349F93678E455D76767AA3`, primary `14F26682D0916CDD81E37B6D61B7B526D98F0353` (Mozilla Software Releases); `VALIDSIG` checked against the pinned primary |
| unpacks to | `firefox-160.0/`, `config/milestone.txt` = `160.0` |

`version`, `version.android` = `160.0`; `release`, `release.android` = `1`.

## Patches (check-patchfail, default fuzz)

| run | before | after |
|---|---|---|
| desktop (common + desktop) | 65 patches, 4 failing | exit 0 |
| android (common + android) | 72 patches, 14 failing | exit 0 |

`patchfail/before-*.out`, `patchfail/after-*.out`. Failing before: on both
targets `rs-blocker` and `disable-data-reporting-common`; on desktop also
`ui-patches/privacy-preferences` and `ui-patches/settings-redesign`; on android
also the 12 android patches in the table below. After: the only fuzzed hunks
are in patches this rebase did not change (android 3: `autoconfig-setEnv`,
`custom-ubo-assets-bootstrap-location`, `profile-directory`; desktop 5: those
three plus `ui-patches/trustpanel` and `ui-patches/website-appearance-ui-rfp`).
No android entry needs fuzz in the after run, which applies the lists in order.

Method (the 159 rebase's, `tools/replay.py`; the 160 copy also accepts `-` for
an already unpacked tree): a scratch git repository of the pristine 160.0 tree;
`common.txt` + `android.txt` replayed in order, android entries at `--fuzz=0`;
at each failing entry the patch was applied with fuzz, the rejects fixed by
hand against 160.0, and the patch regenerated from that step's diff. A fresh
replay from the pristine commit then applied all 50 android entries at fuzz 0.
The desktop port regenerated the desktop and common patches against upstream
LibreWolf 160.0-1 and compared them per file with main and with upstream
159.0.1-1 / 160.0-1, so that Redoubt's own hunks survive (for example
settings-redesign's JIT removal and JXL toggle).

### Retired, reduced

None. `assets/patches/*.txt` are unchanged.

### Rewritten for 160's code, same intent

| patch | what 160 changed |
|---|---|
| `rs-blocker` | the SearchEngineSelector remote-config-overrides hunk is gone with its code (`#remoteConfigOverrides` no longer exists in `toolkit/components/search/`); upstream LibreWolf 160.0-1 dropped it too |
| `disable-data-reporting-common` | glean-sdk 70.2.1 -> 70.3.0 in `python/sites/mach.txt`; `GLEAN_CORE_HASH_FIXUPS` in `scripts/librewolf-patches.py` moves to glean-core 70.3.0 |
| `ui-patches/privacy-preferences`, `ui-patches/settings-redesign` (desktop) | regenerated on upstream 160.0-1's versions with Redoubt's changes kept |
| `android/neterror-jar` | `toolkit/themes/mobile/global/jar.mn` gained entries at its end |
| `android/no-adjust` | FxA pairing-campaign attribution added to the install-referrer code (deletions regenerated); `OnboardingPageAdditionSupport` (renamed) gates a pairing sign-in page whose only pref writer the patch deletes |
| `android/no-glean` | `OnboardingFragment` import block |
| `android/no-gms` | `IPProtectionStorageSynchronizer` moved to `feature.ipprotection.storage` |
| `android/branding` | beta/release manifests gained `xmlns:tools` / `tools:ignore="Deprecated"` beside `sharedUserId` |
| `android/search-config` | a "Use search-config-v3" debug row now follows the row the patch removes. Review follow-up: `Settings.useSearchConfigV3` is pinned to a constant `false` and that debug row is removed too (same reasoning as `useRemoteSearchConfiguration`: the packaged v3 dump is Mozilla's, Google default, and only v2 is replaced). Nothing reads or assigns the property on 160, tests included |
| `android/translation-assets` | `decompressFromZstdBlob()` lost a comment line |
| `android/sync-opt-in` | `FxaAccountManager.beginAuthentication()` lost the `service` default: `AccountServicesDisabledTest` passes `service = ""`; new imports and the `orEmptyIf()` helper |
| `android/firefox-suggest-policy` | `SearchEngineFragment.onResume()` ends with `scrollToRequestedPreference()` |
| `android/firefox-suggest-data` | `SearchEngineFragment` context; generated `remote_settings.kt` gained `RemoteSettingsContext.distribution` on other lines (merged by hand, not regenerated with uniffi-bindgen: no build env). The hunk's own 403 +/- lines are byte-identical to the 159.0.1 patch's, the Rust API is unchanged and uniffi is 0.32.2 in both trees, so a checksum mismatch is unlikely but not excluded; it would be a startup crash, not a compile error. Owner step below |
| `android/disable-157-cloud-features` | `IPProtectionEligibilityStorage` moved to `feature.ipprotection.storage`, `FenixIPProtectionEligibilityStorage` to `fenix.ipprotection.store`; the now-unused imports are dropped |
| `android/isolation-media-codecs-in-content` | `Supports()`'s `#ifdef ANDROID` block gained an MCSInfo filter. At default fuzz GNU patch placed the Redoubt filter in the `#ifdef MOZ_WMF_CDM` block (Windows only); the regenerated hunk is inside the ANDROID block |

Context only, refreshed to fuzz 0 with no code change: `android/canvas-webgl-permissions`,
`android/extension-update-controls`, `android/isolation-media-prefs`. The other
desktop/common patch files in the diff changed line numbers, context or hunk
order only.

The android patches whose code changed shape carry a "160 rebase" header note
(`neterror-jar`'s was added in the review follow-up). Also from that follow-up:
`firefox-suggest-policy` and `disable-157-cloud-features` were regenerated at
their new in-order line numbers after the `search-config` change (only `@@` and
`index` lines differ), and `rs-blocker-android`'s header now counts eight
packaged collections (160 adds `search-config-v3`, `client.rs:99`); its hunks
are unchanged. A fresh in-order replay from the pristine commit
(`work/android-fix160-verify`, a worktree of the replay repository) applied all
50 android entries at fuzz 0, with the same output as the first verification
replay.

Counts: 22 common / 50 android / 43 desktop-only = 115 (`board.py --check-scope`).

## Brand images (LW-M4-07, `assets/android-brand/`)

160 ships the Firefox search-widget preview (`fenix_search_widget.webp`,
`previewImage` of `search_widget_info.xml:12`) at mdpi, hdpi, xhdpi and xxhdpi
in each of beta, main, nightly and release; 159.0.1 had hdpi only. It also
halved the hdpi file (1014x180 -> 507x90; 1014x180 is now xxhdpi) and changed
the declared size of `ic_firefox.xml` in beta (512dp -> 108dp) and nightly
(480x496dp -> 108x111.6dp). Before the fix `android-brand-check.py` exited 1
(12 brand images with no replacement), so the Firefox flame would have shipped
as the widget preview on mdpi/xhdpi/xxhdpi devices.

Fixed: 12 new webp files, the 4 hdpi ones re-rendered at 507x90, and the two
vectors with 160's declared sizes (92 replacements, 86 brand images in the
tree). They were made with `scripts/gen-android-brand.py` itself, run against
the replay tree with its output pointed at a scratch directory and its two
ImageMagick calls mapped onto ffprobe / ffmpeg (librsvg decoder, libwebp
encoder, quality 92, method 6), because this VM has no ImageMagick. Only the 18
files above were copied in; every other generated file has the size of the
checked-in one, and the rest of the set is untouched. Font: Noto Sans (the
generator's second choice; no DejaVu here). Rendered to PNG and looked at: the
fort mark plus "Redoubt" in slate on transparent, matching the existing 1014x180
file. The bytes come from a different encoder than the earlier set, so a later
run of the generator with ImageMagick will rewrite these 16 webp files.

`android-brand-check.py` on a copy of the replayed android tree with
`android_brand_images()`' copy applied (no missing destination): exit 0, "86
brand image(s) replaced, and Gecko's branding names no Mozilla mark" (in
`gates.txt`). On the bare replay tree it still fails on the Gecko branding
layer, which only the patcher writes. Not run: the CI step on a `make dir
TARGETS=android` tree.

## Settings (Redoubt-settings, branch `rebase/160.0`, uncommitted)

Upstream LibreWolf 160.0-1's cfg delta is ported into the split:

- `common.cfg`: `lockPref browser.search.configV3.featureGate false`,
  `defaultPref media.webspeech.recognition.enable false` (160's default became
  `@IS_NOT_ANDROID@`, on for release desktop), `app.support.baseURL` set to
  upstream's versioned URL. Android overrides that last one (see below).
- `desktop.cfg`: temporal suggestions (featureGate on, both suggest prefs off),
  New Tab solitaire/travel widgets, `telemetry.privatePing.dwellTime.enabled`
  locked off, `browser.tabs.firefox-view.importHistory.dismissed`,
  `browser.fireButton.enabled`, `browser.engagement.search_counts.pbm` and
  `browser.fireButton.enrollmentSlug` locked; the webcompat-reporter section is
  removed (160 removed the reporter and both prefs).

Redoubt additions from reading 160.0:

- `common.cfg`: `lockPref("network.http.akamai_waf_telemetry.enabled", false)`.
  New in 160, default true on every target; `HttpChannelChild::CollectAkamaiResponseTelemetry`
  scans every response's headers and on a 403 wraps the body in an
  `AkamaiWafBlockDetector`, recording the Glean metrics `akamai_document_loads`
  and `akamai_waf_blocked`.
- `desktop.cfg`: `defaultPref("browser.smartwindow.aitab.enabled", false)`, as
  upstream since 159. 160 makes it Nimbus-settable; the release default is
  already false.
- `android.cfg`: `lockPref` true on `network.lna.enabled` and
  `network.lna.blocking`, next to `block_trackers`. Both are
  `PrefWithoutDefault` in `GeckoRuntimeSettings.java` (`:777`, `:781`), and
  Fenix commits them on every cold start from its Nimbus `lna-blocking`
  defaults, which were `false` on 159.0.1 and are `true` on 160.0. The comment
  that said they "already match" is corrected (also in `POLICIES.md`), and
  `must-not-lock.txt` lists them under LOCKED-CONTROL-DEAD (the only UI is two
  hidden Secret Settings switches). Read in source only: whether a 159.0.1-1
  install really ran with LNA off was not measured.
  Review follow-up: `must-not-lock.txt` now also records two consequences.
  (1) Fenix shows the per-site LNA controls from its own
  `Settings.isLnaFeatureEnabled` (`SiteSettingsFragment.kt:92`,
  `SitePermissionsDetailsExceptionsFragment.kt:87-88`, `TrustPanelStore.kt:93`),
  not from the Gecko pref. On 160 that is the Nimbus default `true`, so the UI
  and the lock agree; a later Fenix default flip would leave Gecko blocking with
  no way to manage exceptions. (2) Upgrades from 159.0.1 start getting LNA
  prompts and blocks, which belongs in the 160 release notes. Both names are now
  in the smoke pref dump (`android-smoke.sh` `PREF_LIST`), and
  `expected-prefs.txt` has rows `bool true locked -` for them. Those two rows are
  written by hand from the `block_trackers` row (same lock, same Fenix chain),
  not generated from a build: both are must-lock keys, so without a row the
  audit would report them as a violation. The next device audit checks them.
  Regenerate the baseline from that run.
- `android.cfg`: `defaultPref("app.support.baseURL", "https://support.librewolf.net/")`
  (review follow-up). Gecko on Android reads it for the HTTPS-only and net-error
  "Learn more" links and `moz-support-link`. Without the override, the common.cfg
  port would send the Gecko version, OS and locale to a site that has no Android
  pages. This keeps Android on the value it shipped through 159.0.1. Desktop
  keeps upstream's versioned URL, and `librewolf.cfg` is unchanged by this.

`librewolf.cfg` is regenerated as `common.cfg + desktop.cfg`. Totals for
common + desktop: 283 defaultPref, 83 lockPref (272 / 80 before); `board.py`
`CFG_EXPECTED`, `ROADMAP.md` and `tasks.yaml` carry the new numbers.

`assets/uBOAssets.json` is upstream 160.0-1's (main was identical to upstream
159); `assets/uBOAssets.android.json` is regenerated from it with
`gen-ubo-assets-android.py` (urlhaus list `-ag-` -> `-vivaldi-`, Persian and
Korean lists at their new repositories). The hosted pin is not moved, see
"Not done here".

## Other upstream and toolchain deltas

- `l10n/sq`: upstream LibreWolf 160.0-1's strings are ported except the JIT
  (`panel-enable-jit`, `permissions-jit2`, `permissions-site-jit-*`,
  `librewolf-jit-checkbox2`), container-tab
  (`customkeys-file-new-tab-current-container`) and updater
  (`update-application-disabled-choose-2`, `update-application-updates-disabled`)
  strings. Redoubt has no patch that uses them: no container-tab or JIT-permission
  patch, and upstream's `allow-disabling-updater.patch` was dropped at the 157
  merge (`assets/patches/desktop.txt:61`). Upstream's new
  `.forgejo/workflows/source-target-test.yaml` is upstream CI and is not taken.
- `assets/Dockerfile.android` is unchanged. Re-read on 160.0: every row that
  gates the image matches 159.0.1 (NDK r30, cmdline-tools, build-tools 37.0.0,
  android-37.2, JDK 17.0.20.1+1, linux64-rust-android 1.95.0, Rust floor 1.90.0,
  Node floor 12.22.12). Upstream moved its Linux Node to 24.21.0
  (`taskcluster/kinds/toolchain/node.yml:24-32`, `fetch/toolchains.yml:591-596`).
  The image keeps 22.16.0, above the floor, and moving it is a deliberate change,
  not part of this rebase. The header's "not baked" rows are stale (160: Gradle
  9.8.1, AGP 9.4.1, Kotlin 2.4.21, KSP 2.3.12, compileSdk 37.2 / target 37).
  They are left alone on purpose: CI rebuilds the build image whenever the file's
  sha256 changes (`android-test.yaml:294`, `android-release.yaml:259`), so a
  comment edit would cost an unpinned image rebuild. Update them with the next
  real image change.
- `assets/l10n-pin.txt` is unchanged since the 157 merge (401f71ba), so 160's
  new strings fall back to English in other locales on both targets (not
  measured). Bumping it means choosing and trusting a new firefox-l10n head,
  which is left to the owner (procedure in the file header).

## Gates

`gates.txt`: `board.py --check`, `--check-scope`, `--diff-mozconfig --strict`,
`lint-patch-scope.py`, `check-patch-order.py`, `--check-policies` on the
pristine 160.0 tree (132 GeckoView prefs, 25 shipped by us; 23 before the LNA
locks), `gen-ubo-assets-android.py --check` and `android-brand-check.py` (see
Brand images): all ok. Re-run after the review follow-up, with the same results.

`--check-cfg-split` exits 1 with 20 errors, all rule B. Rule B compares the
fragments with the last *committed* `librewolf.cfg` of the settings submodule,
and the settings changes above are not committed; the 20 lines are exactly the
upstream 160 delta (18) and the two Redoubt additions to common + desktop.
Rules A (byte concatenation), C and D (283 / 83, 13 `librewolf.*`) pass. Rule B
passes only once the settings commit exists; re-run it then. The release
workflow runs this as a hard preflight (`android-release.yaml:162`), so the
settings commit must be pushed and the superproject gitlink bumped to it.
Otherwise CI keeps the old bddc198f prefs or cannot resolve the commit. The
review follow-up's `android.cfg` line is outside rule B's scope; the 20 errors
are byte-identical before and after it.

Update, 2026-11-11: settings commit `248c576` made; `--check-cfg-split` now
reports `ok: 185 common / 210 desktop / 17 android calls; librewolf.cfg
regenerates exactly` (appended to `gates.txt`).

`scripts/tests` (re-run after the review follow-up, same exit code and the same
failures per file): 9 of 19 files pass, the same 9 as main 99478169 on this VM
(run from a `git archive` of main). The other 10 fail on main too, for the same
reasons (no `node`, no APK outputs, receipt pins from earlier rebases, 2.7 GB
free in `/tmp`), with one difference: `test-ubo-cookie-lists`
`test_pin_is_a_commit_that_serves_the_current_catalog` fails because the
regenerated Android catalog is not yet what the pinned commit serves. That is
the designed reminder for the re-pin step (`gen-ubo-assets-android.py`,
"Re-pinning").

## Section 6, pref drift (159.0.1 vs 160.0, names our three cfgs set)

Source-level pref checks only; the runtime audit (`android-pref-audit.sh` on a
device) was not run.

- 6a, patched trees (android: the in-order replay tree, common + android.cfg,
  202 names; desktop: the pristine tree, with each reported name then looked
  up in the replayed desktop files and in `assets/`, common + desktop.cfg, 399
  names): no new orphan.
  The 159 rebase's `toolkit.coverage.*` no-ops remain; the other names left are
  the known ones (runtime-built `permissions.default.*`,
  `app.update.lastUpdateTime.*` and New Tab `widgets.*` names,
  `network.gio.supported-protocols`, `librewolf.cfg.version`,
  `librewolf.aboutMenu.checkVersion`, `browser.ml.onnxNativeAvailabilityReported`),
  all reported on 159.0.1 too, except the four new solitaire/travel widget
  prefs, which `browser/extensions/newtab/lib/ActivityStream.sys.mjs` declares
  without the `browser.newtabpage.activity-stream.` prefix (false positives).
  Against the stock 160 tree with the HEAD cfgs, the desktop run also reported
  `extensions.webcompat-reporter.enabled` / `.newIssueEndpoint` (160 removed
  them); the port removes both.
- 6b: for the HEAD cfgs, no default changed for a pref we set apart from the
  webcompat-reporter removal. `network.captive-portal-service.enabled` moved
  from `all.js` to `StaticPrefList.yaml` (`mirror: always`, same `false`
  default), so our value still applies. Among the names this rebase adds,
  `media.webspeech.recognition.enable` changed from `@IS_NIGHTLY_BUILD@` to
  `@IS_NOT_ANDROID@` and `browser.smartwindow.aitab.enabled` from `false` to
  `@IS_NIGHTLY_BUILD@`; the rest are new in 160.
- 6c: no pref we set is `mirror: once` in either patched tree (209 such names).
  The procedure doc's 6c awk, `/^- name:/`, skipped the `#ifdef`-indented
  `-   name:` entries and credited their `mirror: once` to the previous name: on
  160 it prints 196 names for the 209 entries. Both copies in
  `docs/android/REBASE.md` (6c and Appendix A) now use `/^-[[:space:]]+name:/`, which
  prints all 209. Re-run with the fixed pattern over common, android and
  desktop.cfg: still empty.
- 6d: `--check-policies` ok (132 GeckoView prefs, 25 shipped by us).
- 6e (`librewolf.webgl.prompt` in the generated header): not run, since it needs a
  build. See "Not done here".
- 6f.1 (isolation-media gate) holds on 160: one `GeckoRuntime.create()` (fenix
  `GeckoProvider.kt:73`); `getDefault()` only as the default argument of
  `GeckoEngine.kt:117` and `GeckoViewFetchClient.kt:33`, and `Core.kt` passes
  the GeckoProvider runtime to both; the `GeckoRuntime.init()` body up to
  `GeckoThread.init` is byte-identical in 159.0.1 and 160.0 (the process manager
  is still set before `InitInfo` is built). 6f.3: `isolation-media-prefs`
  (the variants.yml prefs) and `isolation-media-codecs-in-content` (the
  `Supports()` / `CreateDecoder()` hooks, rewritten for 160, see the table) apply
  at fuzz 0; what the hooks do was checked by reading only, not run.
- Nimbus release defaults (`fmldiff.py` from the 159 record): added
  `account-sync-decouple` and `search-config-v3` (both `enabled: false`);
  changed `lna-blocking` (`blocking` and `enabled` false -> true, see Settings),
  `universal-edge-to-edge-wallpapers` (`enabled` false -> true),
  `pairing-signin-prompt` (`campaign-utm-content` "" -> "DTM_SYNC_PAIR_V2") and
  `juno-onboarding` (a `sync-sign-in` card added).

## Not done here

This VM has no Android SDK, emulator, node or Gecko build environment. Not
run: the x86_64 / arm64 build, Fenix and android-components unit tests
(including the edited `AccountServicesDisabledTest`), lint, detekt, the smoke
(SMOKE.md) and the device acceptance (`--check-video`, `--check-eme`, first-run
capture, the LNA prefs in `about:config` and Settings > Site permissions after a
cold start, the pref audit with the two new LNA rows), the §6e/§10 L1
`librewolf.webgl.prompt` generated-header check (needs `./mach build`), and the
CI brand-check step on a `make dir TARGETS=android` tree. Every Kotlin, C++ and
JS edit was checked by reading the 160.0 source only.

Owner steps before a release:

- Commit the settings submodule, push that commit, and bump the superproject
  gitlink to it; then `--check-cfg-split` rule B passes (it is a hard preflight
  in the release workflow). The bddc198f trap applies again. Separately, the uBO
  catalog re-pin: commit the regenerated `uBOAssets.android.json` alone, then
  set `CATALOG_COMMIT` and `android.cfg`'s `librewolf.uBO.assetsBootstrapLocation`
  to that commit in a later one. Until then fresh Android installs bootstrap the
  catalog of the currently pinned commit (612fac02), without the 160 list moves.
- `firefox-suggest-data`'s `remote_settings.kt` hunk: regenerate it in CI with
  embedded-uniffi-bindgen over the 160 megazord and diff it against the
  committed one (the patch header says how). At minimum, the device smoke must
  open the Suggest data settings and run a pinned install.
- Release notes for 160 on Android: Local Network Access is now active (sites
  must ask before reaching localhost or the local network), new for users
  upgrading from 159.0.1.
- Decide whether to bump `assets/l10n-pin.txt` (unchanged since 157; see above).
- After the first 160 device run, regenerate `expected-prefs.txt` from it. Its
  two new LNA rows are hand-written expectations until then.

Seen, not changed:

- `dom.speculation_rules.enabled` (I1 of the pref-drift review): 160 lets a
  Nimbus feature switch speculation-rules prefetch on
  (`toolkit/components/nimbus/FeatureManifest.yaml:4812`). The default stays
  `@IS_NIGHTLY_BUILD@`, so it is off in release, and Nimbus rollouts are locked
  off. No `defaultPref` added.
- `svg.use-element.block-inline-event-handlers` (I3): new hardening pref,
  `@IS_NIGHTLY_BUILD@`, off in release. Left at upstream's default, as upstream
  LibreWolf 160.0-1 does.
- 160 adds a "Search bar with image search" Glance widget
  (`SearchBarWithLensWidgetReceiver`). Its Lens button is hidden because
  `googleLensIntegrationEnabled` is constant false; the widget stays in the
  picker.
- 160 adds an isolated GMP process (`media.gmp.android.isolated-process`,
  `@IS_NIGHTLY_BUILD@`, off in release). No patch touches it.
- Desktop: Mini Window (`browser.mini-window.enabled` now true in `firefox.js`)
  is left at upstream's default, as upstream LibreWolf 160.0-1 does.
- Upstream LibreWolf's 158 and 159 cfg changes that Redoubt never took are
  still not ported (33 calls); only the 160 delta is.
