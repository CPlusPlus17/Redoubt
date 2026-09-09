#!/usr/bin/env python3
"""Reproduce historical232, verify current process admission fixes, then derive corrected232; never stage or build."""
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


def run(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    require(result.returncode == 0, f'failed {command}:\n{result.stdout}\n{result.stderr}')
    return {'command': command, 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}


def compose(repo):
    pins = json.loads((HERE / 'inputs.json').read_bytes())
    current_inputs = {name: (repo / safe_name(name)).read_bytes() for name in pins['files']}
    check_files(current_inputs, pins['files'])
    parent_raw = (HERE / 'historical232-handoff.tar.gz').read_bytes()
    require(sha(parent_raw) == pins['historical232_handoff_sha256'], 'historical232 archive differs')
    parent = unpack(parent_raw)
    parent_pins = json.loads(parent['handoff-sha256.json'])
    check_files({k: v for k, v in parent.items() if k != 'handoff-sha256.json'}, parent_pins)
    old_inputs = json.loads(parent['audit-inputs.json'])
    with tempfile.TemporaryDirectory(prefix='lw-process-compose-') as scratch:
        root = Path(scratch)
        previous, corrected = root / 'historical-inputs', root / 'current-inputs'
        previous.mkdir(); corrected.mkdir()
        historical = {}
        for name, pin in old_inputs['files'].items():
            body = subprocess.check_output(['git', 'show', old_inputs['repository_commit'] + ':' + name], cwd=repo)
            historical[name] = body
            path = previous / safe_name(name)
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        check_files(historical, old_inputs['files'])
        for name, body in current_inputs.items():
            path = corrected / name
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        script = root / 'historical-audit.py'; script.write_bytes(parent['audit.py'])
        input_file = root / 'audit-inputs.json'; input_file.write_bytes(parent['audit-inputs.json'])
        historical_log = run(['python3', str(script), '--repo', str(previous), '--output', str(root / 'replayed'), '--pins', str(input_file)], root)
        repeated = {}
        for name, expected in parent.items():
            output = root / 'replayed' / name
            if output.is_file():
                require(output.read_bytes() == expected, 'historical replay output drifted: ' + name)
                repeated[name] = sha(expected)
        require(len(repeated) == 19, 'historical output comparison scope changed')
        # Run actual corrected task validators using only the declared current input files.
        checks = []
        for task in ['20', '26']:
            checks.append(run(['python3', str(corrected / f'docs/android/evidence/lw-m7-{task}/isolated-process-correction/verify.py')], corrected))
        # Scratch directory names are incidental, so keep logs reproducible.
        logs = json.loads(json.dumps({'historical': historical_log, 'current': checks}).replace(str(root), '<scratch>'))

    task26 = 'docs/android/evidence/lw-m7-26/isolated-process-correction/'
    change = json.loads(current_inputs[task26 + 'current167-overlay.json'])
    overlay = unpack(current_inputs[task26 + 'current167-source-overlay.tar.gz'])
    require(sha(current_inputs[task26 + 'current167-source-overlay.tar.gz']) == change['overlay_archive_sha256'], 'process overlay archive differs')
    original_current = parent['expected-current167-source-sha256.txt']
    require(sha(original_current) == change['previous_source_sha256'], 'process parent current167 differs')
    current = manifest(original_current)
    final = manifest(parent['proposed-source-sha256.txt'])
    old_final = dict(final)
    bodies = unpack(parent['composed-source-subset.tar.gz'])
    old_bodies = dict(bodies)
    subset = manifest(parent['composed-subset-sha256.txt'])
    require(set(subset) == set(bodies), 'historical subset inventory differs')
    for name, body in bodies.items():
        require(sha(body) == subset[name] == final[name], 'historical body differs: ' + name)
    stage = json.loads(parent['proposed-staging.json'])
    stage_rows = {r['path']: r for r in stage['files']}
    original_native = manifest(parent['original-native4-source-sha256.txt'])
    require(set(stage_rows) == set(bodies), 'historical staging scope differs')
    for name, row in stage_rows.items():
        require(row['after_sha256'] == sha(bodies[name]) and row['after_bytes'] == len(bodies[name]), 'historical staging body differs: ' + name)
    require(stage['untouched_original_bindings'] == {n: d for n, d in final.items() if n not in bodies}, 'historical retained bindings differ')
    rows = {r['path']: r for r in change['files']}
    require(len(rows) == 6 and set(rows) == set(overlay), 'process change inventory differs')
    later = ['patches/android/extension-permission-durability.patch', 'patches/android/firefox-suggest-data.patch', 'patches/android/extension-update-controls.patch', 'patches/android/global-privacy-controls.patch']
    registry = [line.split('#', 1)[0].strip() for line in current_inputs['assets/patches/android.txt'].decode().splitlines()]
    require([registry.index(p) for p in later] == sorted(registry.index(p) for p in later), 'later registry order changed')
    disjoint = {}
    for patch in later:
        require(current_inputs[patch] == historical[patch], 'later patch bytes changed: ' + patch)
        paths = set(re.findall(r'^\+\+\+ b/(.+)$', current_inputs[patch].decode(), re.M))
        require(paths and not (paths & set(rows)), 'process correction overlaps later patch: ' + patch)
        disjoint[patch] = {'sha256': sha(current_inputs[patch]), 'process_path_overlap': sorted(paths & set(rows))}
    for name, row in rows.items():
        require(name not in bodies, 'newly retained process source was already materialized: ' + name)
        require(current[name] == final[name] == row['before_sha256'], 'process before differs: ' + name)
        require(sha(overlay[name]) == row['after_sha256'], 'process after differs: ' + name)
        current[name] = final[name] = row['after_sha256']
        bodies[name] = overlay[name]
        stage_rows[name] = {
            'path': name, 'original_native4_sha256': original_native.get(name),
            'expected_before_staging_sha256': row['after_sha256'],
            'after_sha256': row['after_sha256'], 'after_bytes': len(overlay[name]),
            'action': 'retain-bound-input', 'baseline_binding': 'corrected-current167-process-manifest',
            'lineage': [{'task': '20+26-process-correction', 'before_sha256': row['before_sha256'], 'after_sha256': row['after_sha256'], 'delivery': 'already-applied-current167-source-overlay'}],
        }
    require(len(current) == 167 and len(final) == 232 and len(bodies) == 94, 'derived process composition counts changed')
    require(manifest_bytes(current) == current_inputs[task26 + 'proposed-current167-source-sha256.txt'], 'corrected167 derived bytes differ')
    require(sha(manifest_bytes(current)) == change['proposed_source_sha256'], 'corrected167 digest differs')
    require({n for n in old_final if old_final[n] != final[n]} == set(rows), 'unexpected final source change')
    require(all(bodies[n] == b for n, b in old_bodies.items()), 'historical materialized bodies changed')
    retained = {n: d for n, d in final.items() if n not in bodies}
    preflight = dict(current)
    for name, row in stage_rows.items():
        before = row['expected_before_staging_sha256']
        require(name not in preflight or preflight[name] == before, 'live preflight conflict: ' + name)
        preflight[name] = before
    require(set(preflight) == set(final), 'preflight does not cover final union')
    stage.update(scope='SOURCE PLAN ONLY, NOT STAGED. Historical exact232 replay plus six isolated-process corrections already present in corrected167. All current167 and additional before/absence paths require verification before staging.',
        historical232_manifest_sha256=sha(parent['proposed-source-sha256.txt']),
        historical167_manifest_sha256=sha(original_current),
        expected_current167_manifest_sha256=sha(manifest_bytes(current)),
        final_manifest_sha256=sha(manifest_bytes(final)), final_count=len(final),
        process_correction_overlay_sha256=change['overlay_archive_sha256'],
        files=[stage_rows[n] for n in sorted(stage_rows)], untouched_original_bindings=retained)
    outputs = {
        'expected-current167-source-sha256.txt': manifest_bytes(current),
        'proposed-source-sha256.txt': manifest_bytes(final),
        'composed-subset-sha256.txt': manifest_bytes({n: sha(b) for n, b in bodies.items()}),
        'composed-source-subset.tar.gz': pack(bodies),
        'proposed-staging.json': json_bytes(stage),
        'original-native4-source-sha256.txt': parent['original-native4-source-sha256.txt'],
        'original-compiled165-source-sha256.txt': parent['original-compiled165-source-sha256.txt'],
        'historical-current167-source-sha256.txt': original_current,
        'historical-proposed232-source-sha256.txt': parent['proposed-source-sha256.txt'],
        'live-preflight.json': json_bytes({'scope': 'Required read-only before/absence checks, not executed on a guest by this audit.', 'expected_current167_manifest_sha256': sha(manifest_bytes(current)), 'final_manifest_sha256': sha(manifest_bytes(final)), 'files': [{'path': n, 'expected_sha256': d} for n, d in sorted(preflight.items())]}),
        'process-overlay.json': json_bytes(change), 'replay-logs.json': json_bytes(logs),
        'lineage-proof.json': json_bytes({'historical_git_snapshot': old_inputs['repository_commit'], 'historical_input_count': len(historical), 'historical_repeated_outputs': repeated, 'later_patches': disjoint, 'unchanged_materialized_body_count': len(old_bodies), 'current_167_unchanged_bindings': len(current)-len(rows), 'current_repository_commit': pins['repository_commit'], 'current_input_count': len(current_inputs)}),
    }
    receipt = {'status': 'PASS local exact source composition only; NOT staged, built or target-tested',
        'actor': '/root/coverage_map', 'script_sha256': sha(Path(__file__).read_bytes()), 'inputs_sha256': sha((HERE/'inputs.json').read_bytes()),
        'historical232_handoff_sha256': sha(parent_raw), 'historical232_manifest_sha256': sha(parent['proposed-source-sha256.txt']),
        'expected_current167_manifest_sha256': sha(manifest_bytes(current)), 'registry_order': later,
        'final_union_count': len(final), 'materialized_subset_count': len(bodies), 'original_files_without_local_body': len(retained),
        'staging_actions': dict(sorted(collections.Counter(r['action'] for r in stage_rows.values()).items())),
        'live_existing_checks': sum(d is not None for d in preflight.values()), 'live_absence_checks': sum(d is None for d in preflight.values()),
        'additional_to_current167_preflights': len(preflight)-len(current), 'generated_suggest_count': 13,
        'retained_native_rule': 'All 138 unchanged manifest-only bindings require live byte verification. The 94-body archive is not a complete source tree. All prior 88 materialized bodies, 13 generated Suggest resources and Task30 empty raw resource are byte-identical.',
        'target_scope': 'Original compiled165/native4 and prior501d remain historical. Corrected167 target results are separate receipts; this future31/29/35/36 candidate has no target verdict.',
        'outputs': {n: {'sha256': sha(b), 'bytes': len(b)} for n,b in sorted(outputs.items())}}
    outputs['receipt.json'] = json_bytes(receipt)
    return outputs, receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    require(not args.output.exists(), 'output must not exist')
    outputs,receipt=compose(args.repo.resolve())
    args.output.mkdir(parents=True)
    for name,body in outputs.items(): (args.output/name).write_bytes(body)
    print(json.dumps({k:receipt[k] for k in ['status','final_union_count','materialized_subset_count','staging_actions']}))

if __name__=='__main__': main()
