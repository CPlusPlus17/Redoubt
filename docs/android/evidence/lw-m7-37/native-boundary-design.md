# Native completion boundaries: bounded design follow-up

This is a read-only design, not implemented code or a target pass. The 36 further
native inputs and their exact hashes are retained in `native-boundary-inputs.json`
and `native-boundary-inputs.tar.gz`. They are from the frozen beta source; parent
must bind the current source before edits. No requested input is missing locally.
`native-additional-source-request.json` gives the minimum proposed extra ownership
and the separate worker-design inputs. Existing Task37 ownership still stands;
the additional paths below have **not** been declared for production editing.

## 1. Small document-completion primitive

Add a chrome-only `FrameLoader.whenDestroyed()` Promise, without changing the
timing of `ForceClose`, normal `Destroy`, or desktop callers. Minimum paths:

- `dom/base/nsFrameLoader.{h,cpp}`
- `dom/chrome-webidl/FrameLoader.webidl`

The Promise must resolve only at the end of `nsFrameLoader::DestroyComplete`,
after message-manager disconnection. That callback has the needed meaning:
`nsFrameLoader.cpp:1918–1957` waits for remote child actor destruction, or for
the in-process unload/window-destroyed/message sequence. `BrowserParent.cpp:800–868`
also reaches it when the child dies. Record a separate completed flag: `isDead`
means only that destruction was requested, and cannot satisfy this API. A repeated
request after completion resolves immediately. Multiple callers await the same
completion. Account for the Promise in cycle collection. Do not resolve a waiter
just because its caller cancelled, a timeout elapsed, or a close request returned.

The session coordinator obtains these Promises **before** requesting close. It
must first close admission to window creation/navigation, then cover every owned
frame and any replacement created by an already-dispatched process switch. A
Promise for an old frame alone does not cover its new replacement. A timeout means
cleanup remains pending; it is not permission to delete while content still runs.
Tests belong in the existing Task37 GeckoView instrumentation/privileged test
assets: remote and in-process teardown, an unload writer, a crashed child,
already-destroyed/repeated waiters and a concurrent replacement.

This primitive proves frame destruction only. It is intentionally **not** named
or reported as an all-writer barrier.

## 2. Cleanup-owned cookie database operation

Do not retrofit a shared global success flag onto `mRemoveListener`. Add a narrow
cleanup operation with its own immutable predicates, connection identity and
result. Minimum existing paths:

- `netwerk/cookie/nsICookieManager.idl`
- `netwerk/cookie/CookieService.{h,cpp}`
- `netwerk/cookie/CookiePersistentStorage.{h,cpp}`
- `netwerk/cookie/CookieStorage.{h,cpp}`
- `netwerk/cookie/test/unit/xpcshell.toml`, plus new
  `test_cookie_session_cleanup.js`

The proposed contract is a parent-only opaque cleanup token, a read of candidate
cookie host/origin-attribute scopes, and an awaited exact-scope deletion under
that token. This is a new cleanup API, not arbitrary SQL or an unprivileged web
API. Scope dictionaries must be complete and canonical; use existing host/IPv6
normalization and `OriginAttributes` suffix serialization. The public JS layer
computes the desktop retention decisions from the candidate scopes. No cookie
values need to cross the new result interface.

The token closes ordinary cookie mutation admission at the common parent storage
path **before** collection. `CookieStorage::AddCookie:678+` is shared by normal
Set-Cookie, document/IPC and cookie-manager writes; checking only Java navigation
or the HTTP response path misses other writers. Reject new writes before eviction
or replacement side effects. The implementation must audit alternate mutation
paths and distinguish internal cleanup from ordinary callers without a mutable
ambient "current operation" that nested observers could borrow. The token remains
held through journal acknowledgment and remains closed after successful Quit.
Recovery releases it only after the next session is durably armed. Tokens are
generation-bound, never reusable across profile close/rebuild or a new cleanup.

For persistent cookies:

1. Require initialized, usable persistent storage; missing connection after failed
   initialization is an error, not an empty successful store. Snapshot the exact
   connection/generation and validate the complete bounded scope list before
   mutation.
2. Collect candidate scopes from both the current memory view and an ordered read
   of the database. A previous legacy async deletion may have removed memory but
   failed on disk. Retrying from memory alone would omit that remaining row.
3. Issue parameterized DELETE statements on the existing serial connection with
   one operation-owned callback. Delete by exact normalized host and complete
   origin-attribute suffix, not by wildcard attributes or an approximate domain.
   Use a single owned transaction for a batch; no shared borrowed statements or
   caller-supplied SQL.
4. Capture preparation, binding and dispatch errors immediately. Capture
   `HandleError` and accept `HandleCompletion` only with `REASON_FINISHED` and no
   earlier error. `mozStorageAsyncStatementExecution.cpp:328–389` performs commit
   before this callback and changes the completion state to ERROR if commit fails.
   Cancellation is rejection. A stale token/connection generation or corruption
   rebuild also rejects, even if an old connection later reports completion.
5. Only after the checked database result, remove the matching in-memory cookies
   using a memory-only helper and the existing notification semantics. Do not call
   the existing removal method again and enqueue another untracked DELETE. The
   mutation gate prevents a newer matching cookie from being silently removed at
   this step. Do not undo another writer after failure or assert rollback when
   connection state is uncertain.
