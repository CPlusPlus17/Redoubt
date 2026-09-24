#!/usr/bin/env python3
"""Replay the exact home patch and both orders of its shared FML dependency."""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
FML = 'mobile/android/fenix/app/nimbus.fml.yaml'

def apply(source, path, reverse=False):
    args = ['patch', '--batch', '--fuzz=0', '-p1', '-i', str(path)]
    if reverse:
        args.append('--reverse')
    result = subprocess.run(args, cwd=source, capture_output=True, text=True)
    result.check_returncode()
    return result.stdout + result.stderr

def sha(data):
    return hashlib.sha256(data).hexdigest()

inventory = json.loads((EVIDENCE / 'source-files.json').read_text())
patch = ROOT / 'patches/android/home-section-defaults.patch'
assert sha(patch.read_bytes()) == inventory['patch_sha256']
results = {}
with tempfile.TemporaryDirectory(prefix='lw-m7-24-') as scratch:
    scratch = Path(scratch)
    base = scratch / 'base'
    base.mkdir()
    with tarfile.open(EVIDENCE / 'source-baseline.tar.gz') as archive:
        assert archive.getnames() == [FML]
        data = archive.extractfile(FML).read()
        assert sha(data) == inventory['files'][0]['before_sha256']
        original = base / FML
        original.parent.mkdir(parents=True)
        original.write_bytes(data)
    results['current-sequence'] = apply(base, patch)
    assert 'offset' not in results['current-sequence'] and 'fuzz' not in results['current-sequence']
    for row in inventory['files']:
        assert sha((base / row['path']).read_bytes()) == row['after_sha256']
    no_nimbus = (ROOT / 'patches/android/no-nimbus.patch').read_text()
    start = no_nimbus.index('--- a/' + FML + '\n')
    end = no_nimbus.find('\n--- a/', start + 1)
    shared = scratch / 'no-nimbus-fml.patch'
    shared.write_text(no_nimbus[start:] if end < 0 else no_nimbus[start:end] + '\n')
    predecessor = scratch / 'predecessor'
    (predecessor / FML).parent.mkdir(parents=True)
    (predecessor / FML).write_bytes(data)
    results['reconstruct-before-no-nimbus'] = apply(predecessor, shared, reverse=True)
    before_no_nimbus = (predecessor / FML).read_bytes()
    for name, order in [('nimbus-then-home', [shared, patch]), ('home-then-nimbus', [patch, shared])]:
        source = scratch / name
        (source / FML).parent.mkdir(parents=True)
        (source / FML).write_bytes(before_no_nimbus)
        results[name] = ''.join(apply(source, item) for item in order)
        assert sha((source / FML).read_bytes()) == inventory['files'][0]['after_sha256']
    # Check all channels, including nested channel overrides.
    manifest = yaml.safe_load((base / FML).read_text())
    home = manifest['features']['homescreen']
    for channel in manifest['channels']:
        values = dict(home['variables']['sections-enabled']['default'])
        for override in home.get('defaults', []):
            if override.get('channel') == channel:
                values.update(override['value'].get('sections-enabled', {}))
        assert all(values[key] is False for key in ('top-sites','jump-back-in','bookmarks','recent-explorations'))
    results['channels'] = manifest['channels']
print(json.dumps(results, indent=2))
print('PASS source replay and all-channel home defaults; target tests and UI remain pending')
