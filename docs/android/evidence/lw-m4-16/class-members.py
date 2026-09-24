import struct, sys
def parse(path):
    b = open(path,'rb').read()
    assert b[:4] == b'\xca\xfe\xba\xbe', "not a class file"
    p = 8
    cpc = struct.unpack_from('>H', b, p)[0]; p += 2
    cp = {}
    i = 1
    while i < cpc:
        tag = b[p]; p += 1
        if tag == 1:
            n = struct.unpack_from('>H', b, p)[0]; p += 2
            cp[i] = b[p:p+n].decode('utf-8','replace'); p += n
        elif tag in (3,4,9,10,11,12,17,18): p += 4
        elif tag in (5,6): p += 8; i += 1
        elif tag in (7,8,16,19,20): p += 2
        elif tag == 15: p += 3
        else: raise SystemExit("unknown cp tag %d at %d" % (tag,p))
        i += 1
    p += 6  # access, this, super
    ic = struct.unpack_from('>H', b, p)[0]; p += 2 + 2*ic
    def skip_members(p):
        cnt = struct.unpack_from('>H', b, p)[0]; p += 2
        names = []
        for _ in range(cnt):
            _acc, nidx, _didx, acnt = struct.unpack_from('>HHHH', b, p); p += 8
            names.append(cp[nidx])
            for _ in range(acnt):
                _an, alen = struct.unpack_from('>HI', b, p); p += 6 + alen
        return names, p
    fields, p = skip_members(p)
    methods, p = skip_members(p)
    utf8 = [v for v in cp.values() if isinstance(v,str)]
    return fields, methods, utf8

f, m, u = parse(sys.argv[1])
print("FIELDS  (%d): %s" % (len(f), sorted(f)))
print("METHODS (%d): %s" % (len(m), sorted(m)))
gms_members = sorted(x for x in set(f)|set(m) if 'gms' in x.lower())
print("GMS-named members: %s" % gms_members)
print("GMS utf8 constants: %s" % sorted(s for s in u if 'com.google.android.gms' in s or 'com/google/android/gms' in s))
