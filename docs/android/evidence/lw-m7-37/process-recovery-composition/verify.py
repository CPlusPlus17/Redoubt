#!/usr/bin/env python3
"""Independently check current245 coverage and replay both retained source plans."""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
HANDOFF = HERE / 'handoff'
BASE = '4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739'
FINAL = '40da1bf9c42187b1e037fba5b443e4b26fd2758ffa7b07212710df72693eb806'
PATCH37 = 'd2756b4f5fe27adef63114a78ae7338ffbc13d0da60933ac03636b39721c5248'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def name_ok(name):
    p = PurePosixPath(name)
    require(name and str(p) == name and not p.is_absolute() and '..' not in p.parts
            and '\\' not in name, 'unsafe source/archive path: ' + repr(name))
    return name


def unpack(data):
    result = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive:
            name_ok(member.name)
            require(member.isfile() and member.name not in result, 'duplicate or nonregular archive member')
            result[member.name] = archive.extractfile(member).read()
    return result


def check_pins(files, pins):
    require(set(files) == set(pins), 'input inventory differs')
    for name, row in pins.items():
        require(sha(files[name]) == row['sha256'] and len(files[name]) == row['bytes'], 'input differs: ' + name)


def manifest(data):
    result = {}
    for line in data.decode().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        require(match is not None, 'invalid manifest row')
        digest, name = match.groups()
        name_ok(name)
        require(name not in result, 'duplicate manifest row')
        result[name] = digest
    require(result, 'empty manifest')
    return result


