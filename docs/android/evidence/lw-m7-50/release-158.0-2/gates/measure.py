#!/usr/bin/env python3
# measure.py FILE A B : replay FILE's hunks of every common+android list entry
# in list order vs B-moved-directly-before-A vs A-moved-directly-after-B.
import subprocess, sys, tempfile, hashlib, os, shutil
REPO=os.path.expanduser('~/redoubt-artifacts/iso-158-2/repo')
PRIS=os.path.expanduser('~/redoubt-artifacts/iso-158-2/work/pristine/firefox-158.0')
def lst(n):
    out=[]
    for l in open(f'{REPO}/assets/patches/{n}.txt'):
        l=l.split('#')[0].strip()
        if l: out.append(l)
    return out
seq=[(p,'common') for p in lst('common')]+[(p,'android') for p in lst('android')]
F,A,B=sys.argv[1:4]
def touching(p):
    r=subprocess.run(['lsdiff','--strip=1',f'{REPO}/{p}'],capture_output=True,text=True).stdout.split()
    return F in r
s=[x for x in seq if touching(x[0])]
def run(order):
    d=tempfile.mkdtemp()
    os.makedirs(os.path.dirname(f'{d}/{F}'),exist_ok=True)
    shutil.copy(f'{PRIS}/{F}',f'{d}/{F}')
    for p,k in order:
        sub=subprocess.run(['filterdiff','-i','a/'+F,f'{REPO}/{p}'],capture_output=True,text=True).stdout
        args=['patch','-p1','-s','-d',d,'--no-backup-if-mismatch','-r','-']+(['--fuzz=0'] if k=='android' else [])
        r=subprocess.run(args,input=sub,capture_output=True,text=True)
        if r.returncode: return 'REJECT at %s: %s'%(p,(r.stdout+r.stderr).strip()[:200])
    h=hashlib.sha256(open(f'{d}/{F}','rb').read()).hexdigest()
    shutil.rmtree(d); return h
names=[p for p,_ in s]
ia,ib=names.index(A),names.index(B)
base=run(s)
o1=s[:ia]+[s[ib]]+[x for x in s[ia:] if x[0]!=B]
o2=[x for x in s[:ib+1] if x[0]!=A]+[s[ia]]+s[ib+1:]
r1,r2=run(o1),run(o2)
print(F, 'patches touching:', len(s))
print(' list order       ', base)
print(' B before A       ', r1, 'IDENTICAL' if r1==base else '')
print(' A after B        ', r2, 'IDENTICAL' if r2==base else '')
