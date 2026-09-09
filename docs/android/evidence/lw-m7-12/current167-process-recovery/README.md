# Current167 process-recovery checkpoint

This is a separate copy of `../current167/` for the Task20 isolated-process
startup correction. Root owns source staging, full tests, APK builds and runtime.
The selected source is now `4ff8b616…`; the actual full test invocation
`c02a8b984fae45dc859eff2b556b82f0` passed (see Task21
`current-account-process-tests`). APK execution started under invocation
`598783f0987b4c139fb0053c501f5628` and passed all four APK resource checks.
Runtime started under `a172ec824e2a4e94a4dd467627f6a0d0`; its completion remains
pending. See Task21 `current-account-process-apk` and
`current-account-process-runtime` for the separate actual evidence.
The failed-runtime source `501d046…` is explicitly
rejected; a later native245/249 composition is also outside this 167-file driver.

`parent-inputs.json` binds all four original source files. `copy-delta.patch` and
`check-copy.py` reproduce the new files exactly from those unchanged originals.
The original `current167` directory and its historical configurations are not
edited. `local-checks.json` records local source/contract checks only.

Fixed namespaces beneath `/home/runner/work/feature-parity-20260908`:

| Purpose | New namespace |
| --- | --- |
| APK output | `account-process-apk-output` |
| APK evidence | `evidence/account-process-apk` |
| Runtime workspace | `account-process-runtime` |
| Runtime evidence | `evidence/account-process-runtime` |
| APK service | `redoubt-account-process-apk-20260909.service` |
| Runtime service | `redoubt-account-process-runtime-20260909.service` |

Existing directories, files and broken symlinks at these output paths are
rejected. No prior output is rotated, overwritten or reused for acceptance. Both
new services require `RemainAfterExit=yes` and an actual retained invocation.

Configuration capture takes the same six explicit source/test/native fields as
the original driver. Planned inputs are `evidence/account-process-source`,
`evidence/account-process-tests`, and the retained service
`redoubt-fenix-account-process-tests-20260909.service`; source hash and invocation
must come from the actual completed correction. The reserved full runner is
`docs/android/evidence/lw-m7-12/run-fenix-account-process-tests.sh`. Root must
provide it before capture. Its recorded hash is checked against actual current
bytes, along with the board, allowance and fresh-results grader. No name or
elapsed time substitutes for the selected terminal result.

The full gate remains mandatory: all 167 source hashes and complete before/after
checks, successful terminal test invocation, valid start/finish times, container,
Android Components, allowance and fresh-result exits of zero, and all seven
nonempty issue-free suite summaries/archives. Fenix Gradle exit 1 is admitted only
when its sole failed task is `:fenix:testDebugUnitTest` and both independent gates
passed. The existing full-suite grader remains responsible for individual
regression coverage and the checked-in allowance. No skipped or failing new
regression is waived by this driver.

The APK command remains the canonical `scripts/android-apk.sh --skip-gecko` with
all three unchanged native4 AAR inputs, release variant, four jobs, disposable
Android debug signing, the bounded Podman wrapper, cache seed
`work/out/gradle-home`, image
`sha256:c5b57d94cf9e0ed1de7061cee9e0dbfde19d5651e3e2f3824b0e1466116fd687`
and build date `20260906190000`. The output gets its own copied Gradle cache.
There is no native rebuild or production source change by these drivers.

All four new APKs and the package metadata are required. Each APK must pass the
actual resource checker using `aapt2`
`c9f30b34c02fd48165251541125c3b7f21b98624e0f8341436fc65a84095e5d6`.
Both exit zero and the successful structured verdict bound to the exact APK,
tool, package and `raw/initial_shortcuts` resource are required. Nonempty failure
logs cannot pass. Source, native inputs, old artifacts and configuration inputs
are checked again after work, including after a failed stage.

