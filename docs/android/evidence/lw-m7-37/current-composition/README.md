# Current245 source handoff and staging scope

This directory retains coverage_map's complete current245 handoff byte for byte.
Historical243 remains in `../composition-fifth-fixture/` unchanged. Staging and
native execution have **not run** for this increment.

The selected current167 manifest is
`501d04614edbc847b416cd5b6f1dac42dd0728a63125a3d9902c90d07a579c8b`.
The proposed245 manifest is
`9a911246fb9dcf2a55fdfe7827fd2eff000fdfecc97d8f1346c94dc018e0f995`,
with 101 materialized bodies in archive
`17f902935a133f3f7ea9e7f3292071e2ffac9eef5d59b0177e7565df39cfe37f`.
The retained receipt is
`6eeaf49279e6969bb56f85812c84f1aeca66e0bd7ac1f867a32cd470e10c36fe`.

Before staging, all 200 existing source hashes and 45 expected absences must
match. The plan replaces 43 files, creates 45 and retains 13 materialized inputs;
the other 144 source bindings remain unchanged and require live hash checks.
The whole current167 inventory is included in that preflight. A successful
earlier read-only check does not replace repeating it immediately before writes.

`inputs.json` binds the full handoff and all 151 parent repository inputs plus
the six Task37 patch/source/capture inputs. Their exact bytes are retained in
`frozen-repository-inputs.tar.gz`, so historical statuses and ordering receipts
can be replayed without requiring their original live paths to remain current.
Forty consumed patch, asset, source-manifest and packaging inputs remain explicit
current-repository requirements. The selected patches must retain their recorded
relative order; unrelated registry lines and comments are outside this plan.
This distinction never substitutes newer bytes into a historical source replay.

The bounded stage driver will require separately captured successful current167
full tests, new APK/resource checks and runtime receipts, including their actual
terminal service invocations. It will preserve current and historical APKs and
all three native4 inputs, back up every replaced source, apply only declared
materialized changes and emit the full245 manifest with before/after receipts.
Each file write is atomic; the multi-file operation is not a filesystem
transaction. A partial failure must remain failed with its backup and progress
receipt for inspection, without claiming a successful stage or silently retrying.

All code and evidence for this preparation stay within existing Task37 ownership
under `docs/android/evidence/lw-m7-37/`. No new product path ownership is needed.
Task37 still implements only its 15-file frame/cookie native increment; complete
writer/cache admission and cleanup journal-success integration remain pending.
