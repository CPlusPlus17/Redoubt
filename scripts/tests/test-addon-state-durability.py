#!/usr/bin/env python3
"""Replay actual add-on state JavaScript with pinned source; no target-runtime claim."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/android/evidence/lw-m7-19'
PATCH = ROOT / 'patches/android/addon-state-durability.patch'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='verify actual patched source instead of reconstructing baseline')
    parser.add_argument('--apk', type=Path, help='also compare exact packaged production JavaScript')
    args = parser.parse_args()
    entries = json.loads((EVIDENCE / 'source-files.json').read_text())['files']
    originals = {item['path']: item for item in entries if item['before_sha256']}
    with tempfile.TemporaryDirectory(prefix='lw-m7-19-source-') as scratch:
        source = args.source.resolve() if args.source else Path(scratch)
        if not args.source:
            with tarfile.open(EVIDENCE / 'source-baseline.tar.gz') as archive:
                assert {member.name for member in archive} == set(originals)
                for member in archive:
                    assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                    data = archive.extractfile(member).read()
                    assert sha(data) == originals[member.name]['before_sha256']
                    dest = source / member.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
            result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(PATCH)], cwd=source, text=True, capture_output=True, check=True)
            assert 'offset' not in result.stdout and 'fuzz' not in result.stdout, result.stdout
            print('PASS patch applies with zero fuzz and no offsets', flush=True)
        for item in entries:
            data = (source / item['path']).read_bytes()
            assert sha(data) == item['after_sha256'], item['path']
            if item['path'].endswith(('.js', '.mjs')):
                subprocess.run(['node', '--check', str(source / item['path'])], check=True)
        subprocess.run(['node', str(ROOT / 'scripts/tests/test-addon-state-durability.js'), str(source)], check=True, timeout=120)
        if args.apk:
            with zipfile.ZipFile(args.apk) as apk, zipfile.ZipFile(io.BytesIO(apk.read('assets/omni.ja'))) as omni:
                for module in ('AndroidAddonState', 'XPIProvider', 'XPIDatabase', 'XPIInstall'):
                    name = module + '.sys.mjs'
                    assert omni.read('modules/addons/' + name) == (source / 'toolkit/mozapps/extensions/internal' / name).read_bytes(), name
            print('PASS exact APK modules; SHA256=' + sha(args.apk.read_bytes()))
        print('PASS source checks; target compilation, xpcshell and immediate force-stop runtime remain pending')


if __name__ == '__main__':
    main()
