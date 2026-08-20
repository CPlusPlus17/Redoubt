# policies.json on Android — mechanism map

**Owner: LW-M3-06.** Every one of the **22** top-level keys in
`settings/distribution/policies.json` has a row below. A row states either the
Android mechanism that reproduces the policy's effect, or an explicit residual
gap. Gaps are numbered `P1..P8` and feed the M5 parity matrix. No key is marked
"done" because it *sounds* portable.

Everything here was checked against the pristine tree at
`firefox-153.0.4/`, not against memory of what Firefox does.

## The premise, verified

The enterprise policy engine does not exist on Android, and it is gated **twice**:

| gate | file:line | effect |
|---|---|---|
| implementation | `toolkit/components/enterprisepolicies/moz.build:16` | `if CONFIG["MOZ_WIDGET_TOOLKIT"] != "android":` wraps both `EXTRA_JS_MODULES` (`EnterprisePolicies.sys.mjs`, `EnterprisePoliciesParent.sys.mjs`, `EnterprisePoliciesContent.sys.mjs`, `SitePolicyUtils.sys.mjs`) **and** `XPCOM_MANIFESTS += ["components.conf"]` |
| policy bodies | `browser/components/enterprisepolicies/Policies.sys.mjs` | lives under `browser/`, which Android never builds. `browser/components/moz.build:42` adds it for the browser app only |

`toolkit/components/moz.build:45` does add `enterprisepolicies` to `DIRS`
unconditionally, so `nsIEnterprisePolicies.idl` is still compiled on Android —
but the interface has no implementation registered, because `components.conf`
(which is what declares `js_name: 'policies'`) is inside the non-android branch.

**Consequence: `Services.policies` is `undefined` on Android**, not merely
inactive. Toolkit code that must run on both knows this and guards for it —
`toolkit/modules/ResetProfile.sys.mjs:56` (`if (Services.policies && ...)`),
`toolkit/modules/UpdateUtils.sys.mjs:498` (`if (!Services.policies)`),
`toolkit/modules/ServiceRequest.sys.mjs:88`, `toolkit/modules/BrowserUtils.sys.mjs:876`.
So "the policy is inert on Android" is the accurate description; there is no
partial or degraded policy path to lean on.

`policies.json` itself is delivered by `settings/distribution/` and is read only
by the engine above. Shipping it in the APK would be inert weight; **do not**
package it as a substitute for the mechanisms below.

## How to read the "branch / lock" column

From LW-M3-01, and it matters for every pref row:

- desktop policies set prefs through `PoliciesUtils.setDefaultPref`
  (`Policies.sys.mjs:3449-3495`), which writes `Services.prefs.getDefaultBranch("")`
  and locks **only** when the third argument is truthy. `setAndLockPref`
  (`:3409`) is that same call with `locked = true`.
- so a policy that calls `setDefaultPref(name, v, param.Locked)` with no `Locked`
  key in `policies.json` is an **unlocked default**, and `defaultPref()` in a
  `.cfg` is its exact equivalent. A `lockPref()` there would be a *stricter*
  setting than desktop, not parity.
- `MOZ_DEFAULT_PREFS` (`GeckoLoader.java:83-103` → `Preferences.cpp:3963`,
  `PrefValueKind::Default`) writes the default branch and **cannot lock**:
  `modules/libpref/parser/src/lib.rs:14,297-321` has no `locked_pref` token.
- a bare `pref()` in a `.cfg` writes the **user** branch
  (`extensions/pref/autoconfig/src/prefcalls.js:12-18`), not the default branch.

So an unlocked default reaches Android fine through either channel. A **lock**
does not, until LW-M3-03 wires `Preferences::Lock` or LW-M3-08's autoconfig spike
succeeds. Rows that need a lock say so and name the dependency.

## The second reason a pref is not automatically a policy: three writers

Landmine L2 lists two channels that reach Gecko prefs on Android. Tracing the
policy rows turned up a **third**:

| writer | where | beats |
|---|---|---|
| `MOZ_DEFAULT_PREFS` | `GeckoLoader.java:83-103`, before profile load | nothing after it |
| Fenix `GeckoRuntimeSettings` / `ContentBlocking` `Pref.commit()` | on settings load | any unlocked pref |
| Fenix **Nimbus** `GeckoPrefHandler` | `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/experiments/prefhandling/NimbusGeckoPrefHandler.kt:54,283` — `setGeckoPrefsState()` driven by `FxNimbus.geckoPrefsMap()` | any unlocked pref, **from a remote server** |

The Nimbus map is small today (`mobile/android/fenix/app/nimbus.fml.yaml`: the
`nimbus.qa.*` / `gecko.nimbus.test*` test prefs, three
`network.http.happy_eyeballs*` and `privacy.trackingprotection.defer_annotation.enabled`)
but the *values* are fetched remotely, and the pref set is whatever the shipped
`nimbus.fml.yaml` declares. Registered as **P8**. It belongs in LW-M3-04's
must-lock analysis; it is recorded here because it was found while checking the
`DisableRemoteImprovements` row, and because no other document mentions it.

---

## Summary

