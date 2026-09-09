"""Thin retry adapter; frozen runtime functions run with a private explicit binding."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / 'harness-process-recovery'
REPO = HERE.parents[4]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inherited_inputs():
    pins = json.loads((HERE / 'inherited-files.json').read_text())['files']
    require(set(pins) == {'common.py', 'runtime.py', 'capsule-files.json'}, 'inherited file inventory differs')
    records = {}
    for name, row in pins.items():
        path = FROZEN / name; body = path.read_bytes()
        require(hashlib.sha256(body).hexdigest() == row['sha256'] and len(body) == row['bytes'],
                'frozen inherited input changed: ' + name)
        records[str(path.relative_to(REPO))] = {'path': str(path), **row}
    return records


def private_module(name, path, common=None):
    """Bind only during module import and restore the caller's exact module entry."""
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    missing = object()
    previous = sys.modules.get('common', missing)
    try:
        if common is not None:
            sys.modules['common'] = common
        spec.loader.exec_module(result)
    finally:
        if previous is missing:
            sys.modules.pop('common', None)
        else:
            sys.modules['common'] = previous
    return result


inherited_inputs()
engine = private_module('modal_private_frozen_common', FROZEN / 'common.py')
PREVIOUS_RUNTIME = engine.RUNTIME
PREVIOUS_WORK = engine.RUNTIME_WORK
PREVIOUS_SERVICE = engine.SERVICES['runtime']
PREVIOUS_INVOCATION = '0189d8626a9a4a38b540d037781d3c45'
PREVIOUS_ARCHIVE = REPO / 'docs/android/evidence/lw-m7-21/current-harness-process-runtime/runtime-failure.tar.gz'
PREVIOUS_ARCHIVE_SHA = '8ffbb2f513d1cad4f995164c5600cc42dd39852f3afb3d0149775f8ac15e390c'

# Only this fresh, unregistered module instance is configured. Its original
# base/current167 module, REPO, functions and frozen source bytes stay unchanged.
engine.HERE = HERE
engine.CAPSULE = HERE / 'capsule'
engine.RUNTIME = engine.base.WORK / 'evidence/modal-process-runtime'
engine.RUNTIME_WORK = engine.base.WORK / 'modal-process-runtime'
engine.SERVICES = dict(engine.SERVICES, runtime='redoubt-modal-process-runtime-20260909.service')


def __getattr__(name):
    return getattr(engine, name)


def archived_previous():
    require(engine.base.digest(PREVIOUS_ARCHIVE) == PREVIOUS_ARCHIVE_SHA, '0189 failure archive changed')
    files = {}
    with tarfile.open(PREVIOUS_ARCHIVE, 'r:gz') as archive:
        for member in archive:
            path = Path(member.name)
            require(member.isfile() and member.name not in files and not path.is_absolute()
                    and '..' not in path.parts, 'invalid 0189 failure member')
            files[member.name] = archive.extractfile(member).read()
    capture = json.loads(files['capture-result.json'])
    require(len(files) == 95 and set(capture['files']) == set(files) - {'capture-result.json'},
            '0189 archive inventory differs')
    for name, row in capture['files'].items():
        require(hashlib.sha256(files[name]).hexdigest() == row['sha256'] and len(files[name]) == row['bytes'],
                '0189 archive member differs')
    state = json.loads(files['runtime-checkpoint/result.json'])
    config = json.loads(files['runtime-checkpoint/inputs.json'])
    terminal = dict(line.split('=', 1) for line in files['service.txt'].decode().splitlines())
    require(state['status'] == 'FAIL' and state['kind'] == 'runtime'
            and state['service']['InvocationID'] == PREVIOUS_INVOCATION
            and state['source_manifest']['sha256'] == engine.SOURCE_SHA
            and state['emulator_cleanup_exit'] == 0
            and {n: row['exit'] for n, row in state['stages'].items()} ==
                {'ubo-lifecycle': 0, 'baseline': 1, 'pref-audit': 0}
            and terminal['InvocationID'] == PREVIOUS_INVOCATION and terminal['ExecMainStatus'] == '1'
            and (terminal['ActiveState'], terminal['SubState']) == ('failed', 'failed')
            and config['selection']['test_invocation'] == engine.TEST_INVOCATION
            and config['apk_service']['InvocationID'] == engine.BUILD_INVOCATION,
            'archive is not the exact failed0189 same-APK attempt')
    return files, state, config


def previous_history():
    files, _state, _config = archived_previous()
    roots = {'runtime-checkpoint': PREVIOUS_RUNTIME, 'runtime-work': PREVIOUS_WORK, 'configuration': REPO}
    records = []
    for name, body in sorted(files.items()):
        prefix, _, relative = name.partition('/')
        if prefix not in roots:
            continue
        row = engine.base.record(roots[prefix] / relative)
        require(row['sha256'] == hashlib.sha256(body).hexdigest() and row['bytes'] == len(body),
                '0189 evidence/original capsule changed: ' + name)
        records.append(row)
    terminal = engine.base.service(PREVIOUS_SERVICE, PREVIOUS_INVOCATION)
    require(terminal['ExecMainStatus'] == '1' and (terminal['ActiveState'], terminal['SubState']) in
            {('failed', 'failed'), ('inactive', 'dead')}, '0189 service is not the same terminal failure')
    return {'archive': engine.base.record(PREVIOUS_ARCHIVE), 'service': terminal,
            'preserved_files': records, 'checkpoint_tree': engine.base.preserved_tree(PREVIOUS_RUNTIME)}


def adapter_inputs():
    return {**inherited_inputs(), str((HERE / 'inherited-files.json').relative_to(REPO)):
            engine.base.record(HERE / 'inherited-files.json'),
            str(PREVIOUS_ARCHIVE.relative_to(REPO)): engine.base.record(PREVIOUS_ARCHIVE)}


def runtime_inputs():
    """Expose the complete input set to the future versioned staging helper."""
    return {**engine.runtime_inputs(), **adapter_inputs()}


def base_config(kind):
    config = engine.base_config(kind)
    config.update(previous_harness_runtime=previous_history(), inherited_runtime_files=adapter_inputs(),
                  scope='Same successful APK/source/full tests; new modal-aware harness capsule, both prior runtime failures retained. No APK rebuild.')
    return config


def load_config(path, expected_hash, kind):
    config = engine.load_config(path, expected_hash, kind)
    require(config['inherited_runtime_files'] == adapter_inputs(), 'inherited runtime inputs changed')
    require(config['previous_harness_runtime'] == previous_history(), '0189 runtime history changed')
    return config


def initial_state(kind, config_path, config, evidence):
    state = engine.initial_state(kind, config_path, config, evidence)
    state['previous_harness_runtime_archive'] = config['previous_harness_runtime']['archive']
    engine.base.write_json(evidence / 'result.json', state)
    return state


def finish(state, evidence):
    try:
        path = engine.base.checked(state['inputs'])
        load_config(path, state['inputs']['sha256'], 'runtime')
    except Exception as error:
        state.update(status='FAIL', recovery_input_error=type(error).__name__ + ': ' + str(error))
    engine.finish(state, evidence)
