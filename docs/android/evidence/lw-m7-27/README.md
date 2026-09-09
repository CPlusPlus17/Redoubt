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
requires 146 product/test/source dependency paths, including all selected native
tests, the pending Android-excluded uninstall test, and instrumentation classes.
It separately verifies 82 audited harness/build/preference/permission/fixture files against
`harness-sources.json`, read from the frozen Firefox 153.0esr beta tree or the
merged Tasks31/35/36 source candidates. Task35 supersedes two shared Task31
pins; Task36 supersedes five shared Task35 pins. Stale native4, pre-correction
fixtures or superseded shared source cannot pass. Those pins describe the audited source subset, not a fresh
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
mozconfig and frozen source path, with the retained proposed native-test manifest.
The frozen source path is a provisional location, not the composed target tree.
This plan is explicitly **NOT RUN**, and no proposed workspace was created;
actual preflight requires the complete matching integrated source.

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
| Android extension permissions | Four Task31 tasks: acknowledged disk writes, failed-write retry, JSON/KV cache reconciliation and the original GeckoView uninstall cleanup result |
| existing extension permissions | All 26 tasks through the in-process Android manifest, including KV recovery |
| existing permission uninstall | Three tasks remain **pending**: upstream excludes this entire file on Android (Bug 1350559); not counted as execution |
| packaged cookie rules | Android snapshot and validated test-rule tasks, plus the existing test-pref task |
| private cookie lifetime | Five tasks including held native initialization, earlier-observer replacement, stale dispatch, normal/private isolation and autostart |
| Android translations | Two packaged catalog/WASM and passive missing-model/cache-deletion tasks |
| GeckoView canvas/WebGL | All eight `CanvasPermissionTest` methods |
| GeckoView translations | `cacheOnlyTranslationUsesRealCatalogAndPreservesMissingModels` |
| GeckoView private cookie lifetime | All three `CookieBannerPrivateSessionTest` methods |
| native preference save API | Two xpcshell tasks: no-current-profile rejection and actual backup ordering/failure/suspend-flush |
| native extension update admission | Six xpcshell tasks through the in-process Android manifest |
| GeckoView current-profile save API | Three real-profile I/O methods: independent snapshots, clean-file recreation/reset, failed-write/suspend/retry |
| GeckoView automatic extension update controls | Two methods: combined/mixed prefs and native completion order |
| GeckoView preference-service shutdown | One method in a fresh, separately guarded instrumentation process; full application exit is outside its scope |
| native global privacy service | Five Task36 xpcshell cases with real native pref/permission services and an explicit injected-save boundary; no actual disk-persistence claim |
| GeckoView global privacy API | Three Task36 methods: acknowledged boolean/reset branches, referrer value1 and invalid-public-input rejection |

Each xpcshell file runs separately and sequentially with a new raw mozlog file.
The grader requires suite/file start and successful completion, every required
named task's start and finish, no required skip, and no failed assertion, crash
or error-level harness diagnostic. A PASS for the file alone is insufficient.
Four explicitly named desktop-only tasks in the cookie list file may skip on
Android; they are not counted as executed Android tests. The remote xpcshell
command uses `--greomni` with the selected APK; it does not fall back to a desktop
browser app directory.

Permission files additionally use the existing `--tag in-process-webextensions`
selector and require the audited `xpcshell.toml:` test-ID prefix. This excludes
duplicate remote/legacy variants without changing any source manifest or skip.
The existing permissions setup calls `_uninit()` with the test backend selector
at its default `false`, so KV recovery must execute even on a non-Nightly build.
Task31 separately switches between real JSON and KV stores inside its own test.
[permission-coverage.md](permission-coverage.md) records the source/skip analysis.

`pending_xpcshell` preserves the three Android-excluded uninstall task names and
requires their source hashes at preflight. They are not invoked through a forced
manifest override. After every runnable gate passes, the aggregate remains
**PENDING**, and both `driver.py run` and archived `grade.py` exit **3** while that
requirement is open. No skipped file or new mock uninstall test closes it.

Ordinary instrumentation requests the exact twenty `Class#method` names through
`AndroidJUnitRunner`. The grader requires matched per-method start/success records,
matching declared test count, a matching JUnit `OK` summary and a successful final
instrumentation code. Failure, assumption, ignore/skip, missing/duplicate methods,
partial output and an outer adb exit of zero with an inner failure are rejected.

## Task35 real-profile and shutdown boundary

