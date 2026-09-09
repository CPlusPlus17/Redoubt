# Native build for the next candidate

`native.py --inputs FILE` validates the reviewed source manifest, all source
bodies, staging receipt, immutable image ID and repository dependencies, then
prints a plan without creating build output. `--run` additionally requires the
idle KVM guest, runner UID1001, no emulator, the actual named systemd invocation
and `RemainAfterExit=yes`. The last setting preserves the completed service for
the APK checkpoint's independent terminal-state check.

Root supplies measured values for `schema: 1`, `run_id` beginning `native5-`,
`service_name` equal to `redoubt-<run_id>.service`, `reviewed_scope_note`, `work`,
`source_dir`, `build_date`, `container_image_id`, `gradle_home_seed`,
`source_manifest` (absolute path, SHA-256, count), `source_staging_receipt`
(absolute path and SHA-256), and `repository_files` (the exact `DEPENDENCIES`
map). Source staging is a separate operation; this driver does not infer or apply
patches. A staging receipt is retained as provenance, while the selected manifest
and checked source bodies establish the actual build inventory.

Execution creates a fresh native output directory, copies the idle Gradle cache,
builds all three ABIs and the real fat merge, and checks every source binding
before and after. It preserves failure logs and exit codes. A successful result
records the actual invocation, image, build date, all native archives and the
source-bound files required by `checkpoint.py`; success still requires that
service to finish with exit0 before the APK checkpoint can use it.

The six host boundary tests exercise plan-only behavior, source/receipt drift,
prior output preservation, dependency/service mismatch and refusal of host
execution. They do not establish native compilation. No native5 target build
has been run while preparing this driver.
