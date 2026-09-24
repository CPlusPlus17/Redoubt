# Translation and cookie-banner data audit

2026-09-08; entry_audit agent. Read-only source, APK and official metadata
inspection; **no feature was implemented or exercised in a running browser by
this audit**. This is preparation for parity work, not a completed parity gate.
Only this delegated evidence file was written. The frozen beta tree, settings
submodule, guest and privacy-defaults patch were not changed.

## Findings that change the implementation plan

1. Translation runs through Gecko's **JavaScript** Remote Settings client. Its
   current code requests `translations-models-v2` and `translations-wasm-v2`,
   requires model major version **3** and Bergamot WASM major version **4**, and
   decompresses zstd assets before inference. The source's old collection dumps
   and the Rust client's packaged WASM are incompatible and are not the asset
   provider used by this path.
2. The JS blocker rejects `AttachmentDownloader.download()` before it reaches
   the normal cache/dump logic. Adding local model metadata alone cannot repair
   translation or guarantee offline reuse. A feature-specific, verified local
   asset path is needed unless that blocker is carefully redesigned.
3. The beta has the cookie-banner implementation and effective reject-only
   modes, but **no cookie-banner rules dump in its APK**. The source dump is
   explicitly excluded from mobile packaging and is not permitted by the local
   dump list. Cookie handling can be restored with a reviewed local snapshot
   without enabling background cookie-rule Remote Settings sync.
4. The existing cookie dump is dated 2024-09-05, but a full official endpoint
   read during this audit returned exactly the same 558 records. Fetching the
   current collection does not itself supply newer/broader rules.

The owner-approved E12 restriction remains a constraint: the seven network
allowlist entries stay unchanged and the Rust Remote Settings egress blocker
stays in force. An explicit language-asset download must be a separately scoped
user operation, not a temporary widening of a global collection preference.
Nothing here approves broader background sync. A new offline dump entry would
need to be recorded as such; a new candidate must not claim the old eleven-entry
local dump list remained unchanged if it was extended.

## Binding to the released beta payload

Inspected unsigned x86_64 candidate:

`librewolf-android-apk-153.0esr-1-beta-20260908/apk/fenix-x86_64-release-unsigned.apk`

SHA256 `5293ff6cffd3d2a56fbe8ac8c26a2cb936f628992d0fd16cf1ced8103bd5b08b`.
The inspected source is the immutable `librewolf-153.0esr-1-beta-20260908` tree.
All source paths below are relative to that tree unless explicitly identified
as repository paths.

Reading `assets/omni.ja` directly found these six settings entries:

```text
defaults/settings/blocklists/gfx.json
defaults/settings/last_modified.json
defaults/settings/main/doh-config.json
defaults/settings/main/doh-providers.json
defaults/settings/main/password-recipes.json
defaults/settings/security-state/onecrl.json
```

`modules/CookieBannerListService.sys.mjs`, both cookie-banner actors and
`chrome/toolkit/content/global/cookiebanners/CookieBannerRule.schema.json` are
packaged. No `cookie-banner-rules-list`, `translations-models*` or
`translations-wasm*` entry is present in this omni archive. This statement is
about Gecko resources; the separate Rust binary does contain its declared old
packaged WASM attachment.

The archived exact-candidate
[pref dump](../lw-m7-06/beta-audit-2026-09-08/final-candidate/prefs-all.json)
shows `browser.translations.enable=true`, automatic popup enabled, and test
mocks disabled. Cookie service normal/private modes are both `1`, detect-only
is false, and banner clicking, cookie injection, global rules and subframe
global rules are true. Thus the missing-data finding is independent of an
assumption that a default pref won Fenix startup.

## Real translation call and data path

