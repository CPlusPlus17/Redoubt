#!/usr/bin/env python3
"""Apply the reviewed feature increment to the isolated guest's old candidate."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

WORK = Path('/home/runner/work/feature-parity-20260908')
REPO, SOURCE = WORK / 'repo', WORK / 'src'
EVIDENCE = WORK / 'evidence/extended-source'
PLAN = Path(__file__).with_name('input-plan.json')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def check(expected, label):
    rows = [{'path': path, 'expected': digest, 'actual': sha(SOURCE / path)}
            for path, digest in expected.items()]
    (EVIDENCE / (label + '.json')).write_text(json.dumps(rows, indent=2) + '\n')
    wrong = [row for row in rows if row['expected'] != row['actual']]
    if wrong:
        raise RuntimeError(f'{label}: {len(wrong)} source mismatches: {wrong}')
    print(f'{label}: {len(rows)} source hashes match', flush=True)

assert subprocess.check_output(['id', '-un'], text=True).strip() == 'runner'
assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm'
EVIDENCE.mkdir(parents=True, exist_ok=False)
plan = json.loads(PLAN.read_text())
(EVIDENCE / 'input-plan.json').write_bytes(PLAN.read_bytes())
check(plan['initial'], 'initial-compiled-candidate')
paths = sorted({item['path'] for stage in plan['stages'] for item in stage['files']})
with tarfile.open(EVIDENCE / 'before-source.tar.gz', 'w:gz') as archive:
    for path in paths:
        if (SOURCE / path).exists():
            archive.add(SOURCE / path, arcname=path, recursive=False)
final = dict(plan['initial'])
for index, stage in enumerate(plan['stages'], 1):
    patch = REPO / stage['patch']
    assert sha(patch) == stage['sha256'], f'Patch changed: {patch}'
    check({row['path']:row['before_sha256'] for row in stage['files']}, f'{index}-before')
    for dry in (True, False):
        command = ['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch)]
        if dry:
            command.append('--dry-run')
        result = subprocess.run(command, cwd=SOURCE, stdin=subprocess.DEVNULL,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (EVIDENCE / f'{index}-patch-{"dry" if dry else "apply"}.log').write_text(result.stdout)
        result.check_returncode()
    after = {row['path']:row['after_sha256'] for row in stage['files']}
    check(after, f'{index}-after')
    final.update(after)
for item in plan['assets']:
    assert sha(REPO / item['input']) == item['sha256']
result = subprocess.run(['python3', str(REPO / 'scripts/package-translation-assets.py'),
                         '--asset-dir', str(SOURCE / 'toolkit/components/translations/android-data')],
                        capture_output=True, text=True)
(EVIDENCE / 'translation-staging.log').write_text(result.stdout + result.stderr)
result.check_returncode()
final.update({item['path']:item['sha256'] for item in plan['assets']})
check(final, 'final')
(EVIDENCE / 'source-sha256.txt').write_text(''.join(f'{digest}  {path}\n' for path, digest in sorted(final.items())))
print(f'Applied and verified {len(final)} source/asset inputs; no compilation claimed.', flush=True)
