#!/usr/bin/env python3
"""Host regressions for actual graphics evidence and exact Android controls."""
import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('graphics_smoke', ROOT / 'scripts/android-graphics-smoke.py')
g = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g)
COLORS = [[17, 51, 91, 255], [31, 81, 113, 255], [71, 127, 19, 255], [149, 23, 211, 255]]
ORIGIN = 'http://localhost:4245'


def result(**kwargs):
    data = {'commandId': 'command', 'documentId': 'document', 'origin': ORIGIN,
            'operation': 'canvas', 'mode': 'dom', 'context': True,
            'pixels': list(g.expected_pixels(COLORS))}
    data.update(kwargs)
    return data


def grade(value, **kwargs):
    options = {'operation': 'canvas', 'mode': 'dom', 'origin': ORIGIN, 'document_id': 'document',
               'command_id': 'command', 'colors': COLORS, 'context_allowed': True, 'readback_allowed': True}
    options.update(kwargs)
    return g.grade_probe(value, **options)


def ui(*nodes):
    import html
    parts = []
    for node in nodes:
        attributes = {'resource-id': 'org.redoubtbrowser:id/origin_permission_pending_webgl',
                      'package': 'org.redoubtbrowser', 'enabled': 'true', 'clickable': 'true',
                      'bounds': '[10,20][110,80]', 'text': 'WebGL — ' + ORIGIN + '\nReview request'}
        attributes.update(node)
        parts.append('<node ' + ' '.join(f'{key}="{html.escape(str(value), quote=True)}"'
                                         for key, value in attributes.items()) + '/>')
    return '<?xml version="1.0"?><hierarchy>' + ''.join(parts) + '</hierarchy>'


class PixelEvidenceTests(unittest.TestCase):
    def test_independent_quadrant_oracle(self):
        pixels = g.expected_pixels(COLORS)
        self.assertEqual(len(pixels), 4096)
        for x, y, index in [(0, 0, 0), (31, 0, 1), (0, 31, 2), (31, 31, 3)]:
            self.assertEqual(list(pixels[(y*32+x)*4:(y*32+x)*4+4]), COLORS[index])

    def test_real_pixels_are_required_after_consent(self):
        self.assertTrue(grade(result())['actualPixels'])
        changed = result(pixels=[0] * 4096)
        with self.assertRaisesRegex(g.Failure, 'did not restore'):
            grade(changed)

    def test_actual_pixels_before_consent_fail(self):
        with self.assertRaisesRegex(g.Failure, 'leaked'):
            grade(result(), readback_allowed=False)

    def test_protected_readback_is_real_complete_data(self):
        self.assertTrue(grade(result(pixels=[0]*4096), readback_allowed=False)['protected'])
        for pixels in [None, [], [0]*4, [0]*4095, [0]*4097]:
            with self.subTest(pixels_length=len(pixels) if pixels is not None else None):
                with self.assertRaises(g.Failure):
                    grade(result(pixels=pixels), readback_allowed=False)

    def test_invalid_byte_types_do_not_pass_as_protected(self):
        for invalid in [True, -1, 256, 1.2, '0', None]:
            pixels = [0]*4096
            pixels[50] = invalid
            with self.subTest(value=invalid), self.assertRaises(g.Failure):
                grade(result(pixels=pixels), readback_allowed=False)

    def test_every_identity_binding_is_enforced(self):
        for field, value in [('commandId', 'old'), ('documentId', 'stale'),
                             ('origin', 'http://localhost:42450'), ('operation', 'webgl'), ('mode', 'worker')]:
            with self.subTest(field=field), self.assertRaises(g.Failure):
                grade(result(**{field: value}))

    def test_error_or_absent_context_is_not_default_protection(self):
        for value in [result(error='operation failed'), result(context=None), result(context='false'),
                      result(context=False), {}, None]:
            with self.subTest(value=str(value)[:70]), self.assertRaises(g.Failure):
                grade(value, readback_allowed=False)

    def test_webgl_blocked_and_allowed_controls_are_both_required(self):
        blocked = result(operation='webgl', context=False, pixels=None)
        self.assertTrue(grade(blocked, operation='webgl', context_allowed=False, readback_allowed=False)['protected'])
        with self.assertRaises(g.Failure):
            grade(blocked, operation='webgl', context_allowed=True)
        with self.assertRaises(g.Failure):
            grade(result(operation='webgl'), operation='webgl', context_allowed=False, readback_allowed=False)
        self.assertTrue(grade(result(operation='webgl'), operation='webgl')['actualPixels'])

    def test_missing_webgl2_cannot_hide_behind_webgl1(self):
        with self.assertRaises(g.Failure):
            grade(result(operation='webgl'), operation='webgl2')

    def test_blocked_context_cannot_return_pixels(self):
        with self.assertRaises(g.Failure):
            grade(result(operation='webgl', context=False), operation='webgl', context_allowed=False)


