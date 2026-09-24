#!/usr/bin/env python3
"""Replay corrected20 ->26 and verify the combined actual167 overlay; no target run."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sha = lambda body: hashlib.sha256(body).hexdigest()

def unpack(raw):
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as stream:
        members = stream.getmembers()
        assert len({m.name for m in members}) == len(members)
        assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
        return {m.name: stream.extractfile(m).read() for m in members}

def main():
    previous = json.loads((HERE / 'before-source-files.json').read_bytes())
    current = json.loads((HERE.parent / 'source-files.json').read_bytes())
    change = json.loads((HERE / 'source-overlay.json').read_bytes())
    combined = json.loads((HERE / 'current167-overlay.json').read_bytes())
    patch = ROOT / 'patches/android/firefox-suggest-policy.patch'
    assert sha(gzip.decompress((HERE / 'before-firefox-suggest-policy.patch.gz').read_bytes())) == previous['patch_sha256'] == change['previous_patch_sha256']
    assert sha(patch.read_bytes()) == current['patch_sha256'] == change['patch_sha256'] == combined['patch26_sha256']
    assert sha((ROOT / 'patches/android/sync-opt-in.patch').read_bytes()) == change['predecessor20_sha256'] == combined['patch20_sha256']
    old = {r['path']: r for r in previous['files']}
    new = {r['path']: r for r in current['files']}
    assert set(old) == set(new)
    assert {p for p in old if old[p]['after_sha256'] != new[p]['after_sha256']} == {r['path'] for r in change['files']}
    assert len(change['files']) == 3
    assert {p for p in old if old[p]['before_sha256'] != new[p]['before_sha256']} == set(change['changed_predecessor_bodies'])
    for row in change['files']:
        name = Path(row['path']).name
        assert sha((HERE / (name + '.before')).read_bytes()) == old[row['path']]['after_sha256'] == row['before_sha256']
        assert sha((HERE / name).read_bytes()) == new[row['path']]['after_sha256'] == row['after_sha256']
    with tempfile.TemporaryDirectory(prefix='lw26-isolated-gnu-') as tmp:
        destination = Path(tmp)
        for name, body in unpack((HERE.parent / 'scoped-pristine.tar.gz').read_bytes()).items():
            assert sha(body) == current['scoped_pristine_files'][name]
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        for pred in current['scoped_predecessors']:
            assert sha((ROOT / pred['path']).read_bytes()) == pred['sha256']
            subprocess.run(['git', 'apply', *['--include=' + p for p in new], str(ROOT / pred['path'])], cwd=destination, check=True, capture_output=True)
        result = subprocess.run(['patch', '-p1', '--batch', '--fuzz=0', '--input', str(patch)], cwd=destination, capture_output=True, text=True)
        assert result.returncode == 0 and not re.search(r'offset|fuzz|FAILED|Reversed', result.stdout + result.stderr), result.stdout + result.stderr
        for name, row in new.items():
            assert sha((destination / name).read_bytes()) == row['after_sha256'], name
        print(result.stdout.rstrip())
    before_raw = (HERE / 'actual-expanded-source-before.tar.gz').read_bytes()
    assert sha(before_raw) == combined['before_archive_sha256']
    actual = unpack(before_raw)
    policy = 'mobile/android/fenix/app/src/test/java/org/mozilla/fenix/settings/search/FirefoxSuggestPolicyTest.kt'
    actual[policy] = (HERE / 'actual-FirefoxSuggestPolicyTest.kt.before').read_bytes()
    assert sha(actual[policy]) == combined['policy_test_before_sha256']
    raw = (HERE / 'current167-source-overlay.tar.gz').read_bytes()
    assert sha(raw) == combined['overlay_archive_sha256']
    overlay = unpack(raw)
    manifest = (HERE / 'actual-current167-source-sha256.txt').read_bytes()
    assert sha(manifest) == combined['previous_source_sha256']
    pins = {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in manifest.decode().splitlines()}
    assert len(combined['files']) == len(overlay) == 6 and len(pins) == 167
    assert set(overlay) == {r['path'] for r in combined['files']}
    scoped20 = json.loads((ROOT / 'docs/android/evidence/lw-m7-20/source-files.json').read_bytes())
    final = {r['path']: r['after_sha256'] for r in scoped20['files']}
    final.update({r['path']: r['after_sha256'] for r in current['files']})
    for row in combined['files']:
        name = row['path']
        assert sha(actual[name]) == pins[name] == row['before_sha256'], name
        assert sha(overlay[name]) == final[name] == row['after_sha256'], name
        pins[name] = row['after_sha256']
    derived = ''.join(f'{h}  {p}\n' for p, h in sorted(pins.items())).encode()
    assert derived == (HERE / 'proposed-current167-source-sha256.txt').read_bytes()
    assert sha(derived) == combined['proposed_source_sha256']
    for task in ['20', '26']:
        subprocess.run(['python3', str(ROOT / f'docs/android/evidence/lw-m7-{task}/check-source.py')], cwd=ROOT, check=True)
    print('PASS: 21 scoped26 outputs and six actual167 replacements verified; 161 existing bindings unchanged. Target compilation/tests/runtime UNRUN.')

if __name__ == '__main__':
    main()
