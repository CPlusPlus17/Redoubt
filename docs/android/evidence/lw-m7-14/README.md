# LW-M7-14 implementation and integration handoff

Status: complete source implementation candidate; **not task completion**. Native ABI builds, affected Android test execution and the built-APK permission/rendering checks have not been performed by this task. No frozen source, VM, installed APK or release artifact was modified.

## Baseline and patch

Worktree branch `android/LW-M7-14` started from repository `982a3fb`. A task-private sparse Gecko checkout copies the frozen `librewolf-153.0esr-1-beta-20260908` targets and applies the repository's current `ubo-readiness.patch`, `ubo-preinstall.patch` and `privacy-defaults.patch` before committing its baseline (`a759e38`). `canvas-webgl-permissions.patch` is the diff against that baseline. Its 36 exact source paths are owned in `tasks.yaml`; the patch is registered after its predecessors in `android.txt`.

The complete patch enables `librewolf.webgl.prompt` on Android together with its usable permission controls. Earlier candidates and the untouched frozen source retain the historical false default. Never apply the default change without the accompanying bridge/UI.

## Implemented behavior

- Android DOM and OffscreenCanvas WebGL creation consult the exact requesting principal's `webgl` permission. Worker lookups run on the main thread, and worker prompts require an active ancestor window with an equal principal. Unowned service/shared workers cannot manufacture a document prompt; a matching existing exception still participates in their permission lookup.
- Canvas readback uses the existing RFP targets, placeholder/randomization machinery and privileged exemptions. Android changes its permission lookup to exact-origin matching and routes both DOM and OffscreenCanvas prompts, including quiet pre-gesture attempts, through the document actor.
- Native observers are queued outside script-unsafe canvas calls, capture the original inner window/principal, and recheck full activity and principal equality. The child supplies only an operation kind and quiet flag. The parent derives its own principal, validates HTTP(S) content principals and active/current WindowGlobal identity, and deduplicates by operation/document. Pagehide and actor destruction cancel pending choices, including BFCache transitions.
- GeckoView exposes additive WebGL/canvas kinds, explicit decision lifetime, real expiry metadata and acknowledged write/reload methods. ALLOW and DENY default to `EXPIRE_SESSION`; Remember selects `EXPIRE_NEVER` only for normal browsing. Dismissal leaves existing state alone. Pending responses cannot overwrite an intervening permission choice.
- Stored edits compare exact principal, value, expiry and modification time in one parent-thread turn. A stale edit cannot recreate a revoked/private-ended record. Ask/reset removes only that exact kind and principal. The existing global private-isolation policy is preserved; runtime evidence must record effective `permissions.isolateBy.privateBrowsing` (default true).
- Fenix has an engine-owned permission model and controls; temporary/private records never enter Room. Generic host-keyed requests do not consume the new requests. The legacy storage writer resets only the legacy records it rewrites instead of clearing every permission for a host.
- An explicit request choice waits for Gecko's write acknowledgment, then `reloadIfCurrent()` checks the original WindowGlobal/principal again and reloads that browsing context without another asynchronous boundary. A frame request reloads that frame. Saved-record edits have a separate explicit Reload page action after the acknowledged update. WebGL revocation prevents new contexts; reload discards contexts that already existed.

UI routes, lifetime labels and stable resource selectors are in [android-ui-handoff.md](android-ui-handoff.md).

## Evidence obtained

- `origin-permission-unit-test.cjs` executes the actual patched permission service, parent/child actors and storage module with small platform doubles. **37/37 tests pass**, with no skips. Coverage includes exact frame origins, private/context/port/subdomain separation, invalid replies, lifetime choices, stale same-origin documents, cached/inactive ancestors, pagehide cancellation, concurrent reloads, failed writes and compare-and-update revocation races. See the TAP output.
- The full generated patch applied cleanly to a second fresh sparse baseline. All 36 resulting files match `source-sha256.txt`; the 37 JavaScript tests also passed against that replay. This proves patch replay, not native IPC behavior.
- All 21 changed/new Kotlin files pass the compiler PSI syntax parser. Three XML resources parse, and new string/ID references resolve. Both changed Java API files were parsed/formatted with google-java-format 1.36.1. JavaScript syntax checks and `git diff --check` in the patched source checkout pass. These are syntax checks, not target compilation.
- Board check: `ok: 100 tasks, 23 waves, 0 warning(s)` in this branch before root's subsequent task additions.
- `board.py --check-scope` awaits the root-owned PATCH-SCOPE inventory update (29 → 30 Android patches; 89 → 90 total). `check-patch-order.py` awaits six new pair classifications listed in [patch-order-review.md](patch-order-review.md). Those shared audit files were not edited by this task.

