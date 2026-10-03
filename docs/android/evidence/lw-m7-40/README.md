# LW-M7-40 — disable-157-cloud-features.patch: build evidence

Produced 2026-10-02 on the build host, by one agent, in a scratch tree
(`work/harden/` next to the release-157 worktree): `librewolf-patches.py
157.0 1 --targets=android` at 4c0bf707 plus this patch, x86_64 only,
`MOZ_BUILD_DATE` 20261002160000, image `librewolf-android-build` plus the two
157 SDK pins of `assets/Dockerfile.android`.

## Compiled

`./mach gradle fenix:assembleRelease` passed `:fenix:compileReleaseKotlin`
(Kotlin 2.4, `-Werror`) and produced `fenix-x86_64-release.apk`
(sha256 `cf5cddc5ce502ab4…`). Not one diagnostic named a file this patch
touches.

The scratch tree is NOT a clean 157 build. Getting there needed four local
workarounds for defects that are not this patch's and are reported for their
owners; none touches a file this patch edits:

1. `librewolf-patches.py` stops twice before it applies a patch on 157:
   the Startpage search-icon record disagrees with its sidecar, and
   `android_brand_images()` expects 14 Fenix brand files 157 renamed. Both
   checks were bypassed in the scratch copy.
2. The checked-in UniFFI Kotlin bindings under
   `toolkit/components/uniffi-bindgen-gecko-js/android/` fail Kotlin 2.4's
   `-Werror` ("Expression is unused" on the bare `UniffiLib` references in
   `uniffiEnsureInitialized()`). Suppressed with `UNUSED_EXPRESSION` in the
   scratch tree.
3. `appservices-logins-addmany.patch` duplicates `addMany`, which 157's
   `DatabaseLoginsStorage.kt` already has ("Conflicting overloads"). The
   duplicate was removed in the scratch tree; the patch looks retirable.
4. `firefox-suggest-data.patch` calls Rust exports
   (`installPinnedSuggestData`, `PinnedSuggestAttachment`, …) that never reach
   Kotlin on 157: the bindings are pregenerated, not built. Its `mobile/`
   hunks were reverse-applied in the scratch tree. And
   `no-crashreporter.patch`'s bare `Unit` in
   `PrivacyPreferencesRepository.kt:76` is "Expression is unused" under
   `-Werror`; deleted in the scratch tree.

Also: GNU patch leaves `.orig` files where a patch applies with an offset, and
`packageReleaseResources` rejects `values/strings.xml.orig`; and
`scripts/android-apk.sh` checks `dist/fat-aar/output/jni/`, which 157 moved
to `dist/fat-aar/output/geckoview/jni/`.

## Tests

`./mach gradle fenix:testDebugUnitTest` restricted to the classes this patch
touches or whose subject it changes: 22 classes, 321 tests, 0 failures, 0
errors (`unit-tests.json`, JUnit timestamps included). That includes
`LibreWolfCloudFeaturesTest` (4), `HomeDeepLinkIntentProcessorTest` (30),
`ShortcutsMiddlewareTest`, `TopSiteStateTest`, `SearchEngineFragmentTest`,
`SearchWidgetProviderTest`, `SettingsTest` (125), every
`org.mozilla.fenix.ipprotection` / `components.ipprotection` class and
`FenixApplicationTest`. The full suite and `board.py --check-fenix-tests`
were NOT run: on the scratch tree its result would mix this patch with the
workarounds above.
