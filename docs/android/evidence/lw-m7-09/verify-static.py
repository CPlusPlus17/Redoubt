#!/usr/bin/env python3
"""Replay patch/source integrity and resource/catalog checks; does not compile Kotlin."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PATCH = REPO / 'patches/android/privacy-defaults.patch'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    inventory = json.loads((HERE / 'source-files.json').read_text())
    paths = {item['path']: item for item in inventory['files']}
    with tempfile.TemporaryDirectory(prefix='lw-m7-09-static-') as directory:
        source = Path(directory)
        with tarfile.open(HERE / 'before-source.tar.gz') as archive:
            members = archive.getmembers()
            assert {m.name for m in members} == {
                name for name, item in paths.items() if item['before_sha256']
            }
            for member in members:
                assert member.isfile() and not Path(member.name).is_absolute()
                assert '..' not in Path(member.name).parts
                data = archive.extractfile(member).read()
                assert sha(data) == paths[member.name]['before_sha256'], member.name
                destination = source / member.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
        apply = subprocess.run(
            ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(PATCH)],
            cwd=source, capture_output=True, text=True, check=True,
        )
        assert 'offset' not in apply.stdout and 'fuzz' not in apply.stdout
        for name, item in paths.items():
            assert sha((source / name).read_bytes()) == item['after_sha256'], name
        xml_defaults = {}
        android = '{http://schemas.android.com/apk/res/android}'
        for name in paths:
            if name.endswith('.xml'):
                tree = ET.parse(source / name)
                xml_defaults[Path(name).name] = {
                    element.attrib[android + 'key']: element.attrib[android + 'defaultValue']
                    for element in tree.iter()
                    if android + 'key' in element.attrib and android + 'defaultValue' in element.attrib
                }
        settings = (source / 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt').read_text()
        constants = dict(re.findall(r'internal const val (LIBREWOLF_DOH_\w+) = "([^"]+)"', settings))
        provider = (source / 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/doh/DohSettingsProvider.kt').read_text()
        for name, value in constants.items():
            provider = provider.replace('Settings.' + name, json.dumps(value))
        android_providers = re.findall(r'"([^"]+)" to "([^"]+)"', provider)
        desktop = (REPO / 'settings/common.cfg').read_text()
        catalog = json.loads(re.search(r'"doh-rollout.provider-list",\s*`(.*?)`', desktop, re.S).group(1))
        assert android_providers == [(item['UIName'], item['uri']) for item in catalog]
        board = subprocess.run(
            ['python3', 'docs/android/board.py', '--check'],
            cwd=REPO, capture_output=True, text=True, check=True,
        )
        print(json.dumps({
            'result': 'PASS_STATIC_ONLY',
            'command': 'python3 docs/android/evidence/lw-m7-09/verify-static.py',
            'patch_sha256': sha(PATCH.read_bytes()),
            'before_archive_sha256': sha((HERE / 'before-source.tar.gz').read_bytes()),
            'source_inventory_sha256': sha((HERE / 'source-files.json').read_bytes()),
            'patched_files': len(paths),
            'patch_application': 'all files apply with fuzz=0 and no offsets; every result matches after SHA256',
            'xml_defaults': xml_defaults,
            'doh_catalog': 'all seven ordered names and URIs match settings/common.cfg',
            'board': board.stdout.strip(),
            'kotlin_compilation': 'NOT RUN by this static verifier',
            'device_runtime': 'NOT RUN by this static verifier',
        }, indent=2))


if __name__ == '__main__':
    main()