| Step | Actual caller / effect |
| --- | --- |
| User presses Translate | `mobile/android/fenix/app/src/main/java/org/mozilla/fenix/translations/TranslationsDialogFragment.kt:314`: optional data-saver warning, then `TranslationsDialogAction.TranslateAction` |
| Fenix dispatches selected pair | `TranslationsDialogMiddleware.kt:76` under the same directory emits browser `TranslationsAction.TranslateAction` with selected source/target and `options=null` |
| Engine dispatch | `mobile/android/android-components/components/browser/state/src/main/java/mozilla/components/browser/state/engine/middleware/EngineDelegateMiddleware.kt:165` calls `requestTranslate` |
| Gecko bridge | `mobile/android/android-components/components/browser/engine-gecko/src/main/java/mozilla/components/browser/engine/gecko/GeckoEngineSession.kt:747` calls `geckoSession.sessionTranslation.translate` |
| Java to parent actor | `mobile/android/geckoview/src/main/java/org/mozilla/geckoview/TranslationsController.java:754`, then `mobile/shared/modules/geckoview/GeckoViewTranslations.sys.mjs:43`, calls the Translations actor's `translate(pair, false)` |
| Inference payload | `toolkit/components/translations/actors/TranslationsEngineParent.sys.mjs:46` handles `TranslationsEngine:RequestEnginePayload` using `TranslationsParent.getTranslationsEnginePayload()` |
| Metadata and assets | `toolkit/components/translations/actors/TranslationsParent.sys.mjs:1967,2497,2542,2643,2858,2987,3358`: two JS RS clients, compatible-record selection, WASM plus model payload loading |
| Local inference | `toolkit/components/translations/actors/TranslationsEngineChild.sys.mjs:34,189` obtains blobs and applies `DecompressionStream("zstd")`; the translation engine runs in its own content process |

`TranslationsUtils.mjs:39,47` chooses the two **v2 collection names**. Parent
constants at `:398,459,460` require WASM 4 and models 3. Current records use
`sourceLanguage`, `targetLanguage`, `architecture`, optional `variant`,
`version`, `fileType`, and an `attachment` with `location`, SHA256 `hash`, byte
`size`, filename and MIME type. They also carry decompressed hash and size.
The exact interfaces are in `toolkit/components/translations/translations.d.ts`.
Old dumps use `fromLang`/`toLang`, model versions 1/2 and uncompressed assets;
renaming those dumps to v2 would not make them compatible.

The model selector chooses the highest supported version per name and language
pair, checks the pivot relationships in debug builds, excludes lexical shortlist
files when the pref is false, and matches component versions to each model
(`TranslationsParent.sys.mjs:2643-2716`). A model needs `model` plus either
`vocab` or the `srcvocab`/`trgvocab` pair; `lex` is needed only when configured.
The beta's lexical-shortlist pref is false. Non-English pairs can require two
complete legs through English (`getTranslationsEnginePayload`). A downloadable
language selection must include the needed directions and pivots; one random
model file is not a working language pack.

The existing "downloadModel=false" Java option is not a sufficient network
boundary: it prechecks **model** download size before the normal translate call
(`TranslationsController.java:769`); WASM is fetched separately by the parent
payload builder. Fenix's ordinary Translate action currently passes null
options. The explicit language-download settings UI reaches
`GeckoViewTranslations.sys.mjs:186-261` and Parent `downloadLanguageFiles` /
`downloadAllFiles`; these must use the same verified asset path.

### Why the two blockers matter differently

Repository `patches/rs-blocker.patch` adds:

- `RemoteSettingsClient.sys.mjs:670`: a disallowed collection's sync returns
  before fetching its changes.
- `RemoteSettingsClient.sys.mjs:221`: attachment `download` throws before
  delegating to `Downloader`. That also prevents the normal cached result for
  these calls; offline success cannot be assumed just because a file exists.
- `SharedUtils.sys.mjs:40,109`: packaged JSON reads require the network list or
  the separate `allowedCollectionsFromDump` list.

`Attachments.sys.mjs` otherwise has local-cache/dump support and verifies the
attachment hash/size. Its `downloadAsBytes` obtains the attachment server base
URL through `Utils.baseAttachmentsURL`, then fetches `baseURL + location`.
Using that generic method as a supposed "direct user download" can still fetch
Remote Settings server information. A narrow alternative should use a pinned
complete URL and the existing integrity-checking primitives, with no discovery
request. `Attachments.sys.mjs:320` already exposes an offline-only `get(record)`
method, but it allows fallback to an older cache/dump record. If reused, compare
the returned record/hash/size against the compiled pin and reject any mismatch;
a successful fallback alone does not prove the requested asset was loaded.

Repository `patches/android/rs-blocker-android.patch` independently changes Rust
`third_party/application-services/components/remote_settings/src/service.rs`
`fetch_changes` to empty, `client.rs::sync` to no-op and `make_request` to error.
The Rust packaged collections at `client.rs:95` name old `translations-models`
and `translations-wasm`; its one packaged WASM is major 3. The actual Gecko JS
translation call graph above does **not** read this Rust client's attachments.
Unblocking Rust would both weaken E12 and fail to repair this JS path.

