# LW-M7-26 — Firefox Suggest control and admission candidate

The candidate makes Android Firefox Suggest **effectively off by default on every
channel**, preserves saved explicit choices, and exposes the existing master,
web, sponsored and online choices in normal Search settings. Ordinary search
engine query suggestions, local history/bookmarks, custom engines and home
sections use separate paths.

**Compilation, Kotlin execution and APK behavior are pending.** Nineteen Kotlin
tests are authored, not executed. The source replay passes; it is not a network
measurement, an ingestion result or proof of working suggestion cards.

**Fresh local web/sponsored results remain unavailable.** There is no bundled
Suggest dataset and the generic Remote Settings blocker stays intact. The UI
states this explicitly, while retaining choices and supporting an existing local
cache. The separately gated online Merino path does not require that dataset.
A reviewed bundled-input followup is required before fresh local opt-in can be
called functional.

## Inspected desktop semantics

`Policies.sys.mjs` maps `FirefoxSuggest.WebSuggestions` to the all-suggestions
parent `browser.urlbar.suggest.quicksuggest.all`, SponsoredSuggestions to its
sponsored child, and the deprecated ImproveSuggest to
`browser.urlbar.quicksuggest.online.enabled`. OnlineEnabled takes precedence
when both online policy names are present.

All three use `PoliciesUtils.setDefaultPref(value, param.Locked)`. The inspected
helper writes the default branch and locks only when requested or when preserving
an earlier lock. LibreWolf's policy object supplies the three false values and
no Locked field. This candidate therefore supplies false defaults and preserves
explicit Android choices; it does not invent an enforced-off policy.

Android has an additional legacy non-sponsored selector below its master. Both
are visible and default false. The master preserves the desktop all-suggestions
boundary; the web and sponsored selectors determine local result types. Online
cards require the master, web and online choices. Existing hidden availability
and per-card explicit exclusions remain saved. Online availability and card
capabilities have channel-independent defaults behind the off consent controls;
a new explicit online opt-in also enables its formerly hidden availability flag.
Stock, sports and flight selectors are exposed so saved exclusions remain usable.

The exact inspected handler, helper, channel inputs and policy object are retained
under [inspected-source](inspected-source/) and bound by `source-files.json`.

## Actual Android wiring

- Production `FenixApplication.attachBaseContext` installs a plain preference
  reader before content providers or workers. It reads the existing Fenix keys
  without constructing Settings, Suggest storage or native clients, and writes
  no defaults. Legacy Fenix unit fixtures explicitly retain enabled behavior;
  new tests call the actual production attach path.
- `FxSuggestAdmission` captures effective choices and a generation. Preference
  notifications invalidate an earlier off/on generation. Query, ingestion,
  provider and transport paths recheck admission at execution and after results.
- Global Suggest dependency registration takes a factory. Disabled startup,
  periodic scheduling, persisted-worker wakeups and stale provider references
  cannot resolve it. Startup and UI ingestion recheck before resolving storage;
  disabled cancellation constructs only the scheduler and cancels by work tag.
- The storage wrapper checks admission before lazy native construction and before
  native query/ingest, and filters local result types against captured choices.
  An existing store can cancel reads without constructing an unused store. A
  worker whose old generation is closed completes without retrying that work.
- Search builder online data-source construction is lazy. The data source's
  native-backed default client is also lazy. Debounced requests carry a policy
  generation; disabled/obsolete/private requests return before the transport,
  and stale results are discarded after the synchronous call.
- `SuggestMerinoClient` itself checks online admission before native client/OHTTP
  setup and again before sending the request. Online providers and their data
  source recheck private browsing context separately from the global opt-in.
- Normal Search and existing debug controls write the same Fenix preferences and
  update the actual scheduler/admission path. Master-off preserves subordinate
  choices. The UI describes online typed-text transfer separately from ordinary
  search-engine suggestions.

An operation already admitted can finish. Desktop `SuggestBackendMerino.enable`
drops its client reference when disabled; it does not abort a request. Its
`cancelQuery` and MerinoClient comments explicitly let ongoing fetches finish.
The Android native SuggestClient exports no request cancellation method. The
candidate blocks new/queued work and drops late results; switching off does not
claim to retract traffic already sent. Likewise, a synchronous ingest already
running may finish; the existing default SuggestStore interrupt is for reads.
The generic Rust Remote Settings network blocker still blocks its network path.

