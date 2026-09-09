# Session cleanup: initial source design

Status: scope and source design only. Task metadata commit `b4093f2` precedes
implementation. No production file, guest, browser profile or settings submodule
was changed. No Kotlin/native test or build ran. The board check ran successfully:
122 tasks, 29 waves, zero warnings.

The base is root `3c6d4b7`. Root's retained
[cleanup audit](../lw-m7-21/cleanup-source-audit/README.md) contains 14 files from
the actual native4 source, with stable before/after hashes and six matches to the
active 164-file build manifest. `design-source-inputs.json` and
`additional-read-only-inputs.tar.gz` retain the further frozen-beta source used
below; those older files are design inputs, **not a claim of current guest
identity**. Before implementation, compose the current Task35 and Task36 changes
and the Task29 startup predecessor on every shared path. The exact additional
source inventory is in `additional-source-request.json`.

## Required behavior and proposed ownership boundaries

1. Keep manual clearing distinct from session cleanup. A manual cookies/site-data
   clear is an explicit request to clear the selected data. Quit and interrupted
   session recovery honor the desktop cookie retention permissions. Neither path
   silently adds history, passwords, permissions, downloads or tab removal.
2. Add a process-owned cleanup coordinator and a versioned journal. Recover an
   existing pending session before any browsing session can load. Then persist
   the new session's selected cleanup categories before admitting browsing.
   Root explicitly confirmed full session journaling: writing the journal only
   when Quit is pressed would miss force-stop before Quit.
3. Update the master/category controls through the same serialized journal
   transition. Preserve existing explicit Off and category choices. Store the
   settings and their cleanup intent consistently; do not acknowledge a disk
   write failure as a saved choice, infer rollback ownership, or reset choices
   after ambiguous failure. A stale armed record must not override a successfully
   persisted explicit Off. Corrupt/unsupported journal data requires a visible
   recovery error, not guessing a destructive category set.
4. Await actual category operations. Replace callback-free engine dispatch with
   suspend bridges that propagate completion/error once. Await translation-cache
   deletion, tracking-protection deletion, selected permission storage and actual
   app storage writes. Capture the category set once; cancellation/partial failure
   keeps recoverable pending work. Work must outlive a view detach, with no late
   detached-view access.
5. Correct GeckoView clear-data result handling for global, host and base-domain
   operations. Nonzero failed-category flags or thrown errors must reject; an
   exception during principal collection cannot become an empty successful clear.
   The new native session-cookie/storage path must use the retention algorithm
   below and never reuse a broad global clear for retained principals.
6. Show cleanup failure and Retry without invoking the success-only quit callback.
   Keep next-start browsing blocked while recovery is incomplete. Closing the
   error UI may leave the task, but must not claim successful cleanup or discard
   the journal. Manual-clear failure restores usable controls and reports failure,
   without the existing success snackbar.

Task metadata currently declares 45 source paths for these JS/GV/A-C/Fenix,
storage and test seams. A native content-close or cookie-database acknowledgment
extension requires its exact additional paths before edits. The three unresolved
boundaries below are part of completion, not exceptions to acceptance.

## Desktop retention semantics to preserve

The retained `Sanitizer.sys.mjs:510–560,1173–1265` collects supported web/file
principals and checks `cookie` permissions before session cookie/storage clearing.
An effective permission for the principal takes precedence: ALLOW retains;
DENY/SESSION or an unsupported old value does not. With no permission, the desktop
fallback considers cookie permissions on matching subdomains using
`Services.eTLD.hasRootDomain(perm.principal.host, principal.host)`. Its fallback
intentionally ignores scheme/port. Do not substitute exact-origin rules, invent a
registrable-domain wildcard, or flip the direction of that subdomain comparison.
The permission manager remains responsible for its configured origin-attribute
isolation; deletion must carry the actual principal attributes.

Use a fresh principal collection for each cleanup attempt. The existing collector
copies quota/service-worker principals and cookie origin attributes, but quota
failure is currently swallowed (`PrincipalsCollector.sys.mjs:109–145`). A narrow
strict mode for the new caller can preserve legacy callers while making recovery
fail closed. Its list must exclude extension/internal principals as today.

