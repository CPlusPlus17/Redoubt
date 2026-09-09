# Patch scope — which LibreWolf patches reach Android

**Status: REVIEWED (LW-M1-01), RECONCILED (LW-M1-12).** LW-M1-01 opened all 53
patch files that existed then and classified each by what it *does*, checked
against the pristine `firefox-153.0.4/` tree. LW-M1-02..09 then split the seven
real straddlers into `-common` / `-desktop` halves, resolved `msix` to plain
desktop-only, and added three Android-only patches. LW-M1-12 deleted the split
monoliths, regenerated the `assets/patches.txt` shim and brought every count in
this file back in line with the lists. Each row below carries a one-line
justification and a reviewer mark. The path-based heuristic that seeded this file
is gone; where it was wrong, the row says so.

Reviewer: **LW-M1-01** (every classification row). "Reviewed" means: the patch was
read in full, every file it touches was traced to the `moz.build` / `jar.mn` /
preprocessor guard that decides whether that file is built on Android, and the
decision below follows from that guard rather than from the path.

Current classification: **24 common / 38 android / 36 desktop-only / 0 straddlers = 98
patch files.** `python3 docs/android/board.py --check-scope` re-derives all five
numbers from the lists and the files on disk and fails on any drift, including the
arithmetic — so these are checked, not asserted.

## Pending — on disk, deliberately in no list

No pending patches. On 2026-09-08 LW-M3-07 replaced the parked catalogue stub
with a genuine signed-XPI installer and a separate filtering-readiness bridge.
Both are registered in `android.txt`; source, packaging and lifecycle evidence is
under `docs/android/evidence/lw-m3-07/completion-20260908/`. Registration records
patch scope, not completion of the required APK build and runtime acceptance. LW-M7-12
also registers `privacy-defaults.patch`, with its shared-file ordering replay in
`docs/android/evidence/lw-m7-12/patch-integration/`; build and behavior gates
remain separate from this scope classification.

A `- <path> (LW-…)` bullet in this section is the only way `board.py --check-scope`
will tolerate a patch file that no list applies. Undeclared unlisted patches fail.

---

## How that maps to the live lists

`assets/patches/` drives the build. `assets/patches.txt` survives only as a
generated `common + desktop` shim for downstream builders and is retired by
LW-M7-01. LW-M1-12 regenerated it; it is exactly the output of the command
`check_compat_shim()` prints:

```
sed -e 's/#.*//' -e 's/[[:space:]]*$//' \
  assets/patches/common.txt assets/patches/desktop.txt \
  | grep . > assets/patches.txt
```

It is deliberately **not sorted**. LW-M0-13 removed the old `sort`, because
`scripts/check-patchfail.sh` applies the shim top to bottom and a sorted shim
claimed an application order the build never uses.

| list | entries | contents |
|---|---|---|
| `common.txt` | 24 | 17 pure-common **+ the 7 common halves of the split straddlers** |
| `desktop.txt` | 36 | 27 pure desktop + `msix` (not a straddler) **+ the 7 desktop halves** + `pref-pane/pref-pane-small` (moved in from its own call site by LW-M1-13) |
| `android.txt` | 38 | the three Android-side patches the M1 splits pulled in, plus `build-fixes` (LW-M2-02), `appservices-logins-addmany` (LW-M2-04), `no-nimbus` (LW-M4-03), `no-nimbus-toolkit` (LW-M4-13), `isolated-process` (LW-M5-02), `autoconfig-resource-fallback` (LW-M3-08/LW-M3-02), `no-onboarding` (LW-M4-10), `no-gms` (LW-M4-05), `branding` (LW-M4-07), `gradle-no-config-cache` (LW-M3-13), `rs-blocker-android` (LW-M4-08), `no-suggest` (LW-M4-11), `search-config` (LW-M4-06), `update-check` (LW-M6-06), `deterministic-version-code` (LW-M6-08), `ubo-readiness` and `ubo-preinstall` (LW-M3-07), `privacy-defaults` (LW-M7-07/LW-M7-12), `cookie-banner-rules` (LW-M7-13), `canvas-webgl-permissions` (LW-M7-14), `translation-assets` (LW-M7-16), `home-section-defaults` (LW-M7-24), `addon-state-durability` (LW-M7-19), `sync-opt-in` (LW-M7-20), `cookie-banner-controls` (LW-M7-23), `firefox-suggest-policy` (LW-M7-26), `no-default-shortcuts` (LW-M7-30) and the M4 dependency removals landing alongside it — one row each in the table below. |

The arithmetic, and it is now boring on purpose: **every patch file on disk is in
exactly one list**, so the three lists sum straight to the total, and
`common + android + desktop-only + 0 straddlers` is that same total. No count is
repeated in prose here, on purpose — the summary line at the top of this file is
the one place they live, and `board.py --check-scope` is what proves them.

Nothing is applied from a call site in `scripts/librewolf-patches.py` any more: LW-M1-09 removed the `xmas.patch` call site and LW-M1-13 moved
`pref-pane/pref-pane-small.patch` into `desktop.txt`, which is why
`check-patch-order.py`'s `OUT_OF_LIST_TAIL` is empty and `--check-scope`'s
`SEPARATE` set derives as empty from the script. Any prose about "separately
applied patches" is stale wherever it still appears.

The straddler count is zero: seven were cut in half by LW-M1-02..04 and
LW-M1-06..09, and the eighth (`msix`) was proved never to have been one by
LW-M1-05.

**The desktop build is still unchanged.** The set applied for `TARGETS=desktop`
is `common ∪ desktop`. LW-M1-01 moved five patches *between* the two lists
without changing that union; each M1 split replaced one monolithic entry with two
halves carrying the same hunks, in the same relative position; and `xmas`'s two
halves sit where its old call site put it in the sequence. The union is still the
same diff applied to a desktop tree. `scripts/librewolf-patches.py` compares the
shim as a set, and since LW-M1-12 regenerated it the two agree — the out-of-sync
warning is gone.

**The straddlers are gone, and Android now gets all seven common halves.** They
are no longer parked in `desktop.txt`, the monolithic files are deleted from
disk, and `scripts/check-patchfail.sh` therefore exercises the halves that
actually ship rather than the pre-split monoliths.

**Android now HAS the autoconfig channel — this paragraph used to say the
opposite and was correct when it was written.** `xmas-common` puts `lw/` into the
build, but on its own `FINAL_TARGET_FILES` at the package root does not reach the
APK: GeckoView packages from `mobile/android/`, and a top-level `librewolf.cfg`
fails `OmniJarSubFormatter.is_resource`, so it is packaged flat into
`dist/geckoview/` and dropped. That was true through M2 and it is what made
landmine L2's prescribed mitigation unavailable.

`patches/android/autoconfig-resource-fallback.patch` (LW-M3-08, landed by
LW-M3-02) closes it: the `.cfg` is *also* installed to
`defaults/autoconfig/librewolf.cfg`, which `is_resource` accepts, both it and
`defaults/pref/local-settings.js` are named in
`mobile/android/installer/package-manifest.in`, and `nsReadConfig` reads the
`.cfg` through `resource://gre/` on Android. Measured on a running build:
`librewolf.cfg` evaluates, and a `lockPref`'d pref survives the Fenix settings
screen that overwrites an unlocked control in the same session. See
`docs/android/AUTOCONFIG-SPIKE.md`.

That still does **not** make an Android build privacy-complete, for reasons that
have nothing to do with packaging: bare `pref()` calls in the `.cfg` write the
*user* branch and `GeckoView:ResetUserPrefs` clears it ~25 ms after autoconfig
runs (landmine L2b — 24 bare `pref()` calls in `common.cfg`, LW-M3-09), the
must-lock list is LW-M3-04's, and `distribution/policies.json` is still not under
`defaults/` and so is still dropped flat (LW-M3-06). And the `.cfg` the patcher
copies into `lw/` is still `settings/librewolf.cfg`, i.e. `common + desktop` —
the `common + android` composition is not wired up in
`scripts/librewolf-patches.py` yet. No one should read a green M2 build, or this
paragraph, as "the prefs are right on Android".

### `android.txt` — one row per entry, and why each exists

<!-- Deliberately not "N entries": this heading has been wrong three times.
     The count is derived by `board.py --check-scope`; if you land an
     android.txt entry, add its row below in the same change. -->

LW-M1-01's review turned up **no** Android-only patch among the 53 files that
existed then, and that finding still holds for those 53: each is common,
desktop-only, or a straddler whose common half belongs in `common.txt`. What
filled `android.txt` is new work the splits pulled in. The Android side of a
straddler is never "the straddler's Android half" — it is a separate patch under
`patches/android/`, written against `mobile/android/`, with its own file and its
own line in this table.

