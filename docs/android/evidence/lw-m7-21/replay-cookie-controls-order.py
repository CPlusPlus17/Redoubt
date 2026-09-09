#!/usr/bin/env python3
"""Replay the cookie-control scoped stack, including the later Sync candidate."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
COOKIE = 'patches/android/cookie-banner-controls.patch'
SYNC = 'patches/android/sync-opt-in.patch'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def touched(patch):
    return set(re.findall(r'^\+\+\+ b/(.+)$', (ROOT / patch).read_text(), re.M))

inventory = json.loads((ROOT / 'docs/android/evidence/lw-m7-23/source-files.json').read_text())
paths = {row['path'] for row in inventory['files']}
cookie_paths = touched(COOKIE)
before = {row['path']: row['before_sha256'] for row in inventory['files']}
after = {row['path']: row['after_sha256'] for row in inventory['files']}
sequence = []
for registry in ('common', 'android'):
    sequence.extend(line.split('#')[0].strip() for line in
                    (ROOT / f'assets/patches/{registry}.txt').read_text().splitlines()
                    if line.split('#')[0].strip())
predecessors = [patch for patch in sequence[:sequence.index(COOKIE)]
                if patch != SYNC and touched(patch) & paths]
report = {'patch_sha256': sha(ROOT / COOKIE), 'sync_sha256': sha(ROOT / SYNC),
          'predecessors': {p: sha(ROOT / p) for p in predecessors}, 'pairs': []}

def apply(source, patch, reverse=False):
    command = ['git', 'apply', *['--include=' + path for path in sorted(paths)]]
    if reverse:
        command.append('--reverse')
    result = subprocess.run(command + [str(ROOT / patch)], cwd=source,
                            capture_output=True, text=True)
    return {'patch': patch, 'reverse': reverse, 'exit': result.returncode,
            'output': result.stdout + result.stderr}

def hashes(source):
    return {p: sha(source / p) for p in sorted(paths)}

with tempfile.TemporaryDirectory(prefix='lw21-cookie-order-') as temporary:
    scratch = Path(temporary)
    pristine = scratch / 'pristine'
    pristine.mkdir()
    with tarfile.open(ROOT / 'docs/android/evidence/lw-m7-23/source-baseline.tar.gz') as archive:
        for entry in archive:
            assert entry.isfile() and entry.name in before and not Path(entry.name).is_absolute()
            assert '..' not in Path(entry.name).parts
            target = pristine / entry.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(entry).read())
    assert hashes(pristine) == before
    report['reverse'] = []
    for patch in reversed(predecessors):
        result = apply(pristine, patch, True)
        report['reverse'].append(result)
        assert result['exit'] == 0, result
    normal = scratch / 'normal'
    shutil.copytree(pristine, normal)
    report['forward'] = []
    for patch in predecessors:
        result = apply(normal, patch)
        report['forward'].append(result)
        assert result['exit'] == 0, result
    assert hashes(normal) == before
    for patch in (SYNC, COOKIE):
        result = apply(normal, patch)
        report['forward'].append(result)
        assert result['exit'] == 0, result
    final = hashes(normal)
    changed_by_sync = touched(SYNC) & paths
    assert all(final[p] == after[p] for p in paths - changed_by_sync)
    report['combined_source'] = final
    for predecessor in predecessors + [SYNC]:
        candidate = scratch / Path(predecessor).stem
        shutil.copytree(pristine, candidate)
        order = [p for p in predecessors + [SYNC] if p != predecessor] + [COOKIE, predecessor]
        steps = []
        for patch in order:
            result = apply(candidate, patch)
            steps.append(result)
            if result['exit']:
                break
        report['pairs'].append({
            'predecessor': predecessor,
            'shared_files': sorted(touched(predecessor) & cookie_paths),
            'alternate_steps': steps,
            'alternate_succeeded': all(step['exit'] == 0 for step in steps),
            'identical_final_bytes': hashes(candidate) == final,
        })

(HERE / 'cookie-controls-order.json').write_text(json.dumps(report, indent=2) + '\n')
for row in report['pairs']:
    print(row['predecessor'], 'BOTH ORDERS IDENTICAL' if row['identical_final_bytes']
          else 'KEEP SELECTED ORDER; inspect failed alternate step')
print(f'PASS scoped reconstruction and combined Sync/cookie source: {len(final)} paths')
