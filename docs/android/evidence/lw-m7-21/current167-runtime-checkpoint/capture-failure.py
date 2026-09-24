import io,tarfile,json,hashlib,subprocess,sys,os
from pathlib import Path
w=Path('/home/runner/work/feature-parity-20260908');os.environ['XDG_RUNTIME_DIR']='/run/user/1001'
e=w/'evidence/fenix-regression-runtime';state=json.loads((e/'result.json').read_text());assert state['status']=='FAIL' and state['stages']['ubo-lifecycle']['exit']==2 and state['emulator_cleanup_exit']==0
unit='redoubt-fenix-regression-runtime-20260909.service'
files={'service.txt':subprocess.check_output(['systemctl','--user','show',unit,'-p','InvocationID','-p','ActiveState','-p','SubState','-p','ExecMainStatus','-p','ExecMainStartTimestamp','-p','ExecMainExitTimestamp']),'journal.txt':subprocess.check_output(['journalctl','--user','--no-pager','-u',unit])}
assert b'InvocationID=9513a070506a4a29baf9848b2ea7e8eb' in files['service.txt'] and b'SubState=exited' in files['service.txt']
for file in e.iterdir():
 if file.is_file():files['runtime-checkpoint/'+file.name]=file.read_bytes()
for folder in ['smoke-first-navigation','smoke-baseline']:
 for file in (w/'fenix-regression-runtime'/folder).iterdir():
  if file.is_file():files['runtime-work/'+folder+'/'+file.name]=file.read_bytes()
for h,n in [r.split('  ',1) for r in (e/'source-sha256.txt').read_text().splitlines()]:assert hashlib.sha256((w/'src'/n).read_bytes()).hexdigest()==h
result={'status':'FAIL actual isolated Gecko child startup; uBO harness timed out and exited2. Root interrupted remaining baseline after confirmed repeated crash; pref audit not run. Emulator cleanup succeeded.','source_manifest_sha256':state['source_manifest']['sha256'],'invocation':'9513a070506a4a29baf9848b2ea7e8eb','files':{n:{'sha256':hashlib.sha256(d).hexdigest(),'bytes':len(d)} for n,d in files.items()}}
files['capture-result.json']=(json.dumps(result,indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for name,data in files.items():
  member=tarfile.TarInfo(name);member.size=len(data);t.addfile(member,io.BytesIO(data))
