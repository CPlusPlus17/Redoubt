"""Capture completed APK resource checks while separate target tests may run."""
import datetime
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

work = Path('/home/runner/work/feature-parity-20260908')
folder = work / 'evidence/apk-resource-verification-recovery'
apk = work / 'evidence/parity-extended-apk'
assert (work / 'evidence/apk-resource-recovery-checkpoint/resources-exit.txt').read_text().strip() == '0'
assert (apk / 'finished.txt').is_file() and (apk / 'build-exit.txt').read_text().strip() == '0'
sha = lambda data: hashlib.sha256(data).hexdigest()
result = json.loads((folder / 'result.json').read_text())
assert result['parent_compile_invocation'] == '202a41bedcc148ef9faf7d2180eec463'
assert result['source_manifest_sha256'] == 'c53736e87152ba6de7ae232efd0a26197601027e4553be3f5f4bd7e6045601ae'
assert (folder / 'result.json').read_bytes() == (apk / 'resource-verification-recovery.json').read_bytes()
manifest = (apk / 'source-sha256.txt').read_bytes()
assert sha(manifest) == result['source_manifest_sha256']
rows = [line.split('  ', 1) for line in manifest.decode().splitlines()]
assert len(rows) == 165
for expected, name in rows:
    assert sha((work / 'src' / name).read_bytes()) == expected, name
for name, row in result['checks'].items():
    assert row['exit'] == 0 and sha((folder / (name + '.log')).read_bytes()) == row['log_sha256']
    with (work / 'out/apk' / name).open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['apk']['sha256'], name
capture = {}
for directory, prefix in [(folder, 'resource-recovery'), (apk, 'completed-apk')]:
    for path in directory.iterdir():
        if path.is_file():
            capture[prefix + '/' + path.name] = path.read_bytes()
for name in ['resources.log', 'resources-exit.txt', 'started.txt']:
    capture['checkpoint/' + name] = (work / 'evidence/apk-resource-recovery-checkpoint' / name).read_bytes()
inputs_path = work / 'repo/docs/android/evidence/lw-m7-21/apk-resource-recovery-inputs.json'
assert sha(inputs_path.read_bytes()) == result['inputs_sha256']
inputs = json.loads(inputs_path.read_text())
for name, expected in inputs['repository_files'].items():
    data = (work / 'repo' / name).read_bytes()
    assert sha(data) == expected, name
    capture['configuration/' + name] = data
assert sha((work / inputs['aapt2_path']).read_bytes()) == inputs['aapt2_sha256']
for expected, name in rows:
    assert sha((work / 'src' / name).read_bytes()) == expected, name
receipt = {
    'actor': '/root', 'scope': 'Four completed APK resource checks only; concurrent full tests and runtime results excluded.',
    'captured': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'source_checked_before_after': 165, 'resource_recovery': result,
    'files': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in capture.items()},
}
capture['capture.json'] = (json.dumps(receipt, indent=2) + '\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
    for name, data in capture.items():
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