There are additional background entry points to avoid accidentally enabling:
metadata lookup for supported languages occurs before translating, and Parent
RS sync handlers (`:2325-2489`) can automatically replace previously downloaded
assets when records update. A global allowlist change or a generic downloader
bypass would enable more than the button the user just pressed.

### Practical translation implementation

Recommended shape, to be implemented and tested in a new task:

1. Add a build-reviewed, hash-pinned **v2 catalog** and a compatible bundled
   WASM 4 blob. Package both as Gecko resources in
   `toolkit/components/translations/jar.mn` (or a dedicated Android data
   manifest). Keep catalog origin/ETag, all source and attachment hashes, sizes,
   version constraints and licenses in repository provenance. Existing local
   WASM lookup at Parent `:2892` is a development shortcut; turn a production
   asset path into an explicit checked path rather than relying on a commented
   development line.
2. Add a narrow translations asset provider used by Parent metadata selection,
   `#getBergamotWasmBlob`, `getTranslationModelPayload`, and the model
   download/delete/status helpers. Serve catalog and bundled/cached files
   locally. Preserve model-version filtering and English-pivot selection.
   Do not run normal collection sync or RS attachment server discovery. Leave
   both RS blockers intact.
3. For an explicit Translate / Download language operation, authorize only the
   missing assets selected from that compiled catalog. Fetch pinned HTTPS
   attachment URLs with credentials omitted, verify compressed size and SHA256
   before atomic cache insertion, and reject unlisted IDs/URLs/versions. Bound
   redirects to the approved asset origin. Cancellation, navigation and process
   restart must not leave a global download permission. Include decompressed
   size limits before inference; the current child simply decompresses blobs.
4. Distinguish **using** cached models from authorizing downloads. Page detection,
   automatic offers and an existing automatic-translation setting must not
   silently grant new network downloads. Surface a user download action when
   files are missing. The existing Java precheck needs a real parent-side
   boundary or a trusted operation token propagated through the GeckoView
   event/engine-payload path. Do not use a temporary global preference.
5. Update the status/size/delete paths for the new cache so settings reflects
   actual usable complete models. Refresh catalogs only through a reviewed app
   release unless a separate explicit update design is approved. Offering only
   one language pair is a useful first test, not completion of language parity.

This design adds a bounded explicit asset transfer; it does not interpret E12 as
permission for translation collection polling. A fully offline APK with every
model is another possible policy-preserving design, but its package size must
be measured before presenting it as practical.

## Cookie-banner rules and a local snapshot

`toolkit/components/cookiebanners/CookieBannerListService.sys.mjs` constructs
`RemoteSettings("cookie-banner-rules-list")` at `:73`, imports `#rs.get()` at
`:108` and subscribes to sync. Its `#importRules` at `:217` creates
`nsICookieBannerRule` objects from `id`, `domains` (or legacy singular `domain`),
`cookies` and `click`, then calls `Services.cookieBanners.insertRule`.

The schema is
`toolkit/components/cookiebanners/schema/CookieBannerRule.schema.json`.
Cookie rules specify opt-out/opt-in name/value pairs with optional host, path,
expiry, secure/session/HTTP-only and SameSite attributes. Click rules specify
presence/hide/opt-out/opt-in CSS selectors and optional top/child/all context.
Empty domains identify global CMP rules. RS metadata adds `schema` and
`last_modified`, which the narrow rule schema does not accept as rule fields;
strip only known transport metadata before validating the rule structure.
Do not ship a giant value in `cookiebanners.listService.testRules`: that is a
user-branch test override with testing observers, not the production data path.

`nsCookieInjector.cpp:157-222` handles document network loads and obtains cookies
from the cookie-banner service. `CookieBannerChild.sys.mjs` detects the banner
and performs the selected click; Parent/service supplies applicable rules.
`nsCookieBannerService.cpp:748` uses opt-out cookies in mode 1 and only permits
opt-in fallback in mode 2. The beta's mode 1 deliberately does nothing when a
rule provides only acceptance. That is desired reject-only behavior, not a
missing-rejection defect.

