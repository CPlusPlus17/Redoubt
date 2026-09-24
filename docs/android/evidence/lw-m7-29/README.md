# LW-M7-29 — explicitly installed local Firefox Suggest data

Host source candidate by `/root/coverage_map`, reviewed independently by
`/root/entry_audit`. This implements an explicit language/phone-region download
and atomic native cache import on top of Task26's default-off controls. It has
**not compiled or run on Android**. The task remains pending target compilation,
Rust/Kotlin tests and source-bound APK acceptance. Host replay and asset checks
are reported separately in `implementation-verification.txt`.

## User-visible behavior implemented in source

Search settings has Web suggestion data and Sponsored suggestion data actions.
With Suggest and the corresponding leaf enabled, regular browsing offers 21
Wikipedia language choices and five sponsored phone regions: France, Germany,
Italy, United Kingdom and United States. Sponsored data is visibly unavailable
on tablets. Choosing a dataset shows its language/region and exact total download
size. Only the separate **Download** button starts traffic; changing a switch,
opening settings or waking a worker does not download these datasets.

Each action downloads the chosen pinned payload and its exact icons from
Mozilla's attachment CDN. No metadata refresh, redirects, cookies, referrer,
search query, background retry or automatic dataset update is added. The largest
choice is 8,213,442 bytes. The generic RS network blocker and existing Task26
admission rules remain in place. Ordinary query suggestions, local history,
bookmarks, custom search and home shortcuts are outside this patch.

The language/region choice applies even when the browser locale differs. The
actual Fenix `LocaleManager.updateResources` sets `Locale.setDefault` from the
saved app locale or system fallback. Consequently RS `Locale.getDefault()` is
not necessarily the device language. The UI uses that explicit app-language
API as a selection hint, and the native importer removes targeting only from
copies of the exact selected catalog records. It does not change global RS
context. An English selection on `de-CH` therefore remains eligible for local
ingestion. The original official targeting is retained in the catalog.

## Data, source and packaging evidence

* `source-files.json` pins the scoped pristine archive, three predecessors,
  before/after hashes, 17 source-patch files and 13 generated files. Replay uses
  the actual Android RS blocker, search-config and Task26 policy patch.
* `assets/firefox-suggest/catalog.json` is 52,962 bytes, SHA256
  `4960be774112710a938ec47bfea0588697dd35de445aea909be675595ae503aa`.
  It contains 26 exact official primary records, 67 referenced icon records,
  inline global configuration and official collection timestamps.
* `payload-inspection.json` retains host fetch/hash/field/icon-reference receipts
  for all 26 selected payloads; `icon-inspection.json` retains the 67 icon byte
  checks. `check-catalog-review.py` matches every catalog record back to the
  retained official snapshot and all graph/hash/size receipts. Those receipts
  are historical observations, not retained copies of all payloads.
* Seven compressed **test-only** files retain English Wikipedia, German phone
  AMP and their five icons. Their compressed and decompressed pins are checked
  before staging. Rust test modules use those real bytes; they are not production
  attachment assets. PNG/JPEG magic was inspected; Android decoding is pending.
* `scripts/package-firefox-suggest.py` performs no network operations. It stages
  the same catalog into native and Fenix assets, empty AMP/config-only Other
  baseline seeds and native test fixtures. All inputs are validated before
  writing. Makefile extraction dependencies and the Android-only patcher hook
  invoke this actual packager. The 78.5 MiB conservative closure remains a plan
  in `INPUT-PREPARATION.md`; it is not bundled per ABI.
* `implementation-sources.json` pins inspected locale/fetch API excerpts.
  `source-pins.json`, `official/`, `rs-replay.json` and `INPUT-PREPARATION.md`
  retain the earlier metadata/API checkpoint. Official signatures were retained
  but not cryptographically verified; HTTPS provenance and byte pins are the
  claims made here.

## Native publication and lifecycle

