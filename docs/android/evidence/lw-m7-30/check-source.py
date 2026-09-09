#!/usr/bin/env python3
"""Check shortcut source and resolve its compiled APK resource with aapt2."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PACKAGE = 'org.redoubtbrowser'
RESOURCE = 'raw/initial_shortcuts'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_source(manifest):
    patch = ROOT / 'patches/android/no-default-shortcuts.patch'
    require(sha(patch.read_bytes()) == manifest['patch_sha256'], 'patch hash mismatch')
    require(sha((HERE / 'source-baseline.tar.gz').read_bytes()) == manifest['archive_sha256'],
            'baseline archive hash mismatch')
    with tempfile.TemporaryDirectory(prefix='lw30-shortcuts-') as temporary:
        folder = Path(temporary)
        with tarfile.open(HERE / 'source-baseline.tar.gz') as archive:
            for member in archive:
                require(member.isfile() and member.name in manifest['archived_inputs'],
                        'unexpected archived source')
                require(not Path(member.name).is_absolute() and '..' not in Path(member.name).parts,
                        'unsafe archived source path')
                data = archive.extractfile(member).read()
                require(sha(data) == manifest['archived_inputs'][member.name], 'source hash mismatch')
                dest = folder / member.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
        for dry in (True, False):
            command = ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)]
            if dry:
                command.append('--dry-run')
            result = subprocess.run(command, cwd=folder, check=True, capture_output=True, text=True)
            require('offset' not in result.stdout and 'fuzz' not in result.stdout,
                    'patch applied with offset/fuzz')
        resource = (folder / manifest['path']).read_bytes()
        require(sha(resource) == manifest['after_sha256'] and json.loads(resource) == {'data': []},
                'source resource bytes/schema mismatch')


def resolve_resource(dump):
    """Read aapt2's actual entry, never search ZIP contents by equal hash.

    Only direct file values are supported. An alias or unknown dump format fails
    closed until reviewed. Every configuration must contain the same input.
    """
    package = None
    packages = []
    entries = []
    current = None
    for line in dump.splitlines():
        match = re.fullmatch(r'Package name=(\S+) id=([0-9a-fA-F]+)', line)
        if match:
            package = match.group(1)
            current = None
            if package == PACKAGE:
                packages.append(int(match.group(2), 16))
            continue
        match = re.fullmatch(r'    resource (0x[0-9a-fA-F]{8}) (\S+)(?: .*)?', line)
        if match:
            current = None
            if package == PACKAGE and match.group(2) == RESOURCE:
                current = {'id': match.group(1), 'values': []}
                entries.append(current)
            continue
        if line.startswith('  type '):
            current = None
        if current is not None:
            current['values'].append(line)
    require(len(packages) == 1, 'expected exactly one resource package ' + PACKAGE)
    require(len(entries) == 1, 'expected exactly one resource entry ' + RESOURCE)
    entry = entries[0]
    require(int(entry['id'], 16) >> 24 == packages[0], 'resource/package ID mismatch')
    mappings = []
    configs = set()
    for line in entry['values']:
        match = re.fullmatch(r'      \(([^()]*)\) \(file\) (\S+)(?: type=\S+)?', line)
        require(match is not None, 'unrecognized or non-file shortcut resource value: ' + repr(line))
        config, member = match.group(1, 2)
        require(config not in configs, 'duplicate resource configuration')
        configs.add(config)
        parts = PurePosixPath(member).parts
        require(member.startswith('res/') and '\\' not in member and '\x00' not in member
                and not any(part in ('', '.', '..') for part in member.split('/'))
                and len(parts) >= 2, 'unsafe resource ZIP path')
        mappings.append({'configuration': config, 'member': member})
    require('' in configs, 'shortcut resource has no default file value')
    return {'package': PACKAGE, 'resource': RESOURCE, 'id': entry['id'], 'mappings': mappings}


def check_packaged_bytes(apk, resolution, expected_hash):
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        require(names.count('resources.arsc') == 1, 'missing or duplicate APK resource table')
        values = []
        for mapping in resolution['mappings']:
            member = mapping['member']
            require(names.count(member) == 1, 'missing or duplicate mapped ZIP member: ' + member)
            resource = archive.read(member)
            require(sha(resource) == expected_hash and json.loads(resource) == {'data': []},
                    'mapped shortcut bytes/schema mismatch: ' + member)
            values.append({**mapping, 'sha256': sha(resource), 'size': len(resource)})
        return {**resolution, 'mappings': values,
                'resource_table_sha256': sha(archive.read('resources.arsc'))}


def check_apk(apk, aapt2, expected_hash):
    # Both commands inspect the same candidate; detect concurrent replacement.
    before = sha(apk.read_bytes())
    tool_before = sha(aapt2.read_bytes())
    version = subprocess.run([str(aapt2), 'version'], check=True, capture_output=True, text=True,
                             timeout=30)
    result = subprocess.run([str(aapt2), 'dump', 'resources', str(apk)], check=True,
                            capture_output=True, text=True, timeout=120)
    require(not result.stderr.strip(), 'aapt2 resource dump emitted diagnostics: ' + result.stderr)
    receipt = check_packaged_bytes(apk, resolve_resource(result.stdout), expected_hash)
    require(sha(apk.read_bytes()) == before, 'APK changed during inspection')
    require(sha(aapt2.read_bytes()) == tool_before, 'aapt2 changed during inspection')
    return {**receipt, 'apk_sha256': before, 'apk_size': apk.stat().st_size,
            'aapt2_sha256': tool_before, 'aapt2_version': (version.stdout + version.stderr).strip(),
            'resource_dump_sha256': sha(result.stdout.encode()),
            'runtime_status': 'NOT TESTED; fresh/upgrade/manual-add controls remain pending'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path)
    parser.add_argument('--aapt2', type=Path, help='build aapt2 executable; otherwise use PATH')
    args = parser.parse_args()
    try:
        manifest = json.loads((HERE / 'source-files.json').read_text())
        check_source(manifest)
        print('PASS source resource hash/schema and zero-fuzz/offset patch replay', flush=True)
        if args.apk:
            tool = args.aapt2 or shutil.which('aapt2')
            require(tool is not None, '--apk requires --aapt2 or aapt2 on PATH')
            receipt = check_apk(args.apk.resolve(), Path(tool).resolve(), manifest['after_sha256'])
            print('PASS exact packaged shortcut input resolved through APK resource table')
            print(json.dumps(receipt, sort_keys=True))
        else:
            require(args.aapt2 is None, '--aapt2 requires --apk')
            print('APK RESOURCE: NOT CHECKED; provide --apk and --aapt2 with the compiled candidate')
        print('HOME/BOOKMARK RUNTIME: NOT TESTED; fresh/upgrade/manual-add controls remain pending')
        return 0
    except (ValueError, OSError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print('FAIL shortcut resource verification: ' + str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
