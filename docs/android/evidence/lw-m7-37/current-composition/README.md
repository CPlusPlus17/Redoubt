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

The bounded stage driver requires separately captured successful current167
full tests, new APK/resource checks and runtime receipts, including their actual
terminal service invocations. It preserves current and historical APKs and
all three native4 inputs, backs up every replaced source, applies only declared
materialized changes and emits the full245 manifest with before/after receipts.
Each file write is atomic; the multi-file operation is not a filesystem
transaction. A partial failure must remain failed with its backup and progress
receipt for inspection, without claiming a successful stage or silently retrying.

All code and evidence for this preparation stay within existing Task37 ownership
under `docs/android/evidence/lw-m7-37/`. No new product path ownership is needed.
Task37 still implements only its 15-file frame/cookie native increment; complete
writer/cache admission and cleanup journal-success integration remain pending.

`verify.py` independently checks the complete inventory and action derivation,
then replays the 151-input parent and the Task37 composition in fresh temporary
directories using all 157 archived inputs. The 19 parent outputs and both sets of
10 child outputs must be byte-identical to their retained counterparts. The
97 historical243 bodies must also remain identical inside the new 101 bodies.
`independent-verification.json` records that local replay. Run from the repository:

```sh
python3 docs/android/evidence/lw-m7-37/current-composition/verify.py
python3 docs/android/evidence/lw-m7-37/current-composition/test_stage.py
```

The 14 driver tests use temporary local files. They exercise exact before/absence
checks, path and archive rejection, replacement modes, concurrent-create refusal,
post-rename synchronization failure, backup bytes, admission failure, failure
receipts and refusal to overwrite prior evidence. They mock guest admission only
where needed to test the driver's filesystem/progress behavior. They do not prove
Android compilation, cleanup behavior, guest operation or runtime acceptance.

The stage driver has **not been executed in the guest**. Its config capture is a
read-only guest operation, separate from the explicit source mutation command:

```sh
python3 docs/android/evidence/lw-m7-37/current-composition/stage.py --print-config > /home/runner/work/feature-parity-20260908/current245-stage-inputs.json
sha256sum /home/runner/work/feature-parity-20260908/current245-stage-inputs.json
```

Review those actual bytes and digest before using `--config` plus
`--config-sha256 REVIEWED_SHA256`. Without `--run`, that command checks the selected
prerequisites and all live before hashes/absences, and prints `PLAN ONLY`. The
mutation command must run as the guest runner in a retained service:

```sh
systemd-run --user --unit=redoubt-current245-source-stage-20260909.service --property=Type=exec --property=RemainAfterExit=yes --property=WorkingDirectory=/home/runner/work/feature-parity-20260908/repo /usr/bin/python3 /home/runner/work/feature-parity-20260908/repo/docs/android/evidence/lw-m7-37/current-composition/stage.py --config /home/runner/work/feature-parity-20260908/current245-stage-inputs.json --config-sha256 REVIEWED_SHA256 --run
```

`REVIEWED_SHA256` is deliberately a required concrete review input, not an automatic
hash of whichever file happens to be present. The driver rejects active containers
or emulators, a different guest/source/image, existing output evidence, changed
script/input records, incomplete tests, resource checks, runtime reports or
nonterminal/mismatched service invocations. It regrades the runtime's actual uBO,
baseline and pref-dump reports against the new x86 APK and harness. Its preserved
file inventory includes every recorded new/old APK, native input copy, report,
manifest, config and script from the successful checkpoints. Both the original
native-manifest paths and the reused AAR copies are checked after staging.

Outputs are in
`/home/runner/work/feature-parity-20260908/evidence/current245-source-stage/`:
`inputs.json`, source plan/parent copies, `source-before.json`, the 43-file backup
archive and index, `source-after.json`, `source-sha256.txt`, and `receipt.json`.
Each mutation is recorded as `attempting` before its file operation and as
`applied` only after synchronization and hash verification. Failure after rename
may leave the new file on disk; the driver reports failure and retains the
attempt marker. The source backup and file writes are synchronized, but this is
not a durable multi-file transaction or an automatic rollback system. Hard
termination can leave an `APPLYING` receipt. Preserve all evidence and inspect
all declared paths before any separately reviewed recovery.

Native5 admission must independently require this stage's **PASS receipt and
matching successfully terminal service invocation**, then the exact 245-file
live manifest. A complete-looking manifest alone does not establish successful
preservation checks. The native driver's generic staging-receipt field binds
provenance but does not itself grade this stage's status.

At handoff, root reported that the new current167 APK/resource checkpoint passed
but its runtime attempt exposed an isolated-process startup crash in Task20.
Therefore **this exact 501d/9a911 candidate is blocked from staging**. Neither the
failed runtime nor a future corrected candidate can satisfy this frozen plan by
substitution. After the correction, root must retain the new source/test/APK and
successful runtime evidence, independently refresh the composition and explicit
pins, and review a new stage configuration. This directory preserves the current
candidate and all preceding history without claiming target success.
