#!/usr/bin/env python3
"""Read-only full before/absence or after verification of a reviewed handoff."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from compose import manifest, require, safe_name, sha


def check_source(source, expected):
    require(source.is_dir(), 'source must be an existing directory')
    for name, digest in sorted(expected.items()):
        path = source / safe_name(name)
        if digest is None:
            require(not path.exists() and not path.is_symlink(), f'expected absent: {name}')
        else:
            require(re.fullmatch('[0-9a-f]{64}', digest) is not None, f'invalid digest: {name}')
            require(path.is_file() and not path.is_symlink(), f'missing or nonregular input: {name}')
            require(path.resolve().is_relative_to(source), f'path escapes source: {name}')
            with path.open('rb') as stream:
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == digest,
                        f'live source differs: {name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff', type=Path, required=True)
    parser.add_argument('--receipt-sha256', required=True, help='Explicit independently reviewed receipt digest')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--mode', choices=('before', 'after'), required=True)
    args = parser.parse_args()
    receipt_data = (args.handoff / 'receipt.json').read_bytes()
    require(sha(receipt_data) == args.receipt_sha256, 'receipt differs from reviewed digest')
    receipt = json.loads(receipt_data)
    for name, pin in receipt['outputs'].items():
        data = (args.handoff / safe_name(name)).read_bytes()
        require(sha(data) == pin['sha256'] and len(data) == pin['bytes'], f'handoff differs: {name}')
    final_data = (args.handoff / 'proposed-source-sha256.txt').read_bytes()
    final = manifest(final_data)
    plan = json.loads((args.handoff / 'live-preflight.json').read_bytes())
    require(plan['final_manifest_sha256'] == sha(final_data), 'plan final binding differs')
    before = {row['path']: row['expected_sha256'] for row in plan['files']}
    require(len(before) == len(plan['files']) == receipt['final_union_count'] and
            set(before) == set(final), 'full live inventory differs')
    check_source(args.source.resolve(), before if args.mode == 'before' else final)
    print(json.dumps({'status': 'PASS read-only ' + args.mode + ' source preflight',
                      'source': str(args.source.resolve()), 'count': len(final),
                      'receipt_sha256': args.receipt_sha256,
                      'scope': 'No mutation, build, target execution or release acceptance'}))


if __name__ == '__main__':
    main()
