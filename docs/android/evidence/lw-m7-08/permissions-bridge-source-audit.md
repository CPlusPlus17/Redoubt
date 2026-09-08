# Android WebGL and canvas permission bridge: source audit

Read-only audit by `parity_gates`, 2026-09-08. All paths and line numbers below
refer to the actual frozen source directory
`librewolf-153.0esr-1-beta-20260908/` in this checkout. No source or guest build was
changed. Findings labelled **read** come from source opened during this audit;
the implementation design is a recommendation, not compiled or tested code.

**Recommendation:** attach Android requests to the originating inner window and
its existing `GeckoViewPermission` JSWindowActor, derive the principal in that
actor's parent, and reuse GeckoView's content-permission transport and Fenix's
site-permission UI. Carry session/persistent lifetime in the decision itself.
Do not enable `librewolf.webgl.prompt` until the whole path, including
OffscreenCanvas, reload and revocation, is built and behavior-tested.

## What is actually missing

| Read source | Finding and implementation consequence |
|---|---|
| `dom/canvas/ClientWebGLContext.cpp:845–977` | `GetWebGLPermission` tests the **requesting principal** for type `webgl`. Unknown permission produces an asynchronous prompt attempt and returns false immediately. A later allow cannot repair the already failed synchronous `getContext` call. |
| `dom/canvas/ClientWebGLContext.cpp:1008–1017` | The common patch applies that check only when `mCanvasElement` is nonnull. OffscreenCanvas WebGL bypasses it. Simply enabling the Android preference would leave a real bypass. |
| `dom/canvas/CanvasUtils.cpp:96–130,175–368` | Canvas uses type `canvas`, also on the requesting principal. Third-party blocking can return before any prompt; pre-user-input extraction can request a **hidden** doorhanger. Preserve these restrictions. |
| `dom/canvas/CanvasUtils.cpp:374–402,539–561` | A `canvas` allow bypasses both extraction denial and canvas/WebGL pixel randomization. The UI must identify this as an exception for reading actual canvas pixels, separate from permission to create WebGL contexts. |
| `dom/canvas/CanvasUtils.cpp:404–532` | OffscreenCanvas has both main-thread and worker paths. The worker prompt already dispatches through `WorkerProxyToMainThreadRunnable` and the ancestor window. Windowless workers cannot identify a browsing UI and must remain protected. |
| `dom/ipc/BrowserParent.cpp:4099–4144` | Both current prompt receivers require `mFrameElement->AsBrowser()` and return if absent. The existing desktop observer path cannot be the Android bridge. The IPC payload is an origin string and does not bind an individual originating inner window. |
| `browser/modules/CanvasPermissionPromptHelper.sys.mjs:47–96` | Desktop canvas grants/denials use `EXPIRE_NEVER` only when Remember is checked; otherwise `EXPIRE_SESSION`. Remember is hidden in private windows. This helper does not reload the page. |

An Android implementation must distinguish WebGL context creation from canvas
readback. Granting WebGL must not silently grant canvas extraction, disable RFP,
or exempt other sites. Existing canvas readback calls can be retried after the
grant; many real pages need an explicit reload because they made a synchronous
attempt during initialization. Offer a clear Reload action for that case.

## Existing content-permission path, with its actual limitations

1. **Read:** `dom/interfaces/base/nsIContentPermissionPrompt.idl:39–103` defines
   the request's principal, top-level principal, window or element, gesture and
   delegation information, and `notifyShown`/`allow`/`cancel` methods.
2. **Read:** `dom/base/nsContentPermissionHelper.h:95–166` supplies
   `ContentPermissionRequestBase`. Its constructor in the `.cpp:412–440` captures
   the principal, window, top principal and gesture/delegation state. Subclasses
   implement `Allow` and `Cancel`; `GetTypes` creates the typed XPCOM array.
3. **Read:** `nsContentPermissionUtils::AskPermission`, `.cpp:269–335`, requires
   a current inner window in the content process, obtains its BrowserChild and
   sends `PContentPermissionRequest` with the principals and tab ID. The parent
   route obtains `@mozilla.org/content-permission/prompt;1`.
4. **Read:** `dom/ipc/ContentParent.cpp:5294–5332` resolves the top browser from
   the sending process and tab ID, creates a permission proxy with its owner
   element, then initializes it. These particular methods do **not** visibly
   validate the supplied principal against a current frame document. This audit
   does not promote generic IPC deserialization into proof of that validation.
