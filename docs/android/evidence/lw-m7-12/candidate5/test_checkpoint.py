"""Host failure controls for a future checkpoint; never claims target execution."""
from pathlib import Path
from types import SimpleNamespace
import copy
import datetime as dt
import importlib.util
import io
from contextlib import redirect_stdout
import json
import os
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('candidate_checkpoint', HERE / 'checkpoint.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
g = c.grade
INVENTORY = json.loads((HERE / 'unit-inventory.json').read_text())


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def file(self, name, text='host fixture'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return c.record(path)

    def native(self):
        source = self.root / 'source'; source.mkdir()
        source_file = source / 'test-source'; source_file.write_text('host fixture')
        rows = {'test-source': c.digest(source_file)}
        manifest = self.file('source.sha256', rows['test-source'] + '  test-source\n')
        reviewed = {**manifest, 'count': 1}
        return ({'schema': 1, 'status': 'PASS', 'invocation_id': 'a' * 32,
                 'service_name': 'host-fixture.service', 'source_dir': str(source),
                 'source_manifest': manifest, 'build_exit': self.file('exit', '0\n'),
                 'started': self.file('started', '2026-01-01T00:00:00+00:00'),
                 'finished': self.file('finished', '2026-01-01T00:01:00+00:00'),
                 'build_log': self.file('build.log'),
                 'source_before': self.file('before', 'test-source: OK\n'),
                 'source_after': self.file('after', 'test-source: OK\n'),
                 'aars': {abi: self.file('aar/' + abi + '/target.maven.zip') for abi in c.ABIS}},
                reviewed, rows, source)

    def test_native_receipt_matches_explicit_source_and_three_abis(self):
        native, reviewed, rows, source = self.native()
        self.assertEqual(c.check_native_receipt(native, reviewed, rows, source), self.root / 'aar')

    def test_native_failure_cannot_pass(self):
        native, reviewed, rows, source = self.native()
        native['build_exit'] = self.file('exit', '1\n')
        with self.assertRaisesRegex(ValueError, 'compiler exit'):
            c.check_native_receipt(native, reviewed, rows, source)

    def test_old_native_manifest_cannot_pass_new_review(self):
        native, reviewed, rows, source = self.native()
        reviewed['sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'different reviewed source'):
            c.check_native_receipt(native, reviewed, rows, source)

    def test_missing_abi_and_incomplete_before_after_checks_rejected(self):
        native, reviewed, rows, source = self.native()
        original = copy.deepcopy(native)
        del native['aars']['arm64-v8a']
        with self.assertRaisesRegex(ValueError, 'all three'):
            c.check_native_receipt(native, reviewed, rows, source)
        original['source_after'] = self.file('after', '')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            c.check_native_receipt(original, reviewed, rows, source)

    def test_future_or_reversed_native_times_rejected(self):
        native, reviewed, rows, source = self.native()
        for stamp in ['2099-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00']:
            native['finished'] = self.file('finished', stamp)
            with self.assertRaisesRegex(ValueError, 'completion time'):
                c.check_native_receipt(native, reviewed, rows, source)

    def test_manifest_scope_is_explicit_not_a_fixed_count(self):
        for count in [1, 2]:
            p = self.root / 'manifest'
            p.write_text(''.join('a' * 64 + '  file' + str(i) + '\n' for i in range(count)))
            self.assertEqual(len(c.source_manifest(p, count)), count)
            with self.assertRaisesRegex(ValueError, 'source count'):
                c.source_manifest(p, count + 1)

    def test_invalid_or_duplicate_manifest_paths_rejected(self):
        for names in [['same', 'same'], ['../escape'], ['/absolute'], ['a//b'], ['a\\b']]:
            p = self.root / 'manifest'
            p.write_text(''.join('a' * 64 + '  ' + name + '\n' for name in names))
            with self.assertRaises(ValueError):
                c.source_manifest(p, len(names))

    def test_changed_source_and_artifact_rejected(self):
        data = self.file('input'); Path(data['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'input hash differs'):
            c.checked_file(data)
        with self.assertRaisesRegex(ValueError, 'source differs'):
            c.verify_sources(self.root, {'input': 'a' * 64})

    def test_missing_native_artifact_is_pending(self):
        with self.assertRaises(c.Pending):
            c.checked_file({'path': str(self.root / 'absent'), 'sha256': 'a' * 64})

    def test_exact_four_apk_set_required(self):
        folder = self.root / 'apk'; folder.mkdir()
        with self.assertRaises(ValueError):
            c.assert_apk_set(folder)
        for name in c.APKS:
            (folder / name).write_bytes(b'host fixture')
        self.assertEqual(set(c.assert_apk_set(folder)), c.APKS)
        (folder / 'old-debug.apk').write_bytes(b'host fixture')
        with self.assertRaises(ValueError):
            c.assert_apk_set(folder)

    def test_prior_classes_preserved_and_all_additions_selected(self):
        suites = g.suites(INVENTORY)
        for key, (_, minimum_classes, minimum_tests, required) in g.prior.SUITES.items():
            self.assertLessEqual(required, suites[key]['required'])
            self.assertGreaterEqual(suites[key]['minimum_classes'], minimum_classes)
            self.assertGreaterEqual(suites[key]['minimum_tests'], minimum_tests)
        full, targeted = c.gradle_tasks(INVENTORY)
        self.assertIn(':fenix:testDebugUnitTest', full)
        self.assertIn(':components:support-webextensions:testDebugUnitTest', full)
        self.assertNotIn('--tests', full)
        self.assertIn('--no-build-cache', full)
        self.assertIn('--no-build-cache', targeted)
        for row in INVENTORY['tests']:
            if row['suite'] != 'fenix': self.assertIn(row['class'], targeted)
        self.assertIn('mozilla.components.feature.addons.AddonManagerTest', targeted)

    def test_native_only_cases_are_explicit_separate_gates(self):
        self.assertIn('LW-M7-31', INVENTORY['separate_required_gates'])
        self.assertFalse(any(row['task'] == 'LW-M7-31' for row in INVENTORY['tests']))
        self.assertEqual(sum(len(row['required_methods']) for row in INVENTORY['tests']), 41)

    def test_compiler_failure_cannot_borrow_fenix_allowance(self):
        allowed = '> Task :fenix:testDebugUnitTest FAILED\n'
        self.assertTrue(c.full_exit_is_accounted(1, allowed))
        self.assertFalse(c.full_exit_is_accounted(1, allowed + '> Task :fenix:compileDebugUnitTestKotlin FAILED\n'))
        self.assertFalse(c.full_exit_is_accounted(1, 'no tasks ran'))
        self.assertFalse(c.full_exit_is_accounted(137, allowed))

    def guard_with_image(self, observed):
        image = 'sha256:' + 'b' * 64
        native = {'service_name': 'host-native.service', 'invocation_id': 'a' * 32}
        status = '\n'.join(['InvocationID=' + native['invocation_id'], 'ExecMainStatus=0',
                            'Result=success', 'ActiveState=active', 'SubState=exited'])
        with patch.dict(c.os.environ), \
             patch.object(c.os, 'getuid', return_value=1001), \
             patch.object(c.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='runner')), \
             patch.object(c, 'query', side_effect=['kvm', '', observed, status]) as query, \
             patch.object(c.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            result = c.guard_guest({'inputs': {'container_image_id': image}, 'native': native})
        self.assertEqual(query.call_args_list[2].args[0],
                         ['podman', '--remote=false', 'image', 'inspect', '--format', '{{.Id}}', image])
        self.assertEqual(result['InvocationID'], native['invocation_id'])

    def test_guest_guard_accepts_same_bare_digest(self):
        self.guard_with_image('b' * 64)

    def test_guest_guard_accepts_same_prefixed_digest(self):
        self.guard_with_image('sha256:' + 'b' * 64)

    def test_guest_guard_rejects_wrong_image_in_either_form(self):
        for value in ['c' * 64, 'sha256:' + 'c' * 64]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'image ID differs'):
                self.guard_with_image(value)

    def test_guest_guard_rejects_malformed_digest_before_comparison(self):
        for value in ['', 'b' * 63, 'b' * 65, 'g' * 64, 'sha256:sha256:' + 'b' * 64,
                      'sha512:' + 'b' * 64, 'prefix' + 'b' * 64, 'b' * 64 + '\nextra']:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'image ID is malformed'):
                self.guard_with_image(value)

    def test_plan_does_not_execute_or_create_workspace(self):
        run_root = self.root / 'candidate5-unused'
        context = {'root': run_root, 'out': run_root / 'out', 'source': self.root / 'source',
                   'aar': self.root / 'aar', 'seed': self.root / 'seed', 'inventory': INVENTORY,
                   'rows': {'fixture': 'a' * 64},
                   'inputs': {'run_id': 'candidate5-unused', 'build_date': '20260906190000',
                              'container_image_id': 'sha256:' + 'b' * 64}}
        output = io.StringIO()
        with patch.object(c, 'load_inputs', return_value=context), \
             patch.object(c, 'execute', side_effect=AssertionError('plan executed target')) as execute, \
             patch.object(c.sys, 'argv', ['checkpoint.py', '--inputs', '/host-fixture-inputs']), \
             redirect_stdout(output):
            self.assertEqual(c.main(), 0)
        execute.assert_not_called()
        self.assertFalse(run_root.exists())
        self.assertEqual(json.loads(output.getvalue())['status'], 'PLAN ONLY; target not executed')

    def test_failed_apk_build_stops_before_unit_or_resource_commands(self):
        inputs = self.file('inputs.json', '{}')
        native = self.file('native.json', '{}')
        manifest = self.file('manifest', 'host fixture')
        context = {'input_sha256': inputs['sha256'], 'root': self.root / 'new-run', 'evidence': self.root / 'new-run/evidence',
                   'inputs': {'native_receipt': native, 'reviewed_scope_note': 'host test only'},
                   'manifest': Path(manifest['path']), 'inventory': INVENTORY}
        with patch.object(c, 'guard_guest', return_value={'host': 'fixture'}), \
             patch.object(c, 'apk_command', return_value=['host-fake-build']), \
             patch.object(c.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as run:
            with self.assertRaisesRegex(ValueError, 'APK build failed'):
                c.execute(context, Path(inputs['path']))
        self.assertEqual(run.call_count, 1)
        result = json.loads((context['evidence'] / 'result.json').read_text())
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(set(result['stages']), {'apk-build'})


class XmlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.suite = {'required': {'fixture.Class'}, 'minimum_classes': 1, 'minimum_tests': 1,
                      'methods': {'fixture.Class': ['critical method']}}
        self.start = time.time() - 10

    def xml(self, names=('critical method',), skipped=False):
        root = ET.Element('testsuite', name='fixture.Class', tests=str(len(names)), failures='0', errors='0',
                          skipped=str(len(names) if skipped else 0))
        for name in names:
            case = ET.SubElement(root, 'testcase', name=name, classname='fixture.Class')
            if skipped: ET.SubElement(case, 'skipped')
        p = self.root / 'TEST-fixture.Class.xml'; ET.ElementTree(root).write(p)
        return p

    def inspect(self):
        return g.inspect(self.root, self.start, time.time() + 1, self.suite, False)['issues']

    def test_actual_required_method_passes(self):
        self.xml(); self.assertEqual(self.inspect(), [])

    def test_missing_method_cannot_borrow_another_pass(self):
        self.xml(['unrelated passing method'])
        self.assertTrue(any('required method missing' in x for x in self.inspect()))

    def test_required_method_cannot_hide_truncated_existing_class(self):
        self.xml()
        self.suite['class_counts'] = {'fixture.Class': 3}
        self.assertTrue(any('truncated class test count' in x for x in self.inspect()))

    def test_skipped_required_method_fails(self):
        self.xml(skipped=True)
        self.assertTrue(any('did not fully pass' in x for x in self.inspect()))

    def test_stale_xml_rejected(self):
        p = self.xml(); os.utime(p, (self.start - 1, self.start - 1))
        self.assertTrue(any('stale XML' in x for x in self.inspect()))

    def test_duplicate_case_rejected(self):
        self.xml(['critical method', 'critical method'])
        self.assertTrue(any('duplicate testcase' in x for x in self.inspect()))

    def test_empty_results_rejected(self):
        self.assertTrue(any('Missing or truncated' in x for x in self.inspect()))


if __name__ == '__main__':
    unittest.main()
