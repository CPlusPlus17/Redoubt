"""Read-only successful terminal capture of the corrected167-file Fenix candidate."""
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
evidence = work/'evidence/account-process-tests'
assert (evidence/'finished.txt').is_file()
assert (evidence/'fenix-gate-exit.txt').read_text().strip() == '0'
sha = lambda data: hashlib.sha256(data).hexdigest()
manifest = (evidence/'source-sha256.txt').read_bytes()
assert sha(manifest) == '4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739'
rows = [line.split('  ', 1) for line in manifest.decode().splitlines()]
assert len(rows) == 167
for expected, name in rows:
    assert sha((work/'src'/name).read_bytes()) == expected, name
capture = {}
for folder, prefix in [(evidence, 'target-tests'), (work/'evidence/account-process-source', 'account-process-source')]:
    for path in folder.iterdir():
        if path.is_file():
            capture[prefix+'/'+path.name] = path.read_bytes()
for expected, name in rows:
    if name.endswith('Test.kt'):
        capture['source/'+name] = (work/'src'/name).read_bytes()
extra_names = {
    'FenixApplicationTest.kt', 'FenixApplication.kt', 'ExternalAppBrowserActivityTest.kt',
    'ExternalAppBrowserActivity.kt', 'HomeActivity.kt', 'HomeActivityTest.kt',
    'AuthCustomTabActivityTest.kt', 'AuthCustomTabActivity.kt', 'CookieBannerSettingsTest.kt',
    'CookieBannerSettingsFragment.kt', 'CreditCardItemViewHolderTest.kt', 'CreditCardItemViewHolder.kt',
    'Settings.kt', 'SessionUseCases.kt',
}
for base in [work/'src/mobile/android/fenix/app/src', work/'src/mobile/android/android-components/components/feature/session/src/main']:
    for path in base.rglob('*.kt'):
        if path.name in extra_names:
            capture['source/'+str(path.relative_to(work/'src'))] = path.read_bytes()
for name in ['docs/android/board.py', 'docs/android/fenix-test-allowlist.yaml',
             'docs/android/evidence/lw-m7-12/run-fenix-account-process-tests.sh',
             'docs/android/evidence/lw-m7-12/grade-extended-tests.py']:
    capture['configuration/'+name] = (work/'repo'/name).read_bytes()
unit = 'redoubt-fenix-account-process-tests-20260909.service'
capture['service.txt'] = subprocess.check_output([
    'systemctl', '--user', 'show', unit, '-p', 'ActiveState', '-p', 'InvocationID',
    '-p', 'ExecMainStatus', '-p', 'ExecMainStartTimestamp', '-p', 'ExecMainExitTimestamp'])
assert b'InvocationID=c02a8b984fae45dc859eff2b556b82f0' in capture['service.txt']
assert b'ActiveState=active' in capture['service.txt']
assert b'ExecMainStatus=0' in capture['service.txt']
assert (evidence/'fresh-results-gate-exit.txt').read_text().strip() == '0'
capture['journal.txt'] = subprocess.check_output(['journalctl', '--user', '--no-pager', '-u', unit])
capture['memory-events.txt'] = Path('/sys/fs/cgroup/user.slice/user-1001.slice/memory.events').read_bytes()
for expected, name in rows:
    assert sha((work/'src'/name).read_bytes()) == expected, name
summary = json.loads((evidence/'junit-summary.json').read_text())
assert all(not row['issues'] for row in summary.values())
assert sum(row['summary']['tests'] for name,row in summary.items() if name != 'fenix') == 147
assert all(not row['summary']['failures'] and not row['summary']['errors'] and not row['issues'] for name,row in summary.items() if name != 'fenix')
assert summary['fenix']['summary']['classes'] == 610
assert summary['fenix']['summary']['tests'] == 5523
required = {
    'org.mozilla.fenix.settings.AccountServicesPreferenceTest':
        'production child attachment never accesses app storage and closes account admission',
    'org.mozilla.fenix.settings.search.FirefoxSuggestPolicyTest':
        'production child attachment closes Suggest and accounts without accessing app preferences',
    'mozilla.components.service.fxa.AccountServicesTest':
        'non-main admission closes without reading or changing a saved parent choice',
}
seen = set()
for suite in ['fenix', 'accounts']:
    with tarfile.open(evidence / (suite + '-junit-xml.tar.gz')) as xml:
        for member in xml.getmembers():
            if member.isfile() and member.name.endswith('.xml'):
                tree = ET.fromstring(xml.extractfile(member).read())
                name = tree.attrib['name']
                if name in required:
                    assert name not in seen
                    cases = tree.findall('testcase')
                    assert required[name] in {case.attrib['name'] for case in cases}
                    assert all(not list(case) for case in cases), name
                    seen.add(name)
assert seen == set(required)
result = {
    'classification': 'PASS actual full Fenix allowance and fresh coverage gates, with all147 selected component cases. New APK build and runtime still require separate evidence.',
    'invocation': 'c02a8b984fae45dc859eff2b556b82f0',
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