The exported native import API accepts a dataset ID and byte arrays, not caller
records or URLs. Native code derives canonical metadata from the compiled
catalog, rejects unknown/duplicate/extra/missing input, and checks every actual
size and SHA256. Records, attachments and the official metadata timestamp replace
one collection in one SQLite transaction. The two provider collections use
separate databases; the UI does not imply a cross-collection atomic operation.
Previously usable records and bytes survive validation, insertion and COMMIT
failure. Successful replacement deliberately replaces that type's prior data.

A one-use native token arbitrates cancellation versus publication. Cancellation
that wins before COMMIT publication rolls back. Once publication has begun,
`cancel()` returns false and no rollback is promised. A request already sent may
finish; the fetch API does not expose an in-flight request handle before its
response exists. The UI closes an available response stream, bounds connection
and read time, rejects late results and prevents later requests/import. Stream
close failure cannot bypass token cancellation. Navigating away or changing a
Task26 admission generation cancels the attempt, with no implicit retry. A
cancelled coroutine remains owned until its blocking cleanup finishes, preventing
an old finalizer from overwriting a new attempt's UI state.

Config changes have an issued/applied generation fence, including the interval
where a reader has taken a pending config but not yet acquired the inner lock.
Older config applications cannot restore an older server. **All existing caches
for the two Suggest collections** are retained across config changes, including
older catalog installs; this is broader than retaining only current pinned data.
Other RS collection reset behavior stays in place. Existing collection-URL
scoping and the exact production-main import check prevent stage/custom reads
of the production cache. Retention also prevents another client sharing the
collection database from clearing a freshly installed dataset.

Status reports a current pinned install only after matching canonical records,
metadata timestamp and every cached attachment hash/size. It does not claim
that Suggest indexing succeeded merely because the RS cache is complete. Import
is followed by actual local Suggest ingestion; a later ingestion error has a
separate message saying verified data was saved but preparation failed. Native
AMP/Wikipedia provider constraints exclude unrelated AMO/Yelp/MDN dependencies.

## Upgrade and availability limits

The two packaged seed timestamps are deliberately zero, not fabricated official
revision numbers. Any successful positive-timestamp import wins over these seeds
on restart or a new APK. There is no background update path. Existing valid data
from an older catalog remains usable, while the current-catalog status check may
return no current match; it does not label an incomplete new install as complete.
A cached seed/global configuration is also not automatically refreshed by another
zero seed. An explicit new installation replaces that collection/configuration.

Data availability is release-pinned to the 21 Wikipedia language choices and
five phone regions above. The code accepts explicitly selected data outside its
original locale filter, but this does not create new language or tablet content.
Future official CDN retention and compatibility are not guaranteed: unavailable
or changed bytes fail without replacing a previously usable dataset.

## Executed and pending gates

Host checks are reproducible without the frozen tree or network:

```sh
python3 docs/android/evidence/lw-m7-29/check-input-plan.py
python3 docs/android/evidence/lw-m7-29/check-source.py
python3 docs/android/evidence/lw-m7-29/check-catalog-review.py
python3 docs/android/evidence/lw-m7-29/check-ordering.py
python3 scripts/tests/test-firefox-suggest-assets.py
python3 docs/android/board.py --check
```

The real Python asset packager has nine executed adversarial tests. Source replay
counts **16 Rust and 13 Kotlin tests authored, not executed**. Rust coverage uses
actual native client/storage/Suggest APIs and real payloads, including genuine
open-transaction cancellation, deferred-constraint COMMIT failure, config races,
locale mismatch and positive queries. Kotlin coverage exercises factories,
transport controls, late responses, off/on generations, close failure and
production storage provider constraints. Rustfmt parsed the candidate; that is
not Rust compilation. The existing RS-blocker trace formatting was preserved.

Root owns global scope/order integration. `ordering-review.json` records both
orders: RS blocker and search-config are order-free with Task29 on this scoped
source; Task26 must precede Task29 across all four shared paths. Required target
execution is listed in `RUNTIME-ACCEPTANCE.md`. Per `docs/android/AGENTS.md`, source
application and an APK build do not substitute for the meaningful test suites.
