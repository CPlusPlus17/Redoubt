# LW-M7-20 — Android accounts and Sync opt-in candidate

This source candidate makes account services **off by default** and adds an
**Accounts and Sync** row in Settings. Changing it presents an explicit
**Enable accounts and restart** or **Disable accounts and restart** action.
The confirmation explains that account data, Sync selections and custom servers
stay saved, and that restart ends the current private browsing session.

**Target acceptance is pending.** The 2026-09-09 actual service-firefox-accounts
run executed 19 cases and failed five in `AccountServicesDisabledTest`. Two
failures unboxed the generic Mockito matcher's null return for `getProfile`'s
Boolean parameter; the remaining three reported leftover matcher/verification
state. This fixture correction adds `anyBoolean` at the three affected call sites
and preserves all assertions and all eight cases. The generic `any` import remains
necessary for the separate `processEvent(FxaEvent)` stub. No production source
changes. The full 19-case accounts selection and complete Fenix/affected A-C suite
must run again; no corrected target pass is claimed.

[boolean-matcher-correction/receipt.json](boolean-matcher-correction/receipt.json)
retains all five actual failure identities, the captured XML/log/source hashes,
old patch/manifest lineage and exact test-only replacement. Its archive preserves
the observed original target evidence; root retains the terminal full-run capture
separately. Scoped source replay passes all 23 files and preserves the 28 authored
Kotlin tests, with only the intended test file changed. The scoped Task14 patch
pin also advances to the previously integrated Bundle correction; replay proves
its Task20 intersections still yield the recorded bodies. This source check is
not a Kotlin rerun, login result, network measurement or proof of Android restart.

## Actual service boundary

`AccountServices.initialize` reads a separate Android preference file before
Fenix's content providers can start workers: `FenixApplication.attachBaseContext`
calls the policy initializer before normal process setup. An absent choice means
false in Fenix; existing explicit true/false choices win. Other Android Components
embedders retain their existing enabled default. The desktop preference-pane
switch uses `identity.fxaccounts.enabled`; this implementation does not rely on
that Gecko preference to control the Kotlin account subsystem.

The implementation paths in [sync-opt-in.patch](../../../../patches/android/sync-opt-in.patch)
are:

- Fenix's deferred startup checks admission before resolving the account manager
  or Relay integration. BackgroundServices skips its account feature wiring while
  off. Other Fenix consumers may construct an inert manager shell; it does not
  resolve lazy account storage/native state or construct SyncManager while off.
- The manager gates start, authentication, WebChannel login/completion, Sync,
  engine changes, account getters and queued state-machine work. Its generation
  binding also rejects an old shell if the policy is reinitialized. The public
  storage-wrapper testing hook rejects disabled access. Public debug account
  operations are guarded too. Closing a never-used manager cannot initialize its
  lazy account as a side effect. Checks after token/endpoint/profile awaits and
  before authentication notifications discard late results after disable; closing
  admission does not take the authentication-failure account-reset fallback.
- Sync dispatchers reject scheduling while off. Persisted Sync workers return
  before store/key/native construction, and recheck before native sync and before
  processing a late result. Synced-tabs flush workers return before resolving
  their lazy command provider; their scheduler also rejects new work.
- Relay's start and mask creation paths are guarded. Fenix's browser click path
  checks before resolving the integration and excludes private-tab mask creation.
  Its account WebChannel bridge is not started while off. Existing explicit
  account login from a private auth custom tab remains available after global
  opt-in; merely visiting a page cannot opt in.
- Settings does not construct its account/profile UI while off. Existing sign-in
  entries and the Turn on Sync screen lead to the explicit enable confirmation.
  Auth receiver URLs are discarded while off, with a recheck before dispatch.
  HomeActivity sanitizes a disabled auth custom-tab intent and its saved UI state
  before normal intent processing, then opens Settings. No callback auto-enables
  account services or forwards a stale auth URL into the restarted activity.

The unmodified `FxaServer.config` still reads `overrideFxAServer` and
`overrideSyncTokenServer`. Existing logout, account storage and engine-selection
implementations remain in place. Switching services off invokes neither logout
nor account reset.

## Persistence and restart

| Stage | Stored choice | Service admission in the current process |
| --- | --- | --- |
| Fresh Fenix start | Absent | Off |
| Start with explicit choice | Existing true/false | That choice |
| Failed write | Restore attempted; durability unverified if rollback fails | Previous running state |
| Successful enable or disable commit | New choice, synchronously committed | Closed until process replacement |
| Restarted process | New explicit choice | On or off as selected |

The launcher component is resolved and checked to belong to this package before
committing. The new intent is built from that component; auth URLs and extras are
not copied. Once the write succeeds, the current process closes admission and
invalidates manager generations. It submits cancellation for both periodic and
immediate Sync work and the synced-tabs command worker family, then waits for
bounded local cancellation receipts. The restart runs in `finally`, including
when cancellation fails, and uses the same `makeRestartActivityTask` plus
`Process.killProcess` pattern as the existing Firefox Labs implementation.
The restarted activity opens Settings so the selected state can be reviewed.

