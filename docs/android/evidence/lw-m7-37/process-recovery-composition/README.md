# Process-recovery source composition preparation

This is a new Task37-owned staging version for the corrected account/Suggest
process candidate. The frozen `../current-composition/` 501d/9a911 candidate and
`../composition-fifth-fixture/` history remain unchanged.

The corrected current167 source manifest is
`4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739`.
The final245 manifest is
`40da1bf9c42187b1e037fba5b443e4b26fd2758ffa7b07212710df72693eb806`.
The 107-body archive is
`4ff529867fb992b2db259d7dec95bffabce459aac60e3cc564a38e16d102bbc9`;
the retained receipt is
`fb7ca4f5c93aab3ea089380d6ca8d8ca4e9e3e24a258f65cee45b24f2691493e`.
The plan checks 200 existing hashes and 45 absences, replaces 43 files, creates
45 and retains 19 materialized inputs plus 138 unchanged manifest-only bindings.
All 101 previous materialized bodies are unchanged; the six additional bodies
are process corrections already present in the corrected167 source.

The complete coverage handoff is retained byte for byte in `handoff/`.
`inputs.json` pins 212 current parent inputs plus six Task37 inputs, retained in
`frozen-repository-inputs.tar.gz`. Historical151 inputs remain separately bound
to the immutable prior157 archive. Forty consumed source/patch/asset/packaging
inputs and selected patch order must still match the live repository; historical
metadata is replayed only from its frozen version. No implementation or target
success is inferred from a plan or snapshot.

The eventual source-only stage will import the separate
`docs/android/evidence/lw-m7-12/current167-process-recovery/` checkpoint contracts.
It will require the actual successfully terminal full tests, APK build, all four
resource verdicts and complete runtime acceptance before writes. Preparing this
version does not authorize or claim guest staging, compilation or runtime.

Root owns all guest operations. Source/package/artifact identities, all current
167 source paths and every final existing/absent source path must be rechecked
immediately before staging, and native/APK/evidence identities preserved after.

Independent local verification is recorded in `independent-verification.json`:
19 historical outputs reproduce from the separately frozen 151 inputs, all 14
corrected parent outputs reproduce from its 212 inputs, and two fresh Task37
runs produce the exact same 10 retained outputs. The full245 before inventory,
action classification and six-file difference from historical245 are separately
derived by `verify.py`, rather than accepted from a status string. Its local
replay uses a private no-checkout clone sharing only the original repository's
Git object database because the unchanged parent wrapper calls `git show` for
its pinned historical commit. Every returned historical body must match the151
frozen pins. The staging preflight itself needs no Git object lookup or replay.

The driver is `stage.py`; its only checkpoint import is
`current167-process-recovery`. It revalidates the exact corrected167 full-test,
new APK and all-four-resource proofs and completed uBO/baseline/pref reports,
including their actual retained service invocations, before admitting a stage.
It preserves all recorded new and old APKs, both sets of native input copies,
checkpoint evidence and source/tool/config inputs. Historical collected-runtime
provenance remains archival failure evidence under the recovery contract; it
cannot stand in for a successful new runtime service.

Fresh outputs are
`/home/runner/work/feature-parity-20260908/evidence/account-process245-source-stage/`
and service `redoubt-account-process245-source-stage-20260909.service`. The old
stage namespace is not reused. Existing output evidence, active containers or
emulators, changed inputs and missing/nonterminal/failed new gates are rejected.
No guest staging has run for this source preparation.

After successful recovery runtime and cleanup, the authorized guest operator
captures a concrete config:

```sh
python3 docs/android/evidence/lw-m7-37/process-recovery-composition/stage.py --print-config > /home/runner/work/feature-parity-20260908/account-process245-stage-inputs.json
sha256sum /home/runner/work/feature-parity-20260908/account-process245-stage-inputs.json
```

Review the actual JSON and digest. Using `--config PATH --config-sha256 SHA`
without `--run` repeats the prerequisite and complete source preflight and prints
`PLAN ONLY`. Mutation requires the reviewed digest and a retained matching service:

```sh
systemd-run --user --unit=redoubt-account-process245-source-stage-20260909.service --property=Type=exec --property=RemainAfterExit=yes --property=WorkingDirectory=/home/runner/work/feature-parity-20260908/repo /usr/bin/python3 /home/runner/work/feature-parity-20260908/repo/docs/android/evidence/lw-m7-37/process-recovery-composition/stage.py --config /home/runner/work/feature-parity-20260908/account-process245-stage-inputs.json --config-sha256 REVIEWED_CONFIG_SHA256 --run
```

The explicit digest is a review input, not an automatically trusted hash of
whichever config is present. The script backs up all 43 replaced files, repeats
all 200 existing and 45 absence checks immediately before writing, and applies
only the 88 changed bodies. Each write records an `attempting` marker first,
uses a same-directory temporary file, preserves replacement modes, refuses to
overwrite a concurrently created new path, synchronizes file/directory writes,
and verifies final bytes before recording `applied`. All 245 hashes and preserved
inputs are then checked again.

The output includes config/plan/parent copies, `source-before.json`, the 43-file
backup and index, `source-after.json`, exact245 `source-sha256.txt` and
`receipt.json`. Writes are atomic per file, not a multi-file transaction. Failure
after rename can leave that file changed; the receipt retains the attempted path
and reports failure. Interrupted `APPLYING` evidence never passes. Preserve all
progress/backups and inspect every declared path before any separately reviewed
recovery; the driver neither retries nor rolls back automatically.

Native5 must independently require the stage's **PASS** receipt, matching
successfully terminal invocation and all 245 actual source hashes. Its generic
staging-receipt field binds provenance but does not itself grade this status.
The separate249 test-source supplement is not included in this product manifest.
Task37 still supplies frame/cookie primitives only; complete writer/cache
admission, journal-success coordination and their target acceptance remain open.

Local replay commands:

```sh
python3 docs/android/evidence/lw-m7-37/process-recovery-composition/verify.py
python3 docs/android/evidence/lw-m7-37/process-recovery-composition/test_stage.py
```

The 14 temporary-filesystem tests cover before/absence checks, paths and archive
members, write modes, concurrent creation, synchronization failure, backups,
admission failure, attempted-write receipts and refusal to overwrite prior
output. Guest admission is mocked only in the isolated filesystem/progress tests.
They establish driver contracts, not Android compilation or behavior. Source
replay and the independent interface review are separately recorded. No build,
staging, native test or runtime verdict for this 245 candidate is claimed here.
