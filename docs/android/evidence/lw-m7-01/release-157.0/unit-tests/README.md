# Firefox 157.0 Android test runs (2026-10-02)

Fenix and Android Components unit tests and Gecko xpcshell tests for the
157.0-1 patch set. This is the run the Definition of done asks for. It
covers every patch that inserts code.

## Where they ran

- **Fenix and Android Components unit tests** ran in the release tree
  `build/librewolf-157.0-1`, built from d0c4e13d, the tree of the four 157.0-1
  APKs. They used its `obj-x86_64` objdir, the `localhost/librewolf-android-build:fx157`
  image and the same container environment as `android-apk.sh`, with
  `./mach gradle --max-workers=8 --continue`. The patches committed after
  d0c4e13d change only hunk headers (identical trees) and xpcshell test files
  and one JS module. None of those reaches a Kotlin unit test.
- **xpcshell** needs a test-enabled Gecko and an Android device. A second
  `make dir` tree got the release x86_64 mozconfig with two changes:
  `--enable-tests`, and `--enable-android-subproject=geckoview_example`, the
  only subproject that has `:test_runner`. It got its own objdir, was built
  with `./mach build -j8` (peak 16.2 GB, MemAvailable never below 8.6 GB), and
  `:test_runner:assembleDebug` was built from it. The tests ran with
  `./mach xpcshell-test --deviceSerial emulator-5570` on a private x86_64
  emulator: `system-images/android-30/default`, the AOSP image without GMS,
  with `adb root`. The container reached the host adb server over the host
  network; client and server are both adb protocol 41.

## Fenix: `board.py --check-fenix-tests`

`check-fenix-tests.out`:

```
# 649 classes / 6066 tests from .../fenix/app/test-results/testDebugUnitTest
# failing 13 = 11 environmental + 2 known-real + 0 unexpected
ok: no failures beyond the documented allowlist
```

The first pass also gave three trim warnings (`check-fenix-tests-before-trim.out`).
`docs/android/fenix-test-allowlist.yaml` was trimmed as they asked. No class
was added and no ceiling was raised:

- `ReviewPromptMiddlewareTriggerCriteriaTest`, 16 → 9: upstream 157 has 9 tests
  in the class, and all 9 fail with `UnsatisfiedLinkError: megazord`.
- `AutofillSettingsMiddlewareTest`, 2 → 1.
- `HomeSettingsFragmentTest` left `known_real`: its 8 tests passed.

`fenix-targeted-classes.txt` lists the Fenix test classes our patches add or
edit, from the same run. All 42 ran with no failures. `MetricsUtilsTest` has
no tests on purpose: no-gms empties it and keeps the companion object.

## Android Components and GeckoView

`android-components-modules.txt` covers every module whose tests a patch
touches, plus `concept-engine`, which extension-update-controls changes, and
`:geckoview:testDebugUnitTest`, which runs no-gms's `WebAuthnUtilsTest`:

- 1,986 tests, 3 failures.
- The 3 failures are `WorkManagerSyncManagerTest` in service-firefox-accounts,
  with `UnsatisfiedLinkError: Unable to load library 'megazord'`. The stack
  runs `SyncManager.start` → `WorkManagerSyncManager.createDispatcher`
  (upstream line 103) → `DefaultRustSyncManager` → `syncmanager.UniffiLib`.
  sync-opt-in does not change that path. Its hunks in this file only add
  early returns to `syncNow`, `setEngineEnabled`, `startPeriodicSync` and
  `doWork`.
- This is the same host-JVM limit as the Fenix allowlist. There is no AC
  allowlist, so it is recorded here.

`android-components-targeted-classes.txt` lists the 19 AC/GeckoView classes our
patches add or edit. All ran with no failures.

The first AC run was stopped by the memory guard (MemAvailable 8.07 GB while
the xpcshell Gecko build ran). It was re-run after that build. The modules whose
test tasks had completed were up to date and kept their results; the rest ran.

## xpcshell: the tests our patches add

`xpcshell-targeted.txt`. None of these had ever run before. All 8 now pass
(the subtests passed include setup checks):