The post-commit sequence runs in a non-cancellable coroutine context. Rotation or
navigation after a successful write cannot abandon it. A false commit receipt or
persistence exception reports an error and leaves the running policy unchanged;
no jobs are cancelled and no restart is attempted. The preference helper attempts
to restore SharedPreferences' prior key/value because Android can update that
memory even when a disk commit fails. It checks the rollback receipt and logs
unverified durability if that write also fails. Neither the implementation nor
the UI claims that a failed rollback preserved the previous disk value: the error
message describes the running state and asks the user to review the setting after
a later restart. A dedicated failure test permits that later read to differ from
the previous running policy. A duplicate confirmation cannot replace an already
committed transition.

A blocking Rust operation can remain active during the bounded closing interval.
The completion boundary for switching services off is process termination and
restart. WorkManager cancellation and Kotlin admission checks are not presented
as proof that an already-running native HTTP call stopped. Process identity,
traffic cessation and private-session behavior must be measured on the APK.

No default is written during initialization. The only preference changed by the
control is `enabled` in `mozilla.components.service.fxa.account-services`.
Account records, secure-account storage, Sync authentication caches, engine
choices and custom server strings are not cleared or migrated by this control.

## Input binding and source verification

The isolated worktree started at
`cdb51bf8dacd45f7c85ba2988da15651145ba6d6`. Task metadata and all 23 source/test
paths were registered before implementation. The host input was copied read-only
from `librewolf-153.0esr-1-beta-20260908`; its name is not treated as a revision.
[source-files.json](source-files.json) pins each original copied file, the scoped
predecessors, and every pre-/post-candidate source file. No guest or shared
extracted source was modified.

[scoped-pristine.tar.gz](scoped-pristine.tar.gz) retains the 15 pre-stack files
needed for replay. Eight intersecting predecessor patches were reversed from the
private baseline and replayed in registered order, followed by the new candidate.
All 23 resulting files matched the edited source exactly. Run:

```sh
python3 docs/android/evidence/lw-m7-20/check-source.py
python3 docs/android/board.py --check
```

[verification.txt](verification.txt) records those source checks. The replay does
not invoke Gradle or a browser. The task's source scope matches the patch exactly.
The existing repository scope/order gates require root's integration metadata:
[proposed-ordering.txt](proposed-ordering.txt) lists every new shared pair, and
[ordering-review.json](ordering-review.json) records actual alternate-order runs.
Five pairs produce identical bytes in either tested order. No-nimbus and uBO must
precede this candidate in the measured composition. The no-adjust alternate run
failed in no-GMS before the candidate ran; it is **not** an isolated pair proof.
Root retains the existing no-adjust/no-GMS chain and the selected final order.
The Android/total patch inventory counts also need to increase by one in
PATCH-SCOPE.md. The initial failures are retained in
[order-check-pending.txt](order-check-pending.txt) and
[scope-check-pending.txt](scope-check-pending.txt).

## Required target evidence

The 28 authored tests cover default/explicit-choice persistence, failed writes and
failed rollbacks, actual account/engine preference retention, admission during
enable, stale manager references, rejected account/debug callbacks, worker early
exits before providers, restart ordering/failure behavior and a sanitized launcher
alias intent. Four tests suspend token, endpoint or profile results, commit disable,
then resume completion or a missing-key exception: their assertions reject late
native calls, notifications, cache updates and account disconnect/reset.

Existing Fenix feature tests keep their opted-in test-application fixture. Two
new tests instantiate a subclass of the production Fenix application and invoke
its actual `super.attachBaseContext` path, without overriding the account policy
hook or starting native `onCreate` work. They require default-off without writing
a choice and preservation of both explicit true and false. The suspended-result
tests reuse the existing upstream mock-native `TestableFxaAccountManager` helper;
its inspected source excerpt and full-file hash are retained in
[upstream-test-helper.kt.txt](upstream-test-helper.kt.txt) and `source-files.json`.
All target execution is pending, including both affected Android Components
modules and the full Fenix unit gate. Root should run the actual A-C/Fenix tests and
`python3 docs/android/board.py --check-fenix-tests` with retained XML/results.

The APK matrix must cover:

- Fresh off startup, foreground/background/restart, restored old periodic and
  immediate/command jobs, all sign-in/account/Relay UI paths, and auth deep links:
  no native account initialization or service traffic; control remains off.
- Enable from Settings: confirmed action commits, old PID exits, new PID opens
  Settings, choice is on, and explicit login/Sync succeeds. Exercise existing
  saved accounts and custom server settings separately.
- Disable with a signed-in account, active native sync/Relay work and queued
  callbacks: old PID exits, post-restart service traffic stops, old jobs cannot
  revive services, and account/engine/custom-server data stays intact.
- Cancelled confirmation and failed persistence: no restart or policy transition.
  Rotate/background during a successful commit/cancellation sequence; verify
  process death at each boundary yields the committed choice on the next start.
- Normal/private browsing, private auth custom tabs, stale callback intents and
  alternate launcher icons: no implicit opt-in, no forwarded auth URL on restart,
  and the displayed private-session explanation matches measured behavior.
- Re-enable restores the existing account flow without requiring data deletion;
  existing Sync engine controls and explicit logout work on the enabled build.

This handoff is an implementation candidate. These target checks remain required
before LW-M7-20 or the broader desktop feature-parity goal can be called complete.
