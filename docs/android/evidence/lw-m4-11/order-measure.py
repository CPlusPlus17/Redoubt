#!/usr/bin/env python3
"""Measure per-file order-freedom of a NEW android patch against the android.txt sequence.

For every tree file the new patch touches that at least one listed android patch also
touches: replay that file through the sequence in list order (new patch last), then once
more per partner with the new patch moved to just BEFORE that partner. Report sha256 of the
result, patch exit status, fuzz/offset lines, and whether a .rej appeared.

usage: order-measure.py <new-patch> [<pristine-root>]   (pristine-root default: scratchpad/pristine/firefox-153.0)
"""
import hashlib, os, re, subprocess, sys, tempfile, shutil

REPO = "/home/mgysin/Documents/librewolf"
NEW = sys.argv[1]
PRISTINE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "pristine", "firefox-153.0")
TARBALL = os.path.join(REPO, "firefox-153.0esr.source.tar.xz")

def listed():
    out = []
    for line in open(os.path.join(REPO, "assets/patches/android.txt")):
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out

def files_of(patch):
    fs = []
    for line in open(os.path.join(REPO, patch), errors="replace"):
        if line.startswith("+++ b/"):
            fs.append(line[6:].split("\t")[0].strip())
    return fs

def ensure_pristine(path):
    dst = os.path.join(PRISTINE, path)
    if not os.path.exists(dst):
        subprocess.run(["tar", "-xJf", TARBALL, "-C", os.path.dirname(PRISTINE), "firefox-153.0/" + path], check=True)
    return dst

def slice_patch(patch, path):
    r = subprocess.run(["filterdiff", "-p1", "-i", path, os.path.join(REPO, patch)], capture_output=True, text=True, check=True)
    return r.stdout

def replay(path, seq):
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, os.path.dirname(path)), exist_ok=True)
        shutil.copy(ensure_pristine(path), os.path.join(d, path))
        notes = []
        for p in seq:
            body = slice_patch(p, path)
            r = subprocess.run(["patch", "-p1", "-d", d, "--no-backup-if-mismatch"], input=body, capture_output=True, text=True)
            fuzz = [l.strip() for l in r.stdout.splitlines() if "fuzz" in l or "offset" in l]
            rej = os.path.exists(os.path.join(d, path + ".rej"))
            notes.append((os.path.basename(p), r.returncode, fuzz, rej))
            if r.returncode != 0:
                return None, notes
        h = hashlib.sha256(open(os.path.join(d, path), "rb").read()).hexdigest()
        return h, notes

def main():
    seq_all = listed()
    if NEW in seq_all:
        seq_all.remove(NEW)
    new_files = files_of(NEW)
    shared = {}
    for p in seq_all:
        for f in files_of(p):
            if f in new_files:
                shared.setdefault(f, []).append(p)
    if not shared:
        print("no shared files with any listed android patch")
        return
    for f, partners in shared.items():
        print("=" * 100)
        print("FILE", f)
        base_seq = [p for p in seq_all if f in files_of(p)] + [NEW]
        h0, n0 = replay(f, base_seq)
        print("  list order (new last):", h0)
        for name, rc, fuzz, rej in n0:
            print("     %-40s rc=%d rej=%s %s" % (name, rc, rej, "; ".join(fuzz)))
        for partner in partners:
            seq = [p for p in base_seq if p != NEW]
            i = seq.index(partner)
            seq.insert(i, NEW)
            h1, n1 = replay(f, seq)
            verdict = "IDENTICAL" if h1 == h0 and h1 else ("FAILED" if h1 is None else "DIFFERENT")
            print("  new before %-32s -> %s %s" % (os.path.basename(partner), verdict, h1))
            for name, rc, fuzz, rej in n1:
                print("     %-40s rc=%d rej=%s %s" % (name, rc, rej, "; ".join(fuzz)))

main()
