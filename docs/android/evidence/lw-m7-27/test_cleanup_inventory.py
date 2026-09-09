"""Host acceptance-parser controls; native cookie/frame tests do not run here."""
import copy
import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import driver
import test_pref_runtime as pref_tests
from grade import InvalidResult, grade_instrumentation, grade_run, grade_xpcshell


class CleanupInventory(unittest.TestCase):
    def inventory(self):
        return json.loads(driver.TASK37_INVENTORY.read_text())

    def test_prior_64_tasks_20_methods_and_shutdown_exclusions_preserved(self):
        before = json.loads((driver.HERE / 'pre-cleanup/requirements.json').read_text())
        current = driver.reviewed_requirements()
        self.assertEqual(current['xpcshell'][:-1], before['xpcshell'])
        self.assertEqual(current['instrumentation'][:-5], before['instrumentation'])
        self.assertEqual(current['shutdown_instrumentation'], before['shutdown_instrumentation'])
        self.assertEqual(current['pending_xpcshell'], before['pending_xpcshell'])
        self.assertEqual(sum(len(s['tasks']) for s in current['xpcshell']), 73)
        self.assertEqual(len(current['instrumentation']), 25)
        self.assertEqual(len(current['shutdown_instrumentation']['expected_methods']), 1)
        self.assertEqual(sum(len(s['tasks']) for s in current['pending_xpcshell']), 3)

    def test_native_receipt_pins_all_fifteen_final_paths_and_actual_source_coverage(self):
        inventory = self.inventory()
        receipt = json.loads(driver.TASK37_SOURCE_RECEIPT.read_text())
        expected = {r['path']: r['after_sha256'] for r in receipt['files']}
        self.assertEqual(len(expected), 15)
        self.assertEqual(inventory['required_source_hashes'], expected)
        self.assertEqual(set(inventory['extra_required_source_paths']), expected.keys())
        self.assertEqual(driver.reviewed_requirements()['patches']['session-cleanup.patch'], receipt['patch_sha256'])
        self.assertEqual(inventory['source_receipt_sha256'], driver.sha(driver.TASK37_SOURCE_RECEIPT))

    def test_each_cookie_case_requires_actual_finish_and_assertion_results(self):
        item = self.inventory()['xpcshell_method_sets'][0]
        spec = next(s for s in driver.reviewed_requirements()['xpcshell'] if s['path'] == item['source'])
        name = spec['path']
        rows = [{'action': 'suite_start'}, {'action': 'test_start', 'test': name}]
        for task in spec['tasks']:
            rows += [
                {'action': 'log', 'level': 'INFO', 'message': f'{name} | Starting {task}'},
                {'action': 'test_status', 'test': name, 'status': 'PASS', 'subtest': 'native assertion'},
                {'action': 'log', 'level': 'INFO', 'message': f'head | test {task} finished (1)'},
            ]
        rows += [{'action': 'test_end', 'test': name, 'status': 'PASS'}, {'action': 'suite_end'}]
        raw = lambda items: ''.join(json.dumps(row) + '\n' for row in items)
        graded = grade_xpcshell(raw(rows), spec)
        self.assertEqual(len(graded['passed_tasks']), 9)
        self.assertEqual(graded['execution_scope'], item['execution_scope'])
        self.assertIn('No native callbacks mocked', graded['execution_scope'])
        for task in spec['tasks']:
            with self.subTest(task=task), self.assertRaises(InvalidResult):
                grade_xpcshell(raw([r for r in rows if f'| test {task} finished' not in r.get('message', '')]), spec)
        for status in ['SKIP', 'FAIL']:
            altered = copy.deepcopy(rows); altered[3]['status'] = status
            with self.subTest(status=status), self.assertRaises(InvalidResult):
                grade_xpcshell(raw(altered), spec)

    def test_every_frame_method_required_and_crash_assumption_cannot_pass(self):
        methods = self.inventory()['regular_instrumentation_methods']
        self.assertEqual(len(grade_instrumentation(pref_tests.instrumented(methods), methods)['passed_methods']), 5)
        for method in methods:
            with self.subTest(method=method), self.assertRaises(InvalidResult):
                grade_instrumentation(pref_tests.instrumented([m for m in methods if m != method]), methods)
        crash = next(m for m in methods if '#crashedChild' in m)
        with self.assertRaises(InvalidResult):
            grade_instrumentation(pref_tests.instrumented([crash], code=-3), [crash])

    def test_inventory_hash_scope_method_and_required_source_cannot_be_omitted(self):
        original = driver.reviewed_requirements(); inventory = self.inventory()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'requirements.json'
            for change in ['hash', 'scope', 'method', 'path', 'task', 'skip']:
                req = copy.deepcopy(original)
                if change == 'hash': req['task37_inventory_sha256'] = '0' * 64
                elif change == 'scope': req['xpcshell'][-1]['execution_scope'] = 'Entire session cleanup passed'
                elif change == 'method': req['instrumentation'].remove(inventory['regular_instrumentation_methods'][0])
                elif change == 'path': req['product_paths'].remove(inventory['extra_required_source_paths'][0])
                elif change == 'task': req['xpcshell'][-1]['tasks'].pop()
                else: req['xpcshell'][-1]['allowed_skips'] = req['xpcshell'][-1]['tasks']
                path.write_text(json.dumps(req))
                with self.subTest(change=change), mock.patch.object(driver, 'REQUIREMENTS', path), self.assertRaises(InvalidResult):
                    driver.reviewed_requirements()

    def test_either_actual_old_test_support_body_fails_even_its_valid_manifest(self):
        receipt = json.loads(driver.TASK37_SOURCE_RECEIPT.read_text())
        original = json.loads((driver.HERE / 'pre-cleanup/harness-sources.json').read_text())['files']
        shared = [r for r in receipt['files'] if r['path'] in original]
        self.assertEqual(len(shared), 2)
        archive_path = driver.HERE / 'task37-before-test-support.tar.gz'
        with tarfile.open(archive_path) as archive:
            for row in shared:
                name = row['path']; data = archive.extractfile(name).read()
                self.assertEqual(hashlib.sha256(data).hexdigest(), row['before_sha256'])
                self.assertEqual(original[name], row['before_sha256'])
                with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory); source = root / 'source'; target = source / name
                    target.parent.mkdir(parents=True); target.write_bytes(data)
                    manifest = root / 'sha256'; manifest.write_text(row['before_sha256'] + '  ' + name + '\n')
                    pins = root / 'pins.json'; pins.write_text(json.dumps({'files': {name: row['after_sha256']}}))
                    req = {'product_paths': [name], 'xpcshell': [], 'instrumentation': [],
                           'shutdown_instrumentation': {'expected_methods': []}}
                    with mock.patch.object(driver, 'reviewed_requirements', return_value=req), \
                         mock.patch.object(driver, 'HARNESS', pins), \
                         self.assertRaisesRegex(InvalidResult, 'audited harness changed'):
                        driver.source_binding(source, manifest)

    def test_current_target_overlay_changes_only_reviewed_rows_and_keeps_native_selection(self):
        read = lambda name: {line[66:]: line[:64] for line in (driver.HERE / name).read_text().splitlines()}
        old = read('historical-cleanup/proposed-native-test-source-sha256.txt')
        current = read('proposed-native-test-source-sha256.txt')
        rows = json.loads((driver.HERE / 'current-target-overlay.json').read_text())['changed_or_added_rows']
        self.assertEqual(len(rows), 4)
        self.assertEqual(set(current) - set(old), {r['path'] for r in rows if r['before_sha256'] is None})
        self.assertEqual({name for name in old if current[name] != old[name]},
                         {r['path'] for r in rows if r['before_sha256'] is not None})
        pins = json.loads(driver.HARNESS.read_text())['files']
        for row in rows:
            self.assertEqual(current[row['path']], row['after_sha256'])
            self.assertEqual(pins[row['path']], row['after_sha256'])
        previous = json.loads((driver.HERE / 'historical-cleanup/requirements.json').read_text())
        requirements = driver.reviewed_requirements()
        for key in ['xpcshell', 'instrumentation', 'shutdown_instrumentation', 'pending_xpcshell']:
            self.assertEqual(requirements[key], previous[key])

    def test_actual_old_home_or_cookie_fixture_cannot_pass_its_own_stale_manifest(self):
        rows = json.loads((driver.HERE / 'current-target-overlay.json').read_text())['changed_or_added_rows']
        rows = [row for row in rows if row['before_sha256'] is not None]
        self.assertEqual(len(rows), 2)
        with tarfile.open(driver.HERE / 'current-target-before-source.tar.gz') as archive:
            for row in rows:
                name = row['path']; data = archive.extractfile(name).read()
                self.assertEqual(hashlib.sha256(data).hexdigest(), row['before_sha256'])
                with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory); source = root / 'source'; target = source / name
                    target.parent.mkdir(parents=True); target.write_bytes(data)
                    manifest = root / 'sha256'; manifest.write_text(row['before_sha256'] + '  ' + name + '\n')
                    pins = root / 'pins.json'; pins.write_text(json.dumps({'files': {name: row['after_sha256']}}))
                    req = {'product_paths': [name], 'xpcshell': [], 'instrumentation': [],
                           'shutdown_instrumentation': {'expected_methods': []}}
                    with mock.patch.object(driver, 'reviewed_requirements', return_value=req), \
                         mock.patch.object(driver, 'HARNESS', pins), \
                         self.assertRaisesRegex(InvalidResult, 'audited harness changed'):
                        driver.source_binding(source, manifest)

    def test_source_receipt_is_required_in_preflight_and_archived_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'; path.write_text('{}')
            with mock.patch.object(driver, 'TASK37_SOURCE_RECEIPT', path), self.assertRaisesRegex(InvalidResult, 'source receipt'):
                driver.reviewed_requirements()
        case = pref_tests.ShutdownProcessEvidence(); self.addCleanup(case.doCleanups); case.setUp(); case.run_fake()
        self.assertEqual(grade_run(case.root)['status'], 'PENDING')
        (case.root / 'task37-source-receipt.json').write_text('{}')
        with self.assertRaisesRegex(InvalidResult, 'Task37 source receipt'):
            grade_run(case.root)

    def test_archive_inventory_is_bound_to_the_built_source(self):
        case = pref_tests.ShutdownProcessEvidence(); self.addCleanup(case.doCleanups); case.setUp(); case.run_fake()
        (case.root / 'task37-inventory.json').write_text('{}')
        with self.assertRaisesRegex(InvalidResult, 'Task37 inventory'):
            grade_run(case.root)


if __name__ == '__main__':
    unittest.main()
