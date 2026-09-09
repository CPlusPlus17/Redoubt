#!/usr/bin/env python3
"""Host negatives for real cookie behavior evidence; no real adb is invoked."""
import ast
from contextlib import redirect_stdout, redirect_stderr
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('cookie_smoke', ROOT/'scripts/android-cookie-banner-smoke.py')
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)
ORIGIN = 'http://localhost:4245'


def state(**changes):
    value = {'run': 'run', 'caseId': 'case', 'documentId': 'document', 'origin': ORIGIN,
             'loaded': True, 'errors': [], 'reject': 1, 'accept': 0, 'cookieValue': 'reject',
             'initialCookie': None, 'observedMillis': 7000, 'bannerPresent': False, 'bannerVisible': False}
    value.update(changes)
    return value


def request(route='/state', **changes):
    value = {'run': 'run', 'caseId': 'case', 'documentId': 'document', 'origin': ORIGIN,
             'route': route, 'requestCookie': 'reject'}
    value.update(changes)
    return value


def grade(value=None, requests=None, **changes):
    options = {'run': 'run', 'case_id': 'case', 'document_id': 'document', 'origin': ORIGIN,
               'reject': 1, 'accept': 0, 'consent': 'reject', 'initial': None, 'minimum_ms': 7000}
    options.update(changes)
    if requests is None:
        requests = [request('/action', action='reject'), request()]
    return c.grade_observation(state() if value is None else value, requests, **options)


def inventory():
    return {'ready': True, 'snapshotSha256': c.SNAPSHOT_HASH, 'snapshotBytes': 262208,
            'ruleCount': 558, 'globalCount': 9, 'selected': {
                **{name: {'domains': [], 'click': copy.deepcopy(selectors)} for name, selectors in c.RULES.items()},
                'duh': {'domains': ['duh.de'], 'cookies': [{'name': 'cookie_dismiss', 'value': 'true'}]}}}


def prefs():
    return [{'name': name, 'value': value, 'hasUserValue': False}
            for name, value in [('cookiebanners.listService.testRules', ''),
                ('cookiebanners.listService.testSkipRemoteSettings', False), ('cookiebanners.bannerClicking.testing', False)]]


