# LW-M7-18 graphics runtime acceptance runner

Status: **implemented; built-APK acceptance pending**. Host tests validate the
grader, exact UI selection, fixture transport and failure paths. They do not
establish Android rendering, permission propagation or working Fenix controls.
No device, APK installation, guest build or guest mutation was performed by this
subtask. Root owns live integration after the LW-M7-14 native rebuilds.

## Run against the installed release

Use a dedicated, already initialized test profile, an English Fenix UI, no
pre-existing private tabs, an installed non-debuggable APK, and the standard
transport-only Marionette configuration already enabled by the existing smoke
setup. The runner starts two host loopback fixtures and its own adb reverse and
Marionette forwarding. It does not install, wipe, modify preferences, write engine
permissions, create debug configuration or change Android's debug-app setting.

From the repository root:

```sh
python3 scripts/android-graphics-smoke.py \
  --adb /path/to/platform-tools/adb \
  --serial emulator-5554 \
  --package org.redoubtbrowser \
  --apk /path/to/the-installed-release.apk \
  --dedicated-test-profile \
  --work /path/to/graphics-evidence
```

`--apk` checks the supplied file's SHA256 against the installed APK. Installed
base/split hashes and package flags are recorded even without that argument.
`--marionette-port PORT` can reuse an existing host forward; otherwise the runner
creates and removes its own forward to device port 2828. A different device port
requires `--device-marionette-port PORT` and an exactly matching existing config.
Only successfully created mappings are removed, including after failures.

For the first integration attempt, add `--stop-after-core`. It exercises the full
core rendering/consent/revoke sequence, then deliberately returns **3/PENDING**;
it cannot represent complete lifetime and frame acceptance.

The accepted `/data/local/tmp/org.redoubtbrowser-geckoview-config.yaml` contents
are the existing smoke harness's transport setup:

```yaml
args:
  - "-remote-allow-system-access"
env:
  MOZ_MARIONETTE: "1"
prefs:
  remote.prefs.recommended: false
  marionette.port: 2828
```

This is a description of the prerequisite, not a configuration write performed
by this runner. Extra entries, duplicated entries, injected privacy preferences,
recommended-pref injection or unknown contents taint acceptance and return
PENDING. Evidence stores the config hash and verdict without copying unknown
values. Effective graphics, fingerprinting, private-isolation, HTTPS-only and DoH
preferences are read and recorded. The runner requires the shipped quiet WebGL
gate, usable WebGL and private permission isolation. It never changes those
values. LW-M7-11 remains responsible for the broader preference/network audit.

## Actual acceptance flow

1. Launch the parser-loaded loopback fixture through the real Fenix intent
   receiver before starting the Marionette session. Find its exact current,
   active Gecko document without focusing a background tab. Require default
   blocked WebGL1/2 and protected 2D readback. Test DOM canvas, OffscreenCanvas,
   dedicated workers, nested workers and transferred canvas workers separately.
   Quiet attempts must not automatically open the permission list or dialog.
2. Open the real Review action or toolbar site controls, then the graphics
   permission list. Choose the WebGL request by exact origin and kind; require
   unchecked Remember, tap Allow, observe the engine's acknowledged session
   record and replacement document. A fresh canvas attempt in that document
   produces the canvas request; repeat the actual Allow flow. Require every
   RGBA byte of a random four-quadrant 32×32 challenge for both WebGL versions
   and 2D across all five modes.
3. Reset the saved canvas exception, explicitly choose Reload page, and require
   protected readback while WebGL contexts still work. Change the saved WebGL
   choice to Block, reload and require blocked contexts. Reset it through the
   saved control, reload and require default protection again across all modes.
4. Grant both kinds with Remember unchecked, verify real pixels, terminate and
   relaunch the actual app process, and require absent records plus protection.
   Grant both with Remember checked; require persistent engine expiry, a second
   real process restart and restored real pixels.
5. Long-press the real tab counter and choose New private tab. Enter the fixture
   URL through the empty focused Fenix address field. Require protection despite
   the normal remembered exceptions. Grant both through private dialogs with no
   visible Remember control, require distinct private/session records and real
   pixels, then close the tab through the real Close tab action. Require the
   last private Gecko context to close and its records to disappear. A second
   private tab must start protected; the normal remembered choices must survive.
6. Load a parent fixture with a child of the same host on a different port.
   Require child protection despite the parent's remembered consent. Select
   requests by the child's exact origin and require the dialog to name the
   parent. Native request decisions must reload only the requesting frame.
   Require actual pixels across all five modes. Revoke child exceptions using
   saved controls and their explicit tab reload, then require protected child
   behavior while the parent remains allowed. Finally remove the test's normal
   exceptions using the same UI controls.

