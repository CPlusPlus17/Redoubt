# Current167 APK and runtime checkpoint

These drivers are prepared but **not run on the guest**. Local Python syntax and
21 synthetic input/result contract tests pass. No new APK, emulator, resource or
browser acceptance is claimed here. Root owns launch and evidence collection.

The fourth full test invocation `784b8ec5172a487d83970eb9879dee3c` failed its
allowance gate, so its `f55095…` source cannot qualify for these drivers. Build
configuration capture instead requires an explicit source stage, all-167 manifest
digest, test evidence directory, exact test service and actual invocation. It
never picks the newest directory or treats an elapsed wait as success.

The selected service must have `RemainAfterExit=yes` and a successful terminal
state. The selected complete source manifest, before/after source checks,
`finished.txt`, container/AC/full-allowance/fresh-XML gate exit files, summary and
all seven XML archives are required and pinned in the reviewed config. Fenix's
upstream allowance is retained: Gradle exit 1 is accepted only when its sole
failed task is `:fenix:testDebugUnitTest` and both independent gates passed.
Compiler failures, skipped required suites and incomplete source checks cannot
borrow that allowance. The existing grader owns detailed class/count grading;
these drivers consume its exact retained outputs and terminal invocation.

Both drivers verify all 167 current source hashes and all three native4 AARs
before and after work, plus the configured original APK hashes. The three archives
actually passed from `work/aar` must equal the retained native input manifest.
The container is the explicit image
`sha256:c5b57d94cf9e0ed1de7061cee9e0dbfde19d5651e3e2f3824b0e1466116fd687`,
with build date `20260906190000`. The build uses the existing bounded Podman
wrapper, `--skip-gecko`, all three native4 inputs and `work/out/gradle-home` as
the cache seed. It writes only its new APK output namespace and the ordinary
APK build's existing owned objdir; it does not rebuild Gecko. The release variant
uses disposable Android debug signing via the canonical build script.

Fixed fresh namespaces beneath `/home/runner/work/feature-parity-20260908`:

- APK output: `fenix-regression-apk-output`.
- APK evidence: `evidence/fenix-regression-apk`.
- Runtime workspace: `fenix-regression-runtime`.
- Runtime evidence: `evidence/fenix-regression-runtime`.

Existing namespaces are rejected. The old `out/apk` candidates are read and
hashed before and after; they are never selected for new runtime acceptance.
The separate runtime config inherits the successful new APK's exact input
selection and binds all four new APKs and their resource verdicts.

## Explicit operator sequence

After the next full test service passes, an authorized operator runs the following
inside the guest as `runner`. Replace every angle-bracket argument with the
independently reviewed actual value. The native manifest can remain the retained
unchanged `evidence/fenix-regression-source/native-input-sha256.txt` even when the
new source stage has another name.

```sh
cd /home/runner/work/feature-parity-20260908/repo
python3 docs/android/evidence/lw-m7-12/current167/build.py --print-config \
  --source-stage <absolute-selected-source-stage> \
  --test-evidence <absolute-successful-test-evidence> \
  --source-manifest-sha256 <reviewed-167-manifest-sha256> \
  --test-service-name <exact-retained-tests.service> \
  --test-invocation <actual-32-hex-invocation> \
  --native-manifest <absolute-retained-native-input-sha256.txt> \
  > /new/private/apk-config.json
```

Review that concrete JSON and compute its SHA-256. Plain `--config` plus
`--config-sha256` validates and prints the plan without building. Only an explicit
`--run` starts the build, inside the matching retained service:

```sh
systemd-run --user --unit=redoubt-fenix-regression-apk-20260909.service \
  --property=RemainAfterExit=yes --property=WorkingDirectory=/home/runner/work/feature-parity-20260908/repo \
  python3 docs/android/evidence/lw-m7-12/current167/build.py \
  --config /absolute/apk-config.json --config-sha256 <reviewed-config-sha256> --run
```

The result requires exactly four APKs. Each invokes the actual shortcut resource
checker with the known build `aapt2`, SHA-256
`c9f30b34c02fd48165251541125c3b7f21b98624e0f8341436fc65a84095e5d6`.
Both exit 0 and its explicit successful structured APK/tool/resource receipt are
required. A nonempty failure log never qualifies. Every resource log and new APK
digest is retained; `result.json` can become `PASS` only after all four succeed.

After that APK service is successfully terminal, capture and review the new
runtime config separately:

```sh
python3 docs/android/evidence/lw-m7-12/current167/runtime.py --print-config \
  > /new/private/runtime-config.json
systemd-run --user --unit=redoubt-fenix-regression-runtime-20260909.service \
  --property=RemainAfterExit=yes --property=WorkingDirectory=/home/runner/work/feature-parity-20260908/repo \
  python3 docs/android/evidence/lw-m7-12/current167/runtime.py \
  --config /absolute/runtime-config.json --config-sha256 <reviewed-config-sha256> --run
```

Runtime requires no existing device, including an offline or unauthorized one,
and creates its own emulator workspace. The exact canonical `android-smoke.sh`
runs full uBO lifecycle and the default baseline, followed by
`android-pref-audit.sh`. No harness implementation is modified. JSON grading
requires all 10 lifecycle checks and all 8 baseline checks, the new x86_64 APK
hash, the actual harness hash, completion, no failed checks and no injected prefs.
The pref audit's ordinary post-startup must-lock scope is unchanged; it does not
claim every settings screen was opened. Raw emulator logs, AVD data, pcaps and
pref work remain in the fresh workspace for collection. The created emulator is
stopped afterward, including on a measured gate failure.

Build stage timeout is four hours; uBO lifecycle is one hour, baseline 45 minutes,
pref audit 20 minutes and each resource checker three minutes. A timeout fails
the checkpoint and requests process-group termination. Hard service/process loss
can leave `RUNNING` or incomplete evidence, which cannot pass a later gate.
The guest owner remains responsible for service-level cleanup if interrupted.

## Local replay

```sh
python3 docs/android/evidence/lw-m7-12/current167/test_contracts.py
python3 -m py_compile docs/android/evidence/lw-m7-12/current167/*.py
```

The tests use local synthetic files and controlled service responses to prove
rejection of missing checks, failed/stale/tainted reports, wrong APK/tool identity,
bad manifests and wrong terminal service state. They do not establish actual
service launch, SDK compatibility, compilation or Android runtime success.