`CookieCleaner.deleteByPrincipal` documents wildcard matching when default origin
attributes are omitted. `ChromeUtils.fillNonDefaultOriginAttributes`, whose
actual WebIDL is retained, supplies **all defaults** despite its name. The new
cookie path must use complete attributes or remove exact cookie tuples with
`nsICookieManager.remove(host,name,path,originAttributes)`; it must not turn an
ordinary principal into a wildcard over private, container or partitioned data.
The appropriate implementation and its native persistence result still need
review. Preserve desktop permission-matching behavior separately from exact
deletion targeting. Cookie retention does not automatically exempt network/image
cache: cache is a separately selected category.

When session cleanup is globally disabled, desktop also processes explicit
ACCESS_SESSION exceptions (`Sanitizer.sys.mjs:1094–1154`). This must be accounted
for alongside explicit master Off; Off disables the global selection, not a
separate explicit per-site session permission. This design does not add a site
permission UI yet; existing permission creation/control coverage remains separate.

## Boundaries requiring further native/storage design

| Boundary | Primary source finding | Consequence |
| --- | --- | --- |
| Browsing admission | Existing uBO middleware holds only `CreateEngineSessionAction`. `AddonPopupBaseFragment.kt:321` calls `engine.createSession()` directly; `GeckoEngineSession` opens Gecko from its constructor path. | A cleanup middleware beside uBO is useful but insufficient alone. Trace restored/custom/background/direct sessions and enforce the gate at an actual common admission boundary. |
| Content teardown | `GeckoSession.close():1872–1891` dispatches proxy `Window.nativeClose`. `GeckoViewSupport::Close` in `nsWindow.cpp:1925–1939` calls `ForceClose`. `nsGlobalWindowOuter::FinalClose:6113–6147` posts another event and deliberately permits intervening timers. | Returning from Java close, or a BrowserStore dispatch, cannot establish that content has stopped repopulating data. A native teardown acknowledgment and closed admission are required before a successful Quit. No such barrier is claimed yet. |
| Cookie disk completion | `CookiePersistentStorage.cpp:544–555,628–645` enqueue asynchronous DELETE statements. `RemoveCookieDBListener::HandleCompletion:434` ignores its reason. `CookieCleaner` resolves after calling the synchronous API. | A zero clear-data mask acknowledges that wrapper, not the cookie database deletion. Preserve recovery intent and add a meaningful native acknowledgment/error path before claiming durable completion. Do not use test-only close/reopen APIs in production. |
| Tab/download/history storage | Remove-all tab/download use cases return after BrowserStore dispatch. RecentlyClosedMiddleware launches storage deletion. SessionStorage/AutoSave independently save snapshots, and SessionStorage's empty-state deletion returns success without checking file removal. | Await storage outcomes and order them against older queued writes; stopping or reading a queue alone is insufficient. Startup must settle relevant restore work before finalizing the selected clear, so an old restored snapshot cannot reappear afterward. |

The master/category checkpoint and native admission/teardown solution remain design
work. This handoff deliberately does not present an implementation that passes a
mocked callback while those boundaries remain unresolved.

## Required target evidence

Use the separately built native test environment for real clear-data, cookie DB,
principal collection and error tests. Use the production candidate for final
normal/private cookies, localStorage, IndexedDB, service-worker storage and cache
seeds; ALLOW, DENY, SESSION and no-permission controls; subdomains/schemes and
partition/container attributes; unrelated history/bookmarks/passwords/download
records; real manual clear, Quit, partial failure, retry, immediate interruption
and next-start recovery before the first load. Include a page actively writing
data while Quit begins and a direct/background session entry attempt. Invalid or
missing seeds, ignored native tests, mocked-only writes and stale APK evidence do
not close these requirements.

Android cannot execute cleanup while force-stopped. The intended behavior is
durable intent and recovery on next startup, not deletion at process death.