| # | policy key | Android mechanism | gap |
|---|---|---|---|
| 1 | `AIControls` | mixed: Android defaults already match for the two features that exist; the other four have no Android code at all | — |
| 2 | `AppUpdateURL` | none needed — no updater on Android | — |
| 3 | `DisableAppUpdate` | none needed — no updater on Android | — |
| 4 | `DisableDefaultBrowserAgent` | none needed — Windows-only component | — |
| 5 | `DisableFeedbackCommands` | Kotlin | **P1** |
| 6 | `DisableFirefoxStudies` | pref (already in `common.cfg`) + Kotlin | **P2** |
| 7 | `DisableRemoteImprovements` | pref (already in `common.cfg`) + Kotlin | **P2** |
| 8 | `DisableSetDesktopBackground` | none needed — value is `false`, and desktop-only | — |
| 9 | `DisableTelemetry` | prefs (already in `common.cfg`) + Kotlin | **P3** |
| 10 | `DontCheckDefaultBrowser` | Kotlin | **P4** |
| 11 | `WebsiteFilter` | none needed — the shipped value is a self-cancelling placeholder | — |
| 12 | `EncryptedMediaExtensions` | **pref → `android.cfg`** | — |
| 13 | `ExtensionSettings` | Kotlin — preinstall half is **LW-M3-07**; restriction half has no analogue | **P5** |
| 14 | `FirefoxHome` | Kotlin | **P6** (= G4) |
| 15 | `FirefoxSuggest` | Kotlin | **P6** |
| 16 | `HttpsOnlyMode` | Kotlin default flip (a pref cannot hold it) | **P7** |
| 17 | `LocalNetworkAccess` | **pref → `android.cfg`** | — |
| 18 | `NoDefaultBookmarks` | none needed — Android ships no default bookmarks | — |
| 19 | `OverridePostUpdatePage` | none needed — no updater on Android | — |
| 20 | `SkipTermsOfUse` | Kotlin | **P4** |
| 21 | `SupportMenu` | Kotlin | **P1** |
| 22 | `UserMessaging` | Kotlin | **P6** (= G3) |

Two prefs are added to `settings/android.cfg` by this task. Both are **unlocked
defaults**, because both desktop policies are unlocked defaults. Neither pref is
in `common.cfg` or `desktop.cfg`, neither appears in `GeckoRuntimeSettings.java`
or `ContentBlocking.java`, and neither is in `nimbus.fml.yaml`'s gecko-pref map —
so no writer overwrites them and no lock is needed.

---

## Rows

### 1. `AIControls`

Desktop implementation: `Policies.sys.mjs:118-173`. For each named feature it
calls `setDefaultPref` on a `browser.ai.control.<feature>` reporting pref **and**
on the feature's real gate prefs, with `value === "available"`.

Taken sub-key by sub-key, because they do not share an answer:

| sub-key | our value | gate pref | on Android |
|---|---|---|---|
| `Translations` | `available` | `browser.translations.enable` | **already true** — `mobile/android/app/geckoview-prefs.js:137`. Matches. |
| `PDFAltText` | `blocked` | `pdfjs.enableAltText` | **already false** — `toolkit/components/pdfjs/PdfJsDefaultPrefs.js:33`. `PdfJsOverridePrefs.js` (`#include`d at `PdfJsDefaultPrefs.js:70`) sets it true only in its `#else` branch; the `#if defined(ANDROID)` branch at `:16-21` does not touch it. Matches. |
| `SmartTabGroups` | `blocked` | `browser.tabs.groups.smart.userEnabled` | pref only exists in `browser/app/profile/firefox.js:1139`; the feature is `browser/components/tabbrowser/SmartTabGrouping.sys.mjs`. Absent on Android. |
| `LinkPreviewKeyPoints` | `blocked` | `browser.ml.linkPreview.enabled` | pref only in `browser/app/profile/firefox.js:2262`; feature is `browser/components/genai/`. Absent on Android. |
| `SidebarChatbot` | `blocked` | `browser.ml.chat.enabled`, `browser.ml.chat.page` | pref only in `browser/app/profile/firefox.js:2239`; feature is `browser/components/genai/`. Absent on Android. |
| `SmartWindow` | `blocked` | (none — reporting pref only) | nothing to gate. |

The `browser.ai.control.*` reporting prefs are declared in
`modules/libpref/init/all.js:3636-3642`, so they *do* exist on Android. But their
only non-`browser/` readers are:

- `toolkit/components/translations/TranslationsFeature.sys.mjs:114-118`, which
  uses `browser.ai.control.translations` **only** in `isManagedByPolicy` (a UI
  greying-out check). The functional gate is `isBlocked` at `:87-89`, which reads
  `browser.translations.enable` and nothing else.
- `toolkit/components/nimbus/ExperimentAPI.sys.mjs:42,374,471,499-501`, which
  reads `browser.ai.control.default` — and `common.cfg:495` already locks that to
  `"blocked"`, so Android gets it.

Everything else that reads them (`browser/components/StartupTelemetry.sys.mjs:367-374`,
`browser/components/uitour/UITour.sys.mjs`, `browser/components/customizableui/content/panelUI.js:105`)
is desktop UI.

**Mechanism: no android.cfg pref.** The two features that exist on Android
already default to the value the policy would set; the other four have no code
to gate. Setting `browser.ai.control.translations` to `"available"` in
`android.cfg` would be cosmetic — nothing on Android reads it functionally — and
`android.cfg`'s own header warns against a second source for a value. Not a gap.