class BehaviorTests(unittest.TestCase):
    def test_real_rejection_requires_callback_cookie_and_endpoint(self):
        self.assertEqual(grade()['reject'], 1)

    def test_cosmetic_hiding_never_counts_as_rejection(self):
        with self.assertRaises(c.Failure):
            grade(state(reject=0, cookieValue=None, bannerVisible=False), [request(requestCookie=None)])

    def test_callback_without_cookie_fails(self):
        with self.assertRaisesRegex(c.Failure, 'Page cookie'):
            grade(state(cookieValue=None))

    def test_callback_without_action_request_fails(self):
        with self.assertRaisesRegex(c.Failure, 'Server action count'):
            grade(requests=[request()])

    def test_action_cookie_header_is_independent(self):
        with self.assertRaisesRegex(c.Failure, 'Action request did not carry'):
            grade(requests=[request('/action', action='reject', requestCookie=None), request()])

    def test_final_cookie_header_is_independent(self):
        with self.assertRaisesRegex(c.Failure, 'Server cookie'):
            grade(requests=[request('/action', action='reject'), request(requestCookie=None)])

    def test_allowed_request_control_is_mandatory(self):
        with self.assertRaisesRegex(c.Failure, 'successful allowed'):
            grade(requests=[request('/action', action='reject')])

    def test_duplicate_or_wrong_actions_fail(self):
        for events in [[request('/action', action='reject')]*2+[request()],
                       [request('/action', action='accept'), request()]]:
            with self.assertRaises(c.Failure):
                grade(requests=events)

    def test_stale_or_cross_origin_page_state_fails(self):
        for field, value in [('run', 'other'), ('caseId', 'other'), ('documentId', 'old'),
                             ('origin', 'http://localhost:42450')]:
            with self.subTest(field=field), self.assertRaises(c.Failure):
                grade(state(**{field: value}))

    def test_stale_or_cross_origin_request_cannot_pass(self):
        for field, value in [('run', 'other'), ('caseId', 'other'), ('documentId', 'old'),
                             ('origin', 'http://localhost.evil:4245')]:
            with self.subTest(field=field), self.assertRaises(c.Failure):
                grade(requests=[request('/action', action='reject', **{field: value}), request()])

    def test_errors_wrong_counter_types_and_short_windows_fail(self):
        for value in [state(reject=True), state(accept='0'), state(loaded=False), state(errors=['blocked fetch']),
                      state(observedMillis=6999)]:
            with self.assertRaises(c.Failure):
                grade(value)

    def test_accept_only_protection_and_later_accept_are_distinct(self):
        protected = state(reject=0, cookieValue=None, bannerVisible=True)
        result = grade(protected, [request(requestCookie=None)], reject=0, consent=None)
        self.assertEqual(result['accept'], 0)
        with self.assertRaises(c.Failure):
            grade(protected, [request(requestCookie=None)], reject=0, accept=1, consent='accept')
        accepted = state(reject=0, accept=1, cookieValue='accept')
        events = [request('/action', action='accept', requestCookie='accept'), request(requestCookie='accept')]
        self.assertEqual(grade(accepted, events, reject=0, accept=1, consent='accept')['accept'], 1)
        with self.assertRaises(c.Failure):
            grade(accepted, events, reject=0, consent=None)

    def test_preexisting_consent_is_explicit(self):
        retained = state(reject=0, initialCookie='reject')
        self.assertEqual(grade(retained, [request()], reject=0, initial='reject')['initialCookie'], 'reject')
        with self.assertRaises(c.Failure):
            grade(retained, [request()], reject=0)

    def test_cookie_parser_matches_only_exact_name(self):
        self.assertEqual(c.cookie_value('unrelated=secret; lw_cookie_a=reject', 'lw_cookie_a'), 'reject')
        self.assertIsNone(c.cookie_value('lw_cookie_ab=accept', 'lw_cookie_a'))


