"""Capture the separately pinned harness retry configuration in the guest."""
from pathlib import Path
import json
import subprocess
import sys

work = Path('/home/runner/work/feature-parity-20260908')
data = subprocess.check_output([
    'python3', 'docs/android/evidence/lw-m7-12/harness-process-recovery/runtime.py',
    '--print-config',
], cwd=work/'repo')
config = json.loads(data)
assert config['kind'] == 'runtime'
assert config['source_sha256'] == '4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739'
assert config['apk_service']['InvocationID'] == '598783f0987b4c139fb0053c501f5628'
assert config['test_service']['InvocationID'] == 'c02a8b984fae45dc859eff2b556b82f0'
with (work/'harness-process-runtime-inputs.json').open('xb') as stream:
    stream.write(data)
sys.stdout.buffer.write(data)
