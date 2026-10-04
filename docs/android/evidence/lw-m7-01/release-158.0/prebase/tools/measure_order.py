#!/usr/bin/env python3
"""Re-measure every shared-file pair of the common+android and common+desktop
sequences on a pristine Firefox tree, the way _M157_ANDROID was measured:
per shared file, that file's hunks of every entry in list order (android
entries at --fuzz=0, common/desktop at patch's default), then with B moved
directly before A, then with A moved directly after B.

usage: measure_order.py PRISTINE_TREE OUT.json
"""
import hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(os.environ.get("REPO", Path(__file__).resolve().parent.parent / "repo"))
spec = importlib.util.spec_from_file_location("cpo", REPO / "scripts/check-patch-order.py")
cpo = importlib.util.module_from_spec(spec)
sys.argv_saved = sys.argv
spec.loader.exec_module(cpo)

pristine = Path(sys.argv[1]); out = sys.argv[2]

def section(patch, f):
    r = subprocess.run(["filterdiff", "--strip=1", "--addprefix=a/", "-i", f, str(REPO / patch)],
                       capture_output=True)
    # filterdiff rewrites paths; keep both prefixes usable by patch -p1
    return r.stdout

_cache = {}
def sec(patch, f):
    k = (patch, f)
    if k not in _cache:
        r = subprocess.run(["filterdiff", "-p1", "-i", f, str(REPO / patch)], capture_output=True)
        _cache[k] = r.stdout
    return _cache[k]

def replay(seq, f):
    with tempfile.TemporaryDirectory(dir="/home/mgysin/redoubt-artifacts/ff158/work") as d:
        d = Path(d)
        src = pristine / f
        dst = d / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copyfile(src, dst)
        for p in seq:
            s = sec(p, f)
            if not s.strip():
                continue
            fz = ["--fuzz=0"] if p.startswith("patches/android/") else []
            r = subprocess.run(["patch", "-p1", "--no-backup-if-mismatch", "-r", "-", *fz],
                               cwd=d, input=s, capture_output=True)
            if r.returncode != 0:
                return ("REJECT", p)
        return ("OK", hashlib.sha256(dst.read_bytes()).hexdigest() if dst.exists() else "absent")

results = []
for target in ("android", "desktop"):
    seq = cpo.read_patch_list("common") + cpo.read_patch_list(target)
    files = {p: set(cpo.parse_patch(p)) for p in seq}
    common = set(cpo.read_patch_list("common"))
    for i, a in enumerate(seq):
        for b in seq[i + 1:]:
            shared = sorted(files[a] & files[b])
            if not shared:
                continue
            # common/common pairs are measured once, in the android run
            if target == "desktop" and a in common and b in common:
                continue
            ia, ib = seq.index(a), seq.index(b)
            b_before_a = seq[:ia] + [b, a] + [x for x in seq[ia + 1:] if x != b]
            a_after_b = [x for x in seq[:ib + 1] if x != a] + [a] + seq[ib + 1:]
            per = {}
            for f in shared:
                base = replay(seq, f)
                s1 = replay(b_before_a, f)
                s2 = replay(a_after_b, f)
                def verdict(s):
                    if s[0] != "OK":
                        return "reject@" + s[1]
                    return "same" if s == base else "differs"
                per[f] = {"list": base[0] if base[0] != "OK" else "ok",
                          "list_reject": base[1] if base[0] != "OK" else None,
                          "b_before_a": verdict(s1), "a_after_b": verdict(s2)}
            results.append({"target": target, "a": a, "b": b, "files": per})
            print(target, a, b, json.dumps(per), flush=True)
json.dump(results, open(out, "w"), indent=1)