## Missing local dataset: concrete followup boundary

Native `SuggestRemoteSettingsClient` constructs clients for
`main/quicksuggest-amp` and `main/quicksuggest-other`. It calls `sync()` and then
`get_records(false)`, and obtains each record attachment through the existing
RemoteSettingsClient attachment API. Suggestion rows generally live in JSON
attachments, not directly in collection metadata.

AMP requires its `amp` records and icons in quicksuggest-amp. Wikipedia requires
its `wikipedia` records and icons in quicksuggest-other. Ingestion also always
includes global configuration from quicksuggest-other. Default ingestion may
request additional provider record types; a bounded bundled-data implementation
must either supply their dependencies or explicitly constrain ingestion to the
reviewed AMP/Wikipedia set. Both choices need native ingestion coverage.

The existing `packaged_collections!` inventory has neither collection. Its
`packaged_attachments!` entries must explicitly name every bundled attachment;
the macro also includes the matching `.meta.json`, which binds hash and size.
Merely copying collection JSON or restoring network permissions is insufficient.

A separate reviewed task should retain official collection snapshots, selected
record IDs/types, global configuration, all required data/icon attachment bytes,
attachment metadata, hashes, sizes and source provenance; register them against
the actual packaged-data API; and exercise empty-profile native ingestion and
both positive and negative known queries with the network blocker intact. This
candidate provides no substitute or fabricated suggestion data.

## Source lineage and gates

The isolated repository starts at root `5ece20a`, with the two LW-M7-20 commits
transplanted as local predecessors (`fc70f34`, `8af9a17`). Task26 source scope was
registered first in `22e7596`. The private source copied the immutable host tree;
its two intersecting Sync files were overlaid with the reviewed Task20 source.
Per-file origin hashes and successful/unsuccessful reverse checks are retained.
No guest, shared extracted source, device or network experiment was used.

Nine intersecting registered predecessor patches were replayed from the retained
14-file [scoped-pristine.tar.gz](scoped-pristine.tar.gz), followed by this candidate.
All 20 final source/test files match individual before/after pins. The source
checker validates declared ownership, patch/input hashes, retained excerpts,
source-added whitespace and authored test counts:

```sh
python3 docs/android/evidence/lw-m7-26/check-source.py
python3 docs/android/board.py --check
```

[verification.txt](verification.txt) records those executions. Root owns global
patch-order and scope metadata. [proposed-ordering.txt](proposed-ordering.txt)
and [ordering-review.json](ordering-review.json) contain measured shared pairs:
six alternate orders produce identical source; no-GMS and Sync are kept before
the candidate in the tested composition. The no-adjust inverse fails in no-GMS
before reaching the candidate, so it is not an isolated intrinsic pair conflict.
Root must also increase the Android and total patch inventories by one.

The 19 authored tests cover the production default/upgrade reader, retained
master/leaf/card exclusions, ordinary search/local setting retention, factory and
native-store avoidance while off, restored worker success, denied scheduling,
lazy opt-in storage access, online transport admission, debounce cancellation,
late-result rejection, off/on generations and private context.

Before completion, root must execute affected Android Components tests and the
Fenix unit suite with `board.py --check-fenix-tests`, compile the affected target,
and retain source-bound APK evidence for fresh/upgrade/off/on/private/background
and process-restart cases. Positive online parsing in a mocked client test is not
a live Merino result. Local fresh-profile positive controls additionally require
the bundled dataset followup. Existing-cache local controls, ordinary engine
suggestions, custom engine selection, history/bookmark results and home settings
need regression coverage on the actual APK.

The actual native4 APK build subsequently reached the Suggest Kotlin compiler and
failed under `-Werror` because `Snapshot` had an internal constructor with a
generated exposed copy method. Task21 adds `@ConsistentCopyVisibility`, already
used in this source tree, preserving structural equality and the internal
constructor. The existing generation test now first checks a valid unchanged
snapshot. Failed source/logs and exact two-file correction are retained in
`../lw-m7-21/native4-apk-failure/` and `../lw-m7-21/admission-copy-correction/`.
This correction still requires an actual target rebuild and test run.

The [isolated-process correction](isolated-process-correction/README.md) composes
with corrected Task20 to keep both saved-policy readers in the main process and
close isolated-child admission entirely in memory. The actual six-file167 overlay
is retained separately; rebuilt target tests and first navigation remain pending.
