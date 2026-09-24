"""Host controls for the native build boundary; these do not run a target build."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_driver', HERE / 'native.py')
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)


class NativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.source = self.work / 'source'; self.source.mkdir()
        self.body = self.source / 'source-file'; self.body.write_text('explicit host fixture')
        manifest = self.work / 'source.sha256'
        manifest.write_text(n.c.digest(self.body) + '  source-file\n')
        stage = self.work / 'stage.json'; stage.write_text('{"scope":"host fixture only"}\n')
        seed = self.work / 'seed'; seed.mkdir()
        self.inputs = {
            'schema': 1, 'run_id': 'native5-host-fixture',
            'service_name': 'redoubt-native5-host-fixture.service',
            'reviewed_scope_note': 'Explicit host parser fixture; no target source',
            'container_image_id': 'sha256:' + 'a' * 64, 'build_date': '20260906190000',
            'work': str(self.work), 'source_dir': str(self.source),
            'repository_files': {name: n.c.digest(n.REPO / name) for name in n.DEPENDENCIES},
            'source_manifest': {**n.c.record(manifest), 'count': 1},
            'source_staging_receipt': n.c.record(stage), 'gradle_home_seed': str(seed),
        }
        self.path = self.work / 'inputs.json'; self.save()

    def save(self):
        self.path.write_text(json.dumps(self.inputs))

    def test_plan_cannot_invoke_a_build_or_create_output(self):
        with patch('sys.argv', ['native.py', '--inputs', str(self.path)]), \
             patch.object(n.subprocess, 'run', side_effect=AssertionError('plan executed command')), \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(n.main(), 0)
        plan = json.loads(output.getvalue())
        self.assertEqual(plan['status'], 'PLAN ONLY')
        self.assertFalse(Path(plan['output']).exists())
        self.assertNotIn('--skip-existing', plan['command'])
        self.assertEqual(plan['command'][-1], self.inputs['container_image_id'])

    def test_changed_source_fails_before_build_output(self):
        self.body.write_text('changed source')
        with self.assertRaisesRegex(ValueError, 'source differs'):
            n.load(self.path)
        self.assertFalse((self.work / self.inputs['run_id']).exists())

    def test_prior_output_is_never_reused(self):
        output = self.work / self.inputs['run_id']; output.mkdir()
        sentinel = output / 'prior'; sentinel.write_text('retain')
        with self.assertRaisesRegex(ValueError, 'output already exists'):
            n.load(self.path)
        self.assertEqual(sentinel.read_text(), 'retain')

    def test_changed_staging_receipt_is_rejected(self):
        Path(self.inputs['source_staging_receipt']['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'input hash differs'):
            n.load(self.path)

    def test_missing_dependency_and_wrong_service_are_rejected(self):
        del self.inputs['repository_files'][n.DEPENDENCIES[0]]; self.save()
        with self.assertRaisesRegex(ValueError, 'dependency inventory'):
            n.load(self.path)
        self.inputs['service_name'] = 'other.service'; self.save()
        with self.assertRaisesRegex(ValueError, 'service must match'):
            n.load(self.path)

    def test_host_execution_cannot_reach_output_creation(self):
        context = n.load(self.path)
        with patch.object(n.os, 'getuid', return_value=1000), \
             patch.object(n.subprocess, 'run', side_effect=AssertionError('host reached build')):
            with self.assertRaisesRegex(ValueError, 'requires guest runner'):
                n.run(self.path, context)
        self.assertFalse(context[2].exists())


if __name__ == '__main__':
    unittest.main()
