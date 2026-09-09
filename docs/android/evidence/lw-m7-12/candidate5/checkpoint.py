#!/usr/bin/env python3
"""Package a reviewed native candidate and run full Fenix/targeted AC units in CI.

Default is a read-only plan. --run requires the isolated guest and a terminal,
source-bound native receipt. This never builds Gecko, starts a device, or stages
source patches. Future native artifact identities must be supplied, not inferred.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
spec = importlib.util.spec_from_file_location('candidate5_grade', HERE / 'grade.py')
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)
ABIS = ('armeabi-v7a', 'arm64-v8a', 'x86_64')
APKS = {f'fenix-{abi}-release.apk' for abi in (*ABIS, 'universal')}
FIXED_REPO_INPUTS = (
    'scripts/android-apk.sh', 'assets/mozconfig.android',
    'docs/android/board.py', 'docs/android/fenix-test-allowlist.yaml',
    'docs/android/evidence/lw-m7-15/podman-bounded.sh',
    'docs/android/evidence/lw-m7-12/grade-extended-tests.py',
    'docs/android/evidence/lw-m7-12/candidate5/checkpoint.py',
    'docs/android/evidence/lw-m7-12/candidate5/grade.py',
    'docs/android/evidence/lw-m7-12/candidate5/unit-inventory.json',
    'docs/android/evidence/lw-m7-30/check-source.py',
    'docs/android/evidence/lw-m7-30/source-files.json',
    'docs/android/evidence/lw-m7-30/source-baseline.tar.gz',
    'patches/android/no-default-shortcuts.patch',
)


class Pending(Exception):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def canonical_image_id(value):
    require(isinstance(value, str), 'container image ID is malformed')
    value = value.removeprefix('sha256:')
    require(sha(value), 'container image ID is malformed')
    return 'sha256:' + value


def absolute(value):
    require(isinstance(value, str) and Path(value).is_absolute(), 'expected an absolute path')
    return Path(value).resolve()


def record(path):
    return {'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size}


def checked_file(row):
    require(isinstance(row, dict) and sha(row.get('sha256')), 'missing explicit file hash')
    path = absolute(row['path'])
    if not path.is_file():
        raise Pending('required input is absent: ' + str(path))
    require(digest(path) == row['sha256'], 'input hash differs: ' + str(path))
    return path


def source_manifest(path, count):
    require(type(count) is int and count > 0, 'reviewed source count is required')
    rows = {}
    for line in path.read_text().splitlines():
        value, name = line.split('  ', 1)
        require(sha(value) and name not in rows and not Path(name).is_absolute()
                and not any(p in ('', '.', '..') for p in name.split('/')) and '\\' not in name,
                'invalid or duplicate source binding')
        rows[name] = value
    require(len(rows) == count, 'source count differs from reviewed inventory')
    return rows


def verify_sources(source, rows):
    for name, value in rows.items():
        require(digest(source / name) == value, 'source differs: ' + name)


def check_native_receipt(receipt, reviewed, rows, source):
    require(receipt['schema'] == 1 and receipt['status'] == 'PASS', 'native build is not successful')
    require(re.fullmatch('[0-9a-f]{32}', receipt['invocation_id']) is not None,
            'actual native invocation ID is required')
    require(re.fullmatch(r'[A-Za-z0-9_.@-]+\.service', receipt['service_name']) is not None,
            'native service name is invalid')
    require(absolute(receipt['source_dir']) == source, 'native source directory differs')
    native_manifest = checked_file(receipt['source_manifest'])
    require(receipt['source_manifest']['sha256'] == reviewed['sha256']
            and source_manifest(native_manifest, reviewed['count']) == rows,
            'native build used a different reviewed source inventory')
    exit_file = checked_file(receipt['build_exit'])
    require(exit_file.read_text().strip() == '0', 'native compiler exit is not zero')
    started = dt.datetime.fromisoformat(checked_file(receipt['started']).read_text().strip())
    finished = dt.datetime.fromisoformat(checked_file(receipt['finished']).read_text().strip())
    require(started.tzinfo is not None and finished.tzinfo is not None and started <= finished
            and finished <= dt.datetime.now(dt.timezone.utc), 'native completion time is invalid')
    checked_file(receipt['build_log'])
    for key in ('source_before', 'source_after'):
        lines = checked_file(receipt[key]).read_text().splitlines()
        require(len(lines) == len(rows) and set(lines) == {name + ': OK' for name in rows},
                'native source verification was incomplete: ' + key)
    require(set(receipt['aars']) == set(ABIS), 'native receipt must bind all three ABI archives')
    aar_paths = {abi: checked_file(row) for abi, row in receipt['aars'].items()}
    aar_roots = {path.parent.parent for path in aar_paths.values()}
    require(len(aar_roots) == 1 and all(path.name == 'target.maven.zip' and path.parent.name == abi
                                     for abi, path in aar_paths.items()), 'unexpected native archive layout')
    return aar_roots.pop()


def load_inputs(path):
    input_bytes = path.read_bytes()
    inputs = json.loads(input_bytes)
    require(inputs.get('schema') == 1, 'unsupported run-input schema')
    require(isinstance(inputs.get('reviewed_scope_note'), str) and inputs['reviewed_scope_note'].strip(),
            'reviewed source scope note must explicitly name included/excluded increments')
    require(re.fullmatch('candidate5-[a-z0-9-]+', inputs.get('run_id') or '') is not None, 'new run ID required')
    require(sha((inputs.get('container_image_id') or '').removeprefix('sha256:'))
            and inputs['container_image_id'].startswith('sha256:'), 'immutable container image ID required')
    date = inputs.get('build_date') or ''
    require(re.fullmatch('[0-9]{14}', date) is not None, 'explicit build date required')
    dt.datetime.strptime(date, '%Y%m%d%H%M%S')
    work, source = absolute(inputs['work']), absolute(inputs['source_dir'])
    require(source.is_relative_to(work) and source != work, 'source must be within the selected work tree')
    run_root = work / inputs['run_id']
    require(not run_root.exists(), 'run workspace already exists; preserve it and select a new run ID')
    require(set(inputs['repository_files']) == set(FIXED_REPO_INPUTS), 'repository dependency inventory differs')
    for name, value in inputs['repository_files'].items():
        require(sha(value) and digest(REPO / name) == value, 'repository input changed: ' + name)
    reviewed = inputs['reviewed_source_manifest']
    manifest = checked_file(reviewed)
    rows = source_manifest(manifest, reviewed['count'])
    inventory = json.loads((HERE / 'unit-inventory.json').read_text())
    for row in inventory['tests']:
        require(rows.get(row['source_path']) == row['source_sha256'],
                'selected unit source is absent/different: ' + row['source_path'])
    shortcut = json.loads((REPO / 'docs/android/evidence/lw-m7-30/source-files.json').read_text())
    require(rows.get(shortcut['path']) == shortcut['after_sha256'],
            'native candidate must already include the reviewed final shortcut resource')
    verify_sources(source, rows)
    native_path = checked_file(inputs['native_receipt'])
    native = json.loads(native_path.read_text())
    require(native['build_date'] == inputs['build_date']
            and native['container_image_id'] == inputs['container_image_id'],
            'native build date/toolchain differs from APK configuration')
    aar = check_native_receipt(native, reviewed, rows, source)
    tool = checked_file(inputs['aapt2'])
    require(os.access(tool, os.X_OK), 'aapt2 is not executable')
    seed = absolute(inputs['gradle_home_seed'])
    require(seed.is_dir() and not seed.is_relative_to(run_root), 'Gradle cache seed directory is absent/invalid')
    return {'inputs': inputs, 'input_sha256': hashlib.sha256(input_bytes).hexdigest(), 'work': work, 'source': source, 'manifest': manifest,
            'rows': rows, 'native': native, 'aar': aar, 'tool': tool, 'seed': seed,
            'root': run_root, 'out': run_root / 'out', 'evidence': run_root / 'evidence', 'inventory': inventory}


def gradle_tasks(inventory):
    suite_map = grade.suites(inventory)
    tasks = {
        'gecko': ':components:browser-engine-gecko:testDebugUnitTest',
        'state': ':components:browser-state:testDebugUnitTest',
        'accounts': ':components:service-firefox-accounts:testDebugUnitTest',
        'syncedtabs': ':components:feature-syncedtabs:testDebugUnitTest',
        'suggest': ':components:feature-fxsuggest:testDebugUnitTest',
        'addons': ':components:feature-addons:testDebugUnitTest',
    }
    common = ['--continue', '--no-daemon', '--no-build-cache', '--max-workers=4']
    full = [':fenix:testDebugUnitTest', ':components:support-webextensions:testDebugUnitTest', *common]
    targeted = []
    for key, task in tasks.items():
        targeted.append(task)
        for klass in sorted(suite_map[key]['required']):
            targeted.extend(['--tests', klass])
    return [full, targeted + common]


def apk_command(context):
    c = context; i = c['inputs']
    return [str(REPO / 'scripts/android-apk.sh'), '--srcdir', str(c['source']),
            '--aar-dir', str(c['aar']), '--outdir', str(c['out']), '--engine',
            str(REPO / 'docs/android/evidence/lw-m7-15/podman-bounded.sh'),
            '--variant', 'release', '--jobs', '4', '--build-date', i['build_date'],
            '--gradle-home', str(c['seed']), '--image', i['container_image_id'], '--skip-gecko']


def unit_commands(context):
    c = context; i = c['inputs']; out = str(c['out'])
    glean = dt.datetime.strptime(i['build_date'], '%Y%m%d%H%M%S').strftime('%Y-%m-%dT%H:%M:%S')
    base = ['podman', '--remote=false', 'run', '--rm', '--memory=14g', '--memory-swap=22g', '--cpus=6',
            '-v', str(c['source']) + ':/work/src:z', '-v', out + ':/work/out:z',
            '-v', out + '/mozbuild-srcdirs:/root/.mozbuild/srcdirs:z', '-w', '/work/src',
            '-e', 'MOZCONFIG=/work/out/mozconfig.x86_64', '-e', 'MOZ_BUILD_DATE=' + i['build_date'],
            '-e', 'GRADLE_USER_HOME=/work/out/gradle-home',
            '-e', 'MOZ_ANDROID_FAT_AAR_ARCHITECTURES=' + ','.join(ABIS)]
    for abi in ABIS:
        base += ['-e', 'MOZ_ANDROID_FAT_AAR_' + abi.upper().replace('-', '_') + '=/work/out/input/' + abi + '/target.maven.zip']
    return [base + ['--name', i['run_id'] + '-units-' + str(n), i['container_image_id'], './mach', 'gradle',
                    *tasks, '-PgleanBuildDate=' + glean]
            for n, tasks in enumerate(gradle_tasks(c['inventory']), 1)]


def assert_apk_set(folder):
    require({p.name for p in folder.glob('*.apk')} == APKS, 'APK output set is not exactly three ABIs plus universal')
    return {name: record(folder / name) for name in sorted(APKS)}


def full_exit_is_accounted(exit_code, log):
    if exit_code == 0:
        return True
    # Exit1 is allowed only for the exact Fenix test task whose XML is graded.
    # A compiler/dependency task failure cannot borrow the Fenix allowance.
    failed = set(re.findall(r'^> Task (\S+) FAILED\s*$', log, re.M))
    return exit_code == 1 and failed == {':fenix:testDebugUnitTest'}


def query(command):
    return subprocess.check_output(command, text=True, timeout=30).strip()


def guard_guest(context):
    require(pwd.getpwuid(os.getuid()).pw_name == 'runner' and os.getuid() == 1001, 'run requires guest runner')
    os.environ['XDG_RUNTIME_DIR'] = '/run/user/1001'
    require(query(['systemd-detect-virt', '--vm']) == 'kvm', 'run requires isolated KVM guest')
    require(not query(['podman', '--remote=false', 'ps', '-q']), 'another container is active')
    # pgrep exit1 means absent; no adb calls or emulator launch are made here.
    processes = subprocess.run(['pgrep', '-f', '[e]mulator.*-avd|[q]emu-system'], capture_output=True, text=True)
    require(processes.returncode == 1, 'an emulator is active or process inspection failed')
    image = context['inputs']['container_image_id']
    observed_image = query(['podman', '--remote=false', 'image', 'inspect', '--format', '{{.Id}}', image])
    require(canonical_image_id(observed_image) == canonical_image_id(image),
            'container image ID differs')
    n = context['native']
    status = dict(line.split('=', 1) for line in query([
        'systemctl', '--user', 'show', n['service_name'], '-p', 'InvocationID', '-p', 'ActiveState',
        '-p', 'SubState', '-p', 'Result', '-p', 'ExecMainStatus']).splitlines())
    require(status['InvocationID'] == n['invocation_id'] and status['ExecMainStatus'] == '0'
            and status['Result'] == 'success' and (status['ActiveState'], status['SubState'])
            in {('inactive', 'dead'), ('active', 'exited')}, 'native invocation is not successfully terminal')
    return status


def execute(context, input_path):
    c = context
    service = guard_guest(c)
    require(digest(input_path) == c['input_sha256'], 'run inputs changed after preflight')
    c['root'].mkdir()
    evidence = c['evidence']; evidence.mkdir()
    shutil.copy2(input_path, evidence / 'inputs.json')
    shutil.copy2(checked_file(c['inputs']['native_receipt']), evidence / 'native-receipt.json')
    shutil.copy2(c['manifest'], evidence / 'source-sha256.txt')
    state = {'status': 'RUNNING', 'scope': 'APK resource verification and full/targeted Gradle only',
             'inputs': record(evidence / 'inputs.json'), 'native_service': service,
             'reviewed_scope_note': c['inputs']['reviewed_scope_note'],
             'additional_unit_classes': [row['class'] for row in c['inventory']['tests']],
             'unit_coverage_limit': 'Only the retained baseline and pinned unit inventory have required-class/method guards. Additional product increments need separate reviewed coverage.',
             'native_tests_and_APK_runtime': c['inventory']['separate_required_gates'], 'stages': {}}

    def save():
        (evidence / 'result.json').write_text(json.dumps(state, indent=2) + '\n')

    def run(label, command):
        log = evidence / (label + '.log')
        row = {'command': command, 'started': dt.datetime.now(dt.timezone.utc).isoformat()}
        state['stages'][label] = row; save()
        with log.open('w') as stream:
            result = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT)
        row.update(exit=result.returncode, log=record(log), finished=dt.datetime.now(dt.timezone.utc).isoformat()); save()
        return result.returncode

    save()
    try:
        require(run('apk-build', apk_command(c)) == 0, 'APK build failed')
        verify_sources(c['source'], c['rows'])
        check_native_receipt(c['native'], c['inputs']['reviewed_source_manifest'], c['rows'], c['source'])
        apks = assert_apk_set(c['out'] / 'apk'); state['apks'] = apks; save()
        for name in sorted(APKS):
            require(run(name + '-resource', [sys.executable, str(REPO / 'docs/android/evidence/lw-m7-30/check-source.py'),
                                           '--apk', apks[name]['path'], '--aapt2', str(c['tool'])]) == 0,
                    'APK resource verification failed: ' + name)
        require(assert_apk_set(c['out'] / 'apk') == apks, 'APK bytes changed during resource checks')
        require(digest(c['tool']) == c['inputs']['aapt2']['sha256'], 'aapt2 changed')
        results = c['source'] / 'obj-x86_64/gradle/build/mobile/android'
        prior = evidence / 'prior-unit-results'; prior.mkdir()
        for key, suite in grade.suites(c['inventory']).items():
            directory = results / suite['relative'] / 'test-results/testDebugUnitTest'
            if directory.exists():
                shutil.move(str(directory), prior / key)
        (evidence / 'started-epoch.txt').write_text(str(time.time()) + '\n')
        commands = unit_commands(c)
        full_rc = run('fenix-and-extensions', commands[0])
        ac_rc = run('targeted-ac', commands[1])
        (evidence / 'tests-ended-epoch.txt').write_text(str(time.time()) + '\n')
        gate_rc = run('fenix-allowance-gate', [sys.executable, str(REPO / 'docs/android/board.py'),
                      '--check-fenix-tests', '--results', str(results / 'fenix/app/test-results/testDebugUnitTest')])
        fresh_rc = run('fresh-unit-gate', [sys.executable, str(HERE / 'grade.py'), str(results), str(evidence)])
        verify_sources(c['source'], c['rows'])
        check_native_receipt(c['native'], c['inputs']['reviewed_source_manifest'], c['rows'], c['source'])
        require(assert_apk_set(c['out'] / 'apk') == apks, 'APK bytes changed during unit tests')
        for name, value in c['inputs']['repository_files'].items():
            require(digest(REPO / name) == value, 'repository input changed: ' + name)
        # Full Fenix may exit1 for only the exact pre-existing allowed failures.
        require(full_exit_is_accounted(full_rc, (evidence / 'fenix-and-extensions.log').read_text())
                and ac_rc == 0 and gate_rc == 0 and fresh_rc == 0,
                'required full/targeted unit gate failed')
        state['status'] = 'PASS APK resources and required Gradle gates; native/behavior acceptance PENDING'
        return 0
    except Exception as error:
        state['status'] = 'FAIL'
        state['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        state['finished'] = dt.datetime.now(dt.timezone.utc).isoformat(); save()


def template():
    return {'schema': 1, 'run_id': None, 'work': '/home/runner/work/feature-parity-20260908',
            'source_dir': '/home/runner/work/feature-parity-20260908/src',
            'reviewed_scope_note': None,
            'reviewed_source_manifest': {'path': None, 'sha256': None, 'count': None},
            'native_receipt': {'path': None, 'sha256': None},
            'container_image_id': None, 'build_date': '20260906190000',
            'gradle_home_seed': '/home/runner/work/feature-parity-20260908/out/gradle-home',
            'aapt2': {'path': None, 'sha256': None},
            'repository_files': {name: digest(REPO / name) for name in FIXED_REPO_INPUTS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', action='store_true')
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    try:
        if args.template:
            require(not args.run and args.inputs is None, '--template is read-only and takes no run inputs')
            print(json.dumps(template(), indent=2)); return 0
        require(args.inputs is not None, '--inputs is required')
        context = load_inputs(args.inputs)
        if not args.run:
            print(json.dumps({'status': 'PLAN ONLY; target not executed', 'apk_command': apk_command(context),
                              'unit_commands': unit_commands(context), 'resource_checks': sorted(APKS),
                              'source_count': len(context['rows']), 'output': str(context['root'])}, indent=2))
            return 0
        return execute(context, args.inputs)
    except Pending as error:
        print('PENDING: ' + str(error)); return 3
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print('FAIL: ' + str(error)); return 1


if __name__ == '__main__':
    raise SystemExit(main())
