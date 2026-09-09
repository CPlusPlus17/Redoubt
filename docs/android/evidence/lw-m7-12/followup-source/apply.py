#!/usr/bin/env python3
"""Apply reviewed followup sources only after the current native job is terminal."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

WORK = Path('/home/runner/work/feature-parity-20260908')
REPO, SOURCE = WORK / 'repo', WORK / 'src'
EVIDENCE = WORK / 'evidence/followup-source'
PLAN = Path(__file__).with_name('input-plan.json')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def check(values, label):
    rows = [{'path': path, 'expected': expected, 'actual': sha(SOURCE / path)}
            for path, expected in values.items()]
    (EVIDENCE / (label + '.json')).write_text(json.dumps(rows, indent=2) + '\n')
    assert all(row['expected'] == row['actual'] for row in rows), label
    print(f'PASS {label}: {len(rows)} source/asset hashes', flush=True)

assert subprocess.check_output(['id', '-un'], text=True).strip() == 'runner'
assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm'
os.chdir(REPO)
plan = json.loads(PLAN.read_text())
env = dict(os.environ, XDG_RUNTIME_DIR='/run/user/1001')
state = subprocess.check_output(['systemctl', '--user', 'show',
    plan['requires_inactive_native_service'], '-p', 'ActiveState', '--value'], env=env, text=True).strip()
assert state == 'inactive', f'Native build is still active: {state}'
interrupted = WORK / plan['interrupted_native_evidence']
assert (interrupted / 'classification.txt').read_text().startswith('INTERRUPTED: controlled VM shutdown')
assert (interrupted / 'captured.txt').is_file()
assert (interrupted / 'new-boot-id.txt').read_text().strip() == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert (interrupted / 'native-attempt-2/boot-id.txt').read_text().strip() != (interrupted / 'new-boot-id.txt').read_text().strip()
assert not subprocess.check_output(['podman', 'ps', '-q'], text=True).strip(), 'A build container is active'
EVIDENCE.mkdir(exist_ok=False)
(EVIDENCE / 'input-plan.json').write_bytes(PLAN.read_bytes())
parent = WORK / plan['parent_manifest']
final = {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in parent.read_text().splitlines()}
check(final, 'parent-source')
paths = sorted({row['path'] for stage in plan['stages'] for row in stage['files']})
with tarfile.open(EVIDENCE / 'before-source.tar.gz', 'w:gz') as archive:
    for path in paths:
        if (SOURCE / path).is_file():
            archive.add(SOURCE / path, arcname=path, recursive=False)
for index, stage in enumerate(plan['stages'], 1):
    patch = REPO / stage['patch']
    assert sha(patch) == stage['sha256']
    check({row['path']: row['before_sha256'] for row in stage['files']}, f'{index}-before')
    for dry in (True, False):
        args = ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)]
        if dry:
            args.append('--dry-run')
        result = subprocess.run(args, cwd=SOURCE, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True)
        (EVIDENCE / f'{index}-{"dry" if dry else "apply"}.log').write_text(result.stdout + result.stderr)
        result.check_returncode()
        assert 'offset' not in result.stdout and 'fuzz' not in result.stdout
    after = {row['path']: row['after_sha256'] for row in stage['files']}
    check(after, f'{index}-after')
    final.update(after)
check(final, 'final-source')
(EVIDENCE / 'source-sha256.txt').write_text(''.join(f'{digest}  {path}\n' for path, digest in sorted(final.items())))
print('Source changes applied; native packaging, target tests and APK behavior require new runs', flush=True)
