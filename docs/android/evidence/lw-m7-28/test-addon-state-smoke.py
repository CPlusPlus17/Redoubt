#!/usr/bin/env python3
"""Host tests: real graders/fixture/UI selection, never a real device."""
import ast
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('addon_smoke', ROOT/'scripts/android-addon-state-smoke.py')
a = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(a)
PACKAGE = 'org.redoubtbrowser'
ORIGIN = 'http://127.0.0.1:4111'
VERSION = '1.74.0'


def state(enabled=True, private=False, installed=True):
    return {'id': a.ADDON_ID, 'errors': [], 'sameNameOtherIds': [],
        'addon': {'id': a.ADDON_ID, 'version': VERSION, 'active': enabled, 'userDisabled': not enabled,
                  'appDisabled': False, 'pendingUninstall': False, 'amoSigned': True, 'isBuiltin': False} if installed else None,
        'policy': enabled and installed, 'policyPrivateAllowed': private if enabled else None,
        'privatePermission': private, 'listeners': 1 if enabled and installed else 0,
        'permissionBackend': 'legacy-json', 'privatePermissionDisk': private,
        'memory': {'enabled': enabled, 'version': VERSION} if installed else None,
        'database': [{'active': enabled, 'userDisabled': not enabled, 'version': VERSION}] if installed else [],
        'cache': [{'enabled': enabled, 'version': VERSION}] if installed else []}


def grade_state(value, enabled=True, private=False, installed=True):
    return a.grade_state(value, installed=installed, enabled=enabled, private_allowed=private, version=VERSION)


def page(blocked=True):
    meta = {'run': 'run', 'caseId': 'case', 'documentId': 'doc', 'origin': ORIGIN,
            'url': ORIGIN+'/addon-probe?run=run&case=case'}
    kinds = ['allowed'] if blocked else ['blocked', 'allowed']
    return dict(meta, loaded=True, errors=[], counts={'allowed': 1, 'blocked': 0 if blocked else 1},
        executions=[{'kind': kind, 'ready': 'loading', 'async': False, 'defer': False,
                     'src': ORIGIN+(a.ALLOWED_PATH if kind == 'allowed' else a.BLOCKED_PATH)+'?run=run&case=case&doc=doc'} for kind in kinds])


def requests(blocked=True):
    value = page(blocked)
    meta = {key: value[key] for key in ['run', 'caseId', 'documentId', 'origin', 'url']}
    return [dict(meta, kind=kind, at=1, counts=value['counts']) for kind in
            ['document']+(['allowed'] if blocked else ['blocked', 'allowed'])+['report']]


def grade_navigation(value=None, rows=None, blocked=True):
    return a.grade_navigation(page(blocked) if value is None else value, requests(blocked) if rows is None else rows,
        run='run', case_id='case', document_id='doc', origin=ORIGIN, blocked=blocked, before_connect=2)


def ui_xml(enabled=True, private=False, clickable=True, completed=True, private_visible=True, package=PACKAGE):
    def node(rid, **attrs):
        values = {'resource-id': package+':id/'+rid, 'package': package, 'enabled': 'true', 'bounds': '[0,0][200,40]', **attrs}
        return '<node '+' '.join(key+'="'+str(value)+'"' for key, value in values.items())+'/>'
    return '<hierarchy>'+node('toolbar_title', text=a.ADDON_NAME)+\
        node('enable_switch', checkable='true', checked=str(enabled).lower(), clickable=str(clickable).lower())+\
        (node('allow_in_private_browsing_switch', checkable='true', checked=str(private).lower(), clickable=str(clickable).lower()) if private_visible else '')+\
        node('remove_add_on', clickable='true', enabled=str(completed).lower())+\
        node('report_add_on', clickable='true', enabled=str(completed).lower())+'</hierarchy>'