class SelectionTests(unittest.TestCase):
    def test_exact_origin_and_resource_row(self):
        xml = ui({'text': 'WebGL — http://localhost:42450'}, {})
        node = g.select_node(xml, rid='origin_permission_pending_webgl', origin=ORIGIN, package='org.redoubtbrowser')
        self.assertEqual(node['centre'], (60, 50))
        self.assertEqual(g.text_origins(node['text']), {ORIGIN})

    def test_port_prefix_subdomain_and_host_suffix_never_match(self):
        for wrong in ['http://localhost:42450', 'http://localhost.evil:4245', 'http://sub.localhost:4245',
                      'https://localhost:4245', 'http://localhost.:4245']:
            with self.subTest(origin=wrong):
                self.assertIsNone(g.select_node(ui({'text': 'WebGL — '+wrong}),
                    rid='origin_permission_pending_webgl', origin=ORIGIN, required=False))

    def test_same_origin_duplicate_requests_fail_instead_of_picking_first(self):
        with self.assertRaisesRegex(g.Failure, 'Ambiguous'):
            g.select_node(ui({}, {}), rid='origin_permission_pending_webgl', origin=ORIGIN)

    def test_different_kind_and_forged_id_suffix_never_match(self):
        for rid in ['origin_permission_pending_canvas', 'xorigin_permission_pending_webgl',
                    'origin_permission_pending_webgl_extra']:
            self.assertIsNone(g.select_node(ui({'resource-id': 'org.redoubtbrowser:id/'+rid}),
                rid='origin_permission_pending_webgl', origin=ORIGIN, required=False))

    def test_disabled_hidden_or_zero_area_controls_are_not_actionable(self):
        for properties in [{'enabled': 'false'}, {'visible-to-user': 'false'}, {'bounds': '[0,0][0,0]'},
                           {'bounds': 'broken'}, {'package': 'another.app'}]:
            self.assertIsNone(g.select_node(ui(properties), rid='origin_permission_pending_webgl',
                origin=ORIGIN, package='org.redoubtbrowser', required=False))

    def test_compose_tag_and_native_resource_id_are_supported(self):
        for rid in ['origin_permissions_entry', 'org.redoubtbrowser:id/origin_permissions_entry']:
            self.assertIsNotNone(g.select_node(ui({'resource-id': rid}), rid='origin_permissions_entry'))

    def test_malformed_xml_is_not_missing_permission(self):
        with self.assertRaises(g.Failure):
            g.select_node('ERROR: UI hierarchy unavailable', rid='origin_permissions_entry', required=False)


