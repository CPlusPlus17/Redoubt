# Inspected source index — LW-M7-17

The source tree was `/home/mgysin/Documents/librewolf/librewolf-153.0esr-1-beta-20260908`. It is a frozen host input; its name is not a revision proof. Each retained file is independently SHA-256 pinned. It is not the final M7 APK source. New M7 changes are cited as repository patches separately.

Settings source commit: `2206f8d1e59c0a0c0f69ee3fe5121eb353426687`. Complete preserved files are in [inspected-source.tar.gz](inspected-source.tar.gz); [source-evidence.json](source-evidence.json) binds each file and the archive hash. Only the ranges below are claimed as inspected.

Read a preserved file without an installed SDK, device, guest or extracted source tree:

```sh
tar -xOf docs/android/evidence/lw-m7-17/inspected-source.tar.gz \
  android/mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs | nl -ba
```

### desktop-policy-effects

Path: `browser/components/enterprisepolicies/Policies.sys.mjs`
Archive member: `android/browser/components/enterprisepolicies/Policies.sys.mjs`
SHA-256: `dd147216996d87f6dd1aadb6f3b7d514b51052a0f288de4eade227439a983e9d`
Inspected ranges: `[[1044, 1062], [1460, 1482], [1820, 1849], [2121, 2175], [2204, 2226], [3365, 3376]]`

### website-filter

Path: `browser/components/enterprisepolicies/helpers/WebsiteFilter.sys.mjs`
Archive member: `android/browser/components/enterprisepolicies/helpers/WebsiteFilter.sys.mjs`
SHA-256: `28c434aff8ce0d57eb6d4c8e5815e3ae3f84a83c0b4cf96afee2107385d26229`
Inspected ranges: `[[1, 20], [160, 184]]`

### menu-state

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/store/MenuState.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/store/MenuState.kt`
SHA-256: `d0c111dc1982bd01ae8263ec330d5015347762f2df05a2b9aefb63b7f3cb58fe`
Inspected ranges: `[[1, 52]]`

### feature-flags

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FeatureFlags.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FeatureFlags.kt`
SHA-256: `d732ea5a07213c4c464bc1fa3b9d8c9b71c2d9535ea3168a1d45aa968c996008`
Inspected ranges: `[[20, 49]]`

### initial-shortcuts

Path: `mobile/android/fenix/app/src/main/res/raw/initial_shortcuts.json`
Archive member: `android/mobile/android/fenix/app/src/main/res/raw/initial_shortcuts.json`
SHA-256: `6843fce203c441b5e270e239ede3cd5493c6f26572206b51063a8f744c279c8f`
Inspected ranges: `[[1, 145]]`

