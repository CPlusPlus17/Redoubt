"""Host admission/result controls. No guest, emulator, APK install or target execution."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as c
import runtime as r


class CapsuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(c.CAPSULE, self.root / 'capsule')
        shutil.copy2(HERE / 'capsule-files.json', self.root / 'capsule-files.json')

    def check(self):
        with patch.object(c, 'HERE', self.root), patch.object(c, 'CAPSULE', self.root / 'capsule'):
            return c.capsule_inputs()

    def test_exact_actual_five_files_and_original_base_module_are_preserved(self):
        self.assertEqual(len(self.check()), 5)
        self.assertIs(c.original_runtime.c, c.base)
        self.assertEqual(c.base.REPO, c.REPO)
        self.assertNotEqual(c.base.REPO, c.CAPSULE)
        self.assertEqual(r.UBO, c.original_runtime.UBO)
        self.assertEqual(r.BASELINE, c.original_runtime.BASELINE)
        self.assertEqual((len(r.UBO), len(r.BASELINE)), (10, 8))

    def test_each_missing_or_changed_capsule_file_is_rejected(self):
        for name in c.CAPSULE_PATHS:
            path = self.root / 'capsule' / name; body = path.read_bytes()
            with self.subTest(name=name, mode='changed'):
                path.write_bytes(body + b'changed')
                with self.assertRaisesRegex(ValueError, 'capsule input changed'): self.check()
            path.unlink()
            with self.subTest(name=name, mode='missing'):
                with self.assertRaisesRegex(ValueError, 'capsule file missing'): self.check()
            path.write_bytes(body); path.chmod(0o755 if name.endswith('.sh') else 0o644)

    def test_extra_and_linked_capsule_files_are_rejected(self):
        extra = self.root / 'capsule' / 'extra'; extra.write_text('not reviewed')
        with self.assertRaises(ValueError): self.check()
        extra.unlink(); extra.symlink_to('/tmp')
        with self.assertRaisesRegex(ValueError, 'linked capsule'): self.check()


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive_files, cls.failed, cls.failed_config = c.archived_history()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_actual_failure_archive_is_exact_and_never_a_success(self):
        self.assertEqual(len(self.archive_files), 55)
        self.assertEqual(self.failed['status'], 'FAIL')
        self.assertEqual(self.failed['service']['InvocationID'], c.FAILED_INVOCATION)
        path = self.root / 'changed.tar.gz'; path.write_bytes(b'changed')
        with patch.object(c, 'FAILED_ARCHIVE', path), self.assertRaisesRegex(ValueError, 'archive changed'):
            c.archived_history()

    def test_other_source_or_test_invocation_is_rejected(self):
        for key, value in [('source_manifest_sha256', 'a'*64), ('test_invocation', 'b'*32)]:
            selection = dict(self.failed_config['selection'], **{key: value})
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'same reviewed source/full-test'):
                c.select_inputs(selection)

    def history_record(self, path):
        path = Path(path)
        roots = {'runtime-checkpoint': c.base.RUNTIME, 'runtime-work': c.base.RUNTIME_WORK,
                 'configuration': c.REPO}
        if path == c.FAILED_ARCHIVE:
            return {'path': str(path), 'sha256': c.FAILED_ARCHIVE_SHA, 'bytes': path.stat().st_size}
        for prefix, root in roots.items():
            if path.is_relative_to(root):
                name = prefix + '/' + path.relative_to(root).as_posix()
                if name in self.archive_files:
                    body = self.archive_files[name]
                    return {'path': str(path), 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
        raise AssertionError(path)

    def test_failed_history_requires_all_old_bytes_and_same_terminal_invocation(self):
        terminal = {'InvocationID': c.FAILED_INVOCATION, 'ExecMainStatus': '1',
                    'RemainAfterExit': 'yes', 'ActiveState': 'failed', 'SubState': 'failed', 'Result': 'exit-code'}
        with patch.object(c, 'archived_history', return_value=(self.archive_files, self.failed, self.failed_config)), \
             patch.object(c.base, 'record', side_effect=self.history_record), \
             patch.object(c.base, 'preserved_tree', return_value={'retained': 'host fixture'}), \
             patch.object(c.base, 'service', return_value=terminal):
            self.assertEqual(c.failed_history()['service'], terminal)
            original = self.history_record
            def changed(path):
                row = original(path)
                if str(path).endswith('baseline.json'): row['sha256'] = '0'*64
                return row
            with patch.object(c.base, 'record', side_effect=changed), self.assertRaisesRegex(ValueError, 'evidence/original code changed'):
                c.failed_history()
            for change in [{'ExecMainStatus': '0'}, {'ActiveState': 'active', 'SubState': 'running'}]:
                with patch.object(c.base, 'service', return_value=terminal | change), self.assertRaisesRegex(ValueError, 'not terminal'):
                    c.failed_history()

    def test_same_build_uses_original_config_validation_and_rejects_another_service(self):
        folder = self.root / 'build'; folder.mkdir()
        config_path = folder / 'inputs.json'; config_path.write_text(json.dumps({'selection': self.failed_config['selection']}))
        state = {'inputs': c.base.record(config_path)}; (folder / 'result.json').write_text(json.dumps(state))
        config = {'selection': self.failed_config['selection']}
        with patch.object(c.base, 'BUILD', folder), patch.object(c.base, 'load_config', return_value=config) as original, \
             patch.object(c.original_runtime, 'checked_build', return_value=(state, {'InvocationID': c.BUILD_INVOCATION})):
            self.assertEqual(c.checked_build()[0], state)
            self.assertEqual(original.call_args.args, (config_path, c.base.digest(config_path), 'apk'))
            with patch.object(c.original_runtime, 'checked_build', return_value=(state, {'InvocationID': 'd'*32})), \
                 self.assertRaisesRegex(ValueError, 'different successful APK invocation'):
                c.checked_build()

    def test_config_cannot_change_original_apk_dependencies_or_version_linkage(self):
        parent_path = self.root / 'parent.json'
        parent = json.loads((c.REPO / 'docs/android/evidence/lw-m7-21/current-account-process-apk/inputs.json').read_text())
        parent_path.write_text(json.dumps(parent))
        build_dir = self.root / 'build'; build_dir.mkdir(); (build_dir / 'result.json').write_text('bound build')
        build = {'inputs': c.base.record(parent_path), 'apks': self.failed_config['apks'], 'metadata': self.failed_config['metadata']}
        terminal = self.failed_config['apk_service']
        config = dict(parent, kind='runtime', service_name=c.SERVICES['runtime'],
                      parent_build_inputs=c.base.record(parent_path), build_receipt=c.base.record(build_dir / 'result.json'),
                      capsule_inputs=['capsule fixture'], runtime_repository_files={'driver': 'fixture'},
                      failed_runtime={'history': 'fixture'}, apks=build['apks'], metadata=build['metadata'], apk_service=terminal)
        path = self.root / 'config.json'
        def write(): path.write_text(json.dumps(config)); return c.base.digest(path)
        with patch.object(c.base, 'load_config', return_value=parent), patch.object(c.base, 'BUILD', build_dir), \
             patch.object(c, 'checked_build', return_value=(build, terminal)), \
             patch.object(c, 'capsule_inputs', return_value=['capsule fixture']), \
             patch.object(c, 'runtime_inputs', return_value={'driver': 'fixture'}), \
             patch.object(c, 'failed_history', return_value={'history': 'fixture'}):
            self.assertEqual(c.load_config(path, write(), 'runtime'), config)
            for key, value in [('repository_files', {}), ('source_sha256', 'b'*64), ('selection', {}),
                               ('service_name', 'other.service'), ('apks', {}), ('failed_runtime', {})]:
                old = config[key]; config[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError): c.load_config(path, write(), 'runtime')
                config[key] = old


class SmokeGrading(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'smoke.json'
        self.apk = {'path': '/host-fixture/apk', 'sha256': 'a'*64, 'bytes': 1}
        self.report = {'status': 'completed', 'error': None, 'tainted': False, 'injected_prefs': {},
                       'artifact': {'path': self.apk['path'], 'sha256': self.apk['sha256'], 'size': 1,
                                    'harness_sha256': c.base.digest(c.CAPSULE / 'scripts/android-smoke.sh')},
                       'checks': [{'check': name, 'ok': True} for name in sorted(r.UBO)]}

    def grade(self, required=None):
        self.path.write_text(json.dumps(self.report))
        return r.grade_smoke(self.path, required or r.UBO, self.apk)

    def test_complete_capsule_bound_report_passes(self):
        self.assertEqual(self.grade()['sha256'], c.base.digest(self.path))

    def test_each_ubo_and_baseline_gate_is_still_required(self):
        for required in [r.UBO, r.BASELINE, {'pref-dump'}]:
            for missing in required:
                self.report['checks'] = [{'check': name, 'ok': True} for name in required - {missing}]
                with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, 'checks missing'):
                    self.grade(required)

    def test_incomplete_failed_tainted_and_injected_reports_are_rejected(self):
        for key, value in [('status', 'running'), ('error', 'startup failed'), ('tainted', True),
                           ('injected_prefs', {'webgl.disabled': False})]:
            old = self.report[key]; self.report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.grade()
            self.report[key] = old
        self.report['checks'][0]['ok'] = False
        with self.assertRaises(ValueError): self.grade()

    def test_wrong_apk_or_original_harness_report_cannot_pass(self):
        archived = c.archived_history()[0]['configuration/scripts/android-smoke.sh']
        for key, value in [('path', '/other.apk'), ('size', 2), ('sha256', 'b'*64),
                           ('harness_sha256', hashlib.sha256(archived).hexdigest())]:
            old = self.report['artifact'][key]; self.report['artifact'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'another APK/harness'): self.grade()
            self.report['artifact'][key] = old

    def test_final_history_or_capsule_change_forces_failure(self):
        state = {'status': 'PASS', 'inputs': {'path': '/host-fixture/inputs.json', 'sha256': 'a'*64}}
        with patch.object(c.base, 'checked', return_value=Path('/host-fixture/inputs.json')), \
             patch.object(c, 'load_config', side_effect=ValueError('capsule/history changed')), \
             patch.object(c.base, 'finish') as original:
            c.finish(state, Path('/host-fixture/evidence'))
        self.assertEqual(state['status'], 'FAIL')
        self.assertIn('capsule/history changed', state['recovery_input_error'])
        original.assert_called_once()


class RuntimeFlow(unittest.TestCase):
    def run_flow(self, failed_gate=None, cleanup=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); evidence = root / 'runtime'; work = root / 'work'
            build = root / 'build'; build.mkdir(); (build / 'result.json').write_text('same APK receipt fixture')
            apk = {'path': '/host-fixture/same.apk', 'sha256': 'a'*64, 'bytes': 1}
            config = {'apks': {'fenix-x86_64-release.apk': apk},
                      'build_receipt': c.base.record(build / 'result.json'), 'sdk_inputs': ['sdk fixture']}
            state = {'status': 'RUNNING', 'stages': {}}
            commands = []
            def initial(*args): evidence.mkdir(); return state
            def stage(state, folder, label, command, env):
                commands.append((label, command, env))
                checks, target = {'ubo-lifecycle': (r.UBO, evidence / 'ubo-lifecycle.json'),
                                  'baseline': (r.BASELINE, evidence / 'baseline.json'),
                                  'pref-audit': ({'pref-dump'}, work / 'smoke-pref-audit/result.json')}[label]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({'status': 'completed', 'error': None, 'tainted': False,
                    'injected_prefs': {}, 'artifact': {'path': apk['path'], 'sha256': apk['sha256'], 'size': 1,
                    'harness_sha256': c.base.digest(c.CAPSULE / 'scripts/android-smoke.sh')},
                    'checks': [{'check': name, 'ok': True} for name in checks]}))
                return int(label == failed_gate)
            attached = ['devices', [['emulator-5554', 'device']]]
            with patch.object(c, 'RUNTIME', evidence), patch.object(c, 'RUNTIME_WORK', work), \
                 patch.object(c.base, 'BUILD', build), patch.object(c, 'guest_guard'), \
                 patch.object(c, 'own_service'), patch.object(c, 'initial_state', side_effect=initial), \
                 patch.object(c, 'source_check') as source_check, patch.object(c, 'native_check'), \
                 patch.object(c, 'run_stage', side_effect=stage), patch.object(c, 'load_config', return_value=config), \
                 patch.object(c, 'finish') as finish, patch.object(r, 'validate', return_value=config), \
                 patch.object(r, 'checked_build'), patch.object(r, 'sdk_inputs', return_value=['sdk fixture']), \
                 patch.object(r, 'devices', side_effect=[('no devices', []), attached, attached]), \
                 patch.object(r.subprocess, 'run', return_value=SimpleNamespace(returncode=cleanup, stdout='', stderr='')) as subprocess:
                if failed_gate or cleanup:
                    with self.assertRaises((ValueError, RuntimeError)):
                        r.execute(root / 'config.json', 'b'*64)
                    self.assertEqual(state['status'], 'FAIL')
                else:
                    self.assertEqual(r.execute(root / 'config.json', 'b'*64), 0)
                    self.assertEqual(state['status'], 'PASS')
                finish.assert_called_once_with(state, evidence)
                self.assertEqual(subprocess.call_args.args[0][-4:], ['-s', 'emulator-5554', 'emu', 'kill'])
                self.assertEqual([row[0] for row in commands], ['ubo-lifecycle', 'baseline', 'pref-audit'])
                for label, command, env in commands:
                    expected = 'android-pref-audit.sh' if label == 'pref-audit' else 'android-smoke.sh'
                    self.assertEqual(command[0], str(c.CAPSULE / 'scripts' / expected))
                    self.assertEqual(env['LW_SMOKE_APK'], apk['path'])
                self.assertIn('--check-ubo-lifecycle', commands[0][1])
                self.assertGreaterEqual(source_check.call_count, 1)

    def test_actual_retry_flow_routes_all_gates_through_capsule_and_cleans_owned_emulator(self):
        self.run_flow()

    def test_each_failed_gate_and_failed_cleanup_prevents_runtime_pass(self):
        for gate in ['ubo-lifecycle', 'baseline', 'pref-audit']:
            with self.subTest(gate=gate): self.run_flow(failed_gate=gate)
        self.run_flow(cleanup=1)


if __name__ == '__main__':
    unittest.main()
