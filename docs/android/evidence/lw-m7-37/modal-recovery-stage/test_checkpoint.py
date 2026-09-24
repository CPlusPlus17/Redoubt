#!/usr/bin/env python3
"""Versioned checkpoint admission controls; no guest or installed-APK verdict."""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

import stage as s


class VersionContracts(unittest.TestCase):
    def test_imports_select_new_runtime_and_preserve_original_authority(self):
        self.assertEqual(s.c.RUNTIME.name, 'modal-process-runtime')
        self.assertIs(s.prior_runtime.c, s.c)
        self.assertIs(s.prior_runtime.implementation.c, s.c)
        self.assertEqual(s.c.PREVIOUS_RUNTIME.name, 'harness-process-runtime')
        self.assertEqual(s.c.engine.RUNTIME.name, 'modal-process-runtime')
        self.assertIs(s.c.original_runtime.c, s.c.base)
        self.assertEqual(s.c.base.RUNTIME.name, 'account-process-runtime')
        self.assertEqual(s.v.HERE.name, 'process-recovery-composition')
        self.assertEqual(s.SERVICE, 'redoubt-account-process245-source-stage-20260909.service')
        self.assertEqual(s.OUT.name, 'account-process245-source-stage')

    def test_exact_runtime_capsule_and_original_modules_are_pinned(self):
        pins = s.version_inputs()
        paths = {row['path'] for row in s.own_inputs()}
        for row in s.checkpoint_inputs():
            self.assertIn(row['path'], paths)
        self.assertEqual(len(pins['checkpoint_files']), 18)
        self.assertEqual(len(pins['parent_helper_files']), 39)
        self.assertNotIn(str(s.CHECKPOINT / 'build.py'), paths)
        self.assertIn(str(s.c.PARENT / 'build.py'), paths)
        for name in s.c.CAPSULE_PATHS:
            self.assertIn(str(s.c.CAPSULE / name), paths)
        self.assertIn(str(s.c.FAILED_ARCHIVE), paths)
        self.assertIn(str(s.c.PREVIOUS_ARCHIVE), paths)
        for name in pins['parent_helper_files']:
            self.assertIn(str(s.v.REPO / name), paths)
        self.assertIn(str(s.HERE / 'stage.py'), paths)
        self.assertIn(str(s.COMPOSITION / 'stage.py'), paths)

    def test_actual_failed0189_archive_is_failure_history_only(self):
        files, state, config = s.c.archived_previous()
        self.assertEqual(len(files), 95)
        self.assertEqual(state['status'], 'FAIL')
        self.assertEqual(state['service']['InvocationID'], s.c.PREVIOUS_INVOCATION)
        self.assertEqual(config['apk_service']['InvocationID'], s.c.BUILD_INVOCATION)
        self.assertNotEqual(s.c.PREVIOUS_SERVICE, s.c.SERVICES['runtime'])

    def test_import_preserves_existing_common_module_or_explicit_none(self):
        for existing in (ModuleType('unrelated_common'), None):
            with self.subTest(existing=existing), patch.dict(sys.modules, {'common': existing}):
                imported = s.module('modal245_import_control', s.HERE / 'stage.py')
                self.assertIs(sys.modules['common'], existing)
                self.assertIs(imported.prior_runtime.implementation.c, imported.c)
                self.assertIs(imported.c.original_runtime.c, imported.c.base)
                self.assertIsNot(imported.c.engine, s.c.engine)

    def test_drift_in_retained_parent_capsule_is_rejected(self):
        pins = s.version_inputs()
        name = next(n for n in pins['parent_helper_files']
                    if n.endswith('harness-process-recovery/capsule/scripts/android-graphics-smoke.py'))
        record = s.c.record
        def changed(path):
            value = record(path)
            return {**value, 'sha256': '0' * 64} if path == s.v.REPO / name else value
        with patch.object(s.c, 'record', side_effect=changed), self.assertRaisesRegex(ValueError, 'retained parent helper'):
            s.version_inputs()

    def test_changed_checkpoint_record_cannot_silently_refresh_input_pins(self):
        records = s.checkpoint_inputs()
        records[0] = {**records[0], 'sha256': '0' * 64}
        with patch.object(s, 'checkpoint_inputs', return_value=records), self.assertRaisesRegex(ValueError, 'reviewed checkpoint'):
            s.version_inputs()

    def test_unchanged_composition_contains_full245_and107_bodies(self):
        plan = s.v.load_plan()
        self.assertEqual(len(plan['final']), 245)
        self.assertEqual(len(plan['before']), 245)
        self.assertEqual(len(plan['bodies']), 107)
        self.assertEqual(sum(x is None for x in plan['before'].values()), 45)
        self.assertEqual(s.v.sha(plan['files']['proposed-source-sha256.txt']),
                         '40da1bf9c42187b1e037fba5b443e4b26fd2758ffa7b07212710df72693eb806')


class CheckpointContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='harness245-checkpoint-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / 'runtime'
        self.build = self.root / 'build'
        self.stage = self.root / 'stage'
        for folder in (self.runtime, self.build, self.stage):
            folder.mkdir()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for key, value in [('RUNTIME', self.runtime), ('BUILD', self.build),
                           ('STAGE', self.stage), ('CURRENT', s.v.BASE)]:
            self.stack.enter_context(patch.object(s.c, key, value))
        self.source_rows = {f'source/{i}': 'a' * 64 for i in range(167)}
        (self.stage / 'source-sha256.txt').write_text(''.join(f'{sha}  {name}\n' for name, sha in self.source_rows.items()))
        self.apk = self.put(self.root / 'candidate.apk', b'fixture; never installed')
        self.terminal = {'InvocationID': '1' * 32, 'RemainAfterExit': 'yes',
                         'ActiveState': 'active', 'SubState': 'exited', 'Result': 'success', 'ExecMainStatus': '0'}
        self.config = {'test_service': self.terminal, 'apk_service': self.terminal,
                       'apks': {'fenix-x86_64-release.apk': self.apk}}
        build_config = self.put(self.build / 'inputs.json', b'{}')
        self.build_state = {'apks': self.config['apks'], 'inputs': build_config}
        self.config['build_receipt'] = self.put(self.build / 'result.json', json.dumps(self.build_state).encode())
        config_record = self.put(self.runtime / 'inputs.json', json.dumps(self.config).encode())
        source = self.put(self.runtime / 'source-sha256.txt', b'synthetic source receipt')
        # The hash identifies the real expected source at this boundary; source
        # body verification remains a separately mocked external prerequisite.
        source['sha256'] = s.v.BASE
        self.state = {'schema': 1, 'kind': 'runtime', 'status': 'PASS', 'inputs': config_record,
                      'source_manifest': source, 'started': self.put(self.runtime / 'started.txt', b'start'),
                      'finished': self.put(self.runtime / 'finished.txt', b'end'), 'service': self.terminal,
                      'emulator_cleanup_exit': 0, 'input_checks': {}, 'stages': {}}
        for name in ('source-before.txt', 'source-after.txt', 'native-before.txt', 'native-after.txt'):
            body = ''.join(n + ': OK\n' for n in self.source_rows).encode() if name.startswith('source-') else b'native fixture'
            self.state['input_checks'][name] = self.put(self.runtime / name, body)
        for label in ('ubo-lifecycle', 'baseline', 'pref-audit'):
            self.state['stages'][label] = {'exit': 0, 'log': self.put(self.runtime / (label + '.log'), b'fixture')}
        for key, names in [('ubo_lifecycle', s.prior_runtime.UBO), ('baseline', s.prior_runtime.BASELINE), ('pref_dump', {'pref-dump'})]:
            report = {'status': 'completed', 'error': None, 'tainted': False, 'injected_prefs': {},
                      'artifact': {'path': self.apk['path'], 'sha256': self.apk['sha256'], 'size': self.apk['bytes'],
                                   'harness_sha256': s.c.digest(s.c.CAPSULE / 'scripts/android-smoke.sh')},
                      'checks': [{'check': name, 'ok': True} for name in sorted(names)]}
            self.state[key] = self.put(self.runtime / (key + '.json'), json.dumps(report).encode())
        self.native = self.root / 'native.txt'
        self.native.write_text(''.join(f'{row["sha256"]}  {row["path"]}\n' for row in
                                     [self.put(self.root / f'native-{i}', b'native fixture') for i in range(3)]))
        self.stack.enter_context(patch.object(s.c, 'NATIVE_MANIFEST', self.native))
        self.stack.enter_context(patch.object(s.c, 'load_config', return_value=self.config))
        self.stack.enter_context(patch.object(s.prior_runtime, 'checked_build', return_value=(self.build_state, self.terminal)))
        real_checked = s.c.checked
        self.stack.enter_context(patch.object(s.c, 'checked', side_effect=lambda row:
            self.runtime / 'source-sha256.txt' if row == source else real_checked(row)))
        self.services = self.stack.enter_context(patch.object(s.c, 'service', return_value=self.terminal))

    def put(self, path, body):
        path.write_bytes(body)
        return s.c.record(path)

    def run_prerequisites(self):
        self.put(self.runtime / 'result.json', json.dumps(self.state).encode())
        return s.prerequisites()

    def mutate_report(self, key, operation):
        path = Path(self.state[key]['path'])
        payload = json.loads(path.read_text())
        operation(payload)
        self.state[key] = self.put(path, json.dumps(payload).encode())

    def test_all_named_reports_and_new_terminal_service_are_required(self):
        result = self.run_prerequisites()
        self.assertEqual(result['runtime_service'], self.terminal)
        self.services.assert_called_once_with('redoubt-modal-process-runtime-20260909.service', '1' * 32, terminal=True)
        self.assertGreater(len(result['preserved_files']), 10)

    def test_failed_runtime_never_reaches_config_or_report_admission(self):
        self.state['status'] = 'FAIL'
        with self.assertRaisesRegex(ValueError, 'successful new current167'):
            self.run_prerequisites()
        s.c.load_config.assert_not_called()

    def test_missing_ubo_check_cannot_pass(self):
        self.mutate_report('ubo_lifecycle', lambda p: p['checks'].pop())
        with self.assertRaisesRegex(ValueError, 'checks missing or failed'):
            self.run_prerequisites()

    def test_failed_baseline_cannot_pass(self):
        self.mutate_report('baseline', lambda p: p['checks'][0].update(ok=False))
        with self.assertRaisesRegex(ValueError, 'checks missing or failed'):
            self.run_prerequisites()

    def test_original_harness_hash_does_not_validate_corrected_capsule_report(self):
        self.mutate_report('pref_dump', lambda p: p['artifact'].update(harness_sha256='0' * 64))
        with self.assertRaisesRegex(ValueError, 'another APK/harness'):
            self.run_prerequisites()

    def test_failed_cleanup_cannot_pass(self):
        self.state['emulator_cleanup_exit'] = 1
        with self.assertRaisesRegex(ValueError, 'cleanup'):
            self.run_prerequisites()

    def test_replaced_or_nonterminal_service_cannot_pass(self):
        self.services.side_effect = ValueError('service invocation differs')
        with self.assertRaisesRegex(ValueError, 'invocation differs'):
            self.run_prerequisites()

    def test_partial_source_after_receipt_cannot_pass(self):
        self.state['input_checks']['source-after.txt'] = self.put(self.runtime / 'source-after.txt', b'one: OK\n')
        with self.assertRaisesRegex(ValueError, 'source receipt incomplete'):
            self.run_prerequisites()


if __name__ == '__main__':
    unittest.main(verbosity=2)
