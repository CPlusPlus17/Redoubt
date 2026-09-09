#!/usr/bin/env python3
"""Stage the reviewed Fenix-only shortcut resource after the native build ends."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
from datetime import datetime, timezone


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def query(command):
    return subprocess.check_output(command, text=True, timeout=30).strip()


def manifest(path):
    rows = {}
    for line in path.read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'invalid digest')
        require(name not in rows and not Path(name).is_absolute() and '..' not in Path(name).parts, 'invalid source path')
        rows[name] = digest
    require(rows, 'empty source manifest')
    return rows


def main():
    require(query(['systemd-detect-virt', '--vm']) == 'kvm', 'requires the CI guest')
    require(pwd.getpwuid(os.getuid()).pw_name == 'runner', 'requires the guest runner')
    work = Path('/home/runner/work/feature-parity-20260908')
    repo, source = work/'repo', work/'src'
    os.chdir(repo)
    os.environ['XDG_RUNTIME_DIR'] = '/run/user/' + str(os.getuid())
    require(not query(['podman', '--remote=false', 'ps', '--format', '{{.Names}}']), 'another container is active')
    native = work/'evidence/parity-extended-native'
    require((native/'build-exit.txt').read_text().strip() == '0' and (native/'finished.txt').is_file(), 'native build is not successfully terminal')
    before = manifest(native/'source-sha256.txt')
    require(all(sha(source/name) == digest for name, digest in before.items()), 'native source binding changed')
    pin_path = repo/'docs/android/evidence/lw-m7-30/source-files.json'
    pin = json.loads(pin_path.read_text())
    patch = repo/'patches/android/no-default-shortcuts.patch'
    require(sha(patch) == pin['patch_sha256'], 'shortcut patch changed')
    name = pin['path']
    require(name == 'mobile/android/fenix/app/src/main/res/raw/initial_shortcuts.json', 'unexpected resource path')
    target = source/name
    require(name not in before, 'resource is already part of the native source contract; review staging')
    after = dict(before, **{name: pin['after_sha256']})
    evidence = work/'evidence/apk-resource-source'
    aar_inputs = {str(work/'aar'/abi/'target.maven.zip'): sha(work/'aar'/abi/'target.maven.zip')
                  for abi in ['armeabi-v7a', 'arm64-v8a', 'x86_64']}
    binding = {'native_manifest_sha256': sha(native/'source-sha256.txt'),
               'resource_pin_sha256': sha(pin_path), 'patch_sha256': sha(patch),
               'native_inputs': aar_inputs, 'resource': name,
               'before_sha256': pin['before_sha256'], 'after_sha256': pin['after_sha256']}
    if evidence.exists():
        receipt = json.loads((evidence/'receipt.json').read_text())
        require(receipt['status'] == 'PASS' and receipt['binding'] == binding, 'existing staging receipt does not match')
        require(manifest(evidence/'source-sha256.txt') == after and sha(target) == pin['after_sha256'], 'staged source no longer matches')
        print('PASS verified existing resource stage; native inputs unchanged')
        return
    require(sha(target) == pin['before_sha256'], 'unexpected shortcut resource baseline')
    evidence.mkdir()
    (evidence/'initial_shortcuts.before.json').write_bytes(target.read_bytes())
    command = ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)]
    for label, args in [('dry-run', ['--dry-run']), ('apply', [])]:
        result = subprocess.run(command+args, cwd=source, text=True, capture_output=True, timeout=30)
        (evidence/(label+'.txt')).write_text(result.stdout+result.stderr)
        require(result.returncode == 0 and 'offset' not in result.stdout and 'fuzz' not in result.stdout, 'resource patch did not apply exactly')
    require(sha(target) == pin['after_sha256'] and json.loads(target.read_text()) == {'data': []}, 'resource result differs')
    require(all(sha(source/path) == digest for path, digest in before.items()), 'native source changed while staging')
    require(all(sha(Path(path)) == digest for path, digest in aar_inputs.items()), 'native archive changed while staging')
    (evidence/'source-sha256.txt').write_text(''.join(digest+'  '+path+'\n' for path, digest in sorted(after.items())))
    receipt = {'status': 'PASS', 'scope': 'Fenix resource staging only; APK and behavior NOT RUN',
               'finished': datetime.now(timezone.utc).isoformat(), 'binding': binding,
               'source_count': len(after), 'source_manifest_sha256': sha(evidence/'source-sha256.txt')}
    (evidence/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'PASS staged empty shortcut resource; {len(after)} source bindings, native inputs unchanged')


if __name__ == '__main__':
    main()
