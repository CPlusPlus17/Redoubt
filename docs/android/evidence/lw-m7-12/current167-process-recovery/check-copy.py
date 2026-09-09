#!/usr/bin/env python3
"""Replay the versioned checkpoint delta without executing any driver operation."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
NAMES = ('common.py', 'build.py', 'runtime.py', 'test_contracts.py')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parent = json.loads((HERE / 'parent-inputs.json').read_text())
    prefix = 'docs/android/evidence/lw-m7-12/current167/'
    require(set(parent['original_driver_inputs']) == {prefix + name for name in NAMES},
            'original driver inventory differs')
    with tempfile.TemporaryDirectory(prefix='process-recovery-copy-') as temporary:
        root = Path(temporary)
        for name in NAMES:
            data = (REPO / (prefix + name)).read_bytes()
            require(parent['original_driver_inputs'][prefix + name] ==
                    {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)},
                    'original driver changed: ' + name)
            (root / name).write_bytes(data)
        result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(HERE / 'copy-delta.patch')],
                                cwd=root, capture_output=True, text=True)
        require(result.returncode == 0, result.stdout + result.stderr)
        require(set(p.name for p in root.iterdir()) == set(NAMES), 'unexpected replay output')
        for name in NAMES:
            require((root / name).read_bytes() == (HERE / name).read_bytes(), 'copy replay differs: ' + name)
            compile((HERE / name).read_text(), str(HERE / name), 'exec')
    print('PASS four original driver byte pins, exact versioned source replay and Python syntax; no guest execution')


if __name__ == '__main__':
    main()