Historical preservation is a separate requirement. The old successful APK
invocation `7a054c6290054e568f626c13bf8704a1` must remain successfully terminal;
the old runtime invocation `9513a070506a4a29baf9848b2ea7e8eb` is bound to the
retained terminal failure in
`docs/android/evidence/lw-m7-21/current167-runtime-checkpoint/runtime-failure.tar.gz`
(SHA-256 `f931817d0a42c567bd68211b6804367e73d45511501b089f3e30430f192c1149`).
Its exact `service.txt` member is 199 bytes, SHA-256
`4c5143defa0bc0e4e81956624b5a85ec40cefe9f2386a3d9f79695f9f94373e4`, and records
that invocation exited with status 2 at 05:25:34 UTC. Root stopped the old unit
after preserving that failure, and systemd collected it. The historical check
accepts the same retained terminal invocation or only the exact collected
`LoadState=not-found`, inactive/dead, empty-invocation defaults. A running unit,
a conflicting invocation, an unstarted loaded replacement or incomplete
inspection is rejected. No unit is recreated and no success is inferred from an
absent unit. The archived failure remains diagnostic history, never a passing
prerequisite. Current old `result.json`, `inputs.json` and source manifest must
still match the exact archived bytes. Recovery configuration pins every regular file beneath
`evidence/fenix-regression-apk`, `evidence/fenix-regression-runtime` and
`fenix-regression-apk-output/apk`. Added, removed, changed or linked entries fail
preservation. Original driver files are bound both to their retained parent
hashes and the old APK/runtime configurations. Existing `out/apk` artifacts and
native inputs retain their original before/after checks. The older disposable
Gradle and AVD caches are not recursively hashed and are not selected as recovery
outputs; preservation claims here concern the explicit evidence/artifact/code
inventories.

After corrected source and full tests pass, capture inside the guest as runner:

```sh
python3 docs/android/evidence/lw-m7-12/current167-process-recovery/build.py --print-config \
  --source-stage /home/runner/work/feature-parity-20260908/evidence/account-process-source \
  --test-evidence /home/runner/work/feature-parity-20260908/evidence/account-process-tests \
  --source-manifest-sha256 REVIEWED_CORRECTED_167_SHA256 \
  --test-service-name redoubt-fenix-account-process-tests-20260909.service \
  --test-invocation ACTUAL_TERMINAL_TEST_INVOCATION \
  --native-manifest /home/runner/work/feature-parity-20260908/evidence/fenix-regression-source/native-input-sha256.txt \
  > /home/runner/work/feature-parity-20260908/account-process-apk-inputs.json
```

Review that concrete JSON and its SHA-256. `--config PATH --config-sha256 SHA`
without `--run` validates and prints the plan. Building requires explicit `--run`
inside the matching retained service:

```sh
systemd-run --user --unit=redoubt-account-process-apk-20260909.service \
  --property=RemainAfterExit=yes --property=WorkingDirectory=/home/runner/work/feature-parity-20260908/repo \
  python3 docs/android/evidence/lw-m7-12/current167-process-recovery/build.py \
  --config /home/runner/work/feature-parity-20260908/account-process-apk-inputs.json \
  --config-sha256 REVIEWED_APK_CONFIG_SHA256 --run
```

After the new APK service is successfully terminal, capture and independently
review `runtime.py --print-config`, then use `--config`, its reviewed digest and
`--run` under `redoubt-account-process-runtime-20260909.service`. The runtime
inherits the exact successful new APK's source/test selection and all four APK
resource verdicts. It cannot select an old APK or a later untested source.

The canonical smoke/pref scripts remain unchanged. Runtime requires no attached
device, creates a fresh emulator workspace and runs all ten uBO lifecycle checks,
all eight baseline checks and the ordinary post-startup must-lock pref audit on
the new x86_64 APK. Reports must be completed, untainted, free of injected prefs,
contain no duplicate/failed checks and name the actual APK and harness hashes.
The SDK/image inputs are explicitly pinned. Cleanup stops the created emulator,
including on failure, and all evidence stays in the new namespace. Other ABI
runtime and every-settings-screen coverage are not implied.

Timeouts remain four hours for APK build, one hour for uBO lifecycle, 45 minutes
for baseline, 20 minutes for pref audit and three minutes for each resource
checker. Failure or interruption stays incomplete/failed. No automatic retry,
cleanup of historical evidence or assumption that process death completes work
is introduced.

Local replay:

```sh
python3 docs/android/evidence/lw-m7-12/current167-process-recovery/check-copy.py
python3 docs/android/evidence/lw-m7-12/current167-process-recovery/test_contracts.py
```

The 40 contract tests use local synthetic evidence, temporary real files and
controlled service responses. They validate source/identity, resource/smoke,
history preservation, failure and namespace rejection. The collected-unit cases
parse the real pinned archive with controlled systemd responses; archive changes,
incomplete inspection, conflicting/running replacements and altered current
failed receipts are rejected. They do not establish
actual compilation, service launch, Android runtime or the Task20 fix. The initial independent review is retained unchanged in
`independent-review.json`; it refers to its recorded pre-correction driver hashes.
`initial-recovery-4633c14.tar.gz` preserves all 11 initial files, including the
34-test results, source receipts and exact copy delta. The collected-unit change
and its new checks are recorded separately. The later actual target evidence is
kept in Task21; these local checks do not establish that result.

The frozen Task37 501d/9a911 staging driver is unchanged. A later corrected native
composition must explicitly adopt this recovery checkpoint in a new reviewed
version after successful source/test/APK/runtime evidence exists.
