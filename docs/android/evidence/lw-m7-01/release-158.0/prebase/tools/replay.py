#!/usr/bin/env python3
"""In-order replay of a Redoubt patch sequence onto a pristine Firefox tree,
in a scratch git repo, to rebase failing patches at --fuzz=0.

usage:
  replay.py init  TREE TARBALL LIST...       extract + git init, track every file any patch touches
  replay.py run   TREE LIST...                apply patches (resumes after the last committed one)
                                              stops at the first patch that is not clean at --fuzz=0
  replay.py fuzz  TREE PATCH                  apply PATCH with default fuzz (leaves .rej) for hand-fixing
  replay.py regen TREE PATCH OUT              commit the tree's state as PATCH and write header+git diff to OUT
LIST entries are repo-relative patch paths, or @common/@android/@desktop for a whole list.
REPO env var = the librewolf checkout holding patches/ and assets/ (default: ../repo).
"""
import os, re, subprocess, sys
from pathlib import Path

REPO = Path(os.environ.get("REPO", Path(__file__).resolve().parent.parent / "repo"))

def sh(cmd, cwd=None, check=True, inp=None):
    r = subprocess.run(cmd, cwd=cwd, input=inp, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"FAILED {cmd}:\n{r.stdout}\n{r.stderr}")
    return r

def read_list(name):
    out = []
    for line in (REPO / "assets/patches" / f"{name}.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out

def expand(items):
    seq = []
    for it in items:
        seq += read_list(it[1:]) if it.startswith("@") else [it]
    return seq

PATH_RE = re.compile(r"^(?:---|\+\+\+) (?:[ab]/)?([^\t\n]+)")

def patch_paths(p):
    paths = set()
    for line in (REPO / p).read_text(errors="replace").splitlines():
        m = PATH_RE.match(line)
        if m and m.group(1) != "/dev/null" and not line.startswith(("--- -", "+++ +")):
            paths.add(m.group(1).strip())
    return paths

def git(tree, *args, check=True):
    return sh(["git", "-c", "commit.gpgsign=false", "-c", "user.email=replay@local", "-c", "user.name=replay", *args], cwd=tree, check=check)

def init(tree, tarball, items):
    tree = Path(tree)
    tree.mkdir(parents=True)
    sh(["tar", "xf", tarball, "-C", str(tree), "--strip-components=1"])
    git(tree, "init", "-q")
    git(tree, "config", "status.showUntrackedFiles", "no")
    allp = set()
    for p in expand(items):
        allp |= patch_paths(p)
    exist = sorted(x for x in allp if (tree / x).exists())
    for i in range(0, len(exist), 500):
        git(tree, "add", "-f", "--", *exist[i:i + 500])
    git(tree, "commit", "-q", "-m", "pristine")
    print(f"tracked {len(exist)} pristine files of {len(allp)} touched paths")

def done(tree):
    log = git(tree, "log", "--format=%s").stdout.splitlines()
    return {l for l in log if l != "pristine"}

def commit(tree, p):
    paths = sorted(patch_paths(p))
    for i in range(0, len(paths), 500):
        git(tree, "add", "-A", "-f", "--", *paths[i:i + 500])
    git(tree, "commit", "-q", "--allow-empty", "-m", p)

def run(tree, items):
    d = done(tree)
    for p in expand(items):
        if p in d:
            continue
        r = sh(["patch", "-p1", "--fuzz=0", "--dry-run", "-i", str(REPO / p)], cwd=tree, check=False, inp="")
        fz = "--fuzz=0"
        if r.returncode != 0:
            r2 = sh(["patch", "-p1", "--dry-run", "-i", str(REPO / p)], cwd=tree, check=False, inp="")
            if r2.returncode != 0 or p.startswith("patches/android/"):
                print(f"STOP {p}: not clean at --fuzz=0 (default fuzz: exit {r2.returncode})\n{r.stdout}{r.stderr}")
                return 1
            fz = "--fuzz=2"
        ra = sh(["patch", "-p1", fz, "--no-backup-if-mismatch", "-i", str(REPO / p)], cwd=tree, inp="")
        commit(tree, p)
        offs = ra.stdout.count("offset")
        print(f"ok {p}" + ("  (needs fuzz)" if fz != "--fuzz=0" else "") + (f"  ({offs} hunks at an offset)" if offs else ""))
    print("ALL APPLIED")
    return 0

def fuzz(tree, p):
    r = sh(["patch", "-p1", "--no-backup-if-mismatch", "-i", str(REPO / p)], cwd=tree, check=False, inp="")
    print(r.stdout, r.stderr)

def header_of(text):
    lines = text.splitlines(keepends=True)
    for i, l in enumerate(lines):
        if l.startswith(("diff ", "Index: ")) or (l.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ ")):
            return "".join(lines[:i]), "".join(lines[i:])
    return text, ""

def track(tree, paths):
    git(tree, "add", "-f", "--", *paths)
    git(tree, "commit", "-q", "-m", "pristine+ " + " ".join(paths))

def regen(tree, p, out, extra=()):
    tree = Path(tree)
    orig = (REPO / p).read_text(errors="replace")
    head, body = header_of(orig)
    new = [x for x in list(patch_paths(p)) + list(extra) if (tree / x).exists()]
    git(tree, "add", "-u")
    if new:
        git(tree, "add", "-f", "--", *new)
    diff = git(tree, "diff", "--cached", "--no-color", "--no-renames", "-U3", "HEAD").stdout
    gitstyle = "\ndiff --git " in "\n" + body
    if not gitstyle:
        diff = "".join(l for l in diff.splitlines(keepends=True) if not l.startswith(("diff --git ", "index ", "new file mode ", "deleted file mode ")))
    Path(out).write_text(head + diff)
    git(tree, "commit", "-q", "--allow-empty", "-m", p)
    print(f"wrote {out}")

if __name__ == "__main__":
    cmd, *a = sys.argv[1:]
    if cmd == "init":
        init(a[0], a[1], a[2:])
    elif cmd == "run":
        sys.exit(run(a[0], a[1:]))
    elif cmd == "fuzz":
        fuzz(a[0], a[1])
    elif cmd == "regen":
        regen(a[0], a[1], a[2], a[3:])
    elif cmd == "track":
        track(a[0], a[1:])

def regen_hist(tree, p, out):
    """Rewrite PATCH from the replay history at exact in-order line numbers."""
    log = git(tree, "log", "--format=%H %s").stdout.splitlines()
    commits = [l.split(" ", 1) for l in log]
    idx = [i for i, (h, s) in enumerate(commits) if s == p]
    assert len(idx) == 1, idx
    h = commits[idx[0]][0]
    orig = (REPO / p).read_text(errors="replace")
    head, body = header_of(orig)
    diff = git(tree, "diff", "--no-color", "--no-renames", "-U3", h + "^", h).stdout
    if "\ndiff --git " not in "\n" + body:
        diff = "".join(l for l in diff.splitlines(keepends=True) if not l.startswith(("diff --git ", "index ", "new file mode ", "deleted file mode ")))
    Path(out).write_text(head + diff)
    print("wrote", out)

if __name__ == "__main__" and sys.argv[1] == "regenhist":
    regen_hist(sys.argv[2], sys.argv[3], sys.argv[4])
