#!/usr/bin/env python3
"""Re-capture source receipts for patches on the Android patch stack.

Run it from the repository root. It reads only repository files and the Firefox
tarball named by ./version.android, and it changes neither.

1. Extract from the tarball every path that any patch on the Android stack
   touches (assets/patches/common.txt and then android.txt, the order
   check-patchfail.sh and the patcher use).
2. Apply the whole stack with `patch -p1` (default fuzz), as
   check-patchfail.sh does.
3. Just before each TARGET patch, capture the bytes of every path it touches.
   That capture is the "before" tree: the real stack state the patch meets.
4. Replay the target alone on that capture with --fuzz=0. Require no offset and
   no fuzz, and require that the result is byte-identical to what the stack
   produced.
5. Optionally (--objdir), compare each touched path after the WHOLE stack with
   the same path in an independently patched build tree.

Outputs per target: <stem>-before.tar.gz (deterministic) and <stem>.json.
"""
import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sections(text):
    """Same splitter as docs/android/evidence/lw-m7-35/check-ordering.py."""
    marks = list(re.finditer(r'^--- (?:a/[^\n]+|/dev/null)\n\+\+\+ (?:b/([^\n]+)|/dev/null)\n', text, re.M))
    result = {}
    for index, mark in enumerate(marks):
        name = mark.group(1) or mark.group(0).splitlines()[0][6:]
        assert name not in result, name
        chunk = text[mark.start():marks[index + 1].start() if index + 1 < len(marks) else len(text)]
        chunk = re.split(r'^(?:diff --git |index [a-f0-9]+\.\.|new file mode |deleted file mode )', chunk, flags=re.M)[0]
        result[name] = chunk
    return result


def read_list(root, name):
    out = []
    for line in (root / 'assets/patches' / f'{name}.txt').read_text().splitlines():
        line = line.split('#', 1)[0].strip()
        if line:
            out.append(line)
    return out


def snapshot(tree, paths):
    out = {}
    for p in paths:
        f = tree / p
        out[p] = f.read_bytes() if f.is_file() else None
    return out


