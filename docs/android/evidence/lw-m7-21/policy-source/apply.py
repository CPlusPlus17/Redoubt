#!/usr/bin/env python3
"""Apply the reviewed policy composition only after the archived native failure."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

WORK = Path('/home/runner/work/feature-parity-20260908')
REPO, SOURCE = WORK / 'repo', WORK / 'src'
HERE = Path(__file__).resolve().parent
EVIDENCE = WORK / 'evidence/policy-source'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def check(values, label):
    rows = [{'path': path, 'expected': expected, 'actual': sha(SOURCE / path)}
            for path, expected in sorted(values.items())]
    (EVIDENCE / (label + '.json')).write_text(json.dumps(rows, indent=2) + '\n')
    assert all(row['actual'] == row['expected'] for row in rows), label
    print(f'PASS {label}: {len(rows)} source/asset hashes', flush=True)

assert subprocess.check_output(['id', '-un'], text=True).strip() == 'runner'
assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm'
os.chdir(REPO)
env = dict(os.environ, XDG_RUNTIME_DIR='/run/user/1001')
plan = json.loads((HERE / 'input-plan.json').read_text())
state = subprocess.check_output(['systemctl', '--user', 'show', plan['requires_terminal_service'],
    '-p', 'ActiveState', '--value'], env=env, text=True).strip()
assert state in ('failed', 'inactive'), state
assert not subprocess.check_output(['podman', 'ps', '-q'], text=True).strip()
failed = WORK / 'evidence/parity-extended-native'
assert (failed / 'build-exit.txt').read_text().strip() == '1'
assert (failed / 'finished.txt').read_text().strip() == '2026-09-09T00:29:30+00:00'
assert sha(REPO / 'assets/mozconfig.android') == plan['base_mozconfig_sha256']
assert sha(HERE / 'guest-before-source.tar.gz') == plan['guest_archive_sha256']
EVIDENCE.mkdir(exist_ok=False)
(EVIDENCE / 'input-plan.json').write_bytes((HERE / 'input-plan.json').read_bytes())
parent = {line.split('  ', 1)[1]: line.split('  ', 1)[0]
          for line in (WORK / plan['parent_manifest']).read_text().splitlines()}
check(parent, 'parent-source')
with tarfile.open(EVIDENCE / 'before-source.tar.gz', 'w:gz') as archive:
    for path in sorted({row['path'] for stage in plan['stages'] for row in stage['files']}):
        if (SOURCE / path).is_file():
            archive.add(SOURCE / path, arcname=path, recursive=False)
for stage in plan['stages']:
    task = stage['task']
    assert sha(REPO / stage['patch']) == stage['patch_sha256']
    patch = HERE / stage['guest_patch']
    assert sha(patch) == stage['guest_patch_sha256']
    check({r['path']: r['before_sha256'] for r in stage['files']}, task + '-before')
    for dry in (True, False):
        args = ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)]
        if dry:
            args.append('--dry-run')
        result = subprocess.run(args, cwd=SOURCE, stdin=subprocess.DEVNULL, capture_output=True, text=True)
        output = result.stdout + result.stderr
        (EVIDENCE / f'{task}-{"dry" if dry else "apply"}.log').write_text(output)
        result.check_returncode()
        assert 'offset' not in output and 'fuzz' not in output
    check({r['path']: r['after_sha256'] for r in stage['files']}, task + '-after')
check(plan['final_source'], 'final-source')
(EVIDENCE / 'source-sha256.txt').write_text(''.join(
    f'{digest}  {path}\n' for path, digest in sorted(plan['final_source'].items())))
print('Source applied; native/Fenix compilation, target tests and APK behavior remain pending', flush=True)