class TransportTests(unittest.TestCase):
    CONFIG = 'args:\n  - "-remote-allow-system-access"\nenv:\n  MOZ_MARIONETTE: "1"\nprefs:\n  remote.prefs.recommended: false\n  marionette.port: 2828\n'

    def test_only_standard_transport_config_is_accepted(self):
        self.assertTrue(g.transport_config_facts(self.CONFIG)['transportOnly'])
        self.assertTrue(g.transport_config_facts('# comment\n'+self.CONFIG)['transportOnly'])

    def test_extra_privacy_pref_and_permission_bypass_taint_acceptance(self):
        for addition in ['  librewolf.webgl.prompt: false\n', '  privacy.resistFingerprinting: false\n',
                         '  dom.security.https_only_mode: false\n', '  marionette.port: 2828\n',
                         'extra-env: private-secret\n']:
            facts = g.transport_config_facts(self.CONFIG+addition)
            self.assertFalse(facts['transportOnly'])
            self.assertNotIn('private-secret', json.dumps(facts))

    def test_recommended_pref_injection_or_missing_config_is_rejected(self):
        for body in ['', self.CONFIG.replace('recommended: false', 'recommended: true'),
                     self.CONFIG.replace('MOZ_MARIONETTE: "1"', 'MOZ_MARIONETTE: "0"')]:
            self.assertFalse(g.transport_config_facts(body)['transportOnly'])

    def test_transport_port_is_valid_and_explicit(self):
        self.assertEqual(g.transport_config_facts(self.CONFIG)['marionettePort'], 2828)
        for port in ['0', '-1', '65536', '2828 trailing-value']:
            self.assertFalse(g.transport_config_facts(self.CONFIG.replace('2828', port))['transportOnly'])

    def test_extractor_does_not_execute_harness_top_level_or_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'smoke.sh'
            file.write_text("<<'PYDRIVEREOF'\nimport json\nraise RuntimeError('must not execute')\n"+
                '\n'.join('class '+name+':\n    pass' for name in ['Adb', 'Marionette', 'HarnessError', 'MarionetteError'])+
                "\nPYDRIVEREOF\n")
            module = g.foundation(file)
            self.assertTrue(hasattr(module, 'Marionette'))

    def test_real_transport_extraction_is_bound_to_a_hash(self):
        module = g.foundation()
        self.assertTrue(hasattr(module, 'Adb'))
        self.assertEqual(len(module.input_sha256), 64)
        self.assertFalse(hasattr(module, 'App'))
        self.assertFalse(hasattr(module, 'open_session'))

    def test_absent_device_is_pending_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)/'adb'
            log = Path(tmp)/'calls'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> '+str(log)+'\nprintf "List of devices attached\\n"\n')
            fake.chmod(0o755)
            with redirect_stdout(io.StringIO()) as stdout:
                code = g.main(['--adb', str(fake), '--work', tmp, '--dedicated-test-profile'])
            self.assertEqual(code, g.PENDING)
            summary = json.loads(stdout.getvalue())
            self.assertFalse(summary['acceptanceComplete'])
            self.assertEqual(summary['passedChecks'], 0)
            self.assertEqual(log.read_text().strip(), 'devices')

    def test_connected_adb_alone_does_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)/'adb'
            fake.write_text('#!/bin/sh\nprintf "List of devices attached\\nlab\\tdevice\\n"\n')
            fake.chmod(0o755)
            with redirect_stdout(io.StringIO()) as stdout:
                code = g.main(['--adb', str(fake), '--work', tmp])
            self.assertEqual(code, g.PENDING)
            self.assertEqual(json.loads(stdout.getvalue())['passedChecks'], 0)

    def test_connected_device_and_profile_flag_without_apk_still_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake, log = Path(tmp)/'adb', Path(tmp)/'calls'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> '+str(log)+'\n'+
                'if [ "$1" = devices ]; then printf "List of devices attached\\nlab\\tdevice\\n"; fi\n')
            fake.chmod(0o755)
            with redirect_stdout(io.StringIO()) as stdout:
                code = g.main(['--adb', str(fake), '--work', tmp, '--dedicated-test-profile'])
            summary = json.loads(stdout.getvalue())
            self.assertEqual(code, g.PENDING)
            self.assertFalse(summary['acceptanceComplete'])
            self.assertEqual(summary['passedChecks'], 0)
            self.assertIn('installed package is absent', summary['reason'])
            self.assertEqual(log.read_text().splitlines(), ['devices', '-s lab shell pm path org.redoubtbrowser'])

    def test_partial_runner_return_never_passes_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)/'adb'
            fake.write_text('#!/bin/sh\nprintf "List of devices attached\\nlab\\tdevice\\n"\n')
            fake.chmod(0o755)
            with patch.object(g.Runner, 'run'), patch.object(g.Runner, 'close'), \
                 patch.object(g.Runner, 'diagnostics'), redirect_stdout(io.StringIO()) as stdout:
                code = g.main(['--adb', str(fake), '--work', tmp, '--dedicated-test-profile'])
            self.assertEqual(code, g.PENDING)
            self.assertFalse(json.loads(stdout.getvalue())['acceptanceComplete'])

    def test_cleanup_continues_after_transport_failure_and_only_removes_owned_forward(self):
        args = type('Args', (), {'package': 'org.redoubtbrowser', 'ui_timeout': 1, 'no_screenshots': True})()
        with tempfile.TemporaryDirectory() as tmp:
            runner = g.Runner(args, g.Evidence(tmp, 'test', 'full'), object(), Mock())
            runner.reversed_ports = [1234, 5678]
            runner.forward_port = 4444  # Supplied/pre-existing, not created by this runner.
            runner.adb.run.side_effect = [OSError('device detached'), Mock()]
            fixture = Mock()
            runner.fixtures = [fixture]
            with self.assertRaisesRegex(g.Failure, 'device detached'):
                runner.close()
            fixture.close.assert_called_once()
            self.assertEqual(runner.adb.run.call_count, 2)
            self.assertTrue(all(call.args[0] == 'reverse' for call in runner.adb.run.call_args_list))


