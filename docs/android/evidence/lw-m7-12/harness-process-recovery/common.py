"""Same-APK retry contracts; original repository and checkpoint remain authoritative."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
PARENT = HERE.parent / 'current167-process-recovery'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


base = module('harness_retry_original_common', PARENT / 'common.py')
# The original runtime's import must resolve to its unchanged original contracts.
saved = sys.modules.get('common')
try:
    sys.modules['common'] = base
    original_runtime = module('harness_retry_original_runtime', PARENT / 'runtime.py')
finally:
    if saved is None:
        sys.modules.pop('common', None)
    else:
        sys.modules['common'] = saved

RUNTIME = base.WORK / 'evidence/harness-process-runtime'
RUNTIME_WORK = base.WORK / 'harness-process-runtime'
CAPSULE = HERE / 'capsule'
SERVICES = dict(base.SERVICES, runtime='redoubt-harness-process-runtime-20260909.service')
SOURCE_SHA = '4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739'
BUILD_INVOCATION = '598783f0987b4c139fb0053c501f5628'
TEST_INVOCATION = 'c02a8b984fae45dc859eff2b556b82f0'
FAILED_INVOCATION = 'a172ec824e2a4e94a4dd467627f6a0d0'
FAILED_ARCHIVE = REPO / 'docs/android/evidence/lw-m7-21/current-account-process-runtime/runtime-failure.tar.gz'
FAILED_ARCHIVE_SHA = '7be5d87a93ac83c983bbe93dd28679b101d6c381fce564627cdb16cc011382b1'
CAPSULE_PATHS = {'scripts/android-smoke.sh', 'scripts/android-graphics-smoke.py',
                 'scripts/android-pref-audit.sh', 'docs/android/expected-prefs.txt',
                 'docs/android/must-lock.txt'}


def __getattr__(name):
    return getattr(base, name)


def select_inputs(selection):
    base.select_inputs(selection)
    base.require(base.CURRENT == SOURCE_SHA and base.TEST_INVOCATION == TEST_INVOCATION,
                 'retry requires the same reviewed source/full-test invocation')
    SERVICES['tests'] = base.SERVICES['tests']


def capsule_inputs():
    pins = json.loads((HERE / 'capsule-files.json').read_text())
    base.require(set(pins['files']) == CAPSULE_PATHS, 'capsule inventory differs')
    base.require(CAPSULE.is_dir() and not CAPSULE.is_symlink(), 'capsule directory absent/linked')
    actual = set()
    for path in CAPSULE.rglob('*'):
        base.require(not path.is_symlink(), 'linked capsule path')
        if path.is_file():
            name = path.relative_to(CAPSULE).as_posix(); actual.add(name)
            row = pins['files'].get(name)
            base.require(row is not None and base.digest(path) == row['sha256']
                         and path.stat().st_size == row['bytes'], 'capsule input changed: ' + name)
            if name.endswith('.sh'):
                base.require(os.access(path, os.X_OK), 'capsule shell script is not executable')
    base.require(actual == CAPSULE_PATHS, 'capsule file missing/extra')
    return [base.record(CAPSULE / name) for name in sorted(actual)]


def archived_history():
    base.require(base.digest(FAILED_ARCHIVE) == FAILED_ARCHIVE_SHA, 'failed-runtime archive changed')
    files = {}
    with tarfile.open(FAILED_ARCHIVE, 'r:gz') as archive:
        for member in archive:
            path = Path(member.name)
            base.require(member.isfile() and member.name not in files and not path.is_absolute()
                         and '..' not in path.parts, 'invalid failure archive member')
            files[member.name] = archive.extractfile(member).read()
    capture = json.loads(files['capture-result.json'])
    base.require(len(files) == 55 and set(capture['files']) == set(files) - {'capture-result.json'},
                 'failed-runtime archive inventory differs')
    import hashlib
    for name, row in capture['files'].items():
        base.require(hashlib.sha256(files[name]).hexdigest() == row['sha256']
                     and len(files[name]) == row['bytes'], 'failed-runtime archive body differs')
    state = json.loads(files['runtime-checkpoint/result.json'])
    config = json.loads(files['runtime-checkpoint/inputs.json'])
    terminal = dict(line.split('=', 1) for line in files['service.txt'].decode().splitlines())
    base.require(state['status'] == 'FAIL' and state['kind'] == 'runtime'
                 and state['service']['InvocationID'] == FAILED_INVOCATION
                 and state['source_manifest']['sha256'] == SOURCE_SHA
                 and state['emulator_cleanup_exit'] == 0
                 and terminal['InvocationID'] == FAILED_INVOCATION and terminal['ExecMainStatus'] == '1'
                 and (terminal['ActiveState'], terminal['SubState']) == ('failed', 'failed')
                 and config['selection']['test_invocation'] == TEST_INVOCATION
                 and config['apk_service']['InvocationID'] == BUILD_INVOCATION,
                 'archive does not describe the exact failed same-APK attempt')
    return files, state, config


def failed_history():
    files, state, config = archived_history()
    kept = []
    roots = {'runtime-checkpoint': base.RUNTIME, 'runtime-work': base.RUNTIME_WORK,
             'configuration': REPO}
    import hashlib
    for name, body in sorted(files.items()):
        prefix, _, relative = name.partition('/')
        if prefix not in roots:
            continue
        path = roots[prefix] / relative
        record = base.record(path)
        base.require(record['sha256'] == hashlib.sha256(body).hexdigest()
                     and record['bytes'] == len(body), 'failed runtime evidence/original code changed: ' + name)
        kept.append(record)
    terminal = base.service(base.SERVICES['runtime'], FAILED_INVOCATION)
    base.require(terminal['ExecMainStatus'] == '1'
                 and (terminal['ActiveState'], terminal['SubState']) in
                 {('failed', 'failed'), ('inactive', 'dead')},
                 'failed runtime invocation is not terminal or was replaced')
    return {'archive': base.record(FAILED_ARCHIVE), 'service': terminal,
            'preserved_files': kept, 'checkpoint_tree': base.preserved_tree(base.RUNTIME)}


def runtime_inputs():
    files = [HERE / name for name in ('common.py', 'runtime.py', 'capsule-files.json')]
    files += [FAILED_ARCHIVE]
    return {str(path.relative_to(REPO)): base.record(path) for path in files}


def checked_build():
    state = json.loads((base.BUILD / 'result.json').read_text())
    path = base.checked(state['inputs'])
    config = base.load_config(path, state['inputs']['sha256'], 'apk')
    select_inputs(config['selection'])
    checked, terminal = original_runtime.checked_build()
    base.require(terminal['InvocationID'] == BUILD_INVOCATION,
                 'retry selected a different successful APK invocation')
    return checked, terminal


def base_config(kind):
    base.require(kind == 'runtime', 'this version supports runtime only')
    base.guest_guard()
    state, terminal = checked_build()
    path = base.checked(state['inputs']); parent = json.loads(path.read_text())
    config = dict(parent, kind='runtime', service_name=SERVICES['runtime'])
    config.update(parent_build_inputs=base.record(path), build_receipt=base.record(base.BUILD / 'result.json'),
                  apk_service=terminal, apks=state['apks'], metadata=state['metadata'],
                  capsule_inputs=capsule_inputs(), runtime_repository_files=runtime_inputs(),
                  failed_runtime=failed_history(),
                  scope='Same successful current167 APK/source/full tests; separately pinned corrected harness capsule. No APK or native rebuild.')
    return config


def load_config(path, expected_hash, kind):
    base.require(kind == 'runtime' and base.digest(path) == expected_hash, 'wrong runtime config/hash')
    config = json.loads(Path(path).read_text())
    parent_path = base.checked(config['parent_build_inputs'])
    parent = base.load_config(parent_path, config['parent_build_inputs']['sha256'], 'apk')
    select_inputs(parent['selection'])
    for key, value in parent.items():
        if key not in {'kind', 'service_name', 'scope'}:
            base.require(config[key] == value, 'original successful APK contract changed: ' + key)
    base.require(config['schema'] == 1 and config['kind'] == 'runtime'
                 and config['service_name'] == SERVICES['runtime'] and config['source_sha256'] == SOURCE_SHA,
                 'wrong versioned runtime selection')
    state, terminal = checked_build()
    base.require(parent_path == base.checked(state['inputs'])
                 and base.record(base.BUILD / 'result.json') == config['build_receipt']
                 and state['apks'] == config['apks'] and state['metadata'] == config['metadata']
                 and terminal == config['apk_service'], 'successful APK/runtime linkage differs')
    base.require(capsule_inputs() == config['capsule_inputs'], 'capsule selection changed')
    base.require(runtime_inputs() == config['runtime_repository_files'], 'retry driver inputs changed')
    base.require(failed_history() == config['failed_runtime'], 'failed runtime history changed')
    return config


def own_service(kind):
    base.require(kind == 'runtime', 'runtime-only service')
    invocation = os.environ.get('INVOCATION_ID', '')
    base.require(re.fullmatch('[0-9a-f]{32}', invocation) is not None, 'actual retained runtime service required')
    state = base.service(SERVICES[kind], invocation)
    base.require(state['ActiveState'] == 'active' and state['SubState'] == 'running', 'runtime service not running')
    return state


def initial_state(kind, config_path, config, evidence):
    evidence.mkdir()
    shutil.copy2(config_path, evidence / 'inputs.json')
    shutil.copy2(base.STAGE / 'source-sha256.txt', evidence / 'source-sha256.txt')
    shutil.copy2(base.NATIVE_MANIFEST, evidence / 'native-input-sha256.txt')
    (evidence / 'started.txt').write_text(base.now() + '\n')
    state = {'schema': 1, 'status': 'RUNNING', 'kind': kind, 'scope': config['scope'],
             'inputs': base.record(evidence / 'inputs.json'), 'source_manifest': base.record(evidence / 'source-sha256.txt'),
             'service': own_service(kind), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
             'stages': {}, 'started': base.record(evidence / 'started.txt'),
             'capsule_inputs': config['capsule_inputs'], 'failed_runtime_archive': config['failed_runtime']['archive']}
    base.write_json(evidence / 'result.json', state)
    return state


def finish(state, evidence):
    try:
        path = base.checked(state['inputs'])
        load_config(path, state['inputs']['sha256'], 'runtime')
    except Exception as error:
        state.update(status='FAIL', recovery_input_error=type(error).__name__ + ': ' + str(error))
    base.finish(state, evidence)