def write_tar(path, files):
    """Deterministic tar.gz of the present files (absent paths are recorded in JSON)."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(files):
            data = files[name]
            if data is None:
                continue
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            tar.addfile(info, io.BytesIO(data))
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0, compresslevel=9) as gz:
        gz.write(raw.getvalue())
    path.write_bytes(buf.getvalue())


def run_patch(cwd, patchfile, *extra):
    r = subprocess.run(['patch', '--batch', '-p1', *extra, '-i', str(patchfile)], cwd=cwd,
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', type=Path, default=Path.cwd())
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--objdir', type=Path, help='independently patched tree to compare final bytes with')
    ap.add_argument('targets', nargs='+', help='patch paths relative to --root')
    args = ap.parse_args()
    root = args.root.resolve()
    version = (root / 'version.android').read_text().strip()
    tarball = root / f'firefox-{version}.source.tar.xz'
    tar_sha = sha(tarball.read_bytes())
    stack = read_list(root, 'common') + read_list(root, 'android')
    for t in args.targets:
        assert t in stack, f'{t} is not on the Android stack'
    texts = {p: (root / p).read_text() for p in stack}
    touched = {p: list(sections(texts[p])) for p in stack}
    union = sorted({x for p in stack for x in touched[p]})
    args.out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix='lw-recapture-') as scratch:
        scratch = Path(scratch)
        # The first member may be "./"; take the first real directory name.
        listing = subprocess.Popen(['tar', '-tf', str(tarball)], stdout=subprocess.PIPE, text=True)
        top = ''
        for line in listing.stdout:
            name = line.strip()
            if name.startswith('./'):
                name = name[2:]
            top = name.split('/', 1)[0]
            if top:
                break
        listing.kill()
        listing.wait()
        assert top, 'cannot determine the tarball top directory'
        members = scratch / 'members.txt'
        members.write_text(''.join(f'{top}/{p}\n' for p in union))
        # Paths a patch creates are not in the tarball; tar reports them and
        # exits 2 while still extracting everything else.
        r = subprocess.run(['tar', '-xJf', str(tarball), '-C', str(scratch), '--files-from', str(members)],
                           capture_output=True, text=True)
        missing = [l for l in r.stderr.splitlines() if 'Not found in archive' in l]
        other = [l for l in r.stderr.splitlines() if l and 'Not found in archive' not in l
                 and 'Exiting with failure status' not in l]
        assert not other, other
        tree = scratch / top
        tree.mkdir(exist_ok=True)
        stack_log = []
        results = {}
        for p in stack:
            if p in args.targets:
                before = snapshot(tree, touched[p])
            code, out = run_patch(tree, root / p)
            assert code == 0 and '.rej' not in out, f'{p} failed on the stack:\n{out}'
            stack_log.append({'patch': p, 'sha256': sha((root / p).read_bytes()),
                              'offsets': len(re.findall(r'offset', out)), 'fuzz': len(re.findall(r'with fuzz', out))})
            if p in args.targets:
                after = snapshot(tree, touched[p])
                results[p] = {'before': before, 'after': after, 'stack_output': out}
        final = snapshot(tree, sorted({x for t in args.targets for x in touched[t]}))

        for p in args.targets:
            stem = Path(p).stem
            res = results[p]
            replay = scratch / f'replay-{stem}'
            replay.mkdir()
            for name, data in res['before'].items():
                if data is not None:
                    (replay / name).parent.mkdir(parents=True, exist_ok=True)
                    (replay / name).write_bytes(data)
            code, out = run_patch(replay, root / p, '--forward', '--fuzz=0')
            exact = code == 0 and 'offset' not in out and 'fuzz' not in out
            replay_after = snapshot(replay, touched[p])
            identical = replay_after == res['after']
            later = [q for q in stack[stack.index(p) + 1:] if set(touched[q]) & set(touched[p])]
            objdir_rows = {}
            if args.objdir:
                for name in touched[p]:
                    f = args.objdir / name
                    got = f.read_bytes() if f.is_file() else None
                    objdir_rows[name] = (got == final[name])
            predecessors = [{'patch': q, 'sha256': sha((root / q).read_bytes()),
                             'shared_paths': sorted(set(touched[q]) & set(touched[p]))}
                            for q in stack[:stack.index(p)] if set(touched[q]) & set(touched[p])]
            write_tar(args.out / f'{stem}-before.tar.gz', res['before'])
            receipt = {
                'patch': p,
                'patch_sha256': sha((root / p).read_bytes()),
                'firefox_version': version,
                'tarball': tarball.name,
                'tarball_sha256': tar_sha,
                'stack_lists': ['assets/patches/common.txt', 'assets/patches/android.txt'],
                'stack_position': stack.index(p) + 1,
                'stack_length': len(stack),
                'predecessors_touching_these_paths': predecessors,
                'later_patches_touching_these_paths': later,
                'before_archive': f'{stem}-before.tar.gz',
                'before_archive_sha256': sha((args.out / f'{stem}-before.tar.gz').read_bytes()),
                'files': [{'path': n,
                           'before_sha256': sha(res['before'][n]) if res['before'][n] is not None else None,
                           'after_sha256': sha(res['after'][n]) if res['after'][n] is not None else None}
                          for n in touched[p]],
                'stack_apply_output': res['stack_output'],
                'replay_fuzz0_exit': code,
                'replay_fuzz0_output': out,
                'replay_fuzz0_exact': exact,
                'replay_equals_stack_result': identical,
                'objdir': str(args.objdir) if args.objdir else None,
                'objdir_matches_full_stack': objdir_rows,
            }
            (args.out / f'{stem}.json').write_text(json.dumps(receipt, indent=2, sort_keys=False) + '\n')
            print(f'{p}: before={sum(1 for v in res["before"].values() if v is not None)}/{len(touched[p])} present; '
                  f'fuzz0 exact={exact}; replay==stack {identical}; '
                  f'objdir match {sum(objdir_rows.values())}/{len(objdir_rows)}; later={later}')
        (args.out / 'stack-apply.json').write_text(json.dumps({'tarball_sha256': tar_sha, 'patches': stack_log,
                                                              'not_in_tarball': len(missing)}, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
