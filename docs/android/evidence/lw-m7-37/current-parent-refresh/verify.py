#!/usr/bin/env python3
"""Independently verify the captured archive and old/current bodies on the host."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sha = lambda body: hashlib.sha256(body).hexdigest()


def archive_bodies(path):
    bodies = {}
    with tarfile.open(path) as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            assert member.isfile() and not name.is_absolute() and '..' not in name.parts
            assert member.name not in bodies
            bodies[member.name] = archive.extractfile(member).read()
    return bodies


def verify():
    request = json.loads((HERE / 'request.json').read_text())
    plan_body = (HERE / 'plan-source-inputs.json').read_bytes()
    plan = json.loads(plan_body)
    assert sha(plan_body) == request['plan_sha256'] == 'ee18a23ecf25ceff7356730fb3024bfc95de72030d968cf763dbd879d6bcc769'
    assert plan_body == (HERE.parent / 'next-work-plan/source-inputs.json').read_bytes()
    candidate_body = (HERE / 'candidate245-source-sha256.txt').read_bytes()
    assert sha(candidate_body) == request['candidate245_manifest_sha256'] == plan['candidate245_manifest_sha256']
    candidate = dict((n, h) for h, n in [line.split('  ', 1) for line in candidate_body.decode().splitlines()])
    assert len(candidate) == 245 and len(plan['sources']) == 56
    selected = [r for r in plan['sources'] if r['path'] not in candidate]
    assert len(selected) == 30 and request['files'] == selected
    assert all(row['candidate245_sha256'] is None for row in selected)
    capture_code = (HERE / 'capture.py').read_bytes()
    tree = ast.parse(capture_code)
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == 'REQUEST')
    assert json.loads(ast.literal_eval(assignment.value.args[0])) == request
    command = json.loads((HERE / 'capture-command.json').read_text())
    assert command['stdin_script_sha256'] == sha(capture_code) and command['returncode'] == 0
    assert command['command'] == ['scripts/ci-vm/ssh.sh', 'sudo -iu runner python3 -']
    assert command['stderr_sha256'] == sha((HERE / 'capture-stderr.txt').read_bytes()) == sha(b'')
    archive_path = HERE / 'guest-source.tar.gz'
    body = archive_path.read_bytes()
    assert sha(body) == command['stdout_sha256'] and len(body) == command['stdout_bytes']
    bodies = archive_bodies(archive_path)
    expected = {'source/' + r['path'] for r in selected} | {'capture-result.json', 'parent-source-sha256.txt'}
    assert set(bodies) == expected and len(bodies) == 32
    result = json.loads(bodies['capture-result.json'])
    assert result['status'] == 'READ_ONLY_CAPTURE_VERIFIED'
    assert result['source_root'] == request['source_root'] and result['parent_manifest_path'] == request['parent_manifest_path']
    assert result['plan_sha256'] == request['plan_sha256']
    assert result['candidate245_manifest_sha256'] == request['candidate245_manifest_sha256']
    assert set(result['archive_members']) == set(bodies) - {'capture-result.json'}
    for name, row in result['archive_members'].items():
        assert row == {'sha256':sha(bodies[name]), 'bytes':len(bodies[name])}
    parent_body = bodies['parent-source-sha256.txt']
    assert sha(parent_body) == request['parent_manifest_sha256'] == result['parent_manifest_sha256_before'] == result['parent_manifest_sha256_after']
    parent = dict((n, h) for h, n in [line.split('  ', 1) for line in parent_body.decode().splitlines()])
    assert len(parent) == request['parent_manifest_count'] == result['parent_manifest_count'] == 167
    assert not (set(parent) & {r['path'] for r in selected})
    old_archives = {}
    plan_inputs = {r['path']:r for r in plan['inputs']}
    for row in selected:
        name = row['archive']
        if name not in old_archives:
            original = (ROOT / name).read_bytes()
            assert sha(original) == plan_inputs[name]['sha256'] and len(original) == plan_inputs[name]['bytes']
            old_archives[name] = archive_bodies(ROOT / name)
    assert len(result['files']) == 30
    comparisons = []
    for old, captured in zip(selected, result['files']):
        assert {key:captured[key] for key in old} == old
        old_body = old_archives[old['archive']][old['member']]
        assert sha(old_body) == old['sha256'] and len(old_body) == old['bytes']
        current_body = bodies['source/' + old['path']]
        current = {'sha256':sha(current_body), 'bytes':len(current_body)}
        assert current == captured['current_before'] == captured['current_after']
        comparison = 'same' if current_body == old_body else 'different'
        assert comparison == captured['comparison_to_plan']
        comparisons.append({'path':old['path'], 'old_source_kind':old['source_kind'], 'old_sha256':old['sha256'],
                            'current_sha256':current['sha256'], 'bytes':current['bytes'], 'comparison':comparison})
    return {'schema':1, 'status':'HOST_ARCHIVE_VERIFIED', 'scope':'Current-parent source evidence only; no implementation or target acceptance.',
            'guest_archive_sha256':sha(body), 'archive_members':len(bodies), 'captured_source_count':30,
            'captured_source_bytes':sum(r['bytes'] for r in comparisons),
            'parent_manifest_sha256':sha(parent_body), 'parent_manifest_count':len(parent),
            'comparison_counts':dict(Counter(r['comparison'] for r in comparisons)), 'sources':comparisons,
            'old_archives_verified':sorted(old_archives),
            'remaining167_source_bodies_rehashed':False,
            'source_hashes_unchanged_during_capture':True, 'parent_manifest_unchanged_during_capture':True}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
