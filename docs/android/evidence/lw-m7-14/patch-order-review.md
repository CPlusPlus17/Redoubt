# Registration review for root's ordered audit task

The new patch was generated after the complete frozen Android patch stack plus the three current uBO/default predecessors, then replayed on an independent copy of that baseline.

| Existing patch | Relationship to canvas-webgl-permissions.patch | Opened-source evidence |
|---|---|---|
| android/webgl-prompt-default.patch | Required predecessor | New StaticPrefList hunk removes its Android false/default comment and conditional only with the complete bridge. |
| webgl-permission-common.patch | Required predecessor | New ClientWebGLContext hunks wrap the common patch's `GetWebGLPermission`/`IsWebGLAllowed` helpers and replace the Android call with the DOM/Offscreen helper. |
| android/ubo-preinstall.patch | Required predecessor | New Fenix strings hunk begins immediately after the predecessor's `librewolf_ubo_setup_*` strings; they are context, not duplicated by this patch. |
| android/ubo-readiness.patch | Disjoint edits, existing order retained | Shared api.txt additions occupy ContentPermission/StorageController regions; predecessor adds the uBO startup API elsewhere. GeckoViewStartup actor observer and storage event changes are separate from its uBO event handling. |
| android/no-crashreporter.patch | Disjoint edits, existing order retained | Shared strings.xml crash-reporting changes are separate from the new terminal permission string block. |
| fpp-canvas-fix.patch | Disjoint edits, existing order retained | Its ClientWebGLContext canvas extraction changes are separate from the added include and WebGL context-creation helpers. |

`privacy-defaults.patch` is also already in the generation baseline. Its current paths do not create a new shared-file pair here. No predecessor implementation is folded into the generated patch.

The global patch-count inventory and check-patch-order.py registry are root-owned audit edits; this task changes only its own registration line.
