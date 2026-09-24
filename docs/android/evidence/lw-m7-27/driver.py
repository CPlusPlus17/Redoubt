#!/usr/bin/env python3
"""Plan/preflight isolated Android native tests; mutations require build/run --execute."""
import argparse
import difflib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile

from grade import (InvalidResult, bound_log, grade_instrumentation, grade_xpcshell, grade_run,
                   require, sha, shutdown_selection, instrumentation_arguments, process_snapshot,
                   PROCESS_LIST_ARGUMENTS, TEST_PACKAGE, TEST_COMPONENT, check_build_plan)

HERE = Path(__file__).resolve().parent
REQUIREMENTS = HERE / 'requirements.json'
HARNESS = HERE / 'harness-sources.json'
TASK35_INVENTORY = HERE / 'task35-inventory.json'
TASK36_INVENTORY = HERE / 'task36-inventory.json'
TASK36_SOURCE_RECEIPT = HERE / 'task36-source-receipt.json'
TASK37_INVENTORY = HERE / 'task37-inventory.json'
TASK37_SOURCE_RECEIPT = HERE / 'task37-source-receipt.json'


def json_write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def source_path(source, name):
    require(name and not Path(name).is_absolute() and '..' not in Path(name).parts, 'unsafe manifest path')
    path = source / name
    require(path.is_file() and path.resolve().is_relative_to(source), f'missing/escaping source: {name}')
    return path


def reviewed_requirements():
    req = json.loads(REQUIREMENTS.read_text())
    require(sha(TASK35_INVENTORY) == req.get('task35_inventory_sha256'), 'Task35 inventory changed/unbound')
    inventory = json.loads(TASK35_INVENTORY.read_text())
    for item in inventory['xpcshell_method_sets']:
        specs = [spec for spec in req['xpcshell'] if spec['path'] == item['source']]
        require(len(specs) == 1 and specs[0]['tasks'] == item['named_tests'] and not specs[0]['allowed_skips'],
                'Task35 named xpcshell inventory changed')
    require(set(inventory['regular_instrumentation_methods']) <= set(req['instrumentation']),
            'Task35 ordinary instrumentation omitted')
    require(shutdown_selection(req) == inventory['separate_shutdown_invocation'],
            'Task35 isolated shutdown inventory changed')
    require(set(inventory['extra_required_source_paths']) <= set(req['product_paths']),
            'Task35 real-profile helper/class source binding omitted')
    require(sha(TASK36_INVENTORY) == req.get('task36_inventory_sha256'), 'Task36 inventory changed/unbound')
    global_privacy = json.loads(TASK36_INVENTORY.read_text())
    require(sha(TASK36_SOURCE_RECEIPT) == global_privacy['source_receipt_sha256'],
            'Task36 authoritative source receipt changed/unbound')
    for item in global_privacy['xpcshell_method_sets']:
        specs = [spec for spec in req['xpcshell'] if spec['path'] == item['source']]
        require(len(specs) == 1 and specs[0]['tasks'] == item['named_tests'] and not specs[0]['allowed_skips'] and
                specs[0].get('execution_scope') == item['execution_scope'],
                'Task36 native-service inventory or injected-save scope changed')
    require(set(global_privacy['regular_instrumentation_methods']) <= set(req['instrumentation']),
            'Task36 ordinary real-GeckoRuntime methods omitted')
    require(set(global_privacy['extra_required_source_paths']) <= set(req['product_paths']),
            'Task36 implementation/test source binding omitted')
    audited = json.loads(HARNESS.read_text())['files']
    require(all(audited.get(name) == digest for name, digest in global_privacy['required_source_hashes'].items()),
            'Task36 final source pins were replaced by stale/mismatched shared hashes')
    require(sha(TASK37_INVENTORY) == req.get('task37_inventory_sha256'), 'Task37 inventory changed/unbound')
    cleanup = json.loads(TASK37_INVENTORY.read_text())
    require(sha(TASK37_SOURCE_RECEIPT) == cleanup['source_receipt_sha256'],
            'Task37 authoritative source receipt changed/unbound')
    for item in cleanup['xpcshell_method_sets']:
        specs = [spec for spec in req['xpcshell'] if spec['path'] == item['source']]
        require(len(specs) == 1 and specs[0]['tasks'] == item['named_tests'] and not specs[0]['allowed_skips'] and
                specs[0].get('execution_scope') == item['execution_scope'],
                'Task37 native-cookie inventory or execution scope changed')
    require(set(cleanup['regular_instrumentation_methods']) <= set(req['instrumentation']),
            'Task37 real FrameLoader methods omitted')
    require(set(cleanup['extra_required_source_paths']) <= set(req['product_paths']),
            'Task37 implementation/test source binding omitted')
    require(all(audited.get(name) == digest for name, digest in cleanup['required_source_hashes'].items()),
            'Task37 final source pins were replaced by stale/mismatched shared hashes')
    require(len(req['instrumentation']) == len(set(req['instrumentation'])), 'duplicate ordinary methods')
    return req