The existing snapshot is `services/settings/dumps/main/cookie-banner-rules-list.json`:

- 262,208 bytes; SHA256
  `0ddab9560f17710fa1613825b1b8be0e190107dd679e2cd53c5a1822524958fd`.
- Dump wrapper `{data: [...], timestamp: 1725526980846}`; 558 records.
- 150 records have cookie opt-out actions, 207 have click opt-out actions (these
  sets overlap), 257 have neither; nine are global rules.
- `services/settings/dumps/main/moz.build:19-37` excludes the dump from mobile.
  Android's installer includes `defaults/settings` generally, so packaging the
  file in that directory is sufficient at the installer level; the build list
  must also include it.

Two bounded implementation choices preserve the network allowlist:

- **Existing dump path:** package the pinned snapshot for Android, explicitly add
  `main/cookie-banner-rules-list` to Android's **dump-only** list, and load with
  `syncIfEmpty:false` so missing/corrupt packaged data cannot initiate a fetch.
  Keep network sync blocked. Add an observable missing-data error and verify
  exact loaded records on a fresh and existing profile. This changes the local
  dump inventory, not the seven-entry network policy.
- **Literal allowlists unchanged:** add an Android packaged-resource branch in
  `CookieBannerListService`, load and validate the snapshot directly, and avoid
  constructing/subscribing to its RS client on that branch. Feed the validated
  rule objects through the existing import implementation. This costs a little
  more loader code but requires no settings-submodule/list changes.

Either path updates rules with the application release. A refresh tool must
pin the complete snapshot, validate unique IDs/schema/selectors/cookie fields,
record origin and content hashes, and fail the build on missing/wrong content.
Do not silently fetch whatever is current during the build. The runtime must
not substitute a new unaudited rule set or accept-all fallback.

## Official endpoint reads made for this audit

Read-only HTTPS requests on the host, not from the guest or installed app.
The browser tool could not open the query URLs; Python `urllib.request`
subsequently returned HTTP 200. These are metadata observations, **not** a
completed attachment/signature verification or a vendored data manifest.