`task35-inventory.json` retains the exact corrected Task35 inventory from commit
`67300f8`. Its SHA is required by planning/preflight, source bindings, build
selection and archived replay. `preference-source-bindings.json` records the
independent comparison of actual Task31/35 source bytes with their committed
source receipts. `previous-selection.json` retains the preceding complete
selection; host regressions require all original 51+12 cases and the three
Android exclusions unchanged. Task35 adds eight xpcshell tasks, five ordinary
instrumented methods and one separately invoked shutdown method: **59+17+1**.

Xpcshell does not call `InitializeUserPrefs`, including the Android
`-xpcshell` entry point. Its corrected tests must reject an uninitialized native
current profile and may inspect real explicit backup writes. They cannot substitute
for the three `PrefSaveFileAsyncTest` methods or the two
`WebExtensionUpdateSettingsTest` methods that use `RuntimeCreator`'s normal
GeckoView profile. The privileged `browser.test` I/O helper belongs only to the
instrumentation extension. None of these methods runs in the installed release app.

After all ordinary methods complete successfully, the driver runs this sequence
against the explicit disposable emulator. It does not wipe any profile:

```text
adb -s TEST_SERIAL shell ps -A -w -o PID,NAME
adb -s TEST_SERIAL shell am force-stop org.mozilla.geckoview.test
adb -s TEST_SERIAL shell ps -A -w -o PID,NAME
adb -s TEST_SERIAL shell am instrument -w -r \
  -e class org.mozilla.geckoview.test.PrefSaveFileAsyncShutdownTest \
  -e redoubtAllowProfileShutdown true \
  org.mozilla.geckoview.test/androidx.test.runner.AndroidJUnitRunner
```

The ordinary `am instrument -w` must have returned before the stop sequence.
Both process snapshots must be complete, include PID 1/init, and use the full
`NAME` column; after force-stop, neither the exact test package nor any of its
colon-suffixed child processes may remain. A command or parser failure stops
before shutdown. The driver does not stop the release application or the separate
xpcshell test_runner. The process listing is a bounded observation, not a claim
that no unrelated external actor can launch the test app afterward.