### error-pages

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/AppRequestInterceptor.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/AppRequestInterceptor.kt`
SHA-256: `2e841f6d394f8fcdfb56b3550c16e415398508a43c99bdf96cf8bfea83f911ea`
Inspected ranges: `[[65, 102]]`

### gecko-addon-manager

Path: `toolkit/mozapps/extensions/AddonManager.sys.mjs`
Archive member: `android/toolkit/mozapps/extensions/AddonManager.sys.mjs`
SHA-256: `b0693d36b3b954fa456b5d8c3161623277955d1ea8ef0f1a9fec88870b42b3d6`
Inspected ranges: `[[20, 30], [719, 733], [1184, 1196], [3315, 3334]]`

### android-build

Path: `mobile/android/app.mozbuild`
Archive member: `android/mobile/android/app.mozbuild`
SHA-256: `551bb1dc82c336d6cf98e2871b1ecb0d5ad8a499f3a2280a5155ac63b2c547ae`
Inspected ranges: `[[1, 11]]`

### android-config

Path: `mobile/android/moz.configure`
Archive member: `android/mobile/android/moz.configure`
SHA-256: `19d3c801e1377768750606280f57e944f6b6019b99fbeea338cd19d5b48710a7`
Inspected ranges: `[[1, 140]]`

### devtools-build

Path: `devtools/moz.build`
Archive member: `android/devtools/moz.build`
SHA-256: `40a80ec1037cd883131581e9932b525996164d2d142957f57fcd4350acecf077`
Inspected ranges: `[[1, 28]]`

### toolkit-config

Path: `toolkit/moz.configure`
Archive member: `android/toolkit/moz.configure`
SHA-256: `39821307965197fbbcedfb83905623aa418f586170cdb0cdf02a86987c822cf0`
Inspected ranges: `[[32, 50], [876, 888]]`

### policy-build

Path: `toolkit/components/enterprisepolicies/moz.build`
Archive member: `android/toolkit/components/enterprisepolicies/moz.build`
SHA-256: `9221f8793df8dafb2ac63deaf1b247095b26794911c3e989cb7c0ee362100972`
Inspected ranges: `[[1, 40]]`

### gv-permission

Path: `mobile/shared/components/geckoview/GeckoViewPermission.sys.mjs`
Archive member: `android/mobile/shared/components/geckoview/GeckoViewPermission.sys.mjs`
SHA-256: `44199b91bf3e62a54b19c2dcf9c57f18141635c99f58dc8236b69fd5d0c2d35b`
Inspected ranges: `[[118, 220]]`

### gv-session

Path: `mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoSession.java`
Archive member: `android/mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoSession.java`
SHA-256: `9cceed3cb00afa603555f038593025dc157642c31ed903cf592f0feaf8fa03f1`
Inspected ranges: `[[7185, 7220], [7340, 7405]]`

### site-rules

Path: `mobile/android/android-components/components/feature/sitepermissions/src/main/java/mozilla/components/feature/sitepermissions/SitePermissionsRules.kt`
Archive member: `android/mobile/android/android-components/components/feature/sitepermissions/src/main/java/mozilla/components/feature/sitepermissions/SitePermissionsRules.kt`
SHA-256: `d06ec287c42291b0fbbc3bd6ac604368829158101a39f2d8999e9d6201c913e3`
Inspected ranges: `[[15, 140]]`

### phone-feature

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/PhoneFeature.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/PhoneFeature.kt`
SHA-256: `86f3c5f06f78c9d40102cc1d3b0bf84bffbc295090f27b8c77c37c62cedaa261`
Inspected ranges: `[[20, 175]]`

### translation-settings

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/translations/settings/TranslationSettingsFragment.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/translations/settings/TranslationSettingsFragment.kt`
SHA-256: `6eab896dc4ec40e13979e311c06c0d7bbd669a5834a3fc8bccc2247d3d985e48`
Inspected ranges: `[[65, 176]]`

### translation-store

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/translations/TranslationsEnabledSettings.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/translations/TranslationsEnabledSettings.kt`
SHA-256: `866b355d602dd3f6e67c2d96cfa156c779f1a3e9f021e0741b70f493cfe15abe`
Inspected ranges: `[[1, 69]]`

### core

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Core.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Core.kt`
SHA-256: `9a96b6ab9af9534f5b83c116e694b46e6492a514d0b93dc6cff40fc31ea53cb2`
Inspected ranges: `[[172, 220], [260, 289], [402, 445]]`

### settings

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt`
SHA-256: `9d8ee6393e3d23698600ff85c59b84300cf81979b7a696c02b3116e487e4c81f`
Inspected ranges: `[[180, 281], [1170, 1210], [1750, 1845], [2190, 2245], [2610, 2670]]`

