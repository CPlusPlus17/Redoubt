# Runtime retry after the add-on notice blocked graphics controls

This is another separately versioned runtime attempt on the same successful APK
build `598783f0987b4c139fb0053c501f5628`, source167 `4ff8b616…`, full-test invocation
`c02a8b984fae45dc859eff2b556b82f0` and native4 archives. It changes no APK, product
source, policy or acceptance requirement. The capsule changes only the graphics
runner to the exact notice-handling fix `3313174924ff378b9f58126762ec505fa8741152`,
SHA256 `74d66c2c4b47006cfcb861dff0cedf83ffce5fae2f08daca78fe81c05029c12b`.
The other four capsule files remain byte-identical to the first corrected capsule.

The long runtime logic is reused from frozen `harness-process-recovery`, including
every prepare, validate, execution, grading and cleanup function. A fresh private
module instance receives only new HERE/capsule/output/service constants. The
runtime is imported with an explicitly bound common adapter, and the caller's
`sys.modules['common']` entry is restored even on an import exception. The frozen
source files and every independently imported original module remain unchanged;
the original current167 `base.REPO` still points to the original guest repository.
`inherited-files.json` pins the frozen code before its private import.

The adapter adds preservation checks for failed runtime `0189d862…`, alongside
the inherited checks for failed `a172ec82…`. The first failure archive has 55
members. The second archive is
`docs/android/evidence/lw-m7-21/current-harness-process-runtime/runtime-failure.tar.gz`,
SHA256 `8ffbb2f513d1cad4f995164c5600cc42dd39852f3afb3d0149775f8ac15e390c`,
with 95 members, including all 29 graphics evidence files. Every captured source,
capsule, checkpoint and runtime-work file must retain its original bytes, and
both failed services must retain their exact terminal invocations. Successful
uBO observations from 0189 remain evidence of that attempt; the new retry runs
all 10 uBO checks again, all 8 baseline checks, the pref audit and owned-emulator
cleanup. A prior successful subset cannot substitute for any new gate.

Only new files are transferred: `common.py`, `runtime.py`, `inherited-files.json`,
`capsule-files.json`, the five new capsule files, and the exact 0189 archive at its
root-owned path. Preserve the already deployed original guest repository,
original current167 modules, first capsule/wrapper and first failure archive.
Do not copy the host's canonical graphics fix over an original guest script or
the first capsule. Both are now historical configuration dependencies.

The new service is `redoubt-modal-process-runtime-20260909.service`. Its fresh
output paths are `evidence/modal-process-runtime` and `modal-process-runtime`
beneath the existing guest work directory. Require no existing emulator or
container and retain the service with `RemainAfterExit=yes` through subsequent
staging review. Capture the concrete configuration only after all ten new input
files have been copied and rehashed:

```sh
python3 docs/android/evidence/lw-m7-12/modal-process-recovery/runtime.py --print-config
```

Review the exact JSON and hash, then invoke that service with
`runtime.py --config /absolute/inputs.json --config-sha256 ACTUAL_SHA --run`.
Omitting `--run` validates without creating output. This preparation includes no
future invocation or runtime verdict.

The inherited `runtime_repository_files` config field continues to describe the
new local runtime code and capsule manifest as required by the frozen validator.
The additional `inherited_runtime_files` field pins inherited code/manifest and
the second failure archive. The public `runtime_inputs()` returns their complete
union for a future separately reviewed245 staging adapter. New `load_config` and
`finish` validate both sets and both histories. A late 0189 or inherited-file
change marks the result failed before the inherited final checks write it.

The new host controls cover module isolation/restoration, inherited-source drift,
both actual archives, exact capsule selection, prepare/validate dispatch and
post-execution history/input drift. The frozen wrapper's original 15 controls also
remain passing. These are host checks only. No guest command or target runtime
ran while preparing this adapter; full runtime and native5 admission remain
pending actual successful terminal gates.
