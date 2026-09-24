import io,json,tarfile,hashlib,subprocess
from pathlib import Path
w=Path('/home/runner/work/feature-parity-20260908');data={}
for suffix in ['creditcard-diagnostic-20260909','cookie-creditcard-diagnostic-20260909']:
 p=w/'evidence'/suffix
 assert (p/'finished.txt').is_file()
 for f in p.iterdir():
  if f.is_file():data[suffix+'/'+f.name]=f.read_bytes()
for name in ['mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/view/ViewHolder.kt','mobile/android/fenix/app/src/main/res/layout/credit_card_list_item.xml']:
 data['source/'+name]=(w/'src'/name).read_bytes()
result={name:{'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)} for name,body in data.items()}
data['files.json']=(json.dumps(result,indent=2)+'\n').encode()
import sys
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for name,body in data.items():
  m=tarfile.TarInfo(name);m.size=len(body);t.addfile(m,io.BytesIO(body))