### 2. `AppUpdateURL` — `"https://localhost"`

Desktop: no policy body at all (`Policies.sys.mjs:302-305`); `UpdateService.sys.mjs`
reads the policy directly.

`build/moz.configure/update-programs.configure:8-19`: `updater_default` returns
`build_project != "mobile/android" and target.os != "iOS"`, so `MOZ_UPDATER` is
off for Android. `toolkit/moz.build:37` then reads
`if CONFIG["MOZ_UPDATER"] and CONFIG["MOZ_WIDGET_TOOLKIT"] != "android":` before
adding `mozapps/update` — a belt-and-braces double exclusion.

**Mechanism: none needed.** There is no update service to point anywhere. No gap:
the policy exists on desktop purely to neuter Mozilla's update endpoint, and on
Android there is no endpoint. Distribution updates come from the store/APK, which
is LW-M6's problem, not a policy-parity one.

### 3. `DisableAppUpdate` — `true`

Desktop: `Policies.sys.mjs:938-944`, `manager.disallowFeature("appUpdate")`.
Same evidence as row 2. **Mechanism: none needed.** No gap.

### 4. `DisableDefaultBrowserAgent` — `true`

Desktop: `Policies.sys.mjs:1021-1025` — an empty body; the implementation is in
the agent itself, `toolkit/mozapps/defaultagent`. `toolkit/moz.build:31-35`
builds it only under `CC_TYPE == "clang-cl"` / `MOZ_ARTIFACT_BUILDS` **and**
`MOZ_DEFAULT_BROWSER_AGENT` — a Windows-only scheduled task.

**Mechanism: none needed.** Nothing on Android to disable. No gap.

### 5. `DisableFeedbackCommands` — `true` → gap **P1**

Desktop: `Policies.sys.mjs:1050-1056`, `manager.disallowFeature("feedbackCommands")`.
Every consumer is `browser/`:
`browser/base/content/utilityOverlay.js:496`,
`browser/base/content/browser-safebrowsing.js:32`,
`browser/components/reportbrokensite/ReportBrokenSite.sys.mjs:419,669`.

Android has its own equivalents, none of which consult a policy:
`mozilla/components/feature/webcompat` (`WebCompatFeature.kt:16`,
extension id `webcompat@mozilla.org`) is installed from Kotlin at
`mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Core.kt:83`,
and Fenix's menu carries its own SUMO links via
`mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SupportUtils.kt:30-31`.

**Mechanism: Kotlin.** Remove/neutralise the Fenix feedback and "report broken
site" entries, and the `webcompat-reporter` install call.

**P1** — no pref reaches this. Overlaps `android.cfg`'s **G5** (web-compat
reporter), which covers the extension half; P1 additionally covers the menu
commands. Owner: M4.

### 6. `DisableFirefoxStudies` — `true` → gap **P2**

Desktop: `Policies.sys.mjs:1080-1094` — `disallowFeature("Shield")` plus locks on
two `...asrouter.userprefs.cfr.*` prefs.

Two independent study clients exist on Android and only one is reachable by pref.

*Gecko side, already covered.* `common.cfg:633` already ships
`lockPref("app.shield.optoutstudies.enabled", false)` — LW-M3-01 deliberately
kept it in the common half, with the comment explaining that `app.normandy.*`
went to desktop (`toolkit/components/moz.build:141-142` adds `normandy` and
`messaging-system` only for `MOZ_BUILD_APP == "browser"`, verified) while this
one is read by nimbus, which *is* built on Android (`toolkit/components/moz.build:147`,
unconditional `DIRS += ["nimbus"]`). `ExperimentAPI.sys.mjs:474-477` gates
studies on that pref **and** `Services.policies.isAllowed("Shield")` — the second
term is exactly the undefined-on-Android call, so the pref is doing the whole job
there.

*Kotlin side, not covered.* Fenix does not use `ExperimentAPI.sys.mjs`. It runs
the Rust/Kotlin Nimbus SDK: `NimbusSetup.kt:39-100` builds a `NimbusApi` with
`NimbusServerSettings(collectionName = "nimbus-mobile-experiments")`, and
participation is `settings.isExperimentationEnabled` —
`Settings.kt:751-754`, a **SharedPreferences** key
(`pref_key_experimentation_v2`, `res/values/preference_keys.xml:80`) whose
default is `isTelemetryEnabled`, i.e. **true**. No Gecko pref touches it.
`FenixApplication.kt:721` gates messaging restore on the same flag.

**Mechanism: pref (already shipped, covers the JS client) + Kotlin (required for
the real one).** The Kotlin change is a default flip of
`pref_key_experimentation_v2` to `false`.

**P2** — until that Kotlin change lands, LibreWolf for Android enrols in Mozilla
experiments by default while the desktop policy forbids it. This is the largest
single behavioural divergence in this document. Owner: M4.

### 7. `DisableRemoteImprovements` — `true` → gap **P2**

Desktop: `Policies.sys.mjs:1159-1165`, `disallowFeature("NimbusRollouts")`.

