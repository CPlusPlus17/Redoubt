#!/usr/bin/env python3
"""Stage two reviewed Android Components files after the recorded APK failure."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
from datetime import datetime, timezone

WORK = Path('/home/runner/work/feature-parity-20260908')
PARENT = 'be181f8e7c01c02bdc3d8c3d45668619642d810a1ce72e07a1796c3de0b6d4e1'
OVERLAY_FILES = {
    'mobile/android/android-components/components/feature/fxsuggest/src/main/java/mozilla/components/feature/fxsuggest/FxSuggestAdmission.kt',
    'mobile/android/android-components/components/feature/fxsuggest/src/test/java/mozilla/components/feature/fxsuggest/FxSuggestAdmissionTest.kt',
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    require(subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm', 'requires KVM')
    require(pwd.getpwuid(os.getuid()).pw_name == 'runner', 'requires guest runner')
    os.environ['XDG_RUNTIME_DIR'] = '/run/user/' + str(os.getuid())
    require(not subprocess.check_output(['podman', '--remote=false', 'ps', '-q'], text=True).strip(), 'container active')
    repo, source = WORK/'repo', WORK/'src'
    correction = repo/'docs/android/evidence/lw-m7-21/admission-copy-correction'
    overlay = json.loads((correction/'source-overlay.json').read_text())
    entries = {entry['path']: entry for entry in overlay['files']}
    require(set(entries) == OVERLAY_FILES, 'unexpected changed source scope')
    require(sha(repo/'patches/android/firefox-suggest-policy.patch') == overlay['patch_sha256'], 'patch changed')
    evidence = WORK/'evidence/apk-admission-copy-source'
    parent = WORK/'evidence/apk-resource-source/source-sha256.txt'
    require(sha(parent) == PARENT, 'resource-only parent source differs')
    rows = {}
    for line in parent.read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(name not in rows and not Path(name).is_absolute() and '..' not in Path(name).parts, 'invalid path')
        rows[name] = digest
    require(len(rows) == 165 and OVERLAY_FILES <= rows.keys(), 'unexpected source manifest')
    native = json.loads((WORK/'evidence/native4-terminal/result.json').read_text())
    require(native['status'] == 'PASS' and native['invocation'] == 'ccc5207e78634d29bcb93761796c9542', 'native checkpoint differs')
    native_inputs = {str(WORK/'aar'/abi/'target.maven.zip'): item['sha256'] for abi, item in native['artifacts'].items()}
    require(all(sha(Path(path)) == digest for path, digest in native_inputs.items()), 'native artifact changed')
    after = dict(rows)
    for name, entry in entries.items():
        require(rows[name] == entry['before_sha256'], 'changed file baseline differs')
        require(sha(correction/Path(name).name) == entry['after_sha256'], 'correction input changed')
        after[name] = entry['after_sha256']
    binding = {'parent_manifest_sha256': PARENT, 'overlay_sha256': sha(correction/'source-overlay.json'),
               'native_inputs': native_inputs, 'changed_files': overlay['files']}
    if evidence.exists():
        saved = json.loads((evidence/'receipt.json').read_text())
        require(saved['status'] == 'PASS' and saved['binding'] == binding, 'existing correction receipt differs')
        require(all(sha(source/name) == digest for name, digest in after.items()), 'corrected source differs')
        require(sha(evidence/'source-sha256.txt') == saved['source_manifest_sha256'], 'correction manifest changed')
        print('PASS existing two-file admission correction verified')
        return
    failed = WORK/'evidence/parity-extended-apk'
    require((failed/'build-exit.txt').read_text().strip() == '1' and (failed/'finished.txt').is_file(), 'APK failure not terminal')
    require(sha(failed/'source-sha256.txt') == PARENT, 'failed APK source differs')
    require(all(sha(source/name) == digest for name, digest in rows.items()), 'parent source changed')
    evidence.mkdir()
    (evidence/'parent-source-sha256.txt').write_bytes(parent.read_bytes())
    for name in entries:
        target = source/name
        (evidence/(Path(name).name+'.before')).write_bytes(target.read_bytes())
        target.write_bytes((correction/Path(name).name).read_bytes())
    require(all(sha(source/name) == digest for name, digest in after.items()), 'correction staging differs')
    require(all(sha(Path(path)) == digest for path, digest in native_inputs.items()), 'native archive changed during stage')
    (evidence/'source-sha256.txt').write_text(''.join(digest+'  '+name+'\n' for name, digest in sorted(after.items())))
    receipt = {'status': 'PASS', 'scope': 'Two Android Components Kotlin files staged; APK compilation/tests/runtime pending. Native4 source evidence remains immutable.',
               'binding': binding, 'source_count': len(after), 'source_manifest_sha256': sha(evidence/'source-sha256.txt'),
               'finished': datetime.now(timezone.utc).isoformat()}
    (evidence/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS staged two Android Components files;165 exact source bindings and unchanged native AARs')


if __name__ == '__main__':
    main()
