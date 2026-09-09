# LW-M7-28 real add-on UI lifecycle runner

Implementation candidate. **Installed-device acceptance remains pending.** Host
tests exercise the real Python graders, source-derived UI acknowledgment rules,
HTTP fixture and failure paths with fake adb. No real device, guest, APK install,
APK build or frozen-source mutation was performed for this task.

## Integration command

Use the exact already installed, non-debuggable release APK. A release signed
with a debug certificate is acceptable here; an app with the DEBUGGABLE package
flag is not release acceptance. The dedicated initialized English profile must
already contain the pinned ordinary signed uBO, enabled, with no existing private
tabs or test filters. This run deliberately changes its real controls and removes
it last. It does not reinstall, repair inconsistent state or wipe the profile.

```sh
python3 scripts/android-addon-state-smoke.py \
  --adb /path/to/adb \
  --serial emulator-5554 \
  --package org.redoubtbrowser \
  --apk /path/to/the-exact-installed-release.apk \
  --dedicated-test-profile \
  --work /path/to/addon-ui-evidence
```

The existing root-owned Marionette setup must already be enabled. Only this
transport configuration is accepted; extra entries, including policy/test prefs,
taint acceptance:

```yaml
args:
  - "-remote-allow-system-access"
env:
  MOZ_MARIONETTE: "1"
prefs:
  remote.prefs.recommended: false
  marionette.port: 2828
```

The script reads that file but never writes it or changes the debug-app setting.
It adds only its own adb forward/reverse mappings and UI XML file, which cleanup
removes. The fixture uses Android loopback HTTP, covered by Gecko's existing
loopback exemption; no HTTPS exception, hosts edit, test rule or CA is injected.

## Results and independent evidence

`addon-results.json` is written atomically and incrementally. Its final summary
distinguishes:

- `functionalComplete: true`: all real UI enable/disable/private/removal stages,
  parser-resource controls, disk/registry/live-state observations, process
  restarts and unchanged APK bindings completed successfully.
- `acceptanceComplete: true` and exit **0/PASS**: every required criterion,
  including the signed update and immediate timing, completed with no pending
  criteria. This candidate does **not** claim this; signed update is explicitly
  pending and ordinary uiautomator timing cannot establish the narrow window.
- Exit **3/PENDING**: missing prerequisites, incomplete lifecycle, unproven
  timing or missing signed-update evidence. Successful functional checks remain
  visible. A partial return cannot become PASS.
- Exit **1/FAIL**: an exercised assertion failed. Raw state and origin/UI
  evidence are preserved, and later add-on mutations stop.

The supplied APK must match an installed base/split SHA256. Its packaged uBO pin
must equal `assets/ubo-extension.json`; actual signed XPI bytes, manifest ID,
version and bundled EasyList rule are checked. The four durability modules in
`assets/omni.ja` must match LW-M7-19's reviewed source hashes. Updated source
manifests must be deliberate integration changes; hashes cannot silently drift.

The real filter input is `/banner_ads/*$~xmlhttprequest,domain=~clickbd.com` in
`assets/thirdparties/easylist/easylist.txt`. Each HTML response contains ordinary
parser-inserted classic scripts for `/banner_ads/redoubt-probe.js` and
`/redoubt-allowed.js`. Their actual callback records include `document.currentScript`,
its URL/async/defer properties and `document.readyState === "loading"`.
The unblocked script and the independent report request must work. With uBO
enabled, the blocked script must neither execute nor reach the server; disabled
or removed uBO must permit both. A missing result, cosmetic change, blocked
report endpoint or a script injected later cannot pass.

Run/case/document IDs, exact current URL, actual Gecko private/active state and
independent server records must agree. After each process restart the intended
fixture must be the first fixture document requested; its parser completion and
report must predate Marionette's first connection attempt. This establishes the
first observed fixture navigation, not a claim that no unrelated browser network
activity occurred before it. The runner never waits for an extension listener
before requesting that page.

