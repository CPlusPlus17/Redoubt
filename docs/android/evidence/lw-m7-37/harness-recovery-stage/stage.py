#!/usr/bin/env python3
"""Prepare/review or explicitly stage the retained current245 source in the guest."""
import argparse
import gzip
import io
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
COMPOSITION = HERE.parent / 'process-recovery-composition'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


# The existing source verifier retains its original HERE/REPO and every frozen
# composition input. Only the runtime prerequisite implementation changes.
v = module('harness245_composition', COMPOSITION / 'verify.py')
CHECKPOINT = v.REPO / 'docs/android/evidence/lw-m7-12/harness-process-recovery'
c = module('harness245_checkpoint_common', CHECKPOINT / 'common.py')
saved_common = sys.modules.get('common')
try:
    sys.modules['common'] = c
    prior_runtime = module('harness245_checkpoint_runtime', CHECKPOINT / 'runtime.py')
finally:
    if saved_common is None:
        sys.modules.pop('common', None)
    else:
        sys.modules['common'] = saved_common

OUT = c.WORK / 'evidence/account-process245-source-stage'
SERVICE = 'redoubt-account-process245-source-stage-20260909.service'


def records(value, result=None):
    """Collect only file records from the known checkpoint result/config objects."""
    result = {} if result is None else result
    if isinstance(value, dict):
        if set(value) == {'path', 'sha256', 'bytes'}:
            c.checked(value)
            c.require(value['path'] not in result or result[value['path']] == value,
                      'conflicting prerequisite file record')
            result[value['path']] = value
        else:
            for child in value.values():
                records(child, result)
    elif isinstance(value, list):
        for child in value:
            records(child, result)
    return result


def prerequisites():
    result_path = c.RUNTIME / 'result.json'
    state = json.loads(result_path.read_text())
    c.require(state['schema'] == 1 and state['kind'] == 'runtime' and state['status'] == 'PASS',
              'successful new current167 runtime checkpoint is required before native staging')
    config_path = c.checked(state['inputs'])
    config = c.load_config(config_path, state['inputs']['sha256'], 'runtime')
    c.require(c.CURRENT == v.BASE and state['source_manifest']['sha256'] == v.BASE,
              'runtime did not test the exact current167 source')
    c.checked(state['source_manifest'])
    c.checked(state['started']); c.checked(state['finished'])
    terminal = c.service(c.SERVICES['runtime'], state['service']['InvocationID'], terminal=True)
    c.require(state.get('emulator_cleanup_exit') == 0 and not state.get('cleanup_error'),
              'runtime emulator cleanup must have succeeded')
    required = {'source-before.txt', 'source-after.txt', 'native-before.txt', 'native-after.txt'}
    c.require(set(state['input_checks']) == required, 'runtime input verification incomplete')
    source_rows = c.manifest(c.STAGE / 'source-sha256.txt')
    for name, row in state['input_checks'].items():
        path = c.checked(row)
        c.require(path == c.RUNTIME / name, 'runtime input receipt path differs')
        if name.startswith('source-'):
            lines = path.read_text().splitlines()
            c.require(len(lines) == 167 and set(lines) == {n + ': OK' for n in source_rows},
                      'runtime source receipt incomplete')
    build, build_terminal = prior_runtime.checked_build()
    c.require(c.record(c.BUILD / 'result.json') == config['build_receipt'] and
              build['apks'] == config['apks'] and build_terminal == config['apk_service'],
              'successful runtime/build linkage differs')
    apk = build['apks']['fenix-x86_64-release.apk']
    for label in ('ubo-lifecycle', 'baseline', 'pref-audit'):
        c.require(state['stages'][label]['exit'] == 0, 'runtime gate was not successful: ' + label)
        c.checked(state['stages'][label]['log'])
    for key, required_checks in (('ubo_lifecycle', prior_runtime.UBO), ('baseline', prior_runtime.BASELINE),
                                 ('pref_dump', {'pref-dump'})):
        path = c.checked(state[key])
        c.require(prior_runtime.grade_smoke(path, required_checks, apk) == state[key],
                  'runtime report grading differs: ' + key)
    build_config = json.loads(c.checked(build['inputs']).read_text())
    kept = records([state, config, build, build_config,
                    c.record(result_path), c.record(c.BUILD / 'result.json'),
                    [c.record(Path(name)) for name in c.manifest(c.NATIVE_MANIFEST, absolute=True)]])
    return {'runtime_service': terminal, 'build_service': build_terminal,
            'test_service': config['test_service'], 'runtime_receipt': c.record(result_path),
            'build_receipt': c.record(c.BUILD / 'result.json'),
            'preserved_files': [kept[n] for n in sorted(kept)]}


