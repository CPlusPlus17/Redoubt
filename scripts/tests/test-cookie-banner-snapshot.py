#!/usr/bin/env python3
"""Offline source-loader and packaging checks; never claims native banner rejection."""
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
EVIDENCE = ROOT / 'docs/android/evidence/lw-m7-13'
PATCH = ROOT / 'patches/android/cookie-banner-rules.patch'
SNAPSHOT = 'services/settings/dumps/main/cookie-banner-rules-list.json'
SERVICE = 'toolkit/components/cookiebanners/CookieBannerListService.sys.mjs'
EXPECTED_HASH = '0ddab9560f17710fa1613825b1b8be0e190107dd679e2cd53c5a1822524958fd'
EXPECTED_SIZE = 262208


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_snapshot(data):
    assert len(data) == EXPECTED_SIZE, 'snapshot byte count changed'
    assert digest(data) == EXPECTED_HASH, 'snapshot SHA256 changed'
    parsed = json.loads(data)
    assert parsed['timestamp'] == 1725526980846
    assert len(parsed['data']) == 558
    assert len({item['id'] for item in parsed['data']}) == 558
    assert sum(len(item['domains']) for item in parsed['data']) == 1601
    assert sum(not item['domains'] for item in parsed['data']) == 9
    assert any(item['id'] == 'disabled' for item in parsed['data'])



def build_manifest(source, app):
    # Evaluate the actual moz.build file with only its build-output DSL faked.
    class Output:
        def __init__(self):
            self.values = []
            self.children = {}

        def __getattr__(self, name):
            return self.children.setdefault(name, Output())

        def __getitem__(self, name):
            return self.children.setdefault(name, Output())

        def __setitem__(self, name, value):
            self.children[name] = value

        def __iadd__(self, values):
            self.values.extend(values)
            return self

        def flatten(self, prefix=''):
            result = [(prefix, value) for value in self.values]
            for name, child in self.children.items():
                result.extend(child.flatten(prefix + '/' + name))
            return result

    output = Output()
    exec(compile(source, 'services/settings/dumps/main/moz.build', 'exec'), {
        'CONFIG': {'MOZ_BUILD_APP': app}, 'FINAL_TARGET_FILES': output,
    })
    return sorted(output.flatten())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Validate this patched source tree instead of reconstructing the archive')
    parser.add_argument('--apk', type=Path, help='Also verify the packaged module, schema and snapshot in this APK')
    args = parser.parse_args()
    inventory = json.loads((EVIDENCE / 'source-files.json').read_text())['files']
    paths = {item['path']: item for item in inventory}
    with tempfile.TemporaryDirectory(prefix='lw-m7-13-verify-') as scratch:
        source = args.source.resolve() if args.source else Path(scratch)
        if not args.source:
            with tarfile.open(EVIDENCE / 'source-baseline.tar.gz') as archive:
                members = archive.getmembers()
                assert {member.name for member in members} == set(paths)
                for member in members:
                    assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                    data = archive.extractfile(member).read()
                    assert digest(data) == paths[member.name]['before_sha256']
                    dest = source / member.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
            result = subprocess.run(
                ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(PATCH)],
                cwd=source, capture_output=True, text=True, check=True,
            )
            assert 'offset' not in result.stdout and 'fuzz' not in result.stdout
            print('PASS patch applies with fuzz=0 and no offsets', flush=True)
        for name, item in paths.items():
            assert digest((source / name).read_bytes()) == item['after_sha256'], name + ' source differs'
        check_snapshot((source / SNAPSHOT).read_bytes())
        mozbuild = 'services/settings/dumps/main/moz.build'
        with tarfile.open(EVIDENCE / 'source-baseline.tar.gz') as archive:
            original_build = archive.extractfile(mozbuild).read().decode()
        patched_build = (source / mozbuild).read_text()
        for app in ('browser', 'mobile/ios'):
            assert build_manifest(original_build, app) == build_manifest(patched_build, app), app + ' packaging changed'
        before_android = build_manifest(original_build, 'mobile/android')
        after_android = build_manifest(patched_build, 'mobile/android')
        added = ('/defaults/settings/main', 'cookie-banner-rules-list.json')
        assert after_android == sorted(before_android + [added]), 'Android packaging must add exactly the rules dump'
        print('PASS actual moz.build adds exactly one Android snapshot and preserves desktop/iOS outputs', flush=True)
        print('PASS pinned snapshot: 262208 bytes, 558 unique IDs, 1601 domains, 9 global rules', flush=True)
        subprocess.run(['node', '--check', str(source / SERVICE)], check=True)
        subprocess.run(['node', '--check', str(source / 'toolkit/components/cookiebanners/test/unit/test_cookiebannerlistservice.js')], check=True)
        subprocess.run(['node', str(ROOT / 'scripts/tests/test-cookie-banner-rules.js'), str(source)], check=True)
        if args.apk:
            with zipfile.ZipFile(args.apk) as apk:
                with zipfile.ZipFile(io.BytesIO(apk.read('assets/omni.ja'))) as omni:
                    check_snapshot(omni.read('defaults/settings/main/cookie-banner-rules-list.json'))
                    assert digest(omni.read('modules/CookieBannerListService.sys.mjs')) == paths[SERVICE]['after_sha256']
                    schema = 'toolkit/components/cookiebanners/schema/CookieBannerRule.schema.json'
                    assert digest(omni.read('chrome/toolkit/content/global/cookiebanners/CookieBannerRule.schema.json')) == paths[schema]['after_sha256']
            print('PASS APK packaged snapshot/module/schema; APK SHA256=' + digest(args.apk.read_bytes()))
        print('PASS source validation; Gecko build, xpcshell and actual banner-rejection runtime remain separate gates')


if __name__ == '__main__':
    main()