## Tests authored for integration

25 A-C/Fenix unit tests cover requests, storage, state identity, quiet UI lifecycle, exact-origin labels, private/session choices, delayed acknowledgment and legacy-storage preservation. See the Android UI handoff for classes.

`org.mozilla.geckoview.test.CanvasPermissionTest` adds eight native integration tests:

1. WebGL1/2 through DOM, OffscreenCanvas, dedicated workers, nested workers and transferred canvas: protected before allow, usable after matching grant, protected for new contexts after revoke.
2. Known-pixel 2D readback through the same five canvas/worker modes: protected before allow, exact pixels after allow, protected after revoke.
3. WebGL1/2 clear/readPixels requires both context permission and canvas readback permission, and revoking canvas protects readPixels again.
4. Stored record serialization cannot restore a live request/reload capability or recreate a revoked record.
5. Same-origin navigation rejects an old pending decision and reload capability.
6. Private grants stay session-only, have a distinct principal and do not change normal persistent choices.
7. A cross-origin, different-port frame grant does not grant its parent or the same child hostname at another port.
8. An acknowledged frame reload preserves the top document and cannot run twice.

These definitions have not run on Android. Instrumentation controls test prefs deliberately; the release APK acceptance harness must additionally exercise the shipped defaults and real Fenix controls without pref injection.

## Compiler/runtime handoff

Root owns the build VM and all integrated tests. Apply the patch after the named predecessor patches, update the ordered audit registries, then:

- Rebuild native Gecko for arm64-v8a, armeabi-v7a and x86_64. This patch changes C++, so reusing an old native library cannot validate it.
- Compile the GeckoView API and instrumentation target (including API signature validation), affected A-C modules and Fenix. Run the new A-C/Fenix test classes, the relevant existing suites, and the full Fenix unit suite followed by `board.py --check-fenix-tests` using the actual current XML directory.
- Run `CanvasPermissionTest` against the new native build. In particular, acknowledgment of parent permission-manager writes does not by itself prove child IPC propagation/readback; successful rendered pixels after the actual reload must establish that.
- Root's ordered LW-M7-18 runtime harness must replace the old L1 smoke assertion that requires prompt=false. Use the supplied stable controls to establish default blocking, quiet discoverability, Allow/Block, Remember/session/private choices, real WebGL1/2 pixels and 2D readback, exact frame/port isolation, reload, revoke, cold process restart and private teardown. A connected adb or successful install is insufficient.
- Run the resulting smoke and pref audit. Record effective isolation/RFP/WebGL prefs, APK and native artifact hashes, the actual device/ABI and process restart evidence. Confirm session exceptions disappear after process restart and private exceptions after the last private context exits, while explicit normal remembered choices survive.

Keep LW-M7-14 incomplete until those target builds/tests and runtime assertions pass. Source implementation, syntax checks and mocked bridge tests are not substitutes for those gates.

Targeted commands, from the configured Android Gecko source checkout (project names are from `mobile/android/android-components/.buildconfig.yml`):

```sh
./mach gradle :components:browser-engine-gecko:testDebugUnitTest --tests 'mozilla.components.browser.engine.gecko.permission.OriginBoundPermissionRequestTest' --tests 'mozilla.components.browser.engine.gecko.permission.OriginBoundPermissionsStorageTest' --tests 'mozilla.components.browser.engine.gecko.permission.GeckoSitePermissionsStorageTest'
./mach gradle :components:browser-state:testDebugUnitTest --tests 'mozilla.components.browser.state.ext.PermissionRequestTest'
./mach gradle :fenix:testDebugUnitTest --tests 'org.mozilla.fenix.browser.permissions.OriginBoundPermissionsFeatureTest' --tests 'org.mozilla.fenix.browser.permissions.OriginBoundPermissionsDialogFragmentTest'
./mach geckoview-junit org.mozilla.geckoview.test.CanvasPermissionTest
```

The broader Fenix suite/subtraction and release smoke remain additional gates. The root integration branch already has a later cookie patch; its global totals become 31 Android / 91 overall after graphics registration, whereas the recorded scope failure above is from this task's frozen repository branch.