def run_instrumentation(adb, source, env, out, timeout, metadata, requirements):
    selected = requirements['instrumentation']
    ordinary = execute(adb + instrumentation_arguments(requirements), source, env,
                       out / 'instrumentation.log', timeout, metadata)
    results = [grade_instrumentation(bound_log(ordinary, out), selected)]
    shutdown = shutdown_selection(requirements)
    if shutdown is None:
        return results
    before = execute(adb + PROCESS_LIST_ARGUMENTS, source, env,
                     out / 'instrumentation-processes-before.log', 30, metadata)
    process_snapshot(bound_log(before, out))
    stop = execute(adb + ['shell', 'am', 'force-stop', TEST_PACKAGE], source, env,
                   out / 'instrumentation-stop.log', 30, metadata)
    bound_log(stop, out, allow_empty=True)
    after = execute(adb + PROCESS_LIST_ARGUMENTS, source, env,
                    out / 'instrumentation-processes-after.log', 30, metadata)
    require(not process_snapshot(bound_log(after, out)), 'old test process remains; shutdown not started')
    isolated = execute(adb + instrumentation_arguments(requirements, shutdown=True), source, env,
                       out / 'instrumentation-shutdown.log', timeout, metadata)
    results.append(grade_instrumentation(bound_log(isolated, out), shutdown['expected_methods']))
    return results


def source_binding(source, manifest):
    rows = {}
    for line in manifest.read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64}) [ *](.+)', line)
        require(match is not None, 'expected exact SHA256SUMS source manifest format')
        digest, name = match.groups()
        require(name not in rows, f'duplicate source path: {name}')
        path = source_path(source, name)
        require(sha(path) == digest, f'source hash mismatch: {name}')
        rows[name] = digest
    req = reviewed_requirements()
    native_specs = req['xpcshell'] + req.get('pending_xpcshell', [])
    required = set(req['product_paths']) | {s['path'] for s in native_specs}
    require(required <= rows.keys(), 'source manifest omits required product/test paths: ' + ', '.join(sorted(required - rows.keys())))
    audited = json.loads(HARNESS.read_text())['files']
    for name, digest in audited.items():
        require(sha(source_path(source, name)) == digest, f'audited harness changed: {name}; review/re-pin before running')
    # Confirm names still exist in the actual sources being compiled, not just this inventory.
    for spec in native_specs:
        text = source_path(source, spec['path']).read_text()
        for task in spec['tasks']:
            require(re.search(r'function\s+' + re.escape(task) + r'\s*\(', text), f'missing native task: {task}')
    methods = req['instrumentation'] + req['shutdown_instrumentation']['expected_methods']
    for method in methods:
        klass, name = method.rsplit('#', 1)
        path = 'mobile/android/geckoview/src/androidTest/java/' + klass.replace('.', '/') + '.kt'
        require(path in rows, 'missing instrumentation source binding: ' + path)
        require(re.search(r'fun\s+' + re.escape(name) + r'\s*\(', source_path(source, path).read_text()), 'missing method: ' + method)
    return {'manifest_sha256': sha(manifest), 'product_files': rows, 'audited_harness': audited,
            'requirements_sha256': sha(REQUIREMENTS), 'harness_pins_sha256': sha(HARNESS),
            'task35_inventory_sha256': sha(TASK35_INVENTORY),
            'task36_inventory_sha256': sha(TASK36_INVENTORY),
            'task36_source_receipt_sha256': sha(TASK36_SOURCE_RECEIPT),
            'task37_inventory_sha256': sha(TASK37_INVENTORY),
            'task37_source_receipt_sha256': sha(TASK37_SOURCE_RECEIPT)}


