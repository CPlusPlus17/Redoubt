# LW-M7-27 — isolated native Android test drivers

**Driver preparation only. Native test build and device tests have not run.**
The local checks validate configuration isolation and result grading. They do not
validate the C++ changes, packaged Gecko resources, GeckoView APIs or release APK
behavior. The existing production build, full Fenix subtraction gate and installed
release-APK acceptance remain separate requirements.

`driver.py` provides read-only `plan` and `preflight`, then explicit `build --execute`
and `run --execute`. Persistent test outputs belong to a new `redoubt-native-tests-*` workspace
outside the product source directory; container-local caches use disposable layers. It never reconfigures a production objdir.
The driver does not start an emulator, enter a VM, install a toolchain, operate a
runner service or access a release key. `in-vm.py` runs inside the existing guest
and launches the bounded rootless Podman container. Direct host build/run execution
is rejected by the driver. The default
native job count is two, Cargo one, Gradle one; commands have bounded timeouts.

## Source and configuration binding

Preflight verifies every entry in the operator's integrated source SHA256SUMS and
requires all 102 source paths affected by the selected feature patches, all selected
native tests, and their instrumentation classes. It separately verifies 17 pinned
harness/build files against `harness-sources.json`, read from the frozen Firefox
153.0esr beta tree. Those pins describe the audited source subset, not a fresh
verification of every file in the upstream source archive. A changed harness must
be reviewed and re-pinned; it cannot silently reuse this parser contract.

The source-plan git revision is recorded as operator-supplied provenance. The
bytes actually checked are in the source manifest and harness pins. Provide the
reviewed integrated source manifest, not a manifest freshly generated from an
unreviewed tree merely to satisfy this check. The manifest must include the test
source files; product-only manifests that omit tests fail preflight.

The production mozconfig is preserved verbatim. Its derived config changes only:

- `--disable-tests` to `--enable-tests`;
- the native target to `x86_64-linux-android`;
- `--enable-android-subproject=fenix` to `geckoview_example`;
- `MOZ_OBJDIR` to the new workspace's `obj-x86_64-tests`.

The exact diff is recorded. Native optimization, LTO, hardening and the production
symbol policy remain unchanged; `MOZ_BUILD_DATE` must be the corresponding product
build's fixed date. The additional subproject change is necessary:
`settings.gradle:67–75` includes `:test_runner` only with an empty subproject or
`geckoview_example`. That is an existing supported `mobile/android/moz.configure`
choice; it does not select desktop Gecko or GTK.

The driver calls the real commands defined by the pinned source:

```text
python3 mach build -j2
python3 mach gradle test_runner:assembleDebug geckoview:assembleDebugAndroidTest --no-daemon --max-workers=1
```

`mobile/android/gradle.configure` declares those Debug tasks even for an optimized
native build. Direct `mach gradle` propagates the Gradle exit status. Some convenience
`mach android build/install-*` wrappers discard it and return zero, so they are
not used here. A successful build additionally requires `ENABLE_TESTS=1`, Android
x86_64 mozinfo, the target ELF64 xpcshell tool and required HTTP helper, unique
APK outputs, x86_64 ELF64 Gecko inside each APK, debuggable manifests, and the
ordinary `CN=Android Debug` signing certificate. Release-signed artifacts are
rejected. Output hashes, signing reports, source/config/driver bindings, commands
and completion records are preserved.

## Invocation

Use the actual provisioned paths. `plan` does not read the source manifest or
create a workspace; `preflight` reads/verifies source files and writes nothing.
The checked-in `local-plan.json` is a host-side plan against the real production
mozconfig and frozen source path, with a deliberately nonexistent future integrated
manifest. It is explicitly **NOT RUN**, and no proposed workspace was created.

```sh
native_test_args=(
  --source /work/src
  --source-manifest /work/evidence/reviewed-integrated-source-sha256.txt
  --product-mozconfig /work/repo/assets/mozconfig.android
  --product-revision REVIEWED_40_HEX_SOURCE_PLAN_COMMIT
  --build-date 20260906190000
  --workspace /home/runner/native-tests-20260910/redoubt-native-tests-first
)
native_test_driver=/work/repo/docs/android/evidence/lw-m7-27/driver.py
python3 "$native_test_driver" plan "${native_test_args[@]}"
python3 "$native_test_driver" preflight "${native_test_args[@]}"
# Run these wrapper commands as runner INSIDE the KVM guest. The paths in
# native_test_args must be the actual guest paths; the wrapper preserves them.
native_test_wrapper=/work/repo/docs/android/evidence/lw-m7-27/in-vm.py
python3 "$native_test_wrapper" --repo /work/repo --preflight-only \
  build "${native_test_args[@]}"
python3 "$native_test_wrapper" --repo /work/repo \
  build "${native_test_args[@]}" --execute
python3 "$native_test_wrapper" --repo /work/repo \
  run "${native_test_args[@]}" --execute --serial emulator-5554
```

The wrapper requires KVM, the non-root guest `runner` account, local rootless
Podman, the active guest firewall unit, no host home or 9p/virtiofs share, at least
19 GiB usable guest RAM and 100 GiB free disk. It checks the immutable imported
image `c5b57d94cf9e0ed1de7061cee9e0dbfde19d5651e3e2f3824b0e1466116fd687`
and refuses a concurrent container before reserving this build slot. Preflight
prints the exact Podman command and source/resource evidence without starting it.
The writable parent must be a dedicated `/home/runner/.../native-tests-*` directory,
separate from both repository and source.

