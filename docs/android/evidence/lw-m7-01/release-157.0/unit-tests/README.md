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
One was a product bug: in addon-state-durability, re-enabling a disabled
extension on Android saved the choice but did not start the extension until
the next restart. The other changes were test bugs:

- Three tests stubbed the test global's `IOUtils` instead of the module
  global's.
- One test was missing an `AddonManager` import.
- The cookie test used an error-name pattern, and set no cookie prefs.

The release APKs do **not** contain the `XPIDatabase.sys.mjs` fix.
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

`toolkit/mozapps/extensions/test/xpcshell` and
`toolkit/components/extensions/test/xpcshell` were not run as whole
directories. Only our tests in them ran.
