#!/usr/bin/env python3
"""Compose reviewed policy patches against an archived, verified guest baseline."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
STAGES = [('20', 'sync-opt-in'), ('23', 'cookie-banner-controls'), ('26', 'firefox-suggest-policy')]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read(path):
    return path.read_bytes() if path.is_file() else None

def sha(path):
    value = read(path)
    return digest(value) if value is not None else None

def apply(folder, patch, path=None, reverse=False):
    command = ['git', 'apply', '--whitespace=error-all']
    if path:
        command.append('--include=' + path)
    if reverse:
        command.append('--reverse')
    result = subprocess.run(command + [str(patch)], cwd=folder, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)

with tarfile.open(HERE / 'guest-before-source.tar.gz') as archive:
    baseline = json.load(archive.extractfile('before-hashes.json'))
    parent_manifest = archive.extractfile('parent-source-sha256.txt').read().decode()
    source = {member.name.removeprefix('source/'): archive.extractfile(member).read()
              for member in archive if member.isfile() and member.name.startswith('source/')}
assert all((digest(source[p]) if p in source else None) == expected for p, expected in baseline.items())
plan = {'requires_terminal_service': 'redoubt-parity-native3-20260909.service',
        'parent_manifest': 'evidence/followup-source/source-sha256.txt',
        'guest_archive_sha256': digest((HERE / 'guest-before-source.tar.gz').read_bytes()),
        'base_mozconfig_sha256': digest((ROOT / 'assets/mozconfig.android').read_bytes()),
        'stages': []}
final = {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in parent_manifest.splitlines()}
with tempfile.TemporaryDirectory(prefix='lw21-policy-source-') as temporary:
    folder = Path(temporary) / 'source'
    folder.mkdir()
    for path, data in source.items():
        assert '..' not in Path(path).parts and not Path(path).is_absolute()
        dest = folder / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    readiness = ROOT / 'patches/android/ubo-readiness.patch'
    previous = [(readiness, set(re.findall(r'^\+\+\+ b/(.+)$', readiness.read_text(), re.M)))]
    plan['preexisting_composition_patches'] = {str(readiness.relative_to(ROOT)): digest(readiness.read_bytes())}
    for task, name in STAGES:
        patch = ROOT / f'patches/android/{name}.patch'
        inventory = json.loads((ROOT / f'docs/android/evidence/lw-m7-{task}/source-files.json').read_text())
        touched = set(re.findall(r'^\+\+\+ b/(.+)$', patch.read_text(), re.M))
        assert touched <= baseline.keys(), sorted(touched - baseline.keys())
        before = {p: read(folder / p) for p in touched}
        rows = {r['path']: r for r in inventory['files']}
        assert touched <= rows.keys()
        composition = {}
        for path in touched:
            if sha(folder / path) == rows[path]['before_sha256']:
                continue
            # Later author baselines can include some preceding candidates but
            # omit others. Undo only the extra intersecting candidates until the
            # author's exact per-file baseline is recovered, then replay them.
            check = Path(temporary) / 'check'
            if check.exists():
                shutil.rmtree(check)
            (check / path).parent.mkdir(parents=True, exist_ok=True)
            if before[path] is not None:
                (check / path).write_bytes(before[path])
            undone = []
            for earlier, earlier_paths in reversed(previous):
                if path not in earlier_paths:
                    continue
                apply(check, earlier, path, True)
                undone.append(earlier)
                if sha(check / path) == rows[path]['before_sha256']:
                    break
            assert sha(check / path) == rows[path]['before_sha256'], ('unaccounted baseline drift', name, path)
            apply(check, patch, path)
            assert sha(check / path) == rows[path]['after_sha256'], ('isolated after mismatch', name, path)
            for earlier in reversed(undone):
                apply(check, earlier, path)
            composition[path] = {'extra_predecessors': [str(p.relative_to(ROOT)) for p in undone],
                                 'expected_combined_sha256': sha(check / path)}
        apply(folder, patch)
        files = []
        delta = []
        for path in sorted(touched):
            after = read(folder / path)
            expected = composition.get(path, {}).get('expected_combined_sha256', rows[path]['after_sha256'])
            assert sha(folder / path) == expected, ('after mismatch', name, path)
            files.append({'path': path, 'before_sha256': digest(before[path]) if before[path] is not None else None,
                          'after_sha256': expected})
            delta.extend(difflib.unified_diff(
                before[path].decode().splitlines(keepends=True) if before[path] is not None else [],
                after.decode().splitlines(keepends=True),
                fromfile='a/' + path if before[path] is not None else '/dev/null', tofile='b/' + path))
            final[path] = expected
        delta_name = f'{task}-{name}-guest.patch'
        (HERE / delta_name).write_text(''.join(delta))
        plan['stages'].append({'task': task, 'patch': str(patch.relative_to(ROOT)),
                               'patch_sha256': digest(patch.read_bytes()), 'guest_patch': delta_name,
                               'guest_patch_sha256': digest((HERE / delta_name).read_bytes()),
                               'composition': composition, 'files': files})
        previous.append((patch, touched))
    for path in baseline:
        if path not in final and (folder / path).is_file():
            final[path] = sha(folder / path)
    plan['final_source'] = final
(HERE / 'input-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
print(f'PASS composed {len(STAGES)} policy candidates; {len(final)} final source/asset hashes')
