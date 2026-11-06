# Firefox 159.0.1 rebase (both targets), 2026-11-06

Branch `rebase/159.0.1` (worktree `~/redoubt-artifacts/rebase-159.0.1/repo`),
off main 64bdb411. Closes, once a signed release is published: #11 (Firefox
159.0), #12 (MFSA 2026-118, 167 CVEs, 108 high), #13 (Firefox 159.0.1, MFSA
2026-123, CVE-2026-120572 high). 159.0 is skipped: 159.0.1 carries both.

## Input

| | |
|---|---|
| tarball | `archive.mozilla.org/pub/firefox/releases/159.0.1/source/firefox-159.0.1.source.tar.xz` |
| size, sha256 | 817946068 bytes, `b5fe407199685f8bddf3b2c81feb8b805429e6f3d307c9430f53456f85b6e063` |
| signature | `make fetch TARGETS=android`: good signature, made 2026-11-02 18:59:52 CET, subkey `827E658608679618CD349F93678E455D76767AA3`, primary `14F26682D0916CDD81E37B6D61B7B526D98F0353` (Mozilla Software Releases) |
| unpacks to | `firefox-159.0.1/`, `config/milestone.txt` = `159.0.1` |

`version`, `version.android` = `159.0.1`; `release`, `release.android` = `1`.

## Patches (check-patchfail, default fuzz)

| run | before | after |
|---|---|---|
| desktop (common + desktop) | 66 patches, 2 failing | exit 0 |
| android (common + android) | 74 patches, 18 failing | exit 0 |

`patchfail/before-*.out`, `patchfail/after-*.out`. After: the only fuzzed hunks
are in upstream LibreWolf's common patches (8 on android, 31 on desktop), as
on 158. Every android entry applies at `--fuzz=0` in list order.