def source_path(source, name):
    v.name_ok(name)
    c.require(source.is_dir() and not source.is_symlink(), 'source root must be a real directory')
    current = source
    parts = Path(name).parts
    for part in parts[:-1]:
        current = current / part
        c.require(not current.is_symlink() and (not current.exists() or current.is_dir()),
                  'source parent is a symlink/non-directory: ' + name)
    target = source / name
    c.require(not target.is_symlink(), 'source target is a symlink: ' + name)
    return target


def source_checks(source, expected):
    rows = []
    for name, digest in sorted(expected.items()):
        path = source_path(source, name)
        if digest is None:
            c.require(not path.exists(), 'expected source absence: ' + name)
            rows.append({'path': name, 'expected_sha256': None, 'observed': 'absent'})
        else:
            c.require(path.is_file() and c.digest(path) == digest, 'source hash differs: ' + name)
            rows.append({'path': name, 'expected_sha256': digest, 'observed': digest})
    return rows


def checkpoint_inputs():
    # This checkpoint is runtime-only. Its build authority remains the unchanged
    # original module, not a fabricated build.py in the new directory.
    paths = list(c.runtime_inputs().values()) + c.capsule_inputs()
    paths += [c.record(c.PARENT / n) for n in ('common.py', 'build.py', 'runtime.py', 'parent-inputs.json')]
    return sorted(paths, key=lambda row: row['path'])


def version_inputs():
    pins = json.loads((HERE / 'version-inputs.json').read_text())
    c.require(pins['schema'] == 1 and pins['before_manifest_sha256'] == v.BASE
              and pins['final_manifest_sha256'] == v.FINAL and pins['source_count'] == 245
              and pins['body_count'] == 107 and pins['stage_kind'] == 'account-process245-source-stage'
              and pins['stage_service'] == SERVICE and c.SOURCE_SHA == v.BASE
              and pins['checkpoint'] == str(CHECKPOINT.relative_to(v.REPO))
              and pins['payload_sha256'] == c.digest(v.HANDOFF / 'composed-source-subset.tar.gz'),
              'versioned stage/source identity differs')
    for key in ('parent_stage', 'composition_inputs', 'composition_verifier'):
        row = pins[key]
        observed = c.record(v.REPO / row['path'])
        c.require(observed['sha256'] == row['sha256'] and observed['bytes'] == row['bytes'],
                  'frozen composition code changed: ' + key)
    observed = {str(Path(row['path']).relative_to(v.REPO)):
                {'sha256': row['sha256'], 'bytes': row['bytes']} for row in checkpoint_inputs()}
    c.require(observed == pins['checkpoint_files'], 'reviewed checkpoint/capsule bytes changed')
    return pins


def own_inputs():
    version_inputs()
    paths = [HERE / n for n in ('stage.py', 'version-inputs.json')]
    paths += [v.HERE / n for n in ('inputs.json', 'frozen-repository-inputs.tar.gz', 'verify.py', 'stage.py')]
    paths += sorted(p for p in v.HANDOFF.iterdir() if p.is_file())
    paths += [Path(row['path']) for row in checkpoint_inputs()]
    pins = json.loads((v.HERE / 'inputs.json').read_text())
    paths += [v.REPO / pins[key]['path'] for key in
              ('historical_frozen_repository_inputs', 'historical245_bodies', 'historical245_manifest')]
    return [c.record(p) for p in sorted(set(paths))]


def prepare():
    c.guest_guard()
    c.require(not OUT.exists() and not OUT.is_symlink(), 'fresh staging evidence directory required')
    plan = v.load_plan()
    gates = prerequisites()
    source_checks(c.SOURCE, plan['before'])
    return {'schema': 1, 'kind': 'account-process245-source-stage', 'service_name': SERVICE,
            'source_dir': str(c.SOURCE), 'evidence_dir': str(OUT),
            'before_manifest_sha256': v.BASE, 'final_manifest_sha256': v.FINAL,
            'source_count': 245, 'source_plan_receipt_sha256': plan['pins']['handoff_receipt_sha256'],
            'source_inputs': own_inputs(), 'prerequisites': gates,
            'scope': 'Stage exactly the 88 reviewed changed source bodies after current167 acceptance; no native build, install, signing or release.'}


