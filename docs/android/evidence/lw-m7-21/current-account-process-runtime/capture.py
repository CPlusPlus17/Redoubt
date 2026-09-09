"""Capture a terminal process-recovery runtime, preserving success or failure."""
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
evidence = work/'evidence/account-process-runtime'
state = json.loads((evidence/'result.json').read_text())
assert state['status'] in {'PASS', 'FAIL'} and (evidence/'finished.txt').is_file()
assert state['source_manifest']['sha256'] == '4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739'
assert state['service']['InvocationID'] == 'a172ec824e2a4e94a4dd467627f6a0d0'
unit = 'redoubt-account-process-runtime-20260909.service'
files = {'service.txt': subprocess.check_output([
    'systemctl', '--user', 'show', unit, '-p', 'LoadState', '-p', 'InvocationID',
    '-p', 'ActiveState', '-p', 'SubState', '-p', 'RemainAfterExit',
    '-p', 'ExecMainStatus', '-p', 'ExecMainStartTimestamp', '-p', 'ExecMainExitTimestamp']),
    'journal.txt': subprocess.check_output(['journalctl', '--user', '--no-pager', '-u', unit])}
assert b'InvocationID=a172ec824e2a4e94a4dd467627f6a0d0' in files['service.txt']
assert b'SubState=running' not in files['service.txt']
assert b'RemainAfterExit=yes' in files['service.txt']
if state['status'] == 'PASS':
    assert b'SubState=exited' in files['service.txt'] and b'ExecMainStatus=0' in files['service.txt']
    assert state['emulator_cleanup_exit'] == 0
    assert all(state['stages'][name]['exit'] == 0 for name in ['ubo-lifecycle', 'baseline', 'pref-audit'])
for path in evidence.iterdir():
    if path.is_file():
        files['runtime-checkpoint/'+path.name] = path.read_bytes()
for name in ['smoke-first-navigation', 'smoke-baseline', 'smoke-pref-audit']:
    folder = work/'account-process-runtime'/name
    if folder.is_dir():
        for path in folder.iterdir():
            if path.is_file():
                files['runtime-work/'+name+'/'+path.name] = path.read_bytes()
config = json.loads((evidence/'inputs.json').read_text())
sha = lambda data: hashlib.sha256(data).hexdigest()
for name, row in config['repository_files'].items():
    data = (work/'repo'/name).read_bytes()
    assert sha(data) == row['sha256']
    files['configuration/'+name] = data
manifest = (evidence/'source-sha256.txt').read_text()
rows = [row.split('  ', 1) for row in manifest.splitlines()]
assert len(rows) == 167
for digest, name in rows:
    assert sha((work/'src'/name).read_bytes()) == digest, name
for name, row in config['apks'].items():
    path = Path(row['path'])
    assert path.stat().st_size == row['bytes']
    with path.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256']
result = {
    'status': state['status'], 'source_manifest_sha256': state['source_manifest']['sha256'],
    'invocation': 'a172ec824e2a4e94a4dd467627f6a0d0',
    'scope': state.get('scope'), 'error': state.get('error'),
    'emulator_cleanup_exit': state.get('emulator_cleanup_exit'),
    'stage_exits': {name: row.get('exit') for name, row in state['stages'].items()},
    'files': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in files.items()},
}
files['capture-result.json'] = (json.dumps(result, indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
    for name, data in files.items():
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