6. Resolve the operation only after both steps. Propagate its actual failure to
   the native cleanup result and keep the journal pending. Retry the scopes, not
   a list filtered down to cookies still present in memory. Nonpersistent private
   cookies use checked in-memory completion and their actual attribute bucket;
   they must not masquerade as a disk write.

This avoids redesigning ordinary add/update/remove persistence. Legacy calls keep
their existing signatures. Their concurrent errors can still invalidate the
operation's captured connection, which must be handled conservatively.

**Durability limit:** the pinned cookie connection sets `PRAGMA synchronous=OFF`
at `CookiePersistentStorage.cpp:2239`. A checked SQLite commit acknowledges the
actual deletion and its reported errors; it is not a power-loss fsync guarantee.
Process interruption and system/storage failure are different tests. Do not claim
power-loss durability or silently change the connection's global PRAGMA. If that
stronger guarantee is required, it needs a separately reviewed owned sync barrier.

Meaningful tests: two retained and two removed hosts; exact partition/container/
private attributes; leading-dot and IPv6 normalization; a DELETE/commit failure;
cancel before completion; dispatch failure; missing/closing/rebuilding connection;
legacy-memory/disk mismatch; a late HTTP/IPC/extension-cookie writer; and retry
without losing retained data. Cookie xpcshell can initialize its cookie database
from its real profile directory; this must be verified on the target and is not
an assumption that Task35's current-pref-file initialization exists there.

## 3. Remaining writers cannot be omitted

The above two primitives do not close full Task37 acceptance. The source exposes
these concrete paths, which constrain the eventual coordinator:

| Writer or operation | Existing behavior | Required completion/admission contract |
| --- | --- | --- |
| Direct/restored/background Gecko sessions | `GeckoEngineSession` opens sessions directly; addon popups bypass BrowserStore. | A runtime/native admission token must precede **all** session creation and restored/queued navigation; a Fenix middleware remains supplemental. Capture it before engine/profile consumers can start browsing. |
| Service workers | `nsIServiceWorkerInfo.terminateWorker` explicitly permits the next event to spawn a replacement. `ServiceWorkerPrivate::Shutdown` resolves its DOM Promise on both native resolution and rejection. | A separate temporary cleanup admission generation must reject new launches/events while running workers terminate; aggregate actual native termination outcomes. Do not reuse the shutdown-only `mShuttingDown` flag or unregister retained registrations just to stop their workers. |
| Service-worker registration deletion | `ServiceWorkerCleanUp.sys.mjs:27–43` resolves `unregisterFailed` as success. | The new cleanup caller needs strict unregister result handling. Preserve legacy semantics through an explicit strict path if necessary; failed unregister must retain pending cleanup. |
| Shared/dedicated workers and other active clients | Frame completion alone does not document completion of every client's queued storage/network work. | Account for them at the actual worker/client or affected storage-admission boundary, not by a fixed wait or by observing an empty tab list. |
| Quota-managed storage | `QuotaCleaner` documents new-origin races during enumeration. Its normal clear releases its directory locks on completion. | If any writer survives, retain a scoped cleanup admission/lock boundary through journal acknowledgment. `QuotaManager::OpenClientDirectory` is the central client-lock entry point; no implementation or completeness claim is proposed here yet. Do not hold an exclusive lock and then deadlock the normal clearer trying to acquire it. |
| Existing HTTP and extension-cookie writes | These can outlive page-close requests. | The common cookie mutation token above must reject them for the held cleanup interval, including late already-dispatched responses. A snapshot of existing channels is not enough. |
| Network cache | `NetworkCacheCleaner.deleteAll` resolves immediately after `cache2.clear`; `CacheStorageService::Clear` schedules eviction and returns. | The selected cache category needs its own actual eviction result and late-write treatment. A queue drain, disk-consumption read or a wrapper Promise is not a deletion/error receipt. This is a discovered selected-category dependency, not an unrelated cache redesign. |

Minimal worker-contract ownership, if selected after review, is
`dom/interfaces/base/nsIServiceWorkerManager.idl`,
`dom/serviceworkers/ServiceWorkerManager.{h,cpp}`,
`dom/serviceworkers/ServiceWorkerPrivate.{h,cpp}` and the existing strict caller
`toolkit/components/cleardata/ServiceWorkerCleanUp.sys.mjs`, with target tests.
The exact runtime/remaining-client/cache guard is **still unresolved**, so their
files are archived as read-only design inputs rather than preemptively claimed.

Do not clear a persisted session journal after only the frame and cookie results.
Completion requires every selected category's checked result and a held boundary
that excludes late repopulation. A full Gecko shutdown uses additional worker and
network phases, but invoking those observer topics manually would be an unsafe
substitute: the shutdown state is irreversible and can close services needed for
cleanup/retry. This design does not propose synthetic shutdown notifications.

Recommended implementation order is the independently testable frame completion
primitive and cleanup-owned cookie operation first, while preserving the journal
and leaving full-session acceptance open. Review the common runtime/worker/cache
boundary before wiring a success path that drops the journal. This is an ordering
of implementation work, not a reduced definition of cleanup parity.
