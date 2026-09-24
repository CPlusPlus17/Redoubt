"""Fixed current167 checkpoint contracts. No operation runs at import time."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
WORK = Path('/home/runner/work/feature-parity-20260908')
SOURCE = WORK / 'src'
STAGE = None
TESTS = None
NATIVE_MANIFEST = None
OUTPUT = WORK / 'fenix-regression-apk-output'
BUILD = WORK / 'evidence/fenix-regression-apk'
RUNTIME = WORK / 'evidence/fenix-regression-runtime'
RUNTIME_WORK = WORK / 'fenix-regression-runtime'
SDK = WORK / 'sdk'
CURRENT = None
IMAGE = 'sha256:c5b57d94cf9e0ed1de7061cee9e0dbfde19d5651e3e2f3824b0e1466116fd687'
DATE = '20260906190000'
AAPT = WORK / 'out/gradle-home/caches/9.5.1/transforms/7a972dbdd2c1f9526bc4e36898517d46/transformed/aapt2-8.13.2-14304508-linux/aapt2'
AAPT_SHA = 'c9f30b34c02fd48165251541125c3b7f21b98624e0f8341436fc65a84095e5d6'
SERVICES = {s: f'redoubt-fenix-regression-{s}-20260909.service' for s in ('tests', 'apk', 'runtime')}
TEST_INVOCATION = None
SELECTION = None
ABIS = ('armeabi-v7a', 'arm64-v8a', 'x86_64')
APKS = {f'fenix-{abi}-release.apk' for abi in (*ABIS, 'universal')}
DEPENDENCIES = (
    'docs/android/evidence/lw-m7-12/current167/common.py',
    'docs/android/evidence/lw-m7-12/current167/build.py',
    'docs/android/evidence/lw-m7-12/current167/runtime.py',
    'scripts/android-apk.sh', 'assets/mozconfig.android',
    'docs/android/evidence/lw-m7-15/podman-bounded.sh',
    'docs/android/evidence/lw-m7-12/run-fenix-regression-tests.sh',
    'docs/android/evidence/lw-m7-12/run-fenix-navigation-tests.sh',
    'docs/android/evidence/lw-m7-12/grade-extended-tests.py',
    'docs/android/board.py', 'docs/android/fenix-test-allowlist.yaml',
    'docs/android/evidence/lw-m7-30/check-source.py',
    'docs/android/evidence/lw-m7-30/source-files.json',
    'docs/android/evidence/lw-m7-30/source-baseline.tar.gz',
    'patches/android/no-default-shortcuts.patch',
    'scripts/android-smoke.sh', 'scripts/android-graphics-smoke.py',
    'scripts/android-pref-audit.sh', 'docs/android/expected-prefs.txt',
    'docs/android/must-lock.txt',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def select_inputs(selection):
    """One explicitly reviewed selection per driver process; never guess latest."""
    global STAGE, TESTS, NATIVE_MANIFEST, CURRENT, TEST_INVOCATION, SELECTION
    require(set(selection) == {'source_stage', 'test_evidence', 'source_manifest_sha256',
                               'test_service_name', 'test_invocation', 'native_manifest'},
            'explicit source/test/native selection required')
    require(re.fullmatch('[0-9a-f]{64}', selection['source_manifest_sha256']) is not None
            and re.fullmatch('[0-9a-f]{32}', selection['test_invocation']) is not None
            and re.fullmatch(r'redoubt-fenix-[a-z0-9-]+\.service', selection['test_service_name']) is not None,
            'invalid reviewed manifest/test identity')
    paths = {}
    for key in ('source_stage', 'test_evidence', 'native_manifest'):
        raw = Path(selection[key])
        require(raw.is_absolute(), 'selected evidence paths must be absolute')
        path = raw.resolve()
        require(path.is_relative_to(WORK / 'evidence') and path != WORK / 'evidence'
                and not path.is_relative_to(BUILD) and not path.is_relative_to(RUNTIME),
                'selected input must be prior evidence inside the guest work tree')
        require(str(path) == selection[key], 'selected evidence path must be canonical')
        paths[key] = path
    require(paths['source_stage'] != paths['test_evidence'], 'stage and test evidence must differ')
    STAGE, TESTS, NATIVE_MANIFEST = paths['source_stage'], paths['test_evidence'], paths['native_manifest']
    CURRENT, TEST_INVOCATION = selection['source_manifest_sha256'], selection['test_invocation']
    SERVICES['tests'] = selection['test_service_name']
    SELECTION = dict(selection)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def record(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size}


def checked(row):
    path = Path(row['path'])
    require(path.is_absolute() and path.is_file() and record(path) == row,
            'input changed/missing: ' + str(path))
    return path


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def query(command):
    return subprocess.check_output(command, text=True, timeout=60).strip()


def manifest(path, absolute=False):
    rows = {}
    for line in Path(path).read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        require(match is not None, 'malformed source/native manifest')
        value, name = match.groups()
        p = Path(name)
        require(name not in rows and '\\' not in name and '..' not in p.parts
                and (absolute or not p.is_absolute()) and str(p) == name,
                'unsafe/duplicate manifest path')
        rows[name] = value
    require(rows, 'empty manifest')
    return rows


def source_check(output=None):
    path = STAGE / 'source-sha256.txt'
    require(digest(path) == CURRENT, 'current167 manifest differs')
    rows = manifest(path)
    require(len(rows) == 167, 'current167 inventory differs')
    receipt = json.loads((STAGE / 'receipt.json').read_text())
    require(receipt['status'] == 'PASS' and receipt['source_count'] == 167
            and receipt['source_manifest_sha256'] == CURRENT
            and receipt['inputs_sha256'] == digest(STAGE / 'inputs.json'),
            'source staging receipt differs')
    for name, value in rows.items():
        require(digest(SOURCE / name) == value, 'current source differs: ' + name)
    if output:
        Path(output).write_text(''.join(name + ': OK\n' for name in rows))
    return rows


def native_check(output=None):
    rows = manifest(NATIVE_MANIFEST, absolute=True)
    require(len(rows) == 3, 'native4 input count differs')
    by_abi = {}
    for name, value in rows.items():
        path = Path(name)
        require(path.is_absolute() and path.resolve().is_relative_to(WORK)
                and path.name == 'target.maven.zip' and path.parent.name in ABIS,
                'unexpected native4 input path')
        require(path.parent.name not in by_abi and digest(path) == value, 'native4 input differs')
        by_abi[path.parent.name] = value
    require(set(by_abi) == set(ABIS), 'native4 ABI set differs')
    for abi, value in by_abi.items():
        require(digest(WORK / 'aar' / abi / 'target.maven.zip') == value,
                'actual APK AAR input differs: ' + abi)
    if output:
        Path(output).write_text(''.join(name + ': OK\n' for name in rows))
    return rows


def service(name, invocation=None, terminal=False):
    keys = ('InvocationID', 'RemainAfterExit', 'ActiveState', 'SubState', 'Result', 'ExecMainStatus')
    args = ['systemctl', '--user', 'show', name]
    for key in keys:
        args += ['-p', key]
    values = dict(line.split('=', 1) for line in query(args).splitlines())
    require(set(values) == set(keys) and values['RemainAfterExit'] == 'yes', 'service retention differs')
    require(re.fullmatch('[0-9a-f]{32}', values['InvocationID']) is not None, 'missing actual invocation')
    if invocation:
        require(values['InvocationID'] == invocation, 'service invocation differs')
    if terminal:
        require(values['Result'] == 'success' and values['ExecMainStatus'] == '0'
                and (values['ActiveState'], values['SubState']) in {('active', 'exited'), ('inactive', 'dead')},
                'required service is not successfully terminal')
    return values


def guest_guard():
    require(os.getuid() == 1001 and query(['id', '-un']) == 'runner', 'requires the guest runner')
    require(REPO.resolve() == WORK / 'repo', 'requires the reviewed guest repository')
    require(query(['systemd-detect-virt', '--vm']) == 'kvm', 'requires KVM guest')
    os.environ['XDG_RUNTIME_DIR'] = '/run/user/1001'
    require(not query(['podman', '--remote=false', 'ps', '-q']), 'another container is active')
    result = subprocess.run(['pgrep', '-f', '[e]mulator.*-avd|[q]emu-system'], capture_output=True)
    require(result.returncode == 1, 'emulator active or process inspection failed')
    require('sha256:' + query(['podman', '--remote=false', 'image', 'inspect', '--format', '{{.Id}}', IMAGE]).removeprefix('sha256:') == IMAGE,
            'actual image identity differs')
    require(not any(key.startswith('LW_SMOKE_') or key in ('ANDROID_SERIAL', 'MOZ_AUTOMATION',
                'GRADLE_OPTS', 'JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'CONTAINER_HOST', 'DOCKER_HOST')
                for key in os.environ), 'unexpected inherited build/runtime override')


def recorded_test_driver_check():
    rows = manifest(TESTS / 'driver-sha256.txt')
    fixed = {'docs/android/board.py', 'docs/android/fenix-test-allowlist.yaml',
             'docs/android/evidence/lw-m7-12/grade-extended-tests.py'}
    allowed = {'docs/android/evidence/lw-m7-12/run-fenix-regression-tests.sh',
               'docs/android/evidence/lw-m7-12/run-fenix-navigation-tests.sh'}
    require(len(rows) == 4 and fixed <= set(rows) and len(set(rows) & allowed) == 1,
            'recorded full-test driver inventory differs')
    for name, value in rows.items():
        require(digest(REPO / name) == value, 'recorded full-test driver changed: ' + name)
    return rows


def tests_check():
    observed = service(SERVICES['tests'], TEST_INVOCATION, terminal=True)
    recorded_test_driver_check()
    require(digest(TESTS / 'source-sha256.txt') == CURRENT, 'tests used another source manifest')
    rows = source_check()
    for name in ('source-before.txt', 'source-after.txt'):
        lines = (TESTS / name).read_text().splitlines()
        require(len(lines) == len(rows) and set(lines) == {n + ': OK' for n in rows},
                'incomplete test source verification: ' + name)
    for name in ('container-exit.txt', 'ac-gradle-exit.txt', 'fenix-gate-exit.txt', 'fresh-results-gate-exit.txt'):
        require((TESTS / name).read_text().strip() == '0', 'test gate failed: ' + name)
    full = (TESTS / 'fenix-gradle-exit.txt').read_text().strip()
    failed = set(re.findall(r'^> Task (\S+) FAILED\s*$', (TESTS / 'target-tests.log').read_text(), re.M))
    require(full == '0' or (full == '1' and failed == {':fenix:testDebugUnitTest'}),
            'full Fenix exit is not explained by its separately passed allowance gate')
    start = dt.datetime.fromisoformat((TESTS / 'started.txt').read_text().strip())
    end = dt.datetime.fromisoformat((TESTS / 'finished.txt').read_text().strip())
    require(start.tzinfo and end.tzinfo and start <= end <= dt.datetime.now(dt.timezone.utc),
            'test completion timestamps invalid')
    summary = json.loads((TESTS / 'junit-summary.json').read_text())
    require(set(summary) == {'fenix', 'extensions', 'gecko', 'state', 'accounts', 'syncedtabs', 'suggest'}
            and all(not row['issues'] and row['summary']['tests'] > 0 for row in summary.values()),
            'fresh test summary is incomplete/failed')
    return observed


def apk_set(folder):
    require({p.name for p in folder.glob('*.apk')} == APKS, 'APK set must contain exactly all four candidates')
    return {name: record(folder / name) for name in sorted(APKS)}


def resource_receipt(text, apk):
    lines = [json.loads(line) for line in text.splitlines() if line.startswith('{')]
    require(len(lines) == 1 and 'PASS exact packaged shortcut input resolved through APK resource table' in text,
            'missing explicit successful resource verdict')
    result = lines[0]
    require(result['apk_sha256'] == apk['sha256'] and result['apk_size'] == apk['bytes']
            and result['aapt2_sha256'] == AAPT_SHA and result['package'] == 'org.redoubtbrowser'
            and result['resource'] == 'raw/initial_shortcuts' and result['mappings'],
            'resource verdict is not bound to the candidate/tool')
    return result


def build_command():
    return [str(REPO / 'scripts/android-apk.sh'), '--skip-gecko', '--srcdir', str(SOURCE),
            '--aar-dir', str(WORK / 'aar'), '--outdir', str(OUTPUT), '--gradle-home', str(WORK / 'out/gradle-home'),
            '--image', IMAGE, '--build-date', DATE, '--variant', 'release', '--jobs', '4',
            '--engine', str(REPO / 'docs/android/evidence/lw-m7-15/podman-bounded.sh')]


def input_paths():
    input_paths = [STAGE / name for name in ('source-sha256.txt', 'receipt.json', 'inputs.json')]
    input_paths.append(NATIVE_MANIFEST)
    input_paths += [TESTS / name for name in ('source-sha256.txt', 'source-before.txt', 'source-after.txt',
        'started.txt', 'started-epoch.txt', 'finished.txt', 'container-exit.txt', 'fenix-gradle-exit.txt',
        'ac-gradle-exit.txt', 'fenix-gate-exit.txt', 'fresh-results-gate-exit.txt', 'fenix-gate.txt',
        'fresh-results-gate.txt', 'target-tests.log', 'junit-summary.json', 'driver-sha256.txt')]
    input_paths += [TESTS / (name + '-junit-xml.tar.gz') for name in ('fenix', 'extensions', 'gecko', 'state', 'accounts', 'syncedtabs', 'suggest')]
    return input_paths


def base_config(kind):
    guest_guard()
    terminal = tests_check()
    native_check()
    require(digest(AAPT) == AAPT_SHA and os.access(AAPT, os.X_OK), 'aapt2 differs/unusable')
    return {'schema': 1, 'kind': kind, 'selection': SELECTION,
            'source_sha256': CURRENT, 'source_count': 167,
            'image': IMAGE, 'build_date': DATE, 'service_name': SERVICES[kind],
            'test_service': terminal, 'aapt2': record(AAPT),
            'repository_files': {name: record(REPO / name) for name in DEPENDENCIES},
            'input_files': [record(path) for path in input_paths()],
            'native_inputs': [record(WORK / 'aar' / abi / 'target.maven.zip') for abi in ABIS],
            'historical_apks': apk_set(WORK / 'out/apk'),
            'host_tools': {name: record(Path(shutil.which(name))) for name in ('python3', 'bash', 'openssl', 'podman')},
            'scope': 'Current167 Kotlin APK/runtime checkpoint with unchanged native4 AARs; later native/API increments are excluded.'}


def load_config(path, expected_hash, kind):
    require(digest(path) == expected_hash, 'config differs from explicitly reviewed digest')
    config = json.loads(Path(path).read_text())
    select_inputs(config['selection'])
    require(config['schema'] == 1 and config['kind'] == kind and config['source_sha256'] == CURRENT
            and config['source_count'] == 167 and config['image'] == IMAGE and config['build_date'] == DATE
            and config['service_name'] == SERVICES[kind], 'wrong checkpoint config')
    require(set(config['repository_files']) == set(DEPENDENCIES), 'dependency inventory differs')
    for name, row in config['repository_files'].items():
        require(checked(row) == (REPO / name).resolve(), 'repository dependency path differs')
    require(len(config['input_files']) == len(input_paths()) and
            {row['path'] for row in config['input_files']} == {str(p.resolve()) for p in input_paths()},
            'required gate/source input inventory differs')
    require(len(config['native_inputs']) == 3 and {row['path'] for row in config['native_inputs']} ==
            {str((WORK / 'aar' / abi / 'target.maven.zip').resolve()) for abi in ABIS},
            'required native input inventory differs')
    for row in config['input_files'] + config['native_inputs']:
        checked(row)
    require(set(config['host_tools']) == {'python3', 'bash', 'openssl', 'podman'}, 'host tool inventory differs')
    for name, row in config['host_tools'].items():
        require(checked(row) == Path(shutil.which(name)).resolve(), 'selected host tool differs: ' + name)
    require(checked(config['aapt2']) == AAPT and config['aapt2']['sha256'] == AAPT_SHA, 'wrong aapt2 input')
    require(apk_set(WORK / 'out/apk') == config['historical_apks'], 'historical APKs changed')
    require(tests_check() == config['test_service'], 'terminal test service changed')
    native_check()
    return config


def own_service(kind):
    invocation = os.environ.get('INVOCATION_ID', '')
    require(re.fullmatch('[0-9a-f]{32}', invocation) is not None, 'run under explicit retained user service')
    observed = service(SERVICES[kind], invocation)
    require(observed['ActiveState'] == 'active' and observed['SubState'] == 'running', 'own service is not running')
    return observed


def run_stage(state, evidence, label, command, env=None):
    timeout = {'build': 14400, 'ubo-lifecycle': 3600, 'baseline': 2700, 'pref-audit': 1200}.get(label, 180)
    row = {'command': command, 'started': now(), 'timeout_seconds': timeout}
    state['stages'][label] = row
    write_json(evidence / 'result.json', state)
    log = evidence / (label + '.log')
    with log.open('w') as stream:
        process = subprocess.Popen(command, cwd=REPO, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            row['timed_out'] = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=30)
            code = 124
    row.update(exit=code, finished=now(), log=record(log))
    (evidence / (label + '-exit.txt')).write_text(str(code) + '\n')
    write_json(evidence / 'result.json', state)
    return code


def initial_state(kind, config_path, config, evidence):
    evidence.mkdir()
    shutil.copy2(config_path, evidence / 'inputs.json')
    shutil.copy2(STAGE / 'source-sha256.txt', evidence / 'source-sha256.txt')
    shutil.copy2(NATIVE_MANIFEST, evidence / 'native-input-sha256.txt')
    (evidence / 'started.txt').write_text(now() + '\n')
    state = {'schema': 1, 'status': 'RUNNING', 'kind': kind, 'scope': config['scope'],
             'inputs': record(evidence / 'inputs.json'), 'source_manifest': record(evidence / 'source-sha256.txt'),
             'service': own_service(kind), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
             'stages': {}, 'started': record(evidence / 'started.txt')}
    write_json(evidence / 'result.json', state)
    return state


def finish(state, evidence):
    # Even a failed behavioral/packaging gate gets complete source checks when
    # the inputs remain readable. A failed check stays explicit, never a pass.
    try:
        source_check(evidence / 'source-after.txt')
        native_check(evidence / 'native-after.txt')
    except Exception as error:
        state.update(status='FAIL', final_input_error=type(error).__name__ + ': ' + str(error))
    state['input_checks'] = {name: record(evidence / name) for name in
                            ('source-before.txt', 'source-after.txt', 'native-before.txt', 'native-after.txt')
                            if (evidence / name).is_file()}
    (evidence / 'finished.txt').write_text(now() + '\n')
    state['finished'] = record(evidence / 'finished.txt')
    write_json(evidence / 'result.json', state)
