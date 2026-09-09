# LW-M7-17 — semantic coverage audit

All 36 registered desktop patches, 22 policy keys (46 exact scalar/array leaves),
four copied preference-pane assets, 16 settings/buttons and 15 active preference
registrations have an input-bound effect mapping. **This is not a browser parity
pass.** This audit ran no APK, emulator, network or target-build checks.

[coverage-map.md](coverage-map.md) is the readable effect map;
[coverage.json](coverage.json) carries the corresponding source claims and pins.
The latest focused review updates four counterparts: graphics, RFP controls,
extension updates and network controls. It reads the implemented LW-M7-35/36
source and retains their pending target gates. All other counterpart records and
all desktop/policy/pane mappings remain unchanged from the preceding review.
[followup-review.json](followup-review.json) retains the earlier followups and
the distinct source-capture and repository-review revisions.

The four updated counterparts now record these source implementations:

- **Extension updates:** Settings has a native-backed combined switch for
  `extensions.update.enabled` and `extensions.update.autoUpdateDefault`. Opening
  Settings preserves mixed values; checked means both are true. Explicit Off
  writes both false. Automatic work checks native admission before update
  metadata and before installation. A mixed unchecked state can still allow
  metadata and per-addon Enable overrides. Scheduled jobs may wake; manual
  checks, unrelated catalog reads and already-started installation remain
  separate. Network silence, real signed upgrades and restart persistence still
  require target execution.
- **Graphics:** the existing exact-principal request and saved-exception source
  is joined by Always allow WebGL (inverse `librewolf.webgl.prompt`) and Hide
  WebGL popup. The quiet control is disabled during global bypass. These global
  controls preserve site grants. Rendering, document/worker behavior, private
  lifetimes and immediate restart remain unverified. A separate `webgl.disabled`
  control is excluded because the common startup write would overwrite its
  saved value.
- **RFP:** Global privacy controls now exposes Resist Fingerprinting through a
  dedicated native API. Global/private RFP, separate FPP and configured
  exceptions still matter to observed behavior. Optional letterboxing and
  website-appearance interaction remain open; a preference read cannot establish
  a fingerprinting result.
- **Network controls:** Enable IPv6 inverts `network.dns.disableIPv6` and governs
  DNS address-family selection. Cross-host referrers preserves native values
  0/1/2; mode 2 compares host, ignoring scheme and port. Other referrer rules
  still apply. Controlled DNS/server receipts, locks, reset and immediate
  restart remain pending.

These nonpersistent Fenix controls read authoritative native effective/default,
user and lock state. Writes are validated and serialized through Task 35's
current-profile save promise. A failed save reports the actual memory state and
unconfirmed disk state, without inferred rollback. For extension updates, a failed
save also closes automatic admission until a successful explicit save. **Tasks 35/36
target compilation, API/UI tests, disk durability and runtime behavior are still
pending.** Host mocks and authored fixtures do not satisfy those gates.

The current graphics patch pin also includes the compiler correction from
deprecated `bundleOf` to platform `Bundle.putString/putBoolean`. The preserved
original patch binds the earlier reviewed line ranges; the separate correction
receipt pins the corrected dialog and preserves nullable tab/context IDs,
private fallback and argument keys. This is a source correction, without an
inferred native or runtime result. Task 35's ordering receipt now binds that
corrected input; its six measured pair results are unchanged.

## Preserved evidence

[source-index.md](source-index.md) lists the inspected portions of 46 complete
files retained in [inspected-source.tar.gz](inspected-source.tar.gz). The archive
includes Android/Gecko source, desktop policy handlers and exact settings inputs.
Every file and the archive have SHA-256 bindings in
[source-evidence.json](source-evidence.json). These original bytes and their
provenance at `7c78e8a3a86d6feed5ea0517b9c824ce0cbfa8ae` are unchanged.

[before-review.tar.gz](global-controls-followup/before-review.tar.gz) separately
retains the exact five Task17 documents/scripts preceding this focused review,
including their historical findings. [review.json](global-controls-followup/review.json)
pins that archive, the four-counterpart scope and the inspected Task 35/36 source
file hashes. The current patches, source receipts, original 38-file global
privacy audit and Bundle correction are pinned in `coverage.json`.

[bounded-searches.json.gz](bounded-searches.json.gz) preserves the original five
search patterns, scopes, exit status/output, file hashes and Fenix resource list.
A zero-match result is a bounded historical observation. Later implementation is
cited through separate patches; neither source set is silently relabelled as the
final APK. Other existing gaps and target obligations remain in `coverage.json`.
Unrelated counterpart prose was not re-audited in this followup.

## Verification

Run from the repository root without an SDK, VM, device or extracted source tree:

```sh
python3 docs/android/evidence/lw-m7-17/check-coverage.py
python3 docs/android/evidence/lw-m7-17/global-controls-followup/test-checker.py
python3 docs/android/board.py --check
```

The checker binds the desktop inventory, exact policy leaves, settings gitlink,
pane controls and evidence hashes. The new scoped checks additionally preserve
the original mapping, reject unrelated counterpart changes, compare the four
readable sections with their JSON records, and bind inspected source and compiler
correction lineage. These checks cannot prove a semantic interpretation or target
behavior.

The original [verification.txt](verification.txt) and eleven original
[negative controls](checker-negative-controls.txt) are retained. Current results
and additional drift/overclaim negative controls are recorded separately in
[global-controls-followup/verification.txt](global-controls-followup/verification.txt).
