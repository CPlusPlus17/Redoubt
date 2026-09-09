#!/usr/bin/env python3
"""Replay retained scoped source. No target compilation or execution is implied."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def manifest():
    return json.loads((HERE / 'source-files.json').read_text())


def extract(destination, data):
    archive = (HERE / 'scoped-pristine.tar.gz').read_bytes()
    require(digest(archive) == data['scoped_pristine_archive_sha256'], 'pristine archive changed')
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as retained:
        members = retained.getmembers()
        require(len(members) == len(data['scoped_pristine_files']), 'archive count differs')
        require({item.name for item in members} == set(data['scoped_pristine_files']), 'archive inventory differs')
        for item in members:
            require(item.isfile() and not item.name.startswith('/') and '..' not in Path(item.name).parts, 'invalid member')
            content = retained.extractfile(item).read()
            require(digest(content) == data['scoped_pristine_files'][item.name], 'pristine hash differs: ' + item.name)
            path = destination / item.name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def apply(destination, path, paths=None, check=False):
    args = ['git', 'apply', '--whitespace=error-all']
    if check:
        args.append('--check')
    if paths is not None:
        args += ['--include=' + path for path in paths]
    return subprocess.run([*args, str(ROOT / path)], cwd=destination, check=True, capture_output=True, text=True)


def replay(destination):
    data = manifest()
    paths = [item['path'] for item in data['files']]
    patch = 'patches/android/global-privacy-controls.patch'
    require(digest((ROOT / patch).read_bytes()) == data['patch_sha256'], 'candidate patch changed')
    touched = re.findall(r'^\+\+\+ b/(.+)$', (ROOT / patch).read_text(), re.M)
    require(len(touched) == len(set(touched)) and set(touched) == set(paths), 'patch scope differs')
    task = next(item for item in yaml.safe_load((ROOT / 'docs/android/tasks.yaml').read_text())['tasks'] if item['id'] == 'LW-M7-36')
    require(set(task['tree_paths']) == set(paths), 'task scope differs')
    extract(destination, data)
    for predecessor in data['scoped_predecessors']:
        require(digest((ROOT / predecessor['path']).read_bytes()) == predecessor['sha256'], 'predecessor changed: ' + predecessor['path'])
        apply(destination, predecessor['path'], paths)
    for item in data['files']:
        target = destination / item['path']
        require((digest(target.read_bytes()) if target.exists() else None) == item['before_sha256'], 'before hash differs: ' + item['path'])
    apply(destination, patch, check=True)
    apply(destination, patch)
    require({str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()} == set(paths), 'replay output differs')
    for item in data['files']:
        content = (destination / item['path']).read_bytes()
        require(digest(content) == item['after_sha256'], 'after hash differs: ' + item['path'])
        if 'authored_tests' in item:
            pattern = r'@Test\b' if item['path'].endswith('.kt') else r'^add_task\('
            require(len(re.findall(pattern, content.decode(), re.M)) == item['authored_tests'], 'test inventory differs')
    return data


def verify_originals():
    pins = json.loads((HERE / 'inspected-source-pins.json').read_text())
    for name, pin in pins.items():
        require(digest((HERE / name).read_bytes()) == (pin if isinstance(pin, str) else pin['excerpt_sha256']), 'inspected evidence changed: ' + name)
    old = json.loads((HERE / 'original-audit/source-inputs.json').read_text())
    archive = (HERE / 'original-audit/source-inputs.tar.gz').read_bytes()
    require(digest(archive) == old['archive_sha256'], 'original source archive hash differs')
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as retained:
        files = {item.name: item for item in retained.getmembers() if item.isfile()}
        require(set(files) == {item['archive_path'] for item in old['files']}, 'original source inventory differs')
        for item in old['files']:
            content = retained.extractfile(files[item['archive_path']]).read()
            require(len(content) == item['size'] and digest(content) == item['sha256'], 'original source pin differs')


def main():
    verify_originals()
    with tempfile.TemporaryDirectory(prefix='lw-m7-36-replay-') as directory:
        data = replay(Path(directory))
    print(f"SOURCE REPLAY PASS: {len(data['scoped_predecessors'])} scoped predecessors; {len(data['files'])} patch files match before/after pins; 38 original audit inputs verified.")
    for suffix, label in [('.kt', 'KOTLIN'), ('.js', 'XPCSHELL')]:
        count = sum(item.get('authored_tests', 0) for item in data['files'] if item['path'].endswith(suffix))
        print(f'AUTHORED {label} TESTS: {count}; NOT EXECUTED by this replay.')
    print('TARGET COMPILATION / API GENERATION / APK RUNTIME: NOT RUN.')


if __name__ == '__main__':
    main()