Method (the 158 rebase's, `tools/replay.py`): a scratch git repository of the
pristine 159.0.1 tree; `common.txt` + `android.txt` replayed in order, android
entries at `--fuzz=0`; at each failing entry the patch was applied with fuzz,
the rejects fixed by hand, and the patch regenerated from that step's diff.
Headers are kept; the patches whose code changed shape carry a "159 rebase"
note.

### Retired (upstream in 159)

| patch | evidence |
|---|---|
| `newtab-fix` (desktop) | 159's `ExperimentAPI.ready()` has the hunk verbatim; upstream LibreWolf dropped it (ae1ca32d) |
| `android/onecrl-bundle-backport` | bug 2084311 in 159.0.1's `RemoteSecuritySettings.sys.mjs` ("reversed or already applied") |
| `android/isolation-media-drain-backport` | bug 1987001 in 159 (`MaybeDeferDrain`, `mDrainTimer`, `mIsMediaCodec`). Not gated upstream: Android 8-11 software ffvpx now drains the 159 way, Firefox 159's own behaviour |

### Reduced

`android/isolation-eme`: 159 has bug 2067689 (parent NDK Widevine query,
`gfxVars::WidevineSupport()`; the Java `MediaDrmProxy.isSchemeSupported` /
`IsCryptoSchemeSupported` are deleted) and bug 2075686 (RemoteCDMProxy session
close). Kept: isolated content offers Widevine only H.264/AAC in MP4 (159
offers every platform codec, VP9/AV1/WebM included, which RDD refuses under
`isolation-media-codecs-in-content`), and the three RDD CDM fixes 159 still
lacks (expiration 0 -> NaN; `RecvInit` waits for the AMediaCrypto; Android
12-13 license request after a service certificate). The pref
`media.redoubt-eme.widevine-support` is gone.

### Rewritten for 159's code, same intent

| patch | what 159 changed |
|---|---|
| `disable-data-reporting-common` | glean-sdk 70.2.0 -> 70.2.1 in `python/sites/mach.txt` (upstream LibreWolf a8f2861f) |
| `android/no-adjust` | four deleted metrics files and three tests changed upstream (deletions regenerated); `OnboardingFragment`'s `RtamoAttributionHandler` gained an argument |
| `android/no-onboarding` | continuous onboarding gate moved into `start()`; review-prompt and default-browser-prompt checks gained a continuous-onboarding branch; upstream tests that expected the prompts are inverted |
| `android/no-glean` | `GleanDebugToolsScreen.kt` changed (deletion regenerated) |
| `android/no-gms` | `PlayStoreReviewPromptController` lost its `Dispatchers.IO` hop; upstream's new web-fallback test kept without `ReviewManager` |
| `android/no-suggest` | context only (fuzz 1 -> 0) |
| `android/ubo-preinstall` | strings.xml tail |
| `android/privacy-defaults` | the four autofill defaults became `{ isAutofillSupported }` |
| `android/sync-opt-in` | `onEmailMaskClick` no longer wraps in `withContext` |
| `android/firefox-suggest-policy` | import block |
| `android/global-privacy-controls` | nav_graph.xml tail |
| `android/session-cleanup` | `CookieStorage::GetCookies` replaced by `GetAll` |
| `android/disable-157-cloud-features` | "Add shortcut" graduated (Nimbus feature and `enableAddShortcutsImprovement` removed); the tile is hidden in `TopSites.kt` and `ShortcutsScreen.kt`; `maybeSetupIPProtection` moved; the Lens switch gained a listener; `canShowIPProtectionPrompt()` lost its argument |
| `android/isolation-media-prefs` | `GeckoRuntime.init()` gained the isolated-process env override before the zygote line |
| `android/no-webcompat-reporter` | `BrowserMenuBuilder` replaced by `MenuConfigurations`; test moved to `MenuBuilderTest` |

Counts: 22 common / 50 android / 43 desktop-only = 115 (`board.py --check-scope`).

## Gates

`gates.txt`: `board.py --check`, `--check-scope`, `--check-cfg-split`,
`--diff-mozconfig --strict`, `lint-patch-scope.py`, `check-patch-order.py`
(four stale isolation-eme rows removed: it no longer touches
`StaticPrefList.yaml`) and `--check-policies` on the pristine 159.0.1 tree:
all ok.

`scripts/tests`: 9 of 19 files pass, the same 9 as unchanged main on this VM;
the other 10 fail identically on main (no `node`, no APK outputs, receipt pins
from earlier rebases). `test-android-smoke.py EmeGateTests`: 14 tests, ok.

## Section 6, pref drift (158.0.1 vs 159.0.1, names our three cfgs set)

- 6a: `toolkit.coverage.enabled` and `toolkit.coverage.endpoint.base` are no
  longer declared; 159 removed the feature (no reader left). The locks are
  harmless no-ops.
- 6b: no other default changed for a pref we set (StaticPrefList, all.js,
  firefox.js, geckoview-prefs.js).
- 6c: no pref we set is `mirror: once` in 159.
- 6d: `--check-policies` ok (132 GeckoView prefs, 23 shipped by us).
- Nimbus release defaults (`tools/fmldiff.py`): added `account-sync-decouple-m1`,
  `migrate-onboarding-state`, `wayback-machine`, all `enabled: false`; removed
  `add-shortcuts-improvement` (graduated, see above) and `native-share-sheet`.

## Harness

`--check-eme` no longer reads `media.redoubt-eme.widevine-support`: whether the
device has Widevine comes from its DRM HAL listing (`service list`, `lshal`),
so a rejection on a device with Widevine fails.

## Not done here

This VM has no Android SDK, emulator or Gecko build environment. Not run: the
x86_64 / arm64 build, Fenix unit tests, the smoke (SMOKE.md) and the device
acceptance (`--check-video`, `--check-eme`, first-run capture). They are the
next step and decide whether this branch ships.

Upstream LibreWolf (librewolf/source main, 159.0.1-1) also dropped
`rust-gentoo-musl.patch` without a stated reason; it still applies here and
stays.
