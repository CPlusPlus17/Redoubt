The initial four `test_savePrefFileAsync.js` tasks and the extension-control xpcshell disk assertion were authored but **never run**. They assumed `do_get_profile()` initialized the native current preference file. Independent review disproved that assumption before target execution; the original definitions remain in `original-unrun-target-tests.tar.gz`, with their original final source receipt in `original-source-files.json`.

The initializer route is source-proven (`test-initializer-source.json` pins every referenced file):

- `modules/libpref/Preferences.cpp:4157–4172`: only `InitializeUserPrefs()` assigns `mCurrentFile`; it resets/loads the profile before assigning it.
- `toolkit/xre/nsAppRunner.cpp:5986` calls `nsXREDirProvider::InitializeUserPrefs` → `toolkit/xre/nsXREDirProvider.cpp:611–613` → that native initializer during normal `XRE_main`.
- Android `XpcshellTestRunnerService.java` passes `-xpcshell`; `GeckoThread.java:168–176` selects xpcshell, and `mozglue/android/APKOpen.cpp:425` invokes `XRE_XPCShellMain`.
- `js/xpconnect/src/XPCShellImpl.cpp:1201` initializes XPCOM, but does not run the normal profile initializer. `testing/xpcshell/head.js:1351` registers profile directories and notifications; its line1957 reads an explicit prefs file. Neither sets `Preferences.mCurrentFile`, and the preferences observer does not initialize it in response to those notifications.

The correction preserves that no-profile rejection. Xpcshell verifies `NS_ERROR_NOT_INITIALIZED` before mutation, plus actual independent backup/error writes and pending-backup flushing. Extension admission tests use real fixture prefs and explicitly assert durable-control rejection without a current profile. They do not mock a successful native save to imitate a real profile.

Actual current-profile writes move into a normal GeckoView test runtime. The existing privileged test-support extension exposes one bounded test helper with fixed scenarios and fixed private fixture paths; it is built only into the instrumentation test APK. There is no production test-only initializer, alternate prefs destination, profile-prefs overwrite in an ordinary app, or weakened current-profile guard.

The ordinary class tests independent current/backup outcomes, clean-state forced writes/reset and real file failure/retry. Final shutdown has its own class and must be run in a fresh dedicated instrumentation invocation with exact class selection and `redoubtAllowProfileShutdown=true`; a broad suite does not have permission to shut down its shared runtime. Root's native driver must grade every requested method as actually executed, not count an assumption skip as success. Target compilation and all native/instrumentation execution remain **pending**.

Two additional existing test-support files were copied from the frozen source only after ownership commit2c7cc9b. No registered predecessor patch touches them. Root independently compared the actual guest SHA256 values and confirmed exact equality; `test-fixture-before.json` and `test-fixture-baseline.tar.gz` preserve these inputs. All other before lineage remains the original captured guest+Task31.
