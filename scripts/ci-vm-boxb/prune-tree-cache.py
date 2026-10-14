#!/usr/bin/env python3
"""Drop superseded Gecko tree caches inside box B's build VM (docs/android/CI-VM.md).

android-test.yaml's build-android keeps one patched tree per Android version in
$LW_CI_ROOT/tree-<version>-<release> (~40 GB each, with its objdirs). Nothing
removed old ones, so every Firefox release cost another ~40 GB of the VM's
/home until android-release.yaml's 150 GB preflight refused to start
(2026-10-13, 148 GB free; tree-157.0-1 and tree-157.0-2 were deleted by hand).

Policy: keep the two newest versions among the existing trees plus the current
one (version.android + release.android), so the current tree and the previous
one survive even before the current tree has been built; delete every other
tree-<version>-<release>. Versions sort numerically (157.0-3 < 157.0.1-1 <
158.0-1 < 158.0-2), never as strings.

Safety:
  * only direct children of the root named tree-<digits.digits...>-<digits>
    are candidates; anything else in the root is listed and left alone;
  * a candidate must be a real directory, not a symlink, and must resolve to a
    path directly inside the root;
  * the root must resolve to exactly /home/runner/actions-runner/redoubt-ci
    (the runner's $LW_CI_ROOT). LW_PRUNE_ALLOWED_ROOT overrides that for the
    hermetic test (scripts/tests/test-boxb-prune-tree-cache.py) only;
  * --dry-run prints the same plan and deletes nothing.

Usage (in the runner, repository root as cwd):
  python3 scripts/ci-vm-boxb/prune-tree-cache.py --root "$LW_CI_ROOT" \
      --current "$(cat version.android)-$(cat release.android)" [--keep 2] [--dry-run]
Exit 0 on success (also when nothing is pruned), 2 on a refused root or bad input.
"""
import argparse
import os
import pathlib
import re
import shutil
import sys

DEFAULT_ALLOWED_ROOT = "/home/runner/actions-runner/redoubt-ci"
TREE_RE = re.compile(r"^tree-((?:\d+)(?:\.\d+)*)-(\d+)$")
VER_RE = re.compile(r"^((?:\d+)(?:\.\d+)*)-(\d+)$")


def key(ver_rel):
    """'157.0.1-1' -> ((157, 0, 1), 1); trailing .0 parts do not matter for order."""
    m = VER_RE.match(ver_rel)
    if not m:
        raise ValueError(f"not <version>-<release>: {ver_rel!r}")
    parts = [int(p) for p in m.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return (tuple(parts), int(m.group(2)))


def du_gb(path):
    total = 0
    for dirpath, _dirs, files in os.walk(path, followlinks=False):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_blocks * 512
            except OSError:
                pass
    return total / 1e9


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True, help="the runner's LW_CI_ROOT")
    ap.add_argument("--current", required=True, help="<version>-<release> of this checkout, e.g. 158.0-2")
    ap.add_argument("--keep", type=int, default=2, help="newest versions to keep (default 2, minimum 2)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, delete nothing")
    ap.add_argument("--no-size", action="store_true", help="skip the du of each removed tree")
    a = ap.parse_args(argv)

    tag = "prune-tree-cache" + (" (dry run)" if a.dry_run else "")
    if a.keep < 2:
        print(f"{tag}: FATAL --keep {a.keep} < 2 (current + previous is the floor)", file=sys.stderr)
        return 2
    try:
        cur_key = key(a.current)
    except ValueError as e:
        print(f"{tag}: FATAL --current: {e}", file=sys.stderr)
        return 2

    allowed = os.environ.get("LW_PRUNE_ALLOWED_ROOT", DEFAULT_ALLOWED_ROOT)
    allowed_real = os.path.realpath(allowed)
    if not os.path.isdir(a.root):
        print(f"{tag}: no cache root {a.root}; nothing to do")
        return 0
    root = pathlib.Path(os.path.realpath(a.root))
    if str(root) != allowed_real:
        print(f"{tag}: FATAL root {a.root} resolves to {root}, not {allowed_real}; refusing", file=sys.stderr)
        return 2

    trees, other = {}, []
    for entry in sorted(root.iterdir()):
        m = TREE_RE.match(entry.name)
        if not m:
            if entry.name.startswith("tree-"):
                other.append(entry.name)
            continue
        if entry.is_symlink() or not entry.is_dir():
            other.append(entry.name)
            continue
        trees[f"{m.group(1)}-{m.group(2)}"] = entry

    for name in other:
        print(f"{tag}: ignore {name} (not a plain tree-<version>-<release> directory)")
    universe = sorted(set(trees) | {a.current}, key=key, reverse=True)
    keep = set(universe[: a.keep])
    keep.add(a.current)
    print(f"{tag}: root {root}; current {a.current}; keeping {', '.join(sorted(keep, key=key, reverse=True))}")
    removed = 0
    for ver in sorted(trees, key=key):
        path = trees[ver]
        if ver in keep:
            print(f"{tag}: keep   {path.name}")
            continue
        # Belt and braces: a direct child of the allowed root, nothing else.
        real = pathlib.Path(os.path.realpath(path))
        if real.parent != root or not TREE_RE.match(real.name):
            print(f"{tag}: FATAL {path} resolves to {real}; refusing", file=sys.stderr)
            return 2
        size = "" if a.no_size else f" ({du_gb(real):.1f} GB)"
        if a.dry_run:
            print(f"{tag}: would remove {real}{size}")
        else:
            print(f"{tag}: remove {real}{size}")
            shutil.rmtree(real)
        removed += 1
    print(f"{tag}: {removed} tree(s) {'to remove' if a.dry_run else 'removed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
