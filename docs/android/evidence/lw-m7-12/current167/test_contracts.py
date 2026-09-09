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
        self.temp = tempfile.TemporaryDirectory(prefix='current167-contracts-')
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
        self.assertEqual(command[command.index('--outdir') + 1], str(c.WORK / 'fenix-regression-apk-output'))
        self.assertEqual(command[command.index('--aar-dir') + 1], str(c.WORK / 'aar'))
        self.assertEqual(command[command.index('--image') + 1], c.IMAGE)
        self.assertEqual(command[command.index('--build-date') + 1], '20260906190000')
        self.assertNotIn('--disable-debug-signing', command)


if __name__ == '__main__':
    unittest.main(verbosity=2)
