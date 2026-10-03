#!/usr/bin/env python3
"""Replay a 157.0 source receipt written by recapture.py.

The receipt for patches/android/<stem>.patch is <stem>.json plus
<stem>-before.tar.gz. This script checks the pinned patch and archive digests,
rebuilds the before tree, checks every before hash (including "absent"),
applies the patch with --fuzz=0, and requires no offset, no fuzz and every
pinned after hash.

It uses only repository files. It does not compile anything and does not run
any target, native or Android test.

    python3 docs/android/evidence/lw-m7-01/release-157.0/receipts/replay.py <stem>...
"""
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def receipt(stem):
    return json.loads((HERE / f'{stem}.json').read_text())


def replay(stem, dest):
    """Rebuild the before tree in dest, apply the patch, verify. Returns the receipt."""
    data = receipt(stem)
    version = (ROOT / 'version.android').read_text().strip()
    assert data['firefox_version'] == version, \
        f"receipt is for {data['firefox_version']}, version.android is {version}"
    patch = ROOT / data['patch']
    assert sha(patch.read_bytes()) == data['patch_sha256'], f"{data['patch']} changed since its {version} receipt"
    archive = (HERE / data['before_archive']).read_bytes()
    assert sha(archive) == data['before_archive_sha256'], f"{data['before_archive']} changed"
    files = {item['path']: item for item in data['files']}
    present = {p for p, item in files.items() if item['before_sha256'] is not None}
    dest = Path(dest)
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        names = set()
        for member in tar:
            assert member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts, member.name
            names.add(member.name)
            body = tar.extractfile(member).read()
            assert sha(body) == files[member.name]['before_sha256'], f'before hash differs: {member.name}'
            out = dest / member.name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(body)
    assert names == present, 'before archive inventory differs from the receipt'
    for p in files:
        if p not in present:
            assert not (dest / p).exists(), f'{p} must be absent before the patch'
    result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)],
                            cwd=dest, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert 'offset' not in out and 'fuzz' not in out, out
    for p, item in files.items():
        f = dest / p
        got = sha(f.read_bytes()) if f.is_file() else None
        assert got == item['after_sha256'], f'after hash differs: {p}'
    return data


def main(stems):
    for stem in stems:
        with tempfile.TemporaryDirectory(prefix=f'lw-receipt-{stem}-') as scratch:
            data = replay(stem, scratch)
        n_before = sum(1 for f in data['files'] if f['before_sha256'] is not None)
        print(f"PASS {data['patch']}: {data['firefox_version']} receipt; {n_before}/{len(data['files'])} "
              f"before files, exact --fuzz=0 replay, all after hashes")
    print('NOT RUN: compilation, native/xpcshell/GeckoView/Kotlin tests, APK behaviour.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['addon-state-durability', 'extension-permission-durability', 'extension-update-controls',
                              'global-privacy-controls', 'session-cleanup', 'translation-assets']))