### addon-scheduler

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Components.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Components.kt`
SHA-256: `c41c47a2d34ac740b59cc2a40a671a9a8314d4c16c76a2096fb7a7aa3e2642ac`
Inspected ranges: `[[215, 241]]`

### addon-worker

Path: `mobile/android/android-components/components/feature/addons/src/main/java/mozilla/components/feature/addons/update/AddonUpdater.kt`
Archive member: `android/mobile/android/android-components/components/feature/addons/src/main/java/mozilla/components/feature/addons/update/AddonUpdater.kt`
SHA-256: `a0dc44b85410c837ddac022036db4fad56489f46d1976c9ecfecf3b723cd6dbf`
Inspected ranges: `[[175, 213], [282, 310], [652, 710]]`

### addon-manager

Path: `mobile/android/android-components/components/feature/addons/src/main/java/mozilla/components/feature/addons/AddonManager.kt`
Archive member: `android/mobile/android/android-components/components/feature/addons/src/main/java/mozilla/components/feature/addons/AddonManager.kt`
SHA-256: `05a97557e33cdd957d6f63a1de6ad31681b7faaa4d612efc0e5df63dcc0be48b`
Inspected ranges: `[[440, 480]]`

### gecko-engine

Path: `mobile/android/android-components/components/browser/engine-gecko/src/main/java/mozilla/components/browser/engine/gecko/GeckoEngine.kt`
Archive member: `android/mobile/android/android-components/components/browser/engine-gecko/src/main/java/mozilla/components/browser/engine/gecko/GeckoEngine.kt`
SHA-256: `dda7f40702a5e1b6b420fa05812e5d06d418afff739da96252dc5ca0dda533a2`
Inspected ranges: `[[440, 480], [982, 1011]]`

### gv-addons

Path: `mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs`
Archive member: `android/mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs`
SHA-256: `1380237a5997b6dc88345d80ed86de60a502aae2ade893a5bda153a107559037`
Inspected ranges: `[[1078, 1160]]`

### sync

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/BackgroundServices.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/BackgroundServices.kt`
SHA-256: `a9421d2ff808aee2802ceb2e58ecbed2e7b5751ba9c16ea36d679009bf9d2bef`
Inspected ranges: `[[155, 254]]`

### cleanup

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/deletebrowsingdata/DeleteBrowsingDataController.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/deletebrowsingdata/DeleteBrowsingDataController.kt`
SHA-256: `7118f3dec0a6fb2692c051831e212ceb0bb7f2046f92761a5d95cf43ca9c2615`
Inspected ranges: `[[145, 242]]`

### gv-cleanup

Path: `mobile/shared/modules/geckoview/GeckoViewStorageController.sys.mjs`
Archive member: `android/mobile/shared/modules/geckoview/GeckoViewStorageController.sys.mjs`
SHA-256: `3203a5f639175e3255fb0e09d91e81b1750d821ef65bda61090ef3139df2488b`
Inspected ranges: `[[281, 315]]`

### support

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SupportUtils.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SupportUtils.kt`
SHA-256: `ea213cad88c32a75a8bc85f8a0de27c851a3b0a36a23d783fa229b5a9123f7cf`
Inspected ranges: `[[24, 48], [90, 128]]`

### about

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/about/AboutFragment.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/about/AboutFragment.kt`
SHA-256: `8fe848f7ab4279489236b92df63ed1f13ea11e270ecf10956ad5ae784f9452ec`
Inspected ranges: `[[185, 235]]`

### webcompat

Path: `mobile/android/android-components/components/feature/webcompat/src/main/java/mozilla/components/feature/webcompat/WebCompatFeature.kt`
Archive member: `android/mobile/android/android-components/components/feature/webcompat/src/main/java/mozilla/components/feature/webcompat/WebCompatFeature.kt`
SHA-256: `2ccaea57c5a9559b194992df50ebd5c73ee888206bd1c8fbf5449adf18be5f75`
Inspected ranges: `[[1, 40]]`

### menu

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt`
SHA-256: `c75e6b3b95d2003cdc1ea7d338dcc1d962686025272e156a6ab07a6e7667532c`
Inspected ranges: `[[270, 285], [535, 560], [785, 812]]`

### more-menu

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/compose/MoreSettingsSubmenu.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/compose/MoreSettingsSubmenu.kt`
SHA-256: `90be020c51f9d68c1e36b1347cf51c728177c297a629d015df0b9d33c273c304`
Inspected ranges: `[[30, 85], [170, 190], [280, 322]]`

### analytics

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Analytics.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Analytics.kt`
SHA-256: `eab5e34448c7fc8fbd877d924a904bc3c83aea409821d46c0c260a15e31d419a`
Inspected ranges: `[[35, 110]]`

