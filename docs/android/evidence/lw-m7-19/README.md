# LW-M7-19: Android add-on state durability

Implementation and source tests, 2026-09-09. Target compilation, xpcshell and
candidate-bound immediate force-stop tests are **pending**. This task is not done.

The motivating run is [LW-M7-12's fifth attempt](../lw-m7-12/runtime-fifth-attempt/README.md).
After the disable promise completed, its registry and in-memory XPI state were
both disabled, and filtering stopped. The disk startup cache still said enabled.
After immediate force-stop/restart that stale cache created an active extension
policy and blocking listener while the registry continued to report disabled.
The subsequent removal also stalled the browser. This patch has not yet been
measured against that removal failure on an Android process.

The frozen source independently explains the window: XPIDatabase uses a 20 ms
DeferredTask; XPIStates uses JSONFile's default 1500 ms delay. Neither scheduled
save is awaited by disable. An unchanged startup can skip database reconciliation
and bootstrap XPIStates.enabledAddons directly. JSONFile._save also catches
ordinary IO errors, so calling it directly or setting its delay to zero would not
provide the required completion/error guarantee.

## Change and boundaries

Android alone gets a serialized, coalescing writer. It writes extensions.json
first, then addonStartup.json.lz4, each through its own atomic temporary path with
IOUtils flush:true. A request arriving during IO causes another write pass. Any
failure rejects waiting callers and keeps dirty work for a later retry, without
an automatic retry loop. There is no timer, sleep, shutdown-only acknowledgement
or concurrent writer using the same temporary path. These are two atomic files,
**not** an atomic transaction across both files; startup reconciliation handles
process death between them.

Android database/cache changes both use that writer. Disable, enable, removal,
verified install/update and temporary/builtin activation await it before their
completion boundary. onDisabled, onEnabled, onUninstalled and install-completion
notifications follow successful persistence. Same-value disable/enable calls
still reach the barrier after a failed write. Removal failure retains dirty
absence for the next save; its old wrapper is no longer a current installed
instance, so that stale wrapper is not a general retry handle. Disk IO AbortError
also rejects rather than acknowledging a successful operation.

A per-extension queue orders lifecycle operations. A queued operation rejects a
removed/superseded wrapper; an update queued behind removal is cancelled. An
update refreshes the current disabled/embedder state after acquiring the queue.
The existing same-version reinstall path calls the internal state mutation while
holding the queue, avoiding recursive acquisition. Existing signature, manifest,
origin, add-on type, install prompt, policy and locked-location checks remain.
This is general extension handling, with no uBO ID or trust special case.

Pending uninstall is excluded from Android enabled state, including startup
reconciliation. The public cancelUninstall API remains void: its synchronous
return is **not** a durable acknowledgement. Android queues its mutation and emits
the existing operation-cancelled notification after persistence; rejected work
is reported with Cu.reportError. Theme selection retains its existing reentrant
state-change behavior rather than sharing the extension operation queue.

Before Android scans or schedules backgrounds it loads the database identities,
scans the actual locations and runs the existing reconciliation. Only known
installed identities can be recovered from an older cache in locations that do
not accept sideloads; unknown files retain the original sideload restrictions.
The scan also notices removed files even with startupScanScopes=0. Database/cache
mismatches in either direction are resolved from installed state, and failed
reconciliation propagates out of startup before the normal background loop.
Existing manifest/signature validation still handles newly discovered metadata.

Desktop keeps DeferredTask/JSONFile and its startup shortcut. The original cache
write error classification is shared by both writers. AddonTestUtils' explicit
flush helper selects the Android writer, and its existing write-error telemetry
test now injects real rejected Android IO while retaining the desktop JSONFile
case. No production test-only compatibility shim was added.

## Replay and evidence

Source was copied read-only from librewolf-153.0esr-1-beta-20260908. The seven
unchanged input files are preserved in source-baseline.tar.gz; source-files.json
pins all nine before/after paths. The worktree base is 8ef8b2a. No frozen beta
source, APK, VM, emulator, release key or signing state was modified.

```sh
python3 scripts/tests/test-addon-state-durability.py
python3 scripts/tests/test-addon-state-durability.py --source /path/to/patched/gecko
python3 scripts/tests/test-addon-state-durability.py --apk /path/to/candidate.apk
```

The replay validates the baseline hashes, applies the actual production patch
with zero fuzz/no offsets, checks every resulting source hash, parses changed JS,
and runs 31 tests against the actual writer, XPIStates and XPIDatabase objects,
and actual lifecycle/install/scan methods. Filesystem and bootstrap execution are
explicit host-test boundaries; they are not a running Gecko engine. Each test has
a bounded timeout, so an unresolved queue cannot silently exit as success.

source-tests.txt records all 31 passes. They cover both-file completion and
flush/atomic-write options; IO gates and concurrent writes; both-file failures,
AbortError and same-choice retry; ordered disable/enable; removal and pending
uninstall/cancellation; stale handles; retry after error; retained desktop
writers; DB-before-scan/reconcile-before-background ordering; failure propagation;
both cache/DB directions; known first-install recovery versus unknown files;
actual missing files; invalid/system/locked-location controls; first-install and
listener cancellation; toggles while uninstall remains pending; and verified-update
state propagation, write failure, removal race and same-version reentry.

The optional APK check compares all four production modules byte-for-byte inside
assets/omni.ja and prints that APK's SHA256. It has not run on a new candidate.
Source tests do not exercise Gecko's native filesystem, shutdown phases, real
extension startup/listeners, signature verifier or browser navigation.

Target tests to run after packaging:

```sh
./mach xpcshell-test toolkit/mozapps/extensions/test/xpcshell/test_android_addon_state.js
./mach xpcshell-test toolkit/mozapps/extensions/test/xpcshell/test_addonStartup_save_failures.js
./mach xpcshell-test toolkit/mozapps/extensions/test/xpcshell/test_XPIStates.js
```

The new Android xpcshell test reads both real files directly after acknowledged
install/disable/enable/concurrent toggle/update/removal, before any test flush or
shutdown. It also tests write rejection/retry, injects old-profile mismatches in
both directions after shutdown, captures attempted background startups, removes
one known install from the cache, and removes an actual XPI while retaining old
metadata. These Gecko test definitions are syntax-checked but **not run here**.

Root owns final target integration, compilation and runtime acceptance. Repeat
the existing real extension blocking/allowed request controls with immediate
force-stop after each acknowledged disable, enable, removal and update. Compare
registry, XPI memory, disk state, policy/listeners and real network results; verify
normal/private behavior and no browser hang after removal. Keep old inconsistent
profile recovery separate from fresh successful-operation durability. Run the
required browser smoke/pref gates and preserve exact candidate/source bindings.
