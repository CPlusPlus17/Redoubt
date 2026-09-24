# Correction: current-profile pref I/O cannot use plain xpcshell

The earlier test_savePrefFileAsync.js current-file cases are **unrun definitions with an invalid xpcshell profile assumption**, not runnable target coverage. Syntax validation did not detect this. Files remained unchanged after notifying owner/root, pending exact scope for replacement.

Actual opened chain:

- Preferences.cpp:4172 assigns mCurrentFile only in Preferences::InitializeUserPrefs. That method resets/reloads user prefs and establishes the current file. Preferences registers profile-before-change(-telemetry) and suspend observers, not a profile-do-change initializer.
- nsAppRunner.cpp:5986 calls nsXREDirProvider::InitializeUserPrefs; its implementation at nsXREDirProvider.cpp:611 calls the native initializer. Normal GeckoView runtime follows XRE_main.
- XPCShellImpl.cpp:1201 instead initializes XPCOM directly. testing/xpcshell/head.js:1957 reads the harness _PREFS_FILE using readUserPrefsFromFile; that API parses into the user branch but does not set mCurrentFile. do_get_profile at head.js:1351 registers directories and notifications, not the native initializer.
- Android is not an exception: XpcshellTestRunnerService.java:79 passes -xpcshell; GeckoThread.java:168–176 sets its xpcshell mode; APKOpen.cpp:425 dispatches XRE_XPCShellMain rather than XRE_main. The Java call to GeckoRuntime.create in the service is therefore not proof of a normal initialized pref profile.

Correct executable split: retain xpcshell for no-current-profile rejection and actual ordered distinct backup-file writes/failure outcomes; place current-file, clean-state, disk-error/retry and shutdown tests in a normal GeckoView instrumentation runtime or native gtest fixture that really calls InitializeUserPrefs. Do not weaken the production no-profile check or mock the save method.

GeckoSessionTestRule.evaluateExtensionJS delegates ordinary background Eval (background.js:12). It is not arbitrary privileged chrome evaluation. A narrow browser.test experiment method in test-support/test-api.js + schema can perform the actual native pref I/O and return receipts, called from the test background via evaluateExtensionJS. Those exact files need declared task ownership. RuntimeCreator holds a shared runtime, so a successful native profile-shutdown test must run in its own instrumentation invocation/process, not close the shared profile before later test classes run.

Root and owner notified; no device/VM execution or production modification. Target validity remains pending until the test split is implemented and run.
