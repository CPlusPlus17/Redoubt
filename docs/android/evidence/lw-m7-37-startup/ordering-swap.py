import subprocess, shutil, hashlib, sys, os, re
ROOT='/home/user/Redoubt'; PR=sys.argv[1]  # pristine dir
lists=[]
for l in ('common.txt','android.txt'):
    for line in open(f'{ROOT}/assets/patches/{l}'):
        line=line.split('#',1)[0].strip()
        if line: lists.append(line.split()[0])
C='patches/android/interrupted-session-cleanup.patch'
def files(p): return {m for m in re.findall(r'(?m)^\+\+\+ b/(\S+)', open(f'{ROOT}/{p}').read())}
def run(order, work):
    shutil.rmtree(work, ignore_errors=True); shutil.copytree(PR, work)
    for p in order:
        r=subprocess.run(['patch','-p1','--no-backup-if-mismatch','-r','-','-i',f'{ROOT}/{p}'],cwd=work,capture_output=True,text=True)
        if r.returncode: return p
    return None
base=f'{PR}-base'; assert run(lists, base) is None
for partner in ['patches/android/fission-isolation.patch','patches/android/no-adjust.patch','patches/android/no-crashreporter.patch','patches/android/no-glean.patch','patches/android/no-gms.patch','patches/android/ubo-preinstall.patch','patches/android/sync-opt-in.patch','patches/android/firefox-suggest-policy.patch']:
    order=[p for p in lists if p!=C]; order.insert(order.index(partner), C)
    fail=run(order, f'{PR}-swap')
    shared=sorted(files(C)&files(partner))
    if fail: print(f'{partner}: swapped order FAILS at {fail}; shared {len(shared)}'); continue
    same=all(open(f'{base}/{f}','rb').read()==open(f'{PR}-swap/{f}','rb').read() for f in shared)
    print(f'{partner}: swapped order applies; shared {len(shared)} identical={same}')