| patch | task | why it exists |
|---|---|---|
| `patches/android/disable-data-reporting-android.patch` | LW-M1-02 | `mobile/android/moz.configure:131-132` implies the *opposite* pair to `browser/moz.configure` (`MOZ_NORMANDY` False, `MOZ_SERVICES_HEALTHREPORT` **True**), so the common half alone leaves `MOZ_DATA_REPORTING` on for Android. Must be applied *with* `disable-data-reporting-common`, never instead of it. |
| `patches/android/neterror-jar.patch` | LW-M1-07 | Packages `illustrations/warning.svg` for `toolkit/themes/mobile`, which never includes `desktop-jar.inc.mn`. Insurance, not a fix — see the LW-M1-07 row below for why the reference is unreachable on Android three ways over. |
| `patches/android/webgl-prompt-default.patch` | LW-M1-08 | **Landmine L1.** Defaults `librewolf.webgl.prompt` to false on Android, where the prompt's UI and observers are all `browser/`-only. Without it `IsWebGLAllowed_impl` fails closed and every WebGL context dies silently. Shipped in the same change as the split, never as a follow-up. |
| `patches/android/canvas-webgl-permissions.patch` | LW-M7-14 | Android exact-origin native/GV/Fenix WebGL and canvas permissions, explicit session/private/remembered lifetime, acknowledged document-bound reload and saved exception controls. Supersedes the earlier prompt=false block only with the complete bridge. Source and mocked bridge tests exist; target ABI builds, Android tests and runtime rendering/consent checks remain pending. |
| `patches/android/translation-assets.patch` | LW-M7-16 | Android packaged full catalog and verified WASM, explicit cancellable pinned model downloads, cache-only passive translation/status paths, bounded verified decompression and local cache deletion. Desktop Remote Settings path and both Android allowlists are unchanged. Source/packaging tests pass; target build, actual DOM translation and offline/cancellation behavior remain pending. |
| `patches/android/home-section-defaults.patch` | LW-M7-24 | Default ordinary top sites, recent tabs, bookmarks and history home sections off on every channel. Existing stored section choices and real customization controls remain available; no history/bookmark database changes. Target tests and actual home/restart behavior remain pending. |
| `patches/android/addon-state-durability.patch` | LW-M7-19 | Android serializes and acknowledges database/cache persistence before extension lifecycle completion, restores/reconciles cached identities before startup, and preserves corrupt-database recovery and desktop writer behavior. Thirty-six actual-source tests pass; target build and immediate-restart behavior remain pending. |
| `patches/android/sync-opt-in.patch` | LW-M7-20 | Accounts and Sync default off with explicit enable/disable and process restart, persisted choices, preserved account data, guarded workers/auth callbacks and private-session disclosure. Source replay passes; all 28 authored Kotlin tests, compilation and actual lifecycle/network behavior remain pending. |
| `patches/android/cookie-banner-controls.patch` | LW-M7-23 | Independent normal/private reject-only global controls and domain exceptions, with acknowledged storage changes and no implicit site-data clearing. A canonical private-context generation now fences queued writes and scopes private exceptions through teardown. Root composition, 19 actual-JS checks and 43 C++ source assertions pass; target compilation, full Kotlin suite and device behavior remain pending. |
| `patches/android/firefox-suggest-policy.patch` | LW-M7-26 | Default-off Suggest master/web/sponsored/online controls preserve stored choices and gate lazy service construction, workers and queued requests. Source replay passes; 19 authored Kotlin tests, target compilation, device behavior and bundled local suggestion data remain pending. |
| `patches/android/no-default-shortcuts.patch` | LW-M7-30 | Empty bundled default shortcut seed matches the desktop default.sites input while preserving stored and manually added user data. JSON/hash/replay checks pass; packaged resource and fresh/upgrade/manual-add behavior remain pending. Separate bookmark seeding is still unverified. |
| `patches/android/autoconfig-resource-fallback.patch` | LW-M3-08, landed by LW-M3-02 | **The autoconfig/`lockPref` channel — landmine L2's mitigation.** Three hunks, one mechanism: `nsReadConfig::openAndEvaluateJSFile` takes the `resource:` branch on Android (`#if defined(MOZ_WIDGET_ANDROID)`, *not* keyed off a failed `NS_GRE_DIR` lookup — that lookup succeeds and answers the APK's `lib/<abi>` dir, so the obvious patch is dead code and was measured to be); `lw/moz.build` also installs the `.cfg` as `defaults/autoconfig/librewolf.cfg`, the only shape `OmniJarSubFormatter.is_resource` lets into `omni.ja`; and `mobile/android/installer/package-manifest.in` names that file and `defaults/pref/local-settings.js` by hand, because it is an explicit list with no root wildcard. Ordering: **after `xmas-common`**, declared in `scripts/check-patch-order.py`. |
| `patches/android/build-fixes.patch` | LW-M2-02 | The Android build fixes that belong to no single LibreWolf patch — currently one hunk, `computeVersionCode()`'s `Integer.parseInt()` against the `153.0esr-1`-shaped `MOZ_APP_VERSION` the patcher writes. **Kept last in the list on purpose:** it is the collection point for build breakage, and nothing else in any list touches `build.gradle`. Nothing was dropped from `common.txt` to make the build green. |
| `patches/android/appservices-logins-addmany.patch` | LW-M2-04 | Re-exports `add_many` on the `DatabaseLoginsStorage` wrapper; upstream skew exposed by `--enable-appservices-in-tree`. Re-check on every rebase. |
| `patches/android/no-nimbus.patch` | LW-M4-03 | Severs the Nimbus remote-config channel (`serverSettings=null` → the Rust `NullClient`, `maybeFetchExperiments()` no-oped, `setFetchEnabled(false)`, `initialExperiments` unwired). It also raises the fission `isolationStrategy` FML default from 0 to 2 in the same change, because `Core.kt:207-208` applies that value unconditionally and disabling the remote channel alone would have cemented `ISOLATE_NOTHING`. LW-M5-01 owns the final 1-vs-2 choice and applies after this. |
| `patches/android/isolated-process.patch` | LW-M5-02 | Forces `isolatedProcessEnabled(true)` and `appZygoteProcessEnabled(true)` at the `GeckoProvider.kt` call site. Gecko's own content sandbox is not compiled on Android (no `MOZ_SANDBOX` in the Android `config.status`), so Android's isolated uid plus the app zygote **is** the content-process containment. Hard-coded rather than set in `nimbus.fml.yaml` so it cannot be lowered by an experiment, a Fenix settings write or an upstream default flip. |
| `patches/android/about-config.patch` | LW-M4-09 | **about:config on the release channel.** `GeckoProvider.kt:123` gates `.aboutConfigEnabled()` on `Config.channel.isBeta || isNightlyOrDebug`, and `Config.channel` is `BuildConfig.BUILD_TYPE` (`Config.kt:46-56`), so the one build type LibreWolf ships is the one without a pref editor: the argument becomes GeckoView's `general.aboutConfig.enable` `Pref` (`GeckoRuntimeSettings.java:768`) and `nsAboutRedirector.cpp:285-288` answers about:config with `NS_ERROR_NOT_AVAILABLE` when it is false. **Not fixable from `librewolf.cfg`** — `RuntimeSettings.Pref.addToBundle()` commits `mIsSet ? mValue : defaultValue` on every startup, so the release build actively pushes `false` over `GeckoView:SetDefaultPrefs` *after* autoconfig has run (landmine L2), which is why the fix is at the Kotlin call site and is a literal `true` rather than a Settings/Nimbus lookup. **No warning interstitial is removed, and none exists to remove:** `nsAboutRedirector.cpp:106-113` maps about:config to `chrome://geckoview/content/config.xhtml` on Android, and `toolkit/components/moz.build:103-113` does not build toolkit's `aboutconfig` for `mobile/android` at all — so desktop's interstitial, its `browser.aboutConfig.showWarning` pref (shipped false at `common.cfg:600`, **dead code on Android**) and its `about-config-intro-warning-*` strings are simply not in the APK. Checked in the built `omni.ja`: `chrome/geckoview/content/config.xhtml` is present, no toolkit `aboutconfig` is. That page *does* handle locked prefs (`config.js:583-584,708-710` + `config.css:210-228` draw a padlock and disable the field), so LW-M3-04's locks render read-only rather than broken. Ordering: shares `GeckoProvider.kt` with `isolated-process` above, **order-free by measurement**, declared in `scripts/check-patch-order.py`. |
| `patches/android/no-nimbus-toolkit.patch` | LW-M4-13 | **The SECOND experiment client.** `toolkit/components/moz.build:147` is an unconditional `DIRS += ["nimbus"]`, so the Gecko/JS Nimbus (`ExperimentAPI.sys.mjs` plus 12 more modules and 3 schemas) ships in the Android `omni.ja`, with `resource nimbus toolkit/res/nimbus/` mapped in its `chrome.manifest` — verified in the built APK, not in the source tree. `no-nimbus.patch` addressed only the Kotlin/Rust SDK. Measured on a running build: the JS side does **not** reach the network today, but only by four accidents — no shipped code calls `ExperimentAPI.init()` on Android (its only non-`browser/` callers are `normandy`, not built here, and the background-task path, which needs a command line); `RemoteSettings.pollChanges`'s default-client fallback (`remote-settings.sys.mjs:187-216`) needs a JSON dump or a local DB for the collection and there is neither; `resource://normandy/` and `resource://messaging-system/` are both absent from the APK's `chrome.manifest`, so `lazy.log` and `CleanupManager` throw; and `ExperimentAPI.enabled` throws because `Services.policies` is undefined. **The last one is the real hole**: `enabled` is `labsEnabled || rolloutsEnabled || studiesEnabled`, `labsEnabled` is evaluated first and is a bare `Services.policies.isAllowed("FirefoxLabs")` that reads **no pref**, so neither `app.shield.optoutstudies.enabled` nor `nimbus.rollouts.enabled` covers it — the moment anything defines `Services.policies` on Android it becomes true and the loader syncs `nimbus-desktop-experiments`. Three hunks in one file (`init()`, `#computeEnabled()`, `labsEnabled`), each guarded on `AppConstants.platform === "android"` so the patch is safe to promote to `common.txt` without silently changing desktop, where `labsEnabled` **is** true today. `DIRS` is deliberately not guarded out: `lib/NimbusFeatures.cpp` is linked into libxul and read from C++ by `KeySystemConfig.cpp`, `GMPParent.cpp`, `UtilityProcessHost.cpp` and `Preferences.cpp`. |
| `patches/android/no-onboarding.patch` | LW-M4-10 | **The first-run flow and the home-screen promos.** Eight files, one measurement: a 90 s `--first-run-capture` on a factory-fresh AVD went from 47 outbound events over 8 hostnames to 37 over **5** (an earlier version of this row said 4, and the derived phrase 'the four that remain'; the capture it cites has five hostnames — falsified by the skeptical verification of LW-M4-10), and the five that remain are LW-M4-08's (remote settings), LW-M4-01's (Glean) and LW-M4-11's (`ads.mozilla.org`, the sponsored-tile feed). Onboarding is off in Kotlin rather than in `nimbus.fml.yaml` (LW-M4-03's file), and `Settings.shouldShowOnboarding()` returns `false` outright because its other arm, `enablePersistentOnboarding`, is a real SharedPreferences boolean that forces the flow on every `HomeActivity` creation regardless of the feature flag. `PocketMiddleware`'s two `startPeriodic*Refresh()` calls are deleted, not gated: they were the only callers of `merino.services.mozilla.com` and the MARS spocs endpoint, and a WorkManager periodic job runs its first pass immediately, so a "4-hourly" feature was a first-run leak. `ContentRecommendationsFeatureHelper` returning false additionally turns the two Pocket prefs into `DummyProperty` (`FeatureFlagPreference.kt:115-120`), i.e. unwritable, and `HomeSettingsFragment` already hides both toggles on the same condition. **The android-components hunk is the surprise**: `BrowserIcons`' first preparer injects an icon URL the site never declared, so merely drawing the first-run home screen fetched the two `initial_shortcuts.json` tiles' favicons from Mozilla's CDN. Proved by ablation, and switching `enableMerinoManifest` off is a regression rather than a fix — it moves the fetch to google.com and www.wikipedia.org. Also off: the Terms of Use bottom sheet (Mozilla's legal text, in a browser that is not Mozilla's) and the Play Store review prompt. |
| `patches/android/no-gms.patch` | LW-M4-05 | **Every Google Play services dependency.** Firebase Cloud Messaging, Play Integrity, the Play In-App Review API, the Google Advertising ID client, the `com.google.android.gms:oss-licenses` Gradle plugin and the Play services FIDO2 backend inside GeckoView. Measured on the pre-patch APK, not grepped: **2,623 defined dex classes** (1944 `com.google.android.gms`, 459 `com.google.firebase`, 220 `com.google.android.play`) and **26 google/firebase-named entities in the MERGED manifest**, only one of which is written in Fenix's own `AndroidManifest.xml` — among the merged-in ones a `FirebaseInitProvider` ContentProvider, i.e. code that runs before `Application.onCreate()`. Both go to **0**; `--check-no-gms` goes from 4,474 to 2, and the two survivors are `static final String` fields of AndroidX's `ActivityResultContracts$PickVisualMedia` (the photo-picker backport's implicit Intent action), not a Play services artifact — see the patch header. Two features were *already inert* and that removed nothing: push never worked in a LibreWolf build (no `google-services.json`, no `project_id` string resource) and `BuildConfig.GPS_INTEGRITY_TOKEN` was always empty. Costs, all in the header: Sync send-tab degrades from push to **on-demand** polling (Sync Now / synced-tabs screen / device rename — *not* the four-hourly periodic sync); Web Push for sites is gone; WebAuthn keeps working through the platform Credential Manager on **Android 14+** and is **lost below that**, where Play services FIDO2 was the only backend. Contradicts this task's board text on two points, both checked: Play Integrity feeds the MLPA/summarise client and **not** the add-on collection (so LW-M3-07 is unaffected), and there is **no GMS location provider** in 153 to remove — `Geolocation.cpp:743` picks `AndroidLocationProvider` unconditionally. Ordering: **after `no-adjust` and after `no-glean`**, both measured per shared file and declared in `scripts/check-patch-order.py`. |
| `patches/android/r8-keep-rules.patch` | LW-M6-07 | **Restores the consumer ProGuard file the build already references.** `third_party/application-services/build-scripts/component-common.gradle` declares `consumerProguardFiles "$appServicesRootDir/proguard-rules-consumer-jna.pro"` on the AAR's release buildType, but that file is **absent from the ESR tarball** (`tar -tJf`; the per-component `android/proguard-rules.pro` files are empty boilerplate, not a substitute). So the in-tree Nimbus AAR ships with zero consumer rules, and in `fenix:assembleRelease` R8 strips the `@Structure.FieldOrder` runtime annotation off the uniffi `RustBuffer` classes — `Structure.getFieldOrder()` then returns an empty name list and the app dies on launch (`java.lang.Error … enough names [0] ([]) to match declared fields [3]`, reproduced in `~/lw-m4-09/evidence/release-r8-crash.logcat`). That is why every "release" APK built so far needed `-PdisableOptimization`. The patch adds the file with content byte-identical to upstream Mozilla's (`application-services` main, 949 bytes, `cmp`'d): `-keepattributes …RuntimeVisibleAnnotations…` plus `-keep class org.mozilla.experiments.nimbus.internal.** { *; }` and the JNA keeps. Stays in `android.txt` because it is a pure Gradle build input the desktop build never consumes — the desktop tree must stay byte-identical to stock. No ordering constraint: no other patch in either list touches the file. |
| `patches/android/fenix-abi-split.patch` | LW-M6-07 | **Makes the Fenix ABI split honour the `--abis` request.** `fenix/app/build.gradle`'s `splits` block hardcoded `include "armeabi-v7a","arm64-v8a","x86_64"`, so `--abis x86_64` still produced the full three-ABI split plus a universal and `scripts/android-apk.sh`'s `apk_index` check (which asserts the produced set equals the requested set — correct to do so) exited 1 with `AGP split for [arm64-v8a,armeabi-v7a,x86_64], expected [x86_64]`. The owner's verdict: the check is right, the build is wrong. Generalises the existing `benchmarkTest` branch (which already proves a property can drive the split set — it restricts to `arm64-v8a`) with a `fenixSplitAbi` property: when set to a comma-separated ABI list it includes exactly those ABIs and keeps a universal (the check requires exactly one), otherwise behaviour is unchanged. `scripts/android-apk.sh` passes the requested `--abis` set as `-PfenixSplitAbi`, reusing the `MOZ_ANDROID_FAT_AAR_ARCHITECTURES` env var it already sets for both passes. The `splits` block is touched by no other patch, so the hunk is in vanilla coordinates (identical in the desktop and ESR trees, verified by diff) and order-free against the four `fenix/app/build.gradle` touchers (no-adjust, no-glean, no-gms, no-crashreporter) — all four pairs recorded in `scripts/check-patch-order.py`. |
| `patches/android/l10n-strings.patch` | LW-M4-12 | **The Fenix UI's strings, in every locale.** `mobile/android/fenix/l10n.toml` has `basepath = "."`, so mozilla-l10n/android-l10n is synced into in-tree `res/values-*/strings.xml` before upstream cuts a release — 4,969 values files across 81 resource directories, 250,412 translated string rows in the built APK — and neither `--with-l10n-base` nor the repository's `l10n/` overlay reaches one of them. The patch adds `mobile/android/lw-brand/` (rewriter, brand map, android-l10n pin, Gradle glue, host-side UI scanner) and one `gradle.projectsLoaded` hook at the end of `mobile/android/shared-settings.gradle`. The rewrite runs per module as `:<module>:lwBrandStrings`, writes a rewritten copy of each `res` directory into that module's build directory and **replaces** `res.srcDirs` with it: the source tree is never mutated (contrast landmine L4), and replacing rather than overlaying is forced — a second srcDir in the same source set makes every rewritten string a duplicate-resource error. Measured with `aapt2` over the built `resources.arsc`: brand-word occurrences in string values **6,259 → 0**, with 300 rows of *enumerated* exception (`firefox.com/pair` in the two Mozilla-account pairing instructions, and Google's `client=firefox` suggestion-URL example) and 16 internal key strings whose value equals their own name (`pref_key_*`, `mozac_error_*`) deliberately untouched — rewriting those breaks stored preferences and error-page image lookups, which a `sed` over `strings.xml` would do silently. **37 locales spell the mark in their own script** (Фајерфокс, فايرفوكس, ഫയർഫോക്സ്, ෆයර්ෆොක්ස්, ᱯᱷᱟᱭᱟᱨᱯᱷᱚᱠᱥ), so an ASCII substitution moves the problem rather than solving it; those spellings are derived from the android-l10n commit pinned and sha256-verified in `mobile/android/lw-brand/android-l10n-pin.txt`. Anything the map cannot clean is **dropped** from the translated file and falls back to the rewritten English string — 43 (string, locale) pairs on this tree, listed in each module's `build/lw-brand/dropped.txt`. No ordering constraint: `shared-settings.gradle` is touched by no other patch, which is why the hook is there and not at the end of the root `build.gradle`. See `docs/android/L10N-ANDROID.md`. |
| `patches/android/gradle-no-config-cache.patch` | LW-M3-13 | **Turns the Gradle configuration cache off for the Android build.** Every Gecko/AAR pass died at `:geckoview:compileDebugKotlin` with *"Could not **load** the value of field `__buildFusService__` … Cannot set the value of a property of type `BuildFusService` using a provider of type `FlowActionBuildFusService`"*. The operative word is **load**: this is configuration-cache *deserialization*. The Kotlin Gradle plugin writes its FUS usage-statistics build service into the cache as `FlowActionBuildFusService` and reads it back into a field declared `BuildFusService`; the types do not round-trip. The cache is therefore not *stale* but *unusable* — deleting `<srcdir>/.gradle/configuration-cache` does not help, and a freshly written entry fails identically. Two things disguised this and are worth recording: the cache lives in the **source tree**, not the `--outdir`, so every "clean fresh outdir" run silently reused it; and `armeabi-v7a` is both first in `DEFAULT_ABIS` and the default `--fat-host-abi`, so in a 3-ABI run it always failed first and the other two ABIs never ran, manufacturing an "ARM-specific" conclusion from a single data point. Three diagnoses were drawn and acted on before this one — ARM-specificity; a Kotlin 2.3.21-vs-2.3.20 mismatch (real, flagged by the build log itself, and **harmless** — aligning it changed nothing, and that patch is dropped rather than kept as an unproven divergence every rebase would carry); and a stale cache — none of which held. Measured 2026-08-24: with the cache off, `compileDebugKotlin` completes at upstream's Kotlin 2.3.21. Cost is negligible — the configuration cache accelerates the *configuration* phase of repeated builds, and these are from-scratch container release builds where configuration is a rounding error against a ~20 minute compile. Touches `gradle.properties`, which no other patch in any list touches, so no ordering constraint. Revisit when KGP fixes the round-trip: flip the flag, run one ABI pass. |
| `patches/android/rs-blocker-android.patch` | LW-M4-08 | **Stops the Rust RemoteSettingsService's network traffic on Android.** Desktop's `rs-blocker.patch` (common.txt) covers only the JS/Gecko stack (`services/settings/*.mjs` + `SearchEngineSelector.sys.mjs`); Fenix's Remote Settings traffic goes through the Rust crate in `third_party/application-services/components/remote_settings/`, which that patch never touches. Three hunks close all network choke points: `fetch_changes()` returns an empty `Changes`, `sync()` is a no-op, `make_request()` returns an error (the single choke point for `fetch_changeset`, `fetch_attachment`, `fetch_cert`). The server stays Prod so `is_prod_server()` remains true and the packaged data path (`get_records` Case 1, `get_attachment` step 2, `reset_storage` re-seed) keeps working — the seven packaged collections and their attachments are served from the binary. `search-config-overrides-v2` is NOT packaged but Fenix passes `applyEngineOverrides=false` so no client is created for it. Touches two files (`service.rs`, `client.rs`) in the Rust crate; no other patch in either list touches these files, so no ordering constraint. |
| `patches/android/no-suggest.patch` | LW-M4-11 | **Search suggestions and trending searches off by default; the sponsored top-sites feed removed.** Two Fenix defaults flip (`Settings.shouldShowSearchSuggestions`, `trendingSearchSuggestionsEnabled`): a default, not a lock — both rows stay in Settings > Search, which is acceptance line 3. The sponsored tiles ("Contile", in 153 the MARS / Mozilla ads client feed at `ads.mozilla.org`, measured by LW-M4-10) are removed rather than switched off: `Settings.showContileFeature` becomes a constant `false` getter (no preference, so no settings write, Nimbus experiment or upstream default flip can revive it), the `TopSitesRefresher` observer and the `ContileTopSitesUpdater` periodic work are deleted from `HomeActivity.kt`, and the "Sponsored shortcuts" checkbox leaves Settings > Homepage. `Core.kt`'s MARS/MAC providers stay but have no caller (`lazyMonitored`, never constructed). Five files incl. `SettingsTest.kt`. Shares `Settings.kt` with `no-adjust`/`no-onboarding`/`no-gms`, `HomeActivity.kt` with `no-nimbus`/`no-adjust`, `SettingsTest.kt` with `no-onboarding`; every pair replayed from the pristine file in both orders, byte-identical (check-patch-order rows). Verify: `android-smoke.sh --check-no-suggest`. |
| `patches/android/search-config.patch` | LW-M4-06 | **The LibreWolf engine set on Android.** Fenix never reads `services/settings/dumps/`; its engines come from the app-services `search` component reading the `search-config-v2` / `search-config-icons` Remote Settings dumps compiled into `libmegazord.so` (`remote_settings/src/client.rs` `packaged_collections!`), which `rs-blocker-android` freezes for the life of the build. The data half is a plain copy, like desktop: `scripts/librewolf-patches.py` `android_search_config()` puts `assets/search-config-v2.json` (DuckDuckGo No-AI default, Startpage, Mojeek, Wikipedia) and the icons dump into `third_party/application-services/components/remote_settings/dumps/main/`, rewrites the `.timestamp` sidecars, drops icon records android-components cannot decode (the DuckDuckGo *pdf* record would be the first match for `ddg`), and writes the Mojeek attachment plus a sidecar whose hash/size are computed from the file. The diff half: the Mojeek and Startpage record ids join `packaged_attachments!` in `client.rs` (attachments are served from the binary by record id, nothing else; upstream ships Startpage's file but never lists it, and the patcher now asserts every kept icon id is listed), `Settings.useRemoteSearchConfiguration` is pinned to `true` so the legacy `assets/search/list.json` bundle (Google default, partner codes) stays unreachable across a rebase, and the hidden debug switch for it is removed. Shares `Settings.kt` with `no-adjust`/`no-onboarding`/`no-gms`/`no-suggest` and `client.rs` with `rs-blocker-android`; measured order-free. Verify: `android-smoke.sh --check-search` (engine list read off the running Settings screen + a real query). |
| `patches/android/deterministic-version-code.patch` | LW-M6-08 | Derives Fenix versionCode from the pinned UTC MOZ_BUILD_DATE, with strict date validation. The Android Gradle config plugin is never used by desktop; no other patch touches its source file. |
| `patches/android/ubo-readiness.patch` | LW-M3-07 | Android GeckoView API waits for a real live blocking response listener, with ID/version/permission checks and bounded failure. Shared Gecko webRequest code records live registrations and removes them on unregister; primed startup listeners do not qualify. The API does not alter the signed XPI or claim arbitrary extension internals are ready. |
| `patches/android/ubo-preinstall.patch` | LW-M3-07 | Fenix installs the hash-pinned genuine uBO XPI through ordinary Gecko signature verification from a private file. A one-shot exact local transaction receives install permission, including private mode; ordinary installs and updates retain their prompts. Durable state preserves removal/disable across upgrades. Browsing session creation waits for installation/reconciliation and actual filter-listener readiness; failures offer Retry/Close. The common Gecko filter-bootstrap pref is unchanged. Requires no-adjust before the HomeActivity hunk; seven other shared-file pairs replay byte-identically in both orders. |
| `patches/android/privacy-defaults.patch` | LW-M7-07/LW-M7-12 | Fenix preference defaults and their settings screens agree on HTTPS-only, strict tracking protection, cookie/cache cleanup, disabled password/address/card autofill and DoH off with the LibreWolf provider catalog. Existing explicit choices remain effective; absent companion radio keys use the same fallback as the engine policy. The patch changes only Fenix Kotlin, XML preferences and tests. Five shared-file pairs with prior defaults patches are reviewed in the LW-M7-12 integration evidence; registration does not establish compiled or runtime behavior. |
| `patches/android/cookie-banner-rules.patch` | LW-M7-13 | Packages the pinned cookie-banner snapshot directly for Android and validates its hash, metadata and schema before importing through CookieBannerListService. Android constructs no cookie Remote Settings client or subscription; both collection allowlists and blockers remain unchanged. Desktop retains its existing data path. The 23 actual-source tests pass; Gecko compilation, packaged resource loading and real native banner rejection remain pending. No new co-applied shared-file pair. |
| `patches/android/update-check.patch` | LW-M6-06 | **The opt-in update check for the direct-APK distribution** (contract: `DISTRIBUTION.md`). A switch in Settings > About, off by default, whose summary names the host, the cadence and what is sent. When on, `HomeActivity.onResume` calls `org.mozilla.fenix.lw.UpdateCheck.maybeRun`: at most once per 24 h it fetches `latest.json` and `latest.json.sig`, verifies ECDSA P-256 / SHA-256 against a public key embedded at build time, and if a newer version is named shows a dialog offering the download page — never downloads, never installs, every failure is silent. The request carries a static User-Agent, no cookies, no cache validators, no redirects, and not even the version string (the comparison is local); `UpdateCheckerTest` pins each of those fields. Without `-PlwUpdateCheckPubkey` (forwarded from `LW_UPDATE_CHECK_PUBKEY` by `scripts/android-apk.sh`) the feature is compiled out: no row, no reachable code — which is how store builds (F-Droid, Accrescent) are told apart from the direct APK, by artifact rather than by runtime query. No key is checked in; no endpoint exists yet. Seven files, three new. Shares `fenix/app/build.gradle` with the ordered `no-adjust`…`branding` chain and `HomeActivity.kt` with `no-nimbus`/`no-adjust`/`no-suggest`; measured order-free. Verify: `android-smoke.sh --check-update-privacy`. |

The first three rows are the ones the M1 splits pulled in; the rest are later
work. Where a split needed **no** Android counterpart, that is recorded as a
comment block in `assets/patches/android.txt` with the evidence — LW-M1-03
(`eme-permission`), LW-M1-04 (`moz-official`) and LW-M1-06 (`remove-pingsender`)
each have one. A silent absence and a checked absence look identical in a patch
list, which is why those blocks are there.

---

## Common — apply to both desktop and Android

24 entries: the 17 originally-common patches below, plus the 7 common halves of
the split straddlers (table after this one). Every row was traced to the guard
that proves the file is built on Android.

| patch | touches | why common (reviewed) |
|---|---|---|
| `always-fetch-latest-toolchain-artifact` | `python/mozbuild/…/artifact_commands.py` | Build tooling. mach imports it for every target; artifact builds are not desktop-specific. |
| `autoconfig-setEnv` | `extensions/pref/autoconfig/src/prefcalls.js` | `toolkit/moz.configure:3186-3187` makes `MOZ_PREF_EXTENSIONS` default-on (`--disable-pref-extensions`), and `toolkit/toolkit.mozbuild:135-136` traverses `/extensions/pref` under it. `prefcalls.js` ships on Android. Must apply **before** `profile-directory`. |
| `bootstrap` | `python/mozversioncontrol/…/source.py` | Build tooling; path separator normalisation, target-independent. |
| `custom-ubo-assets-bootstrap-location` | `toolkit/components/extensions/parent/ext-storage.js` | **Live on Android, and more useful there than on desktop.** `jar.mn:45` ships `parent/ext-storage.js` with no `#ifndef ANDROID` (the only such guard in that file is for `child/ext-identity.js`). Upstream `storage.managed` goes through `getManagedStorageManifestData` → `NativeManifests.init()`, which *throws* on Android (`AppConstants.platform` matches neither `win` nor `macosx`/`linux`). The patch wraps that call in `try/catch` and returns `adminSettings` anyway, so it is the only reason `storage.managed` returns anything at all for uBO on Android. Answers LW-M3-07: **yes, the code path is live.** |
| `devtools-bypass` | `devtools/server/actors/*`, `devtools/shared/flags.js` | `devtools/moz.build:11-16` adds `platform/`, `server/`, `shared/`, `startup/` to `DIRS` with no guard. Ships on Android. |
| `extensions-setUninstallURL` | `toolkit/components/extensions/parent/ext-runtime.js` | `jar.mn:43`, unguarded. WebExtensions ship on Android. |
| `firefox-in-ua` | `toolkit/moz.configure` | Shared configure file. `mobile/android/moz.configure:135` already does `imply_option("MOZ_APP_UA_NAME", "Firefox")`, and an implied value outranks a `project_flag` default without conflicting (`_value_for_option` only raises on command-line/environment origins), so on Android this is a safe no-op with the same outcome. Kept common: it edits a file `moz-configure` also edits, and must apply **before** it. |
| `fix-canvas-extraction-permission` | `dom/html/HTMLCanvasElement.cpp` | Core DOM, built everywhere. |
| `fpp-canvas-fix` | `dom/canvas/*`, `toolkit/components/resistfingerprinting/nsRFPService.cpp` | Core canvas + RFP. Must apply **before** `webgl-permission`; that holds across files because `common.txt` is applied first. |
| `limit-access` | `caps/nsScriptSecurityManager.cpp` | Core security check on `chrome://branding/` access. Genuinely common. |
| `moz-configure` | `toolkit/moz.configure` | **Not inert on Android.** `MOZ_APP_PROFILE` is defined only by this `project_flag` (`toolkit/moz.configure:35`) — nothing under `mobile/` implies it — so the added `default="librewolf"` reaches the Android build and lands in `application.ini` via `build/moz.build:88-89`, i.e. `gAppData->profile`. |
| `mozilla_dirs` | `NativeManifests.sys.mjs`, `toolkit/xre/nsXREDirProvider.cpp`, `xpcom/build/nsXULAppAPI.h` | **The heuristic guess ("native messaging is desktop-only") was wrong about the file, right about the feature.** `XP_UNIX` is set for every unix target including Android (`build/moz.configure/init.configure:867`), so the `#if defined(XP_UNIX) \|\| defined(XP_MACOSX)` blocks at `nsXULAppAPI.h:108-116`, `nsXREDirProvider.cpp:326-362` and `:416-430` all **compile on Android**, and the `AppendSysUserExtensionPath` `.mozilla` → `.librewolf` rename (`:1293-1302`, `#elif defined(XP_UNIX)`) takes effect there. Only the JS half is dead: `NativeManifests.init()` throws on Android before it reaches the patched `dirs` array. Dropping this would be a real Android branding regression. Must apply **before** `xdg-dir`. |
| `profile-directory` | `extensions/pref/autoconfig/src/prefcalls.js` | Same file and same reasoning as `autoconfig-setEnv`; must apply **after** it. The `HOME`/`XDG_CONFIG_HOME` lookup resolves to a non-existent path on Android, which is harmless — the file ships, so the patch stays with its partner rather than splitting the pair across lists. |
| `remove-openai` | `toolkit/components/ml/*`, `toolkit/content/license.html` | **Mandatory on Android, not merely allowed.** `toolkit/components/moz.build:59` puts `ml` in the unconditional `DIRS`, and `scripts/librewolf-patches.py:325-328` deletes `OpenAIPipeline.mjs` and `vendor/openai/` for *every* target. Leaving the patch off an Android build would leave `toolkit/components/ml/jar.mn` referencing files that no longer exist. This is landmine L4 pointing at scope. (The `aboutinference` hunk is `NIGHTLY_BUILD`-only per `toolkit/components/moz.build:155-156`, on every platform; that does not change the classification.) |
| `rs-blocker` | `services/settings/*`, `toolkit/components/search/SearchEngineSelector.sys.mjs` | `services/moz.build:12` traverses `settings` unconditionally; `toolkit/components/moz.build:79` traverses `search` and `search/moz.build:21` ships `SearchEngineSelector.sys.mjs`. Both halves are live on Android. **Caveat for LW-M4-08:** the allowlist defaults to the empty pref, and `"".split(",")` is `[""]`, i.e. deny-everything. Android must populate `librewolf.services.settings.allowedCollections{,FromDump}` with its own collections or remote settings is dead there — that is the LW-M4-08 work, and it is a configuration gap, not a reason to move this patch. |
| `rust-gentoo-musl` | `build/moz.configure/rust.configure` | **Does not disturb the NDK path.** The added block sits between the existing vendor narrowing and the terminal `return None` in `find_candidate`, i.e. it only runs on the path that would otherwise `die("Don't know how to translate …")`. Android targets (`aarch64-linux-android` &c.) resolve earlier, at the `sub_configure_alias`/`raw_os` narrowing. It strictly widens; it can never displace a candidate that would otherwise have won. And `detect_rustc_target` runs for the **host** as well as the target, so a Gentoo/musl build host cross-compiling to Android needs it. |
| `vendor-name` | `toolkit/components/extensions/parent/ext-runtime.js`, `toolkit/xre/nsAppRunner.cpp` | Both files are core and built on Android. |

### The 7 common halves added by the M1 splits

Each replaces the Android-facing part of a former straddler. The desktop half of
the same name is in `desktop.txt`; the per-patch evidence lives in each patch's
own header and in the straddler table further down.

| patch | task | touches | why common |
|---|---|---|---|
| `disable-data-reporting-common` | LW-M1-02 | `python/mach/mach/telemetry.py`, `python/sites/mach.txt`, `toolkit/components/glean/src/init/mod.rs`, `toolkit/components/telemetry/core/Telemetry.cpp`, `toolkit/library/rust/gkrust-features.mozbuild` | Build tooling plus core Glean/Telemetry, all built on Android. Note the *name drops* `-at-compile-time`. The compile-time switch itself is per-front-end, hence the separate `android.txt` entry. |
| `eme-permission-common` | LW-M1-03 | `dom/media/eme/MediaKeySystemAccessManager.cpp` | `dom/media/moz.build:28,32` puts `eme` in `DIRS` with no guard. |
| `moz-official-common` | LW-M1-04 | `dom/media/gmp/ChromiumCDMAdapter.cpp`, `media/gmp-clearkey/0.1/gmp-clearkey.cpp` | `dom/media/moz.build:28-36` has `gmp` unguarded; `toolkit/toolkit.mozbuild:167-169` traverses clearkey unconditionally and `clearkey/moz.build:13-16` has an explicit Android `FINAL_TARGET` branch, i.e. it is packaged into the APK. |
| `remove-pingsender-common` | LW-M1-06 | `toolkit/components/telemetry/moz.build`, `toolkit/components/telemetry/app/TelemetrySend.sys.mjs`, `python/mozbuild/mozbuild/artifacts.py` | `toolkit/components/telemetry/moz.build:9-11` has `DIRS = ["pingsender"]` with no guard, so dropping it really does change the Android build — see the corrected mechanism in the straddler table. |
| `ui-patches/neterror-common` | LW-M1-07 | `toolkit/content/errors/net-error-illustrations.mjs`, `toolkit/content/net-error-card.mjs`, `toolkit/themes/shared/aboutNetError.css`, `toolkit/themes/shared/illustrations/warning.svg` | The two `.mjs` files ship unguarded (`toolkit/content/jar.mn:18,214`); the CSS and SVG are shared theme files. The desktop boundary was the *filename* `desktop-jar.inc.mn`, which is in the desktop half — landmine L3. |
| `webgl-permission-common` | LW-M1-08 | `dom/canvas/ClientWebGLContext.cpp`, `dom/ipc/BrowserParent.{cpp,h}`, `dom/ipc/PBrowser.ipdl`, `modules/libpref/init/StaticPrefList.yaml`, `modules/libpref/moz.build` | Core Gecko. Must apply **after** `fpp-canvas-fix` (shared `ClientWebGLContext.cpp`). Ships with `patches/android/webgl-prompt-default.patch` — landmine L1. |
| `xmas-common` | LW-M1-09 | root `moz.build` (`DIRS += ["lw"]`), `lw/moz.build` | `FINAL_TARGET_FILES` works on any target, so `lw/` enters the build on both. Necessary but **not sufficient** on Android: it does not reach the APK. See landmine L2. |

### Moved out of common by this review

Five entries the seed put in `common.txt` are now in `desktop.txt`. Each is
**demonstrated** inert on Android by a build guard, not assumed inert from a
filename. None of them is a parity loss; where the *requirement* survives on
Android, the tracking task is named.

| patch | was | now | proof it is inert on Android |
|---|---|---|---|
| `add-mojeek` | common (?) | desktop | The two added icon lines land inside `services/settings/dumps/main/moz.build:46`, `if CONFIG["MOZ_BUILD_APP"] == "browser":`. Android is `mobile/android`, so the block never executes and the entry is never added. Android reads search config from `third_party/application-services/…/dumps/`; the Android equivalent is **LW-M4-06**. (Note `librewolf-patches.py:341-342` still copies the icon file into the tree for every target — a harmless orphan on Android, and LW-M4-06's problem.) |
| `dbus_name` | common (?) | desktop | `toolkit/components/remote/moz.build:24-35`: `nsDBusRemoteClient.cpp` / `nsDBusRemoteServer.cpp` are only in `SOURCES` when `MOZ_WIDGET_TOOLKIT == "gtk"` **and** `MOZ_ENABLE_DBUS`. Not compiled on Android. Already caught by `scripts/lint-patch-scope.py`. |
| `macos-relaunch-without-updater` | common (?) | desktop | Objective-C++ (`.mm`). `toolkit/xre/moz.build:71-84` compiles `nsCommandLineServiceMac.mm` only for `MOZ_WIDGET_TOOLKIT == "cocoa"`. Caught by the linter. |
| `ui-patches/lw-logo-devtools` | common (?) | desktop | All four files are under `devtools/client/`. `devtools/moz.build:5-8` adds `client/` only when `MOZ_DEVTOOLS == "all"`, and `browser/moz.configure:17` is the only `imply_option` that sets it; Android keeps the `toolkit/moz.configure:40-46` default `"server"`. Caught by the linter. This is the L3 carve-out *inside* an otherwise-common tree. |
| `xdg-dir` | common (?) | desktop | **All three hunks** (`AppendFromAppData`, `LegacyHomeExists`, `GetLegacyOrXDGHomePath`) sit between `nsXREDirProvider.cpp:1309` `#if defined(MOZ_WIDGET_GTK)` and `:1539` `#endif`. Android's toolkit is `android`, so the whole region is compiled out. XDG config-home semantics have no Android meaning; Fenix owns the profile location. The `mozilla_dirs` → `xdg-dir` ordering constraint still holds, because `common.txt` is applied before `desktop.txt`. |

Note the two `nsXREDirProvider.cpp` patches split on *evidence*, not on
appearance: `xdg-dir` looks Linux-flavoured and is provably compiled out;
`mozilla_dirs` looks equally Linux-flavoured and is provably compiled **in**.
That asymmetry is the whole point of this task.

## Desktop only — never applied to Android

36 entries: the 35 in `desktop.txt` plus `pref-pane/pref-pane-small`, which the
patcher applies at its own call site — the only patch still applied that way.
Of those 36: **23** are the plain `browser/`-only rows listed below (one of them
being `pref-pane-small` itself), **5** were moved out of common by LW-M1-01,
**7** are the desktop halves of the split straddlers, and **`msix`** is
desktop-only for the reason LW-M1-05 established. All were read; the
classification for the plain rows is the same one line, so it is stated once
rather than 23 times.

**Justification (reviewed, applies to every row below unless noted):** the patch
touches only paths under `browser/`. `browser/app.mozbuild:7-11` is what pulls
`/browser` into a build and `mobile/android/app.mozbuild` never does, so none of
these files exists in an Android build and none of these patches could apply to
one.

`fullpage-translations-customization` · `hide-passwordmgr` · `languages` ·
`link-preview` · `lw-permissions` · `newtab-fix` · `pref-pane/pref-pane-small` ·
`remove-language-packs` · `temp-macos-fix` · `windows-theming-bug` ·
`ui-patches/add-translate-page-context-menu` · `ui-patches/allow_cookies_for_site` ·
`ui-patches/firefox-view` · `ui-patches/hide-default-browser` ·
`ui-patches/hide-finish-setup-bookmark` · `ui-patches/home-preferences` ·
`ui-patches/pref-naming` · `ui-patches/privacy-preferences` ·
`ui-patches/remove-cfrprefs` · `ui-patches/remove-organization-policy-banner` ·
`ui-patches/settings-redesign` · `ui-patches/trustpanel` ·
`ui-patches/website-appearance-ui-rfp`

…plus the five moved out of common above, each with its own proof; plus `msix`;
plus the seven desktop halves, which are desktop-only by construction —
`disable-data-reporting-desktop`, `eme-permission-desktop`,
`moz-official-desktop`, `remove-pingsender-desktop`,
`ui-patches/neterror-desktop`, `webgl-permission-desktop`, `xmas-desktop`. Six of
those touch only `browser/`; the seventh, `ui-patches/neterror-desktop`, touches
only `toolkit/themes/shared/desktop-jar.inc.mn`, which is landmine L3 and the
reason the whole split existed.

Two of the `browser/`-only rows have a note worth keeping:

- `temp-macos-fix` and `windows-theming-bug` are additionally macOS- and
  Windows-only *within* desktop (`*/macbuild/*`, `*.exe.manifest`); they are
  desktop-only twice over.
- `languages` edits `browser/locales/shipped-locales`, which has an Android
  counterpart at `mobile/android/locales/`. Adding `ku` there is a real Android
  requirement and needs its own task; it is not satisfied by this patch.

Several of these describe behaviour Android still needs — a hidden password
manager, a privacy preferences surface, RFP appearance handling. They are desktop
*implementations*, not desktop *requirements*. Anything that turns out to be a
requirement gets an Android counterpart under `patches/android/`, tracked as its
own task, not by forcing the desktop patch onto Fenix.

## Straddlers — all resolved, count now 0

LW-M1-01 nominated eight. Seven really did edit both shared Gecko code and
desktop-only code and were cut in half; the eighth (`msix`) turned out not to be
one. Nothing is parked in `desktop.txt` any more and every monolithic straddler
file has been deleted from disk (LW-M1-12) — `patches/msix.patch` is still there
because it was never a straddler, not because the cleanup missed it.

The table is kept because it is the evidence trail, not a to-do list. The
**common half** column is what actually shipped. Where the owning task disproved
something LW-M1-01 wrote, the row says so and LW-M1-12 has corrected the claim
rather than deleting it — a wrong reason that produced a right verdict is exactly
the thing that gets copied into the next release's review.

| patch | task | common half | desktop half | evidence / caveat |
|---|---|---|---|---|
| `disable-data-reporting-at-compile-time` | LW-M1-02 | `python/mach/mach/telemetry.py`, `python/sites/mach.txt`, `toolkit/components/glean/src/init/mod.rs`, `toolkit/components/telemetry/core/Telemetry.cpp`, `toolkit/library/rust/gkrust-features.mozbuild` | `browser/moz.configure`, `browser/components/tabbrowser/content/tabbrowser.js` | Unchanged from the seed. The `browser/moz.configure` hunk flips `MOZ_SERVICES_HEALTHREPORT`/`MOZ_NORMANDY` to `False`; **`mobile/android/moz.configure:131-132` implies the exact opposite pair** (`MOZ_NORMANDY` False, `MOZ_SERVICES_HEALTHREPORT` **True**), so Android needs its own configure change and LW-M1-02 must not assume the desktop hunk covers it. That is the one genuinely new finding here. **Landed:** that change is `patches/android/disable-data-reporting-android.patch`, listed in `android.txt`; the common half's name drops the `-at-compile-time` suffix. |
| `eme-permission` | LW-M1-03 | `dom/media/eme/MediaKeySystemAccessManager.cpp` | `browser/components/permissions/ContentPermissionPrompt.sys.mjs`, `browser/modules/EMEPermissionPrompt.sys.mjs` (new file) | Split correct; **the L1 worry is corrected by LW-M1-12** — LW-M1-03 checked it and it does not hold. This is *not* the same shape as L1, and "Android has no equivalent surface yet" is **false**. Fenix implements this exact permission type end to end and always has: `mobile/shared/components/geckoview/components.conf:28-33` binds the content-permission prompt to `GeckoViewPermission`, whose `promptPermission()` (`GeckoViewPermission.sys.mjs:119-219`) is type-agnostic and forwards **any** `perm.type` to the embedder — there is no per-type switch to fall off, which is the structural difference from `webgl-permission`'s `browser/`-only observers; `GeckoSession.java:7354-7355,7195,7386-7387` carries `"media-key-system-access"` across JNI as `PERMISSION_MEDIA_KEY_SYSTEM_ACCESS`; and Fenix has both doorhanger and settings entry (`PhoneFeature.kt:38`, `Settings.kt:1812`, `SitePermissionsRules.kt:92-94`, default `ASK_TO_ALLOW`). No Android patch needed. The one deliberate silent deny is Clear Key, and it is deny-by-default on **both** targets: the common half reads `Preferences::GetBool("librewolf.eme.gmp-clearkey.enabled", false)`, whose built-in fallback already equals LibreWolf's own default (`settings/librewolf.cfg:395`) — there is no shared default to flip, which is precisely why `webgl-permission` needed one (its shared default was the permissive-looking `true`). The **real remaining gap is narrower**: there is no Android surface for the LibreWolf-specific Clear Key *denial* (desktop's learn-more link to `librewolf.eme.warning.infoURL`). That is a UI follow-up, not a scope question. |
| `moz-official` | LW-M1-04 | `dom/media/gmp/ChromiumCDMAdapter.cpp`, `media/gmp-clearkey/0.1/gmp-clearkey.cpp` | `browser/base/content/browser-init.js`, `browser/base/content/browser-main.js`, `browser/base/jar.mn` | Unchanged. The two `#ifdef MOZILLA_OFFICIAL` → `#if 0` hunks are in core GMP code and matter on Android too (CDM host verification). |
| `msix` | LW-M1-05 | **none — NOT A STRADDLER** | the whole patch: `browser/installer/windows/msix/AppxManifest.xml.in`, `python/mozbuild/mozbuild/mach_commands.py`, `python/mozbuild/mozbuild/repackaging/msix.py` | **RESOLVED by LW-M1-05: `msix` was never a straddler.** No halves exist and none should; `patches/msix.patch` stays on disk and stays in `desktop.txt`, and the straddler count drops by one independently of any split. The AST evidence, in one line: stripping every function body leaves `repackaging/msix.py`'s import-time AST **identical** and `mach_commands.py`'s differing by exactly one constant — the `--vendor` default on `@SubCommand("repackage","msix")`, read only by `vendor = vendor or second` inside `msix.py`'s function bodies — and `msix.py`'s only non-test importers are two *function-local* imports at `mach_commands.py:3336,3458`, so nothing the patch changes is reachable at import time on any target, and no LibreWolf target runs `mach repackage`. Everything below is LW-M1-01's reasoning, which reached the same verdict from a different direction and is kept as corroboration. **LW-M1-01 disagrees with the seed table.** The seed said `mach_commands.py` is common "because Android traverses this file". It is true that mach imports the module on every build, but the hunk only edits the `repackage msix` command's `--vendor` default and the `identity=`/`displayname=` kwarg it passes to `repackage_msix()` — a command an Android build never runs. Applying it on Android changes nothing observable. Worse, the two `python/` hunks are a **matched pair**: `mach_commands.py` switches to `identity=identity_name` and `repackaging/msix.py` supplies the `displayname = displayname or first` fallback that makes the new call correct (`repackage_msix()` already takes `identity` upstream, so the halves *apply* independently but are only *correct* together). LW-M1-05 should either produce an empty common half and leave `msix` desktop-only, or keep both `python/` hunks in the same half. Do not split them from each other. **Flagged as a judgement call.** |
| `remove-pingsender` | LW-M1-06 | `toolkit/components/telemetry/moz.build`, `toolkit/components/telemetry/app/TelemetrySend.sys.mjs`, `python/mozbuild/mozbuild/artifacts.py` | `browser/app/macbuild/Contents/MacOS-files.in`, `browser/installer/package-manifest.in`, `browser/installer/windows/nsis/shared.nsh` | Verdict unchanged (**common**); **mechanism corrected by LW-M1-12**, because LW-M1-06 disproved the one LW-M1-01 gave. `toolkit/components/telemetry/moz.build:9-11` does have `DIRS = ["pingsender"]` with **no** guard, so removing it is a real change on Android — but *not* for the stated reason. LW-M1-01 wrote that `pingsender/moz.build` "still appends `pingsender_unix_common.cpp` to `UNIFIED_SOURCES` outside that guard", implying compiled code on Android. That is textually true (`moz.build:28-31`, the `else:` arm of the `WINNT` test) and **nothing compiles from it**: `GeckoProgram("pingsender")` is inside `if CONFIG["OS_TARGET"] != "Android"` (`:5-6`), so on Android the context has no linkable and the file sets no `FINAL_LIBRARY`, and `python/mozbuild/mozbuild/frontend/emitter.py:1038-1042` — "Only emit sources if we have linkables defined in the same context" — returns before emitting a single source. The real effect of the patch on Android is simply that the directory **stops being traversed**: one less `moz.build` read, zero object files either way. Keep the patch in common for intent and for the desktop effect; do not cite compiled Android code as the reason. The `TelemetrySend.sys.mjs` throw is redundant on Android — upstream already throws for `AppConstants.platform === "android"` — but harmless and worth keeping for intent. The `artifacts.py` hunks touch `LinuxArtifactJob`/`MacArtifactJob` only, so they are inert on Android; keep them with the common half rather than splitting a single tooling file. |
| `ui-patches/neterror` | LW-M1-07 | `toolkit/content/errors/net-error-illustrations.mjs`, `toolkit/content/net-error-card.mjs`, `toolkit/themes/shared/aboutNetError.css`, `toolkit/themes/shared/illustrations/warning.svg` | `toolkit/themes/shared/desktop-jar.inc.mn` | Split correct — landmine L3, the desktop boundary is the *filename* `desktop-jar.inc.mn` inside a shared directory. **The "broken image reference on Android" caveat is corrected by LW-M1-12**, because LW-M1-07 disproved it as a *regression* claim. The packaging fact is right: the common half points `securityError.src` at `chrome://global/skin/illustrations/warning.svg`, the only manifest packaging that file is `desktop-jar.inc.mn:152`, and `toolkit/themes/moz.build:19-26` routes `MOZ_BUILD_APP == "mobile/android"` to `toolkit/themes/mobile`. But **upstream already does exactly the same**: the unpatched `net-error-illustrations.mjs` points at `illustrations/security-error.svg` and `no-connection.svg`, both packaged only by `desktop-jar.inc.mn:148,151`. The patch swaps one desktop-only-packaged illustration for another — it is not a new Android breakage, and it is **not L1-shaped**: L1 changes behaviour that was working; this changes nothing reachable. The component is unreachable on Android three ways over — `net-error-card.mjs:38-41,80-83` gate it on `security.certerrors.felt-privacy-v1`, `pref()`'d true only in `browser/app/profile/firefox.js:2965` with no `StaticPrefList` entry and nothing under `mobile/` setting it; `aboutNetError.css` is itself packaged only by `desktop-jar.inc.mn:17`; and Fenix's `AppRequestInterceptor.onErrorRequest` answers every GeckoView load error with its own `ErrorPages` document. `patches/android/neterror-jar.patch` was added anyway, as insurance rather than as a fix. **Trap within the trap, for whoever adds the next mobile jar entry:** it goes in `toolkit/themes/mobile/global/jar.mn` and **never** in `shared/minimal-toolkit.jar.inc.mn` — `desktop-jar.inc.mn:10` includes that file, so an entry there also lands in the desktop jar and breaks the byte-identical-desktop-tree guarantee. |
| `webgl-permission` | LW-M1-08 | `dom/canvas/ClientWebGLContext.cpp`, `dom/ipc/BrowserParent.{cpp,h}`, `dom/ipc/PBrowser.ipdl`, `modules/libpref/init/StaticPrefList.yaml`, `modules/libpref/moz.build` | `browser/base/content/popup-notifications.inc.xhtml`, `browser/modules/ObserverForwarder.sys.mjs`, `browser/modules/WebGLPermissionPromptHelper.sys.mjs`, `browser/themes/shared/*` (icons, `jar.inc.mn`, `notification-icons.css`) | Unchanged — **landmine L1, and re-confirmed by reading the patch.** `StaticPrefList.yaml` gives `librewolf.webgl.prompt` `value: true`; `IsWebGLAllowed` then returns false for any principal without an explicit `webgl` permission; `RecvShowWebGLPermissionPrompt` early-returns unless `mFrameElement->AsBrowser()` yields an `nsIBrowser`, which GeckoView has no XUL `<browser>` for; and the `webgl-permissions-prompt` observers live entirely in the desktop half. The Android default (`lockPref` or a per-platform `StaticPrefList` value) ships in the same commit — never a follow-up. **Landed:** `patches/android/webgl-prompt-default.patch`. This is the only one of the eight where the Android-side patch was mandatory rather than defensive. |
| `xmas` | LW-M1-09 | `moz.build` (adds `DIRS += ["lw"]`), `lw/moz.build` | `browser/installer/package-manifest.in` | Unchanged. `lw/moz.build` installs `librewolf.cfg`, `distribution/policies.json` and `defaults/pref/local-settings.js` via `FINAL_TARGET_FILES`, which works on any target; only the packaging manifest is desktop. **Caveat, now RESOLVED:** `FINAL_TARGET_FILES` at the package root alone does not get these into the Android APK — GeckoView packages from `mobile/android/`, and a root-level `librewolf.cfg` fails `OmniJarSubFormatter.is_resource` and is dropped flat. The Android packaging half LW-M1-09 owed is `patches/android/autoconfig-resource-fallback.patch` (LW-M3-08, listed in `android.txt` by LW-M3-02): it re-installs the `.cfg` under `defaults/autoconfig/` and names it plus `defaults/pref/local-settings.js` in `mobile/android/installer/package-manifest.in`. Android therefore **has** `librewolf.cfg` and the `lockPref` channel landmine L2 depends on. `distribution/policies.json` is still dropped — it is not under `defaults/` either, and LW-M3-06 owns it. Note this makes `lw/moz.build` a **shared tree file between a common and an android patch**, so `xmas-common` must apply first; that constraint is declared in `scripts/check-patch-order.py`. |

`msix` is still the one to be careful with, but for the opposite reason to the
one the seed gave: it looks like the most obviously Windows-only patch in the
tree, it edits a file the Android build *imports*, and that import nevertheless
does not make any of it common.

### What each split actually produced

| former straddler | common half | desktop half | Android patch |
|---|---|---|---|
| `disable-data-reporting-at-compile-time` | `disable-data-reporting-common` (name drops `-at-compile-time`) | `disable-data-reporting-desktop` | `android/disable-data-reporting-android` |
| `eme-permission` | `eme-permission-common` | `eme-permission-desktop` | none needed (checked) |
| `moz-official` | `moz-official-common` | `moz-official-desktop` | none needed (checked) |
| `msix` | — | `msix` (unsplit) | — |
| `remove-pingsender` | `remove-pingsender-common` | `remove-pingsender-desktop` | none needed (checked) |
| `ui-patches/neterror` | `ui-patches/neterror-common` | `ui-patches/neterror-desktop` | `android/neterror-jar` |
| `webgl-permission` | `webgl-permission-common` | `webgl-permission-desktop` | `android/webgl-prompt-default` (L1, mandatory) |
| `xmas` | `xmas-common` | `xmas-desktop` (kept last in `desktop.txt`) | none yet — the APK packaging half is still owed, see L2 |

All eight monolithic files are off disk except `patches/msix.patch`, which is not
a straddler. Until LW-M1-12 deleted them, `scripts/check-patchfail.sh` and
`scripts/fuzzfail.sh` were still reading the monoliths out of the
`assets/patches.txt` shim, so every green run proved something about code that no
longer shipped.

---

## Could not be determined from the tree

Two things this task could not settle, recorded so they are not silently assumed:

1. **Whether autoconfig actually runs on Android — SETTLED, AND THE ANSWER IS
   YES.** `prefcalls.js` provably *ships* (that is what puts `autoconfig-setEnv`
   and `profile-directory` in common), and this file used to record the rest as
   undeterminable from the tree: whether `general.config.filename` gets set and
   whether `librewolf.cfg` reaches the APK. LW-M3-08 answered both **on a running
   build**, not from the tree — `defaults/pref/local-settings.js` sets
   `general.config.filename` and is read out of `omni.ja` by
   `pref_ReadDefaultPrefs`, and `librewolf.cfg` is read as
   `resource://gre/defaults/autoconfig/librewolf.cfg`. Both files are packaged by
   `patches/android/autoconfig-resource-fallback.patch`, landed by LW-M3-02. Scope
   was unaffected either way, which is why it sat here unresolved for two
   milestones.
2. **Whether `--enable-system-extension-dirs` is on for the Android build.** It
   gates part of `mozilla_dirs`' effect (`ENABLE_SYSTEM_EXTENSION_DIRS`,
   `toolkit/moz.configure:4050`). It does not change the classification: the
   `AppendSysUserExtensionPath` and native-manifest-key hunks compile on Android
   regardless, so `mozilla_dirs` is common either way.

## What the board got wrong

- The seed table's `msix` row ("`python/mozbuild/…/mach_commands.py` — **Android
  traverses this file**") is true but does not support the conclusion drawn from
  it. Corrected in the straddler table above.
- `PATCH-SCOPE.md` previously counted 22/23/8 = 53. The 23 was the desktop-only
  count *excluding* the five patches the seed had misfiled in common; LW-M1-01's
  counts were 17/28/8; after the M1 splits they were 24/3/36/0 = 63; and after
  M2–M5 added five more Android-only patches they were 24/8/36/0 = 68, and with
  LW-M4-13's `no-nimbus-toolkit` they are 24/9/36/0 = 69. Do not quote
  a count from prose — `board.py --check-scope` derives all of them.
- `docs/android/AGENTS.md` "Patch ordering constraints" describes
  `mozilla_dirs` → `xdg-dir` as a within-list pair. After this review they are in
  different lists (common → desktop), which still satisfies the constraint for
  the same reason `fpp-canvas-fix` → `webgl-permission` does: `common.txt` is
  applied first. `scripts/check-patch-order.py` (LW-M1-10) must handle the
  cross-list case for this pair too; `scripts/enable-patch.sh` already models it
  correctly via `applies_before()`. Note the second pair is now *within* one
  list: after LW-M1-08 it is `fpp-canvas-fix` → `webgl-permission-common`, both
  in `common.txt`.

### Corrections landed by LW-M1-12

Four claims in this file were disproved by the tasks that acted on them, and are
corrected in place above rather than deleted — a wrong reason that produced a
right verdict is what gets copied into the next release's review.

- **LW-M1-06 / `remove-pingsender`.** "Still appends `pingsender_unix_common.cpp`
  to `UNIFIED_SOURCES` outside that guard" implied compiled code on Android.
  Textually true, but nothing compiles: no `GeckoProgram` and no `FINAL_LIBRARY`
  means no linkable in the context, and `emitter.py:1038-1042` returns before
  emitting a source. Verdict (common) unchanged; mechanism is that the directory
  stops being traversed.
- **LW-M1-07 / `ui-patches/neterror`.** The "broken image reference on Android"
  is real but is **not a regression** — upstream already points at
  desktop-only-packaged illustrations (`desktop-jar.inc.mn:148,151`) and the
  component is unreachable on Android three ways over. Not L1-shaped. The trap to
  remember is where a mobile jar entry goes:
  `toolkit/themes/mobile/global/jar.mn`, never
  `shared/minimal-toolkit.jar.inc.mn`.
- **LW-M1-03 / `eme-permission`.** "Android has no equivalent surface yet" is
  false; Fenix implements `PERMISSION_MEDIA_KEY_SYSTEM_ACCESS` end to end. The
  real gap is only the LibreWolf-specific Clear Key denial UI.
- **LW-M1-05 / `msix`.** Not a straddler. Import-time AST comparison shows
  `repackaging/msix.py` unchanged and `mach_commands.py` differing by one
  `@SubCommand` default, neither reachable on any Android build.

Two pieces of prose that were simply stale, not wrong, and are now fixed: the
"two separately applied patches" arithmetic (only `pref-pane-small` is left after
LW-M1-09 folded `xmas` into the lists), and `assets/patches/android.txt`'s
"DELIBERATELY EMPTY" header.

## Reproducing this classification

The seed heuristic was intentionally crude — it mapped `mobile/` → android,
`browser/` → desktop, filenames containing `desktop`/`windows`/`macos`/`osx` →
desktop, and everything else → common. That is exactly the prefix rule landmine
L3 says cannot be trusted, which is why LW-M0-08 replaced it with the file-level
linter and LW-M1-01 replaced that table with this one.

`scripts/lint-patch-scope.py` is the mechanical half and it exits 0 against the
lists above. It is necessary and **not sufficient**: it can only catch a patch
that touches a file which provably does not build on the target. It cannot catch
a patch touching genuinely-common files whose *effect* is desktop-only
(`add-mojeek`, `xdg-dir` — both caught here by reading the guard around the hunk,
not the path), nor the reverse (`mozilla_dirs`, `custom-ubo-assets-bootstrap-location`,
`remove-openai` — all of which look desktop-flavoured and are load-bearing on
Android). Those judgements are recorded per row above and must be re-made, not
re-run, when upstream moves.