class InventoryTests(unittest.TestCase):
    def test_actual_inventory_requires_readiness_and_packaged_hash(self):
        self.assertEqual(c.grade_inventory(inventory())['ruleCount'], 558)
        for field, value in [('ready', False), ('snapshotSha256', '0'*64), ('snapshotBytes', 0),
                             ('ruleCount', 557), ('globalCount', 0)]:
            data = inventory(); data[field] = value
            with self.subTest(field=field), self.assertRaises(c.Failure):
                c.grade_inventory(data)

    def test_real_selectors_and_accept_only_rule_are_mandatory(self):
        for name, field, value in [('cookiebot', 'optOut', '#fake-reject'), ('didomi', 'optOut', '#invented-reject'),
                                  ('didomi', 'optIn', '#fake-accept')]:
            data = inventory(); data['selected'][name]['click'][field] = value
            with self.assertRaises(c.Failure):
                c.grade_inventory(data)

    def test_missing_domain_injection_rule_is_not_inventory_success(self):
        data = inventory(); data['selected']['duh']['cookies'] = []
        with self.assertRaises(c.Failure):
            c.grade_inventory(data)

    def test_production_overrides_must_be_unset_not_just_false(self):
        self.assertEqual(c.grade_pref_taint(prefs())['cookiebanners.listService.testRules'], '')
        for index in range(3):
            data = prefs(); data[index]['hasUserValue'] = True
            with self.assertRaises(c.Pending):
                c.grade_pref_taint(data)
        for index, value in [(0, '[]'), (0, 0), (1, True), (1, 0), (2, True)]:
            data = prefs(); data[index]['value'] = value
            with self.assertRaises(c.Pending):
                c.grade_pref_taint(data)

    def test_readiness_await_precedes_real_rule_read(self):
        self.assertLess(c.INVENTORY_JS.index('await service.initForTest()'), c.INVENTORY_JS.index('Services.cookieBanners.rules'))
        self.assertNotIn('resetRules', c.INVENTORY_JS)

    def test_both_disabled_restart_does_not_wait_for_disabled_list_service(self):
        args = type('Args', (), {'package': 'org.redoubtbrowser', 'ui_timeout': 1, 'no_screenshots': True})()
        observed = prefs() + [{'name': name, 'value': value, 'hasUserValue': False} for name, value in [
            ('cookiebanners.service.mode', 0), ('cookiebanners.service.mode.privateBrowsing', 0),
            ('cookiebanners.service.detectOnly', False), ('cookiebanners.service.enableGlobalRules', True),
            ('cookiebanners.bannerClicking.enabled', True), ('cookiebanners.bannerClicking.timeoutAfterLoad', 5000)]]
        with tempfile.TemporaryDirectory() as tmp:
            runner = c.Runner(args, c.Evidence(tmp, 'run', 'test'), object(), Mock())
            runner.marionette = Mock()
            runner.marionette.script.return_value = observed
            self.assertEqual(runner.facts()['cookiebanners.service.mode'], 0)
            runner.marionette.script.assert_called_once_with(c.PREFS_JS, chrome=True)
            self.assertEqual(runner.evidence.data['checks'], [])
            observed[3]['value'] = 1
            runner.marionette.script.reset_mock()
            runner.marionette.script.side_effect = [observed, inventory()]
            runner.facts()
            self.assertEqual(runner.marionette.script.call_args.args[0], c.INVENTORY_JS)
            self.assertEqual(runner.evidence.data['checks'][0]['name'], 'packaged-rule-inventory')

    def test_existing_global_off_choice_is_pending_without_default_failure_or_injection(self):
        args = type('Args', (), {'package': 'org.redoubtbrowser', 'ui_timeout': 1, 'no_screenshots': True})()
        with tempfile.TemporaryDirectory() as tmp:
            runner = c.Runner(args, c.Evidence(tmp, 'run', 'test'), object(), Mock())
            runner.prerequisite = Mock()
            runner.start_fixtures = Mock()
            runner.fixture = Mock()
            runner.open_case = Mock()
            runner.facts = Mock(return_value={'cookiebanners.service.mode': 0,
                                              'cookiebanners.service.mode.privateBrowsing': 1})
            runner.verify_controlled_origins = Mock()
            runner.core = Mock()
            with self.assertRaisesRegex(c.Pending, 'existing saved Off choice'):
                runner.run()
            runner.core.assert_not_called()


class ControlledOriginTests(unittest.TestCase):
    def test_invalid_or_empty_credential_origins_are_rejected_before_device_access(self):
        for value in ['https://@fixture.test', 'https://:@fixture.test', 'https://fixture.test:0',
                      'https://fixture.test:bad', 'https://fixture.test:65536', 'https://', 'https://[bad']:
            with self.subTest(value=value), redirect_stderr(io.StringIO()), \
                    patch.object(c.g, 'foundation') as protocol, self.assertRaises(SystemExit) as error:
                c.main(['--site-origin', value, '--fixture-port', '40000'])
            self.assertEqual(error.exception.code, 2)
            protocol.assert_not_called()

    def response(self, **changes):
        response = {'url': 'https://duh.de/cookie-fixture-probe?run=r', 'status': 200, 'proof': 'secret-proof',
                    'secure': True, 'overridden': False, 'errorCode': 0, 'overridableErrorCategory': 0,
                    'verifiedChainSha256': ['leaf-sha256', 'a'*64]}
        response.update(changes)
        return response

    def grade(self, response):
        return c.grade_controlled_origin(response, url='https://duh.de/cookie-fixture-probe?run=r',
                                        proof='secret-proof', ca_sha256='a'*64)

    def test_valid_origin_requires_private_proof_and_expected_verified_ca(self):
        verified = self.grade(self.response())
        self.assertNotIn('proof', verified)
        self.assertEqual(verified['verifiedChainSha256'][-1], 'a'*64)

    def test_unrelated_live_origin_cannot_echo_public_url_nonce_as_proof(self):
        for proof in [None, 'r', 'wrong-proof', '']:
            with self.assertRaises(c.Pending):
                self.grade(self.response(proof=proof))

    def test_redirect_status_and_tls_overrides_fail_closed(self):
        for properties in [{'url': 'https://other.example/cookie-fixture-probe?run=r'}, {'status': 302},
                           {'secure': False}, {'overridden': True}, {'errorCode': -8181},
                           {'overridableErrorCategory': 1}, {'error': 'certificate error'}]:
            with self.subTest(properties=properties), self.assertRaises(c.Pending):
                self.grade(self.response(**properties))

    def test_missing_unverified_or_wrong_ca_chain_is_pending(self):
        for chain in [None, [], ['a'*64, 'different-root'], ['b'*64]]:
            with self.assertRaises(c.Pending):
                self.grade(self.response(verifiedChainSha256=chain))

    def test_verifier_never_sends_the_host_secret_or_navigates_the_unverified_origin(self):
        args = type('Args', (), {'package': 'org.redoubtbrowser', 'ui_timeout': 1, 'no_screenshots': True,
            'site_origin': None, 'injection_origin': 'https://duh.de', 'fixture_ca_sha256': 'a'*64})()
        with tempfile.TemporaryDirectory() as tmp:
            runner = c.Runner(args, c.Evidence(tmp, 'run', 'test'), object(), Mock())
            runner.fixture = Mock(proof='private-not-in-request')
            runner.marionette = Mock()
            runner.marionette.script.return_value = self.response(proof='remote-site-guess')
            runner.open_case = Mock()
            runner.verify_controlled_origins()
            self.assertFalse(runner.injection_verified)
            self.assertNotIn('private-not-in-request', repr(runner.marionette.script.call_args))
            self.assertNotIn('remote-site-guess', json.dumps(runner.evidence.data))
            runner.open_case.assert_not_called()