5. **Read:** `mobile/shared/components/geckoview/GeckoViewPermission.sys.mjs`
   implements the prompt service. `promptPermission:129–235` requires one type,
   applies the notification gesture check, obtains the actor and sends
   `GeckoView:ContentPermission` with the serialized principal, URI, private
   mode, context ID and request ID. It tracks `notifyShown` and rejects errors.
6. **Critical read:** that method chooses `aRequest.topLevelPrincipal` for every
   type except `storage-access`. Reusing it unchanged for `canvas` or `webgl`
   would write an exception for the top site while their enforcement checks the
   requesting frame. It also writes every ordinary reply with `EXPIRE_NEVER`.
7. **Read:** `mobile/shared/actors/GeckoViewPermissionParent.sys.mjs:37–42`
   forwards `getContentPermission` to the session's event dispatcher.
   `mobile/shared/modules/geckoview/GeckoViewActorParent.sys.mjs:12–34` derives
   that dispatcher from the top embedder's chrome window; it is not a global
   activity guessed from an origin string.
8. **Read:** `mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoSession.java:1139–1151`
   calls `PermissionDelegate.onContentPermissionRequest` and resolves its
   `GeckoResult<Integer>`. `ContentPermission` carries a private serialized
   principal, URI, private flag, context ID and request ID. Its type mappings at
   `7334–7400` have no `canvas` or `webgl`; unknown types map to -1 and stored
   unknown permissions are filtered out at `7405–7416`.
9. **Read:** current permission constants are 0–10, ending with local device
   and local network access (`7166–7213`). `GeckoSession.Permission`'s `@IntDef`
   at `7678–7693` even omits those existing last two constants. Extend the enum,
   both mapping directions, the annotation and `mobile/android/geckoview/api.txt`
   together. Do not reuse another permission's number.

There is a usable C++ subclass pattern in
`dom/media/autoplay/GVAutoplayPermissionRequest.{h,cpp}`: asynchronous dispatch,
one pending request per page/type, and cancellation when the context disappears.
Its per-page status design is useful for deduplication, not an instruction to
make a synchronous WebGL call wait. If the implementation uses a new
`ContentPermissionRequestBase` subclass instead of the actor adapter below, note
that `ShowPrompt` calls `CheckPermissionDelegate`: unknown types are denied by
`extensions/permissions/PermissionDelegateHandler.cpp:181–206`. Such a design
also needs explicit requesting-origin delegation entries and the corresponding
`DELEGATED_PERMISSION_COUNT` change. Calling `ShowPrompt` with an empty testing
pref prefix asserts; the autoplay class deliberately dispatches the request
directly instead. Avoid either accidental behavior.

## Recommended origin-bound interception

This design needs no new origin-string IPC and no new `PWindowGlobal` message.

1. Add an Android-only helper at the existing canvas/WebGL prompt call sites.
   It captures the **inner** window and requesting principal, verifies that they
   match, and dispatches a runnable before notifying an observer. The observer
   subject is that inner window; data contains only an allowlisted permission
   kind and the quiet-prompt flag. Existing desktop code remains its own path.
   Recheck currentness and principal equality in the runnable. Do not dispatch
   script from an unsafe canvas operation stack.
2. Add the observer topics to the child registration of `GeckoViewPermission`
   in `mobile/shared/components/geckoview/GeckoViewStartup.sys.mjs:60–69`, and an
   `observe` handler to `mobile/shared/actors/GeckoViewPermissionChild.sys.mjs`.
   **Read:** `dom/ipc/jsactor/JSWindowActorProtocol.cpp:208–254` specifically
   accepts an inner-window observer subject, obtains *that window's*
   WindowGlobalChild, creates its registered actor and invokes its observer.
   Thus the native denial site can reach the existing actor without inventing
   another parent-process origin reconstruction mechanism.
3. The child sends a bounded message containing the kind and quiet flag. In
   `GeckoViewPermissionParent.sys.mjs`, derive the principal from
   `this.manager.documentPrincipal`, not from a URI in that message. Reject a
   discarded/noncurrent WindowGlobal, missing embedder/dispatcher, null or
   privileged principal, unsupported type and malformed metadata. Capture the
   manager and principal, then recheck currentness and equality after awaiting
   the Android decision and **before** any permission write or reload.
