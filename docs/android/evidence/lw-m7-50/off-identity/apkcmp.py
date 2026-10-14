import zipfile,hashlib,sys,json
a,b=sys.argv[1],sys.argv[2]
def ents(p):
    z=zipfile.ZipFile(p); return {i.filename:hashlib.sha256(z.read(i.filename)).hexdigest() for i in z.infolist()}
A,B=ents(a),ents(b)
same=[k for k in A if k in B and A[k]==B[k]]; diff=[k for k in A if k in B and A[k]!=B[k]]
print("entries local=%d beta2=%d identical=%d differ=%d only-local=%d only-beta2=%d"%(len(A),len(B),len(same),len(diff),len(set(A)-set(B)),len(set(B)-set(A))))
for k in sorted(diff): print("DIFF",k)
for k in sorted(set(A)-set(B)): print("ONLY-LOCAL",k)
for k in sorted(set(B)-set(A)): print("ONLY-BETA2",k)