After the page request, read-only observations compare AddonManager, the live
WebExtensionPolicy and actual blocking-listener count, XPIStates memory,
`extensions.json`, and `addonStartup.json.lz4`. The private choice is compared
with ExtensionPermissions and the live policy. On the non-Nightly legacy backend,
`extension-preferences.json` is read separately too. A missing registry entry
does not excuse a residual policy, listener, database or startup-cache record.

## Actual UI route and lifecycle

The source route is `<scheme>://settings_addon_manager`; `--scheme` defaults to
the actual Redoubt branding, `redoubt`. The runner selects `add_on_name` with
the exact name `uBlock Origin`, then its own `add_on_content_wrapper`. A second
installed add-on with that name is rejected as ambiguous.

| Control | Stable source ID | Completion evidence |
|---|---|---|
| Enabled | `enable_switch` | Requested checked value, clickable restored, Remove/Report re-enabled and dependent private control visibility updated |
| Run in private browsing | `allow_in_private_browsing_switch` | Requested checked value, clickable restored and Remove/Report re-enabled |
| Remove | `remove_add_on` | Source success callback returns to `add_ons_list`; the old details switch is absent |

`InstalledAddonDetailsFragment` changes checkmarks optimistically. The runner
therefore rejects a checked bit while the control remains unclickable or its
completion buttons remain disabled. It records the actual command sequence and
performs force-stop as the first command after completion XML, with no intervening
registry read, screenshot or intentional delay.

The audited source directly removes when the user presses Remove; it does not
offer a second confirmation dialog. The evidence reports this explicitly as
`confirmationDialogOffered: false`. It does not fabricate a confirmation control
or treat an absent checkbox alone as successful removal.

Sequence: initial blocking; actual Disable then restart and both resources
allowed; actual Enable then restart and blocking restored; both real private
permission choices, each followed by a normal first navigation and a new private
tab's first navigation; actual removal last; normal/private absence and both
resources allowed; another normal process restart still absent. Private tabs are
created/closed through real Fenix controls and last-private-context teardown is
required. Removal may leave the entry visible as a recommended add-on; the
runner does not press Add or reinstall it.

## Timing boundary

The archived [AOSP DumpCommand source](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/cmds/uiautomator/cmds/uiautomator/src/com/android/commands/uiautomator/DumpCommand.java)
waits for 1000 ms of UI idleness before reading accessibility state. Its
`--compressed` option changes hierarchy compression, not that wait. This source
was fetched read-only; the device's exact command implementation has not been
measured here.

The runner measures a conservative interval from starting the UI action through
completed force-stop. An interval greater than 1000 ms leaves that individual
`immediate-*` checkpoint pending while functional lifecycle testing continues.
It does not call a late observation an immediate regression test. Given AOSP's
idle wait, the command-based observer is expected to miss this bound.

Root must separately rerun the source-bound AddonManager-completion/force-stop
regression that reproduced the old startup-cache race. That API test proves the
narrow native completion boundary; this runner proves real user controls and
their effective behavior. Neither substitutes for the other. A new large device
automation framework is outside this bounded task.

## Signed update and additional source finding

`source-audit.md` maps the actual periodic updater, debug UI, information-only
version dialog, verified install/update route and a reproducible signed
older-to-newer setup. No pair of suitable signed versions or actual UI update
completion was exercised here. `signed-update` remains an explicit required
pending checkpoint even if every functional lifecycle stage passes. A no-update
response, changing the version string, modifying signed XPI bytes, disabling
signature checks or calling install/update through privileged JS cannot pass.

The audit also found that non-Nightly ExtensionPermissions still uses a separate
legacy JSONFile with scheduled writes. GeckoView awaits that API and reloads the
extension before reporting the private choice complete. This is a source-level
durability concern, not a measured loss. Root reserved LW-M7-31 to inspect and
test that boundary; the UI runner's delayed observation cannot prove immediate
private-permission durability by itself.

## Host checks

```sh
python3 docs/android/evidence/lw-m7-28/test-addon-state-smoke.py
python3 docs/android/board.py --check
```

Receipts and input hashes are stored alongside this document. Target compilation,
required Android/Fenix tests, installed-release smoke/pref gates, actual UI
selectors, first-navigation behavior and signed update acceptance remain the
root-owned integration work. No host test result is labeled a device pass.
