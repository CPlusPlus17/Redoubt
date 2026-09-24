import subprocess, shutil, hashlib, sys, os, re
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'../../../..')); PR=sys.argv[1]  # pristine dir
C=sys.argv[2] if len(sys.argv)>2 else 'patches/android/interrupted-session-cleanup.patch'
lists=[]
for l in ('common.txt','android.txt'):
    for line in open(f'{ROOT}/assets/patches/{l}'):
        line=line.split('#',1)[0].strip()
        if line: lists.append(line.split()[0])
def files(p): return {m for m in re.findall(r'(?m)^\+\+\+ b/(\S+)', open(f'{ROOT}/{p}').read())}
def run(order, work):
    shutil.rmtree(work, ignore_errors=True); shutil.copytree(PR, work)
    for p in order:
        r=subprocess.run(['patch','-p1','--no-backup-if-mismatch','-r','-','-i',f'{ROOT}/{p}'],cwd=work,capture_output=True,text=True)
        if r.returncode: return p
    return None
base=f'{PR}-base'; assert run(lists, base) is None
partners=[p for p in lists if p!=C and files(p)&files(C)]
for partner in partners:
    order=[p for p in lists if p!=C]; order.insert(order.index(partner), C)
    fail=run(order, f'{PR}-swap')
    shared=sorted(files(C)&files(partner))
    if fail: print(f'{partner}: swapped order FAILS at {fail}; shared {len(shared)}'); continue
    same=all(open(f'{base}/{f}','rb').read()==open(f'{PR}-swap/{f}','rb').read() for f in shared)
    print(f'{partner}: swapped order applies; shared {len(shared)} identical={same}')