class UiTests(unittest.TestCase):
    def xml(self, first_has_switch=True, duplicate=False):
        switch = '<node class="android.widget.Switch" package="org.redoubtbrowser" checkable="true" checked="true" enabled="true" bounds="[100,10][160,70]" />'
        title = '<node text="Cookie Banner Blocker in private browsing" package="org.redoubtbrowser" enabled="true" bounds="[0,10][100,70]" />'
        return '<hierarchy><node scrollable="true"><node>'+title+(switch if first_has_switch else '')+\
            '</node><node><node text="Another setting" />'+switch+'</node>'+\
            ('<node>'+title+switch+'</node>' if duplicate else '')+'</node></hierarchy>'

    def test_switch_is_bound_to_own_preference_row(self):
        switch = c.preference_switch(self.xml(), 'Cookie Banner Blocker in private browsing', 'org.redoubtbrowser')
        self.assertEqual(switch['checked'], 'true')

    def test_next_rows_switch_cannot_substitute_for_missing_control(self):
        with self.assertRaisesRegex(c.Failure, 'own row'):
            c.preference_switch(self.xml(False), 'Cookie Banner Blocker in private browsing', 'org.redoubtbrowser')

    def test_duplicate_preference_titles_are_ambiguous(self):
        with self.assertRaisesRegex(c.Failure, 'Ambiguous'):
            c.preference_switch(self.xml(duplicate=True), 'Cookie Banner Blocker in private browsing', 'org.redoubtbrowser')

    def test_site_scope_requires_correct_domain_subdomains_schemes_and_lifetime(self):
        import html
        def scope_xml(text):
            return '<hierarchy><node resource-id="org.redoubtbrowser:id/cookie_banner_site_scope" '+\
                'package="org.redoubtbrowser" enabled="true" bounds="[0,0][400,100]" text="'+html.escape(text, quote=True)+'"/></hierarchy>'
        normal = 'fixture.test and all its subdomains, over HTTP and HTTPS. Normal browsing only. Exceptions are remembered after restarting.'
        c.verify_site_scope(scope_xml(normal), 'fixture.test', False, 'org.redoubtbrowser')
        for wrong in [normal.replace('fixture.test', 'other.test'), normal.replace('and all its subdomains, ', ''),
                      normal.replace('HTTP and HTTPS', 'HTTPS'), normal.replace('Normal browsing', 'Private browsing')]:
            with self.assertRaises(c.Failure):
                c.verify_site_scope(scope_xml(wrong), 'fixture.test', False, 'org.redoubtbrowser')
        with self.assertRaises(c.Failure):
            c.verify_site_scope(scope_xml(normal), 'fixture.test', True, 'org.redoubtbrowser')

    def test_site_reload_waits_for_actual_engine_domain_ack(self):
        args = type('Args', (), {'package': 'org.redoubtbrowser', 'ui_timeout': 1, 'no_screenshots': True})()
        with tempfile.TemporaryDirectory() as tmp:
            runner = c.Runner(args, c.Evidence(tmp, 'run', 'test'), object(), Mock())
            calls = []
            runner.snapshot = lambda: {'document': {'documentId': 'current'}}
            runner.domain_mode = lambda *_: {'domain': 'fixture.test', 'mode': 0}
            runner.ui = Mock()
            runner.ui.site.side_effect = lambda *a, **kw: calls.append('real-ui-reset')
            runner.wait_domain_mode = lambda *a: calls.append('engine-ack') or {'mode': 3}
            runner.wait_reload = lambda *a: calls.append('new-document')
            runner.site_choice('https://fixture.test', True, reset=True)
            self.assertEqual(calls, ['real-ui-reset', 'engine-ack', 'new-document'])
            self.assertTrue(runner.ui.site.call_args.kwargs['reset'])

    def test_failed_domain_ack_never_counts_a_reload_or_success(self):
        args = type('Args', (), {'package': 'org.redoubtbrowser', 'ui_timeout': 1, 'no_screenshots': True})()
        with tempfile.TemporaryDirectory() as tmp:
            runner = c.Runner(args, c.Evidence(tmp, 'run', 'test'), object(), Mock())
            runner.snapshot = lambda: {'document': {'documentId': 'current'}}
            runner.domain_mode = lambda *_: {'domain': 'fixture.test', 'mode': 3}
            runner.ui = Mock()
            runner.wait_domain_mode = Mock(side_effect=c.Failure('not applied'))
            runner.wait_reload = Mock()
            with self.assertRaises(c.Failure):
                runner.site_choice('https://fixture.test', False)
            runner.wait_reload.assert_not_called()
            self.assertEqual(runner.evidence.data['checks'], [])

    def test_explicit_accept_happens_after_protected_observation(self):
        args = type('Args', (), {'package': 'org.redoubtbrowser', 'ui_timeout': 1, 'no_screenshots': True})()
        with tempfile.TemporaryDirectory() as tmp:
            runner = c.Runner(args, c.Evidence(tmp, 'run', 'test'), object(), Mock())
            runner.fixture = Mock()
            runner.fixture.case.side_effect = ['cookie', 'didomi']
            runner.fixture.lock = __import__('threading').RLock()
            runner.fixture.requests = [{'documentId': 'doc', 'route': '/action', 'isTrusted': True}]
            calls = []
            runner.open_case = lambda case: calls.append('open-'+case)
            runner.observe = lambda **kw: calls.append(kw['label']) or {'documentId': 'doc'}
            runner.explicit_click = lambda selector: calls.append('explicit-click')
            runner.core()
            self.assertEqual(calls, ['open-cookie', 'cookiebot-native-reject', 'open-didomi', 'didomi-reject-only',
                                     'explicit-click', 'didomi-explicit-click-control'])