def selection_arguments(spec):
    """Use audited manifest tags, never override upstream platform exclusions."""
    tags = spec.get('tags', [])
    require(isinstance(tags, list) and all(re.fullmatch('[a-z][a-z0-9-]*', tag) for tag in tags), 'invalid test selection tag')
    return [part for tag in tags for part in ['--tag', tag]] + [spec['path']]


def derive_config(original, objdir):
    require('\n' not in str(objdir) and re.fullmatch(r'[A-Za-z0-9_./-]+', str(objdir)), 'object directory must be shell-safe')
    require(re.search(r'^ac_add_options --enable-(?:application|project)=mobile/android$', original, re.M), 'not a production Android config')
    require(len(re.findall(r'^ac_add_options --disable-tests$', original, re.M)) == 1, 'expected one production --disable-tests option')
    require(not re.search(r'^ac_add_options --enable-tests$', original, re.M), 'input already test-enabled')
    require(len(re.findall(r'^ac_add_options --target=.+$', original, re.M)) == 1, 'ambiguous production target')
    require(len(re.findall(r'^ac_add_options --enable-android-subproject=fenix$', original, re.M)) == 1, 'expected Fenix production subproject')
    derived = re.sub(r'^ac_add_options --disable-tests$', 'ac_add_options --enable-tests', original, flags=re.M)
    derived = re.sub(r'^ac_add_options --target=.+$', 'ac_add_options --target=x86_64-linux-android', derived, flags=re.M)
    derived = re.sub(r'^ac_add_options --enable-android-subproject=fenix$', 'ac_add_options --enable-android-subproject=geckoview_example', derived, flags=re.M)
    derived = re.sub(r'^mk_add_options MOZ_OBJDIR=.*\n?', '', derived, flags=re.M)
    derived += '\n# LW-M7-27: separate test artifact; never a release acceptance candidate.\nmk_add_options MOZ_OBJDIR=' + str(objdir) + '\n'
    return derived


def require_completed_identity(build, plan, workspace):
    saved = json.loads((workspace / 'plan.json').read_text())
    check_build_plan(build, saved, workspace / 'plan.json')
    for key in ('build_date', 'product_revision_operator_supplied'):
        require(saved.get(key) == plan.get(key), 'run differs from completed build: ' + key)


def execute(command, cwd, env, log, timeout, bindings):
    """Exclusive logs, bounded process group, explicit completion receipt even on timeout."""
    started = time.time_ns()
    with log.open('xb') as output:
        created = time.time_ns()
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            rc = proc.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            rc = 124
    receipt = dict(bindings, command=command, cwd=str(cwd), started_ns=started,
                   finished_ns=time.time_ns(), log_created_ns=created, exit=rc,
                   log=log.name, log_sha256=sha(log))
    json_write(log.with_suffix(log.suffix + '.receipt.json'), receipt)
    return receipt


def query(command):
    return subprocess.check_output(command, text=True, timeout=120)


def inspect_apk(path, analyzer, signer):
    manifest = ET.fromstring(query([analyzer, 'manifest', 'print', str(path)]))
    android = '{http://schemas.android.com/apk/res/android}'
    app = manifest.find('application')
    require(app is not None and app.get(android + 'debuggable') == 'true', 'test APK must be debuggable')
    cert = query([signer, 'verify', '--print-certs', str(path)])
    require(re.search(r'^Signer #1 certificate DN: .*CN=Android Debug(?:,|$)', cert, re.M), 'test APK is not signed with the ordinary Android debug certificate')
    with zipfile.ZipFile(path) as apk:
        libraries = [n for n in apk.namelist() if n.endswith('/libxul.so')]
        require(libraries == ['lib/x86_64/libxul.so'], 'test APK must contain exactly the x86_64 Gecko library')
        with apk.open(libraries[0]) as stream:
            header = stream.read(20)
        require(header[:5] == b'\x7fELF\x02' and header[18:20] == b'>\x00', 'not Android x86_64 ELF64')
    instrument = manifest.find('instrumentation')
    return {'path': str(path), 'sha256': sha(path), 'size': path.stat().st_size,
            'package': manifest.get('package'), 'debug_certificate': cert,
            'instrumentation': None if instrument is None else {
                'name': instrument.get(android + 'name'), 'targetPackage': instrument.get(android + 'targetPackage')}}