4. Refactor a narrow helper from `GeckoViewPermission.promptPermission` to reuse
   its Android transport, request-ID/`notifyShown` handling and result validation.
   The new origin-bound entry uses the supplied parent-derived **requesting**
   principal; normal permission types retain their existing delegation behavior.
   Include both frame origin and top site in cross-origin UI text. A frame grant
   must never be relabelled as an exception for the top site.
5. Deduplicate by current WindowGlobal and permission kind; preserve pending
   state and cancel on navigation, tab close and actor destruction. Do not let
   repeated `getContext`/canvas reads produce an unbounded queue of dialogs.
6. For OffscreenCanvas, use its existing worker-to-main-thread pattern, retain
   the worker's principal and require equality with the ancestor window's
   principal before using that window actor. Missing/closed/changed ancestors
   fail closed. Also enforce WebGL permission when `mCanvasElement` is null;
   copying only the current DOM-canvas branch leaves a bypass.

The generic actor is registered with `allFrames: true` and `includeChrome: true`.
That makes the content/principal checks in the new entry necessary. The proposed
adapter must explicitly define handling for opaque sandboxed and local-file
origins; the existing Fenix origin formatter is based on `java.net.URL`, not
proof that every possible principal is a supported site-settings key.

## Lifetime, revocation and the Android UI

**Read:** `GeckoPermissionRequest.kt:51–113` maps Gecko type constants to A-C
`Permission` subclasses, completes every merged result with only ALLOW or DENY,
and merges by URI plus permission list. `GeckoEngineSession.kt:1577–1586`
constructs that request and notifies observers. The new path needs explicit
decision lifetime; a mutable global “last permission choice” is unsafe for
concurrent tabs. Add a request-scoped, backward-compatible result/decision API
and corresponding A-C request methods. Preserve existing embedder behavior for
old permission types. Represent stored values as the existing 1/2/3 states;
session versus persistent is separate metadata, never an invalid stored state.

| Choice | Required engine behavior |
|---|---|
| Normal window, Remember checked | Exact requesting principal/type, ALLOW or DENY, `EXPIRE_NEVER`. |
| Normal window, Remember unchecked | Exact requesting principal/type, `EXPIRE_SESSION`; survives the deliberate reload and does not survive a browser restart/crash. Label the scope as this browser session. |
| Private window | No persistent checkbox; session only. Never call the permanent-private API. Closing the last private context removes the exception. |
| Dismiss/quiet attempt | Keep extraction/context protected; do not create a permanent denial merely because no choice was made. Show a usable blocked-attempt control without a modal when the native quiet flag requests that behavior. |
| Revoke/reset | Remove the exact permission (or restore prompt state), retain unrelated origins/attributes/types, update the visible state, and reload the affected document when necessary. |

These semantics match the desktop canvas helper's actual session/permanent
choice. The following existing Android behaviors need deliberate handling:

- **Read:** `GeckoViewPermission.sys.mjs:226–232` writes generic replies as
  `EXPIRE_NEVER`. `GeckoSitePermissionsStorage.kt:54–89` implements unchecked
  Remember by keeping a RAM list, then later replacing those permissions with
  PROMPT. `SitePermissionsFeature.kt:178–193,268–273` clears that list on **every
  loading event** and feature stop. A WebGL allow followed by reload would lose
  its grant. The RAM cleanup also cannot guarantee crash-safe temporary normal
  permissions. New session permissions must use real engine expiry and stay out
  of that navigation-cleared list.
- **Read, important correction:** ordinary private grants are protected even
  when the JS caller requests `EXPIRE_NEVER`: `extensions/permissions/PermissionManager.cpp:1999–2013`
  converts them to `EXPIRE_SESSION`; `3077–3081` clears them on
  `last-pb-context-exited`. The normal-mode temporary issue above must not be
  misreported as a proven private-mode persistence defect.
- **Read:** `GeckoViewStorageController.sys.mjs:133–170` exports permission
  values and principal metadata, but no expiration metadata. Its update route
  at `173–195` picks session only for private mode. Expose lifetime and preserve
  it when changing a session exception; editing some other permission must not
  promote a WebGL/canvas session grant into a permanent grant.