Same shape as row 6. `common.cfg:659` already ships
`lockPref("nimbus.rollouts.enabled", false)`, which is the pref
`ExperimentAPI.sys.mjs:43,488-492` reads (again alongside an
`isAllowed("NimbusRollouts")` term that is absent on Android).

The Kotlin side is a distinct setting: `Settings.kt:isRolloutsEnabled`, key
`pref_key_rollouts` (`preference_keys.xml:81`), whose default is
`appContext.components.nimbus.sdk.rolloutParticipation` — i.e. whatever the SDK
says, not `false`.

**Mechanism: pref (shipped) + Kotlin.** Flip `pref_key_rollouts` to a hard
`false` default.

Folded into **P2** because it is the same Kotlin Nimbus client and the same fix
site. Owner: M4.

### 8. `DisableSetDesktopBackground` — `false`

Desktop: `Policies.sys.mjs:1201-1207`. Our value is `false`, so the policy does
nothing even on desktop (`if (param)` is not taken). The feature it would guard
is `browser/`-only regardless.

**Mechanism: none needed.** No gap. Listed only so the key count is complete —
this row exists to record that it was checked, not skipped.

### 9. `DisableTelemetry` — `true` → gap **P3**

Desktop: `Policies.sys.mjs:1217-1227` — `setAndLockPref` on
`datareporting.healthreport.uploadEnabled`,
`datareporting.policy.dataSubmissionEnabled`,
`toolkit.telemetry.archive.enabled`, `datareporting.usage.uploadEnabled`, plus
`blockAboutPage(manager, "about:telemetry")`.

All four prefs are **already locked in `common.cfg`** (lines 628, 629, 616, 649
respectively), so LW-M3-01 has already carried the Gecko half to Android —
subject to the standing caveat that a `lockPref` in a `.cfg` is advisory on
Android until LW-M3-03 or LW-M3-08 lands. As *defaults* they still reach Gecko
through `MOZ_DEFAULT_PREFS`, and nothing in `GeckoRuntimeSettings.java` writes
them, so the practical risk of the missing lock is low for these four.

What the prefs do **not** cover is the telemetry that Fenix actually sends.
Fenix's Glean is driven entirely from Kotlin off a SharedPreferences flag:
`Settings.kt:618-621` `isTelemetryEnabled` (key `pref_key_telemetry`,
`preference_keys.xml:130`), **default `true`**, consumed at
`FenixApplication.kt:262` (`initializeGlean`), `Analytics.kt:132`
(`isUploadEnabled`), `GleanMetricsService.kt:75,95`
(`Glean.setCollectionEnabled`). Two further flags default off the same value:
`isMarketingTelemetryEnabled` (`pref_key_marketing_telemetry`) and
`isDailyUsagePingEnabled` (`Settings.kt:745-749`, `persistDefaultIfNotExists = true`).

**Mechanism: prefs (already shipped, cover the Gecko half) + Kotlin (required for
Glean).**

**P3** — the four locked prefs do not switch off a single Glean ping. Owner: M4.
This is the row most likely to be mistaken for "done" on a pref audit, because
`android-pref-audit.sh` will find all four prefs present and green.

### 10. `DontCheckDefaultBrowser` — `true` → gap **P4**

Desktop: `Policies.sys.mjs:1334-1338`, `setAndLockPref("browser.shell.checkDefaultBrowser", !param)`.

`browser.shell.checkDefaultBrowser` has no Android consumer. Its non-test readers
are `browser/components/aboutwelcome/*` and
`toolkit/components/messaging-system/lib/SpecialMessageActions.sys.mjs:353` —
and `messaging-system` is browser-only (`toolkit/components/moz.build:141-142`).
`toolkit/components/telemetry/app/TelemetryEnvironment.sys.mjs:245` merely records
its value.

Fenix has its own, unrelated default-browser nudge:
`Settings.kt:1222-1236` (`checkIfFenixIsDefaultBrowserOnAppResume`,
`isDefaultBrowserBlocking`), `Settings.kt:2863` (`shouldShowSetAsDefaultPrompt`,
driven by the `defaultBrowserPrompt` **Nimbus** feature), and
`Settings.kt:2839` `promptToSetAsDefaultBrowserDisplayedInOnboarding`.

**Mechanism: Kotlin.** Suppress the Fenix default-browser prompt directly; the
pref is inert on Android and must not be used as evidence of coverage.

**P4** — grouped with row 20, since both are onboarding-surface suppressions in
the same Fenix code area. Owner: M4.

### 11. `WebsiteFilter`

Desktop: `Policies.sys.mjs:3369-3373` → `browser/components/enterprisepolicies/helpers/WebsiteFilter.sys.mjs`
(the only copy in the tree; `browser/`, so not on Android).

Our shipped value blocks `https://localhost/*` and then lists the identical
pattern under `Exceptions`. It is a self-cancelling placeholder that filters
nothing, present so the key is documented rather than to enforce anything.

**Mechanism: none needed.** Reproducing an inert filter would be pure cost. No
gap. If LibreWolf ever gives this policy real content, this row becomes a gap —
Android would need a `feature/sitepermissions`-style Kotlin interceptor or a
`nsIContentPolicy`, and there is no pref for it.

### 12. `EncryptedMediaExtensions` — `{"Enabled": false}` → **pref, added to `android.cfg`**

