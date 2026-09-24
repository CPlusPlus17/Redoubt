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
        self.stage = self.work / 'evidence' / 'host-stage'; self.stage.mkdir(parents=True)
        manifest = self.stage / 'source-sha256.txt'
        manifest.write_text(n.c.digest(self.body) + '  source-file\n')
        stage = self.stage / 'receipt.json'
        self.plan = {'final_union_count': 1, 'outputs': {
            'proposed-source-sha256.txt': {'sha256': n.c.digest(manifest)},
            'expected-current167-source-sha256.txt': {'sha256': 'b' * 64}}}
        self.after = [{'path': 'source-file', 'expected_sha256': n.c.digest(self.body),
                       'observed': n.c.digest(self.body)}]
        self.stage_config = {'schema': 1, 'kind': n.STAGE_KIND, 'service_name': n.STAGE_SERVICE,
                             'source_dir': str(self.source), 'evidence_dir': str(self.stage),
                             'source_count': 1, 'before_manifest_sha256': 'b' * 64,
                             'final_manifest_sha256': n.c.digest(manifest)}
        self.stage_state = {'schema': 1, 'kind': n.STAGE_KIND, 'status': 'PASS',
                            'source_dir': str(self.source), 'source_count': 1,
                            'source_manifest': n.c.record(manifest),
                            'service': {'InvocationID': 'c' * 32, 'RemainAfterExit': 'yes',
                                        'ActiveState': 'active', 'SubState': 'running'},
                            'started': '2026-01-01T00:00:00+00:00', 'finished': '2026-01-01T00:01:00+00:00'}
        seed = self.work / 'seed'; seed.mkdir()
        self.inputs = {
            'schema': 1, 'run_id': 'native5-host-fixture',
            'service_name': 'redoubt-native5-host-fixture.service',
            'reviewed_scope_note': 'Explicit host parser fixture; no target source',
            'container_image_id': 'sha256:' + 'a' * 64, 'build_date': '20260906190000',
            'work': str(self.work), 'source_dir': str(self.source),
            'repository_files': {name: n.c.digest(n.REPO / name) for name in n.DEPENDENCIES},
            'source_manifest': {**n.c.record(manifest), 'count': 1},
            'source_staging_receipt': {}, 'gradle_home_seed': str(seed),
        }
        self.path = self.work / 'inputs.json'; self.save_stage()

    def save_stage(self):
        for name, value in [('source-plan-receipt.json', self.plan), ('source-after.json', self.after)]:
            (self.stage / name).write_text(json.dumps(value))
        self.stage_config['source_plan_receipt_sha256'] = n.c.digest(self.stage / 'source-plan-receipt.json')
        (self.stage / 'inputs.json').write_text(json.dumps(self.stage_config))
        self.stage_state.update(inputs=n.c.record(self.stage / 'inputs.json'),
                                source_after=n.c.record(self.stage / 'source-after.json'),
                                source_plan_receipt=n.c.record(self.stage / 'source-plan-receipt.json'))
        (self.stage / 'receipt.json').write_text(json.dumps(self.stage_state))
        self.inputs['source_staging_receipt'] = n.c.record(self.stage / 'receipt.json')
        self.save()

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

    def test_failed_or_unfinished_stage_rejected_even_when_every_source_matches(self):
        for status in ['PREPARING', 'APPLYING', 'FAIL', None]:
            with self.subTest(status=status):
                self.stage_state['status'] = status; self.save_stage()
                with self.assertRaisesRegex(ValueError, 'staging did not finish successfully'):
                    n.load(self.path)
                self.assertFalse((self.work / self.inputs['run_id']).exists())

    def test_stage_source_config_and_plan_must_match_reviewed_manifest(self):
        controls = [(self.stage_state, 'source_dir', str(self.work), 'source selection'),
                    (self.stage_state, 'source_count', 2, 'source selection'),
                    (self.stage_config, 'final_manifest_sha256', 'a' * 64, 'config/source linkage'),
                    (self.stage_config, 'evidence_dir', str(self.work), 'config/source linkage'),
                    (self.stage_config, 'service_name', 'unrelated.service', 'config/source linkage'),
                    (self.plan, 'final_union_count', 2, 'reviewed source plan')]
        for target, key, changed, message in controls:
            old = target[key]
            with self.subTest(key=key):
                target[key] = changed; self.save_stage()
                with self.assertRaisesRegex(ValueError, message):
                    n.load(self.path)
            target[key] = old
        self.save_stage()

    def test_stage_completion_requires_all_source_checks_and_real_linked_record_sizes(self):
        old = self.after[:]
        for rows in [[], old + old, [{**old[0], 'observed': 'a' * 64}]]:
            self.after = rows; self.save_stage()
            with self.assertRaisesRegex(ValueError, 'source verification incomplete'):
                n.load(self.path)
        self.after = old; self.save_stage()
        self.stage_state['source_manifest']['bytes'] += 1; self.save_stage()
        with self.assertRaisesRegex(ValueError, 'record path/size differs'):
            n.load(self.path)

    def test_stage_completion_time_must_be_ordered_aware_and_not_future(self):
        for started, ended in [('2026-01-01T00:00:00', '2026-01-01T00:01:00'),
                               ('2026-01-01T00:02:00+00:00', '2026-01-01T00:01:00+00:00'),
                               ('2099-01-01T00:00:00+00:00', '2099-01-01T00:01:00+00:00')]:
            self.stage_state.update(started=started, finished=ended); self.save_stage()
            with self.assertRaisesRegex(ValueError, 'completion time invalid'):
                n.load(self.path)

    def terminal(self, **changes):
        return dict(InvocationID='c' * 32, RemainAfterExit='yes', ActiveState='active',
                    SubState='exited', Result='success', ExecMainStatus='0') | changes

    def test_stage_terminal_requires_same_successful_retained_invocation(self):
        for observed in [self.terminal(), self.terminal(ActiveState='inactive', SubState='dead')]:
            with patch.object(n.c, 'query', return_value='\n'.join(k+'='+v for k,v in observed.items())) as query:
                self.assertEqual(n.terminal_stage(n.STAGE_SERVICE, 'c' * 32), observed)
                self.assertEqual(query.call_args.args[0][3], n.STAGE_SERVICE)
        for change in [{'InvocationID': 'd' * 32}, {'InvocationID': ''}, {'RemainAfterExit': 'no'},
                       {'SubState': 'running'}, {'Result': 'exit-code'}, {'ExecMainStatus': '1'},
                       {'ActiveState': 'failed', 'SubState': 'failed'}]:
            with self.subTest(change=change), patch.object(n.c, 'query', return_value='\n'.join(
                    k+'='+v for k,v in self.terminal(**change).items())):
                with self.assertRaisesRegex(ValueError, 'not successfully terminal'):
                    n.terminal_stage(n.STAGE_SERVICE, 'c' * 32)

    def test_failed_terminal_stage_blocks_native_output_even_with_valid_pass_receipt(self):
        context = n.load(self.path)
        def query(command):
            if command == ['id', '-un']: return 'runner'
            if command == ['systemd-detect-virt', '--vm']: return 'kvm'
            if command[:3] == ['podman', '--remote=false', 'ps']: return ''
            if command[:3] == ['podman', '--remote=false', 'image']: return 'a' * 64
            if command[:3] == ['systemctl', '--user', 'show']:
                if command[3] == n.STAGE_SERVICE:
                    return '\n'.join(k+'='+v for k,v in self.terminal(ExecMainStatus='1').items())
                return 'InvocationID='+'e'*32+'\nRemainAfterExit=yes'
            raise AssertionError(command)
        def run(command, **kwargs):
            if command[0] == 'pgrep': return type('P', (), {'returncode': 1})()
            raise AssertionError('native command reached: '+repr(command))
        with patch.object(n.os, 'getuid', return_value=1001), patch.object(n.c, 'query', side_effect=query), \
             patch.object(n.subprocess, 'run', side_effect=run), patch.dict(n.os.environ, INVOCATION_ID='e'*32):
            with self.assertRaisesRegex(ValueError, 'not successfully terminal'):
                n.run(self.path, context)
        self.assertFalse(context[2].exists())


if __name__ == '__main__':
    unittest.main()
