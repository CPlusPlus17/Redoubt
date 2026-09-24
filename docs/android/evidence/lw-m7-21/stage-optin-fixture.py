"""Stage the coroutine test opt-in after four verified fixture corrections."""
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
APK = WORK / 'evidence/parity-extended-apk'
OUT = WORK / 'evidence/test-fixture-optin-source'
PARENT_STAGE = WORK / 'evidence/test-fixture-source'
PARENT = '46e33df9a7121a161af8e83151b44a2517b17d8609be59dc992e94e1335f4cbd'
COMPILED = 'c53736e87152ba6de7ae232efd0a26197601027e4553be3f5f4bd7e6045601ae'
FILES = {
    'mobile/android/fenix/app/src/test/java/org/mozilla/fenix/browser/permissions/OriginBoundPermissionsFeatureTest.kt',
    'mobile/android/fenix/app/src/test/java/org/mozilla/fenix/settings/quicksettings/protections/cookiebanners/DefaultCookieBannerDetailsControllerTest.kt',
    'mobile/android/android-components/components/browser/engine-gecko/src/test/java/mozilla/components/browser/engine/gecko/permission/OriginBoundPermissionsStorageTest.kt',
    'mobile/android/android-components/components/browser/engine-gecko/src/test/java/mozilla/components/browser/engine/gecko/cookiebanners/GeckoCookieBannersStorageTest.kt',
    'mobile/android/android-components/components/service/firefox-accounts/src/test/java/mozilla/components/service/fxa/AccountServicesDisabledTest.kt',
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parse_manifest(path):
    rows = {}
    for line in path.read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert name not in rows
        rows[name] = expected
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='require existing staging; do not change source')
    args = parser.parse_args()
    assert os.getuid() == 1001
    os.environ['XDG_RUNTIME_DIR'] = '/run/user/1001'
    assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm'
    assert not subprocess.check_output(['podman', '--remote=false', 'ps', '-q'], text=True).strip()
    assert (APK / 'build-exit.txt').read_text().strip() == '0' and (APK / 'finished.txt').is_file()
    parent = json.loads((HERE / 'apk-bundle-resource-check-failure/result.json').read_text())
    assert digest(APK / 'source-sha256.txt') == COMPILED == parent['source_manifest_sha256']
    assert digest(PARENT_STAGE / 'source-sha256.txt') == PARENT
    assert digest(APK / 'native-input-sha256.txt') == parent['files']['parity-extended-apk/native-input-sha256.txt']['sha256']
    before = parse_manifest(PARENT_STAGE / 'source-sha256.txt')
    assert len(before) == 165 and FILES <= before.keys()
    native = parse_manifest(APK / 'native-input-sha256.txt')
    assert len(native) == 3 and all(digest(Path(name)) == value for name, value in native.items())
    assert len(parent['development_apks']) == 4
    assert all(digest(WORK / 'out/apk' / name) == row['sha256'] for name, row in parent['development_apks'].items())
    inputs_path = HERE / 'test-optin-correction/inputs.json'
    inputs = json.loads(inputs_path.read_text())
    assert inputs['parent_manifest_sha256'] == PARENT and inputs['compiled_manifest_sha256'] == COMPILED
    assert digest(PARENT_STAGE / 'receipt.json') == inputs['parent_stage_receipt_sha256']
    assert all(digest(REPO / name) == value for name, value in inputs['repository_inputs'].items())
    fixes = {row['path']: row for row in inputs['files']}
    assert len(inputs['files']) == 5 and set(fixes) == FILES
    assert sum(row['before_sha256'] != row['after_sha256'] for row in fixes.values()) == 1
    after = dict(before)
    for name, row in fixes.items():
        assert before[name] == row['before_sha256']
        assert digest(REPO / row['source']) == row['after_sha256']
        after[name] = row['after_sha256']
    after_text = ''.join(value + '  ' + name + '\n' for name, value in sorted(after.items()))
    assert hashlib.sha256(after_text.encode()).hexdigest() == inputs['proposed_manifest_sha256']
    binding = {'parent_manifest_sha256': PARENT, 'compiled_manifest_sha256': COMPILED, 'inputs_sha256': digest(inputs_path),
               'compiled_apks': parent['development_apks'], 'native_inputs': native}
    if OUT.exists():
        saved = json.loads((OUT / 'receipt.json').read_text())
        assert saved['status'] == 'PASS' and saved['binding'] == binding
        assert parse_manifest(OUT / 'source-sha256.txt') == after
        assert digest(OUT / 'source-sha256.txt') == saved['source_manifest_sha256']
        assert all(digest(WORK / 'src' / name) == value for name, value in after.items())
        print('PASS existing coroutine test opt-in and four retained fixtures; APKs unchanged')
        return
    assert not args.check, 'test fixture staging receipt is absent'
    failed = WORK / 'evidence/parity-extended-tests'
    assert (failed / 'finished.txt').is_file()
    assert digest(failed / 'source-sha256.txt') == PARENT
    assert (WORK / 'evidence/test-fixture-recovery-checkpoint/tests-exit.txt').read_text().strip() == '1'
    assert all(digest(WORK / 'src' / name) == value for name, value in before.items())
    OUT.mkdir()
    (OUT / 'compiled-apk-source-sha256.txt').write_bytes((APK / 'source-sha256.txt').read_bytes())
    (OUT / 'inputs.json').write_bytes(inputs_path.read_bytes())
    (OUT / 'parent-test-source-sha256.txt').write_bytes((PARENT_STAGE / 'source-sha256.txt').read_bytes())
    for name, row in fixes.items():
        target = WORK / 'src' / name
        (OUT / (Path(name).name + '.before')).write_bytes(target.read_bytes())
        if row['before_sha256'] != row['after_sha256']:
            target.write_bytes((REPO / row['source']).read_bytes())
    assert all(digest(WORK / 'src' / name) == value for name, value in after.items())
    assert all(digest(Path(name)) == value for name, value in native.items())
    assert all(digest(WORK / 'out/apk' / name) == row['sha256'] for name, row in parent['development_apks'].items())
    (OUT / 'source-sha256.txt').write_text(after_text)
    result = {'status': 'PASS', 'binding': binding, 'source_count': 165, 'cumulative_test_fixtures': inputs['files'], 'new_test_changes': 1,
              'source_manifest_sha256': digest(OUT / 'source-sha256.txt'),
              'finished': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'One test API opt-in added to four retained fixture corrections; all production source and APK bytes unchanged. Full target rerun/runtime pending.'}
    (OUT / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS staged one coroutine test opt-in; four prior corrections, 165 source bindings and compiled APK identities verified')


if __name__ == '__main__':
    main()