class UiFlowTests(unittest.TestCase):
    def runner(self, tmp):
        args = type('Args', (), {'package': 'org.redoubtbrowser', 'ui_timeout': 1, 'no_screenshots': True})()
        return g.Runner(args, g.Evidence(tmp, 'test', 'full'), object(), Mock())

    def test_saved_reload_waits_for_engine_acknowledgement(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = self.runner(tmp)
            calls = []
            runner.snapshot = lambda: {'document': {'origin': ORIGIN}}
            runner.ui = Mock()
            runner.ui.choose.side_effect = lambda **kw: calls.append('ui-choice')
            runner.wait_record = lambda *args: calls.append('ack')
            runner.ui.saved_reload.side_effect = lambda: calls.append('ui-reload')
            runner.wait_reload = lambda *args, **kw: calls.append('document-replaced')
            runner.choose(type('F', (), {'origin': ORIGIN})(), 'canvas', 'ask', saved=True)
            self.assertEqual(calls, ['ui-choice', 'ack', 'ui-reload', 'document-replaced'])

    def test_navigated_document_cannot_supply_a_current_pixel_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = self.runner(tmp)
            runner.snapshot = Mock(side_effect=[
                {'document': {'origin': ORIGIN, 'documentId': 'document'}},
                {'document': {'origin': ORIGIN, 'documentId': 'replacement'}},
            ])
            fixture = Mock(origin=ORIGIN)
            fixture.issue.return_value = ('command', result())
            with self.assertRaisesRegex(g.Failure, 'Current document changed'):
                runner.probe(fixture, 'canvas', context_allowed=True, readback_allowed=True)
            self.assertEqual(runner.evidence.data['checks'], [])
            raw = runner.evidence.data['artifacts'][0]
            self.assertEqual(json.loads((Path(tmp)/raw['path']).read_text())['pixels'], result()['pixels'])

    def test_failed_ack_never_clicks_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = self.runner(tmp)
            runner.snapshot = lambda: {'document': {'origin': ORIGIN}}
            runner.ui = Mock()
            runner.wait_record = Mock(side_effect=g.Failure('record not applied'))
            with self.assertRaises(g.Failure):
                runner.choose(type('F', (), {'origin': ORIGIN})(), 'canvas', 'ask', saved=True)
            runner.ui.saved_reload.assert_not_called()

    def test_request_frame_reload_is_distinct_from_saved_tab_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = self.runner(tmp)
            runner.snapshot = lambda: {'document': {'origin': ORIGIN}}
            runner.ui = Mock()
            runner.wait_record = Mock(return_value={'value': 1})
            runner.wait_reload = Mock()
            runner.choose(type('F', (), {'origin': 'http://localhost:4246'})(), 'webgl', 'allow', frame=True)
            runner.wait_reload.assert_called_once_with({'document': {'origin': ORIGIN}}, frame=True)
            self.assertEqual(runner.ui.choose.call_args.kwargs['top_origin'], ORIGIN)
            runner.ui.saved_reload.assert_not_called()

    def test_private_remember_checkbox_cannot_be_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = g.Evidence(tmp, 'test', 'full')
            instance = g.UI(Mock(), 'org.redoubtbrowser', evidence, 'test')
            xml = ui({'resource-id': 'origin_permission_request_origin', 'text': ORIGIN},
                     {'resource-id': 'origin_permission_remember', 'checkable': 'true', 'checked': 'false'})
            instance.open_permissions = Mock()
            instance.click = Mock()
            instance.wait = Mock(return_value=(xml, {'text': ORIGIN}))
            with self.assertRaisesRegex(g.Failure, 'Private consent offers'):
                instance.choose(origin=ORIGIN, kind='canvas', saved=False, decision='allow', permanent=False, private=True)
            self.assertEqual(instance.click.call_count, 1)  # Only selects the row, never Allow.

    def test_fresh_normal_consent_must_default_to_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = g.UI(Mock(), 'org.redoubtbrowser', g.Evidence(tmp, 'test', 'full'), 'test')
            xml = ui({'resource-id': 'origin_permission_request_origin', 'text': ORIGIN},
                     {'resource-id': 'origin_permission_remember', 'checkable': 'true', 'checked': 'true'})
            instance.open_permissions = Mock()
            instance.click = Mock()
            instance.wait = Mock(return_value=(xml, {'text': ORIGIN}))
            with self.assertRaisesRegex(g.Failure, 'defaults to persistent'):
                instance.choose(origin=ORIGIN, kind='webgl', saved=False, decision='allow', permanent=True, private=False)
            self.assertEqual(instance.click.call_count, 1)


class FixtureTests(unittest.TestCase):
    def test_parser_script_is_valid_and_contains_no_privileged_grants(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required to check the actual served fixture JavaScript')
        checked = subprocess.run([node, '--check'], input=g.FIXTURE_JS, text=True, capture_output=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        for forbidden in ['Services.', 'SpecialPowers', 'setPermission', 'Marionette']:
            self.assertNotIn(forbidden, g.FIXTURE_JS)
        self.assertIn('worker.terminate()', g.FIXTURE_JS)
        self.assertIn("new OffscreenCanvas(32,32)", g.FIXTURE_JS)

    def test_http_fixture_command_and_result_bind_to_actual_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = g.Evidence(tmp, 'run', 'test')
            fixture = g.Fixture('run', evidence, host='127.0.0.1')
            def post(route, data):
                request = urllib.request.Request(fixture.origin+route, json.dumps(data).encode(),
                                                 {'Content-Type': 'application/json'})
                return json.load(urllib.request.urlopen(request, timeout=3))
            try:
                page = urllib.request.urlopen(fixture.url(), timeout=3).read().decode()
                self.assertIn('<script>\nconst config', page)
                self.assertIn('fixture-state', page)
                metadata = {'run': 'run', 'documentId': 'doc', 'origin': fixture.origin, 'url': fixture.url()}
                self.assertTrue(post('/register', metadata)['ok'])
                out = []
                worker = threading.Thread(target=lambda: out.append(fixture.issue('doc', 'canvas', 'dom', COLORS, timeout=3)))
                worker.start()
                command = None
                for _ in range(30):
                    command = json.load(urllib.request.urlopen(fixture.origin+'/next?run=run&document=doc', timeout=3))
                    if command: break
                    time.sleep(.01)
                self.assertIsNotNone(command)
                post('/result', {**metadata, **command, 'pixels': [0]*4096, 'context': True})
                worker.join(4)
                self.assertEqual(out[0][0], command['commandId'])
                self.assertEqual(out[0][1]['documentId'], 'doc')
                self.assertIn('registeredAt', fixture.documents['doc'])
            finally:
                fixture.close()

    def test_no_connected_page_is_not_a_protected_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = g.Fixture('run', g.Evidence(tmp, 'run', 'test'))
            try:
                with self.assertRaisesRegex(g.Failure, 'did not register'):
                    fixture.issue('missing', 'webgl', 'dom', COLORS, timeout=0)
            finally:
                fixture.close()

    def test_runner_privileged_scripts_are_observation_only(self):
        for script in [g.PREFS_JS, g.PERMISSIONS_JS, g.WINDOW_JS, g.PRIVATE_WINDOWS_JS, g.DOCUMENT_JS]:
            for forbidden in ['setBoolPref', 'setIntPref', 'setStringPref', 'clearUserPref', 'addFromPrincipal',
                              'removeFromPrincipal', 'removeAll', '.allow(', '.cancel(', 'getContext(']:
                self.assertNotIn(forbidden, script)
        tree = ast.parse((ROOT/'scripts/android-graphics-smoke.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        forbidden = {'push_debug_config', 'setPermission', 'setPermissionWithLifetime', 'wipe', 'install'}
        self.assertFalse(any(isinstance(call.func, ast.Attribute) and call.func.attr in forbidden for call in calls))


if __name__ == '__main__':
    unittest.main(verbosity=2)