class StateTests(unittest.TestCase):
    def test_consistent_enable_disable_private_and_removal(self):
        for enabled in (True, False):
            for private in (True, False): grade_state(state(enabled, private), enabled, private)
        grade_state(state(False, installed=False), enabled=False, installed=False)

    def test_disabled_registry_cannot_conceal_stale_live_policy(self):
        for field, value in [('policy', True), ('listeners', 1)]:
            observed = state(False); observed[field] = value
            with self.assertRaises(a.Failure): grade_state(observed, enabled=False)

    def test_each_disk_or_memory_cache_is_independent(self):
        for field in ('cache', 'database', 'memory'):
            observed = state(False)
            if field == 'database': observed[field][0]['userDisabled'] = False
            elif field == 'memory': observed[field]['enabled'] = True
            else: observed[field][0]['enabled'] = True
            with self.subTest(field=field), self.assertRaises(a.Failure): grade_state(observed, enabled=False)

    def test_private_live_and_stored_choices_must_agree(self):
        for field in ('policyPrivateAllowed', 'privatePermission', 'privatePermissionDisk'):
            observed = state(private=True); observed[field] = False
            with self.assertRaises(a.Failure): grade_state(observed, private=True)

    def test_missing_unsigned_builtin_or_wrong_version_never_passes(self):
        for field, value in [('amoSigned', False), ('isBuiltin', True), ('id', 'other'), ('version', 'old'),
                             ('active', 1), ('userDisabled', True), ('pendingUninstall', True)]:
            observed = state(); observed['addon'][field] = value
            with self.subTest(field=field), self.assertRaises(a.Failure): grade_state(observed)

    def test_same_name_ambiguity_and_read_failures_are_not_success(self):
        for field, value in [('sameNameOtherIds', ['other']), ('errors', ['read failed']), ('listeners', True),
                             ('database', []), ('cache', None)]:
            observed = state(); observed[field] = value
            with self.assertRaises(a.Failure): grade_state(observed)

    def test_removed_registry_entry_does_not_excuse_residual_state(self):
        for field, value in [('policy', True), ('listeners', 1), ('memory', {'enabled': False}),
                             ('database', [{'active': False}]), ('cache', [{'enabled': False}])]:
            observed = state(False, installed=False); observed[field] = value
            with self.subTest(field=field), self.assertRaises(a.Failure): grade_state(observed, enabled=False, installed=False)


class NavigationTests(unittest.TestCase):
    def test_actual_block_and_actual_allow_are_separate_controls(self):
        self.assertTrue(grade_navigation()['blocked'])
        self.assertFalse(grade_navigation(blocked=False)['blocked'])

    def test_script_count_alone_cannot_pass_without_server_requests(self):
        for missing in ('document', 'report', 'allowed'):
            with self.assertRaises(a.Failure): grade_navigation(rows=[row for row in requests() if row['kind'] != missing])

    def test_missing_blocked_server_request_cannot_fake_disable_success(self):
        with self.assertRaises(a.Failure):
            grade_navigation(rows=[row for row in requests(False) if row['kind'] != 'blocked'], blocked=False)

    def test_a_network_block_without_working_allowed_script_cannot_pass(self):
        value = page(); value['counts']['allowed'] = 0
        with self.assertRaises(a.Failure): grade_navigation(value)

    def test_unexpected_blocked_request_fails_even_if_page_says_blocked(self):
        with self.assertRaises(a.Failure): grade_navigation(rows=requests()+[dict(requests()[0], kind='blocked')])

    def test_missing_parser_provenance_fails(self):
        value = page(); value['executions'] = []
        with self.assertRaises(a.Failure): grade_navigation(value)

    def test_dynamic_async_deferred_wrong_origin_or_wrong_token_scripts_fail(self):
        for field, value in [('ready', 'complete'), ('async', True), ('defer', True), ('src', 'https://other/script'),
                             ('src', ORIGIN+a.ALLOWED_PATH+'?run=other&case=case&doc=doc')]:
            observed = page(); observed['executions'][0][field] = value
            with self.subTest(field=field), self.assertRaises(a.Failure): grade_navigation(observed)

    def test_duplicate_execution_cannot_replace_another_resource(self):
        value = page(False); value['executions'] = [value['executions'][1]]*2
        with self.assertRaises(a.Failure): grade_navigation(value, blocked=False)

    def test_page_identity_and_url_are_exact(self):
        for field in ('run', 'caseId', 'documentId', 'origin', 'url'):
            value = page(); value[field] = 'wrong'
            with self.subTest(field=field), self.assertRaises(a.Failure): grade_navigation(value)

    def test_wrong_or_stale_origin_requests_fail(self):
        for field in ('run', 'caseId', 'documentId', 'origin'):
            rows = requests(); rows[1][field] = 'other'
            with self.assertRaises(a.Failure): grade_navigation(rows=rows)

    def test_parser_must_finish_before_first_transport_attach(self):
        rows = requests(); rows[-1]['at'] = 3
        with self.assertRaisesRegex(a.Failure, 'before Marionette'): grade_navigation(rows=rows)

    def test_report_and_real_counter_types_are_required(self):
        value = page(); value['counts']['allowed'] = True
        with self.assertRaises(a.Failure): grade_navigation(value)
        rows = requests(); rows[-1]['counts'] = {'allowed': 0, 'blocked': 0}
        with self.assertRaises(a.Failure): grade_navigation(rows=rows)


