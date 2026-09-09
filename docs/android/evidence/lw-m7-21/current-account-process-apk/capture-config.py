"""Capture the source/test selection only after the actual full suite passes."""
from pathlib import Path
import subprocess
import sys
import json

work = Path('/home/runner/work/feature-parity-20260908')
command = [
    'python3', 'docs/android/evidence/lw-m7-12/current167-process-recovery/build.py',
    '--print-config', '--source-stage', str(work/'evidence/account-process-source'),
    '--test-evidence', str(work/'evidence/account-process-tests'),
    '--source-manifest-sha256', '4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739',
    '--test-service-name', 'redoubt-fenix-account-process-tests-20260909.service',
    '--test-invocation', 'c02a8b984fae45dc859eff2b556b82f0',
    '--native-manifest', str(work/'evidence/fenix-regression-source/native-input-sha256.txt'),
]
data = subprocess.check_output(command, cwd=work/'repo')
assert json.loads(data)['kind'] == 'apk'
with (work/'account-process-apk-inputs.json').open('xb') as stream:
    stream.write(data)
sys.stdout.buffer.write(data)
