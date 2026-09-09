# Remaining session-cleanup work after the first native increment

This is a read-only implementation plan, not F04 completion evidence. The frozen
245-file inventory (`40da1bf9…`) and 107-body archive (`4ff52986…`) remain unchanged.
The current payload provides per-frame destruction completion and cleanup-owned
cookie operations. It has no production coordinator, all-writer admission gate,
acknowledged cache eviction or journal-success path. Native5 compilation and the
14 existing native target cases are still prerequisites, not substitutes for these
remaining contracts. No guest operation or target test ran for this audit.

`source-inputs.json` binds 56 inspected files to retained source archives. Twenty-six
match the exact proposed245 digest; the other 30 are outside that partial manifest
and remain captured or frozen design evidence. `supplemental-source.tar.gz` retains
10 additional read-only files, including the exact candidate GeckoSession and
GeckoEngineSession bodies. Before implementation, obtain current parent receipts
for unbound paths and declare additional ownership; do not assume the old capture
is a complete description of the current source tree.

## Ordered implementation

1. **Establish a held native writer barrier.** Keep the existing cookie lease and
   acquire each `FrameLoader.whenDestroyed()` result before closing its frame.
   Inventory normal/private/custom/extension sessions and replacement frames; a
   Java close, a Redux action, or closing one frame is not a runtime-wide barrier.
   Gate session creation and load/restore before opening content, including the
   direct `GeckoEngine.createSession` → `GeckoEngineSession` → `GeckoSession.open`
   path. A BrowserStore middleware alone misses direct consumers.

   Add a cleanup-specific service-worker fence at the manager/private-worker
   boundary, before `SpawnWorkerIfNeeded`'s existing-controller early return.
   Wait for every captured actor's real termination and reject failed operation
   results. Currently `ShutdownInternal` ignores the returned `Tnsresult`, and
   `Shutdown` resolves its caller even when the native promise rejects. It also
   drops `mControllerChild`, permitting the next operation to spawn a replacement.
   Do not use irreversible `mShuttingDown` or synthetic shutdown notifications as
   a temporary barrier. Do not unregister retained sites merely to stop workers.

   Trace dedicated/shared workers, client creation, extension background work and
   existing quota transactions through a generation-aware admission boundary.
   Blocking only new quota directory locks does not stop clients already holding
   them. A held lock must also permit the coordinator's own deletion operation;
   an exclusive lock that deadlocks ordinary clear-data requests is not a design.
   Selected stores need protection from late writes even when an unselected
   extension or registration remains installed. Until this coverage is complete,
   keep journal-success wiring blocked.

2. **Give selected cache eviction a real completion/error result.** The current
   `NetworkCacheCleaner` resolves after `Services.cache2.clear*` returns.
   `CacheStorageService::Clear` schedules `EvictByContext`; the latter immediately
   hides index entries while disk eviction is still pending. An empty index,
   zero consumption report or successful cache miss cannot prove disk completion.
   `CacheFileContextEvictor` additionally drops failed iterator entries and logs
   dispatch failure without exposing a per-operation error. A cleanup-owned
   operation must carry iterator, dispatch, file-removal and cancellation failures
   to its caller, and fence already-open streams/metadata writes as well as new
   admissions. Keep that generation held until the journal decision is persisted.
   Preserve unrelated cache entries and normal cache API behavior without a lease.

3. **Implement strict category results and the desktop retention decision.** In
   `GeckoViewStorageController.sys.mjs`, return a failure when the native callback
   reports any failed selected category instead of ignoring the failed-flags mask.
   Carry the result through `StorageController.java`, `DataCleanable.kt` and
   `GeckoEngine.kt`, then await it in `DeleteBrowsingDataController.kt`. Await
   translation deletion and tracking-protection clearing too. This can improve
   explicit manual clearing independently; a zero mask alone cannot repair the
   native cache or legacy cookie acknowledgment gaps above.

   Use a fresh, strict `PrincipalsCollector` for each held cleanup attempt. Its
   existing quota enumeration catches errors and returns an empty list; that is
   not evidence of an empty store. Merge quota/service-worker principals with the
   cookie lease's disk-plus-memory scopes, including private and complete origin
   attributes. Evaluate retention before clearing site permissions. Use the exact
   selected cookie IDs for native removal; never convert incomplete attributes
   into wildcard deletion. Reject unknown, inaccessible or over-bound input and
   retain the pending operation for retry.