The command uses 17 GiB RAM, 23 GiB combined memory+swap, six CPUs, a PID bound,
no extra capabilities and no new privileges. It mounts repository, source, manifest
and config read-only, and only the separate workspace parent writable. The guest
network namespace (`--network=host` inside the VM) provides the existing adb server
at `127.0.0.1:5037`; no engine socket, host directory, credentials or release key is
mounted. Inside the container, build/run checks its marker, actual cgroup limits,
toolchain paths and executable hashes/versions before invoking mach. SIGTERM,
SIGHUP, interruption and timeout remove the named container rather than leaving an
unattended native build behind.

Read-only source compatibility is a deliberate **unverified** assumption. Mach,
configure, Cargo or Gradle may require generated files in the source tree. Such a
failure is preserved and must be resolved with a separate source copy (for example
a private reflink copy), not by making the production source writable or moving
the compiler root. No guest/container/build command has run during preparation.

Build requires a fresh workspace; a failed attempt's artifacts and logs remain for
review. Start another workspace after correcting a failure. It preserves the pinned image’s `/root/.mozbuild` toolchain root, including its
NDK/JDK/Rust/WASI/clang/node/cbindgen/nasm paths. That root has disposable container
writes for `srcdirs` and internal state; it is not replaced with an empty cache.
`GRADLE_USER_HOME` is workspace-specific and starts with the image’s own
`/root/.gradle/gradle.properties` when present. Existing toolchains and
pinned dependency availability are environmental prerequisites; a missing tool or
failed download is a failure, not a skipped build. The supplied build timeout is
per command, default six hours; test invocations default to thirty minutes each.

Run verifies the build receipt, unchanged sources/config/artifacts and an explicitly
selected x86_64 emulator before changing the device. It installs only the two
validated debug test apps (`org.mozilla.geckoview.test_runner` and the self-targeted
`org.mozilla.geckoview.test` instrumentation APK). `adb install -r -t` failure stops;
there is no automatic uninstall or data wipe in this driver.

The pinned `verify_android_device` otherwise defaults to uninstall/reinstall of an
inferred app during `mach xpcshell-test`. The driver sets its supported
`MOZ_DISABLE_ADB_INSTALL=1` switch and supplies the exact validated `--apk`. It keeps
remote setup enabled, because `--no-install`/`--noSetup` would also suppress required
test utilities and modules. The remote harness force-stops its own test_runner app
and creates/removes test fixtures under a unique `/data/local/tmp/redoubt-tests-ID`
root. It applies its normal test preferences, including fission, only in this test
environment. Instrumentation likewise creates test profiles and may set test prefs.
None of those preference changes establishes release-APK acceptance.

## Required results

`requirements.json` is the exact selection, source path inventory and input patch
hash inventory. No expected native failure or required skip is allowlisted.

| Suite | Required execution |
|---|---|
| Android add-on state | Six tasks covering acknowledged state, failed-save retry, both DB/cache mismatch directions, first install, removed file and missing/corrupt database |
| add-on startup save failures | Five existing failure-path tasks |
| packaged cookie rules | Android snapshot and validated test-rule tasks, plus the existing test-pref task |
| private cookie lifetime | Five tasks including held native initialization, earlier-observer replacement, stale dispatch, normal/private isolation and autostart |
| Android translations | Two packaged catalog/WASM and passive missing-model/cache-deletion tasks |
| GeckoView canvas/WebGL | All eight `CanvasPermissionTest` methods |
| GeckoView translations | `cacheOnlyTranslationUsesRealCatalogAndPreservesMissingModels` |
| GeckoView private cookie lifetime | All three `CookieBannerPrivateSessionTest` methods |

Each xpcshell file runs separately and sequentially with a new raw mozlog file.
The grader requires suite/file start and successful completion, every required
named task's start and finish, no required skip, and no failed assertion, crash
or error-level harness diagnostic. A PASS for the file alone is insufficient.
Four explicitly named desktop-only tasks in the cookie list file may skip on
Android; they are not counted as executed Android tests. The remote xpcshell
command uses `--greomni` with the selected APK; it does not fall back to a desktop
browser app directory.

Instrumentation requests the exact twelve `Class#method` names through
`AndroidJUnitRunner`. The grader requires matched per-method start/success records,
matching declared test count, a matching JUnit `OK` summary and a successful final
instrumentation code. Failure, assumption, ignore/skip, missing/duplicate methods,
partial output and an outer adb exit of zero with an inner failure are rejected.

## Evidence and replay

Every command gets an exclusive log and a receipt with a new run id, source/build
binding, command, start/completion times, exit status and exact log hash. Raw mozlog
is independently checked for freshness and completeness. Sources are rehashed
after the build and after testing. Results have no PASS verdict until all selected
files/methods and the final source check pass.

A `run-ID` directory copies its build receipt, source binding and requirements. It
can therefore be archived and regraded without the original source tree or emulator:

```sh
python3 docs/android/evidence/lw-m7-27/grade.py /path/to/archived/run-ID
python3 -m unittest discover -s docs/android/evidence/lw-m7-27 -p 'test_*.py' -v
```

Archive the entire run directory, the parent build logs/receipts/config diff and the
built test artifact hashes. The replay verifies the recorded artifact binding; it
does not claim to re-open absent APKs. Receipts provide local integrity and provenance
checks, not protection against deliberate fabrication of all evidence files.

The local suite currently passes **32 synthetic tests**, including parser failures,
source/receipt tampering, foreign-run rejection, read-only planning and config
isolation. `local-tests.txt` records the actual run. Full integrated preflight,
native compilation, API lint and the 21+12 target tests remain **unrun**. A failure
in those real tests must be investigated in the source/test environment; it must
not be converted to a parser allowlist or presented as a release behavior pass.
