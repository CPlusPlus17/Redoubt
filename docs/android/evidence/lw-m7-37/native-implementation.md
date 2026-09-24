# First native increment: review candidate, target execution pending

Metadata `5fb3533` declares the additional native paths before edits (57 total
Task37 paths). This increment changes only 15 of them. It does not implement the
session coordinator, all-writer admission, cache completion or journal success.

`native-composition.json` binds the parent capture of 64 requested paths
(51 present, 13 absent) to the selected 13 existing inputs here. Its archive SHA256
is `f32424a86e6123e7158baddf7d471366381ebbfc0ae7dafe56c195fb611a6eb7`.
The two test-support files then receive corrected Task35, with zero offsets/fuzz.
Tasks29/31/36 have no shared paths in this first increment. The captured existing
`DeleteBrowsingDataOnQuitFragmentTest.kt` is retained, and is not edited or replaced.
`native-source-files.json` gives the exact current patch and before/after hashes.
The capture and earlier design archives remain unchanged.

`check-ordering.py` measures the complete two-file overlap with Task35 in both
orders. Task35 must precede this patch; canonical output matches both exact final
hashes. Root owns the central ordering registry and PATCH-SCOPE count updates.

## Implemented contracts

`FrameLoader.whenDestroyed()` shares a cycle-collected Promise and a distinct
completion flag. It resolves at the end of `DestroyComplete`, after remote/child
message-manager disconnection, including the existing child-crash path. It uses
the same stable privileged global as `GetParentObject`, so a first request after
owner detachment does not require an owner document. The existing destruction
schedule is unchanged. The pinned WebIDL parser rejected an initial `CallWith`
attribute; the final API needs no unsupported attribute or binding-config change.
This is a per-frame result, not a worker or all-content barrier.

The parent cookie manager has four methods:

- `beginSessionCleanup()` acquires an opaque UUID lease without deleting data.
- `getSessionCleanupScopes(token)` awaits an ordered database read, unions it with
  normal/private memory, and returns current `{id, host, originAttributes}` scopes.
  IDs remain bound to exact raw stored hosts and complete attributes for the lease;
  the retained ID registry is separate from current enumeration membership.
- `removeSessionCleanupScopes(token, ids)` prevalidates every ID, executes one
  parameterized SQL DELETE over the exact selected tuples, then removes matching
  memory cookies and sends existing notifications. It does not enqueue a second
  unacknowledged legacy deletion. Unknown IDs, SQL/binding/dispatch errors,
  cancellation and replaced/closing/rebuilding storage reject. Failed work keeps
  the lease held; a removed ID remains valid for an exact retry.
- `endSessionCleanup(token)` releases a known idle lease. It refuses in-flight
  operations; it is explicitly not proof of cleanup success. An invalidated lease
  can be released after its operation rejects, then a new token acquired.

The common parent `CookieStorage::AddCookie` entry refuses additions/replacements
before capacity eviction or other replacement side effects while the lease is
held. Manager/native additions also return an actual admission error. Memory
deletion collects all mutations before notifying observers, and the lease remains
busy through both jars' notifications. An observer cannot release it mid-result.

One SQL DELETE is intentional. The pinned
`storage/mozStorageAsyncStatementExecution.cpp:517–530` continues executing after
an implicit multi-binding BEGIN fails. A repeated-binding batch therefore cannot
establish the required atomicity. The final statement uses one binding set and
`(host, originAttributes) IN (VALUES (?, ?), ...)`. The three parent synchronous
transaction entry points are also fenced: begin refuses an active parent cookie
transaction, and those transactions cannot begin while the cleanup lease is held.
The existing serial asynchronous queue remains the ordering mechanism.

## Concrete limits

- No production caller acquires the lease yet. Existing desktop behavior without
  a lease follows the original paths. The new APIs do not change either Remote
  Settings allowlist, packaged rules, preference defaults or retention decisions.
- The current API rejects unavailable persistent storage, including the alternate
  `network.cookie.noPersistentStorage` profile mode. It must not mistake an unused
  or inaccessible old cookie database for an empty successful store. Supporting
  that mode remains necessary for complete profile coverage.
- SQLite preparation rejects selections beyond its SQL/parameter limits before
  any deletion. Scopes/strings have explicit bounds, and excess input rejects
  rather than truncating. A future journal-aware caller may need bounded batches;
  no such caller or whole-session atomicity is claimed here.
- A reported SQLite commit is not a power-loss fsync guarantee: this source still
  uses `PRAGMA synchronous=OFF`. A failure can leave durability unconfirmed and
  must never authorize clearing the future journal. Generic cookie error recovery
  is not redesigned by this API.
- The lease fences cookie additions and the synchronous transaction wrappers.
  It does not stop workers, network/cache writers or every legacy deletion API.
  Neither these results nor Java close completion permit a full cleanup-success
  path yet. The accepted remaining contracts are in `native-boundary-design.md`.
- The native callback handles cancellation, but there is no new caller cancellation
  API. Dropping a JavaScript await does not release the held operation or lease.

## Checks and actual target definitions

Run `python3 scripts/tests/test-session-cleanup.py`. It rebuilds the captured input
plus the exact Task35 overlay, checks all before/after hashes, replays the patch
without offsets/fuzz, runs the pinned XPIDL/WebIDL parsers, and validates JS syntax,
JSON/TOML and the test definitions. Vendored parser receipts are in
`native-parser-inputs.json`. These checks do not compile C++, generate all imported
bindings, compile Kotlin or run any native/browser test.

The actual cookie target is
`netwerk/cookie/test/unit/test_cookie_session_cleanup.js` (9 tasks): exact scopes
and origin attributes, invalid/busy/stale IDs/tokens, positive-controlled HTTP and
reentrant-manager writes, ambient transactions, real SQL failure and rollback/retry,
disk-only rows, invalid attributes, queued storage close, and private-store teardown.
The SQL failure uses a real SQLite trigger. The database mismatch changes an actual
test-profile row. Neither result nor native callback is mocked.

GeckoView `org.mozilla.geckoview.test.SessionCleanupTest` has 5 methods:

- `remoteCloseWaitsForNativeDestructionAndSharesRepeatedCompletion`
- `closingOneFrameDoesNotReportReplacementFrameDestroyed`
- `crashedChildCompletesItsOwnFrameBoundary`
- `inProcessUnloadPrecedesCompletion`
- `firstPromiseCanBeCreatedAfterOwnerDetachment`

The in-process fixture performs and measures a real cookie write during unload;
it waits for native completion before removing its fixed fixture cookie. The
separate-session replacement test covers independent frame identity, not actual
remoteness swapping/BFCache replacement. The crash method retains upstream's two
unsupported process-mode assumptions; a skip is pending coverage, not a pass.
All 14 target cases, actual commit/disk failure coverage, dispatch cancellation,
remoteness swapping and all product runtime acceptance remain **unrun/pending**.
