# LW-M7-14 Android permission controls — source handoff

The A-C/Fenix implementation is in the task-private `source` tree. `source-paths.txt` and `source-sha256.txt` bind this handoff. Native/GeckoView files belong to the parent agent and are not inventoried here.

## Behavior

- `GeckoPermissionRequest.OriginBoundContent` implements `OriginBoundPermissionRequest`; requests retain a unique ID, exact principal attributes, requesting origin, top-level origin, quiet flag and real engine lifetime. They cannot merge with a different document solely because its URI matches.
- New grant defaults use browser-session lifetime. Explicit Remember requests persistence only for normal browsing. Generic reject/dismiss uses PROMPT, not a stored denial. The engine enforces actual expiry and stale-document rejection.
- The generic SitePermissionsFeature skips this new request type; the new Fenix feature owns its prompt/quiet notice and observes native completion to consume stale quiet requests. Stopping or rotating the feature does not invent a decision or consume an unresolved request. Native cancellation or failure idempotently rejects the Android callback before consuming the stale request, releasing both sides of the transport.
- Exceptions remain engine-owned. `listOriginBoundPermissions` includes real persistent/session/private records without a Room row, filters by private mode and session context, and shows exact scheme/host/port. `updateOriginBoundPermission` matches a current snapshot and waits for the native acknowledged mutation. The native setter separately compares value, expiry and modification time atomically.
- Legacy permission updates reset only the known legacy records they will rewrite. They no longer clear all permissions for a host, which would erase or race with canvas/WebGL exceptions. Legacy host-keyed single-site removal leaves the new exact-origin records to their explicit controls. Global Remove All still removes all permissions.
- Current-site dialogs list requests for that tab and all stored exceptions in its browsing context, explicitly labelled as saved exceptions with exact website addresses. Settings opens normal browsing exceptions; private exceptions are reachable from the private tab's site controls and never appear in that normal list.

## User and smoke-test routes

1. Load a page that attempts WebGL or protected canvas readback. A quiet request shows a non-modal notice with Review. Ordinary requests open the permissions list. The persistent route is the toolbar's site/trust panel → **Canvas and WebGL permissions**. The older quick-settings sheet contains the same entry. Settings → Site Settings also contains it.
2. Pick a pending row by kind and exact requesting origin. Review shows the requesting origin and, for frames, its top-level page origin. Remember is initially unchecked and describes browser restart persistence. Private mode has no visible Remember checkbox.
3. Press Allow or Block. The exact request completes, `awaitDecisionApplied()` must acknowledge the write, then native `reloadIfCurrent()` rechecks the original WindowGlobal/principal and reloads its browsing context. Frame requests reload the frame. A stale request never reloads a replacement or selected tab. Ask / reset on a pending request leaves protection in place without storing a denial.
4. Reopen the list to see the saved entry's Allowed/Blocked state and Remembered/This browser session/This private session lifetime. Pick it to change Allow/Block or Ask / reset. For a saved entry, Ask / reset invokes the engine's exact-principal removal.
5. A successful saved-entry edit offers a separate **Reload page** confirmation. This is a new explicit action on the tab used to open the controls, performed only after storage acknowledgment; it is not represented as an old-document-bound request reload.

## Stable runtime selectors

All native view IDs are in `org.redoubtbrowser:id/` at runtime (use the built application package if changed).

| Control | Resource ID / Compose tag |
|---|---|
| Trust-panel entry | Compose `origin_permissions_entry`, exposed with `testTagsAsResourceId` |
| Older quick-settings entry | `origin_permissions_entry` |
| Dialog list | `origin_permissions_dialog_list` |
| Pending rows | `origin_permission_pending_webgl`, `origin_permission_pending_canvas` |
| Saved rows | `origin_permission_saved_webgl`, `origin_permission_saved_canvas` |
| Requesting origin/frame explanation | `origin_permission_request_origin` |
| Remember checkbox | `origin_permission_remember` |
| Allow / Block | `origin_permission_allow`, `origin_permission_block` |
| Pending Ask action | `origin_permission_ask` |
| Saved exception Ask/reset action | `origin_permission_reset` |
| Explicit saved-edit reload | `origin_permission_reload` |

Multiple rows may share a kind ID; select by exact origin text as well. Native permission dialogs use Android view IDs; the trust panel's Compose tag may be exposed without a package prefix.

## Tests and validation status

25 meaningful unit tests were authored across Fenix (12), browser state (2), Gecko request/lifetime (5), Gecko storage (5), and legacy storage preservation (1). They cover delayed acknowledgment, stale/closed/background tabs, private/context isolation, quiet modal suppression and invalidation, stopped feature retention, exact frame text, Remember visibility, request identity, private/session lifetime, engine-only listing, exact-port revocation, missing records, and legacy broad-clear removal.

Completed local checks:

- Kotlin compiler PSI parser: all 20 changed/new Kotlin files parse with zero syntax errors.
- Three resource XML files parse; every new origin permission string and ID reference resolves.
- `git diff --check` in the patched source checkout passes.

**Not yet performed by this subtask:** target compilation, execution of these unit tests, full Fenix subtraction gate, GeckoView instrumentation, built APK/runtime probes, ABI native rebuilds or smoke/pref audits. These remain required integration work; syntax checking is not compilation and authored tests are not passing tests. No guest build or release artifact changed in this subtask.

Repeat PSI check with `python3 ui-checks/check-kotlin-syntax.py` from the task root. It uses the local Kotlin 2.3.10 compiler cache and JDK compiler module. To include other files, pass absolute Kotlin source paths; for example `python3 ui-checks/check-kotlin-syntax.py source/mobile/android/geckoview/src/androidTest/java/org/mozilla/geckoview/test/CanvasPermissionTest.kt`. Output is written to `ui-checks/kotlin-syntax.txt`. The helper `KotlinSyntax.java` is syntax-only and intentionally cannot report a target build as passed.
