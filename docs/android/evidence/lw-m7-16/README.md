# LW-M7-16: pinned translation assets and explicit downloads

Implementation handoff, 2026-09-09. Repository base: `c8f8e41`. The frozen
`librewolf-153.0esr-1-beta-20260908` source is read-only and supplied the original
files. **The patch has not yet been compiled or run in the Android APK.** The
source tests below do not mark the task or translation parity complete.

## Implemented boundary

Android uses a packaged catalog and WASM plus an app-private, verified model
cache. It does not construct translation Remote Settings clients, subscribe to
their sync events, discover an attachment server, or change either collection
allowlist or generic JS/Rust blocker. Desktop retains its Remote Settings path.

The adapter's `attachments.download()` is intentionally **cache-only**. Metadata,
supported-language discovery, size/status, automatic translation and inference
payload requests cannot grant network access. Only the explicit native Translate
and language Download commands create operations. An operation is sealed to its
selected, catalog-listed record set and expires on completion, cancellation,
timeout or shutdown. No preference, persistent token or global allow flag grants
downloads to other requests. Catalog updates require a reviewed application
release; neither builds nor installed apps refresh it from the network.

Downloads use exact pinned HTTPS URLs, omit credentials/referrers, bypass the
ambient HTTP cache, reject redirects and verify compressed size/hash. Streams
are bounded by the individual pin and absolute limits (48 MiB compressed,
64 MiB expanded). Expanded size/hash is checked before an atomic cache commit
and again at the real inference-child boundary. Cache reads/status rehash the
compressed bytes; they do not repeatedly decompress all installed languages.
Transfers are serialized to bound memory. Each transfer has a 60-second timeout;
the whole explicit operation has a 15-minute timeout. Failures use existing
translation error callbacks.

Actor identity and current WindowGlobal are checked before preparation and
before network/cache operations. Pagehide, actor destruction, module disable
and native cancellation abort the operation. Delete cancels overlapping or
not-yet-selected operations; Delete All cancels all outstanding model downloads.
Mutations are serialized. Temporary files are removed on error/cancellation;
a failed post-move document check rolls back its committed entry even before
AbortSignal delivery. Cancellation before a second writer commits preserves a
previously valid cache. Abrupt process death can leave an unused temporary file;
it is never a cache entry and Delete All removes it. No download authorization
survives process restart. The cache contains model assets, not translated pages.

## Inputs and provenance

[assets/translations/provenance.json](../../../../assets/translations/provenance.json)
records source URLs, raw-response sizes/hashes/headers, catalog and WASM pins.
The two complete upstream JSON responses and receipts are retained here.

| Input | Pin / observed inventory |
| --- | --- |
| Canonical catalog | 245592 bytes; SHA256 `ce8c163e97d9d5b136cd673f7e63684dada00b45514442bf282b387174100d96` |
| Models v2 | 377 records; ETag `1788296808921`; no next page |
| WASM v2 | One record, version 4.0 / release v0.6.0; ETag `1760455775494` |
| Bundled compressed WASM | 1211955 bytes; SHA256 `327fcfc7b7e9d95f6fa0844ebf899cfc05469872ef02d3aef5783182839a6255` |
| Expanded WASM | 4960506 bytes; SHA256 `f38ef807636a7c994afedaab7ff8ffe0d590d21897f05139f747b80fd7bbe926` |

