"""Verify the unchanged compiled APKs, then finalize their interrupted evidence."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

WORK = Path('/home/runner/work/feature-parity-20260908')
REPO = WORK / 'repo'
HERE = REPO / 'docs/android/evidence/lw-m7-21'
EVIDENCE = WORK / 'evidence/parity-extended-apk'
OUT = WORK / 'evidence/apk-resource-verification-recovery'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_manifest(path, base):
    rows = {}
    for line in path.read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert name not in rows
        assert digest(base / name) == expected, name
        rows[name] = expected
    return rows


assert os.getuid() == 1001
os.environ['XDG_RUNTIME_DIR'] = '/run/user/1001'
assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm'
assert not subprocess.check_output(['podman', '--remote=false', 'ps', '-q'], text=True).strip()
assert (EVIDENCE / 'build-exit.txt').read_text().strip() == '0'
assert not (EVIDENCE / 'finished.txt').exists()
assert digest(EVIDENCE / 'source-sha256.txt') == 'c53736e87152ba6de7ae232efd0a26197601027e4553be3f5f4bd7e6045601ae'
assert len(check_manifest(EVIDENCE / 'source-sha256.txt', WORK / 'src')) == 165
assert len(check_manifest(EVIDENCE / 'native-input-sha256.txt', WORK)) == 3
parent = json.loads((HERE / 'apk-bundle-resource-check-failure/result.json').read_text())
assert parent['compiler_exit'] == 0 and parent['checkpoint_exit'] == 1
assert digest(WORK / 'out/logs/apk.log') == parent['files']['logs/apk.log']['sha256']
for name, row in parent['development_apks'].items():
    path = WORK / 'out/apk' / name
    assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], name
inputs = json.loads((HERE / 'apk-resource-recovery-inputs.json').read_text())
for name, expected in inputs['repository_files'].items():
    assert digest(REPO / name) == expected, name
aapt2 = WORK / inputs['aapt2_path']
assert digest(aapt2) == inputs['aapt2_sha256']
service = subprocess.check_output([
    'systemctl', '--user', 'show', 'redoubt-apk-bundle-recovery-20260909.service',
    '-p', 'ActiveState', '-p', 'ExecMainStatus', '-p', 'InvocationID'], text=True)
assert 'ActiveState=failed' in service and 'ExecMainStatus=1' in service
assert 'InvocationID=202a41bedcc148ef9faf7d2180eec463' in service
OUT.mkdir()
(OUT / 'parent-service.txt').write_text(service)
shutil.copy2(EVIDENCE / 'shortcut-resource-check.txt', OUT / 'original-shortcut-resource-check.txt')
shutil.copy2(HERE / 'apk-resource-recovery-inputs.json', OUT / 'inputs.json')
results = {}
for name in parent['development_apks']:
    command = [sys.executable, str(REPO / 'docs/android/evidence/lw-m7-30/check-source.py'),
               '--apk', str(WORK / 'out/apk' / name), '--aapt2', str(aapt2)]
    result = subprocess.run(command, text=True, capture_output=True)
    log = OUT / (name + '.log')
    log.write_text(result.stdout + result.stderr)
    results[name] = {'command': command, 'exit': result.returncode,
                     'log_sha256': digest(log), 'apk': parent['development_apks'][name]}
    (OUT / 'checks.json').write_text(json.dumps(results, indent=2) + '\n')
    assert result.returncode == 0, log
    assert digest(WORK / 'out/apk' / name) == parent['development_apks'][name]['sha256']
assert len(check_manifest(EVIDENCE / 'source-sha256.txt', WORK / 'src')) == 165
assert len(check_manifest(EVIDENCE / 'native-input-sha256.txt', WORK)) == 3
finished = datetime.datetime.now(datetime.timezone.utc).isoformat()
receipt = {
    'status': 'PASS resource-table verification of all four unchanged development APKs',
    'parent_compile_invocation': parent['invocation'], 'parent_checkpoint_exit': 1,
    'source_manifest_sha256': digest(EVIDENCE / 'source-sha256.txt'),
    'inputs_sha256': digest(HERE / 'apk-resource-recovery-inputs.json'),
    'driver_sha256': digest(Path(__file__)), 'checks': results,
    'completed': finished, 'recompiled': False,
    'unit_tests': 'NOT RUN by this recovery', 'runtime': 'NOT RUN by this recovery',
}
(OUT / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
shutil.copy2(OUT / 'result.json', EVIDENCE / 'resource-verification-recovery.json')
(EVIDENCE / 'shortcut-resource-check.txt').write_text(
    ''.join((OUT / (name + '.log')).read_text() for name in results))
(EVIDENCE / 'SHA256SUMS.development').write_text(''.join(
    row['sha256'] + '  ' + name + '\n' for name, row in parent['development_apks'].items()))
(EVIDENCE / 'finished.txt').write_text(finished + '\n')
print('PASS resource-table verification; all four APKs, 165 source bindings and native AAR inputs unchanged')
