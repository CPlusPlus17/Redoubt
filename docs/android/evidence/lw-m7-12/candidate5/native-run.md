# Native build for the next candidate

`native.py --inputs FILE` validates the reviewed source manifest, all source
bodies, staging receipt, immutable image ID and repository dependencies, then
prints a plan without creating build output. `--run` additionally requires the
idle KVM guest, runner UID1001, no emulator, the actual named systemd invocation
and `RemainAfterExit=yes`. It also checks that the recorded staging invocation is
still available and successfully terminal before creating native build outputs.
Keep both services retained: staging through native admission, and native through
the APK checkpoint's independent terminal-state check.

Root supplies measured values for `schema: 1`, `run_id` beginning `native5-`,
`service_name` equal to `redoubt-<run_id>.service`, `reviewed_scope_note`, `work`,
`source_dir`, `build_date`, `container_image_id`, `gradle_home_seed`,
`source_manifest` (absolute path, SHA-256, count), `source_staging_receipt`
(absolute path, SHA-256 and byte size), and `repository_files` (the exact `DEPENDENCIES`
map). Source staging is a separate operation; this driver does not infer or apply
patches. The selected manifest must be the successful stage's own
`source-sha256.txt`, beside its `receipt.json` inside the guest work evidence tree.
The versioned `account-process245-source-stage` receipt must have status `PASS`,
matching source/count/manifest, ordered completed timestamps and complete final
source checks. Its exact input configuration and reviewed composition receipt
must link the same before/final source identities. A missing, failed or unfinished
stage cannot pass even when every source file already has its final bytes.

The current producer is Task37's `process-recovery-composition/stage.py`, with
before167 `4ff8b616…` and final245 `40da1bf9…`. Native5 uses this product245
manifest; Task27's249 test supplement remains separate. The local plan validates
the receipt files without contacting systemd. Actual execution queries
`redoubt-account-process245-source-stage-20260909.service` and requires the
receipt's same invocation, `RemainAfterExit=yes`, `Result=success`, exit0 and a
terminal active/exited or inactive/dead state. The receipt's initial running
snapshot is not mistaken for its terminal status. Native evidence archives the
successful terminal snapshot and exact stage receipt.

Execution creates a fresh native output directory, copies the idle Gradle cache,
builds all three ABIs and the real fat merge, and checks every source binding
before and after. It preserves failure logs and exit codes. A successful result
records the actual invocation, image, build date, all native archives and the
source-bound files required by `checkpoint.py`; success still requires that
service to finish with exit0 before the APK checkpoint can use it.

The twelve native host boundary tests preserve the six prior controls and add
failed/unfinished-stage rejection, mismatched source/config/plan links, incomplete
final checks, invalid completion times, missing/changed/failed terminal invocation
and a real native-run control that stops before output creation. These fixtures
do not establish native compilation. `pre-stage-admission/` preserves the earlier
driver whose stage-success check depended on root's manual launch review.
