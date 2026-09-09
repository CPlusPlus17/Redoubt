#!/usr/bin/env python3
"""Replay Task37 on the corrected current167 / proposed232 plan; never stage or build it."""
import argparse
import collections
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
TASK = 'docs/android/evidence/lw-m7-37/'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    require(name and not p.is_absolute() and '..' not in p.parts and
            str(p) == name and '\\' not in name, f'unsafe path: {name!r}')
    return name


def unpack(data):
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive:
            name = safe_name(member.name)
            require(member.isfile() and name not in files,
                    f'non-file or duplicate archive member: {name}')
            files[name] = archive.extractfile(member).read()
    return files


def pack(files):
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name, data in sorted(files.items()):
                member = tarfile.TarInfo(safe_name(name))
                member.size, member.mode, member.mtime = len(data), 0o644, 0
                archive.addfile(member, io.BytesIO(data))
    return stream.getvalue()


def manifest(data):
    result = {}
    for row in data.decode().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', row)
        require(match is not None, f'malformed manifest row: {row!r}')
        digest, name = match.groups()
        safe_name(name)
        require(name not in result, f'duplicate manifest path: {name}')
        result[name] = digest
    require(result, 'empty manifest')
    return result


def manifest_bytes(rows):
    return ''.join(f'{digest}  {name}\n' for name, digest in sorted(rows.items())).encode()


