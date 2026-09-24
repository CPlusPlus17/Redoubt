"""Capture and grade the actual eight-class process diagnostic in the KVM guest."""
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET

work = Path('/home/runner/work/feature-parity-20260908')
os.environ['XDG_RUNTIME_DIR'] = '/run/user/1001'
assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm'
assert not subprocess.check_output(['podman', '--remote=false', 'ps', '-q'], text=True).strip()
evidence = work/'evidence/account-process-diagnostic-20260909'
assert (evidence/'finished.txt').is_file()
assert (evidence/'build-exit.txt').read_text().strip() == '0'
sha = lambda data: hashlib.sha256(data).hexdigest()
manifest = (evidence/'source-sha256.txt').read_bytes()
assert sha(manifest) == '4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739'
rows = [line.split('  ', 1) for line in manifest.decode().splitlines()]
assert len(rows) == 167
for expected, name in rows:
    assert sha((work/'src'/name).read_bytes()) == expected, name
expected_classes = {
    'org.mozilla.fenix.HomeActivityAccountSettingsTest',
    'org.mozilla.fenix.FenixApplicationTest',
    'org.mozilla.fenix.settings.AccountServicesPreferenceTest',
    'org.mozilla.fenix.settings.search.FirefoxSuggestPolicyTest',
    'mozilla.components.service.fxa.AccountServicesTest',
    'mozilla.components.service.fxa.AccountServicesDisabledTest',
    'mozilla.components.service.fxa.sync.AccountServicesWorkerTest',
    'mozilla.components.feature.syncedtabs.commands.AccountServicesFlushWorkerTest',
}
new_methods = {
    'production child attachment never accesses app storage and closes account admission',
    'production child attachment closes Suggest and accounts without accessing app preferences',
    'non-main admission closes without reading or changing a saved parent choice',
}
classes = {}
for suite in ['fenix', 'accounts', 'syncedtabs']:
    with tarfile.open(evidence/f'{suite}-junit-xml.tar.gz') as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith('.xml'):
                continue
            root = ET.fromstring(archive.extractfile(member).read())
            name = root.attrib['name']
            assert name in expected_classes and name not in classes, name
            cases = root.findall('testcase')
            assert len(cases) == int(root.attrib['tests']) and len(cases) > 0
            assert all(int(root.attrib.get(key, '0')) == 0 for key in ['failures', 'errors', 'skipped'])
            assert all(not list(case) for case in cases), name
            methods = [case.attrib['name'] for case in cases]
            assert len(methods) == len(set(methods))
            classes[name] = {'tests': len(cases), 'methods': methods}
assert set(classes) == expected_classes
assert new_methods <= {name for row in classes.values() for name in row['methods']}
capture = {}
for path in evidence.iterdir():
    if path.is_file():
        capture['diagnostic/'+path.name] = path.read_bytes()
stage = work/'evidence/account-process-source'
for path in stage.rglob('*'):
    if path.is_file():
        capture['stage/'+str(path.relative_to(stage))] = path.read_bytes()
assert json.loads((stage/'receipt.json').read_text())['status'] == 'PASS'
for expected, name in rows:
    if name.endswith('Test.kt'):
        capture['source/'+name] = (work/'src'/name).read_bytes()
for name in ['docs/android/evidence/lw-m7-21/stage-account-process-fixes.py',
             'docs/android/evidence/lw-m7-21/account-process-correction/run-diagnostic.sh',
             'docs/android/evidence/lw-m7-21/account-process-correction/inputs.json',
             'docs/android/evidence/lw-m7-12/run-fenix-account-process-tests.sh']:
    capture['configuration/'+name] = (work/'repo'/name).read_bytes()
unit = 'redoubt-account-process-diagnostic-20260909.service'
capture['service.txt'] = subprocess.check_output([
    'systemctl', '--user', 'show', unit, '-p', 'LoadState', '-p', 'ActiveState',
    '-p', 'SubState', '-p', 'InvocationID', '-p', 'RemainAfterExit',
    '-p', 'ExecMainStatus', '-p', 'ExecMainStartTimestamp', '-p', 'ExecMainExitTimestamp'])
for expected in [b'LoadState=loaded', b'ActiveState=active', b'SubState=exited',
                 b'RemainAfterExit=yes', b'ExecMainStatus=0',
                 b'InvocationID=6f12325cbb0d4a7a833126faeec509e6']:
    assert expected in capture['service.txt'], expected
capture['journal.txt'] = subprocess.check_output(['journalctl', '--user', '--no-pager', '-u', unit])
for expected, name in rows:
    assert sha((work/'src'/name).read_bytes()) == expected, name
result = {
    'status': 'PASS', 'scope': 'Actual targeted diagnostic only; full suite, APK and runtime pending.',
    'invocation': '6f12325cbb0d4a7a833126faeec509e6',
    'source_manifest_sha256': sha(manifest), 'source_count': 167,
    'classes': classes, 'tests': sum(row['tests'] for row in classes.values()),
    'failures': 0, 'errors': 0, 'skipped': 0, 'new_methods': sorted(new_methods),
    'captured': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'files': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in capture.items()},
}
capture['result.json'] = (json.dumps(result, indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
    for name, data in capture.items():
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
