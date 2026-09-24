#!/usr/bin/env python3
"""Reproduce Task36 pair receipts on retained, scoped pristine sources only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def measure():
    manifest = json.loads((HERE / 'source-files.json').read_text())
    candidate = 'patches/android/global-privacy-controls.patch'
    assert hashlib.sha256((ROOT / candidate).read_bytes()).hexdigest() == manifest['patch_sha256']
    archive = HERE / 'scoped-pristine.tar.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['scoped_pristine_archive_sha256']
    for row in manifest['scoped_predecessors']:
        assert hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() == row['sha256'], 'Predecessor changed: ' + row['path']
    paths = [row['path'] for row in manifest['files']]
    results = []
    for deferred in manifest['scoped_predecessors']:
        with tempfile.TemporaryDirectory(prefix='lw-m7-36-order-') as directory:
            destination = Path(directory)
            with tarfile.open(archive) as retained:
                for member in retained.getmembers():
                    assert member.isfile() and member.name in manifest['scoped_pristine_files']
                    output = destination / member.name
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(retained.extractfile(member).read())
            steps = []
            reached = False
            sequence = [row['path'] for row in manifest['scoped_predecessors'] if row != deferred] + [candidate, deferred['path']]
            for name in sequence:
                if name == candidate:
                    reached = True
                result = subprocess.run(['git', 'apply', *['--include=' + path for path in paths], str(ROOT / name)],
                                        cwd=destination, capture_output=True, text=True)
                steps.append({'patch': name, 'exit_code': result.returncode, 'stderr': result.stderr})
                if result.returncode:
                    break
            identical = all(step['exit_code'] == 0 for step in steps) and all(
                (destination / row['path']).is_file() and
                hashlib.sha256((destination / row['path']).read_bytes()).hexdigest() == row['after_sha256']
                for row in manifest['files']
            )
            # Also swap at the predecessor's original position, restricted to
            # the pair's shared files. This avoids unrelated later prerequisites
            # hiding whether this pair itself is order-free.
            with tempfile.TemporaryDirectory(prefix='lw-m7-36-local-order-') as pair_directory:
                pair_tree = Path(pair_directory)
                with tarfile.open(archive) as retained:
                    for member in retained.getmembers():
                        if member.name not in deferred['shared_paths']:
                            continue
                        output = pair_tree / member.name
                        output.parent.mkdir(parents=True, exist_ok=True)
                        output.write_bytes(retained.extractfile(member).read())
                pair_steps = []
                for row in manifest['scoped_predecessors']:
                    sequence = [candidate, row['path']] if row == deferred else [row['path']]
                    for name in sequence:
                        result = subprocess.run(['git', 'apply', *['--include=' + path for path in deferred['shared_paths']], str(ROOT / name)],
                                                cwd=pair_tree, capture_output=True, text=True)
                        pair_steps.append({'patch': name, 'exit_code': result.returncode, 'stderr': result.stderr})
                        if result.returncode:
                            break
                    if pair_steps[-1]['exit_code']:
                        break
                pair_identical = all(step['exit_code'] == 0 for step in pair_steps) and all(
                    hashlib.sha256((pair_tree / row['path']).read_bytes()).hexdigest() == row['after_sha256']
                    for row in manifest['files'] if row['path'] in deferred['shared_paths']
                )
            results.append({'predecessor': deferred['path'], 'shared_paths': deferred['shared_paths'],
                            'shared_position_swap_identical': pair_identical, 'shared_position_steps': pair_steps,
                            'inverse_source_identical': identical, 'inverse_reached_candidate': reached, 'steps': steps})
    return {'method': 'Forward replay is check-source.py. Inverse omits one of seven predecessors, applies Task36, then applies the omitted patch; compare all 21 final source files. Separately move Task36 to immediately before each predecessor on pair-shared paths, then finish remaining predecessors; compare final shared-path hashes.',
            'candidate_patch_sha256': manifest['patch_sha256'], 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-receipt', action='store_true')
    args = parser.parse_args()
    actual = measure()
    receipt = HERE / 'ordering-review.json'
    if args.write_receipt:
        receipt.write_text(json.dumps(actual, indent=2) + '\n')
    else:
        assert actual == json.loads(receipt.read_text()), 'Ordering receipt changed'
    for row in actual['results']:
        print(f"{row['predecessor']}: inverse identical={row['inverse_source_identical']}; candidate reached={row['inverse_reached_candidate']}; shared position swap identical={row['shared_position_swap_identical']}")
    print('ORDER RECEIPT PASS; global classification remains root integration ownership.')


if __name__ == '__main__':
    main()
