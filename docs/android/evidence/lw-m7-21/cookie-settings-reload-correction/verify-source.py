#!/usr/bin/env python3
"""Reconstruct both complete cookie-control source scopes; no target test run."""
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


def archive(data):
    with tarfile.open(fileobj=io.BytesIO(data)) as stream:
        members = stream.getmembers()
        assert len(members) == len({m.name for m in members})
        assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
        return {m.name: stream.extractfile(m).read() for m in members}


def sections(data):
    return {block.split(b' b/', 1)[1].splitlines()[0].decode(): block
            for block in re.split(rb'(?=^diff --git )', data, flags=re.M) if block}


def check():
    row = json.loads((HERE / 'source-overlay.json').read_bytes())
    for name, expected in row['evidence_inputs'].items():
        assert sha((HERE / name).read_bytes()) == expected, name
    before = (HERE / 'CookieBannerSettingsTest.kt.before').read_bytes()
    after = (HERE / 'CookieBannerSettingsTest.kt').read_bytes()
    target = row['files'][0]
    assert len(row['files']) == 1
    assert sha(before) == target['before_sha256'] and sha(after) == target['after_sha256']
    assert before.count(b'@Test') == after.count(b'@Test') == target['test_count'] == 5
    assert before.split(b'    @Test\n', 1)[1] == after.split(b'    @Test\n', 1)[1]
    assert b'        val store = BrowserStore()\n' in after
    assert b'every { testContext.components.core.store } returns store' in after
    assert b'every { testContext.components.useCases.sessionUseCases } returns SessionUseCases(store)' in after
    assert b'reload.invoke()' not in after and b'core.store.state.translationEngine' not in after
    original = gzip.decompress((HERE / 'original-cookie-banner-controls.patch.gz').read_bytes())
    current = (ROOT / 'patches/android/cookie-banner-controls.patch').read_bytes()
    assert sha(original) == row['original_patch_sha256'] and sha(current) == row['patch_sha256']
    a, b = sections(original), sections(current)
    assert set(a) == set(b)
    assert {name for name in a if a[name] != b[name]} == {target['path']}
    baseline_raw = (ROOT / 'docs/android/evidence/lw-m7-23/source-baseline.tar.gz').read_bytes()
    assert sha(baseline_raw) == row['source_baseline_sha256']
    baseline = archive(baseline_raw)
    old_pins = json.loads((HERE / 'original-task23-source-files.json').read_bytes())
    new_pins = json.loads((ROOT / 'docs/android/evidence/lw-m7-23/source-files.json').read_bytes())
    assert old_pins.keys() == new_pins.keys()
    assert all(old_pins[key] == new_pins[key] for key in old_pins if key != 'files')
    old_rows = {x['path']: x for x in old_pins['files']}
    new_rows = {x['path']: x for x in new_pins['files']}
    assert set(old_rows) == set(new_rows)
    assert {name for name in old_rows if old_rows[name] != new_rows[name]} == {target['path']}
    outputs = {}
    with tempfile.TemporaryDirectory(prefix='lw-m7-21-cookie-reload-') as directory:
        for label, patch, manifest in [('before', original, old_pins), ('after', current, new_pins)]:
            tree = Path(directory) / label
            tree.mkdir()
            for name, data in baseline.items():
                output = tree / name
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(data)
            result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1'], input=patch,
                                    cwd=tree, capture_output=True)
            assert result.returncode == 0 and not result.stderr, result.stdout + result.stderr
            assert b'offset' not in result.stdout and b'fuzz' not in result.stdout
            outputs[label] = {}
            for item in manifest['files']:
                digest = sha((tree / item['path']).read_bytes())
                assert digest == item['after_sha256'], item['path']
                outputs[label][item['path']] = digest
    xml = ET.fromstring((HERE / 'TEST-org.mozilla.fenix.settings.cookiebannerhandling.CookieBannerSettingsTest.xml').read_bytes())
    assert xml.attrib['tests'] == xml.attrib['failures'] == '5' and xml.attrib['errors'] == xml.attrib['skipped'] == '0'
    for test in xml.findall('testcase'):
        failure = test.find('failure')
        assert failure is not None and failure.attrib['type'] == 'java.lang.NullPointerException'
        assert 'ReloadUrlUseCase.invoke$default(SessionUseCases.kt:163)' in failure.text
        assert 'CookieBannerSettingsTest.kt:55' in failure.text
    actual_manifest = (HERE / 'original-source-sha256.txt').read_bytes()
    assert sha(actual_manifest) == row['parent_source_manifest_sha256']
    pins = {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in actual_manifest.decode().splitlines()}
    assert pins[target['path']] == target['before_sha256']
    inspected = archive((HERE / 'inspected-source.tar.gz').read_bytes())
    assert {name: sha(data) for name, data in inspected.items()} == {name: x['sha256'] for name, x in row['inspected_sources'].items()}
    print('SOURCE PASS: original/corrected complete37-file cookie scopes replay with zero fuzz/offset.')
    print('SOURCE PASS: one test-file patch section changes; all five test bodies/assertions are byte-identical.')
    print('EVIDENCE PASS: actual current165 source pin and five default-bridge setup failures retained.')
    print('TARGET TESTS/COMPILATION/RUNTIME: NOT RUN for this correction; full rerun required.')
    return outputs


if __name__ == '__main__':
    check()