def checked_config(path, digest):
    c.require(c.digest(path) == digest, 'staging config differs from explicitly reviewed digest')
    config = json.loads(path.read_text())
    c.require(config['schema'] == 1 and config['kind'] == 'account-process245-source-stage'
              and config['service_name'] == SERVICE and config['source_dir'] == str(c.SOURCE)
              and config['evidence_dir'] == str(OUT) and config['source_count'] == 245
              and config['before_manifest_sha256'] == v.BASE and config['final_manifest_sha256'] == v.FINAL,
              'wrong staging selection')
    c.require(config['source_inputs'] == own_inputs(), 'staging code/retained inputs changed')
    plan = v.load_plan()
    c.require(config['source_plan_receipt_sha256'] == plan['pins']['handoff_receipt_sha256'], 'plan receipt differs')
    return config, plan


def check_preserved(config):
    for row in config['prerequisites']['preserved_files']:
        c.checked(row)
    c.require(config['source_inputs'] == own_inputs(), 'staging inputs changed')
    v.load_plan()
    gates = config['prerequisites']
    for kind, key in (('runtime', 'runtime_service'), ('apk', 'build_service')):
        observed = c.service(c.SERVICES[kind], gates[key]['InvocationID'], terminal=True)
        c.require(observed == gates[key], 'prior checkpoint service changed')
    observed = c.service(c.SERVICES['tests'], gates['test_service']['InvocationID'], terminal=True)
    c.require(observed == gates['test_service'], 'prior test service changed')


