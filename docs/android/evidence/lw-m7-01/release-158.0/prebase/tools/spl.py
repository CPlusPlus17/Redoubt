import sys,re
def load(p):
    d={};name=None;cond=[]
    for l in open(p,errors='replace'):
        m=re.match(r'^- name:\s*(\S+)',l)
        if m: name=m.group(1); d.setdefault(name,[]); continue
        m=re.match(r'^\s+value:\s*(.*)',l)
        if m and name: d[name].append(m.group(1).strip()); continue
        m=re.match(r'^#(if|ifdef|ifndef|elif|else|endif)\b(.*)',l)
        if m and name: d[name].append('#'+m.group(1)+m.group(2).strip())
    return d
a=load(sys.argv[1]); b=load(sys.argv[2])
for n in sorted(set(a)|set(b)):
    if n not in a: print("ADDED  ",n,b[n])
    elif n not in b: print("REMOVED",n,a[n])
    elif a[n]!=b[n]: print("CHANGED",n,a[n],'->',b[n])