Desktop: `Policies.sys.mjs:1463-1473` — `PoliciesUtils.setDefaultPref("media.eme.enabled", false, param.Locked)`.
Our JSON has no `Locked` key, so this is an **unlocked default**.

This is the one row where Android's default actively disagrees with LibreWolf.
`modules/libpref/init/StaticPrefList.yaml:12163-12176`:

```
- name: media.eme.enabled
  type: bool
#if defined(XP_LINUX) && !defined(MOZ_WIDGET_ANDROID)
  value: false
#else
  value: true
#endif
```

The `!defined(MOZ_WIDGET_ANDROID)` in that guard is explicit: **Android takes the
`#else`, so EME is `true` by default.** Neither `common.cfg` nor `desktop.cfg`
sets `media.eme.enabled` — desktop LibreWolf gets it from this policy alone. So
without an `android.cfg` entry, LibreWolf for Android would ship DRM enabled
while LibreWolf desktop ships it disabled.

Android does have an extra approval layer —
`mobile/android/app/geckoview-prefs.js:287` sets `media.eme.require-app-approval`
true, and `dom/media/eme/MediaKeySystemAccessManager.cpp:259` then routes each
request through an embedder permission prompt
(`GeckoSession.java:7213` `PERMISSION_LOCAL_NETWORK_ACCESS`'s sibling
`PERMISSION_MEDIA_KEY_SYSTEM_ACCESS` at `:7195`,
`SitePermissions.kt:94`) — but that is a per-site prompt, not the blanket
disable the policy expresses.

**Mechanism: `defaultPref("media.eme.enabled", false);` in `android.cfg`.**

Branch and lock: **default branch, unlocked** — matching desktop exactly.
`media.eme.enabled` appears in neither `GeckoRuntimeSettings.java` nor
`ContentBlocking.java` nor `nimbus.fml.yaml`, so nothing overwrites it after
startup and no lock is required. It therefore works through `MOZ_DEFAULT_PREFS`
today and needs nothing from LW-M3-08.

### 13. `ExtensionSettings` → gap **P5**, preinstall half is **LW-M3-07**

Desktop: `Policies.sys.mjs:1542-1560` (`manager.setExtensionSettings(param)` +
`applyExtensionGuards`) and `:1558-1723` (`onBeforeUIStartup`, which walks the
per-extension entries and installs `normal_installed` ones).

Two halves with different answers:

**a) the uBO preinstall row** (`uBlock0@raymondhill.net`, `normal_installed`,
`private_browsing: true`).

→ **This is LW-M3-07** (`patches/android/ubo-preinstall.patch`). Do not attempt
it here and do not treat it as covered by this document. The Android mechanism is
a Kotlin/addons-provider change; LW-M3-07 also owns keeping
`librewolf.uBO.assetsBootstrapLocation` working on Android. The only thing this
row contributes is confirming *why* it needs its own task: `setExtensionSettings`
lives on `EnterprisePoliciesParent.sys.mjs`, which is inside the
`MOZ_WIDGET_TOOLKIT != "android"` branch of
`toolkit/components/enterprisepolicies/moz.build:16`, so there is no policy path
to reuse.

**b) the `"*"` restriction row** (`installation_mode: allowed`,
`allowed_types: [dictionary, extension, sitepermission, theme]`,
`blocked_install_message` about language packs).

Note first that this row is already permissive on desktop —
`installation_mode` is `allowed`, so the `blockAllExtensions` branch at
`Policies.sys.mjs:1562-1575` is *not* taken. Its only real effect is excluding
`locale` from `allowed_types`, i.e. blocking language packs.

On Android there is no equivalent enforcement point. What controls add-on
availability instead is the AMO collection, chosen at build time:
`mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Components.kt:190-216`
picks an `AMOAddonsProvider` from `BuildConfig.AMO_SERVER_URL` /
`AMO_COLLECTION_USER` / `AMO_COLLECTION_NAME` (with a Nightly/Beta override via
`settings.overrideAmoUser`). That is a Gradle/`BuildConfig` mechanism, and it is
a *whitelist of specific add-ons*, not a type filter.

**Mechanism: Kotlin/Gradle for (a) via LW-M3-07; nothing for (b).**

**P5** — `allowed_types` has no Android analogue. The practical exposure is small
(Fenix does not offer language packs; app locale is an Android-side setting, and
`common.cfg:422-423` already disables `app.update.langpack.enabled` and blanks
`extensions.getAddons.langpacks.url`), but it is a real absence of the
*enforcement*, not a case of the policy being unnecessary. Record it as a gap
rather than as "not applicable". Owner: M4/M5.

### 14. `FirefoxHome` — six sub-keys, all `false` → gap **P6**

Desktop: `Policies.sys.mjs:1733-1820`. Every sub-key maps to a
`browser.newtabpage.activity-stream.*` pref
(`showWeather` + `widgets.weather.enabled`, `feeds.topsites`,
`showSponsoredTopSites`, `feeds.section.highlights`, `feeds.section.topstories`,
`showSponsored`).

`browser/components/newtab/` is desktop-only, so **not one of those prefs has a
reader on Android**. Fenix's home screen is Kotlin, with its own settings:

