#!/usr/bin/env python3
"""Replay the Android patch series (common.txt, then android.txt) on a Firefox tag.

Downloads only the files the series touches, from github.com/mozilla-firefox/firefox
at TAG, into WORKDIR, and applies every patch with `patch -p1` in list order, the
way scripts/librewolf-patches.py does. Out-of-patch mutations (copies, deletions,
version rewrites) are not replayed: this proves patches apply, not that the tree
builds.

    python3 replay-series.py FIREFOX_153_3_0esr_RELEASE /tmp/replay [--fuzz 0]

Exits 1 if any patch fails. Prints each patch's fuzz and offset counts.
"""
import argparse
import concurrent.futures
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def series():
    names = []
    for listing in ('common.txt', 'android.txt'):
        for line in (ROOT / 'assets/patches' / listing).read_text().splitlines():
            line = line.split('#', 1)[0].strip()
            if line:
                names.append(line.split()[0])
    return names


def touched(patches):
    paths = set()
    for patch in patches:
        for line in (ROOT / patch).read_text(errors='replace').splitlines():
            if line.startswith(('--- a/', '+++ b/')):
                paths.add(line[6:].split('\t')[0].strip())
    return sorted(paths)


def fetch(tag, path, pristine):
    url = f'https://raw.githubusercontent.com/mozilla-firefox/firefox/{tag}/{path}'
    for _ in range(3):
        try:
            data = urllib.request.urlopen(url, timeout=60).read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None  # created by a patch
            continue
        except OSError:
            continue
        target = pristine / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return None
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('tag')
    parser.add_argument('workdir', type=Path)
    parser.add_argument('--fuzz', type=int, help='maximum fuzz (default: patch(1) default, as the build uses)')
    args = parser.parse_args()
    patches = series()
    pristine = args.workdir / f'{args.tag}-pristine'
    if not pristine.exists():
        with concurrent.futures.ThreadPoolExecutor(16) as pool:
            errors = [p for p in pool.map(lambda p: fetch(args.tag, p, pristine), touched(patches)) if p]
        if errors:
            sys.exit('download failed: ' + ', '.join(errors[:5]))
    tree = args.workdir / f'{args.tag}-patched'
    if tree.exists():
        shutil.rmtree(tree)
    shutil.copytree(pristine, tree)
    failed = 0
    for patch in patches:
        argv = ['patch', '-p1', '--no-backup-if-mismatch', '-r', '-', '-i', str(ROOT / patch)]
        if args.fuzz is not None:
            argv.insert(1, f'--fuzz={args.fuzz}')
        result = subprocess.run(argv, cwd=tree, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        output = result.stdout + result.stderr
        fuzz = sum('with fuzz' in line for line in output.splitlines())
        offset = sum('offset' in line for line in output.splitlines())
        print(f'{"FAIL" if result.returncode else "ok  "} {patch} fuzz={fuzz} offset={offset}')
        if result.returncode:
            failed += 1
            print(output)
    print(f'{len(patches)} patches, {failed} failed, tree: {tree}')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