Graphics work runs in parser-inserted page JavaScript using an HTTP command
channel. Marionette only observes preferences, exact-principal records and
document identity. It does not invoke content-permission callbacks or perform
graphics inside a privileged sandbox. Every command binds a random command ID,
document ID, exact origin, operation and worker mode; the current document must
still match when the result arrives. Missing results, exceptions, incomplete
bytes and null allowed contexts fail. An error is never counted as protection.
After Allow, exact matching pixels are mandatory; before consent, complete 2D
readback must differ from that independent oracle.

The fixture uses ordinary `http://localhost:<port>` origins via adb reverse, so
it needs no HTTPS-only override or custom CA. The live origin-isolation case is
an embedded frame with a different port. Host tests additionally reject
subdomains, deceptive host suffixes, scheme changes and port prefixes when
selecting UI rows; those selector tests are not runtime principal-isolation
measurements. Private/lifetime stages exercise DOM operations; worker coverage
is exercised by the core and frame matrices. The runner does not claim BFCache,
process-swap or arbitrary cross-site third-party-cookie coverage.

## Selectors and reload contract

The runner reads the actual registered patch and the
[LW-M7-14 UI handoff](../lw-m7-14/android-ui-handoff.md). Native IDs are matched
exactly within the installed package; Compose tags may be unprefixed.

| Purpose | Resource ID / tag |
|---|---|
| Site-controls entry / list | `origin_permissions_entry`, `origin_permissions_dialog_list` |
| Pending exact-origin row | `origin_permission_pending_webgl`, `origin_permission_pending_canvas` |
| Saved exact-origin row | `origin_permission_saved_webgl`, `origin_permission_saved_canvas` |
| Origin explanation / lifetime | `origin_permission_request_origin`, `origin_permission_remember` |
| Decisions | `origin_permission_allow`, `origin_permission_block`, `origin_permission_ask`, `origin_permission_reset` |
| Saved-edit explicit reload | `origin_permission_reload` |

Multiple matching rows fail rather than selecting the first. The origin parser
compares scheme/host/port, not a text prefix. The list uses Close; the quiet
snackbar uses Review. Private-tab actions use the existing English New private
tab / Close tab menu text and the actual tab-counter ID/content description.
Unsupported layouts or localization fail with UI evidence; no coordinate guesses
or substitute engine grants are used. These selectors still require live APK
validation.

Pending Allow/Block follows the existing source route: Fenix decision → native
permission acknowledgment → `reloadIfCurrent()` → replacement requesting
document, or requesting frame. Saved edits first wait for the acknowledged exact
record change, then click the separate Reload page control, which reloads the
tab used to open the controls. Host tests enforce these distinct orders; real
IPC propagation remains part of the live run.

## Output and host verification

Each invocation creates `<work>/<run-id>/graphics-results.json`, written
incrementally. It contains the installed APK hashes, effective preference reads,
matching fixture permission records, lifecycle events, passed assertions and
artifact hashes. Artifacts include UI XML, optional PNG captures, raw command
responses (retained even when grading fails) and successful RGBA readbacks.
Failure diagnostics capture the current UI and relevant app crash-buffer output.
Only the fixture origins' graphics records are copied.

Exit **0/PASS** requires all core, lifetime, private and frame checkpoints and an
unchanged installed APK. Exit **1/FAIL** means an exercised assertion or cleanup
failed. Exit **3/PENDING** means missing prerequisites, unavailable transport,
interruption or deliberately partial coverage. A connected adb device, empty
results or a returning partial runner cannot pass. A failed run can leave test
tabs or test exceptions for inspection; it never clears unrelated data. Use the
dedicated test profile and its real controls to resolve leftovers before retry.

```sh
python3 docs/android/evidence/lw-m7-18/test-android-graphics-smoke.py
python3 docs/android/board.py --check
```

The host tests execute the actual grader/selector/HTTP fixture, Python protocol
extraction and fixture JavaScript syntax check. They exercise fake-adb absent and
connected negative controls without invoking a real device. See
`host-validation.json`, `host-tests.txt` and `board-check.txt` for this subtask's
executed results and input hashes. Android target compilation, full Fenix/Gecko
unit and instrumentation gates, three-ABI native builds, existing smoke and pref
audits, and this runner's live acceptance remain root integration requirements.