### nimbus

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/experiments/NimbusSetup.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/experiments/NimbusSetup.kt`
SHA-256: `d94372386ffec450696d0e9223ff3ed11ec37226d191b3e759898ee715976d27`
Inspected ranges: `[[60, 78], [95, 125], [157, 174]]`

### home-fml

Path: `mobile/android/fenix/app/nimbus.fml.yaml`
Archive member: `android/mobile/android/fenix/app/nimbus.fml.yaml`
SHA-256: `500390a061e673d68a51baf9a423d0b79cca739e60619f9a72e12c1ce3e20614`
Inspected ranges: `[[35, 70], [372, 402], [409, 453]]`

### pocket

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/home/pocket/ContentRecommendationsFeatureHelper.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/home/pocket/ContentRecommendationsFeatureHelper.kt`
SHA-256: `4c8d44319b01b102cba5ad780a70b46ceecaa2cdff98d52ac2170b481c91b6a0`
Inspected ranges: `[[1, 49]]`

### static-prefs

Path: `modules/libpref/init/StaticPrefList.yaml`
Archive member: `android/modules/libpref/init/StaticPrefList.yaml`
SHA-256: `25bf43f4c96f87d3e95907fd1b1576052862df886d3147e8bb0c5b86e66e128e`
Inspected ranges: `[[8997, 9012], [15380, 15408]]`

### image-build

Path: `image/moz.build`
Archive member: `android/image/moz.build`
SHA-256: `dfb1ac6c6fa9f851c1333f783a738175a4fcd99002c471e216f95036db025c49`
Inspected ranges: `[[1, 14]]`

### gv-settings

Path: `mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoRuntimeSettings.java`
Archive member: `android/mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoRuntimeSettings.java`
SHA-256: `36bd655bd3fe97b7b334252f8428bd8fd4d1c5d2cc6e4df5125e775eca26a361`
Inspected ranges: `[[805, 820], [988, 1002]]`

### gecko-provider

Path: `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/gecko/GeckoProvider.kt`
Archive member: `android/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/gecko/GeckoProvider.kt`
SHA-256: `401426888e7f15cc0593a69a6360c54c5237ec49a99acf5ab758aa25a6aea3c1`
Inspected ranges: `[[118, 160]]`

### app-manifest

Path: `mobile/android/fenix/app/src/main/AndroidManifest.xml`
Archive member: `android/mobile/android/fenix/app/src/main/AndroidManifest.xml`
SHA-256: `c06bd894f09b353d373c65c3ffa734f8ef6e48a8829cf498bd98bbac15ae632e`
Inspected ranges: `[[1, 95]]`

### settings-common.cfg

Path: `common.cfg`
Archive member: `settings/common.cfg`
SHA-256: `6c275bcc554107b22a9f19ac821b73ba35882d6b3a7a550c37f72f2a537773a8`
Inspected ranges: `Relevant referenced preference and policy declarations; comments are not accepted as runtime proof.`

### settings-android.cfg

Path: `android.cfg`
Archive member: `settings/android.cfg`
SHA-256: `de7112285da87907f2b9674a5ffa90d731bb16148f7cbaad09bbea8b525a6c98`
Inspected ranges: `Relevant referenced preference and policy declarations; comments are not accepted as runtime proof.`

### settings-desktop.cfg

Path: `desktop.cfg`
Archive member: `settings/desktop.cfg`
SHA-256: `81f7221b6256fe2f1991b53d59cf1a0d965aa86f54bdc49548e084a51a392816`
Inspected ranges: `Relevant referenced preference and policy declarations; comments are not accepted as runtime proof.`

### settings-distribution/policies.json

Path: `distribution/policies.json`
Archive member: `settings/distribution/policies.json`
SHA-256: `e4367fd58f4f8c32fff1a9b329d53b692efe808dfc89f278f4d1349f1e59738f`
Inspected ranges: `Relevant referenced preference and policy declarations; comments are not accepted as runtime proof.`
