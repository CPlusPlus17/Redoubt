# Isolated-process source composition

This source-only handoff reproduces all 19 historical232 outputs from the exact 151-input c7a8b693 Git snapshot, then verifies current20 and26 source replays from 212 independently pinned current inputs at cfaead4. The six process-correction paths are disjoint from later31/29/35/36 patch paths, whose bytes and order remain unchanged. No guest, build, test or APK execution is performed by this audit.

Run `python3 compose.py --repo /path/to/repository --output /new/private/output`. The repository must provide the pinned current files (reconstruct from the stated Git snapshot if necessary) and the historical Git objects. Both input versions are independently hashed. Python3, PyYAML, Git and GNU patch are required. Every historical comparison and current scoped replay is repeated.

The new167 manifest is 4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739. The future232 union contains94 materialized bodies and138 unchanged manifest-only native bindings. All prior88 bodies,13 Suggest generated resources and Task30 empty raw resource are unchanged. The six added bodies already exist in corrected167, so they are retain-bound-input staging rows. All167 current hashes plus65 additional before/absence checks are required before future staging. This handoff does not authorize or perform staging.

The original501d current167, d25b proposed232, original compiled165c537 and native4 manifests remain retained as history. Two independent fresh local executions produced identical14 outputs; hashes are in repeat-check.json. Current target diagnostic/full-suite/runtime results are separate receipts and never inferred from this source composition.

Root independently reconstructed all212 current inputs from the declared Git
revision, replayed all151 historical inputs and19 outputs, and reproduced all14
new outputs byte for byte. `root-verification.json` records the comparison.
`frozen-repository-inputs.tar.gz` retains the complete212-file current input set,
so mutable working-tree receipts are not needed to recover this snapshot. The
historical c7a8 Git objects are still needed by `compose.py` for its explicit
historical replay. No guest source staging or target verdict is recorded here.
