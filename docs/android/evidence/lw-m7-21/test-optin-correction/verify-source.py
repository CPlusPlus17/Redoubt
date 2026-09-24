"""Reconstruct both graphics snapshots and verify the one-class test API opt-in."""
import importlib.util
import gzip
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
previous = HERE.parent / 'permission-cookie-fixture-correction'
spec = importlib.util.spec_from_file_location('fixture_replay_helpers', previous / 'replay.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
overlay = json.loads((HERE / 'source-overlay.json').read_text())
row = overlay['files'][0]
assert len(overlay['files']) == 1 and row['test_count'] == 8
before = (HERE / 'OriginBoundPermissionsFeatureTest.kt.before').read_bytes()
after = (HERE / 'OriginBoundPermissionsFeatureTest.kt').read_bytes()
assert helper.sha(before) == row['before_sha256'] and helper.sha(after) == row['after_sha256']
expected = before.replace(b'import kotlinx.coroutines.CompletableDeferred\n',
                          b'import kotlinx.coroutines.CompletableDeferred\nimport kotlinx.coroutines.ExperimentalCoroutinesApi\n')
expected = expected.replace(b'class OriginBoundPermissionsFeatureTest {',
                            b'@OptIn(ExperimentalCoroutinesApi::class)\nclass OriginBoundPermissionsFeatureTest {')
assert after == expected and before.count(b'@Test') == after.count(b'@Test') == 8
old_patch = gzip.decompress((HERE / 'original-graphics.patch.gz').read_bytes())
new_patch = (ROOT / 'patches/android/canvas-webgl-permissions.patch').read_bytes()
assert helper.sha(old_patch) == overlay['old_patch_sha256']
assert helper.sha(new_patch) == overlay['patch_sha256']
old_blocks, new_blocks = helper.blocks(old_patch), helper.blocks(new_patch)
assert old_blocks.keys() == new_blocks.keys()
assert {name for name in old_blocks if old_blocks[name] != new_blocks[name]} == {row['path']}
old_pins = helper.pins14((HERE / 'original-source-sha256.txt').read_bytes())
new_pins = helper.pins14((ROOT / 'docs/android/evidence/lw-m7-14/source-sha256.txt').read_bytes())
assert old_pins.keys() == new_pins.keys() and len(new_pins) == 36
assert {name for name in old_pins if old_pins[name] != new_pins[name]} == {row['path']}
assert old_pins[row['path']] == row['before_sha256'] and new_pins[row['path']] == row['after_sha256']
baseline_bytes = (previous / 'graphics-baseline.tar.gz').read_bytes()
assert helper.sha(baseline_bytes) == json.loads((previous / 'inputs.json').read_text())['archives']['graphics-baseline.tar.gz']
baseline = helper.read_archive(baseline_bytes)
with tempfile.TemporaryDirectory(prefix='redoubt-optin-replay-') as temporary:
    for name, patch, pins in [('before', old_patch, old_pins), ('after', new_patch, new_pins)]:
        source = Path(temporary) / name
        helper.materialize(source, baseline)
        helper.apply(source, patch)
        helper.verify_sources(source, pins)
print('PASS both36-file snapshots, zero offsets/fuzz; one test class adds the explicit coroutine opt-in')
print('PASS all eight tests/assertions and all production patch sections unchanged')
print('TARGET TESTS / RUNTIME: NOT RUN by this source replay')
