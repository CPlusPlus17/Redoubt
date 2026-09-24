Task21 corrects the canonical host graphics harness for the exact extension-installed
notice observed in runtime 0189. It changes no app, native source, APK, preference,
permission, frozen capsule, or driver. Target recovery remains pending.

The nested graphics run `3ebfd7619ff31fa0` failed with 17 preliminary PASS checks
and `acceptanceComplete=false`: “No quiet Review action or real Fenix site-info
control was visible”. All three captured UI hierarchies instead expose the same
native bottom notice: “uBlock Origin was added”, the extension-settings description,
and OK. The archived original harness reproduces that exact failure on its XML.
The preceding quiet-no-automatic-dialog check was made while this modal obscured
the browser and is not sufficient evidence about the underlying permission UI.

`before-and-source.tar.gz` preserves the original graphics and smoke scripts from
42c063e, all three XML bodies, the screenshot, complete nested graphics evidence
archive and result, and four inspected product source files. `source-inputs.json`
binds each body's location, SHA256 and size. The product bodies come from the
retained `librewolf-153.0esr-1-beta-20260908` tree; no registered Android patch
names those four paths. They are source inspection evidence, not a new compiled
source receipt.

The source connects this UI to `AddonInstallationDialogFragment.createContainer`
and `mozac_feature_addons_fragment_dialog_addon_installed.xml`. Its exact title,
description and OK resources are in feature-addons values/strings.xml. The OK
listener invokes `onConfirmButtonClicked` and dismisses the dialog. Fenix
`WebExtensionPromptFeature.showPostInstallationDialog` binds that callback to
`consumePromptRequest`, which dispatches `ConsumePromptRequestWebExtensionAction`.
The extension-settings description link has a distinct navigation callback. This
is completion acknowledgment; it is not the extension permission/data choice.

The new selector requires all four leaf controls in one native RelativeLayout,
exact app package and resource IDs, native widget classes, exact English title
and description, non-checkable enabled/visible controls, and an actionable OK
button. Extra choices, split containers, other extensions, other packages,
malformed controls and generic OK/Allow buttons do not authorize a tap; duplicate
matching notices fail. This deliberately supports the captured English test UI.

The harness checks for this notice before the initial graphics probes, again
before the quiet assertions, and before opening real permission controls. Each
recognized notice gets one recorded OK tap. Only hierarchy reads retry while
waiting for its title to disappear. The existing before dump and screenshot and
the new after dumps/screenshots retain the action boundary. A timeout fails;
there is no repeated tap or blind Back. Quiet assertions use the refreshed
hierarchy, so an underlying automatic consent dialog or permission list still
fails. Subsequent real origin/kind/remember/reload checks are unchanged.

Run from the repository root:

    python3 docs/android/evidence/lw-m7-21/addon-installed-notice-correction/test_notice.py
    python3 docs/android/evidence/lw-m7-18/test-android-graphics-smoke.py
    python3 docs/android/evidence/lw-m7-12/protocol-recovery/test_protocol.py

Results: 17 new controls, 38 existing graphics controls and 13 protocol controls
PASS. New controls include the actual three captured XML bodies, the old failure,
strict negative selectors, a single write followed by read-only retries, timeout,
real site-controls continuation, pre-probe acknowledgment, and rejection of quiet
permission dialogs exposed after a later notice. An AST comparison preserves every
acceptance-check call and every existing function except `core` and
`open_permissions`, where the bounded acknowledgment calls are inserted; only
two helper functions are added. The smoke
script remains byte-identical. Task21 board/translation verification and whitespace
checks passed too; exact candidate hashes are in `validation.json`.

These are host controls. They do not convert the failed 0189 run into a pass, prove
that the modal closes on-device, or establish graphics permission/lifetime/frame
acceptance. Root must use a separately frozen replacement capsule and execute the
unchanged full acceptance gates against the retained APK/source identities.
