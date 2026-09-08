# Desktop patch and policy effect map — LW-M7-17

Audit snapshot: `7c78e8a3a86d6feed5ea0517b9c824ce0cbfa8ae`; settings `2206f8d1e59c0a0c0f69ee3fe5121eb353426687`.

All pinned desktop patches, all policy leaves and all copied pane settings/buttons/registrations. Human semantic review plus mechanical enumeration; not a build/runtime parity gate.

**This is source coverage, not feature completion. No browser runtime check was executed by this audit.** Each counterpart below has explicit remaining work; “source implemented” does not mean its behavior has passed on the APK. Concurrent LW-M7-14/LW-M7-16 implementations are outside this snapshot.

## Desktop patches

| Input | Effects | Android counterpart / remaining work |
| --- | --- | --- |
| `patches/add-mojeek.patch` | Package the added Mojeek search icon and metadata for desktop search. | [search](#search) |
| `patches/dbus_name.patch` | Change D-Bus destination/interface namespaces, fallback name and OpenURL routing from org.mozilla to io.gitlab. | [platform](#platform), [branding](#branding) |
| `patches/disable-data-reporting-desktop.patch` | Compile out desktop healthreport and Normandy inputs; remove tab-opening UserInteraction probes. | [telemetry](#telemetry) |
| `patches/eme-permission-desktop.patch` | Route media-key-system-access to a doorhanger; allow/block, remember only outside private browsing, honor browser.eme.ui.enabled, and show branded explanatory URL. | [eme](#eme), [support](#support) |
| `patches/fullpage-translations-customization.patch` | Expose global translation enable and separate automatic-popup settings; initialize/download UI only when enabled and add a disable-translations route from the page panel. | [translations](#translations) |
| `patches/hide-passwordmgr.patch` | Optional librewolf.hidePasswdmgr removes the app password command and preferences group. | [password](#password) |
| `patches/languages.patch` | Include ku in shipped desktop locales. | [locale](#locale) |
| `patches/link-preview.patch` | Keep ordinary link-preview enable independent from AI key-points opt-in/visibility. | [link-preview](#link-preview), [ai](#ai) |
| `patches/lw-permissions.patch` | Expose global EME approval/UI and WebGL gates, visible exception editors, allow/block site entries and disabled-state invalidation. | [eme](#eme), [graphics](#graphics) |
| ↳ | Package EME/WebGL prompt modules and show their blocked/notification icons and permission labels. | [eme](#eme), [graphics](#graphics), [platform](#platform) |
| `patches/macos-relaunch-without-updater.patch` | Use updater.app for relaunch only when it exists; otherwise permit direct NSWorkspace app relaunch. | [platform](#platform) |
| `patches/moz-official-desktop.patch` | Keep XUL quick-restart development helper packaged and load/init it only with optional librewolf.devHelpers, even in official builds. | [platform](#platform), [profile-config](#profile-config) |
| `patches/msix.patch` | Set Windows package runtime dependency/tile background and remove MSAA COM proxy registrations; correct LibreWolf version encoding, vendor/identity/display name and distribution-directory handling during MSIX repackaging. | [platform](#platform), [branding](#branding) |
| `patches/newtab-fix.patch` | Stop desktop new-tab initialization awaiting trainhopFeatureReady after experiment removal. | [remote-improvements](#remote-improvements), [home](#home) |
| `patches/remove-language-packs.patch` | On browser startup uninstall every existing locale-type add-on and log failures, separately from rejecting future installs. | [extension-types](#extension-types) |
| `patches/remove-pingsender-desktop.patch` | Remove pingsender from macOS package inputs, main installer manifest and Windows executable handling; common code removes its build entry. | [telemetry](#telemetry), [platform](#platform) |
| `patches/temp-macos-fix.patch` | Use legacy icns icons instead of CFBundleIconName/AppIcon/Assets.car and stop copying/packaging Assets.car. | [platform](#platform), [branding](#branding) |
| `patches/ui-patches/add-translate-page-context-menu.patch` | Add Translate Page action with enable/hardware/about-page/context guards, distinct from selection translation. | [translations](#translations) |
| `patches/ui-patches/allow_cookies_for_site.patch` | Both identity and trust panels expose current exact-principal cookie ALLOW state, set persistent EXPIRE_NEVER permission and remove exactly that permission when switched off. | [cookie-exemption](#cookie-exemption) |
| `patches/ui-patches/firefox-view.patch` | Keep Firefox View available in customization but remove default toolbar placement and automatic migration insertion. | [platform](#platform), [home](#home) |
| `patches/ui-patches/hide-default-browser.patch` | Remove default-browser settings group, polling and state/button controls, and startup always-check option. | [onboarding](#onboarding), [platform](#platform) |
| `patches/ui-patches/hide-finish-setup-bookmark.patch` | Make both onboarding/easy-checklist message targeting expressions false. | [onboarding](#onboarding) |
| `patches/ui-patches/home-preferences.patch` | Hide Support Firefox sponsored-content marketing and mission message in desktop settings. | [home](#home), [support](#support) |
| `patches/ui-patches/lw-logo-devtools.patch` | Use LibreWolf runtime/logo images in desktop about:debugging for every channel and package them. Android builds server devtools, not this client frontend. | [branding](#branding), [platform](#platform) |
| `patches/ui-patches/neterror-desktop.patch` | Package shared warning illustration in the desktop toolkit jar. | [neterror](#neterror) |
| `patches/ui-patches/pref-naming.patch` | Change DRM help label to Why we disable it and update version link label to Visit the repositories. | [eme](#eme), [support](#support), [app-update](#app-update) |
| `patches/ui-patches/privacy-preferences.patch` | Hide Standard/Custom ETP choices and breakage warning, relocate RFP warning, remove introductory marketing and adjust spacing. | [privacy-defaults](#privacy-defaults), [rfp-controls](#rfp-controls) |
| ↳ | Remove history-mode/permanent-private group choices and simplify history UI while retaining individual controls. | [privacy-defaults](#privacy-defaults), [platform](#platform) |
| ↳ | Remove data-collection/studies/rollouts/crash/telemetry UI and Safe Browsing group initialization. | [telemetry](#telemetry), [remote-improvements](#remote-improvements), [network-controls](#network-controls) |
| `patches/ui-patches/remove-cfrprefs.patch` | Remove extension/feature recommendation pref controls, groups and legacy/redesigned pane placements. | [remote-improvements](#remote-improvements), [home](#home) |
| `patches/ui-patches/remove-organization-policy-banner.patch` | Stop desktop preferences showing the organization policy notice solely because LibreWolf policies are installed. | [policy-engine](#policy-engine), [platform](#platform) |
| `patches/ui-patches/settings-redesign.patch` | Remove updater groups and Share Ideas link; use LibreWolf branding for about/language/sidebar icons, scale newtab/private wordmarks and name backup folder Restore LibreWolf. | [app-update](#app-update), [support](#support), [branding](#branding), [platform](#platform) |
| ↳ | Expose Sync on/off with restart in account enabled/disabled UI; remove default-browser promos across general/home/account. | [sync](#sync), [onboarding](#onboarding) |
| ↳ | Expose separate translation-global/automatic-popup controls and conditionally disable popup choice. | [translations](#translations) |
| ↳ | Expose combined extension-update, IPv6 and referrer controls; move into privacy grouping and remove Safe Browsing/status-warning cards. | [addon-updates](#addon-updates), [network-controls](#network-controls), [telemetry](#telemetry) |
| ↳ | Expose RFP, optional letterboxing, WebGL-global and quiet controls; retain Strict-only ETP, remove RFP warning and simplify history/permanent-private/delete-on-close layout. | [rfp-controls](#rfp-controls), [graphics](#graphics), [privacy-defaults](#privacy-defaults) |
| ↳ | Expose combined clipboard autocopy/middle-paste and userChrome stylesheet controls; these act on desktop chrome/input, not a Kotlin UI. | [platform](#platform), [profile-config](#profile-config) |
| ↳ | Expose optional JPEG XL image decoding. | [jxl](#jxl) |
| ↳ | Remove sponsored shortcuts/stories/mission promo settings and legacy trust-panel graphic; reorganize panes and add user toggle between legacy/redesigned desktop settings with reload. | [home](#home), [platform](#platform) |
| `patches/ui-patches/trustpanel.patch` | Hide ETP promotional description/graphic but preserve tracker count; reorder toggle/count and simplify panel spacing, backgrounds and typography. | [privacy-defaults](#privacy-defaults), [home](#home), [platform](#platform) |
| `patches/ui-patches/website-appearance-ui-rfp.patch` | Show an RFP warning and disable/fade website color chooser while RFP is enabled, restore interaction when disabled. | [rfp-controls](#rfp-controls) |
| `patches/webgl-permission-desktop.patch` | Route normal/quiet WebGL observer events, suppress duplicate or decided prompts, store session/permanent allow/deny, omit persistence in private browsing, reload on allow and show warning/help plus notification/blocked icons. | [graphics](#graphics), [support](#support) |
| `patches/windows-theming-bug.patch` | Rename/brand Windows EXE compatibility manifest so app-name changes retain correct Windows titlebar/OS behavior. | [platform](#platform), [branding](#branding) |
| `patches/xdg-dir.patch` | Adjust GTK profile path/vendor/dot handling, detect real legacy profiles.ini, permit XDG even with app profile name, ensure and return the actual profile directory. | [platform](#platform), [profile-config](#profile-config) |
| `patches/xmas-desktop.patch` | Package local-settings.js, librewolf.cfg and policies.json for desktop. Android autoconfig fallback/manifest is the separate actual config-loading counterpart. | [policy-engine](#policy-engine), [profile-config](#profile-config) |
| `patches/pref-pane/pref-pane-small.patch` | Package/register the LibreWolf preferences JS/XHTML/CSS/icon, replace AI navigation with LibreWolf navigation, and define behavior/network/privacy/fingerprinting control groups. | [policy-engine](#policy-engine), [ai](#ai), [profile-config](#profile-config), [addon-updates](#addon-updates), [sync](#sync), [network-controls](#network-controls), [rfp-controls](#rfp-controls), [graphics](#graphics) |

Every affected desktop tree path and patch SHA-256 is recorded in `coverage.json`; the checker compares all paths and bytes with the registered input list. Path coverage is accounting only. The human effect analysis, not the path prefix, determines the counterpart.

## Policy leaves

Arrays are exact whole values, including order and every element. Policies lacking `Locked=true` are not silently promoted to locked settings. Packaging policies.json does not activate its desktop service on Android.

| JSON Pointer | Pinned value | Effect | Counterpart |
| --- | --- | --- | --- |
| `/AIControls/Translations/Value` | `"available"` | Translations: available. This leaf requires its own effective feature/entry-point check. | [translations](#translations), [ai](#ai) |
| `/AIControls/PDFAltText/Value` | `"blocked"` | PDFAltText: blocked. This leaf requires its own effective feature/entry-point check. | [ai](#ai) |
| `/AIControls/SmartTabGroups/Value` | `"blocked"` | SmartTabGroups: blocked. This leaf requires its own effective feature/entry-point check. | [ai](#ai) |
| `/AIControls/LinkPreviewKeyPoints/Value` | `"blocked"` | LinkPreviewKeyPoints: blocked. This leaf requires its own effective feature/entry-point check. | [ai](#ai) |
| `/AIControls/SidebarChatbot/Value` | `"blocked"` | SidebarChatbot: blocked. This leaf requires its own effective feature/entry-point check. | [ai](#ai) |
| `/AIControls/SmartWindow/Value` | `"blocked"` | SmartWindow: blocked. This leaf requires its own effective feature/entry-point check. | [ai](#ai) |
| `/AppUpdateURL` | `"https://localhost"` | Point the Mozilla desktop update endpoint at localhost; do not contact Mozilla update servers. | [app-update](#app-update), [platform](#platform) |
| `/DisableAppUpdate` | `true` | Disable the Mozilla application updater. | [app-update](#app-update), [platform](#platform) |
| `/DisableDefaultBrowserAgent` | `true` | Disable the desktop background default-browser agent. | [platform](#platform), [onboarding](#onboarding) |
| `/DisableFeedbackCommands` | `true` | Suppress product feedback commands. Android reporters/routes must be audited independently of upload transport. | [support](#support), [telemetry](#telemetry) |
| `/DisableFirefoxStudies` | `true` | Prevent study enrollment and experiment fetching. | [remote-improvements](#remote-improvements) |
| `/DisableRemoteImprovements` | `true` | Prevent remotely delivered rollouts/improvements. | [remote-improvements](#remote-improvements) |
| `/DisableSetDesktopBackground` | `false` | False leaves desktop Set as background permitted; this is not a requirement to disable Android wallpaper actions. | [platform](#platform) |
| `/DisableTelemetry` | `true` | Prevent telemetry collection/upload mechanisms expressed by this policy. | [telemetry](#telemetry) |
| `/DontCheckDefaultBrowser` | `true` | Do not perform unsolicited desktop default-browser checks/prompts. | [onboarding](#onboarding), [platform](#platform) |
| `/WebsiteFilter/Block` | `["https://localhost/*"]` | Identical localhost block/exception sets have no effective denial. | [website-filter](#website-filter) |
| `/WebsiteFilter/Exceptions` | `["https://localhost/*"]` | Identical localhost block/exception sets have no effective denial. | [website-filter](#website-filter) |
| `/EncryptedMediaExtensions/Enabled` | `false` | Default EME off, unlocked because no Locked=true is supplied. | [eme](#eme) |
| `/ExtensionSettings/*/blocked_install_message` | `"LibreWolf does not allow installing Language Packs."` | Explain rejected language-pack installation to the user. | [extension-types](#extension-types) |
| `/ExtensionSettings/*/installation_mode` | `"allowed"` | Ordinary allowed installations remain user-controlled and are constrained by allowed_types. | [extension-types](#extension-types) |
| `/ExtensionSettings/*/allowed_types` | `["dictionary", "extension", "sitepermission", "theme"]` | Permit exactly dictionary, extension, sitepermission and theme install types, excluding locale. | [extension-types](#extension-types) |
| `/ExtensionSettings/uBlock0@raymondhill.net/install_url` | `"https://addons.mozilla.org/firefox/downloads/latest/uBlock0@raymondhill.net/latest.xpi"` | Use a genuine signed uBO install source; the Android offline build pins and verifies the XPI instead of relying on a live latest URL. | [ubo](#ubo) |
| `/ExtensionSettings/uBlock0@raymondhill.net/installation_mode` | `"normal_installed"` | normal_installed preinstalls once and permits user disable/uninstall; it is not force_installed. | [ubo](#ubo) |
| `/ExtensionSettings/uBlock0@raymondhill.net/private_browsing` | `true` | Enable private permission for the initial install, then preserve later user choice. | [ubo](#ubo) |
| `/FirefoxHome/Weather` | `false` | Weather is false. Map to the Android home surface and prove absence/default state independently. | [home](#home) |
| `/FirefoxHome/TopSites` | `false` | TopSites is false. This is ordinary home content; advertisement removal does not implement it. | [home](#home) |
| `/FirefoxHome/SponsoredTopSites` | `false` | SponsoredTopSites is false. Map to the Android home surface and prove absence/default state independently. | [home](#home) |
| `/FirefoxHome/Highlights` | `false` | Highlights is false. This is ordinary home content; advertisement removal does not implement it. | [home](#home) |
| `/FirefoxHome/Stories` | `false` | Stories is false. Map to the Android home surface and prove absence/default state independently. | [home](#home) |
| `/FirefoxHome/SponsoredStories` | `false` | SponsoredStories is false. Map to the Android home surface and prove absence/default state independently. | [home](#home) |
| `/FirefoxSuggest/WebSuggestions` | `false` | Disable Firefox Suggest web results; ordinary search-engine query suggestions are a different setting. | [firefox-suggest](#firefox-suggest) |
| `/FirefoxSuggest/SponsoredSuggestions` | `false` | Disable sponsored Firefox Suggest results; home Contile removal is a different feed. | [firefox-suggest](#firefox-suggest) |
| `/FirefoxSuggest/ImproveSuggest` | `false` | Disable online Suggest improvement/collection (deprecated name maps to online.enabled on this source). | [firefox-suggest](#firefox-suggest) |
| `/HttpsOnlyMode` | `"enabled"` | Enable HTTPS-only by default, with user-controlled mode and exceptions. | [privacy-defaults](#privacy-defaults) |
| `/LocalNetworkAccess/Enabled` | `true` | network.lna.enabled=true | [lna](#lna) |
| `/LocalNetworkAccess/BlockTrackers` | `true` | network.lna.block_trackers=true; Android cfg uses a real lockPref. | [lna](#lna) |
| `/LocalNetworkAccess/EnablePrompting` | `true` | network.lna.blocking=true plus the actual Android local-network prompt flow. | [lna](#lna) |
| `/NoDefaultBookmarks` | `true` | Avoid inserting built-in bookmarks. | [default-bookmarks](#default-bookmarks) |
| `/OverridePostUpdatePage` | `""` | Do not automatically open a post-update promotional page. | [app-update](#app-update), [onboarding](#onboarding) |
| `/SkipTermsOfUse` | `true` | Skip terms-of-use prompts. | [onboarding](#onboarding) |
| `/SupportMenu/Title` | `"LibreWolf Issue Tracker"` | Provide a named LibreWolf Issue Tracker menu entry linking to Codeberg. | [support](#support) |
| `/SupportMenu/URL` | `"https://codeberg.org/librewolf/issues"` | Provide a named LibreWolf Issue Tracker menu entry linking to Codeberg. | [support](#support) |
| `/UserMessaging/UrlbarInterventions` | `false` | Suppress desktop URL-bar intervention messages; audit Fenix toolbar recommendations separately. | [remote-improvements](#remote-improvements), [support](#support) |
| `/UserMessaging/SkipOnboarding` | `true` | Suppress first-run/setup and continuous onboarding. | [onboarding](#onboarding) |
| `/UserMessaging/MoreFromMozilla` | `false` | Suppress Mozilla product marketing surfaces; desktop pane absence alone is not Android surface proof. | [remote-improvements](#remote-improvements), [support](#support) |
| `/UserMessaging/FirefoxLabs` | `false` | Suppress Labs UI/opt-in routes as well as experiment fetching; Gecko ExperimentAPI being off alone is not Android UI proof. | [remote-improvements](#remote-improvements), [support](#support) |

## Copied preference pane

| Control/dependency | Effect | Counterpart |
| --- | --- | --- |
| `librewolfExtensionUpdateEnabled` | Underlying extensions.update.enabled setting. | [addon-updates](#addon-updates) |
| `librewolfExtensionAutoUpdateEnabled` | Underlying extensions.update.autoUpdateDefault setting. | [addon-updates](#addon-updates) |
| `librewolfExtensionUpdate` | Combined checkbox reads logical AND and writes both update settings. | [addon-updates](#addon-updates) |
| `librewolfSync` | Enable/disable accounts and offer restart. | [sync](#sync) |
| `librewolfAutocopy` | Underlying clipboard.autocopy setting. | [platform](#platform) |
| `librewolfPaste` | Underlying middlemouse.paste setting. | [platform](#platform) |
| `librewolfMiddleClick` | Combined autocopy/paste AND checkbox writes both settings; desktop selection clipboard/input integration. | [platform](#platform) |
| `librewolfUserChrome` | Enable optional profile stylesheets for desktop chrome. | [profile-config](#profile-config), [platform](#platform) |
| `librewolfIPv6` | Display the inverse of network.dns.disableIPv6. | [network-controls](#network-controls) |
| `librewolfCrossOrigin` | Checked only for XOriginPolicy=2; write 2 when checked and 0 when unchecked. | [network-controls](#network-controls) |
| `librewolfRFP` | Enable/disable privacy.resistFingerprinting. | [rfp-controls](#rfp-controls) |
| `librewolfLetterboxing` | Optional privacy.resistFingerprinting.letterboxing switch. | [rfp-controls](#rfp-controls) |
| `librewolfWebGLPrompt` | Invert librewolf.webgl.prompt: allow globally versus require per-site decision. | [graphics](#graphics) |
| `librewolfWebGLPromptHide` | Set quiet permission notification; disabled when WebGL is globally allowed. | [graphics](#graphics) |
| `librewolf-config-link` | Open about:config in a new tab. | [profile-config](#profile-config) |
| `librewolf-open-profile` | Reveal ProfD in the desktop file manager. | [profile-config](#profile-config) |

All 15 active `Preferences.addAll` registrations are also listed in `coverage.json`. Five Safe Browsing registrations have no visible control in the copied pane; they are recorded as dormant registration, not as five missing UI switches. The four copied assets are individually pinned. CSS collapse/warning/icon styling and category SVG are desktop presentation; no Android enforcement is inferred from them.

## Counterparts and evidence

Status meanings: **source implemented, runtime open** means the cited code implements an effect but this audit has no runtime verdict; **mixed open** includes implementation plus missing/uncertain behavior; **open gap** requires implementation or a justified product/platform disposition; **desktop boundary** explains an OS/frontend integration and never certifies cross-platform behavior.

### platform

**Desktop boundary.** Android app.mozbuild includes toolkit, its branding directory, and mobile/android. It does not include the desktop browser frontend. D-Bus remote command routing, Windows MSIX/COM/EXE manifests, NSWorkspace relaunch, macOS Assets.car, GTK XDG profile migration, XUL toolbars, and desktop CSS therefore need platform treatment. This boundary does not dispose of cross-platform behavior such as permission decisions, settings or cleanup.

**Remaining:** Android intents, app identity, lifecycle, accessibility and private app storage must be checked as Android behavior; no desktop OS parity claim is made.

Inspected evidence:

- Archived source **android-build**: `mobile/android/app.mozbuild`; inspected line ranges and SHA-256 in [source index](source-index.md#android-build).
- Archived source **android-config**: `mobile/android/moz.configure`; inspected line ranges and SHA-256 in [source index](source-index.md#android-config).
- Archived source **app-manifest**: `mobile/android/fenix/app/src/main/AndroidManifest.xml`; inspected line ranges and SHA-256 in [source index](source-index.md#app-manifest).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### branding

**Source implemented, runtime open.** Android branding.patch sets the Redoubt application ID and app name and replaces Android launcher assets. Desktop SVG dimensions and XUL icon placement are not Android rendering inputs.

**Remaining:** Check all Android surfaces, release-channel names, icon variants and locale fallbacks. Desktop LibreWolf branding is not copied blindly to the authorized Redoubt product.

Inspected evidence:

- [patches/android/branding.patch](../../../../patches/android/branding.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- Archived source **app-manifest**: `mobile/android/fenix/app/src/main/AndroidManifest.xml`; inspected line ranges and SHA-256 in [source index](source-index.md#app-manifest).
- Archived source **android-build**: `mobile/android/app.mozbuild`; inspected line ranges and SHA-256 in [source index](source-index.md#android-build).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### telemetry

**Source implemented, runtime open.** Android MOZ_SERVICES_HEALTHREPORT and MOZ_NORMANDY are false. Android no-glean removes initialization/transport integration, and Analytics retains FirstSessionMetricsService rather than Glean upload services. CrashReporter uses an empty service list and Prompt.NEVER; no-adjust/no-gms remove their integrations. The presence of generated metric classes or a UI submit call alone is not evidence of upload, nor is a false pref alone evidence of absence.

**Remaining:** Final APK dependency/manifest inventory and negative network evidence on all relevant entry points remain required. This audit ran neither APK nor network tests.

Inspected evidence:

- Archived source **android-config**: `mobile/android/moz.configure`; inspected line ranges and SHA-256 in [source index](source-index.md#android-config).
- Archived source **analytics**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Analytics.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#analytics).
- [patches/android/disable-data-reporting-android.patch](../../../../patches/android/disable-data-reporting-android.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/disable-data-reporting-common.patch](../../../../patches/disable-data-reporting-common.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/android/no-glean.patch](../../../../patches/android/no-glean.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/android/no-adjust.patch](../../../../patches/android/no-adjust.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/android/no-gms.patch](../../../../patches/android/no-gms.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/android/no-crashreporter.patch](../../../../patches/android/no-crashreporter.patch) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### eme

**Mixed open.** settings/android.cfg supplies defaultPref(media.eme.enabled,false), the policy effect absent from common/desktop cfg. GeckoView routes media-key-system-access to PERMISSION_MEDIA_KEY_SYSTEM_ACCESS; Fenix PhoneFeature and SitePermissionsRules retain an ASK_TO_ALLOW path. The frozen generic GeckoView prompt writes EXPIRE_NEVER, so desktop private/session lifetime behavior must not be assumed from the type mapping. Common EME patches also gate Clear Key separately.

**Remaining:** Measure global default-off, user opt-in, actual DRM playback, deny, exact origin exceptions/revocation, and private/session lifetimes. A site permission row is not a global EME enable switch; the desktop global control still needs an Android counterpart or explicit usable pref control.

Inspected evidence:

- Archived source **settings-android.cfg**: `android.cfg`; inspected line ranges and SHA-256 in [source index](source-index.md#settings-androidcfg).
- Archived source **gv-permission**: `mobile/shared/components/geckoview/GeckoViewPermission.sys.mjs`; inspected line ranges and SHA-256 in [source index](source-index.md#gv-permission).
- Archived source **gv-session**: `mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoSession.java`; inspected line ranges and SHA-256 in [source index](source-index.md#gv-session).
- Archived source **phone-feature**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/PhoneFeature.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#phone-feature).
- Archived source **site-rules**: `mobile/android/android-components/components/feature/sitepermissions/src/main/java/mozilla/components/feature/sitepermissions/SitePermissionsRules.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#site-rules).
- [patches/eme-permission-common.patch](../../../../patches/eme-permission-common.patch) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### translations

**Mixed open.** Fenix already has a global translation feature switch and a separate Offer to translate switch. TranslationSettingsFragment calls translationsFeature.set and dispatches UpdateGlobalOfferTranslateSettingAction, persisting offerTranslation. TranslationsEnabledSettings stores is_enabled_key with default true; Core reads its first value before initializing TranslationsMiddleware. MenuDialogFragment routes Translate Page into the existing translation flow. Model/download/status UI presence does not repair the denied Remote Settings asset path.

**Remaining:** LW-M7-16 is separate work in progress at this snapshot: verified explicit asset download/cache and offline translation are not established here. Test global switch and offer switch separately across restart, menu availability, supported hardware/languages, cancel/delete, private mode and stale-document behavior. Desktop context-specific hiding is not identical to a mobile menu.

Inspected evidence:

- Archived source **translation-settings**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/translations/settings/TranslationSettingsFragment.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#translation-settings).
- Archived source **translation-store**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/translations/TranslationsEnabledSettings.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#translation-store).
- Archived source **core**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Core.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#core).
- Archived source **menu**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#menu).
- [patches/android/rs-blocker-android.patch](../../../../patches/android/rs-blocker-android.patch) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### password

**Mixed open.** privacy-defaults.patch changes Fenix password-save and login/card/address autofill defaults while preserving stored choices. The separate desktop librewolf.hidePasswdmgr option removes password menu/settings entries; the bounded Fenix/engine-gecko search has no reader for that option. Disabling saving does not implement hiding the manager.

**Remaining:** Implement or explicitly resolve the optional hide-manager behavior. Verify actual save/autofill off and opt-in behavior, UI consistency, stored choices and upgrade; old defaults persisted into XML keys cannot automatically be distinguished from explicit choices.

Inspected evidence:

- [patches/android/privacy-defaults.patch](../../../../patches/android/privacy-defaults.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- Archived source **settings-desktop.cfg**: `desktop.cfg`; inspected line ranges and SHA-256 in [source index](source-index.md#settings-desktopcfg).
- Bounded search **hide-password-control**, including pattern, scope, exit status, output and file input hashes, in [bounded-searches.json.gz](bounded-searches.json.gz).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### locale

**Open gap.** Desktop languages.patch adds ku to shipped-locales. Frozen Fenix resources contain values-ckb and no values-ku directory; these are distinct locale codes, so the Sorani resource does not prove the ku requirement.

**Remaining:** Determine and implement the correct Android ku/Kurmanji locale coverage and selection; verify UI resources and locale fallback on the APK. A resource-directory check alone cannot prove runtime locale completeness.

Inspected evidence:

- Bounded search **fenix-locales**, including pattern, scope, exit status, output and file input hashes, in [bounded-searches.json.gz](bounded-searches.json.gz).
- [scripts/librewolf-patches.py](../../../../scripts/librewolf-patches.py) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### link-preview

**Open gap.** Desktop link-preview.patch separates ordinary preview enablement from AI key-points eligibility. The bounded Fenix browser source search has no browser.ml.linkPreview or LinkPreview counterpart; Android context menus are a separate implementation.

**Remaining:** Inspect/implement an equivalent optional non-AI page preview where appropriate. Do not claim that disabling all ML delivers the positive preview feature, or infer absence throughout Android from this bounded search.

Inspected evidence:

- Bounded search **preview-control**, including pattern, scope, exit status, output and file input hashes, in [bounded-searches.json.gz](bounded-searches.json.gz).
- Archived source **android-build**: `mobile/android/app.mozbuild`; inspected line ranges and SHA-256 in [source index](source-index.md#android-build).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### graphics

**Open gap.** At the frozen source and audit base, webgl-prompt-default.patch deliberately defaults librewolf.webgl.prompt to false on Android because the old desktop observer/UI cannot answer Android requests. This preserves usable WebGL but does not implement desktop per-site protection. LW-M7-14 is concurrent implementation, not part of this pinned snapshot.

**Remaining:** Integrate and compile LW-M7-14, then measure canvas/WebGL protection before choice, actual Android prompt/quiet indicator, allow/deny, session/permanent/private lifetimes, exact-origin exceptions, revoke and real pixels after reload, including workers/iframes. Also provide global/quiet controls; a native permission constant is not sufficient.

Inspected evidence:

- [patches/android/webgl-prompt-default.patch](../../../../patches/android/webgl-prompt-default.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/webgl-permission-common.patch](../../../../patches/webgl-permission-common.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- Archived source **gv-permission**: `mobile/shared/components/geckoview/GeckoViewPermission.sys.mjs`; inspected line ranges and SHA-256 in [source index](source-index.md#gv-permission).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### app-update

**Source implemented, runtime open.** Android has no desktop updater UI/agent to relabel. update-check.patch adds an optional Android notification checker: off by default, hidden without its compiled public key, signature-verifies bounded metadata and opens a download only after a user action. It does not automatically install an APK.

**Remaining:** Test off-state network silence, enabled checks, bad signature and correct external release/download routes on the shipping configuration. This optional Android checker is distinct from the disabled Mozilla desktop updater.

Inspected evidence:

- [patches/android/update-check.patch](../../../../patches/android/update-check.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- Archived source **android-build**: `mobile/android/app.mozbuild`; inspected line ranges and SHA-256 in [source index](source-index.md#android-build).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### home

**Mixed open.** no-onboarding makes the Pocket recommendation/sponsored-story eligibility functions false; no-suggest removes the sponsored top-site feed and defaults search/trending suggestions off. But the frozen FML homescreen defaults still enable top-sites, jump-back-in, bookmarks and recent-explorations, and Fenix Settings reads them. Desktop FirefoxHome.TopSites=false and Highlights=false therefore have remaining ordinary-content counterparts. No Weather symbol was found in the bounded home Kotlin search.

**Remaining:** Resolve ordinary home sections/default shortcuts and Highlights equivalents, preserve user bookmarks/history rather than deleting them, and test fresh/restart/upgrade home. Weather absence is a bounded source observation, not a full APK proof. Recheck all advertisement/recommendation network paths.

Inspected evidence:

- Archived source **home-fml**: `mobile/android/fenix/app/nimbus.fml.yaml`; inspected line ranges and SHA-256 in [source index](source-index.md#home-fml).
- Archived source **settings**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#settings).
- Archived source **pocket**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/home/pocket/ContentRecommendationsFeatureHelper.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#pocket).
- [patches/android/no-onboarding.patch](../../../../patches/android/no-onboarding.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/android/no-suggest.patch](../../../../patches/android/no-suggest.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- Bounded search **weather-home**, including pattern, scope, exit status, output and file input hashes, in [bounded-searches.json.gz](bounded-searches.json.gz).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### extension-types

**Open gap.** Android enterprise-policy service is not compiled, so ExtensionSettings.allowed_types and blocked_install_message are not enforced merely by packaging policies.json. The bounded mobile search found no allowed_types/blocked_install_message or desktop-style locale-addon removal loop. Desktop remove-language-packs additionally uninstalls already-installed locale add-ons at startup.

**Remaining:** Trace all GeckoView/AMO/file/extension API install routes and implement exact allowed types and useful error handling. Cover existing locale add-ons at upgrade/startup separately from rejecting new installs; preserve dictionary, extension, sitepermission and theme choices where supported. Do not treat an AMO curated list as policy enforcement.

Inspected evidence:

- Archived source **policy-build**: `toolkit/components/enterprisepolicies/moz.build`; inspected line ranges and SHA-256 in [source index](source-index.md#policy-build).
- Bounded search **language-pack-removal**, including pattern, scope, exit status, output and file input hashes, in [bounded-searches.json.gz](bounded-searches.json.gz).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### ubo

**Source implemented, runtime open.** Current ubo-preinstall and ubo-readiness patches bundle a pinned signed uBO XPI, use ordinary AddonManager installation, provision private access initially, and gate engine-session creation on first installation and the real blocking listener. Durable state is designed to preserve user disabling/removal. This is the Android counterpart of normal_installed rather than a permanently forced built-in.

**Remaining:** Full first-navigation, private, disable/remove, update, crash/retry and install-entry matrix remains a runtime obligation. Root is running candidate checks separately; this source audit imports no live success claim. The desktop latest-XPI URL is deliberately represented by a pinned verified build input, with later user-managed extension updates.

Inspected evidence:

- [patches/android/ubo-preinstall.patch](../../../../patches/android/ubo-preinstall.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/android/ubo-readiness.patch](../../../../patches/android/ubo-readiness.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [scripts/fetch-ubo-extension.py](../../../../scripts/fetch-ubo-extension.py) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### cookie-exemption

**Open gap.** Desktop site panels store cookie ALLOW on the exact content principal with EXPIRE_NEVER and remove exactly that permission when toggled off. Fenix cleanup deletes COOKIES/AUTH_SESSIONS and DOM_STORAGES without a host argument. GeckoEngine routes unscoped clearData to GeckoViewStorageController, which calls Services.clearData.deleteData. This inspected path does not implement an exemption list. ETP exceptions and clearing site data are different actions.

**Remaining:** Add a site-data retention permission/control and ensure automatic cleanup respects it without broad host/subdomain grants. Test retained/nonretained cookies and storage across quit, restart, private sessions and upgrade. Existing explicit Clear all data semantics may differ from automatic cleanup and must be specified.

Inspected evidence:

- Archived source **cleanup**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/deletebrowsingdata/DeleteBrowsingDataController.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#cleanup).
- Archived source **gecko-engine**: `mobile/android/android-components/components/browser/engine-gecko/src/main/java/mozilla/components/browser/engine/gecko/GeckoEngine.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#gecko-engine).
- Archived source **gv-cleanup**: `mobile/shared/modules/geckoview/GeckoViewStorageController.sys.mjs`; inspected line ranges and SHA-256 in [source index](source-index.md#gv-cleanup).
- [patches/android/privacy-defaults.patch](../../../../patches/android/privacy-defaults.patch) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### onboarding

**Mixed open.** no-onboarding hard-disables first-run and continuous onboarding plus ToS prompts and recommendation scheduling. Desktop default-browser polling/UI is XUL; Android still offers a user-initiated system default-browser setting. The desktop patch removes even that preferences group, so exact UI matching is a conscious platform/product boundary, not automatically a pass.

**Remaining:** Verify no default-browser/ToS/setup/review prompts on fresh install and later days, and decide whether the explicit Android default-app affordance remains. Do not confuse no unsolicited prompt with removal of all default-browser controls.

Inspected evidence:

- [patches/android/no-onboarding.patch](../../../../patches/android/no-onboarding.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- Archived source **settings**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#settings).
- Archived source **app-manifest**: `mobile/android/fenix/app/src/main/AndroidManifest.xml`; inspected line ranges and SHA-256 in [source index](source-index.md#app-manifest).
- Archived source **android-build**: `mobile/android/app.mozbuild`; inspected line ranges and SHA-256 in [source index](source-index.md#android-build).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### neterror

**Source implemented, runtime open.** The Android neterror-jar patch packages warning.svg through the mobile toolkit manifest; common neterror code points to it. Android Fenix also supplies its own error documents, so packaging the SVG proves only resource availability.

**Remaining:** Exercise actual cert/network/HTTPS-only error pages and resources on the final APK; the desktop illustration is not assumed to be the visible Fenix page.

Inspected evidence:

- [patches/android/neterror-jar.patch](../../../../patches/android/neterror-jar.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/ui-patches/neterror-common.patch](../../../../patches/ui-patches/neterror-common.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- Archived source **error-pages**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/AppRequestInterceptor.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#error-pages).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### support

**Open gap.** Frozen AboutFragment links Whats New through SupportUtils.WHATS_NEW_URL (Mozilla Firefox Android notes) and Support via a Mozilla SUMO URL. These do not implement the shipped LibreWolf Issue Tracker SupportMenu or the desktop Visit the repositories label. The Android menu has a distinct WebCompatReporter route and cookie-banner reporting UI; bundled WebCompatFeature instead installs website compatibility interventions and must be preserved.

**Remaining:** Provide correct product support/repository/release-note routes and audit feedback/report affordances. Disabled Glean upload does not make a visible reporter truthful. Preserve compatibility interventions while handling the separate reporter, and inspect gating/reachability before deleting UI.

Inspected evidence:

- Archived source **about**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/about/AboutFragment.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#about).
- Archived source **support**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SupportUtils.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#support).
- Archived source **menu**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#menu).
- Archived source **more-menu**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/compose/MoreSettingsSubmenu.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#more-menu).
- Archived source **menu-state**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/store/MenuState.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#menu-state).
- Archived source **webcompat**: `mobile/android/android-components/components/feature/webcompat/src/main/java/mozilla/components/feature/webcompat/WebCompatFeature.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#webcompat).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### privacy-defaults

**Mixed open.** privacy-defaults.patch aligns Fenix HTTPS-only, Strict tracking protection, cookie/site-data+cache cleanup, DoH-off/provider catalog and password/autofill defaults, including settings XML and persisted-choice fallbacks. Standard/Custom remain deliberate choices in Android. This is broader than setting Gecko prefs but does not implement desktop strict-only UI literally.

**Remaining:** Test positive/negative browser behavior, settings transitions and restarts; preserve explicit choices and existing history. Cleanup on process death and exact retention exceptions are unimplemented/unproven. Ambiguous old persisted defaults need an explicit apply-defaults path or another justified migration design.

Inspected evidence:

- [patches/android/privacy-defaults.patch](../../../../patches/android/privacy-defaults.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- Archived source **cleanup**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/deletebrowsingdata/DeleteBrowsingDataController.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#cleanup).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### rfp-controls

**Mixed open.** common.cfg defaults privacy.resistFingerprinting true. Desktop letterboxing defaults false and is optional. The bounded Fenix search has no letterboxing pref reader/control, and a browser-window resizing implementation cannot be inferred from the pref. Desktop website appearance UI disables its chooser under RFP; Android theme code is a different frontend, so its effective page color scheme and opt-out controls need checking.

**Remaining:** Implement optional mobile letterboxing and accessible RFP controls as appropriate, then measure coherent viewport/screen/color scheme/timezone/language behavior across devices and opt-out/restart. A pref value alone cannot prove fingerprinting parity.

Inspected evidence:

- Archived source **settings-common.cfg**: `common.cfg`; inspected line ranges and SHA-256 in [source index](source-index.md#settings-commoncfg).
- Archived source **settings-desktop.cfg**: `desktop.cfg`; inspected line ranges and SHA-256 in [source index](source-index.md#settings-desktopcfg).
- Bounded search **mobile-specific-pane-controls**, including pattern, scope, exit status, output and file input hashes, in [bounded-searches.json.gz](bounded-searches.json.gz).
- Archived source **core**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Core.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#core).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### addon-updates

**Mixed open.** Fenix constructs DefaultAddonUpdater at 12-hour frequency, registers WorkManager periodic jobs and calls AddonManager.updateAddon -> GeckoEngine.updateWebExtension. GeckoViewWebExtension refreshes stale AddonRepository metadata first, then honors AddonManager.updateEnabled before checking/installing updates. This path does not consult autoUpdateDefault before install. Thus extensions.update.enabled is honored; saying both Gecko prefs are simply ignored would be wrong. The desktop combined checkbox writes both prefs.

**Remaining:** Add the Android combined control and align scheduler, metadata traffic and per-addon semantics; prove disabled means the intended network silence and enabled ordinary updates still work. Do not count the pref as an Android settings UI or assume the metadata request is prevented by the later updateEnabled guard.

Inspected evidence:

- Archived source **addon-scheduler**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Components.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#addon-scheduler).
- Archived source **addon-worker**: `mobile/android/android-components/components/feature/addons/src/main/java/mozilla/components/feature/addons/update/AddonUpdater.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#addon-worker).
- Archived source **addon-manager**: `mobile/android/android-components/components/feature/addons/src/main/java/mozilla/components/feature/addons/AddonManager.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#addon-manager).
- Archived source **gecko-engine**: `mobile/android/android-components/components/browser/engine-gecko/src/main/java/mozilla/components/browser/engine/gecko/GeckoEngine.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#gecko-engine).
- Archived source **gv-addons**: `mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs`; inspected line ranges and SHA-256 in [source index](source-index.md#gv-addons).
- Archived source **gecko-addon-manager**: `toolkit/mozapps/extensions/AddonManager.sys.mjs`; inspected line ranges and SHA-256 in [source index](source-index.md#gecko-addon-manager).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### sync

**Open gap.** Desktop librewolfSync writes identity.fxaccounts.enabled and requests a restart; desktop.cfg defaults it false. Frozen Fenix BackgroundServices creates FxaAccountManager and starts it when the lazy property is resolved. The bounded Fenix search has no reader of identity.fxaccounts.enabled. Turning off onboarding sign-in cards therefore does not gate the account component or established accounts. no-gms removes push, with polling behavior separate.

**Remaining:** Implement explicit Sync-off/opt-in behavior at actual Fenix component/network boundaries with safe logout/disable semantics. Test fresh, existing account, restart, disabled traffic, manual sync, send/receive tabs and polling limitations; do not erase user data to implement the default.

Inspected evidence:

- Archived source **settings-desktop.cfg**: `desktop.cfg`; inspected line ranges and SHA-256 in [source index](source-index.md#settings-desktopcfg).
- Archived source **sync**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/BackgroundServices.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#sync).
- Bounded search **mobile-specific-pane-controls**, including pattern, scope, exit status, output and file input hashes, in [bounded-searches.json.gz](bounded-searches.json.gz).
- [patches/android/no-gms.patch](../../../../patches/android/no-gms.patch) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### network-controls

**Open gap.** Desktop pane provides IPv6 enablement through network.dns.disableIPv6 inversion and a strict cross-origin referrer checkbox setting XOriginPolicy to 2 or 0. The bounded Fenix source search has no readers of those prefs. common.cfg supplies engine defaults, but a default is not a matching Android control. Safe Browsing pref registrations in the pane are largely leftover registrations, not a visible opt-in checkbox.

**Remaining:** Provide usable IPv6/referrer controls and verify network effects plus restarts. Audit locked/runtime-written preferences separately; an [ANDROID: LOCK] comment is not lockPref.

Inspected evidence:

- Archived source **settings-common.cfg**: `common.cfg`; inspected line ranges and SHA-256 in [source index](source-index.md#settings-commoncfg).
- Bounded search **mobile-specific-pane-controls**, including pattern, scope, exit status, output and file input hashes, in [bounded-searches.json.gz](bounded-searches.json.gz).
- [patches/pref-pane/librewolf.js](../../../../patches/pref-pane/librewolf.js) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### profile-config

**Mixed open.** Android about-config.patch forces GeckoProvider.aboutConfigEnabled(true), giving the release frontend its GeckoView config page. The desktop pane also exposes ProfD.reveal; Android app-private storage and an external file manager cannot be assumed to support this desktop action.

**Remaining:** Verify release about:config editing, locks and persistence; decide a safe Android profile/config export/access counterpart rather than claiming desktop reveal works. Optional desktop userChrome styling targets XUL; no equivalent Kotlin UI stylesheet feature is implemented.

Inspected evidence:

- [patches/android/about-config.patch](../../../../patches/android/about-config.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- Archived source **gecko-provider**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/gecko/GeckoProvider.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#gecko-provider).
- Archived source **app-manifest**: `mobile/android/fenix/app/src/main/AndroidManifest.xml`; inspected line ranges and SHA-256 in [source index](source-index.md#app-manifest).
- [patches/pref-pane/librewolf.js](../../../../patches/pref-pane/librewolf.js) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### ai

**Mixed open.** common.cfg disables browser.ml.enable and locks browser.ai.control.default to blocked, while policies.json separately allows translations. The shared remove-openai patch and asserted patcher deletion remove that integration. Android does not run the enterprise policy service, and Fenix has its own AI-controllable translation and summarization surfaces. A global blocked default cannot by itself prove the per-feature exception works or that all Kotlin features obey it.

**Remaining:** Verify every AIControls leaf: translations remains available via the verified offline path; PDF alt text, smart tab groups, link key points, chatbot and SmartWindow stay unavailable through all Android entry points. Separate unavailable desktop UI from equivalent Android positive/negative behavior.

Inspected evidence:

- Archived source **settings-common.cfg**: `common.cfg`; inspected line ranges and SHA-256 in [source index](source-index.md#settings-commoncfg).
- Archived source **policy-build**: `toolkit/components/enterprisepolicies/moz.build`; inspected line ranges and SHA-256 in [source index](source-index.md#policy-build).
- Archived source **translation-settings**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/translations/settings/TranslationSettingsFragment.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#translation-settings).
- Archived source **menu**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#menu).
- [patches/remove-openai.patch](../../../../patches/remove-openai.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [scripts/librewolf-patches.py](../../../../scripts/librewolf-patches.py) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### lna

**Source implemented, runtime open.** Static prefs network.lna.enabled and blocking are true. settings/android.cfg actually lockPrefs network.lna.block_trackers true (unlike the stale earlier prose in that file). GeckoSession maps local-network permission and Fenix PhoneFeature/SitePermissionsRules provide the Android permission path. This matches the three policy inputs in source.

**Remaining:** Measure local-network requests, tracker blocking, prompt/deny/allow, origin scope, private behavior, revocation and restarts. A permission enum and locked pref do not demonstrate the runtime request is guarded.

Inspected evidence:

- Archived source **static-prefs**: `modules/libpref/init/StaticPrefList.yaml`; inspected line ranges and SHA-256 in [source index](source-index.md#static-prefs).
- Archived source **settings-android.cfg**: `android.cfg`; inspected line ranges and SHA-256 in [source index](source-index.md#settings-androidcfg).
- Archived source **gv-session**: `mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoSession.java`; inspected line ranges and SHA-256 in [source index](source-index.md#gv-session).
- Archived source **phone-feature**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/PhoneFeature.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#phone-feature).
- Archived source **site-rules**: `mobile/android/android-components/components/feature/sitepermissions/src/main/java/mozilla/components/feature/sitepermissions/SitePermissionsRules.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#site-rules).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### remote-improvements

**Source implemented, runtime open.** Fenix NimbusSetup uses serverSettings=null, initialExperiments=null, setFetchEnabled(false), and no-op maybeFetchExperiments. no-nimbus-toolkit also makes Gecko ExperimentAPI Android initialization return false and enabled-state computation return without enabling features. Rust/JS Remote Settings blockers are separate from this experiment disablement.

**Remaining:** Test negative network/runtime experiment state in the final APK; static FML defaults still feed Android features and can be true. Firefox Labs UI and feedback controls require a separate reachability audit.

Inspected evidence:

- Archived source **nimbus**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/experiments/NimbusSetup.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#nimbus).
- [patches/android/no-nimbus.patch](../../../../patches/android/no-nimbus.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/android/no-nimbus-toolkit.patch](../../../../patches/android/no-nimbus-toolkit.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/android/rs-blocker-android.patch](../../../../patches/android/rs-blocker-android.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/rs-blocker.patch](../../../../patches/rs-blocker.patch) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### search

**Source implemented, runtime open.** Android search-config.patch forces the packaged configuration path, includes Mojeek/Startpage icon attachments in Rust, and the patcher copies/validates matching search dumps. rs-blocker-android retains local dump reads while denying network fetches. This provides the counterpart to desktop add-mojeek packaging.

**Remaining:** Verify final APK engine list/default/icon, actual searches and private/upgrade choices without remote configuration. Search suggestions off is distinct from Firefox Suggest web/sponsored data feeds.

Inspected evidence:

- [patches/android/search-config.patch](../../../../patches/android/search-config.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [scripts/librewolf-patches.py](../../../../scripts/librewolf-patches.py) — SHA-256 in `coverage.json` → `repository_evidence`.
- [assets/search-config-v2.json](../../../../assets/search-config-v2.json) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/android/rs-blocker-android.patch](../../../../patches/android/rs-blocker-android.patch) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### jxl

**Open gap.** settings-redesign adds an optional image.jxl.enabled control. Frozen toolkit/moz.configure enables MOZ_JXL unless disabled; image/moz.build includes the decoder only with that flag. StaticPrefList defines image.jxl.enabled only under MOZ_JXL and defaults it to IS_NIGHTLY_BUILD. The bounded Fenix search has no direct JXL setting.

**Remaining:** Confirm the actual release native configuration and decode a known JXL with opt-in enabled and default disabled as specified; implement a usable Android control. A compiled flag or pref existence alone is not actual image decoding.

Inspected evidence:

- Archived source **toolkit-config**: `toolkit/moz.configure`; inspected line ranges and SHA-256 in [source index](source-index.md#toolkit-config).
- Archived source **image-build**: `image/moz.build`; inspected line ranges and SHA-256 in [source index](source-index.md#image-build).
- Archived source **static-prefs**: `modules/libpref/init/StaticPrefList.yaml`; inspected line ranges and SHA-256 in [source index](source-index.md#static-prefs).
- Bounded search **mobile-specific-pane-controls**, including pattern, scope, exit status, output and file input hashes, in [bounded-searches.json.gz](bounded-searches.json.gz).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### policy-engine

**Desktop boundary.** toolkit/components/enterprisepolicies/moz.build omits EnterprisePolicies JS modules and components.conf on Android. Shipping the JSON does not enforce its keys. Effects must come from common engine config/patches or Fenix implementations; this map treats each leaf separately.

**Remaining:** No Android policy engine or generic policy enforcement is claimed. Keep autoconfig loading/locks and policy translation mechanisms distinct.

Inspected evidence:

- Archived source **policy-build**: `toolkit/components/enterprisepolicies/moz.build`; inspected line ranges and SHA-256 in [source index](source-index.md#policy-build).
- [patches/android/autoconfig-resource-fallback.patch](../../../../patches/android/autoconfig-resource-fallback.patch) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### firefox-suggest

**Mixed open.** Frozen Fenix FeatureFlags.FX_SUGGEST is true; its fx-suggest FML default is false for the release configuration but true for developer/nightly. Settings.enableFxSuggest, showSponsoredSuggestions and showNonSponsoredSuggestions are persisted independently from ordinary search suggestions. Android Remote Settings network is blocked, but local packaged results and stored preferences require separate evaluation. Desktop ImproveSuggest now maps to browser.urlbar.quicksuggest.online.enabled.

**Remaining:** Verify WebSuggestions, SponsoredSuggestions and ImproveSuggest/online collection separately in the final release APK and on upgrade. Do not equate no-suggest search-engine query defaults with Firefox Suggest policy enforcement.

Inspected evidence:

- Archived source **feature-flags**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FeatureFlags.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#feature-flags).
- Archived source **home-fml**: `mobile/android/fenix/app/nimbus.fml.yaml`; inspected line ranges and SHA-256 in [source index](source-index.md#home-fml).
- Archived source **settings**: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt`; inspected line ranges and SHA-256 in [source index](source-index.md#settings).
- Archived source **desktop-policy-effects**: `browser/components/enterprisepolicies/Policies.sys.mjs`; inspected line ranges and SHA-256 in [source index](source-index.md#desktop-policy-effects).
- [patches/android/no-suggest.patch](../../../../patches/android/no-suggest.patch) — SHA-256 in `coverage.json` → `repository_evidence`.
- [patches/android/rs-blocker-android.patch](../../../../patches/android/rs-blocker-android.patch) — SHA-256 in `coverage.json` → `repository_evidence`.

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### website-filter

**Desktop boundary.** The desktop WebsiteFilter helper checks exception patterns before blocking a matching URL. The shipped Block and Exceptions arrays contain the same https://localhost/* pattern, so these rules produce no effective website denial. Android omits this policy service and need not add a localhost ban to copy a no-op configuration.

**Remaining:** This inference concerns exactly the pinned policy values. Re-audit if either array changes; do not claim Android supports arbitrary WebsiteFilter policies.

Inspected evidence:

- Archived source **website-filter**: `browser/components/enterprisepolicies/helpers/WebsiteFilter.sys.mjs`; inspected line ranges and SHA-256 in [source index](source-index.md#website-filter).
- Archived source **desktop-policy-effects**: `browser/components/enterprisepolicies/Policies.sys.mjs`; inspected line ranges and SHA-256 in [source index](source-index.md#desktop-policy-effects).
- Archived source **settings-distribution/policies.json**: `distribution/policies.json`; inspected line ranges and SHA-256 in [source index](source-index.md#settings-distributionpoliciesjson).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.

### default-bookmarks

**Mixed open.** Desktop NoDefaultBookmarks disallows the defaultBookmarks feature. Android has a separate initial_shortcuts.json containing Google/Wikipedia and region-specific entries. Those are home shortcuts, not evidence of bookmark-database insertion. Android policy service is absent, and bookmark-seeding equivalence has not been established by the inspected files.

**Remaining:** Check a fresh bookmark database and startup seeding path. Keep NoDefaultBookmarks separate from the FirefoxHome.TopSites issue and preserve all user-created bookmarks.

Inspected evidence:

- Archived source **desktop-policy-effects**: `browser/components/enterprisepolicies/Policies.sys.mjs`; inspected line ranges and SHA-256 in [source index](source-index.md#desktop-policy-effects).
- Archived source **initial-shortcuts**: `mobile/android/fenix/app/src/main/res/raw/initial_shortcuts.json`; inspected line ranges and SHA-256 in [source index](source-index.md#initial-shortcuts).
- Archived source **policy-build**: `toolkit/components/enterprisepolicies/moz.build`; inspected line ranges and SHA-256 in [source index](source-index.md#policy-build).

Provenance: inspected code; behavioral interpretation is an inference from that code. No static check is presented as live evidence.