def json_bytes(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def check_files(files, pins):
    require(set(files) == set(pins), 'file inventory differs from pins')
    for name, pin in pins.items():
        require({'sha256': sha(files[name]), 'bytes': len(files[name])} == pin,
                f'input differs: {name}')


def compose(repo):
    pins = json.loads((HERE / 'inputs.json').read_bytes())
    parent_archive = (HERE / 'parent-handoff.tar.gz').read_bytes()
    require(sha(parent_archive) == pins['parent_handoff_sha256'] and
            len(parent_archive) == pins['parent_handoff_bytes'], 'parent archive differs')
    parent = unpack(parent_archive)
    check_files({k: v for k, v in parent.items() if k != 'handoff-sha256.json'},
                json.loads(parent['handoff-sha256.json']))
    inputs = {name: (repo / safe_name(name)).read_bytes() for name in pins['task37_inputs']}
    check_files(inputs, pins['task37_inputs'])
    task = json.loads(inputs[TASK + 'native-source-files.json'])
    composition = json.loads(inputs[TASK + 'native-composition.json'])
    baseline = unpack(inputs[TASK + 'native-source-baseline.tar.gz'])
    capture = unpack(inputs[TASK + 'current-capture/guest-source.tar.gz'])
    capture_rows = json.loads(inputs[TASK + 'current-capture/source-inputs.json'])['files']
    captured = {row['path']: row for row in capture_rows}
    for name, row in captured.items():
        blob = capture.get('source/' + name)
        require((blob is not None) == row['exists'], f'capture existence: {name}')
        if blob is not None:
            require(sha(blob) == row['sha256'] and len(blob) == row['bytes'],
                    f'capture bytes: {name}')
    require(sha(inputs[TASK + 'native-composition.json']) == task['source_composition_sha256'],
            'Task37 composition pin')
    require(sha(inputs[TASK + 'native-source-baseline.tar.gz']) == task['baseline_archive_sha256'],
            'Task37 baseline pin')
    require(sha(inputs['patches/android/session-cleanup.patch']) == task['patch_sha256'],
            'Task37 patch pin')
    task_rows = {row['path']: row for row in task['files']}
    require(len(task_rows) == len(task['files']) == 15 and
            set(task_rows) == set(composition['paths']), 'Task37 scope differs')
    require(set(baseline) == {name for name, row in task_rows.items() if row['before_sha256']},
            'Task37 before inventory')
    for name, data in baseline.items():
        require(sha(data) == task_rows[name]['before_sha256'] and
                len(data) == task_rows[name]['before_bytes'], f'Task37 before: {name}')

    require(sha(parent['proposed-source-sha256.txt']) == pins['parent_final_manifest_sha256'],
            'parent final manifest differs')
    require(sha(parent['expected-current167-source-sha256.txt']) ==
            pins['expected_current167_manifest_sha256'], 'parent current manifest differs')
    final = manifest(parent['proposed-source-sha256.txt'])
    current = manifest(parent['expected-current167-source-sha256.txt'])
    original = manifest(parent['original-native4-source-sha256.txt'])
    bodies = unpack(parent['composed-source-subset.tar.gz'])
    subset = manifest(parent['composed-subset-sha256.txt'])
    require(set(subset) == set(bodies), 'parent subset inventory')
    for name, data in bodies.items():
        require(sha(data) == subset[name] == final.get(name), f'parent body: {name}')
    stage = json.loads(parent['proposed-staging.json'])
    stage_rows = {row['path']: row for row in stage['files']}
    require(len(stage_rows) == len(stage['files']) and set(stage_rows) == set(bodies),
            'parent staging inventory')
    for name, row in stage_rows.items():
        require(row['after_sha256'] == final[name] and row['after_bytes'] == len(bodies[name]),
                f'parent staged body: {name}')
    require(stage['untouched_original_bindings'] ==
            {name: digest for name, digest in final.items() if name not in bodies},
            'parent retained native inventory')
    shared = sorted(set(task_rows) & set(final))
    added = sorted(set(task_rows) - set(final))
    require(len(shared) == 2 and len(added) == 13, 'reviewed overlay inventory changed')
    for name, row in task_rows.items():
        before = row['before_sha256']
        if name in bodies:
            require(sha(bodies[name]) == before, f'composed predecessor differs: {name}')
        else:
            require(name not in final, f'unmaterialized shared path needs review: {name}')
            cap = captured[name]
            require((cap['sha256'] if cap['exists'] else None) == before,
                    f'new staging baseline differs from actual capture: {name}')
            if before:
                bodies[name] = baseline[name]
    old_bodies = dict(bodies)
    with tempfile.TemporaryDirectory(prefix='lw-m7-37-compose-') as scratch:
        tree = Path(scratch)
        for name, data in bodies.items():
            path = tree / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1'],
                                cwd=tree, input=inputs['patches/android/session-cleanup.patch'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        text = (result.stdout + result.stderr).decode()
        require(result.returncode == 0 and not re.search(r'offset|fuzz|FAILED|reject', text, re.I),
                f'composition patch failed or drifted:\n{text}')
        bodies = {path.relative_to(tree).as_posix(): path.read_bytes()
                  for path in tree.rglob('*') if path.is_file()}
    require(set(bodies) == set(old_bodies) | set(task_rows), 'patch changed undeclared paths')
    for name, data in bodies.items():
        if name in task_rows:
            require(sha(data) == task_rows[name]['after_sha256'] and
                    len(data) == task_rows[name]['after_bytes'], f'composed after: {name}')
        else:
            require(data == old_bodies[name], f'unrelated body changed: {name}')
    for name, row in task_rows.items():
        if name not in stage_rows:
            before = row['before_sha256']
            stage_rows[name] = {
                'path': name, 'original_native4_sha256': original.get(name),
                'expected_before_staging_sha256': before,
                'action': 'replace-if-before-matches' if before else 'create-if-absent',
                'baseline_binding': 'Task37-actual-guest-capture-requires-live-preflight',
                'lineage': [],
            }
        item = stage_rows[name]
        item.update(after_sha256=row['after_sha256'], after_bytes=row['after_bytes'])
        item['lineage'].append({'task': '37', 'before_sha256': row['before_sha256'],
                                'after_sha256': row['after_sha256'], 'delivery': 'source_patch'})
        final[name] = row['after_sha256']
    before = dict(current)
    for name, item in stage_rows.items():
        digest = item['expected_before_staging_sha256']
        require(name not in before or before[name] == digest, f'conflicting live input: {name}')
        before[name] = digest
    require(set(before) == set(final), 'full live preflight coverage differs')
    retained = {name: digest for name, digest in final.items() if name not in bodies}
    require(retained == stage['untouched_original_bindings'], 'retained native coverage changed')
    after_manifest = manifest_bytes(final)
    stage.update(
        scope='SOURCE PLAN ONLY, NOT STAGED. Exact Task37 increment on corrected current167 / proposed232; preserve historical243 separately. Preflight every existing and absent path before any mutation.',
        parent_final232_manifest_sha256=sha(parent['proposed-source-sha256.txt']),
        final_manifest_sha256=sha(after_manifest), final_count=len(final),
        files=[stage_rows[name] for name in sorted(stage_rows)],
        task37_patch_sha256=task['patch_sha256'],
        untouched_original_bindings=retained,
    )
    outputs = {
        'proposed-source-sha256.txt': after_manifest,
        'composed-subset-sha256.txt': manifest_bytes({n: sha(b) for n, b in bodies.items()}),
        'composed-source-subset.tar.gz': pack(bodies),
        'proposed-staging.json': json_bytes(stage),
        'expected-current167-source-sha256.txt': parent['expected-current167-source-sha256.txt'],
        'parent-final232-source-sha256.txt': parent['proposed-source-sha256.txt'],
        'original-native4-source-sha256.txt': parent['original-native4-source-sha256.txt'],
        'live-preflight.json': json_bytes({
            'scope': 'READ ONLY verification required before any staging; not proof of a build or navigation barrier.',
            'expected_current167_manifest_sha256': pins['expected_current167_manifest_sha256'],
            'final_manifest_sha256': sha(after_manifest),
            'files': [{'path': n, 'expected_sha256': d} for n, d in sorted(before.items())],
        }),
        'replay-log.json': json_bytes({'command': ['patch', '--batch', '--forward', '--fuzz=0', '-p1'],
                                      'exit_code': result.returncode, 'stdout': result.stdout.decode(),
                                      'stderr': result.stderr.decode()}),
    }
    receipt = {
        'status': 'PASS local exact source composition only; NOT staged, compiled or target-tested',
        'actor': '/root/coverage_map', 'script_sha256': sha(Path(__file__).read_bytes()),
        'inputs_sha256': sha((HERE / 'inputs.json').read_bytes()),
        'parent_handoff_sha256': sha(parent_archive),
        'parent_final232_manifest_sha256': pins['parent_final_manifest_sha256'],
        'task37_implementation_commit': pins['task37_implementation_commit'],
        'task37_patch_sha256': task['patch_sha256'], 'task37_source_paths': len(task_rows),
        'shared_with_parent': shared, 'new_to_manifest': added,
        'materialized_subset_count': len(bodies), 'final_union_count': len(final),
        'original_files_without_local_body': len(retained),
        'staging_actions': dict(sorted(collections.Counter(r['action'] for r in stage_rows.values()).items())),
        'live_existing_checks': sum(d is not None for d in before.values()),
        'live_absence_checks': sum(d is None for d in before.values()),
        'additional_to_current167_preflights': len(before) - len(current),
        'retained_native_rule': f'All {len(retained)} unchanged native bindings retain original hashes; bytes require live verification. The {len(bodies)}-file archive is not a complete Gecko tree.',
        'limits': 'Only frame and cookie primitives implemented. Full writer/cache admission, journal success and all target compilation/runtime remain pending. Current167 Home routing and test corrections are included via the exact parent handoff; older native/compiler/test receipts remain historical.',
        'outputs': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in sorted(outputs.items())},
    }
    outputs['receipt.json'] = json_bytes(receipt)
    return outputs, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New local output directory; never a source tree')
    args = parser.parse_args()
    require(not args.output.exists(), 'output directory must not exist')
    outputs, receipt = compose(args.repo.resolve())
    args.output.mkdir(parents=True)
    for name, data in outputs.items():
        (args.output / name).write_bytes(data)
    print(json.dumps({k: receipt[k] for k in ['status', 'materialized_subset_count', 'final_union_count',
                                             'live_existing_checks', 'live_absence_checks']}))


if __name__ == '__main__':
    main()
