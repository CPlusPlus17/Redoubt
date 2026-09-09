"""Read-only terminal capture of the second target suite for the165-file candidate."""
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
evidence = work/'evidence/parity-extended-tests'
checkpoint = work/'evidence/test-fixture-recovery-checkpoint'
assert (evidence/'finished.txt').is_file()
assert (checkpoint/'tests-exit.txt').read_text().strip() == '1'
assert not (checkpoint/'runtime-exit.txt').exists()
sha = lambda data: hashlib.sha256(data).hexdigest()
manifest = (evidence/'source-sha256.txt').read_bytes()
assert sha(manifest) == '46e33df9a7121a161af8e83151b44a2517b17d8609be59dc992e94e1335f4cbd'
rows = [line.split('  ', 1) for line in manifest.decode().splitlines()]
assert len(rows) == 165
for expected, name in rows:
    assert sha((work/'src'/name).read_bytes()) == expected, name
capture = {}
for folder, prefix in [(evidence, 'target-tests'), (checkpoint, 'checkpoint'), (work/'evidence/test-fixture-source', 'test-fixture-source')]:
    for path in folder.iterdir():
        if path.is_file():
            capture[prefix+'/'+path.name] = path.read_bytes()
for expected, name in rows:
    if name.endswith('Test.kt'):
        capture['source/'+name] = (work/'src'/name).read_bytes()
for name in ['docs/android/board.py', 'docs/android/fenix-test-allowlist.yaml',
             'docs/android/evidence/lw-m7-12/run-fixture-tests.sh',
             'docs/android/evidence/lw-m7-12/grade-extended-tests.py']:
    capture['configuration/'+name] = (work/'repo'/name).read_bytes()
unit = 'redoubt-test-fixture-recovery-20260909.service'
capture['service.txt'] = subprocess.check_output([
    'systemctl', '--user', 'show', unit, '-p', 'ActiveState', '-p', 'InvocationID',
    '-p', 'ExecMainStatus', '-p', 'ExecMainStartTimestamp', '-p', 'ExecMainExitTimestamp'])
assert b'InvocationID=429bea8c9f9c45e3911fd19cf8422fe7' in capture['service.txt']
assert b'ActiveState=failed' in capture['service.txt']
capture['journal.txt'] = subprocess.check_output(['journalctl', '--user', '--no-pager', '-u', unit])
capture['memory-events.txt'] = Path('/sys/fs/cgroup/user.slice/user-1001.slice/memory.events').read_bytes()
for expected, name in rows:
    assert sha((work/'src'/name).read_bytes()) == expected, name
summary = json.loads((evidence/'junit-summary.json').read_text())
assert sum(row['summary']['tests'] for name,row in summary.items() if name != 'fenix') == 146
assert all(not row['summary']['failures'] and not row['summary']['errors'] and not row['issues'] for name,row in summary.items() if name != 'fenix')
result = {
    'classification': 'FAIL Fenix test compiler on ExperimentalCoroutinesApi opt-in; all146 component cases pass. Runtime did not run.',
    'invocation': '429bea8c9f9c45e3911fd19cf8422fe7',
    'source_manifest_sha256': sha(manifest), 'source_count': len(rows),
    'source_checked_before_and_after': True,
    'suites': {name: {key: value for key, value in row.items() if key != 'classes'} for name, row in summary.items()},
    'captured': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'files': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in capture.items()},
}
capture['result.json'] = (json.dumps(result, indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
    for name, data in capture.items():
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
