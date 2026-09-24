from pathlib import Path
import hashlib,json,subprocess,tarfile
repo=Path('/home/mgysin/Documents/librewolf')
actual=repo/'librewolf-153.0esr-1-beta-20260908'
work=Path('/home/mgysin/redoubt-artifacts/lw-m6-08-session/patch-source-check')
work.mkdir(exist_ok=True)
patches=[]
for name in ('common','android'):
    for line in (repo/f'assets/patches/{name}.txt').read_text().splitlines():
        line=line.split('#')[0].strip()
        if line:patches.append(repo/line)
paths=set()
for p in patches:
    for line in p.read_text().splitlines():
        if line.startswith(('--- a/','+++ b/')):
            paths.add(line[6:].split('\t')[0].split(' ')[0])
found=[]
with tarfile.open(repo/'firefox-153.0esr.source.tar.xz','r|xz') as archive:
    for m in archive:
        rel=m.name.split('/',1)[-1]
        if rel in paths and m.isfile():
            out=work/rel;out.parent.mkdir(parents=True,exist_ok=True)
            out.write_bytes(archive.extractfile(m).read());found.append(rel)
with (work/'apply.log').open('w') as log:
    for p in patches:
        subprocess.run(['patch','--batch','-p1','-i',str(p)],cwd=work,stdout=log,stderr=subprocess.STDOUT,check=True)
rows=[]
for rel in sorted(paths):
    a,b=work/rel,actual/rel
    ha=hashlib.sha256(a.read_bytes()).hexdigest() if a.is_file() else None
    hb=hashlib.sha256(b.read_bytes()).hexdigest() if b.is_file() else None
    rows.append(dict(path=rel,from_pinned_tarball_and_patches=ha,candidate_source=hb,match=ha==hb))
out=repo/'docs/android/evidence/lw-m6-08/patch-source-comparison.json'
out.write_text(json.dumps(dict(patches=[str(p.relative_to(repo)) for p in patches],compared=len(rows),mismatches=[r for r in rows if not r['match']],files=rows),indent=2)+'\n')
print(f'{len(patches)} patches, {len(rows)} source paths, {sum(not r["match"] for r in rows)} differences',flush=True)
for r in rows:
    if not r['match']:print(r['path'])