`process-list-source.txt` and `process-list-source.c.gz` retain the pinned primary
Toybox source receipt and exact original source bytes: `NAME` is
`argv[0]`, `CMD` is the kernel thread name, and `-w` expands output width. Actual
Toybox command support, process visibility, normal GeckoView initialization and
I/O behavior remain target prerequisites to verify; unsupported or incomplete
output fails closed. The readonly primary source was fetched from
[Android Toybox ps.c](https://android.googlesource.com/platform/external/toybox/+/59a869a838cfadbf6bc41cb400471ca9d2cae9b5/toys/posix/ps.c).

The shutdown helper intentionally leaves its test-only marker in its closed
profile. The driver never clears that data to make a rerun pass. Reusing the same
persistent test profile may fail the helper's existing-marker guard; retain that
failure and use a fresh disposable test environment for a new complete run.

The shutdown class requires **both** the exact class selector (no `#method` or
comma-separated class list) and string opt-in `true`. Its assumption skip is
correct when a broad suite runs, but does not satisfy this driver's named gate.
Missing/ignored/skipped/partial/failed shutdown results remain unaccepted. Replay
requires the separate shutdown log, all three process-boundary receipts, matching
commands/device/source/build/run identities, and strictly sequential timing.
An empty successful force-stop log is valid only for that exact bound command;
empty test or process-list logs still fail. The isolated invocation acknowledges
the native preference-service shutdown observer and saved bytes; it does not
establish the complete application's shutdown or release durability after death.

## Task36 inventory and composed source

`task36-inventory.json` is derived from the actual test definitions and all 21
files in Task36's authoritative `source-files.json`. Planning/preflight binds its
hash and the retained `task36-source-receipt.json`, all five exact xpcshell names,
three ordinary GeckoView methods, explicit
injected-save scope and all 21 final source hashes. The native tests use real
preference/permission services, but supply a save function. Their recorded
`execution_scope` therefore remains explicit in graded results; an injected
completion cannot establish current-profile disk durability. The three API
methods require normal GeckoRuntime initialization and the production controller.
They check acknowledged native state/validation; Task35's separate actual-I/O
methods retain their independent role. Assumption skips remain unaccepted.

`previous-task35-selection.json` retains all 59+17+1 preceding requirements and
the three Android exclusions. The current selection is **64 xpcshell tasks,
20 ordinary instrumented methods and one guarded shutdown method**. Shutdown
remains last and separate; Task36 adds no opt-in or preference mutation to the
driver's command line. Fenix runtime behavior after restart/navigation/network
changes remains separate release-APK acceptance.

`global-privacy-source-bindings.json` records independent hashing of actual
Task36 source and 45 materialized files from coverage_map's final scoped
29/31/35/36 composition. The five shared Task35→36 before/after hashes match the
producer's final source; native preference I/O and test-support hashes remain
unchanged. The producer receipt and product manifest are retained separately.
This is scoped source comparison, not compilation or a full integrated test
preflight. Root's `301e662` Bundle constructor correction is separately retained in
`root-bundle-source-overlay.json`. The producer then replayed the corrected
composition; the updated product manifest differs only in that existing Fenix
body. I independently compared the root-retained and newly composed body bytes.
The three `pre-bundle-*` files preserve the earlier product/test manifests and
receipt. Task36's refreshed source receipt (`35062553`) changes only that scoped
predecessor digest; all 21 output hashes remain unchanged. Neither scoped replay
nor this driver preparation claims a successful corrected target build.

The product source union has 230 bindings. Four unchanged files already required
by Task27 are absent from that changed-file union: `Extension.sys.mjs`,
`ExtensionTaskScheduler.sys.mjs`, `test_ext_permissions.js` and
`test_ext_permissions_uninstall.js`. Their actual frozen bodies were hashed
against existing audited pins and retained in `native-test-extra-source-sha256.txt`.
`proposed-native-test-source-sha256.txt` combines those four with the reviewed
product union, preserves every existing binding, contains 234 distinct paths and
covers all 146 required paths. Use that reviewed test manifest only with the
complete matching target source. The driver still separately verifies the other
unchanged harness pins; it does not waive a missing source or test.

## Five test-fixture corrections

The current 230-file product manifest is
`7af4e037a693c46a86403d1d4bf31df66b81891c4a3857a73d222ca66fff597b`.
Adding the same four supplemental bindings produces 234 distinct native-test
paths, manifest SHA256
`214cf2eea22899ecadfa913d8653a223ff1e10eb85e8746b6dc3dab6f4af67cb`.
The five fixture changes are recorded in `fixture-source-overlays.json`; all
other product rows and every native/test selection remain identical. These are
the accounts primitive matcher, origin-storage nested mock, two cookie fixture
fixes, and the permissions feature test's coroutine opt-in. Current compiled APK
source remains `c53736…`; the separate current 165-file test manifest is `659bf836…`.
`fixture-current165-source-sha256.txt` preserves that exact test manifest.

The five actual corrected bodies now have independent audited pins (82 total),
and the accounts fixture joins the explicitly required source paths (146 total).
`pre-fixture-source.tar.gz` retains the five original bodies. Host regressions
prove that none can pass source preflight even with its own internally valid
manifest; they do not rerun Kotlin behavior. Original pre-fixture manifests,
requirements, current-receipt snapshots and preparation evidence are preserved
under `pre-fixture/`; earlier `pre-bundle-*` and Bundle overlay history are intact.

`fixture-source-comparison.json` records independent hashing of 50 audited
materialized bodies from the frozen fifth-overlay handoff, and rehashing of the
four unchanged supplemental inputs against the frozen source. Task36's current
source receipt advances to `499f4e0`, SHA256
`10e5317ec0cc4a88e96df858c16ba377978a6635292548d32549f5056d3321e7`;
its 21 output pins and all native/GV implementation bytes remain unchanged.
This source refresh preserves 64 runnable xpcshell cases, 20 ordinary GeckoView
methods and the one separate guarded shutdown, plus the three Android exclusions.
Task37 is deliberately outside this refresh and requires its own reviewed
inventory/composed source update. Target build and test execution remain unrun
by these preparation steps.

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

The local suite currently passes **62 host driver/grader tests**, including
parser failures, stale/foreign command receipts, source/selection tampering,
pre-Task35 native bytes, missing/failed process boundaries and guarded shutdown
skips. `local-tests.txt` records the observed invocation. Full integrated
preflight, native compilation, API lint, **64 xpcshell tasks and 20+1 instrumented
methods remain unrun**. Three further upstream uninstall tasks remain
Android-excluded and pending. The aggregate therefore stays PENDING/exit 3 even
if every currently runnable gate passes. A real failure must be investigated in
the source/test environment, never converted into a parser allowlist.

The Task36 inventory followup starts from root `bf5af6c`; metadata is `ff21bd3`.
The previous corrected-preference driver was integrated as `4b9e30a` (original
`6054033`, metadata `076fcad`). Earlier permission preparation is retained at
`ceb333e`, and original driver preparation at
`5b472bc3afd4882d38c6ccbfc8c712f2cc002f91`. Their snapshots describe their older
selection and host-test counts. No guest, build or device command ran here.
