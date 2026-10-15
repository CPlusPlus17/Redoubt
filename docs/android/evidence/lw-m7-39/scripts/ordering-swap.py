#!/usr/bin/env python3
"""LW-M7-39 ordering measurement (lw-m7-51/ordering-swap.py with the patch as an argument).

For every listed patch that shares a tree file with drm-permission-default.patch,
apply the shared files' hunks of the whole common+android sequence to pristine
Firefox 158.0 copies twice: in list order, and with drm-permission-default moved
to just before that partner. Every application is GNU patch --fuzz=0. A pair is
order-free when both runs apply and the files end byte-identical.

usage: ordering-swap.py REPO FIREFOX_158_SRC_DIR PATCH
"""
import hashlib, re, shutil, subprocess, sys, tempfile
from pathlib import Path

repo, src = Path(sys.argv[1]), Path(sys.argv[2])
NEW = sys.argv[3]

def listed():
    out = []
    for lst in ("assets/patches/common.txt", "assets/patches/android.txt"):
        for line in (repo / lst).read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                out.append(line.split()[0])
    return out

def files_of(p):
    return {m.group(1) for m in re.finditer(r"^\+\+\+ b/(\S+)", (repo / p).read_text(), re.M)}

shared_files = sorted(files_of(NEW))
lst = listed()
if NEW not in lst:          # held back (PATCH-SCOPE "Pending"): measure it as the last entry
    lst.append(NEW)
seq = [p for p in lst if files_of(p) & set(shared_files)]
assert seq[-1] == NEW, seq

def run(order):
    d = Path(tempfile.mkdtemp())
    try:
        for f in shared_files:
            (d / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src / f, d / f)
        for p in order:
            diff = subprocess.run(["filterdiff"] + sum((["-i", "*/" + f] for f in shared_files), []) + [str(repo / p)],
                                  capture_output=True, text=True, check=True).stdout
            # android-list entries at --fuzz=0, common.txt ones at patch's default, as
            # scripts/librewolf-patches.py applies them (scripts/check-patch-order.py header)
            fuzz = ["--fuzz=0"] if p.startswith("patches/android/") else []
            r = subprocess.run(["patch", "-d", str(d), "-p1"] + fuzz + ["--no-backup-if-mismatch", "-s"],
                               input=diff, capture_output=True, text=True)
            if r.returncode:
                return None, f"{p}: {r.stdout.strip()} {r.stderr.strip()}"
        return {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for f in shared_files}, ""
    finally:
        shutil.rmtree(d)

base, err = run(seq)
print(f"list order ({len(seq)} patches): " + ("applies" if base else "FAILS " + err))
for f, h in (base or {}).items():
    print(f"  {h}  {f}")
for partner in seq[:-1]:
    order = [p for p in seq if p != NEW]
    order.insert(order.index(partner), NEW)
    res, err = run(order)
    common = sorted(files_of(partner) & files_of(NEW))
    verdict = "FAILS " + err if res is None else ("identical" if res == base else "DIFFERENT")
    print(f"{NEW.split('/')[-1]} before {partner.split('/')[-1]} [{', '.join(Path(c).name for c in common)}]: {verdict}")
    # second swap (scripts/check-patch-order.py: "A moved directly after B"): the partner moved to just
    # after NEW, everything else in list order -- the pairwise test when a third patch sits between them
    order = [p for p in seq if p != partner]
    order.insert(order.index(NEW) + 1, partner)
    res, err = run(order)
    verdict = "FAILS " + err if res is None else ("identical" if res == base else "DIFFERENT")
    print(f"{partner.split('/')[-1]} after {NEW.split('/')[-1]} [{', '.join(Path(c).name for c in common)}]: {verdict}")
