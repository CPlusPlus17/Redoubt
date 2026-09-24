"""Stage one reviewed test fixture after retaining the terminal fourth failure."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

WORK = Path('/home/runner/work/feature-parity-20260908')
REPO = WORK / 'repo'
HERE = REPO / 'docs/android/evidence/lw-m7-21'
PARENT = WORK / 'evidence/fenix-regression-source'
OUT = WORK / 'evidence/fenix-navigation-fixture-source'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(path):
    rows = {}
    for line in path.read_text().splitlines():
        value, name = line.split('  ', 1)
        assert name not in rows and not Path(name).is_absolute() and '..' not in Path(name).parts
        rows[name] = value
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    assert os.getuid() == 1001
    os.environ['XDG_RUNTIME_DIR'] = '/run/user/1001'
    assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm'
    assert not subprocess.check_output(['podman', '--remote=false', 'ps', '-q'], text=True).strip()
    path = HERE / 'fenix-navigation-correction/inputs.json'
    inputs = json.loads(path.read_text())
    assert all(digest(REPO / name) == value for name, value in inputs['repository_inputs'].items())
    assert digest(PARENT / 'source-sha256.txt') == inputs['parent_manifest_sha256']
    assert digest(PARENT / 'receipt.json') == inputs['parent_receipt_sha256']
    before = manifest(PARENT / 'source-sha256.txt')
    assert len(before) == 167 and len(inputs['files']) == 1
    fix = inputs['files'][0]
    assert before[fix['path']] == fix['before_sha256']
    assert digest(REPO / fix['source']) == fix['after_sha256']
    after = dict(before)
    after[fix['path']] = fix['after_sha256']
    after_text = ''.join(value + '  ' + name + '\n' for name, value in sorted(after.items()))
    assert hashlib.sha256(after_text.encode()).hexdigest() == inputs['proposed_manifest_sha256']
    if OUT.exists():
        receipt = json.loads((OUT / 'receipt.json').read_text())
        assert receipt['status'] == 'PASS' and receipt['inputs_sha256'] == digest(path)
        assert manifest(OUT / 'source-sha256.txt') == after
        assert all(digest(WORK / 'src' / name) == value for name, value in after.items())
        print('PASS existing167 source stage; one test fixture correction')
        return
    assert not args.check
    failed = WORK / 'evidence/fenix-regression-tests'
    assert (failed / 'finished.txt').is_file()
    assert digest(failed / 'source-sha256.txt') == inputs['parent_manifest_sha256']
    assert int((failed / 'fenix-gate-exit.txt').read_text()) == inputs['failed_gate_exit']
    service = subprocess.check_output(['systemctl', '--user', 'show', inputs['failed_service'],
        '-p', 'ActiveState', '-p', 'InvocationID', '-p', 'ExecMainStatus'], text=True)
    assert 'ActiveState=failed\n' in service and 'ExecMainStatus=1\n' in service
    assert 'InvocationID=' + inputs['failed_invocation'] + '\n' in service
    assert all(digest(WORK / 'src' / name) == value for name, value in before.items())
    native = [line.split('  ', 1) for line in (PARENT / 'native-input-sha256.txt').read_text().splitlines()]
    assert len(native) == 3 and all(digest(Path(name)) == value for value, name in native)
    OUT.mkdir()
    (OUT / 'inputs.json').write_bytes(path.read_bytes())
    for name in ['source-sha256.txt', 'receipt.json']:
        (OUT / ('parent-' + name)).write_bytes((PARENT / name).read_bytes())
    (OUT / 'native-input-sha256.txt').write_bytes((PARENT / 'native-input-sha256.txt').read_bytes())
    (OUT / 'failed-service.txt').write_text(service)
    target = WORK / 'src' / fix['path']
    (OUT / (target.name + '.before')).write_bytes(target.read_bytes())
    target.write_bytes((REPO / fix['source']).read_bytes())
    assert all(digest(WORK / 'src' / name) == value for name, value in after.items())
    assert all(digest(Path(name)) == value for value, name in native)
    (OUT / 'source-sha256.txt').write_text(after_text)
    receipt = {'status': 'PASS', 'inputs_sha256': digest(path), 'source_count': len(after),
        'source_manifest_sha256': digest(OUT / 'source-sha256.txt'), 'changes': inputs['files'],
        'finished': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope': 'One test fixture only. Targeted and full tests, new APK and runtime require separate results.'}
    (OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('PASS staged one reviewed test fixture; all167 source and three native identities verified')


if __name__ == '__main__':
    main()
