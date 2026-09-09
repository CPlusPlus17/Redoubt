"""Read-only completed current167 APK checkpoint capture; binaries stay in guest output."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

work = Path('/home/runner/work/feature-parity-20260908')
evidence = work / 'evidence/fenix-regression-apk'
os.environ['XDG_RUNTIME_DIR'] = '/run/user/1001'
state = json.loads((evidence / 'result.json').read_text())
assert state['status'] == 'PASS'
assert state['source_manifest']['sha256'] == '501d04614edbc847b416cd5b6f1dac42dd0728a63125a3d9902c90d07a579c8b'
assert state['service']['InvocationID'] == '7a054c6290054e568f626c13bf8704a1'
unit = 'redoubt-fenix-regression-apk-20260909.service'
service = subprocess.check_output(['systemctl', '--user', 'show', unit, '-p', 'ActiveState', '-p', 'SubState', '-p', 'InvocationID', '-p', 'ExecMainStatus', '-p', 'ExecMainStartTimestamp', '-p', 'ExecMainExitTimestamp'])
assert b'SubState=exited' in service and b'ExecMainStatus=0' in service
assert b'InvocationID=7a054c6290054e568f626c13bf8704a1' in service
sha = lambda data: hashlib.sha256(data).hexdigest()
files = {'service.txt': service, 'journal.txt': subprocess.check_output(['journalctl', '--user', '--no-pager', '-u', unit])}
for path in evidence.iterdir():
    if path.is_file(): files['apk-checkpoint/' + path.name] = path.read_bytes()
config = json.loads((evidence / 'inputs.json').read_text())
for name, row in config['repository_files'].items():
    data = (work / 'repo' / name).read_bytes()
    assert sha(data) == row['sha256']
    files['configuration/' + name] = data
for name, row in state['apks'].items():
    path = Path(row['path'])
    assert path.stat().st_size == row['bytes']
    with path.open('rb') as stream: assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256']
    assert state['stages'][name + '-resource']['exit'] == 0
    assert state['resources'][name]['apk_sha256'] == row['sha256']
files['apk-output/output-metadata.json'] = Path(state['metadata']['path']).read_bytes()
for path in (work / 'fenix-regression-apk-output/logs').iterdir():
    if path.is_file(): files['build-logs/' + path.name] = path.read_bytes()
manifest = (evidence / 'source-sha256.txt').read_text()
for line in manifest.splitlines():
    value, name = line.split('  ', 1)
    assert sha((work / 'src' / name).read_bytes()) == value
result = {'status': 'PASS actual current167 all-four APK compilation and resource checks; runtime remains separate', 'source_manifest_sha256': state['source_manifest']['sha256'], 'invocation': state['service']['InvocationID'], 'apks': state['apks'], 'resources': state['resources'], 'files': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in files.items()}}
files['capture-result.json'] = (json.dumps(result, indent=2) + '\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
    for name, data in files.items():
        member = tarfile.TarInfo(name); member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