- **Read:** `GeckoSitePermissionsStorage.kt:166–179` clears host permission data
  before rewriting its mapped types, and `275–373` only merges Gecko state when
  a Room row is present. `areSame:460–463` compares host, permission and private
  mode, omitting scheme, port and session context. Do not copy those assumptions
  for new exceptions: use exact principal/attributes, preserve unrelated types,
  and construct an ephemeral UI model for engine-only session/private grants.
  Otherwise a grant can work while being invisible and impossible to revoke.
- **Read:** `SitePermissionsFeature.kt:468–489` and
  `OnDiskSitePermissionsStorage.kt:62,76,94` refuse private Room storage. Private
  state must remain engine/in-memory state, not a synthetic normal-mode row.
- **Read:** `SitePermissionsFeature.kt:374–393` completes the permission before
  its asynchronous persistence work. A new Reload action must wait until the
  chosen permission write is acknowledged, then verify the requesting document
  is still current. A fixed delay is not an acknowledgment.
- **Read:** Fenix's `BaseBrowserFragment.kt:1231–1260` supplies the existing
  permission feature and hides Remember in private mode. Existing LNA prompt
  branches hardcode that checkbox to true; new branches should use the actual
  requesting tab's private state instead of copying that hardcoding.
- **Read:** `TrustPanelMiddleware.kt:147–173` already updates a site permission
  and reloads its tab. The older `QuickSettingsController.kt:289–301` does the
  same. The new fields must be shown in both the active trust panel and supported
  older quick-settings UI, including quiet blocked attempts and session grants.

Room database migration is **not inherently required** if WebGL/canvas stay
exclusively engine-owned, as recommended: use existing origin rows for normal
persistent exception listing, and merge the real Gecko state into the two new
`SitePermissions` fields. Tests must prove those fields are never treated as
Room authority or lost when no row exists. If implementation instead stores them
in Room, it must extend the entity, version 9→10 migration, generated schema and
on-device migration test; adding fields without that migration is incomplete.

## Concrete patch surface

Paths below are relative to the frozen source. `AC` means
`mobile/android/android-components/components`; `F` means
`mobile/android/fenix/app/src/main`; `GV` means
`mobile/android/geckoview/src/main/java/org/mozilla/geckoview`.
The table is a proposed ownership inventory derived from the definitions and
call sites above; it does not claim every resource or test body was reviewed.

| Area | Required paths and edits |
|---|---|
| Native enforcement and prompt source | `dom/canvas/ClientWebGLContext.cpp`, `dom/canvas/CanvasUtils.cpp`; optionally a shared new helper/header and `dom/canvas/moz.build` instead of duplicate helper code. Cover DOM and OffscreenCanvas. |
| Android activation | `modules/libpref/init/StaticPrefList.yaml` via the Android WebGL default patch, only after verified prompting. Preserve the common desktop path. |
| Actor and prompt bridge | `mobile/shared/components/geckoview/GeckoViewStartup.sys.mjs`, `mobile/shared/actors/GeckoViewPermissionChild.sys.mjs`, `mobile/shared/actors/GeckoViewPermissionParent.sys.mjs`, `mobile/shared/components/geckoview/GeckoViewPermission.sys.mjs`. |
| GeckoView decision and storage API | `GV/GeckoSession.java`, `GV/StorageController.java`, `mobile/shared/modules/geckoview/GeckoViewStorageController.sys.mjs`, `mobile/android/geckoview/api.txt`. Add type mappings, explicit lifetime/quiet metadata and acknowledged writes. |
| A-C request and state | `AC/concept/engine/src/main/java/mozilla/components/concept/engine/permission/PermissionRequest.kt`, `SitePermissions.kt`, `SitePermissionsStorage.kt`; `AC/browser/engine-gecko/src/main/java/mozilla/components/browser/engine/gecko/permission/GeckoPermissionRequest.kt`, `GeckoSitePermissionsStorage.kt`. `GeckoEngineSession.kt` changes only if the chosen callback signature requires it. |
| A-C prompt behavior | `AC/feature/sitepermissions/src/main/java/mozilla/components/feature/sitepermissions/SitePermissionsFeature.kt`, `SitePermissionsRules.kt`, `SitePermissionsDialogFragment.kt` if needed for explicit Reload or lifetime controls, and `AC/feature/sitepermissions/src/main/res/values/strings.xml`. Extend supported types, granted checks, rule mapping, status updates, prompt construction, deduplication, quiet handling and Remember behavior. Generic facts use `permission.name`, so they need no new type switch. |
| Toolbar blocked/changed state | `AC/browser/state/src/main/java/mozilla/components/browser/state/state/content/PermissionHighlightsState.kt`, `AC/browser/state/src/main/java/mozilla/components/browser/state/action/BrowserAction.kt`, `AC/browser/state/src/main/java/mozilla/components/browser/state/reducer/ContentStateReducer.kt`. Distinguish no-decision blocked attempts from saved DENY. |
| Fenix settings model | `F/java/org/mozilla/fenix/settings/PhoneFeature.kt`, `settings/Extensions.kt`, `utils/Settings.kt`; `F/res/values/strings.xml`, `F/res/values/preference_keys.xml`. Add two phone features with empty Android OS permission lists, exact mappings and global default rules/listeners. |
| Fenix settings screens | `F/res/xml/site_permissions_preferences.xml`, `site_permissions_details_exceptions_preferences.xml`; `F/java/org/mozilla/fenix/settings/sitepermissions/SitePermissionsDetailsExceptionsFragment.kt`. `SiteSettingsFragment.kt` iterates `PhoneFeature.entries` and binds each required XML preference automatically; adding an enum without XML will crash its `requirePreference`. |
| Fenix current-site controls | `F/java/org/mozilla/fenix/settings/quicksettings/WebsitePermissionsView.kt`, `QuickSettingsFragmentStore.kt`, `QuickSettingsController.kt` as needed for exact-origin/lifetime/quiet behavior; `F/res/layout/quicksettings_permissions.xml`; `F/java/org/mozilla/fenix/settings/trustpanel/store/TrustPanelStore.kt` and `middleware/TrustPanelMiddleware.kt`. The trust panel iterates phone features but currently hides NO_DECISION; that must accommodate quiet blocked attempts. |
| Storage wrappers if signatures change | `F/java/org/mozilla/fenix/components/PermissionStorage.kt`, plus site-permission exception management fragments calling its update/delete APIs. Keep private-aware operations explicit. |