4. **Serialize the app's own stores and cache producers.** `AutoSave.triggerSave`
   starts an independent `GlobalScope` job, and ignores `SessionStorage.save`'s
   Boolean result. `SessionStorage.clear()` has no result, and saving an empty tab
   list returns true after calling it. RecentlyClosed and download middleware
   launch independent storage writes/restores after dispatch. Pause admissions,
   await outstanding operations, then perform selected deletion with a checked
   result; prevent an old snapshot or restoration observer from repopulating the
   store afterward. Preserve unselected history, passwords, permissions, downloads
   and extension data. Bulk download-list clearing does not authorize deleting
   downloaded files.

   `AndroidTranslationAssets.deleteAll()` already awaits its serialized file
   removal and aborts existing downloads, but another download can be admitted
   afterward. For selected cache cleanup, hold a provider admission/publication
   fence until completion. Preserve explicit user-operation authorization and the
   pinned catalog/asset checks. Do not erase Suggest databases or add-on state as
   an accidental interpretation of “cache.”

5. **Add the durable session journal and settings transitions.** The new journal
   must be armed before the first admitted browsing session, not only when Quit is
   tapped. Load and validate it while admission is closed; recover interrupted
   cleanup before navigation; durably arm the current selection before reopening.
   Serialize master/category changes, operation generations and retries. Existing
   explicit Off choices must survive; do not reset seeded stored choices.

   Choose and review one authoritative persisted operation record before wiring
   SharedPreferences to a second native record. `apply()`, a queued write, or two
   independent “successful” writes do not establish cross-store atomicity.
   Task35's `savePrefFileAsync()` is available for a native-pref journal only after
   a real current profile is initialized; await its actual result. Never infer
   rollback ownership from a same-value concurrent write. A failed or unconfirmed
   save keeps admission/pending recovery conservative and offers an explicit retry.
   Normal runtime initialization must distinguish Fenix's main process from its
   isolated content-process path, following the current Task20 process guards.

6. **Connect Quit, retry and recovery only after those contracts exist.** The
   successful path is: hold admissions → drain/cancel writers with checked results
   → acquire/store leases and collect retained scopes → delete selected categories
   → await all native and app-store results → durably mark journal completion while
   the barrier is still held → finish the activity. `clearBrowsingDataOnQuit` must
   stop invoking completion in `finally`; `MenuDialogFragment` must finish only on
   acknowledged success. Cancellation, frame crashes with unresolved replacement
   writers, deletion errors and journal errors retain pending state and provide
   retry without presenting success. Manual-clear UI must also restore usable
   controls and report errors without accessing a destroyed view.

   Startup recovery can reopen navigation only after recovery succeeds and the new
   session is durably armed. A force-stop cannot run cleanup at the instant it
   happens; the claim is next-start cleanup before content is admitted. Releasing
   a cookie lease, stopping a worker, or running a `finally` block is not journal
   completion.

## Retention cases that must remain explicit

The inspected desktop `browser/modules/Sanitizer.sys.mjs` uses an effective
`cookie` permission first. ALLOW retains; DENY, SESSION and unsupported legacy
values do not. If no explicit value applies, its domain/subdomain fallback uses
`Services.eTLD.hasRootDomain(perm.principal.host, principal.host)` in that direction,
with supported HTTP/HTTPS/file principals and no scheme/port distinction. Porting
this to a registrable-domain or exact-origin approximation would change behavior.
Deletion nevertheless targets each actual principal's complete origin attributes.

When the global shutdown-cleanup master is Off, desktop still honors explicit
ACCESS_SESSION site permissions. Its separate path selects matching principals
and clears their cache/cookies/DOM storage/EME/bounce state. This is a separate
explicit site choice, not permission to clear all unselected data. Global cookie
and storage cleanup honors ALLOW exceptions; explicit manual deletion retains its
separate user-requested semantics. Preserve desktop's ancillary selected category
effects (cookie-banner execution, fingerprinting and bounce state) deliberately.