def backup_replacements(source, plan, folder):
    stream = io.BytesIO()
    entries = []
    with gzip.GzipFile(fileobj=stream, mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name, row in sorted(plan['rows'].items()):
                if row['action'] != 'replace-if-before-matches':
                    continue
                path = source_path(source, name)
                data = path.read_bytes()
                c.require(v.sha(data) == plan['before'][name], 'replacement changed before backup: ' + name)
                mode = stat.S_IMODE(path.stat().st_mode)
                member = tarfile.TarInfo(name)
                member.mode, member.size, member.mtime = mode, len(data), 0
                archive.addfile(member, io.BytesIO(data))
                entries.append({'path': name, 'sha256': v.sha(data), 'bytes': len(data), 'mode': mode})
    path = folder / 'source-before-replacements.tar.gz'
    path.write_bytes(stream.getvalue())
    with path.open('rb') as stream:
        os.fsync(stream.fileno())
    c.write_json(folder / 'source-before-replacements.json', entries)
    return {'archive': c.record(path), 'files': c.record(folder / 'source-before-replacements.json'), 'count': len(entries)}


def install_body(source, name, before, body):
    """One atomic file update. A created path never overwrites an existing one."""
    path = source_path(source, name)
    source_checks(source, {name: before})
    mode = stat.S_IMODE(path.stat().st_mode) if before is not None else 0o644
    path.parent.mkdir(parents=True, exist_ok=True)
    # Recheck newly traversed parents before opening the temporary file.
    source_path(source, name)
    fd, temporary_name = tempfile.mkstemp(prefix='.' + path.name + '.current245-', dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        source_checks(source, {name: before})
        if before is None:
            # link() fails with EEXIST even if another file appeared after the
            # last check. The temporary file is on the same source filesystem.
            os.link(temporary, path)
            temporary.unlink()
        else:
            os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        c.require(c.digest(path) == v.sha(body), 'written source hash differs: ' + name)
    finally:
        temporary.unlink(missing_ok=True)


def own_service():
    invocation = os.environ.get('INVOCATION_ID', '')
    c.require(re.fullmatch('[0-9a-f]{32}', invocation) is not None, 'actual retained staging service required')
    state = c.service(SERVICE, invocation)
    c.require(state['ActiveState'] == 'active' and state['SubState'] == 'running', 'staging service is not running')
    return state


def execute(path, digest):
    c.guest_guard()
    config, plan = checked_config(path, digest)
    c.require(not OUT.exists() and not OUT.is_symlink(), 'staging output already exists; preserve failed/successful evidence')
    observed = own_service()
    c.require(prerequisites() == config['prerequisites'], 'current167 acceptance changed after config review')
    before = source_checks(c.SOURCE, plan['before'])
    check_preserved(config)
    OUT.mkdir()
    shutil.copy2(path, OUT / 'inputs.json')
    shutil.copy2(v.HANDOFF / 'receipt.json', OUT / 'source-plan-receipt.json')
    shutil.copy2(v.HANDOFF / 'proposed-staging.json', OUT / 'source-plan.json')
    shutil.copy2(v.HANDOFF / 'expected-current167-source-sha256.txt', OUT / 'parent-source-sha256.txt')
    c.write_json(OUT / 'source-before.json', before)
    state = {'schema': 1, 'status': 'PREPARING', 'kind': 'account-process245-source-stage', 'service': observed,
             'source_dir': str(c.SOURCE), 'started': c.now(), 'inputs': c.record(OUT / 'inputs.json'),
             'source_plan_receipt': c.record(OUT / 'source-plan-receipt.json'),
             'source_before': c.record(OUT / 'source-before.json'), 'applied': [],
             'scope': 'Source staging only; native compilation, APK rebuild and target runtime for245 remain pending.'}
    c.write_json(OUT / 'receipt.json', state)
    try:
        state['backups'] = backup_replacements(c.SOURCE, plan, OUT)
        c.require(state['backups']['count'] == 43, 'replacement backup count differs')
        # Final full preflight after backups and immediately before any source
        # mutation. Current167 and every additional existing/absent path repeat.
        c.require(source_checks(c.SOURCE, plan['before']) == before, 'source changed after backup')
        check_preserved(config)
        c.guest_guard()
        state['status'] = 'APPLYING'
        c.write_json(OUT / 'receipt.json', state)
        for name, row in sorted(plan['rows'].items()):
            if row['action'] == 'retain-bound-input':
                continue
            state['attempting'] = {'path': name, 'action': row['action'],
                                   'before_sha256': plan['before'][name], 'after_sha256': row['after_sha256']}
            c.write_json(OUT / 'receipt.json', state)
            install_body(c.SOURCE, name, plan['before'][name], plan['bodies'][name])
            state['applied'].append({'path': name, 'action': row['action'], 'sha256': row['after_sha256']})
            del state['attempting']
            c.write_json(OUT / 'receipt.json', state)
        c.require(len(state['applied']) == 88, 'applied source count differs')
        after = source_checks(c.SOURCE, plan['final'])
        check_preserved(config)
        c.write_json(OUT / 'source-after.json', after)
        (OUT / 'source-sha256.txt').write_bytes(plan['files']['proposed-source-sha256.txt'])
        c.require(c.digest(OUT / 'source-sha256.txt') == v.FINAL, 'final manifest output differs')
        state.update(status='PASS', source_count=245, source_manifest=c.record(OUT / 'source-sha256.txt'),
                     source_after=c.record(OUT / 'source-after.json'), preserved_file_count=len(config['prerequisites']['preserved_files']))
        return 0
    except BaseException as error:
        state.update(status='FAIL', error=type(error).__name__ + ': ' + str(error),
                     recovery='Do not rerun automatically. Preserve backups/progress and inspect every touched path before an explicitly reviewed recovery.')
        raise
    finally:
        state['finished'] = c.now()
        c.write_json(OUT / 'receipt.json', state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print-config', action='store_true')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--config-sha256')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.print_config:
        c.require(not args.config and not args.config_sha256 and not args.run, 'config capture is separate from staging')
        print(json.dumps(prepare(), indent=2))
        return 0
    c.require(args.config is not None and args.config_sha256, 'explicit reviewed config/hash required')
    if args.run:
        return execute(args.config, args.config_sha256)
    config, plan = checked_config(args.config, args.config_sha256)
    c.require(prerequisites() == config['prerequisites'], 'prerequisites changed')
    source_checks(c.SOURCE, plan['before'])
    print(json.dumps({'status': 'PLAN ONLY', 'source_count': 245, 'existing': 200, 'absent': 45,
                      'final_manifest_sha256': v.FINAL, 'evidence': str(OUT)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
