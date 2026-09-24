"""Read-only capture of successful APK compilation and failed resource verification."""
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

work = Path('/home/runner/work/feature-parity-20260908')
os.environ['XDG_RUNTIME_DIR'] = '/run/user/1001'
assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm'
assert not subprocess.check_output(['podman', '--remote=false', 'ps', '-q'], text=True).strip()
evidence = work/'evidence/parity-extended-apk'
assert (evidence/'build-exit.txt').read_text().strip() == '0'
assert not (evidence/'finished.txt').exists()
sha = lambda data: hashlib.sha256(data).hexdigest()
rows = dict((name, digest) for digest, name in
            (line.split('  ', 1) for line in (evidence/'source-sha256.txt').read_text().splitlines()))
assert len(rows) == 165
for name, digest in rows.items():
    assert sha((work/'src'/name).read_bytes()) == digest, name
capture = {}
for folder in ['parity-extended-apk', 'apk-bundle-recovery-checkpoint',
               'apk-resource-source', 'apk-admission-copy-source',
               'apk-search-context-source', 'apk-permission-bundle-source']:
    for path in (work/'evidence'/folder).iterdir():
        if path.is_file():
            capture[folder+'/'+path.name] = path.read_bytes()
capture['logs/apk.log'] = (work/'out/logs/apk.log').read_bytes()
assert b'MACH_EXIT=0' in capture['logs/apk.log']
assert b'BUILD SUCCESSFUL' in capture['logs/apk.log']
assert b'KeyError' in capture['apk-bundle-recovery-checkpoint/apk.log']
for name in [
    'mobile/android/android-components/components/feature/fxsuggest/src/main/java/mozilla/components/feature/fxsuggest/FxSuggestAdmission.kt',
    'mobile/android/android-components/components/feature/fxsuggest/src/test/java/mozilla/components/feature/fxsuggest/FxSuggestAdmissionTest.kt',
    'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/browser/permissions/OriginBoundPermissionsDialogFragment.kt',
    'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/search/SearchEngineFragment.kt',
    'mobile/android/fenix/app/src/main/res/raw/initial_shortcuts.json',
]:
    capture['source/'+name] = (work/'src'/name).read_bytes()
for name in ['scripts/android-apk.sh', 'assets/mozconfig.android',
             'docs/android/evidence/lw-m7-12/run-apk-bundle-recovery.sh',
             'docs/android/evidence/lw-m7-12/run-bundle-recovery-checkpoint.sh',
             'docs/android/evidence/lw-m7-21/stage-permission-bundle.py',
             'docs/android/evidence/lw-m7-30/check-source.py']:
    capture['configuration/'+name] = (work/'repo'/name).read_bytes()
apks = {}
for abi in ['armeabi-v7a', 'arm64-v8a', 'x86_64', 'universal']:
    path = work/'out/apk'/f'fenix-{abi}-release.apk'
    before = path.stat()
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert path.stat() == before
    apks[path.name] = {'sha256': digest, 'bytes': before.st_size,
                       'mtime_ns': before.st_mtime_ns}
with zipfile.ZipFile(work/'out/apk/fenix-x86_64-release.apk') as archive:
    capture['apk/entries.json'] = (json.dumps(archive.namelist(), indent=2)+'\n').encode()
    capture['apk/resources.arsc'] = archive.read('resources.arsc')
capture['apk/output-metadata.json'] = (work/'out/apk/output-metadata.json').read_bytes()
unit = 'redoubt-apk-bundle-recovery-20260909.service'
capture['service.txt'] = subprocess.check_output([
    'systemctl', '--user', 'show', unit, '-p', 'ActiveState', '-p', 'InvocationID',
    '-p', 'ExecMainStatus', '-p', 'ExecMainStartTimestamp', '-p', 'ExecMainExitTimestamp'])
assert b'InvocationID=202a41bedcc148ef9faf7d2180eec463' in capture['service.txt']
assert b'ActiveState=failed' in capture['service.txt']
capture['journal.txt'] = subprocess.check_output(['journalctl', '--user', '--no-pager', '-u', unit])
capture['memory-events.txt'] = Path('/sys/fs/cgroup/user.slice/user-1001.slice/memory.events').read_bytes()
for name, digest in rows.items():
    assert sha((work/'src'/name).read_bytes()) == digest, name
result = {
    'classification': 'APK compiler and packaging exit 0; fixed-path resource verifier raises KeyError. Full tests and runtime did not run. APK acceptance pending resource verification.',
    'invocation': '202a41bedcc148ef9faf7d2180eec463',
    'source_count': len(rows), 'source_manifest_sha256': sha((evidence/'source-sha256.txt').read_bytes()),
    'compiler_exit': 0, 'checkpoint_exit': 1, 'source_checked_before_and_after': True,
    'development_apks': apks,
    'captured': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'files': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in capture.items()},
}
capture['result.json'] = (json.dumps(result, indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
    for name, data in capture.items():
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