def populate(folder, files):
    for name, data in files.items():
        path = folder / name_ok(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def pinned_history(pins, key):
    row = pins[key]
    data = (REPO / name_ok(row['path'])).read_bytes()
    require(sha(data) == row['sha256'] and len(data) == row['bytes'], 'historical input differs: ' + key)
    return data


def load_plan(check_current=True):
    pins = json.loads((HERE / 'inputs.json').read_bytes())
    require(pins['current167_manifest_sha256'] == BASE and pins['final245_manifest_sha256'] == FINAL,
            'reviewed source identities differ')
    files = {p.name: p.read_bytes() for p in HANDOFF.iterdir() if p.is_file()}
    require(sha(files['handoff-sha256.json']) == pins['handoff_manifest_sha256'], 'handoff inventory pin differs')
    check_pins({n: b for n, b in files.items() if n != 'handoff-sha256.json'}, json.loads(files['handoff-sha256.json']))
    require(sha(files['receipt.json']) == pins['handoff_receipt_sha256'], 'handoff receipt differs')
    receipt = json.loads(files['receipt.json'])
    for name, pin in receipt['outputs'].items():
        check_pins({name: files[name]}, {name: pin})
    frozen_data = (HERE / 'frozen-repository-inputs.tar.gz').read_bytes()
    frozen_pin = pins['frozen_repository_inputs']
    require(sha(frozen_data) == frozen_pin['sha256'] and len(frozen_data) == frozen_pin['bytes'], 'frozen repository archive differs')
    frozen = unpack(frozen_data)
    check_pins(frozen, frozen_pin['files'])
    parent = unpack(files['parent-handoff.tar.gz'])
    check_pins({n: b for n, b in parent.items() if n != 'handoff-sha256.json'}, json.loads(parent['handoff-sha256.json']))
    parent_inputs = json.loads(parent['inputs.json'])['files']
    task_inputs = json.loads(files['inputs.json'])['task37_inputs']
    require(len(parent_inputs) == 212 and len(task_inputs) == 6 and len(frozen) == 218,
            '212 parent plus six Task37 inputs are required')
    require({**parent_inputs, **task_inputs} == frozen_pin['files'], 'frozen input lineage differs')
    historical_parent = unpack(parent['historical232-handoff.tar.gz'])
    check_pins({n: b for n, b in historical_parent.items() if n != 'handoff-sha256.json'},
               json.loads(historical_parent['handoff-sha256.json']))
    historical_pins = json.loads(historical_parent['audit-inputs.json'])
    historical_frozen = unpack(pinned_history(pins, 'historical_frozen_repository_inputs'))
    require(len(historical_frozen) == 157 and len(historical_pins['files']) == 151,
            'historical input count differs')
    check_pins({n: historical_frozen[n] for n in historical_pins['files']}, historical_pins['files'])
    require(set(historical_frozen) == set(historical_pins['files']) | set(task_inputs),
            'historical151 plus six Task37 inventory differs')
    check_pins({n: historical_frozen[n] for n in task_inputs}, task_inputs)
    require(sha(frozen['patches/android/session-cleanup.patch']) == PATCH37, 'Task37 patch differs')
    if check_current:
        check_pins({n: (REPO / name_ok(n)).read_bytes() for n in pins['required_current_repository_files']},
                   pins['required_current_repository_files'])
        registry = [line.split('#', 1)[0].strip() for line in (REPO / 'assets/patches/android.txt').read_text().splitlines()]
        require([n for n in registry if n in pins['required_patch_order']] == pins['required_patch_order'],
                'consumed patch order/membership differs')
    require(sha(files['expected-current167-source-sha256.txt']) == BASE and sha(files['proposed-source-sha256.txt']) == FINAL,
            'full source manifest identity differs')
    current = manifest(files['expected-current167-source-sha256.txt'])
    final = manifest(files['proposed-source-sha256.txt'])
    body_map = unpack(files['composed-source-subset.tar.gz'])
    body_manifest = manifest(files['composed-subset-sha256.txt'])
    require(len(current) == 167 and len(final) == 245 and len(body_map) == 107,
            'reviewed source/body count differs')
    require({n: sha(b) for n, b in body_map.items()} == body_manifest and
            all(final.get(n) == d for n, d in body_manifest.items()), 'materialized source differs')
    plan = json.loads(files['proposed-staging.json'])
    rows = {r['path']: r for r in plan['files']}
    require(len(rows) == len(plan['files']) == 107 and set(rows) == set(body_map), 'stage/body coverage differs')
    live = json.loads(files['live-preflight.json'])
    before = {r['path']: r['expected_sha256'] for r in live['files']}
    require(len(before) == len(live['files']) == 245 and set(before) == set(final), 'live preflight coverage differs')
    require(live['final_manifest_sha256'] == FINAL and
            all(before.get(n) == d for n, d in current.items()), 'current167 not completely retained in preflight')
    counts = Counter()
    for name, row in rows.items():
        expected = before[name]
        require(row['expected_before_staging_sha256'] == expected and row['after_sha256'] == final[name]
                and row['after_bytes'] == len(body_map[name]), 'stage transition differs: ' + name)
        action = 'create-if-absent' if expected is None else 'retain-bound-input' if expected == final[name] else 'replace-if-before-matches'
        require(row['action'] == action, 'incorrect stage action: ' + name)
        counts[action] += 1
    require(dict(counts) == {'create-if-absent': 45, 'replace-if-before-matches': 43, 'retain-bound-input': 19},
            'stage actions differ')
    retained = {n: d for n, d in final.items() if n not in body_map}
    require(len(retained) == 138 and retained == plan['untouched_original_bindings'] and
            all(before[n] == d for n, d in retained.items()), 'unchanged native coverage differs')
    require(sum(d is not None for d in before.values()) == 200, 'existing input count differs')
    task = json.loads(frozen['docs/android/evidence/lw-m7-37/native-source-files.json'])
    require(len(task['files']) == 15 and task['patch_sha256'] == PATCH37, 'Task37 source manifest differs')
    for row in task['files']:
        require(final[row['path']] == row['after_sha256'], 'Task37 output absent or changed')
    old_bodies = unpack(pinned_history(pins, 'historical245_bodies'))
    require(len(old_bodies) == 101 and all(body_map.get(n) == b for n, b in old_bodies.items()),
            'historical245 materialized bodies changed')
    old_final = manifest(pinned_history(pins, 'historical245_manifest'))
    correction = json.loads(parent['process-overlay.json'])
    changed = {row['path']: row for row in correction['files']}
    require(len(changed) == 6 and set(body_map) - set(old_bodies) == set(changed),
            'six corrected process bodies must be the only additions')
    require(set(old_final) == set(final) and {n for n in final if old_final[n] != final[n]} == set(changed),
            'final245 differs outside the six process corrections')
    for name, row in changed.items():
        require(old_final[name] == row['before_sha256'] and final[name] == row['after_sha256']
                and current[name] == before[name] == final[name] and rows[name]['action'] == 'retain-bound-input',
                'process correction is not already present in corrected167: ' + name)
    return {'pins': pins, 'files': files, 'frozen': frozen, 'parent': parent, 'before': before,
            'final': final, 'bodies': body_map, 'rows': rows, 'receipt': receipt,
            'historical_parent': historical_parent, 'historical_frozen': historical_frozen,
            'historical_pins': historical_pins}


def replay(plan):
    with tempfile.TemporaryDirectory(prefix='current245-independent-') as temporary:
        base = Path(temporary)
        repo, parent = base / 'repo', base / 'parent'
        # The unchanged parent wrapper calls git show for its pinned historical
        # snapshot. Give the private replay tree read-only access to local Git
        # objects; all 151 returned bodies are checked against frozen pins.
        subprocess.run(['git', 'clone', '--quiet', '--shared', '--no-checkout', str(REPO), str(repo)],
                       capture_output=True, text=True, check=True)
        populate(repo, plan['frozen'])
        populate(parent, plan['parent'])
        historical = base / 'historical-inputs'
        populate(historical, {n: plan['historical_frozen'][n] for n in plan['historical_pins']['files']})
        historical_parent = base / 'historical-parent'
        populate(historical_parent, plan['historical_parent'])
        historical_result = subprocess.run([sys.executable, str(historical_parent / 'audit.py'), '--repo', str(historical),
                                           '--output', str(base / 'historical-replay')],
                                          capture_output=True, text=True, check=True)
        historical_outputs = {p.name: p.read_bytes() for p in (base / 'historical-replay').iterdir() if p.is_file()}
        require(len(historical_outputs) == 19 and all(plan['historical_parent'].get(n) == b for n, b in historical_outputs.items()),
                'independent historical151 replay differs')
        result = subprocess.run([sys.executable, str(parent / 'compose.py'), '--repo', str(repo), '--output', str(base / 'parent-replay')],
                                capture_output=True, text=True, check=True)
        parent_outputs = {p.name: p.read_bytes() for p in (base / 'parent-replay').iterdir() if p.is_file()}
        require(len(parent_outputs) == 14 and all(plan['parent'].get(n) == b for n, b in parent_outputs.items()), 'independent parent replay differs')
        child_outputs = []
        for index in (1, 2):
            subprocess.run([sys.executable, str(HANDOFF / 'compose.py'), '--repo', str(repo), '--output', str(base / f'child-{index}')],
                           capture_output=True, text=True, check=True)
            output = {p.name: p.read_bytes() for p in (base / f'child-{index}').iterdir() if p.is_file()}
            require(len(output) == 10 and all(plan['files'].get(n) == b for n, b in output.items()), 'independent Task37 replay differs')
            child_outputs.append(output)
        require(child_outputs[0] == child_outputs[1], 'fresh child replays differ')
        return {'historical_output_count': len(historical_outputs), 'historical_input_count': 151,
                'parent_current_input_count': 212, 'parent_output_count': len(parent_outputs), 'child_output_count': len(child_outputs[0]),
                'parent_stdout': result.stdout, 'parent_stderr': result.stderr,
                'historical_stdout': historical_result.stdout, 'historical_stderr': historical_result.stderr,
                'historical_outputs': {n: sha(b) for n, b in sorted(historical_outputs.items())},
                'parent_outputs': {n: sha(b) for n, b in sorted(parent_outputs.items())},
                'child_outputs': {n: sha(b) for n, b in sorted(child_outputs[0].items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    plan = load_plan()
    result = {'actor': '/root/entry_audit', 'status': 'PASS independent local source/plan replay only',
              'scope': 'No guest staging, native build or target execution', 'source_count': 245,
              'existing_checks': 200, 'absence_checks': 45, 'task37_paths': 15,
              'source_manifest_sha256': FINAL, 'handoff_receipt_sha256': plan['pins']['handoff_receipt_sha256'],
              'script_sha256': sha(Path(__file__).read_bytes()), 'replay': replay(plan)}
    path = HERE / 'independent-verification.json'
    if args.record:
        path.write_text(json.dumps(result, indent=2) + '\n')
    else:
        require(json.loads(path.read_bytes()) == result, 'independent receipt differs')
    print('PASS all218 frozen current inputs, historical151 replay, current212 parent replay, full245 coverage and two exact Task37 replays; no guest execution')


if __name__ == '__main__':
    main()