`SitePermissionsManageExceptionsPhoneFeatureFragment.kt` already implements
Allow/Block/Ask through generic `PhoneFeature` mappings (`121–149,231–252`), and
the details screen already has Clear Permissions (`153–178`). Extend those
existing routes instead of adding a separate untracked exceptions database.
Remember that Fenix `utils/Settings.kt`, Gecko startup and `api.txt` overlap the
ongoing defaults/uBO tasks; declare patch ordering/dependencies before writing.

## Tests that make the implementation reviewable

Existing test locations identified from filenames and source references follow.
Named methods and annotated lines were read; unannotated test files are an
inventory for the implementer, not a claim that their full contents were reviewed.

- GeckoView `src/androidTest/java/org/mozilla/geckoview/test/PermissionDelegateTest.kt`:
  notification round trip (`568`), context ID (`747`), allow/deny/prompt changes
  (`902/982/1069`), JSON conversion (`1142`), and LNA callback (`1205`). Extend
  these with both new kinds, origins/attributes, lifetime and stale-document
  rejection. `StorageControllerTest.kt` is the existing storage test location.
- A-C `browser/engine-gecko/.../permission/GeckoPermissionRequestTest.kt` tests
  type mapping, grants, rejects, merged requests and `notifyShown`;
  `GeckoSitePermissionsStorageTest.kt` covers storage merge/filter/update.
- A-C `feature/sitepermissions/.../SitePermissionsFeatureTest.kt`,
  `SitePermissionsRulesTest.kt`, `SitePermissionsDialogFragmentTest.kt`,
  `SitePermissionsTest.kt`, and `OnDiskSitePermissionsStorageTest.kt` cover the
  prompt, private Remember control, mappings and persistence. If Room changes,
  `src/androidTest/.../db/OnDeviceSitePermissionsStorageTest.kt:232–261` supplies
  the version-8→9 migration pattern; add 9→10 without dropping existing rows.
- Fenix `src/test/.../settings/PhoneFeatureTest.kt`,
  `settings/ExtensionsTest.kt`, `utils/SettingsTest.kt`,
  `settings/sitepermissions/SitePermissionsDetailsExceptionsFragmentTest.kt`,
  `SitePermissionsManageExceptionsPhoneFeatureFragmentTest.kt`,
  `settings/trustpanel/TrustPanelStoreTest.kt`, `TrustPanelMiddlewareTest.kt`,
  and existing `settings/quicksettings/*Test.kt` cover settings and UI state.
