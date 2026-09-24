from pathlib import Path
import os,json,hashlib,datetime,subprocess
root=Path('/home/runner/work/feature-parity-20260908/src');manifest=root.parent/'evidence/fenix-navigation-fixture-source/source-sha256.txt'
assert subprocess.check_output(['systemd-detect-virt','--vm'],text=True).strip()=='kvm'
assert hashlib.sha256(manifest.read_bytes()).hexdigest()=='501d04614edbc847b416cd5b6f1dac42dd0728a63125a3d9902c90d07a579c8b'
rows=[line.split('  ',1) for line in manifest.read_text().splitlines()]
for h,n in rows:assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h
links=[];dirs=0
for current,children,files in os.walk(root,followlinks=False):
 parent=Path(current)
 children[:]=[n for n in children if n not in {'.git','.hg','.gradle'} and not(parent==root and n.startswith('obj-'))]
 dirs+=1
 for name in children+files:
  child=parent/name
  if child.is_symlink() and (child.is_dir() or not child.resolve().is_relative_to(root)):
   links.append({'path':str(child.relative_to(root)),'directory':child.is_dir(),'target':os.readlink(child)})
for h,n in rows:assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h
print(json.dumps({'actor':'/root','operation':'read-only guest source traversal via ssh; no systemd service or source copy','captured':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'source_count':len(rows),'source_checked_before_after':True,'directories_scanned':dirs,'private_copy_review_required':links,'scope':'Early source-copy compatibility observation only. Actual copy/build and fresh source checks remain required.'},indent=2))
