#!/usr/bin/env python3
"""Retain the successfully terminal native4 checkpoint before later builds."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
import zipfile

WORK = Path('/home/runner/work/feature-parity-20260908')
INVOCATION = '367f4a0c473843b4832ee42f0c9e2ff2'
MANIFEST = '4756b69d2f016997221f44c31a8213535a01b68e44e467b7ee5987d209e345c2'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def query(args):
    return subprocess.check_output(args, text=True, timeout=30).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit', default='redoubt-parity-native4-20260909.service')
    parser.add_argument('--invocation', default=INVOCATION)
    parser.add_argument('--started', default='2026-09-09T00:53:49+00:00')
    args = parser.parse_args()
    require(query(['systemd-detect-virt', '--vm']) == 'kvm', 'requires KVM guest')
    require(pwd.getpwuid(os.getuid()).pw_name == 'runner', 'requires guest runner')
    os.environ['XDG_RUNTIME_DIR'] = '/run/user/' + str(os.getuid())
    os.chdir(WORK/'repo')
    service = query(['systemctl', '--user', 'show', args.unit,
                     '-p', 'LoadState', '-p', 'ActiveState', '-p', 'SubState', '-p', 'ExecMainStatus',
                     '-p', 'InvocationID', '-p', 'ExecMainStartTimestamp',
                     '-p', 'ExecMainExitTimestamp'])
    state = dict(line.split('=', 1) for line in service.splitlines())
    require(state['ActiveState'] == 'inactive', 'native service is still active or failed')
    # systemd collects successful transient units. Bind the previously observed
    # invocation as well as the driver timestamps, exact manifest and ABI logs.
    observed = (WORK/'evidence/native4-checkpoint/initial-service.txt').read_text()
    require('InvocationID=' + args.invocation in observed, 'initial invocation differs')
    if state['LoadState'] != 'not-found':
        require(state['InvocationID'] == args.invocation and state['ExecMainStatus'] == '0',
                'native invocation or service exit differs')
    require(not query(['podman', '--remote=false', 'ps', '--format', '{{.Names}}']),
            'another container is active')
    native = WORK/'evidence/parity-extended-native'
    require((native/'build-exit.txt').read_text().strip() == '0' and
            (native/'finished.txt').is_file(), 'native driver did not finish successfully')
    require((native/'started.txt').read_text().strip() == args.started,
            'native driver start changed')
    require(sha(native/'source-sha256.txt') == MANIFEST, 'wrong native source manifest')
    rows = (native/'source-sha256.txt').read_text().splitlines()
    require(len(rows) == 164, 'unexpected source count')
    for row in rows:
        digest, name = row.split('  ', 1)
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'unsafe source path')
        require(sha(WORK/'src'/name) == digest, 'source changed: ' + name)
    destination = WORK/'evidence/native4-terminal'
    destination.mkdir()
    shutil.copytree(native, destination/'driver')
    (destination/'service.txt').write_text(service + '\n')
    (destination/'initial-service.txt').write_text(observed)
    (destination/'memory-events.txt').write_text(Path('/sys/fs/cgroup/user.slice/user-1001.slice/memory.events').read_text())
    (destination/'memory.txt').write_text(query(['free', '-b']) + '\n')
    (destination/'journal.txt').write_text(query(['journalctl', '--user', '--no-pager',
                                                '-u', args.unit]) + '\n')
    artifacts = WORK/'native4-artifacts'
    artifacts.mkdir()
    results = {}
    for abi in ['armeabi-v7a', 'arm64-v8a', 'x86_64']:
        log = WORK/'aar/logs'/f'{abi}.log'
        require('MACH_EXIT=0' in log.read_text(), 'missing actual successful mach exit: ' + abi)
        shutil.copy2(log, destination/f'{abi}.log')
        original = WORK/'aar'/abi/'target.maven.zip'
        retained = artifacts/abi/'target.maven.zip'
        retained.parent.mkdir()
        shutil.copy2(original, retained)
        digest = sha(original)
        require(sha(retained) == digest, 'artifact copy changed')
        with zipfile.ZipFile(original) as outer:
            aars = [name for name in outer.namelist() if name.endswith('.aar')]
            require(len(aars) == 1, 'unexpected Maven AAR count')
            with outer.open(aars[0]) as stream, zipfile.ZipFile(stream) as aar:
                jni = sorted(name for name in aar.namelist() if name.startswith('jni/') and name.endswith('.so'))
                require(jni and {name.split('/')[1] for name in jni} == {abi}, 'wrong packaged ABI')
        results[abi] = {'sha256': digest, 'bytes': original.stat().st_size,
                        'retained': str(retained), 'aar': aars[0], 'jni': jni,
                        'log_sha256': sha(log)}
        profile = WORK/'src'/f'obj-{abi}'/'build_resources.json'
        if profile.is_file():
            shutil.copy2(profile, destination/f'{abi}-build-resources.json')
        profiles = sorted((WORK/'src'/f'obj-{abi}'/'.mozbuild/logs/build').glob('profile_log_*.json'))
        if profiles:
            shutil.copy2(profiles[-1], destination/f'{abi}-{profiles[-1].name}')
    for path in ['assets/mozconfig.android', 'scripts/android-fat-aar.sh',
                 'docs/android/evidence/lw-m7-25/podman-native-bounded.sh',
                 'docs/android/evidence/lw-m7-12/run-extended-native.sh']:
        output = destination/'configuration'/path
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WORK/'repo'/path, output)
    fat_log = WORK/'aar/logs/fat.log'
    require('MACH_EXIT=0' in fat_log.read_text(), 'merge did not finish successfully')
    shutil.copy2(fat_log, destination/'fat.log')
    shutil.copy2(WORK/'aar/build-times.txt', destination/'build-times.txt')
    merged = list((WORK/'aar').glob('geckoview-*.aar'))
    require(len(merged) == 1, 'unexpected merged AAR count')
    with zipfile.ZipFile(merged[0]) as aar:
        jni = sorted(name for name in aar.namelist() if name.startswith('jni/') and name.endswith('.so'))
        require({name.split('/')[1] for name in jni} == set(results), 'merged ABI set differs')
    retained = artifacts/merged[0].name
    shutil.copy2(merged[0], retained)
    require(sha(retained) == sha(merged[0]), 'merged artifact copy changed')
    merged_result = {'sha256': sha(retained), 'bytes': retained.stat().st_size,
                     'retained': str(retained), 'jni': jni, 'log_sha256': sha(fat_log)}
    receipt = {'status': 'PASS', 'scope': 'Three native ABI builds and Maven packaging only; APK/tests/runtime pending',
               'invocation': args.invocation, 'source_manifest_sha256': MANIFEST, 'source_count': len(rows),
               'artifacts': results, 'merged': merged_result,
               'captured': datetime.now(timezone.utc).isoformat()}
    if (native/'compilation-parent.json').is_file():
        receipt['compilation_parent'] = json.loads((native/'compilation-parent.json').read_text())
        receipt['scope'] = 'Three source-bound ABI compilations across retained parent/recovery and successful merge; APK/tests/runtime pending'
    (destination/'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    archive = WORK/'evidence/native4-terminal.tar.gz'
    require(not archive.exists(), 'capture archive already exists')
    with tarfile.open(archive, 'w:gz') as retained:
        retained.add(destination, arcname=destination.name)
    print(json.dumps({'archive': str(archive), 'sha256': sha(archive), 'result': receipt}, indent=2))


if __name__ == '__main__':
    main()