Sources: [complete models collection](https://firefox.settings.services.mozilla.com/v1/buckets/main/collections/translations-models-v2/records?_limit=1000),
[complete WASM collection](https://firefox.settings.services.mozilla.com/v1/buckets/main/collections/translations-wasm-v2/records?_limit=1000),
and [pinned WASM attachment](https://firefox-settings-attachments.cdn.mozilla.net/main-workspace/translations-wasm-v2/a76f9efe-b185-4a7f-9c3b-5f5d216d12e6.zst).
These were explicit host audit downloads, not traffic from the guest/app.
The WASM record declares MPL-2.0. Mozilla also explicitly confirmed
[MPL-2.0 for generation 3 model weights](https://github.com/mozilla/translations/issues/1434#issuecomment-4734030816);
the model records themselves have no license field. The pinned WASM's source
revision is `1de4a085d3a7afb625c51a60aabb5ad298e4059f`. The frozen glue records
v0.6.0 at `eea6e5a80aa4ddd86d9cc35ce9a65b79aa3ab96d`; real host instantiation
and BlockingService construction with that glue pass. Android inference remains
a separate compatibility gate. No new Remote Settings signature verification is
claimed by the HTTPS/size/hash audit.

The catalog keeps all records and preserves its four exact targeting cases:
unconditional, Android-only, non-Android, and default/nightly channel. Unknown
targeting is rejected. Android release eligibility yields 347 records; the
existing Parent version/model/lex selection yields **217 records, 106 complete
directional pairs, 54 source and 54 target languages**, including English.
This retains the original Parent English-pivot algorithm, including its treatment
of non-English requests; it does not introduce a new direct-route solver.

Only the WASM is bundled as an engine asset. Models download on explicit use.
The 318635-byte Vietnamese vocabulary fixture archived here was also verified
against compressed and expanded pins and is used by the actual-source tests.
It is not staged into the APK. Other model attachments have catalog pins but
were not all downloaded during this work; one vocabulary file is not a working
translation model. Real direct and pivot translations remain required.

## Caller trace and controls

| Entry point | Behavior after this patch |
| --- | --- |
| Fenix `TranslationsDialogFragment` → `TranslationsDialogMiddleware` → browser `TranslateAction` → `EngineDelegateMiddleware.requestTranslate` | Explicit native Translate request |
| `SessionUseCases.TranslateUseCase` | Alternate explicit embedder request; source search found no passive Fenix caller |
| `TranslationsController.SessionTranslation.translate` | Private UUID and explicit `allowDownload`; false is enforced inside Parent, eliminating the separate size-check race; GeckoResult cancellation targets that UUID |
| `GeckoViewTranslations` Translate | Binds request to its actual actor and calls `translateFromUser`; omitted/non-true download permission remains cache-only |
| Parent automatic/reload/detection flow | Calls the original `translate()`; never enters the explicit prefetch wrapper |
| Fenix download item/dialog → `ManageLanguageModelsAction` → runtime accessor → native ManageModel | Explicit language/all operation; existing error/status/delete flows retained, cancellation uses the existing event with a private cancellation ID |
| Opening translation/download settings | Metadata/status only; no operation created |
| `TranslationsUtils.deleteAllLanguageFiles` | Android provider deletion, avoiding its former independently constructed RS client |
| Engine payload and `about:translations` engine use | Verified local assets only; no new download authorization through an engine payload request |

Internal `about:translations` therefore needs models already downloaded through
the explicit Fenix controls. Its distinct user-input download flow is not newly
implemented here and must not be described as full internal-page UI parity.

The existing Fenix settings already contain both translation controls:
`TranslationSettingsFragment.kt:102` calls `translationsFeature.set(enabled)`;
its persisted DataStore defaults true. `TranslationsMiddleware.kt:1076` calls
`engine.aiFeatures.setFeatureEnablement("translations", enabled)`.
The Offer to translate switch (`TranslationSettingsFragment.kt:134–150`) writes
`Settings.offerTranslation` and dispatches `UpdateGlobalOfferTranslateSettingAction`;
the middleware calls `engine.setTranslationsOfferPopup`, and GeckoEngine assigns
`runtime.settings.translationsOfferPopup`. Both effective toggles and restart
behavior remain APK tests; this is source wiring evidence only.

## Verification and integration

[replay-verification.log](replay-verification.log): **6 packaging tests and
45 actual-source tests pass**. The latter execute the provider, full patched
Parent, GeckoView module, child actors, real zstd decoding, and frozen Bergamot
glue/WASM. Native/browser/I/O boundaries are mocked. They cover corrupt inputs,
URL/redirect/bounds rejection, eligible catalog and complete selected pairs,
cache-only paths, direct/pivot selection, cancellation/deletion/concurrency,
stale documents, post-move rollback and retained desktop RS behavior.
[ubo-packaging-regression.log](ubo-packaging-regression.log): all 22 existing
uBO packaging tests still pass after the shared patcher change.

[source-files.json](source-files.json) and [source-baseline.tar.gz](source-baseline.tar.gz)
pin 15 original/result source dependencies: 13 changed files and two unchanged
Bergamot compatibility-test inputs. No production test-only API was added.
The patcher stages only verified checked-in assets; Android-only Makefile
prerequisites include those inputs, and a real Make variable check proves
desktop's added prerequisite set is empty.

```sh
python3 scripts/tests/test-translation-assets.py
python3 scripts/tests/test-translation-assets.py --source /path/to/patched/gecko
python3 scripts/tests/test-translation-assets.py --apk /path/to/new-candidate.apk
```

Replay requires Python 3, Make, patch, zstd and Node with `createZstdDecompress`
(this run used Node v26.8.1). The default reconstructs archived originals,
applies the patch with zero fuzz/no offsets, verifies result hashes, stages
assets offline, syntax-checks JS and runs the source tests. `--apk` additionally
compares actual packaged catalog/WASM/production modules and prints APK SHA256;
it has **not** yet been run against a new APK.

[integration-checks.json](integration-checks.json) records passing board, order,
scope lint and immutable-source dry-run checks. The root-owned PATCH-SCOPE count
update remains pending: this isolated checkout adds one Android patch (29→30,
89→90 total); root must calculate combined counts after integrating cookie and
other work. No existing patch shares a changed Gecko source file. New target
xpcshell and unmocked GeckoView cache-only tests are authored and syntax/source
reviewed, but not executed in their target environments.

Before completion: compile/package in the VM; run target xpcshell/GeckoView and
required full application gates; verify exact APK assets; use real unmocked
Fenix controls to translate direct and pivot pages and assert changed DOM text;
restart offline and reuse models; exercise cancel, delete, failure/retry,
normal/private navigation, feature/offer toggles and existing profiles. Capture
passive startup/detection/settings with no asset transfer, then a deliberate
download plus an allowed network control. A shared Mozilla hostname alone
cannot distinguish allowed security Remote Settings from forbidden collection
traffic. No signing, version advance, guest mutation or publication occurred.
