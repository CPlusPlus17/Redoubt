#!/usr/bin/env python3
"""Check the retained composition and bounded negative preflight controls locally."""
import argparse
import json
from pathlib import Path
import tempfile

import compose
import preflight


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    first, _ = compose.compose(compose.ROOT)
    second, _ = compose.compose(compose.ROOT)
    compose.require(first == second, 'fresh private replays differ')
    retained = {p.name: p.read_bytes() for p in (compose.HERE / 'handoff').iterdir()}
    compose.require(first == retained, 'replay differs from retained handoff')
    cases = []
    with tempfile.TemporaryDirectory(prefix='lw-m7-37-preflight-check-') as d:
        tree = Path(d)
        (tree / 'existing').write_bytes(b'retained-source')
        expected = {'existing': compose.sha(b'retained-source'), 'new': None}
        preflight.check_source(tree, expected)
        for name in ('changed-existing', 'unexpected-create', 'broken-symlink-create'):
            if name == 'changed-existing':
                (tree / 'existing').write_bytes(b'drift')
            elif name == 'unexpected-create':
                (tree / 'new').write_bytes(b'late-create')
            else:
                (tree / 'new').symlink_to('missing')
            try:
                preflight.check_source(tree, expected)
            except ValueError as error:
                cases.append({'case': name, 'rejected': True, 'error': str(error)})
            else:
                raise AssertionError('accepted ' + name)
            (tree / 'existing').write_bytes(b'retained-source')
            (tree / 'new').unlink(missing_ok=True)
        for raw in (b'0' * 64 + b'  ../escape\n', b'0' * 64 + b'  dup\n' + b'1' * 64 + b'  dup\n'):
            try:
                compose.manifest(raw)
            except ValueError:
                pass
            else:
                raise AssertionError('accepted malformed manifest')
    record = {
        'scope': 'Actual retained source replay twice and local synthetic preflight error controls only; no guest preflight/build/target execution.',
        'script_hashes': {name: compose.sha((compose.HERE / name).read_bytes())
                          for name in ('compose.py', 'preflight.py', 'check.py')},
        'byte_identical_fresh_replays': 2,
        'output_files': {name: compose.sha(data) for name, data in sorted(first.items())},
        'preflight_controls': cases,
        'invalid_manifest_controls': ['parent traversal rejected', 'duplicate path rejected'],
    }
    target = compose.HERE / 'local-replay-checks.json'
    if args.record:
        target.write_bytes(compose.json_bytes(record))
    else:
        compose.require(record == json.loads(target.read_bytes()), 'local receipt differs')
    print('PASS: two exact source replays, retained outputs, three rejected live-input errors and two rejected malformed manifests; no target execution')


if __name__ == '__main__':
    main()
