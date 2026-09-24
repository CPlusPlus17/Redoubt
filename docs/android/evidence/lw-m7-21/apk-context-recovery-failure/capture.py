"""Read-only failed APK capture; writes the evidence archive to stdout."""
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

work = Path('/home/runner/work/feature-parity-20260908')
os.environ['XDG_RUNTIME_DIR'] = '/run/user/1001'
assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm'
assert not subprocess.check_output(['podman', '--remote=false', 'ps', '-q'], text=True).strip()
evidence = work/'evidence/parity-extended-apk'
assert (evidence/'build-exit.txt').read_text().strip() == '1'
assert (evidence/'finished.txt').is_file()
sha = lambda data: hashlib.sha256(data).hexdigest()
rows = dict((name, digest) for digest, name in
            (line.split('  ', 1) for line in (evidence/'source-sha256.txt').read_text().splitlines()))
assert len(rows) == 165
for name, digest in rows.items():
    assert sha((work/'src'/name).read_bytes()) == digest, name
capture = {}
for folder in ['parity-extended-apk', 'apk-context-recovery-checkpoint', 'apk-resource-source', 'apk-admission-copy-source', 'apk-search-context-source']:
    for path in (work/'evidence'/folder).iterdir():
        if path.is_file():
            capture[folder+'/'+path.name] = path.read_bytes()
capture['logs/apk.log'] = (work/'out/logs/apk.log').read_bytes()
assert b'MACH_EXIT=1' in capture['logs/apk.log']
assert b'OriginBoundPermissionsDialogFragment.kt:303:29' in capture['logs/apk.log']
assert b'bundleOf(vararg pairs' in capture['logs/apk.log']
assert b'is deprecated' in capture['logs/apk.log']
for name in [
    'mobile/android/android-components/components/feature/fxsuggest/src/main/java/mozilla/components/feature/fxsuggest/FxSuggestAdmission.kt',
    'mobile/android/android-components/components/feature/fxsuggest/src/test/java/mozilla/components/feature/fxsuggest/FxSuggestAdmissionTest.kt',
    'mobile/android/android-components/components/service/pocket/src/main/java/mozilla/components/service/pocket/stories/api/PocketResponse.kt',
    'gradle/libs.versions.toml',
    'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/browser/permissions/OriginBoundPermissionsDialogFragment.kt',
    'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/search/SearchEngineFragment.kt',
]:
    capture['source/'+name] = (work/'src'/name).read_bytes()
for name in ['scripts/android-apk.sh', 'assets/mozconfig.android',
             'docs/android/evidence/lw-m7-12/run-extended-apk.sh',
             'docs/android/evidence/lw-m7-21/stage-apk-resource.py',
             'docs/android/evidence/lw-m7-12/run-apk-copy-recovery.sh',
             'docs/android/evidence/lw-m7-21/stage-admission-copy.py']:
    capture['configuration/'+name] = (work/'repo'/name).read_bytes()
unit = 'redoubt-apk-context-recovery-20260909.service'
capture['service.txt'] = subprocess.check_output([
    'systemctl', '--user', 'show', unit, '-p', 'ActiveState', '-p', 'InvocationID',
    '-p', 'ExecMainStatus', '-p', 'ExecMainStartTimestamp', '-p', 'ExecMainExitTimestamp'])
assert b'InvocationID=dd05803acb2349149c35c6f47448d994' in capture['service.txt']
assert b'ActiveState=failed' in capture['service.txt']
capture['journal.txt'] = subprocess.check_output(['journalctl', '--user', '--no-pager', '-u', unit])
capture['memory-events.txt'] = Path('/sys/fs/cgroup/user.slice/user-1001.slice/memory.events').read_bytes()
for name, digest in rows.items():
    assert sha((work/'src'/name).read_bytes()) == digest, name
result = {
    'classification': 'Nullable settings context errors resolved; Fenix compilation failed under -Werror on deprecated bundleOf in origin permission dialog. No APK tests or runtime ran.',
    'invocation': 'dd05803acb2349149c35c6f47448d994',
    'source_count': len(rows), 'source_manifest_sha256': sha((evidence/'source-sha256.txt').read_bytes()),
    'driver_exit': 1, 'source_checked_before_and_after': True,
    'captured': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'files': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in capture.items()},
}
capture['result.json'] = (json.dumps(result, indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
    for name, data in capture.items():
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
