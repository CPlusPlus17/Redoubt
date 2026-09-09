#!/usr/bin/env python3
"""Replay pinned Task35 source checks; Android/native target execution is separate."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import tomllib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/android/evidence/lw-m7-35'
PATCH = ROOT / 'patches/android/extension-update-controls.patch'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='verify supplied patched source instead of reconstructing')
    args = parser.parse_args()
    manifest = json.loads((EVIDENCE / 'source-files.json').read_text())
    assert sha(PATCH.read_bytes()) == manifest['patch_sha256'], 'patch changed since source receipt'
    assert sha((EVIDENCE / 'guest-source.tar.gz').read_bytes()) == manifest['guest_capture_sha256']
    assert sha((EVIDENCE / 'source-baseline.tar.gz').read_bytes()) == manifest['baseline_archive_sha256']
    assert sha((ROOT / manifest['predecessor_patch']).read_bytes()) == manifest['predecessor_patch_sha256']
    originals = {item['path']: item for item in manifest['files'] if item['before_sha256']}
    # Independently reconstruct the post-31 before bytes from root's guest
    # receipt, so the second archive is not its own only provenance authority.
    with tempfile.TemporaryDirectory(prefix='lw-m7-35-predecessor-') as scratch:
        tree = Path(scratch)
        with tarfile.open(EVIDENCE / 'guest-source.tar.gz') as archive:
            for member in archive:
                if not member.isfile() or not member.name.startswith('source/'):
                    continue
                name = member.name.removeprefix('source/')
                assert name in originals and '..' not in Path(name).parts
                dest = tree / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.extractfile(member).read())
        chosen = set(manifest['predecessor_applied_paths'])
        parts = (ROOT / manifest['predecessor_patch']).read_text().split('--- a/')
        selected = ''.join('--- a/' + part for part in parts[1:] if part.splitlines()[0] in chosen)
        selected_patch = tree / 'predecessor.patch'
        selected_patch.write_text(selected)
        result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(selected_patch)], cwd=tree, capture_output=True, text=True, check=True)
        assert 'offset' not in result.stdout and 'fuzz' not in result.stdout, result.stdout
        for name, item in originals.items():
            assert sha((tree / name).read_bytes()) == item['before_sha256'], name
        print('PASS original captured guest + exact scoped Task31 hunks equal all17 before hashes', flush=True)
    with tempfile.TemporaryDirectory(prefix='lw-m7-35-source-') as scratch:
        source = args.source.resolve() if args.source else Path(scratch)
        if not args.source:
            with tarfile.open(EVIDENCE / 'source-baseline.tar.gz') as archive:
                assert {member.name for member in archive} == set(originals)
                for member in archive:
                    assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                    data = archive.extractfile(member).read()
                    assert sha(data) == originals[member.name]['before_sha256'], member.name
                    dest = source / member.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
            result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(PATCH)], cwd=source, capture_output=True, text=True, check=True)
            assert 'offset' not in result.stdout and 'fuzz' not in result.stdout, result.stdout
            print('PASS exact captured guest+Task31 baseline; patch applies without offsets or fuzz', flush=True)
        for item in manifest['files']:
            path = source / item['path']
            assert sha(path.read_bytes()) == item['after_sha256'], item['path']
            if path.suffix in ('.js', '.mjs'):
                subprocess.run(['node', '--check', str(path)], check=True)
            if path.suffix == '.toml':
                tomllib.loads(path.read_text())
            if path.suffix == '.xml':
                ET.parse(path)
        prefs = (source / 'modules/libpref/Preferences.cpp').read_text()
        assert 'sPendingWriteData' not in prefs
        assert 'new PWRunnable(aFile, std::move(prefs), std::move(aPromiseHolder))' in prefs
        assert 'return async ? NS_OK : writer->Result();' in prefs
        assert 'writer->Cancel(rv);' in prefs and 'mCounted.exchange(false)' in prefs
        assert 'mPromiseHolder->RejectIfExists(result, __func__);' in prefs
        libpref = tomllib.loads((source / 'modules/libpref/test/unit/xpcshell.toml').read_text())
        assert libpref['test_savePrefFileAsync.js']['prefs'] == ['preferences.allow.omt-write=true']
        extension_tests = tomllib.loads((source / 'toolkit/components/extensions/test/xpcshell/xpcshell.toml').read_text())
        assert extension_tests['test_ext_android_update_settings.js']['run-if'] == ["os == 'android'"]
        print('PASS source hashes, JavaScript syntax, XML/TOML and native test registration (not C++ compilation)', flush=True)
        subprocess.run(['node', str(ROOT / 'scripts/tests/test-extension-update-controls.js'), str(source)], check=True, timeout=120)
    print('PENDING target C++/Java/Kotlin compilation, native/Kotlin tests, APK restart/network/signed-update acceptance')


if __name__ == '__main__':
    main()
