"""Host driver/grader checks; logs are synthetic and no native test executes."""
import copy
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest import mock

import driver
import test_pref_runtime as pref_tests
from grade import InvalidResult, grade_instrumentation, grade_run, grade_xpcshell


class GlobalPrivacyInventory(unittest.TestCase):
    def test_entire_task35_selection_and_guarded_shutdown_preserved(self):
        before = json.loads((driver.HERE / 'previous-task35-selection.json').read_text())
        current = driver.reviewed_requirements()
        self.assertEqual(current['xpcshell'][:len(before['xpcshell'])], before['xpcshell'])
        self.assertEqual(current['instrumentation'][:len(before['instrumentation'])], before['instrumentation'])
        self.assertEqual(current['shutdown_instrumentation'], before['shutdown_instrumentation'])
        self.assertEqual(current['pending_xpcshell'], before['pending_xpcshell'])
        self.assertEqual(sum(len(s['tasks']) for s in current['xpcshell']), 73)
        self.assertEqual(len(current['instrumentation']), 25)
        self.assertEqual(len(current['shutdown_instrumentation']['expected_methods']), 1)

    def test_five_named_native_tasks_require_completion_and_retain_injected_scope(self):
        inv = json.loads(driver.TASK36_INVENTORY.read_text())['xpcshell_method_sets'][0]
        spec = next(s for s in driver.reviewed_requirements()['xpcshell'] if s['path'] == inv['source'])
        name = spec['path']
        rows = [{'action': 'suite_start'}, {'action': 'test_start', 'test': name}]
        for task in spec['tasks']:
            rows.extend([
                {'action': 'log', 'level': 'INFO', 'message': f'{name} | Starting {task}'},
                {'action': 'test_status', 'test': name, 'status': 'PASS', 'subtest': 'native assertion'},
                {'action': 'log', 'level': 'INFO', 'message': f'head | test {task} finished (1)'},
            ])
        rows += [{'action': 'test_end', 'test': name, 'status': 'PASS'}, {'action': 'suite_end'}]
        raw = lambda values: ''.join(json.dumps(value) + '\n' for value in values)
        result = grade_xpcshell(raw(rows), spec)
        self.assertEqual(len(result['passed_tasks']), 5)
        self.assertEqual(result['execution_scope'], inv['execution_scope'])
        self.assertIn('injected save boundary', result['execution_scope'])
        for task in spec['tasks']:
            without_finish = [r for r in rows if f'| test {task} finished' not in r.get('message', '')]
            with self.subTest(task=task), self.assertRaises(InvalidResult): grade_xpcshell(raw(without_finish), spec)
            skipped = copy.deepcopy(rows)
            skipped.insert(3, {'action': 'test_status', 'test': name, 'status': 'SKIP', 'subtest': task})
            with self.assertRaises(InvalidResult): grade_xpcshell(raw(skipped), spec)

    def test_three_real_api_methods_cannot_be_missing_or_assumption_skips(self):
        methods = json.loads(driver.TASK36_INVENTORY.read_text())['regular_instrumentation_methods']
        self.assertEqual(len(grade_instrumentation(pref_tests.instrumented(methods), methods)['passed_methods']), 3)
        for method in methods:
            with self.subTest(method=method), self.assertRaises(InvalidResult):
                grade_instrumentation(pref_tests.instrumented([m for m in methods if m != method]), methods)
            with self.assertRaises(InvalidResult):
                grade_instrumentation(pref_tests.instrumented([method], code=-3), [method])

    def test_inventory_scope_hash_method_and_source_omissions_are_rejected(self):
        original = driver.reviewed_requirements()
        inventory = json.loads(driver.TASK36_INVENTORY.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'requirements.json'
            for change in ['hash', 'scope', 'method', 'source', 'task']:
                req = copy.deepcopy(original)
                if change == 'hash': req['task36_inventory_sha256'] = '0' * 64
                elif change == 'scope': next(s for s in req['xpcshell'] if s['path'] == inventory['xpcshell_method_sets'][0]['source'])['execution_scope'] = 'Real disk durability PASS'
                elif change == 'method': req['instrumentation'].remove(inventory['regular_instrumentation_methods'][0])
                elif change == 'source': req['product_paths'].remove(inventory['extra_required_source_paths'][0])
                else: next(s for s in req['xpcshell'] if s['path'] == inventory['xpcshell_method_sets'][0]['source'])['tasks'].pop()
                path.write_text(json.dumps(req))
                with self.subTest(change=change), mock.patch.object(driver, 'REQUIREMENTS', path), self.assertRaises(InvalidResult):
                    driver.reviewed_requirements()

    def test_each_stale_task35_shared_pin_is_rejected_before_source_preflight(self):
        original = json.loads(driver.HARNESS.read_text())
        before = {r['path']: r['after_sha256'] for r in json.loads((driver.HERE.parent / 'lw-m7-35/source-files.json').read_text())['files']}
        after = json.loads(driver.TASK36_INVENTORY.read_text())['required_source_hashes']
        shared = set(before) & set(after)
        self.assertEqual(len(shared), 5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'harness.json'
            for name in shared:
                self.assertNotEqual(before[name], after[name])
                pins = copy.deepcopy(original); pins['files'][name] = before[name]
                path.write_text(json.dumps(pins))
                with self.subTest(name=name), mock.patch.object(driver, 'HARNESS', path), self.assertRaisesRegex(InvalidResult, 'stale/mismatched'):
                    driver.reviewed_requirements()

    def test_reviewed_test_manifest_preserves_product_union_and_adds_only_four_pins(self):
        read = lambda name: {line[66:]: line[:64] for line in (driver.HERE / name).read_text().splitlines()}
        product = read('composed-product-source-sha256.txt')
        extra = read('native-test-extra-source-sha256.txt')
        native = read('proposed-native-test-source-sha256.txt')
        self.assertEqual(len(product), json.loads((driver.HERE / 'cleanup-composition-comparison.json').read_text())['product_union_count'])
        self.assertEqual(len(extra), 4)
        self.assertFalse(product.keys() & extra.keys())
        self.assertEqual(native, dict(product, **extra))
        self.assertTrue(set(driver.reviewed_requirements()['product_paths']) <= native.keys())
        pins = json.loads(driver.HARNESS.read_text())['files']
        for name in pins.keys() & native.keys():
            self.assertEqual(native[name], pins[name], name)
        overlay = json.loads((driver.HERE / 'root-bundle-source-overlay.json').read_text())
        historical = json.loads((driver.HERE / 'pre-fixture/requirements.json').read_text())
        self.assertEqual(historical['patches']['canvas-webgl-permissions.patch'], overlay['patch_sha256'])
        native = read('pre-fixture/proposed-native-test-source-sha256.txt')
        previous = read('pre-bundle-native-test-source-sha256.txt')
        self.assertEqual(previous.keys(), native.keys())
        self.assertEqual({name for name in previous if previous[name] != native[name]}, {row['path'] for row in overlay['files']})
        for row in overlay['files']:
            self.assertEqual(previous[row['path']], row['before_sha256'])
            self.assertEqual(native[row['path']], row['after_sha256'])

    def test_five_fixture_rows_are_only_changes_and_all_selections_stay_identical(self):
        read = lambda name: {line[66:]: line[:64] for line in (driver.HERE / name).read_text().splitlines()}
        before = read('pre-fixture/proposed-native-test-source-sha256.txt')
        after = read('pre-cleanup/proposed-native-test-source-sha256.txt')
        overlay = json.loads((driver.HERE / 'fixture-source-overlays.json').read_text())
        self.assertEqual(before.keys(), after.keys())
        self.assertEqual({name for name in before if before[name] != after[name]},
                         {row['path'] for row in overlay['files']})
        pins = json.loads((driver.HERE / 'pre-cleanup/harness-sources.json').read_text())['files']
        self.assertEqual(len(pins), 82)
        for row in overlay['files']:
            self.assertEqual(before[row['path']], row['before_sha256'])
            self.assertEqual(after[row['path']], row['after_sha256'])
            self.assertEqual(pins[row['path']], row['after_sha256'])
        old = json.loads((driver.HERE / 'pre-fixture/requirements.json').read_text())
        current = json.loads((driver.HERE / 'pre-cleanup/requirements.json').read_text())
        for key in ['xpcshell', 'instrumentation', 'shutdown_instrumentation', 'pending_xpcshell']:
            self.assertEqual(current[key], old[key])

    def test_actual_old_fixture_body_cannot_pass_with_its_own_valid_manifest(self):
        overlay = json.loads((driver.HERE / 'fixture-source-overlays.json').read_text())
        with tarfile.open(driver.HERE / 'pre-fixture-source.tar.gz') as archive:
            for row in overlay['files']:
                name = row['path']
                data = archive.extractfile(name).read()
                with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp); source = root / 'source'
                    target = source / name; target.parent.mkdir(parents=True); target.write_bytes(data)
                    self.assertEqual(driver.sha(target), row['before_sha256'])
                    manifest = root / 'sha256'; manifest.write_text(row['before_sha256'] + '  ' + name + '\n')
                    pins = root / 'pins.json'; pins.write_text(json.dumps({'files': {name: row['after_sha256']}}))
                    req = {'product_paths': [name], 'xpcshell': [], 'instrumentation': [],
                           'shutdown_instrumentation': {'expected_methods': []}}
                    with mock.patch.object(driver, 'reviewed_requirements', return_value=req), \
                         mock.patch.object(driver, 'HARNESS', pins), \
                         self.assertRaisesRegex(InvalidResult, 'audited harness changed'):
                        driver.source_binding(source, manifest)

    def test_authoritative_source_receipt_must_match_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / 'source-receipt.json'; changed.write_text('{}')
            with mock.patch.object(driver, 'TASK36_SOURCE_RECEIPT', changed), self.assertRaisesRegex(InvalidResult, 'source receipt'):
                driver.reviewed_requirements()
        case = pref_tests.ShutdownProcessEvidence()
        self.addCleanup(case.doCleanups); case.setUp(); case.run_fake()
        (case.root / 'task36-source-receipt.json').write_text('{}')
        with self.assertRaisesRegex(InvalidResult, 'source receipt'): grade_run(case.root)

    def test_archived_global_inventory_is_bound_to_build_and_source(self):
        case = pref_tests.ShutdownProcessEvidence()
        self.addCleanup(case.doCleanups); case.setUp(); case.run_fake()
        self.assertEqual(grade_run(case.root)['status'], 'PENDING')
        (case.root / 'task36-inventory.json').write_text('{}')
        with self.assertRaisesRegex(InvalidResult, 'Task36 inventory'): grade_run(case.root)


if __name__ == '__main__':
    unittest.main()
