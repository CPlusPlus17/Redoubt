#!/usr/bin/env python3
"""Replay scoped correction and preserve the actual runtime failure boundary."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sha = lambda body: hashlib.sha256(body).hexdigest()

def main():
    old = json.loads((HERE / 'before-source-files.json').read_bytes())
    change = json.loads((HERE / 'source-overlay.json').read_bytes())
    current = json.loads((HERE.parent / 'source-files.json').read_bytes())
    patch = ROOT / 'patches/android/sync-opt-in.patch'
    assert sha(gzip.decompress((HERE / 'before-sync-opt-in.patch.gz').read_bytes())) == old['patch_sha256'] == change['previous_patch_sha256']
    assert sha(patch.read_bytes()) == current['patch_sha256'] == change['patch_sha256']
    before = {r['path']: r for r in old['files']}
    after = {r['path']: r for r in current['files']}
    assert set(before) == set(after)
    changed = {p for p in before if before[p]['after_sha256'] != after[p]['after_sha256']}
    assert len(changed) == 5 and changed == {r['path'] for r in change['files']}
    for row in change['files']:
        name = Path(row['path']).name
        assert sha((HERE / (name + '.before')).read_bytes()) == before[row['path']]['after_sha256'] == row['before_sha256']
        assert sha((HERE / name).read_bytes()) == after[row['path']]['after_sha256'] == row['after_sha256']
    log = gzip.decompress((HERE / change['actual_runtime_log']['path']).read_bytes())
    assert sha(log) == change['actual_runtime_log']['sha256']
    for marker in [b'zygoteTab_disable_art_image_', b'ContextImpl.getSharedPreferences', b'UserManager.isUserUnlockingOrUnlocked', b'FenixApplication.attachBaseContext']:
        assert marker in log
    assert sum(r['authored_tests'] for r in current['files']) == 34
    with tempfile.TemporaryDirectory(prefix='lw20-isolated-gnu-') as tmp:
        destination = Path(tmp)
        with tarfile.open(HERE.parent / 'scoped-pristine.tar.gz', 'r:gz') as stream:
            for member in stream.getmembers():
                assert member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts
                body = stream.extractfile(member).read()
                assert sha(body) == current['scoped_pristine_files'][member.name]
                path = destination / member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
        for pred in current['scoped_predecessors']:
            subprocess.run(['git', 'apply', *['--include=' + p for p in after], str(ROOT / pred['path'])], cwd=destination, check=True, capture_output=True)
        result = subprocess.run(['patch', '-p1', '--batch', '--fuzz=0', '--input', str(patch)], cwd=destination, capture_output=True, text=True)
        assert result.returncode == 0 and not re.search(r'offset|fuzz|FAILED|Reversed', result.stdout + result.stderr), result.stdout + result.stderr
        for path, row in after.items():
            assert sha((destination / path).read_bytes()) == row['after_sha256'], path
        print(result.stdout.rstrip())
    subprocess.run(['python3', str(HERE.parent / 'check-source.py')], cwd=ROOT, check=True)
    print('PASS: five scoped corrections, preserved runtime crash and 24 exact GNU/Git source outputs. 34 Kotlin tests authored; target unrun.')

if __name__ == '__main__':
    main()
