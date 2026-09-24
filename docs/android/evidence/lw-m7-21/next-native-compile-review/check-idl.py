import sys
sys.dont_write_bytecode = True
import hashlib, io, json, subprocess, tarfile
from pathlib import Path
here=Path(__file__).resolve().parent
source=Path('/home/mgysin/Documents/librewolf/librewolf-153.0esr-1-beta-20260908')
repo=Path('/home/mgysin/redoubt-artifacts/feature-parity/lw-m7-36-process-lineage/repo')
handoff=Path('/home/mgysin/redoubt-artifacts/feature-parity/post-native4-composition-process-with37-20260909/handoff')
sys.path[:0]=[str(source/'xpcom/idl-parser'),str(source/'third_party/python/ply')]
from xpidl import xpidl, header
rows=json.loads((repo/'docs/android/evidence/lw-m7-37/native-source-files.json').read_bytes())['files']
with tarfile.open(handoff/'composed-source-subset.tar.gz','r:gz') as t:
 bodies={r['path']:t.extractfile(r['path']).read() for r in rows}
for r in rows: assert hashlib.sha256(bodies[r['path']]).hexdigest()==r['after_sha256']
incdirs=sorted({str(Path(n).parent) for n in subprocess.check_output(['rg','--files','--hidden','--no-ignore','-g','*.idl',str(source)],text=True).splitlines()})
parser=xpidl.IDLParser();name='netwerk/cookie/nsICookieManager.idl';idl=parser.parse(bodies[name].decode(),filename=name);idl.resolve(incdirs,parser,None)
out=io.StringIO();header.print_header(idl,out,'nsICookieManager.idl','netwerk/cookie');(here/'nsICookieManager.generated.h').write_text(out.getvalue())
methods=[line.strip() for line in out.getvalue().splitlines() if 'SessionCleanup' in line and line.strip().startswith('NS_IMETHOD')]
(here/'idl-result.json').write_text(json.dumps({'scope':'Host XPIDL parse/resolve/C++ declaration generation only. No C++/Kotlin compiler or target execution.','generated_methods':methods,'source_sha256':hashlib.sha256(bodies[name]).hexdigest(),'generator_sha256':hashlib.sha256((source/'xpcom/idl-parser/xpidl/header.py').read_bytes()).hexdigest(),'parser_sha256':hashlib.sha256((source/'xpcom/idl-parser/xpidl/xpidl.py').read_bytes()).hexdigest(),'includes':[{ 'path':str(p), 'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in idl.deps if Path(p).is_file()]},indent=2)+'\n')
print('\n'.join(methods));print('PASS host XPIDL declaration generation only; actual native compilation pending.')