def container_environment():
    """Refuse direct host builds; preserve the immutable image's configured toolchains."""
    require(Path('/run/.containerenv').is_file(), 'build/run must execute in the bounded Podman test container')
    image = os.environ.get('REDOUBT_NATIVE_TEST_IMAGE', '')
    expected = json.loads(REQUIREMENTS.read_text())['build_image_sha256']
    require(image == expected, 'missing/unapproved immutable build image marker')
    require(os.environ.get('MOZBUILD_STATE_PATH') == '/root/.mozbuild', 'do not replace the image compiler/toolchain root')
    require(not Path('/home/mgysin').exists(), 'host home must not be mounted')
    cgroup = Path('/sys/fs/cgroup')
    memory = (cgroup / 'memory.max').read_text().strip()
    swap = (cgroup / 'memory.swap.max').read_text().strip()
    cpu = (cgroup / 'cpu.max').read_text().split()
    require(memory.isdigit() and 0 < int(memory) <= 17 * 1024**3, 'container memory limit missing/too large')
    require(swap.isdigit() and int(swap) <= 6 * 1024**3, 'container swap limit missing/too large')
    require(len(cpu) == 2 and all(x.isdigit() for x in cpu) and 0 < int(cpu[0]) <= 6 * int(cpu[1]), 'container CPU limit missing/too large')
    root = Path('/root/.mozbuild')
    tools = {}
    for name in ['clang/bin/clang', 'node/bin/node', 'cbindgen/cbindgen', 'nasm/nasm']:
        path = root / name
        require(path.is_file() and os.access(path, os.X_OK), 'missing pinned toolchain executable: ' + name)
        tools[name] = {'sha256':sha(path), 'version':query([str(path), '-v' if name.startswith('nasm/') else '--version'])}
    require((root / 'sysroot-wasm32-wasi/lib/wasm32-wasi/libc.a').is_file(), 'missing image WASI sysroot')
    paths = {}
    for name in ['ANDROID_NDK_HOME', 'JAVA_HOME', 'CARGO_HOME', 'RUSTUP_HOME']:
        path = Path(os.environ.get(name, '/missing'))
        require(path.is_dir() and path.is_relative_to(root), 'toolchain environment moved outside image root: ' + name)
        paths[name] = str(path)
    return {'image_sha256':image, 'memory_max':memory, 'swap_max':swap, 'cpu_max':cpu,
            'toolchain_root':str(root), 'toolchains':tools, 'configured_paths':paths}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'preflight', 'build', 'run'])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-manifest', type=Path, required=True, help='Complete integrated product/test SHA256SUMS, relative to source')
    parser.add_argument('--product-mozconfig', type=Path, required=True)
    parser.add_argument('--product-revision', required=True, help='Reviewed product source-plan git commit, recorded as operator-supplied provenance')
    parser.add_argument('--build-date', required=True, help='Same MOZ_BUILD_DATE as the associated product build')
    parser.add_argument('--workspace', type=Path, required=True, help='NEW dedicated workspace outside the production source/objdirs')
    parser.add_argument('--execute', action='store_true', help='Authorize the selected explicit build or test-device mutations')
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', help='Explicit disposable test emulator serial; never auto-select a device')
    parser.add_argument('--apkanalyzer', default='apkanalyzer')
    parser.add_argument('--apksigner', default='apksigner')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--build-timeout', type=int, default=21600)
    parser.add_argument('--test-timeout', type=int, default=1800)
    return parser.parse_args(argv)


