#!/usr/bin/env python3
"""Per-file swap measurement: replay every list entry touching FILE (in list order) on the
pristine FILE, then again with A and B swapped; report patch exit codes and result sha256."""
import hashlib, os, re, subprocess, sys, tempfile, shutil
R=os.path.expanduser('~/redoubt-artifacts/rebase-161.0'); REPO=R+'/repo'; PR=R+'/pristine/firefox-161.0'
def lst(n): return [l.split('#',1)[0].strip() for l in open(f'{REPO}/assets/patches/{n}.txt') if l.split('#',1)[0].strip()]
seq=lst('common')+lst('android')
def hunks_for(patch, f):
    L=open(f'{REPO}/{patch}',errors='replace').read().splitlines(True)
    out=[];cur=False;i=0
    while i<len(L):
        l=L[i]
        if l.startswith('--- ') and i+1<len(L) and L[i+1].startswith('+++ '):
            path=L[i+1][4:].split('\t')[0].strip()
            path=path[2:] if path.startswith(('a/','b/')) else path
            cur=(path==f)
            if cur: out+= [L[i],L[i+1]]
            i+=2; continue
        if l.startswith('diff ') : cur=False
        elif cur: out.append(l)
        i+=1
    return ''.join(out)
def run(order,f):
    d=tempfile.mkdtemp(); os.makedirs(os.path.dirname(f'{d}/{f}'),exist_ok=True)
    if os.path.exists(f'{PR}/{f}'): shutil.copy(f'{PR}/{f}',f'{d}/{f}')
    rcs=[]
    for p in order:
        h=hunks_for(p,f)
        if not h: continue
        r=subprocess.run(['patch','-p1','-s','-f','--no-backup-if-mismatch','-r','-','--fuzz=0','-d',d],input=h,text=True,capture_output=True)
        rcs.append((os.path.basename(p),r.returncode))
    data=open(f'{d}/{f}','rb').read() if os.path.exists(f'{d}/{f}') else b''
    shutil.rmtree(d); return rcs, hashlib.sha256(data).hexdigest()[:12]
A,B=sys.argv[1],sys.argv[2]
for f in sys.argv[3:]:
    o=[p for p in seq if hunks_for(p,f)]
    s=[p for p in o if p!=B]; s.insert(s.index(A),B)  # B moved directly before A
    r1,h1=run(o,f); r2,h2=run(s,f)
    bad1=[x for x in r1 if x[1]]; bad2=[x for x in r2 if x[1]]
    verdict='ORDER-FREE (byte-identical)' if h1==h2 and not bad1 and not bad2 else ('LIST-ORDER-REQUIRED' if not bad1 else 'LIST ORDER FAILS')
    print(f'{f}: list {h1} rej={bad1} | swapped {h2} rej={bad2} -> {verdict}')