The existing cookie primitive rejects unavailable/no-persistent-storage mode and
oversized selections rather than treating them as success. Resolve those supported
profile/batching cases before full F04 acceptance. Its SQLite commit result is an
operation acknowledgment under the existing `synchronous=OFF` setting, not a new
power-loss fsync guarantee. Process interruption and uncertain write results must
continue to leave a retryable journal.

## Paths and validation boundaries

The existing 57-path Task37 declaration already covers the new GV cleanup module,
controller/journal/middleware, clear-data bridge, principal collector, session and
RecentlyClosed stores, Fenix lifecycle/settings/menu/UI and corresponding tests.
Keep the existing `DeleteBrowsingDataOnQuitFragmentTest.kt` as an existing input.
The inspected additional path groups below require metadata before implementation:

| Boundary | Exact additional source paths, relative to the named directory |
|---|---|
| Service workers | `dom/interfaces/base/nsIServiceWorkerManager.idl`; `dom/serviceworkers/{ServiceWorkerManager.cpp,ServiceWorkerManager.h,ServiceWorkerPrivate.cpp,ServiceWorkerPrivate.h,ServiceWorkerRegistrationInfo.cpp}`; `toolkit/components/cleardata/ServiceWorkerCleanUp.sys.mjs` |
| Other worker/storage admission | `dom/workers/RuntimeService.cpp`; `dom/clients/manager/ClientManagerService.cpp`; `dom/quota/{QuotaManager.h,ActorsParent.cpp}`; exact auxiliary headers/IPC/tests remain to be traced before claiming coverage |
| Cache completion | `netwerk/cache2/{nsICacheStorageService.idl,CacheStorageService.cpp,CacheStorageService.h,CacheFileIOManager.cpp,CacheFileIOManager.h,CacheFileContextEvictor.cpp,CacheFileContextEvictor.h}`; `toolkit/components/cleardata/ClearDataService.sys.mjs`; open-handle implementation/test paths remain to be traced |
| Common session admission | `mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoSession.java`; `mobile/android/android-components/components/browser/engine-gecko/src/main/java/mozilla/components/browser/engine/gecko/GeckoEngineSession.kt`; native open/load dispatch paths must be traced before selecting the lowest complete boundary |
| Download writer completion | `mobile/android/android-components/components/feature/downloads/src/main/java/mozilla/components/feature/downloads/{DownloadsUseCases.kt,DownloadMiddleware.kt}` and their targeted tests |
| Translation cache admission | `toolkit/components/translations/{AndroidTranslationAssets.sys.mjs,actors/TranslationsParent.sys.mjs}` and provider tests; preserve Task16 ordering and current pinned source |

After native5 compiles, run the existing nine cookie tasks and five FrameLoader GV
methods with named, non-skipped results. Add actual tests for worker operation
failure and attempted respawn; active HTTP/cache writes crossing cleanup; iterator,
dispatch and disk deletion failures; quota enumeration failure; retained ALLOW and
SESSION scope matrices including default/nondefault/private/partition attributes;
and native lease/batch/no-persistent-storage limits. Target tests must distinguish
real disk/IPC results from queued work. A mocked callback does not prove a native
boundary.

Add Kotlin tests for awaited completion/failure/cancellation, settings master and
category transitions, stale autosave/RecentlyClosed/download operations, detached
views, and repeatable retry. Run the full Fenix and affected A-C gates after actual
compilation. Finally seed selected and unselected data into the same source-bound
APK, exercise successful Quit and explicit Off/ALLOW/SESSION choices, interrupt
each journal/cleanup phase by real process death, and prove recovery completes
before restored tabs, intents, custom tabs and background content can write.
Keep release-APK acceptance separate from instrumented native fixtures. Source
work and tests can proceed while native5 runs; production journal-success and F04
completion remain blocked until these native and runtime contracts are measured.
