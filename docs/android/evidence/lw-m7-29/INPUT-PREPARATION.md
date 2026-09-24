# LW-M7-29 — local Suggest input preparation

Prepared by `/root/coverage_map` on the Fedora host, from Task26 candidate
`558561d44351ac531fea31564ce1684e6b3be5e4`. This checkpoint is metadata/API
preparation. It does not install data, implement a downloader, compile native
code, or prove APK behavior. The parent subsequently authorized an explicit
selected-data download/import implementation; that requires a later scoped
candidate and separate execution evidence.

## Retained official inputs

`official/` contains exact responses from the production endpoint defined in
app-services' `RemoteSettingsServer::Prod`: service capabilities and metadata
plus complete records for `quicksuggest-amp` and `quicksuggest-other`. URLs,
fetch times, response headers, ETags, byte counts and SHA256 are retained in
`official/requests.json`. Both records requests returned one page without a
`Next-Page` header. The two complete record snapshots contain 218 and 151 rows.
The raw records response ETags are 1788890559407 and 1788319975333; collection
metadata modification times are different and are retained separately. Collection
signatures were retained as provenance; their cryptographic verification was
**not run**. HTTPS provenance and local SHA256 consistency are the claims here.

Official references: [AMP records](https://firefox.settings.services.mozilla.com/v1/buckets/main/collections/quicksuggest-amp/records),
[Other records](https://firefox.settings.services.mozilla.com/v1/buckets/main/collections/quicksuggest-other/records).
`fetch-metadata.py` is an explicit review-time utility requiring a new destination.
It is not a build or runtime step. It refuses redirects, unexpected hosts and
unbounded metadata responses. No attachment was fetched at this checkpoint.

`input-plan.json` retains every attachment URL/hash/size/filename plus the
proposed record-ID file key and sidecar for a conservative mobile type closure.
`plan-data.py` derives it solely from the retained snapshots:

| Input | Records | Attachment bytes |
| --- | ---: | ---: |
| AMP phone datasets | 5 | 10,990,312 |
| AMP icons | 208 | 3,262,601 |
| Wikipedia datasets | 21 | 68,035,027 |
| Other icons | 2 | 27,434 |
| Inline global configuration | 1 | 0 |
| Total | 237 | 82,315,374 |

This 78.5 MiB alternative is a size/coverage plan, **not** an automatic bulk APK
addition. All icons are a conservative type dependency set; exact references
inside the payloads have not yet been checked. The first proposed payload
inspection is German phone AMP (6,957 bytes) plus German Wikipedia (3,373,384
bytes), followed by only the referenced pinned icons. The generic RS blocker
remains unchanged throughout.

## Native packaging and applied API evidence

`source-pins.json` retains exact excerpts with whole-source and excerpt hashes.
`rs-scoped-pristine.tar.gz` and `rs-replay.json` independently reverse/replay the
current RS blocker and search-config patch over four API files. Their final
hashes equal the inspected frozen source. No new source patch is applied by
this checkpoint. This establishes the actually applied APIs, not compilation.

The two macro interfaces have different requirements:

* Collection registration consumes `dumps/main/<collection>.json`, parsed as
  `{data: [...], timestamp: u64}`, and a matching `<collection>.timestamp`.
* Attachment registration consumes an explicit macro key plus
  `dumps/main/attachments/<collection>/<key>` and `<key>.meta.json`.
  The real `get_attachment` caller uses **record.id**, despite nearby comments
  saying `Attachment::filename`. Sidecars have `{location, hash, size}`. Original
  attachment filenames remain provenance, not the package lookup key.
* The packaged read path compares the record's hash/size to the sidecar, but
  does not rehash embedded bytes before first returning them. A build packager
  must verify actual file bytes. Cached reads do verify both bytes and hash.
* Packaged data is used only for the production server and when its timestamp
  is newer than the cache. A full packaged snapshot replaces existing records.
  Import/upgrade design must not silently erase a usable downloaded dataset.
* Native default ingestion includes AMP, Wikipedia, AMO, Yelp and MDN; Yelp
  adds geo dependencies. Fenix's intended local providers are AMP/Wikipedia,
  so selected delivery must constrain ingestion accordingly. Both providers
  need their collection's icons, and every ingest also requires Other's inline
  global configuration. Metadata-only payload rows produce an attachment error
  behind the blocker and do not establish usable local suggestions.

The exported `remote_settings::RemoteSettingsClient` in `lib.rs` adapts the
internal generic client. Its `get_records` returns `Option`, converting internal
errors to `None`. The internal `client.rs` method returns `Result<Option<_>>`.
Suggest imports the exported wrapper; there is no missing-`?` defect here.

## Explicit selected-download implementation direction

The public Kotlin-facing client exposes reads, sync, reset and shutdown, with no
cache import method. Internal storage has record/attachment writers, but each
commits separately and record insertion merges same-URL rows. Calling those in
sequence is not atomic. Direct Kotlin SQLite writes would bypass native locking,
schema and validation and are excluded from the proposed implementation.

A narrow new native API can accept a pinned dataset ID and exactly its payload
and referenced icons. Native code must derive canonical metadata from the
packaged catalog, reject unknown IDs/duplicates/extra or missing attachments,
verify every byte count/hash before publishing, and commit all rows and bytes
for **one collection** in a single transaction. A failed transaction must retain
the previous usable dataset. Wikipedia language and sponsored phone-region
installs have separate explicit actions; two separate SQLite databases are not
represented as one atomic commit. The tiny global-configuration dependency must
be available offline even for AMP-only installs, without a newer baseline seed
overwriting cached Wikipedia data.

The UI should present language, sponsored region, availability and download
size. Choosing or enabling Suggest alone must not start a download. Only the
explicit Download action authorizes exact pinned CDN URLs; no metadata refresh,
redirect, credentials, query text, background retry or generic RS exception is
needed. Cancellation/admission checks must cover queued work, completed network
responses and native publication; a request already sent cannot be retracted.
A failed or partial download cannot be labeled installed. Ordinary search-engine
suggestions, bookmarks, history, custom search and home shortcuts remain outside
this path.

The current Fenix RS context uses `Locale.getDefault().toLanguageTag()` and
`.country`, and `phone`/`tablet` from screen size. It does not use a network region
lookup. AMP has US/GB/DE/IT/FR phone rows and no tablet row; Wikipedia has exact
locale lists. `de-CH` matches neither DE AMP nor Wikipedia's `de`/`de-DE` filter.
An explicit selection such as English data on a Swiss German device must either
be visibly unavailable or use a narrowly scoped explicit-selection context for
these pinned Suggest records. Merely importing it while retaining a mismatching
filter is an inert control. Inspect the app-selected locale separately from the
device/default locale before deciding selection defaults; the UI need not expose
filter/native implementation details.

## Required implementation and execution gates

Before code changes, extend Task29 ownership/dependencies and exact source paths.
The anticipated shared files are native `remote_settings/src/{lib,client,storage}.rs`,
Fenix/A-C ingestion and Search settings, and the extraction asset packager hook.
Root owns global patch-order/scope review. A small catalog can be staged into
native and Android assets with matching pins; selected payloads are downloaded
into the app cache, not embedded into each ABI.

The later test candidate must cover:

1. Catalog/asset staging: hashes, sizes, duplicate IDs, path traversal, wrong
   sidecar/file keys, missing graph members, schema incompatibility, accidental
   extra payload bundling, deterministic outputs and Android-only build inputs.
2. Real native import/cache reads: known good payload and icons; wrong digest,
   truncation, missing/duplicate/extra bytes; atomic rollback preserving old rows
   and attachments; a changed server; restart; catalog/cache upgrade behavior.
3. Actual native Suggest ingestion/query: first install into empty caches,
   real keyword positive controls for AMP and Wikipedia, decoded icons and
   global config, explicit provider constraints, unsupported locale behavior,
   and an explicit choice on a different device locale. Use the production
   pinned-input path, not only a mock RS record provider.
4. Admission/cancellation: off before construction, cancelled while queued,
   off during response/import, interrupted partial download, failed persistence,
   a retained installer reference, and process death. No scheduler or worker may
   turn an incomplete install into an implicit network retry.
5. Root target gates: affected Rust/Kotlin compilation and unit suites, then a
   source-bound APK UI/download/import/restart/off run with network positive and
   negative controls. The box executing these gates owns their result.

Run `python3 docs/android/evidence/lw-m7-29/check-input-plan.py` for the retained
metadata/API checks. It deliberately reports payload/import/ingest/runtime as
not executed. `verification.txt` records this checkpoint and board validation.
