"""Host-only regressions for real-runtime test selection and process evidence.

The logs/processes in this module are synthetic; no adb or native test is run.
"""
import copy
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

import driver
from grade import (InvalidResult, TEST_PACKAGE, SHUTDOWN_CLASS, PROCESS_LIST_ARGUMENTS,
                   grade_run, grade_xpcshell, instrumentation_arguments, process_snapshot,
                   sha, shutdown_selection)


def instrumented(methods, code=0):
    rows = []
    for index, method in enumerate(methods, 1):
        klass, name = method.split('#')
        for status in [1, code]:
            rows += [f'INSTRUMENTATION_STATUS: class={klass}',
                     f'INSTRUMENTATION_STATUS: test={name}',
                     f'INSTRUMENTATION_STATUS: numtests={len(methods)}',
                     f'INSTRUMENTATION_STATUS: current={index}',
                     f'INSTRUMENTATION_STATUS_CODE: {status}']
    return '\n'.join(rows + ['INSTRUMENTATION_RESULT: stream=',
        f'OK ({len(methods)} tests)', 'INSTRUMENTATION_CODE: -1', ''])


class PreferenceInventory(unittest.TestCase):
    def test_all_preexisting_cases_and_exclusions_preserved(self):
        old = json.loads((driver.HERE / 'previous-selection.json').read_text())
        new = driver.reviewed_requirements()
        self.assertEqual(new['xpcshell'][:len(old['xpcshell'])], old['xpcshell'])
        self.assertEqual(new['instrumentation'][:len(old['instrumentation'])], old['instrumentation'])
        self.assertEqual(new['pending_xpcshell'], old['pending_xpcshell'])
        self.assertEqual(sum(len(s['tasks']) for s in new['xpcshell']), 64)
        self.assertEqual(len(new['instrumentation']), 20)
        self.assertEqual(len(new['shutdown_instrumentation']['expected_methods']), 1)

    def test_each_new_native_task_needs_a_finished_record(self):
        req = driver.reviewed_requirements()
        inventory = json.loads(driver.TASK35_INVENTORY.read_text())
        for item in inventory['xpcshell_method_sets']:
            spec = next(s for s in req['xpcshell'] if s['path'] == item['source'])
            name = spec.get('test_id_prefix', '') + spec['path']
            events = [{'action': 'suite_start'}, {'action': 'test_start', 'test': name}]
            for task in spec['tasks']:
                events += [{'action': 'log', 'level': 'INFO', 'message': f'{name} | Starting {task}'},
                           {'action': 'test_status', 'test': name, 'status': 'PASS', 'subtest': 'assertion'},
                           {'action': 'log', 'level': 'INFO', 'message': f'head | test {task} finished (1)'}]
            events += [{'action': 'test_end', 'test': name, 'status': 'PASS'}, {'action': 'suite_end'}]
            render = lambda rows: ''.join(json.dumps(row) + '\n' for row in rows)
            self.assertEqual(len(grade_xpcshell(render(events), spec)['passed_tasks']), len(spec['tasks']))
            for task in spec['tasks']:
                with self.subTest(task=task), self.assertRaises(InvalidResult):
                    grade_xpcshell(render([r for r in events if f'| test {task} finished' not in r.get('message', '')]), spec)

    def test_final_source_receipts_override_old_shared_pins(self):
        pins = json.loads(driver.HARNESS.read_text())['files']
        final = {}
        for task in ['lw-m7-31', 'lw-m7-35', 'lw-m7-36']:
            for spec in json.loads((driver.HERE.parent / task / 'source-files.json').read_text())['files']:
                final[spec['path']] = spec['after_sha256']
        for name, digest in final.items():
            self.assertEqual(pins[name], digest, name)

    def test_actual_old_native_preference_source_fails_reviewed_pin(self):
        name = 'modules/libpref/Preferences.cpp'
        with tarfile.open(driver.HERE.parent / 'lw-m7-35/ordering-source-baseline.tar.gz') as archive:
            data = archive.extractfile(name).read()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'; (source / name).parent.mkdir(parents=True)
            (source / name).write_bytes(data)
            manifest = root / 'sha256'; manifest.write_text(sha(source / name) + '  ' + name + '\n')
            pins = root / 'pins.json'; expected = json.loads(driver.HARNESS.read_text())['files'][name]
            pins.write_text(json.dumps({'files': {name: expected}}))
            req = {'product_paths': [name], 'xpcshell': [], 'instrumentation': [],
                   'shutdown_instrumentation': {'expected_methods': []}}
            with mock.patch.object(driver, 'reviewed_requirements', return_value=req), \
                    mock.patch.object(driver, 'HARNESS', pins), self.assertRaisesRegex(InvalidResult, 'audited harness changed'):
                driver.source_binding(source, manifest)

    def test_old_manifest_missing_profile_tests_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'old').write_text('old source')
            manifest = root / 'sha256'; manifest.write_text(sha(root / 'old') + '  old\n')
            with self.assertRaisesRegex(InvalidResult, 'PrefSaveFileAsyncTest.kt'):
                driver.source_binding(root, manifest)

    def test_inventory_hash_and_selection_are_required(self):
        original = json.loads(driver.REQUIREMENTS.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'requirements.json'
            for change in ['hash', 'ordinary', 'shutdown', 'native', 'helper']:
                req = copy.deepcopy(original)
                if change == 'hash': req['task35_inventory_sha256'] = '0' * 64
                elif change == 'ordinary': req['instrumentation'].remove(json.loads(driver.TASK35_INVENTORY.read_text())['regular_instrumentation_methods'][-1])
                elif change == 'shutdown': req['shutdown_instrumentation']['instrumentation_arguments'].pop('redoubtAllowProfileShutdown')
                elif change == 'native': next(s for s in req['xpcshell'] if s['path'].endswith('/test_ext_android_update_settings.js'))['tasks'].pop()
                else: req['product_paths'].remove('mobile/android/geckoview/src/androidTest/assets/web_extensions/test-support/test-api.js')
                path.write_text(json.dumps(req))
                with self.subTest(change=change), mock.patch.object(driver, 'REQUIREMENTS', path), self.assertRaises(InvalidResult):
                    driver.reviewed_requirements()

    def test_shutdown_never_uses_a_method_selector_or_broad_list(self):
        req = driver.reviewed_requirements()
        args = instrumentation_arguments(req, shutdown=True)
        self.assertEqual(args[7], SHUTDOWN_CLASS)
        self.assertNotIn('#', args[7])
        self.assertEqual(args[8:11], ['-e', 'redoubtAllowProfileShutdown', 'true'])
        req['instrumentation'] += req['shutdown_instrumentation']['expected_methods']
        with self.assertRaises(InvalidResult): shutdown_selection(req)


class ShutdownProcessEvidence(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        self.req = driver.reviewed_requirements()
        self.req['xpcshell'] = []  # This fixture isolates instrumentation evidence grading.
        self.write('requirements.json', self.req)
        (self.root / 'task35-inventory.json').write_bytes(driver.TASK35_INVENTORY.read_bytes())
        (self.root / 'task36-inventory.json').write_bytes(driver.TASK36_INVENTORY.read_bytes())
        (self.root / 'task36-source-receipt.json').write_bytes(driver.TASK36_SOURCE_RECEIPT.read_bytes())
        binding = {'requirements_sha256': sha(self.root / 'requirements.json'),
                   'task35_inventory_sha256': sha(self.root / 'task35-inventory.json'),
                   'task36_inventory_sha256': sha(self.root / 'task36-inventory.json'),
                   'task36_source_receipt_sha256': sha(self.root / 'task36-source-receipt.json')}
        self.write('source-binding.json', binding); self.write('source-after-tests.json', binding)
        build = {'status': 'PASS', 'source_binding_sha256': sha(self.root / 'source-binding.json'),
                 'requirements_sha256': sha(self.root / 'requirements.json')}
        self.write('build-receipt.json', build)
        self.metadata = {'run_id': 'a' * 32, 'source_binding_sha256': sha(self.root / 'source-binding.json'),
                         'build_receipt_sha256': sha(self.root / 'build-receipt.json')}
        self.write('invocation.json', dict(self.metadata, device_serial='emulator-5554'))
        self.adb = ['/sdk/adb', '-s', 'emulator-5554']; self.calls = []; self.now = 10
        self.keep_old = False; self.stop_failure = False; self.shutdown_code = 0

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value) + '\n')

    def execute(self, command, cwd, env, log, timeout, metadata):
        self.calls.append(command)
        self.now += 10
        rc = 0
        if log.name == 'instrumentation.log':
            text = instrumented(self.req['instrumentation'])
        elif log.name == 'instrumentation-shutdown.log':
            text = instrumented(self.req['shutdown_instrumentation']['expected_methods'], self.shutdown_code)
        elif log.name == 'instrumentation-stop.log':
            text = ''; rc = 1 if self.stop_failure else 0
        else:
            text = '  PID NAME\n    1 /system/bin/init\n  600 org.mozilla.fenix\n'
            if log.name.endswith('before.log') or self.keep_old:
                text += f'  777 {TEST_PACKAGE}:tab0\n'
        log.write_text(text)
        receipt = dict(metadata, command=command, cwd=str(cwd), started_ns=self.now,
                       finished_ns=self.now + 2, log_created_ns=self.now + 1,
                       exit=rc, log=log.name, log_sha256=sha(log))
        self.write(log.name + '.receipt.json', receipt)
        return receipt

    def run_fake(self):
        with mock.patch.object(driver, 'execute', side_effect=self.execute), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('no actual process allowed')):
            return driver.run_instrumentation(self.adb, self.root, {}, self.root, 30, self.metadata, self.req)

    def test_real_driver_flow_stops_only_test_package_between_invocations(self):
        results = self.run_fake()
        self.assertEqual(len(results), 2)
        self.assertEqual(self.calls, [
            self.adb + instrumentation_arguments(self.req),
            self.adb + PROCESS_LIST_ARGUMENTS,
            self.adb + ['shell', 'am', 'force-stop', TEST_PACKAGE],
            self.adb + PROCESS_LIST_ARGUMENTS,
            self.adb + instrumentation_arguments(self.req, shutdown=True)])
        verdict = grade_run(self.root)
        self.assertEqual(verdict['status'], 'PENDING')  # Original Android exclusions remain.
        self.assertEqual(verdict['results'][-1]['old_test_processes'], {777: TEST_PACKAGE + ':tab0'})

    def test_missing_process_boundary_cannot_be_replaced_by_junit_pass(self):
        for name in ['instrumentation-stop.log.receipt.json', 'instrumentation-processes-after.log.receipt.json']:
            self.run_fake(); (self.root / name).unlink()
            with self.subTest(name=name), self.assertRaises((InvalidResult, OSError)): grade_run(self.root)

    def test_old_child_process_or_failed_stop_prevents_shutdown_start(self):
        for flag in ['keep_old', 'stop_failure']:
            self.calls.clear(); setattr(self, flag, True)
            with self.subTest(flag=flag), self.assertRaises(InvalidResult): self.run_fake()
            self.assertFalse(any('redoubtAllowProfileShutdown' in c for c in self.calls))
            setattr(self, flag, False)

    def test_shutdown_assumption_is_not_accepted(self):
        for code in [-3, -4]:
            self.shutdown_code = code
            with self.subTest(code=code), self.assertRaises(InvalidResult): self.run_fake()
            with self.assertRaises(InvalidResult): grade_run(self.root)

    def test_timing_foreign_device_opt_in_and_stop_target_are_bound(self):
        for change in ['timing', 'device', 'opt-in', 'stop-target', 'foreign-run']:
            self.run_fake()
            name = 'instrumentation-stop.log.receipt.json' if change == 'stop-target' else 'instrumentation-shutdown.log.receipt.json'
            receipt = json.loads((self.root / name).read_text())
            if change == 'timing': receipt.update(started_ns=1, log_created_ns=2)
            elif change == 'device': receipt['command'][2] = 'emulator-9999'
            elif change == 'opt-in': receipt['command'][-2] = 'false'
            elif change == 'stop-target': receipt['command'][-1] = 'org.mozilla.fenix'
            else: receipt['run_id'] = 'f' * 32
            self.write(name, receipt)
            with self.subTest(change=change), self.assertRaises(InvalidResult): grade_run(self.root)

    def test_changed_inventory_and_partial_shutdown_fail_replay(self):
        self.run_fake(); (self.root / 'task35-inventory.json').write_text('{}')
        with self.assertRaises(InvalidResult): grade_run(self.root)
        (self.root / 'task35-inventory.json').write_bytes(driver.TASK35_INVENTORY.read_bytes())
        (self.root / 'instrumentation-shutdown.log').write_text('OK (1 tests)\n')
        with self.assertRaises(InvalidResult): grade_run(self.root)

    def test_process_listing_needs_full_header_init_and_unique_rows(self):
        for text in ['', 'PID NAME\n', 'PID CMD\n1 init\n', 'PID NAME\n1 init\n1 init\n', 'PID NAME\n1 init']:
            with self.subTest(text=text), self.assertRaises(InvalidResult): process_snapshot(text)
        self.assertEqual(process_snapshot('PID NAME\n1 init\n99 org.mozilla.geckoview.test_runner\n'), {})
        self.assertEqual(process_snapshot('PID NAME\n1 init\n42 org.mozilla.geckoview.test\n'), {42: TEST_PACKAGE})


if __name__ == '__main__':
    unittest.main()