- [WASM v2 record](https://firefox.settings.services.mozilla.com/v1/buckets/main/collections/translations-wasm-v2/records?_sort=-last_modified&_limit=1):
  ETag `1760455775494`, record `ce71828c-5e7a-4024-8f18-03064bf0b9f0`,
  version `4.0`, release `v0.6.0`, MPL-2.0. Compressed size 1,211,955 bytes,
  SHA256 `327fcfc7b7e9d95f6fa0844ebf899cfc05469872ef02d3aef5783182839a6255`;
  location `main-workspace/translations-wasm-v2/a76f9efe-b185-4a7f-9c3b-5f5d216d12e6.zst`.
  Decompressed size 4,960,506 and hash
  `f38ef807636a7c994afedaab7ff8ffe0d590d21897f05139f747b80fd7bbe926`.
- [Models v2 record](https://firefox.settings.services.mozilla.com/v1/buckets/main/collections/translations-models-v2/records?_sort=-last_modified&_limit=1):
  ETag `1788296808921`; newest returned record was `vocab.ruen.spm`, version
  `3.1`, `architecture=base-memory`, ru→en. This confirms the current format;
  one vocabulary record is not a complete usable model or a full catalog pin.
- [Full cookie collection](https://firefox.settings.services.mozilla.com/v1/buckets/main/collections/cookie-banner-rules-list/records?_limit=1000):
  ETag `1725526980846`, 558 records, no `Next-Page`. After sorting by record ID
  and JSON-encoding with sorted keys and separators `(',', ':')`, its bytes
  exactly matched the source dump's data array. Canonical SHA256:
  `ffd2c6142052af84b4d0d23e4d8ef5f3d6a8399f13f155417316677df7efe02e`.
  The timestamp is `2024-09-05T09:03:00.846Z`; both age and observed parity with
  the current upstream collection should be documented.

## Tests needed for an honest completion claim

Translation unit/integration starting points:
`toolkit/components/translations/tests/browser/browser_translations_actor_sync_models.js`,
`browser_translations_actor_sync_wasm.js`, `browser_translations_full_page.js`,
Fenix `TranslationsDialogMiddlewareTest.kt`, A-C `EngineDelegateMiddlewareTest.kt`
and `TranslationsMiddlewareTest.kt`, plus GeckoView `TranslationsTest.kt`.
The existing GeckoView test `setup` enables
`browser.translations.geckoview.enableAllTestMocks`; a passing mocked translation
is not evidence that real assets load or real text is translated.

Required new checks: packaged catalog/WASM hashes; complete direct and pivot
model sets; corrupted/truncated/wrong-version/missing assets fail closed;
unknown IDs and navigated-away or cancelled operations cannot download;
startup/page detection/offer/background sync cause no model/WASM network
transfer; one real user request produces translated DOM text using unmocked
assets; airplane/offline restart reuses the verified cache; deleting one model
makes that language unavailable until another explicit download. Record
request provenance without claiming hostnames alone prove the encrypted RS
collection.

Cookie tests start with
`toolkit/components/cookiebanners/test/unit/test_cookiebannerlistservice.js`
and browser tests `browser_cookieinjector.js`, `browser_bannerClicking.js`,
`browser_bannerClicking_globalRules.js`, `browser_bannerClicking_runContext.js`
and `browser_cookiebannerservice_domainPrefs.js`. Add packaged-loader tests
using the production snapshot path, fresh/old-profile handling, a missing or
corrupt file, and a spy asserting no cookie collection sync/download occurs.
For the built APK use a controlled supported banner and verify an actual
rejection callback or opt-out cookie, not merely a hidden banner (uBO can hide
one independently). Include an accept-only banner that must remain unaccepted,
a preexisting consent cookie, domain exceptions, normal/private modes and an
app restart. A controlled fixture proves the loader and action; at least one
current real supported banner is still needed before claiming useful coverage.

## Frozen source fingerprints

- `toolkit/components/translations/TranslationsUtils.mjs`: `6e562fcf24644205d1f31b5d4517fca54deda703b4ca4affc0f159a79e0a1125`
- `toolkit/components/translations/actors/TranslationsParent.sys.mjs`: `f4858ce0940f602a9faefc426557d58230ac28ed47f8f234d41e35bc494c70e6`
- `toolkit/components/translations/actors/TranslationsEngineChild.sys.mjs`: `c0bc0526cf92c96e166b714612fff57951012a37f02942961b822858e94b5ed2`
- `toolkit/components/cookiebanners/CookieBannerListService.sys.mjs`: `c034e4acb8519c759bcadabfdba32ae280eac3826e37c81d60b598a716cbe66b`
- `services/settings/RemoteSettingsClient.sys.mjs`: `608707a6f156311e9f103e5778d56d0a478d99dd1c94dd916d448aa7cff77b0c`
- `services/settings/SharedUtils.sys.mjs`: `9f3c7b333b4afb16afd3805671f4df7056b4a0d03e84ec1a2bbcf9fd1c23ea0f`
- `services/settings/dumps/main/moz.build`: `b3edb14729cf46562982bde0fcc3b4cc6d32d6b01d6157a27283a770093d0331`

## Separate control-consistency follow-up (reported to root)

A read-code and archived-pref mismatch also needs an independent control task:
`Settings.kt:1189` gives `shouldEnableGlobalPrivacyControl` a false fallback,
`tracking_protection_preferences.xml` declares false, and `Core.kt:194` sets
`globalPrivacyControlEnabled` from that Settings value. The fragment writes the
engine on a toggle. Nevertheless the exact beta's effective pref dump has
`privacy.globalprivacycontrol.enabled`, `.functionality.enabled` and
`.pbmode.enabled` all true. The common configuration supplies true defaults with `[ANDROID: LOCK]`
comments; those comments are annotations, not evidence that a runtime lock
exists. The reason the archived engine values disagree with the Kotlin fallback
is currently unverified. This is not proof that a displayed OFF switch works
or proof that an attempted write was ignored.

Keep the in-flight LW-M7-09 patch frozen. The next controls task should align
the default UI with the effective intended GPC state, then exercise OFF/ON and
restart in normal/private tabs against `navigator.globalPrivacyControl` and
actual `Sec-GPC` requests to a controlled server. Read actual pref value/branch/lock state
as part of diagnosing the discrepancy, without presupposing a locking fix.
Preserve explicit user choices. Similarly verify password/address/card autofill
opt-in against actual form behavior and the effective Gecko prefs; a writable
Kotlin property or UI checkmark is insufficient. These are open behavior
requirements, not fixes made by this audit.
