"""Stage the reviewed custom-tab correction and Fenix fixtures after the failed gate."""
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
PARENT = WORK / 'evidence/test-fixture-optin-source'
OUT = WORK / 'evidence/fenix-regression-source'
OLD = '659bf836ec885425b596bf077236190e8df30b2285df625ff3988c5dc93129b6'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def manifest(path, allow_absolute=False):
    rows = {}
    for line in path.read_text().splitlines():
        value, name = line.split('  ', 1)
        assert name not in rows and (allow_absolute or not Path(name).is_absolute()) and '..' not in Path(name).parts
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
    path = HERE / 'fenix-regression-correction/inputs.json'
    inputs = json.loads(path.read_text())
    assert all(digest(REPO / name) == value for name, value in inputs['repository_inputs'].items())
    assert digest(PARENT / 'source-sha256.txt') == OLD == inputs['parent_manifest_sha256']
    assert digest(PARENT / 'receipt.json') == inputs['parent_receipt_sha256']
    before = manifest(PARENT / 'source-sha256.txt')
    assert len(before) == 165 and len(inputs['files']) == 4
    fixes = {row['path']: row for row in inputs['files']}
    assert len(fixes) == 4
    after = dict(before)
    for name, row in fixes.items():
        if name in before:
            assert before[name] == row['before_sha256']
        assert digest(REPO / row['source']) == row['after_sha256']
        after[name] = row['after_sha256']
    assert len(after) == 167
    after_text = ''.join(value + '  ' + name + '\n' for name, value in sorted(after.items()))
    assert hashlib.sha256(after_text.encode()).hexdigest() == inputs['proposed_manifest_sha256']
    if OUT.exists():
        receipt = json.loads((OUT / 'receipt.json').read_text())
        assert receipt['status'] == 'PASS' and receipt['inputs_sha256'] == digest(path)
        assert manifest(OUT / 'source-sha256.txt') == after
        assert all(digest(WORK / 'src' / name) == value for name, value in after.items())
        print('PASS existing167 source stage; new APK/runtime still require separate evidence')
        return
    assert not args.check
    failed = WORK / 'evidence/parity-extended-tests'
    assert (failed / 'finished.txt').is_file() and digest(failed / 'source-sha256.txt') == OLD
    assert (WORK / 'evidence/test-optin-recovery-checkpoint/tests-exit.txt').read_text().strip() == '1'
    assert all(digest(WORK / 'src' / name) == value for name, value in before.items())
    for name, row in fixes.items():
        source = WORK / 'src' / name
        assert (digest(source) if source.exists() else None) == row['before_sha256'], name
    # Preserve old APK/native identity at the last preflight before source writes.
    historical = json.loads((HERE / 'apk-bundle-resource-check-failure/result.json').read_text())
    apk = WORK / 'evidence/parity-extended-apk'
    assert digest(apk / 'source-sha256.txt') == historical['source_manifest_sha256']
    assert digest(apk / 'native-input-sha256.txt') == historical['files']['parity-extended-apk/native-input-sha256.txt']['sha256']
    native = manifest(apk / 'native-input-sha256.txt', allow_absolute=True)
    assert len(native) == 3 and all(digest(Path(name)) == value for name, value in native.items())
    assert all(digest(WORK / 'out/apk' / name) == row['sha256'] for name, row in historical['development_apks'].items())
    OUT.mkdir()
    (OUT / 'inputs.json').write_bytes(path.read_bytes())
    (OUT / 'parent-source-sha256.txt').write_bytes((PARENT / 'source-sha256.txt').read_bytes())
    (OUT / 'historical-compiled-apk-source-sha256.txt').write_bytes((apk / 'source-sha256.txt').read_bytes())
    (OUT / 'native-input-sha256.txt').write_bytes((apk / 'native-input-sha256.txt').read_bytes())
    for name, row in fixes.items():
        target = WORK / 'src' / name
        if target.exists(): (OUT / (target.name + '.before')).write_bytes(target.read_bytes())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO / row['source']).read_bytes())
    assert all(digest(WORK / 'src' / name) == value for name, value in after.items())
    assert all(digest(Path(name)) == value for name, value in native.items())
    (OUT / 'source-sha256.txt').write_text(after_text)
    receipt = {'status': 'PASS', 'inputs_sha256': digest(path), 'source_count': len(after),
               'source_manifest_sha256': digest(OUT / 'source-sha256.txt'),
               'changes': inputs['files'], 'native_inputs': native,
               'finished': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'scope': 'One Kotlin production correction, two existing test fixtures and four new regression cases. Full tests, new APK build and runtime pending; old APK results are historical.'}
    (OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('PASS staged four reviewed files; complete167 source and native identities verified')


if __name__ == '__main__':
    main()