| policy sub-key | Fenix equivalent |
|---|---|
| `TopSites: false` | `Settings.kt:270` `showTopSitesFeature`, key `pref_key_show_top_sites` (`preference_keys.xml:381`), default from the `homescreen` Nimbus feature |
| `SponsoredTopSites: false` | `Settings.kt:2187` `showContileFeature`, key `pref_key_enable_contile` (`preference_keys.xml:383`), **default `true`** |
| `Weather`, `Highlights`, `Stories`, `SponsoredStories` | the corresponding `HomeScreenSection` entries of the `homescreen` Nimbus feature (`Settings.kt:253-292`) |

**Mechanism: Kotlin.** Setting the activity-stream prefs in `android.cfg` would
be worse than doing nothing: they would sit in `about:config` looking like
coverage while changing no behaviour.

**P6** — this is `android.cfg`'s existing **G4** seen from the policy side. The
new information versus G4 is the `pref_key_enable_contile` default of `true`:
sponsored tiles are **on** in stock Fenix, so this is an opt-out we currently do
not perform. Owner: M4.

### 15. `FirefoxSuggest` — three sub-keys, all `false` → gap **P6**

Desktop: `Policies.sys.mjs:1822-1850` — `browser.urlbar.suggest.quicksuggest.all`,
`browser.urlbar.suggest.quicksuggest.sponsored`,
`browser.urlbar.quicksuggest.online.enabled`, all via `QuickSuggest.initPromise`.
`browser/components/urlbar/QuickSuggest.sys.mjs` is desktop-only.

Firefox Suggest **does** exist on Android — this is the row most likely to be
wrongly waved away. `mobile/android/android-components/components/feature/fxsuggest`
is a real component, and Fenix gates it on three SharedPreferences flags
(`Settings.kt:2607-2650`):

| flag | key | default |
|---|---|---|
| `enableFxSuggest` | `pref_key_fxsuggest_enabled` (`preference_keys.xml:99`) | the `fxSuggest` Nimbus feature's `enabled` |
| `showSponsoredSuggestions` | `pref_key_show_sponsored_suggestions` (`:171`) | `enableFxSuggest` |
| `showNonSponsoredSuggestions` | `pref_key_show_nonsponsored_suggestions` (`:172`) | `enableFxSuggest` |

All three additionally sit behind `FeatureFlags.FX_SUGGEST`.

**Mechanism: Kotlin.** Force `enableFxSuggest` false (which drops the other two
with it) rather than relying on the Nimbus default — see P2: Nimbus is live.

**P6.** Related to `android.cfg`'s **G6** (urlbar surfaces) but distinct: G6 is
about awesomebar suggestion providers and `Engine.speculativeConnect`; this is
the sponsored-content feed. Owner: M4.

### 16. `HttpsOnlyMode` — `"enabled"` → gap **P7**

Desktop: `Policies.sys.mjs:2033-2050`. Note the asymmetry in that switch:
`"force_enabled"` calls `setAndLockPref`, but our value `"enabled"` calls
`PoliciesUtils.setDefaultPref("dom.security.https_only_mode", true)` with no
third argument — an **unlocked default**. LibreWolf deliberately leaves the user
able to turn it off.

That distinction is what makes this row hard on Android, because
`dom.security.https_only_mode` is a **Fenix-mutated pref**:

- `GeckoRuntimeSettings.java:782` declares `new Pref<Boolean>("dom.security.https_only_mode", false)`
- `GeckoEngine.kt:1762-1773` maps `Engine.HttpsOnlyMode` onto it
- `Core.kt:189` passes `context.components.settings.getHttpsOnlyMode()`
- `Settings.kt:2310-2318` `getHttpsOnlyMode()` returns `DISABLED` when
  `shouldUseHttpsOnly` is false, and `Settings.kt:1168-1171` gives
  `shouldUseHttpsOnly` (key `pref_key_https_only`) a default of **`false`**

So this is landmine L2 in its purest form: an unlocked `defaultPref` of `true`
would be set before profile load and then **deterministically overwritten with
`false`** the moment Fenix commits its settings. Not intermittently — on every
launch.

The available answers, and why the obvious one is wrong:

1. `lockPref("dom.security.https_only_mode", true)` — survives the commit, but
   (i) it needs LW-M3-03 or LW-M3-08 to be a real lock at all, and (ii) it is
   **stricter than desktop**, which deliberately left this unlocked, and (iii) it
   makes Fenix's visible HTTPS-Only settings toggle do nothing, which is exactly
   the over-locking failure AGENTS.md warns about under L2. This pref belongs on
   LW-M3-04's must-**not**-lock allowlist.
2. **Kotlin: flip the `pref_key_https_only` default to `true`.** This reproduces
   desktop's semantics exactly — on by default, user can turn it off, the toggle
   keeps working — and it is robust regardless of how LW-M3-08 turns out.

**Mechanism: Kotlin (option 2). No `android.cfg` pref.** This row does not
depend on the autoconfig spike: even if LW-M3-08 succeeds and locking becomes
available, locking would still be the wrong answer here.

**P7** — until that Kotlin default lands, LibreWolf for Android browses plain
HTTP by default while LibreWolf desktop does not. Owner: M4, and it should be
early in M4.

### 17. `LocalNetworkAccess` → **pref, added to `android.cfg`**

