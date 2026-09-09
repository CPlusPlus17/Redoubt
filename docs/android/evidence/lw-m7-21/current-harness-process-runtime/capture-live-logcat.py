"""Read-only, bounded host capture from the runtime's already-created emulator."""
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

here = Path(__file__).resolve().parent
unit = 'redoubt-harness-process-runtime-20260909.service'
invocation = '0189d8626a9a4a38b540d037781d3c45'
service = subprocess.check_output([
    './scripts/ci-vm/ssh.sh', 'sudo -iu runner env XDG_RUNTIME_DIR=/run/user/1001 '
    'systemctl --user show '+unit+' --property=InvocationID,SubState',
], text=True)
assert 'InvocationID='+invocation in service and 'SubState=running' in service
command = ['./scripts/ci-vm/ssh.sh', 'sudo -iu runner timeout 180 '
           '/home/runner/work/feature-parity-20260908/sdk/platform-tools/adb '
           '-s emulator-5584 logcat -v threadtime']
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
raw_hash = hashlib.sha256()
size = 0
with (here/'startup-logcat.txt.gz').open('xb') as target:
    with gzip.GzipFile(fileobj=target, mode='wb', mtime=0) as compressed:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while data := process.stdout.read(65536):
            compressed.write(data)
            raw_hash.update(data)
            size += len(data)
        error = process.stderr.read().decode(errors='replace')
        code = process.wait()
record = {'scope': 'Read-only logcat capture; its timeout/exit is not a runtime gate',
          'runtime_invocation': invocation, 'serial': 'emulator-5584', 'command': command,
          'started': started, 'finished': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'reader_exit': code, 'stderr': error, 'raw_bytes': size,
          'raw_sha256': raw_hash.hexdigest(),
          'gzip_sha256': hashlib.sha256((here/'startup-logcat.txt.gz').read_bytes()).hexdigest()}
(here/'startup-logcat-capture.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({key: record[key] for key in ['reader_exit', 'raw_bytes', 'raw_sha256']}))