class TransportFixtureTests(unittest.TestCase):
    def fake_run(self, connected, flag=True, partial=False):
        with tempfile.TemporaryDirectory() as tmp:
            adb = Path(tmp)/'adb'
            adb.write_text('#!/bin/sh\nif [ "$1" = devices ]; then printf "List of devices attached\\n'+
                ('lab\\tdevice\\n' if connected else '')+'"; fi\n')
            adb.chmod(0o755)
            args = ['--adb', str(adb), '--work', tmp]+(['--dedicated-test-profile'] if flag else [])
            with redirect_stdout(io.StringIO()) as output:
                if partial:
                    with patch.object(c.Runner, 'run'), patch.object(c.Runner, 'close'), patch.object(c.Runner, 'diagnostics'):
                        code = c.main(args)
                else:
                    code = c.main(args)
            return code, json.loads(output.getvalue())

    def test_absent_device_is_pending(self):
        code, summary = self.fake_run(False)
        self.assertEqual(code, c.PENDING)
        self.assertFalse(summary['acceptanceComplete'])

    def test_connected_device_and_flag_without_apk_is_pending(self):
        code, summary = self.fake_run(True)
        self.assertEqual(code, c.PENDING)
        self.assertEqual(summary['passedChecks'], 0)
        self.assertIn('installed package is absent', summary['reason'])

    def test_partial_runner_return_is_pending(self):
        code, summary = self.fake_run(True, partial=True)
        self.assertEqual(code, c.PENDING)
        self.assertFalse(summary['acceptanceComplete'])

    def test_nonzero_package_lookup_is_pending_before_any_mutation(self):
        args = type('Args', (), {'package': 'org.redoubtbrowser', 'ui_timeout': 1, 'no_screenshots': True})()
        with tempfile.TemporaryDirectory() as tmp:
            adb = Mock()
            adb.run.return_value = type('Result', (), {'returncode': 1, 'stdout': ''})()
            runner = c.Runner(args, c.Evidence(tmp, 'run', 'test'), object(), adb)
            with self.assertRaises(c.Pending):
                runner.prerequisite()
            self.assertEqual(adb.run.call_count, 1)

    def test_fixture_serves_real_packaged_selector_script_and_records_cookie_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = c.Fixture('run', c.Evidence(tmp, 'run', 'test'))
            try:
                case_id = fixture.case('cookiebot')
                page = urllib.request.urlopen(fixture.url(case_id), timeout=3).read().decode()
                self.assertIn('CybotCookiebotDialogBodyButtonDecline', page)
                self.assertIn('<script>\nconst config', page)
                meta = {'run': 'run', 'caseId': case_id, 'documentId': 'doc', 'origin': fixture.origin,
                        'url': fixture.url(case_id), 'action': 'reject'}
                request = urllib.request.Request(fixture.origin+'/action', json.dumps(meta).encode(),
                    {'Content-Type': 'application/json', 'Cookie': fixture.cases[case_id]['cookieName']+'=reject; unrelated=secret'})
                self.assertTrue(json.load(urllib.request.urlopen(request, timeout=3))['ok'])
                self.assertEqual(fixture.requests[-1]['requestCookie'], 'reject')
                self.assertNotIn('secret', json.dumps(fixture.requests))
                meta['origin'] = 'https://foreign.example'
                request = urllib.request.Request(fixture.origin+'/register', json.dumps(meta).encode())
                with self.assertRaises(urllib.error.HTTPError) as refused:
                    urllib.request.urlopen(request, timeout=3)
                refused.exception.close()
            finally:
                fixture.close()

    def test_served_javascript_and_observers_parse(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required to check actual fixture source')
        bodies = [c.FIXTURE_JS]+['function observation(){\n'+body+'\n}' for body in
                               [c.PREFS_JS, c.INVENTORY_JS, c.STATE_JS, c.DOMAIN_JS, c.COOKIE_JAR_JS, c.CONTROLLED_ORIGIN_JS]]
        for body in bodies:
            checked = subprocess.run([node, '--check'], input=body, text=True, capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_no_policy_rules_or_permission_writes_exist(self):
        source = (ROOT/'scripts/android-cookie-banner-smoke.py').read_text()
        for forbidden in ['setBoolPref', 'setIntPref', 'setStringPref', 'clearUserPref', 'setDomainPref(',
                          'resetRules(', 'insertRule(', 'removeRule(', 'setCookieBannerMode', 'push_debug_config',
                          'removeAllExecutedRecords', 'markSiteExecuted(']:
            self.assertNotIn(forbidden, source)
        for privileged in [c.PREFS_JS, c.INVENTORY_JS, c.STATE_JS, c.DOMAIN_JS, c.COOKIE_JAR_JS, c.CONTROLLED_ORIGIN_JS]:
            self.assertNotIn('document.cookie=', privileged)
            self.assertNotIn('.click(', privileged)
        calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(call.func, ast.Attribute) and call.func.attr in {'install', 'wipe'} for call in calls))


if __name__ == '__main__':
    unittest.main(verbosity=2)