class UiTests(unittest.TestCase):
    def test_enabled_private_and_disabled_callback_states(self):
        a.grade_ui_ack(ui_xml(), action='enabled', value=True, package=PACKAGE)
        a.grade_ui_ack(ui_xml(private=True), action='private', value=True, package=PACKAGE)
        a.grade_ui_ack(ui_xml(False, private_visible=False), action='enabled', value=False, package=PACKAGE)

    def test_optimistic_checked_bit_is_not_acknowledgment(self):
        for xml in (ui_xml(clickable=False), ui_xml(completed=False)):
            with self.assertRaises(a.Failure): a.grade_ui_ack(xml, action='enabled', value=True, package=PACKAGE)

    def test_private_visibility_requires_actual_enable_callback(self):
        with self.assertRaises(a.Failure):
            a.grade_ui_ack(ui_xml(False), action='enabled', value=False, package=PACKAGE)

    def test_wrong_package_or_ambiguous_addon_title_fails(self):
        for xml in (ui_xml(package='other.package'), ui_xml().replace('</hierarchy>',
                    '<node package="'+PACKAGE+'" text="uBlock Origin" enabled="true" bounds="[0,0][50,50]"/></hierarchy>')):
            with self.assertRaises(a.Failure): a.grade_ui_ack(xml, action='enabled', value=True, package=PACKAGE)

    def test_removal_requires_success_navigation_not_missing_checkbox(self):
        with self.assertRaises(a.Failure): a.grade_ui_ack('<hierarchy/>', action='remove', value=None, package=PACKAGE)
        xml = '<hierarchy><node resource-id="'+PACKAGE+':id/add_ons_list" package="'+PACKAGE+'" enabled="true" bounds="[0,0][50,50]"/></hierarchy>'
        self.assertEqual(a.grade_ui_ack(xml, action='remove', value=None, package=PACKAGE)['ack'], 'manager-after-success')

    def test_stop_is_first_command_after_completion_xml_before_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = a.Evidence(tmp, 'run'); ui = a.AddonUI(Mock(), PACKAGE, evidence, 'run', 1, False)
            ui.open_addon = Mock(return_value=ui_xml())
            calls = []
            def shell(*args, **kwargs):
                calls.append(args)
                return ui_xml(False, private_visible=False) if args[0] == 'cat' else ''
            ui.shell = shell
            evidence.artifact = lambda *args: calls.append(('artifact',))
            timing = ui.choose_then_stop('enabled', False, 'redoubt')
            index = next(index for index, command in enumerate(calls) if command[0] == 'cat')
            self.assertEqual(calls[index+1], ('am', 'force-stop', PACKAGE))
            self.assertGreater(calls.index(('artifact',)), index+1)
            self.assertTrue(timing['acknowledged'])

    def test_timing_requires_ack_order_and_conservative_bound(self):
        timing = {'acknowledged': True, 'actionStarted': 1, 'ackObserved': 1.1, 'stopIssued': 1.11, 'stopCompleted': 1.12}
        self.assertLess(a.grade_timing(timing)['actionToStoppedUpperBoundMs'], 1000)
        with self.assertRaises(a.Failure): a.grade_timing(dict(timing, acknowledged=False))
        with self.assertRaises(a.Failure): a.grade_timing(dict(timing, stopIssued=1.05))
        with self.assertRaises(a.Pending): a.grade_timing(dict(timing, stopCompleted=2.1))

    def test_slow_ui_timing_keeps_functional_restart_running(self):
        args = type('Args', (), {'package': PACKAGE, 'ui_timeout': 1, 'no_screenshots': True, 'scheme': 'redoubt'})()
        with tempfile.TemporaryDirectory() as tmp:
            runner = a.Runner(args, a.Evidence(tmp, 'run'), object(), Mock())
            runner.shell = Mock(return_value='oldpid'); runner.ui = Mock()
            runner.ui.choose_then_stop.return_value = {'acknowledged': True, 'actionStarted': 1,
                'ackObserved': 3, 'stopIssued': 3.01, 'stopCompleted': 3.02}
            runner.resume_first_navigation = Mock()
            runner.choice_restart('enabled', False, 'disabled-normal')
            runner.resume_first_navigation.assert_called_once_with('disabled-normal', 'oldpid')
            self.assertEqual(len(runner.evidence.data['pending']), 1)