| test | patch | subtests |
|---|---|---|
| `netwerk/cookie/test/unit/test_cookie_session_cleanup.js` | session-cleanup | 55/55 |
| `modules/libpref/test/unit/test_savePrefFileAsync.js` | extension-update-controls | 14/14 |
| `toolkit/components/extensions/test/xpcshell/test_ext_android_update_settings.js` | extension-update-controls | 22/22 |
| `mobile/shared/modules/geckoview/test/xpcshell/test_global_privacy_settings.js` | global-privacy-controls | 31/31 |
| `toolkit/mozapps/extensions/test/xpcshell/test_addonStartup_save_failures.js` | addon-state-durability | 15/15 |
| `toolkit/mozapps/extensions/test/xpcshell/test_android_addon_state.js` | addon-state-durability | 80/80 |
| `toolkit/components/extensions/test/xpcshell/test_ext_permissions_android_durability.js` | extension-permission-durability | 19/19 |
| `toolkit/components/translations/tests/unit/test_android_translation_assets.js` | translation-assets | 12/12 |

To get there, four patches changed; `../receipts/README.md` lists each change.
Two were product bugs, both in addon-state-durability:

- Re-enabling a disabled extension on Android saved the choice but did not
  start the extension until the next restart.
- The add-on manager manifest run below found that an install listener's
  disable choice was overwritten. The other changes were test bugs:

- Three tests stubbed the test global's `IOUtils` instead of the module
  global's.
- One test was missing an `AddonManager` import.
- The cookie test used an error-name pattern, and set no cookie prefs.

The release APKs contain **neither** fix (`XPIDatabase.sys.mjs`, `XPIInstall.sys.mjs`).
`test-addon-state-durability.py --apk` against the 157.0-1 x86_64 APK fails on
`XPIDatabase.sys.mjs` for that reason. The fix ships only after a rebuild.

## xpcshell: the neighbouring directories

`xpcshell-neighbour-dirs.txt` covers four directories run with `--keep-going`:
`netwerk/cookie/test/unit`, `modules/libpref/test/unit`,
`mobile/shared/modules/geckoview/test/xpcshell` and
`toolkit/components/translations/tests/unit`. 46 passed and 3 failed. All 3
come from build configuration, not from patch code:

- `test_timestamp_fixup.js` and `test_chips_partition_capping.js` read Glean
  values that stay null. In this harness `testGetValue()` is null even right
  after a direct `record()`: `MOZ_GLEAN_ANDROID` hands metrics to the
  embedder's Glean, and Redoubt builds with data reporting off.
- `test_ChildCrashHandler.js` times out. The build has no crash reporter
  (`--disable-crashreporter`, no-crashreporter.patch).

## xpcshell: the add-on manager manifest, with and without addon-state-durability

addon-state-durability rewrites how `XPIDatabase`, `XPIInstall` and
`XPIProvider` persist on Android, so the whole
`toolkit/mozapps/extensions/test/xpcshell/xpcshell.toml` ran three times on
the same objdir and emulator (`xpcshell-addons-manifest.txt`):

1. **Baseline:** the patch's `toolkit/mozapps/extensions/internal/*` sections
   reverse-applied, then rebuilt.
2. **Patched** (with the `pendingUninstall` fix).
3. **Patched, final.**

| | pass | fail | skip |
|---|---|---|---|
| baseline | 109 | 12 | 31 |
| patched | 106 | 15 | 31 |
| final | 107 | 14 | 31 |

- **10 failures are the same in all three runs.** The tests behind them
  read Glean, telemetry or timeline values that this build does not record.
  They are not from our patch.
- **Our two tests** fail only in the baseline, as they should.
- **`test_install.js` was a bug, now fixed.** Its `test_userDisabled` showed
  that the patch's Android refresh of the existing add-on's disabled state
  ran *after* `onInstallStarted`. It overwrote a listener's
  `install.addon.disable()`. The refresh now runs before the listeners
  (`startInstall` in `XPIInstall.sys.mjs`).
- **Four upstream tests still fail only with the patch.** Each failure
  follows a deliberate Android design choice of LW-M7-19, not a slip. They
  are listed for the owner, and no test was skipped or edited for them:
  - `test_corrupt.js`: a failed `extensions.json` write (the test makes it a
    directory) rejects the operation on Android instead of being swallowed
    ("no swallowed failure", `AndroidAddonState`).
  - `test_reload.js`: after a temporary add-on reloads, uninstalling through
    the pre-reload wrapper throws "Add-on is no longer the installed
    instance". GeckoView looks extensions up by ID for every operation and
    does not hit this.
  - `test_undouninstall.js`: on Android `onOperationCancelled` fires after
    the durable write, so it arrives after `cancelUninstall()` returns, and
    the test expects it synchronously.
  - `test_startup_scan.js`: a sideloaded update is applied before the stale
    version starts (`update` → `startup`), instead of `startup 1.0` →
    `shutdown` → `update` → `startup`.

`toolkit/components/extensions/test/xpcshell` was not run as a whole
directory. Only our two tests in it ran.
