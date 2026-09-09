# Isolated-process startup correction

Actual Android30 runtime repeatedly failed before navigation in a zygoteTab
isolated Gecko child. The retained log has ContextImpl.getSharedPreferences
calling an unavailable UserManager from minified FenixApplication attachment.
The captured actual source has two unconditional preference-reading initializers:
Task26 Firefox Suggest and Task20 accounts. The frame cannot identify only one.
Both initializers require the combined correction; this Task20 commit alone is
not an installable runtime fix. Root owns the separate Task26 followup and target
build/test/runtime gates.

Task20 now reads the saved account choice only in Fenix's existing
`base.isMainProcess()` branch, before locale resources and content providers.
Non-main processes call `AccountServices.disableForProcess()`: only memory
changes, admission closes, generation advances, and restart-choice commits are
rejected before Context access. No account/engine data is read, written or reset.
Other A-C embedders retain their prior default and initialization semantics.

The actual captured support-ktx Context helper uses Application.getProcessName()
on API28+ without Context services or preferences. Its older-API fallback retains
upstream nullable ActivityManager lookup and isolated-process checking. This is
not a claim that every supported API avoids all system-service queries.
GeckoThread.isChildProcess() is private and depends on later native initialization
information; it is not an attachment-time replacement.

Two regression cases are authored: actual production child attachment through a
Context that throws on preferences/system-service calls, and memory-only admission
closure/generation/commit rejection with a saved parent choice preserved. The
child test controls isMainProcess through MockK; target/runtime process detection
is still independently required. Existing production absent/explicit parent
choice tests remain and now explicitly select a main process. No Kotlin test
ran in this host replay.

The fifth changed file is solely the legacy Robolectric application. It initializes
its explicit opted-in account fixture after super.attachBaseContext and before
providers, independently of the simulated process name before per-test setup.
Production-policy tests instantiate plain FenixApplication and bypass this fixture.
This avoids a global disabled-fixture change across unrelated existing tests.

`before-sync-opt-in.patch.gz`, `before-source-files.json`, all five before/after
bodies, actual source capture, current167 manifest and compressed exact crash log preserve the
old AC0 and source501 inputs. `source-overlay.json` describes Task20's scoped
outputs before later patches. A separate Task26 combined overlay must bind the
actual integrated FenixApplication and helper bodies; never apply Task20's
intermediate whole files directly onto current167.

Run `verify.py` for pinned source/patch replay, including GNU zero-fuzz application.
Targeted Fenix AccountServicesPreferenceTest, FenixApplicationTest,
FirefoxSuggestPolicyTest and the A-C account/Suggest admission classes must run,
followed by the full source-bound suite and rebuilt-APK first-navigation/lifecycle
checks. All target execution remains pending for these changed bytes.