- Fenix `src/androidTest/java/org/mozilla/fenix/ui/SitePermissionsTest.kt` and
  `SettingsSitePermissionsTest.kt` exercise visible controls; extend the existing
  corresponding robots. Desktop
  `browser/base/content/test/permissions/browser_canvas_fingerprinting_resistance.js`
  provides a known-pixel canvas fixture, not Android runtime evidence.

Required runtime scenarios, with an allowed control in each relevant pair:

1. Fresh WebGL request is protected, real prompt/quiet control appears, Allow
   makes a new context and visible rendering work after retry/reload; Block and
   later revoke prevent new contexts. Exercise WebGL1 and WebGL2.
2. Known-pixel canvas remains protected by default, allowed readback equals the
   drawn pixels, and revoke restores protection. Exercise 2D, WebGL readback,
   `toDataURL`, `getImageData` and OffscreenCanvas/worker readback as applicable.
3. Same-origin and cross-origin frames, sandboxed opaque frames, nested workers,
   different ports/schemes, Gecko session context IDs, and private mode never
   grant a different principal. Navigate/close before answering and confirm no
   stale permission write. Flood requests and confirm bounded prompts.
4. Remember survives normal restart and appears in exceptions; unchecked
   Remember survives the needed reload but not process restart/crash; private
   decisions survive only the private session and never become normal grants.
   Change another permission and verify it does not alter either lifetime.
5. Quiet canvas denial before user input produces no modal storm and remains
   discoverable/actionable. Clear/reset removes the exact exception. Revocation
   of a live WebGL context requires a reload or explicit context destruction;
   the existing creation-time check does not revoke an already created context.
6. Repeat with incoming intents/custom tabs, background tabs, orientation change
   and restored activity. The decision must remain bound to the requesting tab
   and document, not whichever tab is selected when the callback returns.

Native C++ changes require rebuilt Gecko/native inputs for every supported ABI;
an old fat-AAR native library cannot validate this bridge. Then run GeckoView
instrumentation, relevant A-C tests, the full Fenix suite with the board subtraction
gate, APK smoke/pref audits and actual feature probes. This document establishes
implementation scope and source constraints only; none of those future checks
has been run by this audit.

## Source identity

SHA-256 of the load-bearing files read for this audit:

| Frozen source path | SHA-256 |
|---|---|
| `dom/canvas/ClientWebGLContext.cpp` | `d2884dcb671591e417f4eb92e2619d8f1ece4b2a445e2ae2c496a81e90ea76bc` |
| `dom/canvas/CanvasUtils.cpp` | `173c21ba6feafd6a2257e838263c30bb99c346747660f8798b5d97cd268ffc4f` |
| `dom/ipc/BrowserParent.cpp` | `fc3a313b23fdd450ffcfe7df7abce181394cfc7ddbca5c2d0d97419ed940f4b1` |
| `dom/ipc/jsactor/JSWindowActorProtocol.cpp` | `8d41622f7a21ee3922a69d58e16e6fa827ed74b84a9ee011130994f4d7c1192e` |
| `dom/base/nsContentPermissionHelper.cpp` | `6768d4e2aeb37056489e9af6f2aea19291573bdd3637536f6a51f482da7cd929` |
| `mobile/shared/components/geckoview/GeckoViewPermission.sys.mjs` | `44199b91bf3e62a54b19c2dcf9c57f18141635c99f58dc8236b69fd5d0c2d35b` |
| `mobile/shared/modules/geckoview/GeckoViewStorageController.sys.mjs` | `3203a5f639175e3255fb0e09d91e81b1750d821ef65bda61090ef3139df2488b` |
| `mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoSession.java` | `9cceed3cb00afa603555f038593025dc157642c31ed903cf592f0feaf8fa03f1` |
| `mobile/android/android-components/components/browser/engine-gecko/src/main/java/mozilla/components/browser/engine/gecko/permission/GeckoSitePermissionsStorage.kt` | `e28e539d133f3846ec570d377aa58c363346f6be5cc7d4861482f7774aacc45e` |
| `mobile/android/android-components/components/feature/sitepermissions/src/main/java/mozilla/components/feature/sitepermissions/SitePermissionsFeature.kt` | `616cba31ef250ac14805fcf23ca677f107a16bb7e090366d6e94fe2fe58d95ed` |
