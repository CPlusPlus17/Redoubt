import zipfile,hashlib,base64,sys,re
z=zipfile.ZipFile(sys.argv[1])
mf=z.read('META-INF/manifest.mf'); sf=z.read('META-INF/mozilla.sf').decode()
def sections(t):
    return [s for s in re.split(r'\r?\n\r?\n',t) if s.strip()]
# sf: digest of whole manifest.mf
m=re.search(r'SHA256-Digest-Manifest: (\S+)',sf); assert base64.b64decode(m.group(1))==hashlib.sha256(mf).digest(),'sf->mf'
entries={}
for s in sections(mf.decode())[1:]:
    name=re.search(r'Name: (.+)',s).group(1).strip()
    d=re.search(r'SHA256-Digest: (\S+)',s).group(1)
    entries[name]=d
files=[n for n in z.namelist() if (not n.startswith("META-INF/") or n.startswith("META-INF/cose.")) and not n.endswith("/")]
assert set(files)==set(entries),(set(files)^set(entries))
for n in files: assert base64.b64decode(entries[n])==hashlib.sha256(z.read(n)).digest(),n
print('JAR manifest OK:',len(files),'files covered')
