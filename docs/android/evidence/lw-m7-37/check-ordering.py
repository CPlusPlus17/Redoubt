#!/usr/bin/env python3
"""Measure the first native increment's complete shared-file pair with Task35."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location('sections', ROOT / 'docs/android/evidence/lw-m7-35/check-ordering.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
sha = lambda data: hashlib.sha256(data).hexdigest()

before_name = 'patches/android/extension-update-controls.patch'
candidate_name = 'patches/android/session-cleanup.patch'
patches = {name: helpers.sections(ROOT / name) for name in (before_name, candidate_name)}
shared = sorted(set(patches[before_name]) & set(patches[candidate_name]))
assert shared == ['mobile/android/geckoview/src/androidTest/assets/web_extensions/test-support/test-api.js',
                  'mobile/android/geckoview/src/androidTest/assets/web_extensions/test-support/test-schema.json']
manifest = json.loads((HERE / 'native-source-files.json').read_text())
expected = {item['path']: item['after_sha256'] for item in manifest['files']}
steps = []
with tempfile.TemporaryDirectory(prefix='lw-m7-37-order-') as scratch:
    scratch = Path(scratch)
    base = scratch / 'base'
    base.mkdir()
    with tarfile.open(HERE / 'native-source-baseline.tar.gz') as archive:
        for name in shared:
            path = base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.extractfile(name).read())

    def apply(tree, name, reverse=False):
        scoped = ''.join(patches[name][path] for path in shared)
        run = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '--reverse' if reverse else '--forward'],
            input=scoped, cwd=tree, text=True, capture_output=True)
        assert 'fuzz' not in run.stdout + run.stderr
        steps.append({'tree': tree.name, 'patch': name, 'reverse': reverse, 'scoped_sha256': sha(scoped.encode()),
                      'exit_code': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr})
        return run.returncode

    assert apply(base, before_name, True) == 0
    canonical = scratch / 'canonical'
    shutil.copytree(base, canonical)
    assert apply(canonical, before_name) == 0
    assert apply(canonical, candidate_name) == 0
    outputs = {name: sha((canonical / name).read_bytes()) for name in shared}
    assert outputs == {name: expected[name] for name in shared}
    inverse = scratch / 'inverse'
    shutil.copytree(base, inverse)
    failed = None
    for name in (candidate_name, before_name):
        if apply(inverse, name):
            failed = name
            break
    if failed:
        verdict = 'predecessor-required'
    else:
        assert outputs == {name: sha((inverse / name).read_bytes()) for name in shared}
        verdict = 'order-free-identical'
receipt = {'script_sha256': sha(Path(__file__).read_bytes()), 'patches': {name: sha((ROOT / name).read_bytes()) for name in patches},
           'shared_paths': shared, 'canonical_after_sha256': outputs,
           'verdict': verdict, 'inverse_failed_at': failed, 'steps': steps}
if '--record' in sys.argv:
    (HERE / 'ordering-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
else:
    assert receipt == json.loads((HERE / 'ordering-receipt.json').read_text())
print(f'PASS Task35/37 complete 2 shared paths: {verdict}; canonical exact hashes, both orders, no fuzz')