def main():
    args = parse_args()
    source = args.source.resolve()
    workspace = args.workspace.resolve()
    require(source.is_dir() and (source / 'mach').is_file(), 'missing actual Gecko source/mach')
    require(not workspace.is_relative_to(source) and not source.is_relative_to(workspace), 'test workspace must be separate from source/production objdirs')
    require(workspace.name.startswith('redoubt-native-tests-'), 'workspace name must start redoubt-native-tests-')
    require(re.fullmatch('[a-f0-9]{40}', args.product_revision), 'expected exact reviewed source-plan commit')
    require(re.fullmatch('[0-9]{14}', args.build_date), 'expected fixed product build date')
    require(1 <= args.jobs <= 4 and 1 <= args.build_timeout <= 43200 and 1 <= args.test_timeout <= 7200, 'invalid resource/time bounds')
    config = derive_config(args.product_mozconfig.read_text(), workspace / 'obj-x86_64-tests')
    commands = [[sys.executable, 'mach', 'build', '-j' + str(args.jobs)],
                [sys.executable, 'mach', 'gradle', 'test_runner:assembleDebug',
                 'geckoview:assembleDebugAndroidTest', '--no-daemon', '--max-workers=1']]
    plan = {'status': 'NOT RUN', 'source': str(source), 'workspace': str(workspace),
            'product_revision_operator_supplied': args.product_revision, 'build_date': args.build_date,
            'product_mozconfig_sha256': sha(args.product_mozconfig),
            'config_diff': ''.join(difflib.unified_diff(args.product_mozconfig.read_text().splitlines(True), config.splitlines(True), fromfile='production.mozconfig', tofile='test.mozconfig')),
            'commands': commands, 'test_selection': reviewed_requirements(),
            'device_mutations': 'run --execute only: install two debug test APKs; xpcshell harness pushes utilities/test fixtures to a unique remote root; instrumentation creates test profiles; after ordinary methods finish, only org.mozilla.geckoview.test is force-stopped and verified absent before the guarded shutdown class starts in a fresh process. No release app install, wipe or uninstall.'}
    if args.action == 'plan':
        print(json.dumps(plan, indent=2))
        return
    binding = source_binding(source, args.source_manifest)
    if args.action == 'preflight':
        print(json.dumps(dict(plan, source_binding=binding, preflight='PASS; target build/tests NOT RUN'), indent=2))
        return
    require(args.execute, 'build/run mutations require explicit --execute')
    environment = container_environment()
    env = dict(os.environ, MOZCONFIG=str(workspace / 'test.mozconfig'),
               GRADLE_USER_HOME=str(workspace / 'gradle-home'), MOZ_BUILD_DATE=args.build_date,
               CARGO_BUILD_JOBS='1', MOZ_DISABLE_ADB_INSTALL='1')
    env.pop('MOZ_OBJDIR', None)
    if args.action == 'build':
        require(not workspace.exists(), 'build requires a new workspace; it never reconfigures or resumes production objdirs')
        workspace.mkdir(parents=True)
        (workspace / 'test.mozconfig').write_text(config)
        (workspace / 'production.mozconfig').write_bytes(args.product_mozconfig.read_bytes())
        (workspace / 'gradle-home').mkdir()
        properties = Path('/root/.gradle/gradle.properties')
        if properties.is_file():
            shutil.copy2(properties, workspace / 'gradle-home/gradle.properties')
        json_write(workspace / 'container-environment.json', environment)
        json_write(workspace / 'driver-hashes.json', {p.name:sha(p) for p in [Path(__file__), HERE / 'grade.py', HERE / 'in-vm.py', REQUIREMENTS, HARNESS, TASK35_INVENTORY, TASK36_INVENTORY, TASK36_SOURCE_RECEIPT, TASK37_INVENTORY, TASK37_SOURCE_RECEIPT]})
        json_write(workspace / 'plan.json', plan)
        json_write(workspace / 'source-binding.json', binding)
        run_id = uuid.uuid4().hex
        metadata = {'run_id': run_id, 'source_binding_sha256': sha(workspace / 'source-binding.json')}
        receipts = []
        try:
            for index, command in enumerate(commands):
                receipt = execute(command, source, env, workspace / f'build-{index}.log', args.build_timeout, metadata)
                receipts.append(receipt)
                require(receipt['exit'] == 0, 'test artifact build failed; preserved logs are not a pass')
            obj = workspace / 'obj-x86_64-tests'
            info = json.loads((obj / 'mozinfo.json').read_text())
            require(info.get('os') == 'android' and info.get('processor') == 'x86_64', 'configured the wrong target')
            makefile = (obj / 'config/autoconf.mk').read_text()
            require(re.search(r'^ENABLE_TESTS\s*=\s*1\s*$', makefile, re.M), 'configured test tools are not enabled')
            native_runner = obj / 'dist/bin/xpcshell'
            require(native_runner.is_file(), 'missing actual target xpcshell tool')
            with native_runner.open('rb') as stream:
                header = stream.read(20)
            require(header[:5] == b'\x7fELF\x02' and header[18:20] == b'>\x00', 'xpcshell tool is not x86_64 ELF64')
            require((obj / 'dist/bin/components/httpd.sys.mjs').is_file(), 'missing required xpcshell HTTP helper')
            candidates = [p for p in (obj / 'gradle').rglob('*.apk') if p.is_file()]
            runner = [p for p in candidates if p.name.startswith('test_runner') and 'debug' in p.name.lower() and 'androidTest' not in p.name]
            instrumentation = [p for p in candidates if p.name.startswith('geckoview') and 'androidTest' in p.name]
            require(len(runner) == len(instrumentation) == 1, 'ambiguous/missing fresh test APK outputs')
            artifacts = [inspect_apk(p, args.apkanalyzer, args.apksigner) for p in [runner[0], instrumentation[0]]]
            require(artifacts[0]['package'] == 'org.mozilla.geckoview.test_runner', 'unexpected xpcshell app package')
            instrument = artifacts[1]['instrumentation']
            require(artifacts[1]['package'] == 'org.mozilla.geckoview.test' and instrument and instrument['targetPackage'] == artifacts[1]['package'], 'unexpected/self-target mismatch in GeckoView instrumentation')
            require(instrument['name'] == 'androidx.test.runner.AndroidJUnitRunner', 'unexpected test runner')
            require(source_binding(source, args.source_manifest) == binding, 'source changed during test build')
            json_write(workspace / 'build-receipt.json', dict(metadata, status='PASS', source=str(source),
                       plan_sha256=sha(workspace / 'plan.json'), build_date=args.build_date,
                       product_revision_operator_supplied=args.product_revision,
                       product_mozconfig_sha256=sha(args.product_mozconfig), test_mozconfig_sha256=sha(workspace / 'test.mozconfig'),
                       requirements_sha256=sha(REQUIREMENTS), artifacts=artifacts, commands=receipts,
                       xpcshell={'path':str(native_runner),'sha256':sha(native_runner)}, completed_ns=time.time_ns()))
            print('PASS separate test artifacts built and source-bound; native tests NOT RUN')
        finally:
            json_write(workspace / 'source-after-build.json', source_binding(source, args.source_manifest))
        return
    require(args.serial and re.fullmatch('[A-Za-z0-9_.:-]+', args.serial), 'explicit test emulator serial required')
    build_path = workspace / 'build-receipt.json'
    build = json.loads(build_path.read_text())
    require(build['status'] == 'PASS' and build['source'] == str(source), 'missing matching completed test build')
    require_completed_identity(build, plan, workspace)
    require(build['source_binding_sha256'] == sha(workspace / 'source-binding.json') and json.loads((workspace / 'source-binding.json').read_text()) == binding, 'test source differs from built source')
    require(build['product_mozconfig_sha256'] == sha(args.product_mozconfig) and build['test_mozconfig_sha256'] == sha(workspace / 'test.mozconfig') and (workspace / 'test.mozconfig').read_text() == config, 'test configuration changed')
    require(build['requirements_sha256'] == sha(REQUIREMENTS), 'test selection changed since build')
    for artifact in build['artifacts'] + [build['xpcshell']]:
        require(sha(artifact['path']) == artifact['sha256'], 'built test artifact changed')
    args.adb = shutil.which(args.adb)
    require(args.adb, 'missing adb executable')
    adb = [args.adb, '-s', args.serial]
    require(query(adb + ['get-state']).strip() == 'device', 'test emulator not ready')
    require(query(adb + ['shell', 'getprop', 'ro.kernel.qemu']).strip() == '1', 'device must be a disposable emulator')
    require(query(adb + ['shell', 'getprop', 'ro.product.cpu.abi']).strip() == 'x86_64', 'test emulator must be x86_64')
    run_id = uuid.uuid4().hex
    out = workspace / ('run-' + run_id)
    out.mkdir()
    metadata = {'run_id': run_id, 'source_binding_sha256': sha(workspace / 'source-binding.json'), 'build_receipt_sha256': sha(build_path)}
    json_write(out / 'invocation.json', dict(metadata, device_serial=args.serial, scope='test-only; not release APK acceptance'))
    shutil.copy2(build_path, out / 'build-receipt.json')
    shutil.copy2(workspace / 'plan.json', out / 'plan.json')
    shutil.copy2(workspace / 'source-binding.json', out / 'source-binding.json')
    shutil.copy2(REQUIREMENTS, out / 'requirements.json')
    shutil.copy2(TASK35_INVENTORY, out / 'task35-inventory.json')
    shutil.copy2(TASK36_INVENTORY, out / 'task36-inventory.json')
    shutil.copy2(TASK36_SOURCE_RECEIPT, out / 'task36-source-receipt.json')
    shutil.copy2(TASK37_INVENTORY, out / 'task37-inventory.json')
    shutil.copy2(TASK37_SOURCE_RECEIPT, out / 'task37-source-receipt.json')
    json_write(out / 'driver-hashes.json', {p.name:sha(p) for p in [Path(__file__), HERE / 'grade.py', REQUIREMENTS, HARNESS, TASK35_INVENTORY, TASK36_INVENTORY, TASK36_SOURCE_RECEIPT, TASK37_INVENTORY, TASK37_SOURCE_RECEIPT]})
    results = []
    try:
        for index, artifact in enumerate(build['artifacts']):
            receipt = execute(adb + ['install', '-r', '-t', artifact['path']], source, env, out / f'install-{index}.log', 180, metadata)
            require(receipt['exit'] == 0 and re.search(r'^Success\s*$', (out / receipt['log']).read_text(), re.M), 'test APK install failed; no automatic uninstall/wipe')
        for index, spec in enumerate(plan['test_selection']['xpcshell']):
            raw = out / f'xpcshell-{index}.jsonl'
            command = [sys.executable, 'mach', 'xpcshell-test', '--sequential', '--deviceSerial', args.serial,
                       '--adbPath', args.adb, '--apk', build['artifacts'][0]['path'],
                       '--objdir', str(workspace / 'obj-x86_64-tests'), '--remoteTestRoot', '/data/local/tmp/redoubt-tests-' + run_id,
                       '--log-raw', str(raw), *selection_arguments(spec)]
            require(not raw.exists(), 'raw log already exists')
            receipt = execute(command, source, env, out / f'xpcshell-{index}.log', args.test_timeout, metadata)
            require(raw.is_file() and raw.stat().st_mtime_ns >= receipt['started_ns'], 'missing/stale raw mozlog')
            raw_receipt = dict(receipt, log=raw.name, log_sha256=sha(raw), log_created_ns=raw.stat().st_mtime_ns)
            json_write(out / f'xpcshell-{index}.raw-receipt.json', raw_receipt)
            results.append(grade_xpcshell(bound_log(raw_receipt, out), spec))
        instrument = build['artifacts'][1]
        component = instrument['package'] + '/' + instrument['instrumentation']['name']
        require(component == TEST_COMPONENT, 'instrumentation component differs from reviewed process boundary')
        results.extend(run_instrumentation(adb, source, env, out, args.test_timeout, metadata, plan['test_selection']))
        require(source_binding(source, args.source_manifest) == binding, 'source changed during tests')
    finally:
        json_write(out / 'source-after-tests.json', source_binding(source, args.source_manifest))
    verdict = grade_run(out)
    json_write(out / 'verdict.json', verdict)
    tasks = sum(len(spec['tasks']) for spec in plan['test_selection']['xpcshell'])
    methods = len(plan['test_selection']['instrumentation']) + len(plan['test_selection']['shutdown_instrumentation']['expected_methods'])
    print(f'{verdict["status"]}: {tasks} named xpcshell tasks and {methods} instrumented methods passed; separate test build only')
    if verdict['status'] != 'PASS':
        print('Android-excluded native requirements remain pending; see verdict.json')
        raise SystemExit(3)


if __name__ == '__main__':
    try:
        main()
    except (InvalidResult, OSError, ValueError, subprocess.SubprocessError) as error:
        print('FAIL / NOT ACCEPTED:', error, file=sys.stderr)
        sys.exit(1)
