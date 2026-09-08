#!/usr/bin/env python3
"""Apply only the compiler correction to the already integrated guest source."""
import hashlib
import json
from pathlib import Path
import subprocess

WORK = Path('/home/runner/work/feature-parity-20260908')
SOURCE = WORK / 'src'
INPUT = WORK / 'repo/docs/android/evidence/lw-m7-21'
OUTPUT = WORK / 'evidence/translation-cancellation-fix'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert subprocess.check_output(['id', '-un'], text=True).strip() == 'runner'
assert subprocess.check_output(['systemd-detect-virt', '--vm'], text=True).strip() == 'kvm'
OUTPUT.mkdir(exist_ok=False)
manifest = WORK / 'evidence/extended-source/source-sha256.txt'
check = subprocess.run(['sha256sum', '-c', str(manifest)], cwd=SOURCE,
                       capture_output=True, text=True)
(OUTPUT / 'source-before.txt').write_text(check.stdout + check.stderr)
check.check_returncode()
lineage = json.loads((INPUT / 'translation-cancellation-lineage.json').read_text())
path = SOURCE / lineage['path']
delta = INPUT / 'translation-cancellation-fix.patch'
assert sha(path) == lineage['before_sha256']
assert sha(delta) == lineage['delta_sha256']
assert sha(WORK / 'repo/patches/android/translation-assets.patch') == lineage['new_patch_sha256']
(OUTPUT / 'TranslationsController.java.before').write_bytes(path.read_bytes())
(OUTPUT / 'lineage.json').write_text(json.dumps(lineage, indent=2) + '\n')
for dry in (True, False):
    command = ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(delta)]
    if dry:
        command.append('--dry-run')
    result = subprocess.run(command, cwd=SOURCE, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True)
    (OUTPUT / f'patch-{"dry" if dry else "apply"}.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    assert 'offset' not in result.stdout and 'fuzz' not in result.stdout
assert sha(path) == lineage['after_sha256']
old_line = f"{lineage['before_sha256']}  {lineage['path']}\n"
new_line = f"{lineage['after_sha256']}  {lineage['path']}\n"
contents = manifest.read_text()
assert contents.count(old_line) == 1
new_manifest = OUTPUT / 'source-sha256.txt'
new_manifest.write_text(contents.replace(old_line, new_line))
check = subprocess.run(['sha256sum', '-c', str(new_manifest)], cwd=SOURCE,
                       capture_output=True, text=True)
(OUTPUT / 'source-after.txt').write_text(check.stdout + check.stderr)
check.check_returncode()
print('PASS translation correction applied; all 89 source/asset hashes verified')
