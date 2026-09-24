# Combined isolated-child application attachment correction

The actual failed current167 APK source calls FirefoxSuggestPolicy.initialize
and AccountServices.initialize before checking the process. Both read app
SharedPreferences; an Android30 isolated Gecko child cannot use that storage
and repeatedly dies during FenixApplication attachment. The minified crash frame
cannot attribute the failing read exclusively to one initializer. Task20 retains
the actual log; this directory retains the expanded actual source and the exact
actual FirefoxSuggestPolicyTest body from that same167 manifest.

Apply corrected Task20 first, then this Task26 patch. Fenix performs its existing
safe process check before either persisted policy initializer. The main process
retains both saved-choice readers before locale resources and content providers.
Non-main processes install an explicit constant four-false FxSuggestChoices reader
and close AccountServices entirely in memory, then attach the original Context.
The A-C FxSuggestChoices defaults remain true for unrelated embedders. Child
closure invalidates older Suggest tickets without constructing policy listeners,
Settings, storage, a network client or a native Suggest service.

The existing legacy Robolectric test application restores its explicit Account
and Suggest opt-in fixture after super.attachBaseContext, independently of the
simulated process name before @Before. Its production initializer hooks do
nothing. This is confined to the test application; policy tests instantiate plain
FenixApplication. The new combined child test has a Context that throws on any
app preference/system-service access and verifies both admission policies closed,
a previous Suggest ticket invalid, and saved parent choices unchanged. Its
isMainProcess result is mocked. The existing main absent/true/false and ordinary
query choice tests remain. Real Android process detection and target test behavior
are independently pending.

The captured support-ktx helper uses Application.getProcessName on API28+ without
Context services/preferences. The older-API fallback retains an ActivityManager
lookup before its isolated-process condition; no all-API zero-service-call claim
is made. GeckoThread's private child predicate depends on later initialization and
is deliberately not used during Application attachment.

`source-overlay.json` binds three Task26 outputs and two changed Task20 predecessor
bodies. Every other Task26 output remains identical. `current167-overlay.json`
separately binds the combined six replacements to actual source501d, with the
new manifest4ff8b616 and a six-file source tar. The captured actual FenixApplication
and helper bodies match the reconstructed original26 outputs byte-for-byte. No
intermediate Task20 whole FenixApplication file is substituted into the integrated
source. The 167 path set is unchanged: 161 paths remain unchanged while six existing
paths are replaced. Native5's245 composition remains separate.

Run `verify.py` to reproduce both scoped source replays, GNU zero-fuzz application
and combined167 source/hash derivation. These checks do not compile Kotlin or
execute Android tests. Task20 now has 34 authored tests and Task26 has 28; the
combined increment adds two Fenix tests and one A-C account test in existing
classes. Root must run the focused policy/application/account/Suggest classes,
the full Fenix and selected component gates, the rebuilt APK, and actual first
navigation with a surviving isolated child. Prior green source501d tests and its
failed runtime remain historical evidence, not a verdict for these changed bytes.
