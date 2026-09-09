#!/usr/bin/env python3
"""Check the actual default shortcut input and optionally its compiled APK resource."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import tarfile
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

def sha(data):
    return hashlib.sha256(data).hexdigest()

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apk', type=Path)
args = parser.parse_args()
manifest = json.loads((HERE / 'source-files.json').read_text())
patch = ROOT / 'patches/android/no-default-shortcuts.patch'
assert sha(patch.read_bytes()) == manifest['patch_sha256']
assert sha((HERE / 'source-baseline.tar.gz').read_bytes()) == manifest['archive_sha256']
with tempfile.TemporaryDirectory(prefix='lw30-shortcuts-') as temporary:
    folder = Path(temporary)
    with tarfile.open(HERE / 'source-baseline.tar.gz') as archive:
        for member in archive:
            assert member.isfile() and member.name in manifest['archived_inputs']
            assert not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
            data = archive.extractfile(member).read()
            assert sha(data) == manifest['archived_inputs'][member.name]
            dest = folder / member.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
    for dry in (True, False):
        command = ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)]
        if dry:
            command.append('--dry-run')
        result = subprocess.run(command, cwd=folder, check=True, capture_output=True, text=True)
        assert 'offset' not in result.stdout and 'fuzz' not in result.stdout
    result = (folder / manifest['path']).read_bytes()
    assert sha(result) == manifest['after_sha256'] and json.loads(result) == {'data': []}
    print('PASS source resource hash/schema and zero-fuzz/offset patch replay')
if args.apk:
    with zipfile.ZipFile(args.apk) as archive:
        resource = archive.read('res/raw/initial_shortcuts.json')
    assert sha(resource) == manifest['after_sha256'] and json.loads(resource) == {'data': []}
    print('PASS exact packaged shortcut input; APK SHA256 ' + sha(args.apk.read_bytes()))
else:
    print('APK RESOURCE: NOT CHECKED; provide --apk with the compiled candidate')
print('HOME/BOOKMARK RUNTIME: NOT TESTED; fresh/upgrade/manual-add controls remain pending')
