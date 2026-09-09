"""Host checks for the private module boundary and both retained runtime failures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('tested_modal_common', HERE / 'common.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
r = c.private_module('tested_modal_runtime', HERE / 'runtime.py', common=c)


class ModuleBoundary(unittest.TestCase):
    def test_actual_capsule_changes_only_the_pinned_graphics_input(self):
        current = json.loads((HERE / 'capsule-files.json').read_text())['files']
        prior = json.loads((c.FROZEN / 'capsule-files.json').read_text())['files']
        self.assertEqual(set(current), set(prior))
        self.assertEqual({name for name in current if current[name] != prior[name]}, {'scripts/android-graphics-smoke.py'})
        self.assertEqual(len(c.capsule_inputs()), 5)

    def test_changed_or_missing_capsule_still_fails_in_the_inherited_validator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(HERE / 'capsule', root / 'capsule')
            shutil.copy2(HERE / 'capsule-files.json', root / 'capsule-files.json')
            with patch.object(c.engine, 'HERE', root), patch.object(c.engine, 'CAPSULE', root / 'capsule'):
                for name in c.engine.CAPSULE_PATHS:
                    path = root / 'capsule' / name; data = path.read_bytes()
                    with self.subTest(name=name):
                        path.write_bytes(data + b'changed')
                        with self.assertRaisesRegex(ValueError, 'capsule input changed'): c.capsule_inputs()
                        path.unlink()
                        with self.assertRaisesRegex(ValueError, 'capsule file missing'): c.capsule_inputs()
                    path.write_bytes(data); path.chmod(0o755 if name.endswith('.sh') else 0o644)

    def test_only_private_instance_constants_change_and_runtime_functions_are_frozen(self):
        witness = c.private_module('untouched_frozen_common', c.FROZEN / 'common.py')
        self.assertEqual(witness.HERE, c.FROZEN)
        self.assertEqual(witness.RUNTIME, c.PREVIOUS_RUNTIME)
        self.assertEqual(witness.SERVICES['runtime'], c.PREVIOUS_SERVICE)
        self.assertIsNot(witness, c.engine)
        self.assertEqual(c.engine.base.REPO, c.REPO)
        self.assertIs(c.engine.original_runtime.c, c.engine.base)
        self.assertEqual(c.engine.HERE, HERE)
        self.assertEqual(c.engine.CAPSULE, HERE / 'capsule')
        self.assertIs(r.implementation.c, c)
        self.assertEqual(Path(r.execute.__code__.co_filename), c.FROZEN / 'runtime.py')
        self.assertEqual((len(r.UBO), len(r.BASELINE)), (10, 8))
        self.assertEqual(r.UBO, witness.original_runtime.UBO)
        self.assertEqual(r.BASELINE, witness.original_runtime.BASELINE)

    def test_existing_hostile_or_none_common_is_restored_after_success_and_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.py'
            bound = ModuleType('explicitly_bound')
            for before in [ModuleType('hostile_existing'), None]:
                for raises in [False, True]:
                    path.write_text('import common\nobserved = common\n' + ('raise RuntimeError("fixture")\n' if raises else ''))
                    with self.subTest(before=before, raises=raises), patch.dict(sys.modules, {'common': before}):
                        if raises:
                            with self.assertRaisesRegex(RuntimeError, 'fixture'): c.private_module('fixture', path, bound)
                        else:
                            self.assertIs(c.private_module('fixture', path, bound).observed, bound)
                        self.assertIn('common', sys.modules)
                        self.assertIs(sys.modules['common'], before)

    def test_absent_common_remains_absent(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules):
            sys.modules.pop('common', None)
            path = Path(directory) / 'fixture.py'; path.write_text('import common\n')
            c.private_module('fixture', path, ModuleType('bound'))
            self.assertNotIn('common', sys.modules)

    def test_modified_inherited_source_rejected_before_private_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); frozen = root / 'frozen'; frozen.mkdir()
            for name in ['common.py', 'runtime.py', 'capsule-files.json']:
                shutil.copy2(c.FROZEN / name, frozen / name)
            (frozen / 'runtime.py').write_text('raise AssertionError("unreviewed source executed")')
            with patch.object(c, 'FROZEN', frozen), patch.object(c, 'REPO', root), \
                 self.assertRaisesRegex(ValueError, 'frozen inherited input changed'):
                c.inherited_inputs()


class HistoryAndConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files, cls.state, cls.config = c.archived_previous()

    def test_actual95_member_archive_retains_successful_ubo_and_failed_baseline(self):
        self.assertEqual(len(self.files), 95)
        self.assertEqual(self.state['status'], 'FAIL')
        self.assertEqual(self.state['stages']['ubo-lifecycle']['exit'], 0)
        self.assertEqual(self.state['stages']['baseline']['exit'], 1)
        old = c.engine.archived_history()[1]
        self.assertEqual(old['service']['InvocationID'], c.engine.FAILED_INVOCATION)
        self.assertEqual(old['status'], 'FAIL')

    def test_changed0189_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'archive'; path.write_text('changed')
            with patch.object(c, 'PREVIOUS_ARCHIVE', path), self.assertRaisesRegex(ValueError, '0189 failure archive changed'):
                c.archived_previous()

    def actual_record(self, path):
        path = Path(path)
        if path == c.PREVIOUS_ARCHIVE: return {'path': str(path), 'sha256': c.PREVIOUS_ARCHIVE_SHA, 'bytes': path.stat().st_size}
        for prefix, root in [('runtime-checkpoint', c.PREVIOUS_RUNTIME), ('runtime-work', c.PREVIOUS_WORK), ('configuration', c.REPO)]:
            if path.is_relative_to(root):
                name = prefix + '/' + path.relative_to(root).as_posix()
                if name in self.files:
                    body = self.files[name]; return {'path': str(path), 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
        raise AssertionError(path)

    def test_all_previous_bytes_and_failed_invocation_are_required(self):
        terminal = {'ExecMainStatus': '1', 'ActiveState': 'failed', 'SubState': 'failed'}
        with patch.object(c, 'archived_previous', return_value=(self.files, self.state, self.config)), \
             patch.object(c.engine.base, 'record', side_effect=self.actual_record), \
             patch.object(c.engine.base, 'preserved_tree', return_value={'host fixture': True}), \
             patch.object(c.engine.base, 'service', return_value=terminal) as service:
            c.previous_history()
            service.assert_called_with(c.PREVIOUS_SERVICE, c.PREVIOUS_INVOCATION)
            def changed(path):
                row = self.actual_record(path)
                if str(path).endswith('graphics-results.json'): row['sha256'] = 'a'*64
                return row
            with patch.object(c.engine.base, 'record', side_effect=changed), self.assertRaisesRegex(ValueError, '0189 evidence/original capsule changed'):
                c.previous_history()
            with patch.object(c.engine.base, 'service', return_value=terminal | {'ExecMainStatus': '0'}), \
                 self.assertRaisesRegex(ValueError, 'same terminal failure'):
                c.previous_history()

    def test_extended_runtime_inputs_and_configuration_maps_have_explicit_separate_roles(self):
        small = {'new-code': {'fixture': 'new'}}; expanded = {'inherited-code': {'fixture': 'inherited'}}
        with patch.object(c.engine, 'runtime_inputs', return_value=small), \
             patch.object(c, 'adapter_inputs', return_value=expanded), \
             patch.object(c.engine, 'base_config', return_value={'runtime_repository_files': small}), \
             patch.object(c, 'previous_history', return_value={'0189': 'fixture'}):
            self.assertEqual(c.runtime_inputs(), small | expanded)
            config = c.base_config('runtime')
            self.assertEqual(config['runtime_repository_files'], small)
            self.assertEqual(config['inherited_runtime_files'], expanded)

    def test_prepare_and_validate_use_new_namespace_and_both_added_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = root / 'inputs.json'
            inputs.write_text(json.dumps({'selection': {'host fixture': True}}))
            build = {'inputs': c.engine.base.record(inputs), 'apks': {'same': 'APK'}, 'metadata': {'same': 'metadata'}}
            (root / 'result.json').write_text(json.dumps(build))
            original_fields = {'runtime_repository_files': {'new-code': 'fixture'}}
            with patch.object(c.engine.base, 'BUILD', root), patch.object(c, 'select_inputs'), \
                 patch.object(c.engine, 'base_config', return_value=original_fields.copy()), \
                 patch.object(c, 'adapter_inputs', return_value={'inherited': 'fixture'}), \
                 patch.object(c, 'previous_history', return_value={'0189': 'fixture'}), \
                 patch.object(c, 'fresh_namespace') as fresh, \
                 patch.object(r.implementation, 'checked_build', return_value=(build, {'same': 'service'})), \
                 patch.object(r.implementation, 'sdk_inputs', return_value=['same SDK']):
                config = r.prepare()
                self.assertEqual(config['previous_harness_runtime'], {'0189': 'fixture'})
                self.assertEqual(config['inherited_runtime_files'], {'inherited': 'fixture'})
                self.assertEqual([call.args[0] for call in fresh.call_args_list], [c.RUNTIME, c.RUNTIME_WORK])
                with patch.object(c.engine, 'load_config', return_value=config):
                    self.assertEqual(r.validate(inputs, 'host-config-hash'), config)
                    with patch.object(c, 'previous_history', return_value={'0189': 'changed'}), self.assertRaisesRegex(ValueError, '0189 runtime history changed'):
                        r.validate(inputs, 'host-config-hash')
                    with patch.object(c, 'adapter_inputs', return_value={'inherited': 'changed'}), self.assertRaisesRegex(ValueError, 'inherited runtime inputs changed'):
                        r.validate(inputs, 'host-config-hash')

    def test_final0189_or_inherited_drift_sets_failure_before_frozen_finish(self):
        config = {'previous_harness_runtime': {'0189': 'original'}, 'inherited_runtime_files': {'inherited': 'original'}}
        for changed in ['history', 'inherited']:
            state = {'status': 'PASS', 'inputs': {'sha256': 'a'*64}}
            with patch.object(c.engine.base, 'checked', return_value=Path('/host-fixture/config')), \
                 patch.object(c.engine, 'load_config', return_value=config), \
                 patch.object(c, 'previous_history', return_value={'0189': 'changed' if changed == 'history' else 'original'}), \
                 patch.object(c, 'adapter_inputs', return_value={'inherited': 'changed' if changed == 'inherited' else 'original'}), \
                 patch.object(c.engine, 'finish') as original:
                c.finish(state, Path('/host-fixture/evidence'))
                self.assertEqual(state['status'], 'FAIL')
                self.assertIn('changed', state['recovery_input_error'])
                original.assert_called_once_with(state, Path('/host-fixture/evidence'))


if __name__ == '__main__':
    unittest.main()