Desktop: `Policies.sys.mjs:2124-2177`. With `Enabled: true`, it sets
`network.lna.enabled` = true, `network.lna.block_trackers` = `BlockTrackers`,
`network.lna.blocking` = `EnablePrompting`, all through `setDefaultPref` with
`param.Locked` — absent in our JSON, so **unlocked defaults**.

Against the Android defaults in `modules/libpref/init/StaticPrefList.yaml`:

| pref | policy value | StaticPrefList default | action |
|---|---|---|---|
| `network.lna.enabled` | `true` | `true` (`:15373-15376`) | already matches |
| `network.lna.blocking` | `true` (`EnablePrompting`) | `true` (`:15379-15382`) | already matches |
| `network.lna.block_trackers` | `true` (`BlockTrackers`) | **`false`** (`:15386-15389`) | **needs setting** |

`common.cfg:280-282` already ships three neighbouring `network.lna.*` prefs
(`websocket.enabled`, `allow_top_level_navigation`,
`local-network-to-localhost.skip-checks`) but not `block_trackers` — desktop gets
that one from the policy only.

The prompting half of the policy is functional on Android: GeckoView carries
`PERMISSION_LOCAL_NETWORK_ACCESS` (`GeckoSession.java:7213`, string
`"local-network"` at `:7364,7394`) and android-components stores it
(`SitePermissions.kt:31,97`, `SitePermissionsStorage.kt:82`).

**Mechanism: `defaultPref("network.lna.block_trackers", true);` in `android.cfg`.**

Branch and lock: **default branch, and it NEEDS A LOCK.**

> **Correction.** An earlier version of this row claimed the pref is "not present in
> `GeckoRuntimeSettings.java`, `ContentBlocking.java` or `nimbus.fml.yaml`, so no
> writer overwrites it and no lock is needed." That is false, and it was caught by
> skeptical verification rather than by any gate. It **is** declared at
> `GeckoRuntimeSettings.java:789` as
> `new PrefWithoutDefault<>("network.lna.block_trackers")`.
>
> That makes this the textbook landmine-L2 case: GeckoView owns the pref at
> runtime, so an unlocked `defaultPref` survives startup and is then overwritten
> the moment Fenix touches it. And per LW-M3-01 the `MOZ_DEFAULT_PREFS` channel
> **cannot express a lock at all** — there is no `locked_pref` token in
> `modules/libpref/parser/src/lib.rs`. So the value we ship is advisory until
> LW-M3-08 settles whether autoconfig works on Android.
>
> The lesson generalises: "I grepped and did not find it" is not evidence for
> "nothing writes it". Every negative claim in this document that rules out a lock
> should be re-checked against the real `PrefWithoutDefault` / `Pref` declarations
> in both Java files, not against a name search.

### 18. `NoDefaultBookmarks` — `true`

Desktop: `Policies.sys.mjs:2208-2214`, `disallowFeature("defaultBookmarks")`.
Both consumers are `browser/`:
`browser/components/places/PlacesBrowserStartup.sys.mjs:211` and
`browser/components/migration/MigratorBase.sys.mjs:433`.

Android's bookmark store is application-services Places driven from Kotlin
(`mozilla.appservices.places.BookmarkRoot`, e.g.
`mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/bookmarks/BookmarksUseCase.kt:57-97`).
There is no `bookmarks.html` import path and no default bookmark seeding to
suppress.

**Mechanism: none needed.** No gap.

### 19. `OverridePostUpdatePage` — `""`

Desktop: `Policies.sys.mjs:2244-2253` — locks `startup.homepage_override_url` to
`""` and calls `disallowFeature("postUpdateCustomPage")`.

`startup.homepage_override_url`'s only non-branding, non-test reader is
`browser/components/BrowserContentHandler.sys.mjs:854`. And per rows 2-3 there is
no update on Android to produce a post-update page in the first place.

**Mechanism: none needed.** No gap.

### 20. `SkipTermsOfUse` — `true` → gap **P4**

Desktop: `Policies.sys.mjs:3220-3227` — `setAndLockPref("termsofuse.acceptedVersion", 999)`
and `termsofuse.acceptedDate`.

Neither pref has an Android consumer; the Firefox ToU flow is desktop UI.
`common.cfg:591` already locks `termsofuse.bypassNotification` true, which is the
Gecko-side flag LW-M3-01 kept common.

