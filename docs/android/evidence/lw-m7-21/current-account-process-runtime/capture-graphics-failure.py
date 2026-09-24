from pathlib import Path
import io,tarfile,sys,json,hashlib
root=Path('/home/runner/work/feature-parity-20260908/account-process-runtime/smoke-baseline/graphics-acceptance')
files={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
assert len(files)==5
r=json.loads(files['53bcdfbe4aace91c/graphics-results.json']);assert r['status']=='FAIL' and r['checks']==[] and r['reason']=="'list' object has no attribute 'get'"
for row in r['artifacts']:
 data=files['53bcdfbe4aace91c/'+row['path']];assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
files['capture-result.json']=(json.dumps({'status':'FAIL actual graphics harness before any graphics check','files':{n:{'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)} for n,b in files.items()}},indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for n,b in files.items():
  m=tarfile.TarInfo(n);m.size=len(b);t.addfile(m,io.BytesIO(b))
