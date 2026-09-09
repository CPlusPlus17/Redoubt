#!/usr/bin/env python3
"""Local checkpoint input/result tests; no container, guest or Android execution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import common as c
import runtime


class CheckpointContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='current167-recovery-contracts-')
        self.root = Path(self.temp.name)
        self.apk = {'path': '/explicit/new/fenix-x86_64-release.apk', 'sha256': 'a' * 64, 'bytes': 123}
        self.resource = {'apk_sha256': 'a' * 64, 'apk_size': 123, 'aapt2_sha256': c.AAPT_SHA,
                         'package': 'org.redoubtbrowser', 'resource': 'raw/initial_shortcuts',
                         'mappings': [{'member': 'res/raw/a.json'}]}

    def tearDown(self):
        self.temp.cleanup()

    def resource_log(self, row=None):
        return 'PASS exact packaged shortcut input resolved through APK resource table\n' + json.dumps(row or self.resource)

    def report(self, names):
        return {'status': 'completed', 'error': None, 'tainted': False, 'injected_prefs': {},
                'artifact': {'path': self.apk['path'], 'sha256': self.apk['sha256'], 'size': self.apk['bytes'],
                             'harness_sha256': c.digest(c.REPO / 'scripts/android-smoke.sh')},
                'checks': [{'check': name, 'ok': True} for name in sorted(names)]}

    def grade(self, report, required=runtime.UBO):
        path = self.root / 'report.json'
        path.write_text(json.dumps(report))
        return runtime.grade_smoke(path, required, self.apk)

    def test_explicit_successful_resource_verdict(self):
        self.assertEqual(c.resource_receipt(self.resource_log(), self.apk), self.resource)

    def test_nonempty_failed_resource_log_rejected(self):
        with self.assertRaises(ValueError):
            c.resource_receipt('FAIL shortcut resource verification: missing resource\n', self.apk)

    def test_json_without_actual_pass_verdict_rejected(self):
        with self.assertRaises(ValueError):
            c.resource_receipt(json.dumps(self.resource), self.apk)

    def test_other_apk_resource_receipt_rejected(self):
        row = dict(self.resource, apk_sha256='b' * 64)
        with self.assertRaises(ValueError):
            c.resource_receipt(self.resource_log(row), self.apk)

    def test_other_tool_resource_receipt_rejected(self):
        row = dict(self.resource, aapt2_sha256='b' * 64)
        with self.assertRaises(ValueError):
            c.resource_receipt(self.resource_log(row), self.apk)

    def test_missing_resource_mapping_rejected(self):
        row = dict(self.resource, mappings=[])
        with self.assertRaises(ValueError):
            c.resource_receipt(self.resource_log(row), self.apk)

    def test_complete_lifecycle_report(self):
        self.grade(self.report(runtime.UBO))

    def test_shortened_lifecycle_cannot_pass(self):
        with self.assertRaises(ValueError):
            self.grade(self.report({'ubo-first-navigation', 'ubo-preinstalled-signature'}))

    def test_failed_lifecycle_check_cannot_pass(self):
        report = self.report(runtime.UBO)
        report['checks'][0]['ok'] = False
        with self.assertRaises(ValueError):
            self.grade(report)

    def test_duplicate_check_cannot_pass(self):
        report = self.report(runtime.UBO)
        report['checks'].append(report['checks'][0])
        with self.assertRaises(ValueError):
            self.grade(report)

    def test_running_report_cannot_pass(self):
        report = self.report(runtime.UBO)
        report['status'] = 'running'
        with self.assertRaises(ValueError):
            self.grade(report)

    def test_injected_configuration_cannot_pass(self):
        report = self.report(runtime.UBO)
        report['injected_prefs'] = {'network.offline': True}
        with self.assertRaises(ValueError):
            self.grade(report)

    def test_stale_apk_report_cannot_pass(self):
        report = self.report(runtime.UBO)
        report['artifact']['sha256'] = 'b' * 64
        with self.assertRaises(ValueError):
            self.grade(report)

    def test_old_harness_report_cannot_pass(self):
        report = self.report(runtime.UBO)
        report['artifact']['harness_sha256'] = 'b' * 64
        with self.assertRaises(ValueError):
            self.grade(report)

    def test_baseline_requires_https_and_graphics(self):
        self.grade(self.report(runtime.BASELINE), runtime.BASELINE)
        with self.assertRaises(ValueError):
            self.grade(self.report(runtime.BASELINE - {'https-only-interstitial', 'webgl'}), runtime.BASELINE)

    def test_all_four_apks_required(self):
        for name in c.APKS:
            (self.root / name).write_bytes(b'synthetic artifact for inventory only')
        self.assertEqual(set(c.apk_set(self.root)), c.APKS)
        (self.root / 'fenix-universal-release.apk').unlink()
        with self.assertRaises(ValueError):
            c.apk_set(self.root)

    def test_extra_apk_rejected(self):
        for name in c.APKS | {'old.apk'}:
            (self.root / name).write_bytes(b'synthetic artifact for inventory only')
        with self.assertRaises(ValueError):
            c.apk_set(self.root)

    def test_duplicate_and_traversal_source_rows_rejected(self):
        path = self.root / 'source.txt'
        for content in ('a' * 64 + '  ../escape\n', ('a' * 64 + '  name\n') * 2):
            path.write_text(content)
            with self.assertRaises(ValueError):
                c.manifest(path)

    def test_changed_recorded_input_rejected(self):
        path = self.root / 'pinned'
        path.write_bytes(b'original')
        row = c.record(path)
        path.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            c.checked(row)

    def recorded_driver_fixture(self, runner='run-fenix-account-process-tests.sh'):
        repo = self.root / 'repo'
        evidence = self.root / 'evidence'
        evidence.mkdir()
        names = ['docs/android/board.py', 'docs/android/fenix-test-allowlist.yaml',
                 'docs/android/evidence/lw-m7-12/grade-extended-tests.py',
                 'docs/android/evidence/lw-m7-12/' + runner]
        for name in names:
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic recorded input: ' + name)
        (evidence / 'driver-sha256.txt').write_text(''.join(c.digest(repo / n) + '  ' + n + '\n' for n in names))
        return repo, evidence, names

    def test_selected_account_process_driver_matches_actual_recorded_bytes(self):
        repo, evidence, names = self.recorded_driver_fixture()
        with patch.object(c, 'REPO', repo), patch.object(c, 'TESTS', evidence):
            self.assertEqual(set(c.recorded_test_driver_check()), set(names))

    def test_changed_selected_test_driver_rejected(self):
        repo, evidence, names = self.recorded_driver_fixture()
        (repo / names[-1]).write_text('changed after the completed test run')
        with patch.object(c, 'REPO', repo), patch.object(c, 'TESTS', evidence):
            with self.assertRaises(ValueError):
                c.recorded_test_driver_check()

    def test_incomplete_recorded_driver_inventory_rejected(self):
        repo, evidence, _names = self.recorded_driver_fixture()
        path = evidence / 'driver-sha256.txt'
        path.write_text('\n'.join(path.read_text().splitlines()[:-1]) + '\n')
        with patch.object(c, 'REPO', repo), patch.object(c, 'TESTS', evidence):
            with self.assertRaises(ValueError):
                c.recorded_test_driver_check()

    def test_failed_or_running_service_never_terminal_success(self):
        state = {'InvocationID': 'a' * 32, 'RemainAfterExit': 'yes', 'ActiveState': 'active',
                 'SubState': 'exited', 'Result': 'success', 'ExecMainStatus': '0'}
        def reply():
            return '\n'.join(k + '=' + v for k, v in state.items())
        with patch.object(c, 'query', side_effect=lambda _cmd: reply()):
            c.service('synthetic.service', 'a' * 32, terminal=True)
            for key, bad in (('ExecMainStatus', '1'), ('SubState', 'running'), ('InvocationID', 'b' * 32)):
                previous = state[key]
                state[key] = bad
                with self.assertRaises(ValueError):
                    c.service('synthetic.service', 'a' * 32, terminal=True)
                state[key] = previous

    def test_native_reuse_and_new_output_are_explicit(self):
        command = c.build_command()
        self.assertIn('--skip-gecko', command)
        self.assertEqual(command[command.index('--outdir') + 1], str(c.WORK / 'account-process-apk-output'))
        self.assertEqual(command[command.index('--aar-dir') + 1], str(c.WORK / 'aar'))
        self.assertEqual(command[command.index('--image') + 1], c.IMAGE)
        self.assertEqual(command[command.index('--build-date') + 1], '20260906190000')
        self.assertNotIn('--disable-debug-signing', command)

    def test_recovery_namespaces_do_not_reuse_old_outputs_or_services(self):
        self.assertEqual(c.OUTPUT, c.WORK / 'account-process-apk-output')
        self.assertEqual(c.RUNTIME_WORK, c.WORK / 'account-process-runtime')
        self.assertEqual(c.BUILD, c.WORK / 'evidence/account-process-apk')
        self.assertEqual(c.RUNTIME, c.WORK / 'evidence/account-process-runtime')
        self.assertEqual(c.SERVICES['apk'], 'redoubt-account-process-apk-20260909.service')
        self.assertEqual(c.SERVICES['runtime'], 'redoubt-account-process-runtime-20260909.service')
        self.assertTrue(all('/current167-process-recovery/' in name for name in c.DEPENDENCIES[:4]))

    def test_recovery_rejects_the_known_failed_source_even_with_reviewed_fields(self):
        selection = {'source_stage': str(c.WORK / 'evidence/account-process-source'),
                     'test_evidence': str(c.WORK / 'evidence/account-process-tests'),
                     'native_manifest': str(c.WORK / 'evidence/fenix-regression-source/native-input-sha256.txt'),
                     'source_manifest_sha256': c.PRIOR_SOURCE,
                     'test_service_name': 'redoubt-fenix-account-process-tests-20260909.service',
                     'test_invocation': 'c' * 32}
        with self.assertRaisesRegex(ValueError, 'corrected source'):
            c.select_inputs(selection)

    def test_existing_or_broken_link_output_is_not_fresh(self):
        output = self.root / 'output'
        c.fresh_namespace(output)
        output.symlink_to(self.root / 'missing')
        with self.assertRaises(ValueError):
            c.fresh_namespace(output)
        output.unlink()
        output.mkdir()
        with self.assertRaises(ValueError):
            c.fresh_namespace(output)

    def test_prior_inventory_detects_added_deleted_and_changed_files(self):
        path = self.root / 'history'
        path.mkdir()
        (path / 'log').write_text('original')
        original = c.preserved_tree(path)
        (path / 'new').write_text('added')
        self.assertNotEqual(c.preserved_tree(path), original)
        (path / 'new').unlink()
        (path / 'log').write_text('changed')
        self.assertNotEqual(c.preserved_tree(path), original)
        (path / 'log').unlink()
        with self.assertRaisesRegex(ValueError, 'empty prior'):
            c.preserved_tree(path)

    def test_prior_inventory_rejects_linked_files_and_directories(self):
        path = self.root / 'history'
        path.mkdir()
        (path / 'real').write_text('original')
        linked = path / 'link'
        for target in (path / 'real', self.root):
            linked.symlink_to(target)
            with self.assertRaisesRegex(ValueError, 'linked prior evidence'):
                c.preserved_tree(path)
            linked.unlink()

    def runtime_service_properties(self, **updates):
        result = {'LoadState': 'not-found', 'ActiveState': 'inactive', 'SubState': 'dead',
                  'InvocationID': '', 'RemainAfterExit': 'no', 'Result': 'success', 'ExecMainStatus': '0'}
        result.update(updates)
        return result

    def inspect_prior(self, properties):
        # Only the live systemd inspection is substituted. The real retained
        # archive, member, failed receipt and source pins are parsed each time.
        with patch.object(c, 'service', return_value={'synthetic_apk': 'terminal'}) as service, \
             patch.object(c, 'query', return_value='\n'.join(k + '=' + v for k, v in properties.items())):
            result = c.prior_services()
        service.assert_called_once_with('redoubt-fenix-regression-apk-20260909.service',
                                        c.PRIOR_INVOCATIONS['apk'], terminal=True)
        return result

    def test_collected_prior_runtime_uses_actual_archived_terminal_failure(self):
        result = self.inspect_prior(self.runtime_service_properties())['runtime']
        self.assertEqual(result['current_unit']['InvocationID'], '')
        self.assertEqual(result['history']['archive']['sha256'], c.PRIOR_RUNTIME_ARCHIVE_SHA)
        self.assertEqual(result['history']['terminal']['InvocationID'], c.PRIOR_INVOCATIONS['runtime'])
        self.assertEqual(result['history']['terminal']['ExecMainStatus'], '2')
        self.assertEqual(result['history']['checkpoint_files']['source-sha256.txt']['sha256'], c.PRIOR_SOURCE)

    def test_matching_retained_terminal_failure_is_allowed(self):
        state = self.runtime_service_properties(LoadState='loaded', InvocationID=c.PRIOR_INVOCATIONS['runtime'],
                RemainAfterExit='yes', ActiveState='failed', SubState='failed', ExecMainStatus='2', Result='exit-code')
        self.assertEqual(self.inspect_prior(state)['runtime']['current_unit'], state)

    def test_running_or_conflicting_replacement_cannot_borrow_old_archive(self):
        terminal = self.runtime_service_properties(LoadState='loaded', InvocationID=c.PRIOR_INVOCATIONS['runtime'],
                RemainAfterExit='yes', ActiveState='active', SubState='exited', ExecMainStatus='2')
        invalid = [dict(terminal, SubState='running'), dict(terminal, InvocationID='f' * 32),
                   dict(terminal, ExecMainStatus='0'), self.runtime_service_properties(LoadState='loaded'),
                   self.runtime_service_properties(LoadState='error')]
        for state in invalid:
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'replacement'):
                self.inspect_prior(state)

    def test_incomplete_current_unit_inspection_is_rejected(self):
        properties = self.runtime_service_properties()
        del properties['LoadState']
        with self.assertRaisesRegex(ValueError, 'inspection incomplete'):
            self.inspect_prior(properties)

    def test_changed_historical_archive_is_rejected_before_member_read(self):
        path = self.root / c.PRIOR_RUNTIME_ARCHIVE
        path.parent.mkdir(parents=True)
        path.write_bytes((c.REPO / c.PRIOR_RUNTIME_ARCHIVE).read_bytes() + b'changed')
        with patch.object(c, 'REPO', self.root), self.assertRaisesRegex(ValueError, 'archive differs'):
            c.archived_runtime_history()

    def test_archived_terminal_service_requires_its_exact_member_pin(self):
        with patch.object(c, 'PRIOR_RUNTIME_SERVICE_SHA', 'a' * 64), self.assertRaisesRegex(ValueError, 'service record differs'):
            c.archived_runtime_history()

    def prior_fixture(self):
        """Small real files; only fixed guest locations/services are substituted."""
        from contextlib import ExitStack
        stack = ExitStack()
        self.addCleanup(stack.close)
        repo = self.root / 'repo'
        here = self.root / 'driver'
        here.mkdir()
        parent = json.loads((c.HERE / 'parent-inputs.json').read_text())
        for name in parent['original_driver_inputs']:
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((c.REPO / name).read_bytes())
        (here / 'parent-inputs.json').write_text(json.dumps(parent))
        stack.enter_context(patch.object(c, 'HERE', here))
        stack.enter_context(patch.object(c, 'REPO', repo))
        prior = {kind: self.root / kind for kind in ('apk', 'runtime')}
        for path in prior.values():
            path.mkdir()
            (path / 'source-sha256.txt').write_text('synthetic retained manifest\n')
        stack.enter_context(patch.object(c, 'PRIOR_SOURCE', c.digest(prior['apk'] / 'source-sha256.txt')))
        stack.enter_context(patch.object(c, 'PRIOR_EVIDENCE', prior))
        apks_path = self.root / 'prior-apks'
        apks_path.mkdir()
        for name in c.APKS:
            (apks_path / name).write_bytes(name.encode())
        stack.enter_context(patch.object(c, 'PRIOR_APKS', apks_path))
        code = {name: c.record(repo / name) for name in parent['original_driver_inputs']}
        for kind, path in prior.items():
            config = {'source_sha256': c.PRIOR_SOURCE, 'kind': kind, 'repository_files': code,
                      'apks': c.apk_set(apks_path)}
            (path / 'inputs.json').write_text(json.dumps(config))
            state = {'kind': kind, 'service': {'InvocationID': c.PRIOR_INVOCATIONS[kind]},
                     'source_manifest': c.record(path / 'source-sha256.txt'),
                     'inputs': c.record(path / 'inputs.json'),
                     'status': 'PASS' if kind == 'apk' else 'FAIL', 'apks': c.apk_set(apks_path)}
            (path / 'result.json').write_text(json.dumps(state))
        history = {'checkpoint_files': {name: {key: value for key, value in
                    c.record(prior['runtime'] / name).items() if key != 'path'}
                    for name in ('result.json', 'inputs.json', 'source-sha256.txt')}}
        stack.enter_context(patch.object(c, 'prior_services', return_value={'runtime': {'history': history}}))
        return repo, prior

    def test_prior_success_and_failed_runtime_bind_original_code_and_apks(self):
        _repo, prior = self.prior_fixture()
        expected = c.prior_checkpoint_inputs()
        c.check_prior_checkpoint(expected)
        (prior['runtime'] / 'new-late-log').write_text('changed history')
        with self.assertRaisesRegex(ValueError, 'historical checkpoint'):
            c.check_prior_checkpoint(expected)

    def test_prior_driver_mutation_is_rejected(self):
        repo, _prior = self.prior_fixture()
        path = repo / 'docs/android/evidence/lw-m7-12/current167/common.py'
        path.write_text('changed historical executable code')
        with self.assertRaisesRegex(ValueError, 'driver bytes changed'):
            c.prior_checkpoint_inputs()

    def test_current_failed_receipt_must_still_equal_archived_failure(self):
        _repo, prior = self.prior_fixture()
        path = prior['runtime'] / 'result.json'
        state = json.loads(path.read_text())
        state['extra_late_mutation'] = 'a new receipt cannot replace archived history'
        path.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'retained failure: result.json'):
            c.prior_checkpoint_inputs()

    def test_prior_config_cannot_claim_another_driver_or_artifact(self):
        _repo, prior = self.prior_fixture()
        path = prior['runtime'] / 'inputs.json'
        config = json.loads(path.read_text())
        config['repository_files']['docs/android/evidence/lw-m7-12/current167/common.py']['sha256'] = 'b' * 64
        path.write_text(json.dumps(config))
        result_path = prior['runtime'] / 'result.json'
        state = json.loads(result_path.read_text())
        state['inputs'] = c.record(path)
        result_path.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'config/code binding changed'):
            c.prior_checkpoint_inputs()

    def test_finish_preservation_failure_prevents_success(self):
        evidence = self.root / 'new-evidence'
        evidence.mkdir()
        path = evidence / 'inputs.json'
        path.write_text('{"prior_checkpoint":{}}')
        state = {'status': 'PASS', 'inputs': c.record(path)}
        with patch.object(c, 'source_check'), patch.object(c, 'native_check'), \
             patch.object(c, 'check_prior_checkpoint', side_effect=ValueError('old file changed')):
            c.finish(state, evidence)
        result = json.loads((evidence / 'result.json').read_text())
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('old file changed', result['final_input_error'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