Fenix has an entirely separate ToU prompt, in SharedPreferences and Nimbus:
`Settings.kt:633` `hasAcceptedTermsOfService`, `:671` `termsOfUseAcceptedVersion`,
`:679-681` `isTermsOfUsePromptEnabled` (defaulting to the `termsOfUsePrompt`
Nimbus feature's `enabled`), `:710` `termsOfUsePromptDisplayedCount`,
`:728` `hasPostponedAcceptingTermsOfUse`.

**Mechanism: Kotlin.** Suppress the Fenix ToU prompt at its own flags — and note
that leaving it to the Nimbus default is not safe while P2 is open.

**P4** (with row 10). Owner: M4.

### 21. `SupportMenu` — `{Title, URL}` → gap **P1**

Desktop: `Policies.sys.mjs:3277-3281`, `manager.setSupportMenu(param)`
(`EnterprisePoliciesParent.sys.mjs:411-417`). Consumers are all desktop chrome:
`browser/base/content/utilityOverlay.js:504`,
`browser/base/content/browser-menubar.js:106`,
`browser/components/customizableui/content/panelUI.js:835`.

Fenix's help entry points at hardcoded Mozilla URLs —
`mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SupportUtils.kt:30-31`
(`FXACCOUNT_SUMO_URL`, `ANDROID_SUPPORT_SUMO_URL`) and
`SupportUtils.getSumoURLForTopic` at `:93`.

**Mechanism: Kotlin.** Repoint the help/support menu at
`https://codeberg.org/librewolf/issues`, matching the desktop policy's value.

**P1** (with row 5) — same Fenix menu area, same fix site. Small, visible, and
cheap; a good early M4 item. Owner: M4.

### 22. `UserMessaging` — four sub-keys → gap **P6**

Desktop: `Policies.sys.mjs:3300-3355`.

| sub-key | our value | desktop effect | on Android |
|---|---|---|---|
| `UrlbarInterventions` | `false` | `disallowFeature("urlbarinterventions")` | `browser/components/urlbar` is desktop-only; nothing to disable |
| `SkipOnboarding` | `true` | `setDefaultPref("browser.aboutwelcome.enabled", false)` | `browser/components/aboutwelcome` is desktop-only; Fenix onboarding is Kotlin |
| `MoreFromMozilla` | `false` | `setDefaultPref("browser.preferences.moreFromMozilla", false)` | desktop preferences pane; no Android reader |
| `FirefoxLabs` | `false` | `disallowFeature("FirefoxLabs")` | read at `ExperimentAPI.sys.mjs:484-486` via `Services.policies.isAllowed` — undefined on Android, so **no pref substitutes for it**; Fenix has its own "secret settings"/debug surfaces |

**Mechanism: Kotlin** for the onboarding half; nothing needed for the three
desktop-only halves.

**P6** — this is `android.cfg`'s existing **G3** (first-run and messaging
surfaces) seen from the policy side. Note `FirefoxLabs` is the one sub-key where
the desktop mechanism is a policy check with **no pref behind it at all**, so
there is nothing to port even in principle. Owner: M4.

---

## Gap register (feeds the M5 parity matrix)

| id | what is missing on Android | mechanism required | related `android.cfg` gap | owner |
|---|---|---|---|---|
| **P1** | feedback/report-broken-site commands and the support-menu URL | Kotlin | G5 (extension half only) | M4 |
| **P2** | Fenix's Kotlin Nimbus SDK enrols in experiments and rollouts by default; the Gecko-side prefs do not reach it | Kotlin (`pref_key_experimentation_v2`, `pref_key_rollouts` defaults) | — | M4 |
| **P3** | Glean telemetry is on by default and is not governed by the four `datareporting`/`toolkit.telemetry` prefs | Kotlin (`pref_key_telemetry`, `pref_key_marketing_telemetry`, `pref_key_daily_usage_ping`) | — | M4 |
| **P4** | Fenix default-browser prompt and ToU prompt | Kotlin | G3 | M4 |
| **P5** | no enforcement point for `ExtensionSettings`'s `allowed_types` restriction | none known; AMO collection is a whitelist, not a type filter | — | M4/M5 |
| **P6** | home-screen sponsored content, Firefox Suggest, onboarding/messaging surfaces | Kotlin | G3, G4, G6 | M4 |
| **P7** | HTTPS-Only is off by default on Android and a pref cannot fix it without breaking the settings toggle | Kotlin (`pref_key_https_only` default) | — | M4, early |
| **P8** | Nimbus `GeckoPrefHandler` is a third, **remote** writer of Gecko prefs that landmine L2 does not list | LW-M3-04 must include it in the must-lock analysis | — | M3 |

Six of the eight are Kotlin-layer work in M4. That is the honest headline of this
document: **the policy engine's absence is mostly not a pref problem.** Two prefs
close two rows; everything else needs code in Fenix.

## What this task did *not* do, and why

- **No `policies.json` shim.** There is no Android reader; shipping it would be
  inert.
- **No pref for a policy whose target pref has no Android reader.** Rows 14, 15,
  19 and 22 all *could* have had `android.cfg` lines that parse fine and change
  nothing. That is precisely the "hole labelled done" this task's risk field
  warns about, and `scripts/android-pref-audit.sh` would report them green.
- **No lock added anywhere.** Both prefs this task adds are unlocked defaults
  because both desktop policies are unlocked defaults. Row 16 is the one place a
  lock was considered and rejected on parity grounds, not on feasibility grounds.

## Dependency on LW-M3-08

Stated explicitly, since the brief asks for it: **the two prefs this task adds do
not depend on the autoconfig spike either way.** Both are unlocked defaults on
prefs no Fenix writer touches, so `MOZ_DEFAULT_PREFS` (which writes the default
branch and cannot lock) carries them correctly today, and native autoconfig would
carry them identically.

The spike's outcome does not change any row above. Row 16 is the only row where
locking was on the table, and it was rejected because locking would be *wrong*
there, not because locking is currently *unavailable*. Should a future policy row
need a genuine lock, that row would become LW-M3-08-dependent; none does today.