class FixtureTransportTests(unittest.TestCase):
    def test_actual_http_fixture_has_parser_scripts_and_bound_resource_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = a.Fixture('run', a.Evidence(tmp, 'run'))
            try:
                case_id = fixture.case('test')
                with urllib.request.urlopen(fixture.url(case_id), timeout=3) as response: html = response.read().decode()
                self.assertIn('<script src="'+a.BLOCKED_PATH, html)
                self.assertIn('<script src="'+a.ALLOWED_PATH, html)
                doc_id = next(iter(fixture.documents)); meta = fixture.documents[doc_id].copy()
                url = fixture.origin+a.ALLOWED_PATH+'?'+urllib.parse.urlencode({'run':'run','case':case_id,'doc':doc_id})
                with urllib.request.urlopen(url, timeout=3) as response:
                    self.assertEqual(response.read().decode(), 'window.fixtureScriptRan("allowed");')
                self.assertEqual(fixture.requests[-1]['documentId'], doc_id)
                report = dict(meta, counts={'allowed':1,'blocked':0})
                req = urllib.request.Request(fixture.origin+'/report', json.dumps(report).encode())
                with urllib.request.urlopen(req, timeout=3) as response: self.assertTrue(json.load(response)['ok'])
                self.assertIn('registeredAt', fixture.documents[doc_id])
                report['origin'] = 'https://other.example'
                req = urllib.request.Request(fixture.origin+'/report', json.dumps(report).encode())
                with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(req, timeout=3)
                caught.exception.close()
            finally: fixture.close()

    def test_fixture_and_read_only_observers_parse(self):
        node = shutil.which('node'); self.assertIsNotNone(node)
        for body in [a.FIXTURE_JS]+['function observer(){\n'+body+'\n}' for body in (a.STATE_JS, a.PREFS_JS, a.PAGE_JS)]:
            result = subprocess.run([node, '--check'], input=body, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_installed_apk_fails_before_bundle_or_ui(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp)/'expected.bin'; candidate.write_bytes(b'exact candidate identity')
            args = type('Args', (), {'package':PACKAGE,'ui_timeout':1,'no_screenshots':True,'apk':candidate})()
            adb = Mock(); adb.run.return_value = Mock(returncode=0, stdout='package:/installed/base.apk\n')
            runner = a.Runner(args, a.Evidence(tmp, 'run'), object(), adb)
            def shell(*args):
                return {'pm':'package:/installed/base.apk\n','dumpsys':'flags=[ HAS_CODE ]',
                        'sha256sum':'0'*64+' /installed/base.apk'}[args[0]]
            runner.shell = shell
            with patch.object(a, 'bundle_evidence') as bundle, self.assertRaisesRegex(a.Failure, 'differs from --apk'):
                runner.prerequisite()
            bundle.assert_not_called()

    def fake_run(self, connected, partial=False):
        with tempfile.TemporaryDirectory() as tmp:
            adb = Path(tmp)/'fake-adb'
            adb.write_text('#!/bin/sh\nif [ "$1" = devices ]; then printf "List of devices attached\\n'+
                           ('lab\\tdevice\\n' if connected else '')+'"; fi\n'); adb.chmod(0o755)
            with redirect_stdout(io.StringIO()) as output:
                if partial:
                    with patch.object(a.Runner, 'run'), patch.object(a.Runner, 'diagnostics'), patch.object(a.Runner, 'close'):
                        result = a.main(['--adb',str(adb),'--dedicated-test-profile','--work',tmp])
                else: result = a.main(['--adb',str(adb),'--dedicated-test-profile','--work',tmp])
            return result, json.loads(output.getvalue())

    def test_absent_device_connected_without_apk_and_partial_return_are_pending(self):
        for connected, partial in ((False,False),(True,False),(True,True)):
            result, report = self.fake_run(connected, partial)
            self.assertEqual(result, a.PENDING)
            self.assertFalse(report['acceptanceComplete']); self.assertFalse(report['functionalComplete'])

    def test_no_addon_policy_permission_or_install_mutations(self):
        for source in (a.STATE_JS, a.PREFS_JS, a.PAGE_JS):
            for forbidden in ('.disable(', '.enable(', '.uninstall(', '.install(', 'setBoolPref', 'setIntPref',
                              'setStringPref', 'clearUserPref', 'ExtensionPermissions.add', 'ExtensionPermissions.remove'):
                self.assertNotIn(forbidden, source)
        source = (ROOT/'scripts/android-addon-state-smoke.py').read_text()
        calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(call.func, ast.Attribute) and call.func.attr in {'install','wipe','push_debug_config'} for call in calls))
        self.assertIn('"signed-update"', source)


if __name__ == '__main__': unittest.main(verbosity=2)
