#!/usr/bin/env python3
"""Measure both Task35 shared-file orders without touching a product tree.

Every pair uses its entire shared path set. Canonical replay must reproduce the
pinned final bytes before an inverse failure can be called a constraint. Offsets
are expected when changing order; fuzz, missing files and untested setup fail.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CANDIDATE = 'patches/android/extension-update-controls.patch'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sections(path):
    text = path.read_text()
    marks = list(re.finditer(r'^--- (?:a/[^\n]+|/dev/null)\n\+\+\+ (?:b/([^\n]+)|/dev/null)\n', text, re.M))
    result = {}
    for index, mark in enumerate(marks):
        name = mark.group(1) or mark.group(0).splitlines()[0][6:]
        assert name not in result, name
        chunk = text[mark.start():marks[index + 1].start() if index + 1 < len(marks) else len(text)]
        # Do not carry the next file's git metadata (especially new/deleted mode)
        # into a scoped patch. It is not part of this file's unified hunk body.
        chunk = re.split(r'^(?:diff --git |index [a-f0-9]+\.\.|new file mode |deleted file mode )', chunk, flags=re.M)[0]
        result[name] = chunk
    assert result, path
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true', help='write the owned ordering-receipt.json after successful checks')
    args = parser.parse_args()
    inputs = json.loads((HERE / 'ordering-inputs.json').read_text())
    source = json.loads((HERE / 'source-files.json').read_text())
    source_files = {item['path']: item for item in source['files']}
    assert sha((HERE / 'ordering-source-baseline.tar.gz').read_bytes()) == inputs['before_archive_sha256']
    patches = {}
    for name, digest in inputs['patches'].items():
        assert sha((ROOT / name).read_bytes()) == digest, f'{name}: update inputs only after a fresh review'
        patches[name] = sections(ROOT / name)
    results = []
    with tempfile.TemporaryDirectory(prefix='lw-m7-35-orders-') as scratch:
        scratch = Path(scratch)
        for pair in inputs['pairs']:
            predecessor = pair['predecessor']
            shared = sorted(set(patches[CANDIDATE]) & set(patches[predecessor]))
            assert shared == pair['shared_paths'], f'Incomplete shared set: {predecessor}'
            home = scratch / Path(predecessor).stem
            base = home / 'base'
            base.mkdir(parents=True)
            with tarfile.open(HERE / 'ordering-source-baseline.tar.gz') as archive:
                for name in shared:
                    data = archive.extractfile(name).read()
                    assert sha(data) == source_files[name]['before_sha256'], name
                    dest = base / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
            steps = []

            def apply(tree, patch, role, reverse=False):
                scoped = ''.join(patches[patch][name] for name in shared if name in patches[patch])
                assert scoped, patch
                patchfile = home / 'scoped.patch'
                patchfile.write_text(scoped)
                command = ['patch', '--batch', '--fuzz=0', '--reverse' if reverse else '--forward', '-p1', '-i', str(patchfile)]
                run = subprocess.run(command, cwd=tree, capture_output=True, text=True)
                stdout = run.stdout.replace(str(home), '$PAIR')
                stderr = run.stderr.replace(str(home), '$PAIR')
                assert 'with fuzz' not in stdout + stderr
                steps.append({'role': role, 'patch': patch, 'reverse': reverse,
                              'scoped_sha256': sha(scoped.encode()), 'exit_code': run.returncode,
                              'stdout': stdout, 'stderr': stderr})
                return run.returncode

            peeled = pair['peel_before_reverse']
            # For graphics14, cookie23 changes the earlier patch's context. Its
            # removal is a setup dependency, not evidence of a Task35 constraint.
            for patch in reversed(peeled):
                assert apply(base, patch, 'setup-remove-later', True) == 0
            assert apply(base, predecessor, 'setup-remove-predecessor', True) == 0
            base_hashes = {name: sha((base / name).read_bytes()) for name in shared}
            canonical = home / 'canonical'
            shutil.copytree(base, canonical)
            for patch in [predecessor] + peeled + [CANDIDATE]:
                assert apply(canonical, patch, 'canonical') == 0, predecessor
            final_hashes = {name: sha((canonical / name).read_bytes()) for name in shared}
            assert final_hashes == {name: source_files[name]['after_sha256'] for name in shared}
            inverse = home / 'inverse'
            shutil.copytree(base, inverse)
            failed = None
            for patch in [CANDIDATE, predecessor] + peeled:
                if apply(inverse, patch, 'inverse'):
                    failed = patch
                    break
            if failed:
                # A failure at an unrelated peeled predecessor would not prove
                # a direct ordering constraint between the candidate and pair.
                assert failed in (CANDIDATE, predecessor), f'Inverse failed elsewhere: {failed}'
                verdict = 'predecessor-required'
                inverse_hashes = None
            else:
                inverse_hashes = {name: sha((inverse / name).read_bytes()) for name in shared}
                assert inverse_hashes == final_hashes, f'Both applied but output differs: {predecessor}'
                verdict = 'order-free-identical'
            assert verdict == pair['expected'], (predecessor, verdict)
            results.append({'predecessor': predecessor, 'candidate': CANDIDATE,
                            'shared_paths': shared, 'peel_before_reverse': peeled,
                            'base_hashes': base_hashes, 'canonical_final_hashes': final_hashes,
                            'inverse_final_hashes': inverse_hashes, 'inverse_failed_at': failed,
                            'verdict': verdict, 'steps': steps})
            print(f'PASS {Path(predecessor).name}: {verdict}; all {len(shared)} shared paths checked')
    receipt = {'inputs_sha256': sha((HERE / 'ordering-inputs.json').read_bytes()),
               'script_sha256': sha(Path(__file__).read_bytes()),
               'method': 'full shared-path sets; canonical exact final bytes; both orders; zero fuzz; offsets recorded',
               'pairs': results}
    if args.record:
        (HERE / 'ordering-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    else:
        recorded = json.loads((HERE / 'ordering-receipt.json').read_text())
        assert receipt == recorded, 'Receipt differs; review before --record'
    print('PASS six shared-file ordering measurements; no target compilation or runtime claim')


if __name__ == '__main__':
    main()
