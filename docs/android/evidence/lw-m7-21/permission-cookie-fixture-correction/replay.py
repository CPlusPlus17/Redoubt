#!/usr/bin/env python3
"""Replay all Task14/23 outputs and the actual three-file test overlay offline."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_archive(data):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        names = [item.name for item in archive.getmembers()]
        assert len(names) == len(set(names))
        assert all(item.isfile() and not Path(item.name).is_absolute() and '..' not in Path(item.name).parts
                   for item in archive.getmembers())
        return {item.name: archive.extractfile(item).read() for item in archive.getmembers()}


def materialize(root, files):
    root.mkdir()
    for path, data in files.items():
        output = root / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)


def apply(root, patch):
    result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1'], input=patch,
                            cwd=root, capture_output=True)
    assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()
    assert b'offset' not in result.stdout and b'fuzz' not in result.stdout, result.stdout
    assert not result.stderr, result.stderr
    return result.stdout.decode()


def blocks(patch):
    parts = re.split(rb'(?=^diff --git )', patch, flags=re.M)
    result = {}
    for part in parts:
        if part:
            header = part.splitlines()[0].decode()
            path = header.split(' b/', 1)[1] if header.startswith('diff --git ') else '<preamble>'
            assert path not in result
            result[path] = part
    return result


def pins14(data):
    return {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in data.decode().splitlines()}


def pins23(data):
    return {row['path']: row['after_sha256'] for row in json.loads(data)['files']}


def verify_sources(root, pins):
    for path, expected in pins.items():
        assert sha((root / path).read_bytes()) == expected, path


def run(output):
    inputs = json.loads((HERE / 'inputs.json').read_text())
    captured = {}
    for name, expected in inputs['archives'].items():
        data = (HERE / name).read_bytes()
        assert sha(data) == expected, name
        captured[name] = read_archive(data)
    original = captured['before-repository.tar.gz']
    assert {path: sha(data) for path, data in original.items()} == inputs['original_repository_inputs']
    assert sha((HERE / 'coroutine-recovery.javap.txt').read_bytes()) == inputs['coroutine_runtime']['bytecode_report_sha256']
    cookie_base = (ROOT / 'docs/android/evidence/lw-m7-23/source-baseline.tar.gz').read_bytes()
    assert sha(cookie_base) == inputs['cookie_baseline_sha256']
    current23 = json.loads((ROOT / 'docs/android/evidence/lw-m7-23/source-files.json').read_bytes())
    patch14 = 'patches/android/canvas-webgl-permissions.patch'
    assert current23['predecessors']['canvas-webgl-permissions.patch'] == inputs['patches'][patch14]['after_sha256']
    paths = {row['path'] for row in inputs['files']}
    assert len(paths) == 3
    old_test_counts = {}
    for row in inputs['files']:
        before = captured['before-source.tar.gz'][row['path']]
        after = captured['test-source-overlay.tar.gz'][row['path']]
        assert sha(before) == row['before_sha256'] and sha(after) == row['after_sha256']
        assert before.count(b'@Test') == after.count(b'@Test') == row['test_count_before'] == row['test_count_after']
        assert b'@Ignore' not in after
        old_test_counts[row['path']] = row['test_count_after']
    changed_paths = set()
    receipt = {'repository_before_edit': inputs['repository_before_edit'], 'replays': {},
               'test_counts': old_test_counts, 'target_verdict': inputs['target_verdict']}
    for patch_path, expected in inputs['patches'].items():
        current = (ROOT / patch_path).read_bytes()
        assert sha(current) == expected['after_sha256']
        assert sha(original[patch_path]) == expected['before_sha256']
        old_blocks, new_blocks = blocks(original[patch_path]), blocks(current)
        assert set(old_blocks) == set(new_blocks)
        changed_paths.update(path for path in old_blocks if old_blocks[path] != new_blocks[path])
        number = '14' if patch_path == patch14 else '23'
        manifest = f'docs/android/evidence/lw-m7-{number}/' + ('source-sha256.txt' if number == '14' else 'source-files.json')
        parse = pins14 if number == '14' else pins23
        previous_pins, current_pins = parse(original[manifest]), parse((ROOT / manifest).read_bytes())
        assert set(previous_pins) == set(current_pins)
        for path, data in captured['before-source.tar.gz'].items():
            if path in previous_pins:
                assert sha(data) == previous_pins[path], f'actual source differs from original manifest: {path}'
        baseline = captured['graphics-baseline.tar.gz'] if number == '14' else read_archive(cookie_base)
        for state, patch, pins in [('original', original[patch_path], previous_pins), ('corrected', current, current_pins)]:
            source = output / f'{number}-{state}'
            materialize(source, baseline)
            log = apply(source, patch)
            verify_sources(source, pins)
            receipt['replays'][f'{number}-{state}'] = {
                'path_count': len(pins), 'fuzz': 0, 'offset': 0, 'final_sha256': pins,
            }
            (output / f'{number}-{state}-patch.txt').write_text(log)
        # Only the owned tests can change final bytes. Match their original
        # outputs to the actual failed-run source, not merely repository text.
        expected_changed = {row['path'] for row in inputs['files'] if row['patch'] == patch_path}
        assert {path for path in previous_pins if previous_pins[path] != current_pins[path]} == expected_changed
        for path in expected_changed:
            assert sha(captured['before-source.tar.gz'][path]) == previous_pins[path]
            assert sha(captured['test-source-overlay.tar.gz'][path]) == current_pins[path]
    assert changed_paths == paths, 'production or unrelated patch section changed'
    overlay = output / 'actual-source-overlay'
    materialize(overlay, captured['before-source.tar.gz'])
    compressed_patch = (HERE / 'test-source-overlay.patch.gz').read_bytes()
    assert sha(compressed_patch) == inputs['overlay_patch_compressed_sha256']
    overlay_patch = gzip.decompress(compressed_patch)
    assert sha(overlay_patch) == inputs['overlay_patch_sha256']
    apply(overlay, overlay_patch)
    for path, data in captured['test-source-overlay.tar.gz'].items():
        assert (overlay / path).read_bytes() == data
    for path, data in captured['before-source.tar.gz'].items():
        if path not in paths:
            assert (overlay / path).read_bytes() == data
    reports = captured['target-test-reports.tar.gz']
    summary = json.loads(reports['junit-summary.json'])['gecko']['summary']
    assert summary == {'classes': 4, 'tests': 57, 'failures': 7, 'errors': 0, 'skipped': 0}
    xmls = read_archive(reports['gecko-junit-xml.tar.gz'])
    failures = []
    for name, data in xmls.items():
        root = ET.fromstring(data)
        for case in root.findall('testcase'):
            failure = case.find('failure')
            if failure is not None:
                failures.append({'class': case.attrib['classname'], 'test': case.attrib['name'],
                                 'type': failure.attrib['type'], 'message': failure.attrib['message']})
    assert len(failures) == 7
    assert sum(row['type'].endswith('UnfinishedStubbingException') for row in failures) == 5
    assert sum(row['type'] == 'junit.framework.AssertionFailedError' for row in failures) == 2
    receipt['original_gecko_report'] = summary
    receipt['original_failures'] = failures
    receipt['actual_overlay_paths'] = sorted(paths)
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('PASS: original and corrected Task14/23 patches reconstruct every pinned output with zero fuzz/offset', flush=True)
    print('PASS: only three test patch sections/bodies changed; assertions and 5/16/4 test counts retained', flush=True)
    print('PASS: actual failed-run source overlay and original 57-test/7-failure XML report bound', flush=True)
    subprocess.run(['node', str(ROOT / 'docs/android/evidence/lw-m7-14/origin-permission-unit-test.cjs'),
                    str(output / '14-corrected')], check=True)
    subprocess.run(['python3', str(ROOT / 'scripts/tests/test-cookie-banner-controls.py'),
                    '--source', str(output / '23-corrected')], check=True)
    print('NOT RUN: corrected Android test classes, full Fenix suite, native instrumentation or runtime.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New private directory retaining reconstructed source and receipt')
    args = parser.parse_args()
    if args.output:
        args.output.mkdir()
        run(args.output.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='lw21-fixture-replay-') as tmp:
            run(Path(tmp))
