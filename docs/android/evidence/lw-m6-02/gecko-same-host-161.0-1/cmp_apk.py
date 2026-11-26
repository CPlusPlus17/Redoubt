"""Compare two APKs entry by entry.

usage: python3 -I cmp_apk.py A.apk B.apk [OUT_DIR]
Prints identical/differing counts, then each differing or one-sided entry with
sizes and CRCs. With OUT_DIR, extracts both versions of every differing entry
to OUT_DIR/a/<entry> and OUT_DIR/b/<entry> for diffoscope.
Also reports whether zip metadata (order, timestamps, compression) differs.
"""
import hashlib
import os
import sys
import zipfile

a_path, b_path = sys.argv[1], sys.argv[2]
out = sys.argv[3] if len(sys.argv) > 3 else None
za, zb = zipfile.ZipFile(a_path), zipfile.ZipFile(b_path)
ia = {i.filename: i for i in za.infolist()}
ib = {i.filename: i for i in zb.infolist()}


def digest(z, name):
    return hashlib.sha256(z.read(name)).hexdigest()


same, diff = 0, []
for name in sorted(set(ia) | set(ib)):
    if name not in ia or name not in ib:
        diff.append((name, "only in " + ("B" if name not in ia else "A")))
        continue
    x, y = ia[name], ib[name]
    if x.CRC == y.CRC and x.file_size == y.file_size and digest(za, name) == digest(zb, name):
        meta = []
        if x.date_time != y.date_time:
            meta.append("timestamp")
        if x.compress_type != y.compress_type or x.compress_size != y.compress_size:
            meta.append("compression")
        if meta:
            diff.append((name, "content same, " + "+".join(meta) + " differ"))
        else:
            same += 1
        continue
    diff.append((name, "content differs: %d vs %d bytes" % (x.file_size, y.file_size)))
    if out:
        for side, z in (("a", za), ("b", zb)):
            p = os.path.join(out, side, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(z.read(name))

order_same = [i.filename for i in za.infolist()] == [i.filename for i in zb.infolist()]
print("%s vs %s" % (os.path.basename(a_path), os.path.basename(b_path)))
print("file sha256 equal: %s" % (hashlib.sha256(open(a_path, "rb").read()).hexdigest()
                                 == hashlib.sha256(open(b_path, "rb").read()).hexdigest()))
print("entries: A=%d B=%d identical=%d differing=%d entry order same=%s"
      % (len(ia), len(ib), same, len(diff), order_same))
for name, why in diff:
    print("  %-70s %s" % (name, why))
