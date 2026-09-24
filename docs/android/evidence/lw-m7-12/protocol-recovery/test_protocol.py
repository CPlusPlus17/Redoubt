#!/usr/bin/env python3
"""Actual harness functions against source-declared Marionette response frames.

No device is used. LW_PROTOCOL_TEST_ROOT selects retained before bytes for the
negative replay; the default tests the current repository scripts.
"""
import importlib.util
import json
import os
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(os.environ.get('LW_PROTOCOL_TEST_ROOT', Path(__file__).resolve().parents[5]))
raw = (ROOT / 'scripts/android-smoke.sh').read_text()
embedded = raw.split("<<'PYDRIVEREOF'\n", 1)[1].split('\nPYDRIVEREOF', 1)[0]
h = types.ModuleType('smoke_protocol_test')
exec(compile(embedded, 'actual embedded smoke driver', 'exec'), h.__dict__)
spec = importlib.util.spec_from_file_location('graphics_protocol_test', ROOT / 'scripts/android-graphics-smoke.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class WireSocket:
    """A framed transport peer; its command bodies follow retained server source."""
    def __init__(self, handler):
        self.handler, self.buffer, self.commands = handler, b'', []

    def sendall(self, packet):
        size, raw = packet.split(b':', 1)
        assert int(size) == len(raw)
        kind, number, name, args = json.loads(raw)
        assert kind == 0
        self.commands.append((name, args))
        value = self.handler(name, args)
        # server.sys.mjs lists GetWindowHandles as a no-value response.
        body = value if name == 'WebDriver:GetWindowHandles' else {'value': value}
        raw = json.dumps([1, number, None, body]).encode()
        self.buffer += str(len(raw)).encode() + b':' + raw

    def recv(self, size):
        # Split frames too, so the actual framing/command decoder participates.
        result, self.buffer = self.buffer[:7], self.buffer[7:]
        return result


def session(handler):
    result = h.Marionette.__new__(h.Marionette)
    result.sock, result.buf, result.msgid = WireSocket(handler), b'', 0
    return result


URL = 'https://fixture.invalid/probe?run=one'
READY = {'url': URL, 'uri': URL, 'ready': 'complete'}


class ScriptAndReadinessTests(unittest.TestCase):
    def test_sync_and_async_values_keep_exact_shapes(self):
        for value in [None, False, True, 7, 'text', [], ['window'], {'ready': 'complete'}, {'value': 'literal'}]:
            for method in ['script', 'async_script']:
                with self.subTest(value=value, method=method):
                    m = session(lambda name, args: value)
                    self.assertEqual(getattr(m, method)('return arguments[0]', [value]), value)

    def test_null_actor_result_then_complete_document(self):
        values = iter([None, READY])
        m = session(lambda name, args: next(values) if name == 'WebDriver:ExecuteScript' else None)
        with patch.object(h.time, 'sleep'):
            self.assertEqual(h.wait_for_initial_document(m, URL), READY)
        self.assertEqual(sum(name == 'WebDriver:ExecuteScript' for name, _ in m.sock.commands), 2)

    def test_repeated_null_exhausts_existing_budget_and_reports_null(self):
        m = session(lambda name, args: None)
        with patch.object(h.time, 'sleep'), self.assertRaisesRegex(h.HarnessError, 'None'):
            h.wait_for_initial_document(m, URL)
        self.assertEqual(sum(name == 'WebDriver:ExecuteScript' for name, _ in m.sock.commands), 60)

    def test_complete_only_after_all_three_document_facts_match(self):
        values = iter([None, {**READY, 'url': URL + '-stale'},
                       {**READY, 'uri': 'about:neterror'},
                       {**READY, 'ready': 'loading'}, READY])
        m = Mock(script=lambda _: next(values))
        with patch.object(h.time, 'sleep'):
            self.assertEqual(h.wait_for_initial_document(m, URL), READY)

    def test_wrong_uri_never_becomes_success_after_null(self):
        m = Mock(script=Mock(side_effect=[None] + [{**READY, 'uri': 'about:neterror'}] * 59))
        with patch.object(h.time, 'sleep'), self.assertRaises(h.HarnessError):
            h.wait_for_initial_document(m, URL)
        self.assertEqual(m.script.call_count, 60)

    def test_invalid_snapshot_types_fail_immediately(self):
        for value in [[], False, 3, 'complete']:
            m = Mock(script=Mock(return_value=value))
            with self.subTest(value=value), self.assertRaisesRegex(h.HarnessError, 'invalid snapshot'):
                h.wait_for_initial_document(m, URL)
            self.assertEqual(m.script.call_count, 1)

    def test_readonly_unload_retries_but_other_script_errors_propagate(self):
        unloaded = h.MarionetteError('WebDriver:ExecuteScript',
                                     {'error': 'javascript error', 'message': 'Document was unloaded'})
        m = Mock(script=Mock(side_effect=[unloaded, READY]))
        with patch.object(h.time, 'sleep'):
            self.assertEqual(h.wait_for_initial_document(m, URL), READY)
        m.script.side_effect = h.MarionetteError('WebDriver:ExecuteScript',
                                               {'error': 'javascript error', 'message': 'ReferenceError'})
        with self.assertRaises(h.MarionetteError):
            h.wait_for_initial_document(m, URL)


class WindowHandlesTests(unittest.TestCase):
    def test_handles_raw_list_matches_server_wire_contract(self):
        for value in [[], ['window-a'], ['window-a', 'window-b']]:
            with self.subTest(value=value):
                self.assertEqual(g.window_handles(session(lambda name, args: value)), value)

    def test_malformed_or_wrapped_handles_fail_closed(self):
        for value in [None, {'value': ['window']}, 'window', [None], [1], [''], ['a', 'a'], [['a']]]:
            with self.subTest(value=value), self.assertRaises(g.Failure):
                g.window_handles(session(lambda name, args: value))

    def runner(self, handler):
        runner = g.Runner.__new__(g.Runner)
        runner.marionette = session(handler)
        runner.protocol = h
        runner.evidence = types.SimpleNamespace(data={'run': 'one'})
        return runner

    def test_browser_document_uses_raw_handles_and_exact_active_private_document(self):
        def handler(name, args):
            if name == 'WebDriver:GetWindowHandles':
                return ['window']
            if name == 'WebDriver:ExecuteScript':
                if args['script'] == g.WINDOW_JS:
                    return {'active': True, 'private': False}
                return {'ready': 'complete', 'document': {'url': URL, 'run': 'one'}, 'frame': None}
        runner = self.runner(handler)
        self.assertEqual(runner.browser_document(URL, False)['document']['url'], URL)
        switches = [args for name, args in runner.marionette.sock.commands if name == 'WebDriver:SwitchToWindow']
        self.assertEqual(switches, [{'handle': 'window', 'focus': False}] * 2)

    def test_browser_document_rejects_different_run(self):
        def handler(name, args):
            if name == 'WebDriver:GetWindowHandles':
                return ['window']
            if name == 'WebDriver:ExecuteScript':
                if args['script'] == g.WINDOW_JS:
                    return {'active': True, 'private': False}
                return {'ready': 'complete', 'document': {'url': URL, 'run': 'other'}}
        with self.assertRaisesRegex(g.Failure, 'Wrong fixture run'):
            self.runner(handler).browser_document(URL, False)

    def test_private_close_uses_raw_handles_and_waits_for_zero_private_contexts(self):
        counts = iter([1, 0])
        def handler(name, args):
            if name == 'WebDriver:GetWindowHandles':
                return ['normal-window']
            if name == 'WebDriver:ExecuteScript':
                return next(counts)
        runner = self.runner(handler)
        runner.private, runner.ui = True, Mock()
        with patch.object(g.time, 'sleep'):
            runner.close_private()
        self.assertFalse(runner.private)
        runner.ui.tab_menu.assert_called_once_with('Close tab')
        self.assertEqual(sum(name == 'WebDriver:GetWindowHandles' for name, _ in runner.marionette.sock.commands), 2)

    def test_private_close_invalid_handles_cannot_claim_teardown(self):
        runner = self.runner(lambda name, args: {'value': ['window']})
        runner.private, runner.ui = True, Mock()
        with self.assertRaises(g.Failure):
            runner.close_private()
        self.assertTrue(runner.private)


if __name__ == '__main__':
    unittest.main()
