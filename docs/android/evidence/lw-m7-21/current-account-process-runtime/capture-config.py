from pathlib import Path
import subprocess,sys,json
w=Path('/home/runner/work/feature-parity-20260908')
b=subprocess.check_output(['python3','docs/android/evidence/lw-m7-12/current167-process-recovery/runtime.py','--print-config'],cwd=w/'repo')
assert json.loads(b)['kind']=='runtime'
with (w/'account-process-runtime-inputs.json').open('xb') as f:f.write(b)
sys.stdout.buffer.write(b)
