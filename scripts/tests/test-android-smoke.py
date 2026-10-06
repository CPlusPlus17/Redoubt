#!/usr/bin/env python3
"""Regression tests for capture evidence that handshake-only parsing missed."""
from pathlib import Path
import json
import socket
import struct
import io
import os
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'scripts/android-smoke.sh').read_text()
source = source.split("<<'PYDRIVEREOF'\n", 1)[1].split('\nPYDRIVEREOF', 1)[0]
harness = types.ModuleType('android_smoke_tests')
exec(compile(source, 'android-smoke.sh embedded Python', 'exec'), harness.__dict__)


def hello(host):
    encoded = host.encode('ascii')
    names = b'\0' + struct.pack('>H', len(encoded)) + encoded
    sni = struct.pack('>H', len(names)) + names
    extensions = b'\0\0' + struct.pack('>H', len(sni)) + sni
    body = b'\3\3' + bytes(32) + b'\0\0\2\x13\1\1\0'
    body += struct.pack('>H', len(extensions)) + extensions
    handshake = b'\1' + len(body).to_bytes(3, 'big') + body
    return b'\x16\3\1' + struct.pack('>H', len(handshake)) + handshake


def tcp(payload=b'', source_port=40000, flags=0x18, ipv6=False, hop_by_hop=False):
    transport = struct.pack('>HHII', source_port, 443, 1, 1)
    transport += bytes([0x50, flags]) + bytes(6) + payload
    if ipv6:
        source, dest = '2001:db8::15', '2001:db8::91'
        if hop_by_hop:
            transport = bytes([6, 0]) + bytes(6) + transport
        ip = struct.pack('>IHBB', 6 << 28, len(transport), 0 if hop_by_hop else 6, 64)
        ip += socket.inet_pton(socket.AF_INET6, source) + socket.inet_pton(socket.AF_INET6, dest)
        ethertype = 0x86dd
    else:
        ip = bytes([0x45, 0]) + struct.pack('>H', 20 + len(transport))
        ip += bytes(4) + bytes([64, 6]) + bytes(2)
        ip += socket.inet_aton('10.0.2.15') + socket.inet_aton('151.101.1.91')
        ethertype = 0x0800
    return bytes(12) + struct.pack('>H', ethertype) + ip + transport


class PayloadEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'capture.pcap'
        self.path.write_bytes(struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))

    def tearDown(self):
        self.temp.cleanup()

    def append(self, frame):
        with self.path.open('ab') as f:
            f.write(struct.pack('<IIII', 1, 0, len(frame), len(frame)) + frame)
        return self.path.stat().st_size

    def read(self, start, **kwargs):
        return harness.pcap_payloads(str(self.path), start, {'10.0.2.15', '2001:db8::15'}, **kwargs)

    def test_reused_tls_suggestion_is_visible_without_a_handshake(self):
        start = self.append(tcp(hello('ac.duckduckgo.com')))
        self.append(tcp(b'\x17\3\3\0\5query'))
        self.assertEqual(list(harness.pcap_events(str(self.path), start)), [])
        rows = self.read(start)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['host'], 'ac.duckduckgo.com')
        self.assertGreater(rows[0]['bytes'], 0)
        self.assertFalse(rows[0]['background'])

    def test_security_exception_does_not_allow_another_flow_on_shared_cdn_ip(self):
        self.append(tcp(hello('firefox.settings.services.mozilla.com')))
        start = self.path.stat().st_size
        self.append(tcp(b'blocklist', source_port=40000))
        self.append(tcp(b'unknown query', source_port=40001))
        rows = self.read(start)
        self.assertTrue(rows[0]['background'])
        self.assertFalse(rows[1]['background'])
        self.assertIsNone(rows[1]['host'])

    def test_truncated_sni_cannot_impersonate_an_allowed_hostname_prefix(self):
        allowed = 'firefox.settings.services.mozilla.com'
        full = hello(allowed + '.unexpected.invalid')
        truncated = full[:full.index(allowed.encode()) + len(allowed)]
        self.assertIsNone(harness._tls_sni(truncated))
        self.append(tcp(truncated))
        row = self.read(24)[0]
        self.assertIsNone(row['host'])
        self.assertFalse(row['background'])

    def test_complete_sni_survives_fragmentation_of_later_extensions(self):
        host = 'noai.duckduckgo.com'
        message = bytearray(hello(host))
        # Declare a later, unrelated extension which arrives in a later TCP
        # segment. The SNI itself is completely present in this segment.
        extension_offset = 50
        message[3:5] = struct.pack('>H', len(message) - 5 + 100)
        message[6:9] = (len(message) - 9 + 100).to_bytes(3, 'big')
        size = struct.unpack('>H', message[extension_offset:extension_offset + 2])[0]
        message[extension_offset:extension_offset + 2] = struct.pack('>H', size + 100)
        self.assertEqual(harness._tls_sni(message), host)

    def test_reused_connection_tuple_does_not_inherit_prior_host(self):
        self.append(tcp(hello('firefox.settings.services.mozilla.com')))
        start = self.append(tcp(flags=2))
        self.append(tcp(b'new unknown connection'))
        rows = self.read(start)
        self.assertFalse(rows[0]['background'])
        self.assertIsNone(rows[0]['host'])

    def test_ipv6_payloads_are_not_silently_ignored(self):
        start = self.append(tcp(hello('ac.duckduckgo.com'), ipv6=True))
        self.append(tcp(b'query', ipv6=True))
        self.assertEqual(self.read(start)[0]['host'], 'ac.duckduckgo.com')
        events = list(harness.pcap_events(str(self.path)))
        self.assertEqual(events[0][1:3], ('sni', 'ac.duckduckgo.com'))

    def test_ack_only_packets_cannot_satisfy_search_control(self):
        start = self.append(tcp(hello('noai.duckduckgo.com')))
        self.append(tcp())
        self.assertEqual(self.read(start), [])

    def test_vlan_frames_are_inconclusive_instead_of_invisible(self):
        frame = tcp(b'query')
        self.append(frame[:12] + b'\x81\x00\0\1' + frame[12:])
        with self.assertRaises(harness.HarnessError):
            self.read(24)

    def test_public_udp_on_an_os_port_is_not_automatically_background(self):
        frame = tcp(b'query')
        ip = bytearray(frame[14:34])
        ip[9] = 17
        payload = b'query'
        udp = struct.pack('>HHHH', 40000, 123, 8 + len(payload), 0) + payload
        ip[2:4] = struct.pack('>H', 20 + len(udp))
        self.append(frame[:14] + ip + udp)
        self.assertFalse(self.read(24)[0]['background'])

    def test_partial_snapshot_preserves_packet_boundaries(self):
        start = self.append(tcp(hello('noai.duckduckgo.com')))
        end = self.append(tcp(b'query'))
        with self.assertRaises(harness.HarnessError):
            self.read(start, end_offset=end - 1)
        self.assertEqual(self.read(start, end_offset=end)[0]['bytes'], 5)
        self.assertEqual(self.read(end - 1, end_offset=end)[0]['bytes'], 5)

    def test_partial_header_cannot_silently_pass_the_typing_window(self):
        start = self.append(tcp(hello('noai.duckduckgo.com')))
        self.append(tcp(b'query'))
        with self.assertRaises(harness.HarnessError):
            self.read(start, end_offset=start + 5)

    def test_event_reader_starts_inside_a_record_without_losing_its_hostname(self):
        start = self.path.stat().st_size
        self.append(tcp(hello('ads.mozilla.org')))
        events = list(harness.pcap_events(str(self.path), start + 20))
        self.assertEqual(events[0][1:3], ('sni', 'ads.mozilla.org'))

    def test_malformed_or_partial_event_capture_is_inconclusive(self):
        self.path.write_bytes(b'not a capture')
        with self.assertRaises(harness.HarnessError):
            list(harness.pcap_events(str(self.path)))

    def test_partial_packet_tail_cannot_hide_a_host_event(self):
        self.append(tcp(hello('ads.mozilla.org')))
        self.path.write_bytes(self.path.read_bytes()[:-1])
        with self.assertRaises(harness.HarnessError):
            list(harness.pcap_events(str(self.path)))

    def test_ipv6_hop_by_hop_options_preserve_transport(self):
        self.append(tcp(hello('ac.duckduckgo.com'), ipv6=True, hop_by_hop=True))
        self.assertEqual(self.read(24)[0]['host'], 'ac.duckduckgo.com')

    def test_new_interface_and_retired_addresses_are_retained(self):
        class Device:
            ipv4 = 'radio0 inet 10.0.2.15/24'
            def shell(self, command, **kwargs):
                return self.ipv4 if '-4' in command else ''
        device = Device()
        app = harness.App(device, 'org.redoubtbrowser', self.temp.name)
        self.assertEqual(app.guest_ips(), {'10.0.2.15'})
        device.ipv4 = 'wlan0 inet 10.0.2.16/24'
        self.assertEqual(app.guest_ips(), {'10.0.2.15', '10.0.2.16'})


class AboutConfigProbeTests(unittest.TestCase):
    class Session:
        def __init__(self, failures):
            self.failures = list(failures)
            self.calls = 0

        def async_script(self, script, args=None):
            self.calls += 1
            if self.failures:
                raise harness.MarionetteError("WebDriver:ExecuteAsyncScript",
                                             {"error": "javascript error",
                                              "message": self.failures.pop(0)})
            return {"url": "about:config", "rows": 30}

    def test_transient_document_replacement_retries_read_only_probe(self):
        error = "Document was unloaded"
        session = self.Session([error])
        with patch.object(harness.time, "sleep"):
            page = harness.probe_aboutconfig_page(session)
        self.assertEqual(session.calls, 2)
        self.assertEqual(page["documentUnloadRetries"],
                         ["WebDriver:ExecuteAsyncScript -> javascript error: " + error])
        self.assertEqual(page["rows"], 30)

    def test_document_replacement_retry_is_bounded(self):
        error = "Document was unloaded"
        session = self.Session([error] * 3)
        with patch.object(harness.time, "sleep"), self.assertRaises(harness.MarionetteError):
            harness.probe_aboutconfig_page(session)
        self.assertEqual(session.calls, 3)

    def test_other_script_errors_are_not_retried(self):
        session = self.Session(["ReferenceError: missing"])
        with self.assertRaises(harness.MarionetteError):
            harness.probe_aboutconfig_page(session)
        self.assertEqual(session.calls, 1)

    def test_initial_navigation_must_reach_the_actual_complete_document(self):
        class Session:
            calls = 0
            def script(self, script):
                self.calls += 1
                return {"url": "http://fixture/", "uri": "http://fixture/",
                        "ready": "loading" if self.calls == 1 else "complete"}
        session = Session()
        with patch.object(harness.time, "sleep"):
            page = harness.wait_for_initial_document(session, "http://fixture/")
        self.assertEqual(session.calls, 2)
        self.assertEqual(page["ready"], "complete")

    def test_initial_neterror_document_cannot_satisfy_readiness(self):
        class Session:
            calls = 0
            def script(self, script):
                self.calls += 1
                return {"url": "http://fixture/", "uri": "about:neterror", "ready": "complete"}
        session = Session()
        with patch.object(harness.time, "sleep"), self.assertRaises(harness.HarnessError):
            harness.wait_for_initial_document(session, "http://fixture/")
        self.assertEqual(session.calls, 60)


class ScreenshotEvidenceTests(unittest.TestCase):
    def png(self, method, channels):
        def chunk(kind, data):
            return (struct.pack('>I', len(data)) + kind + data +
                    struct.pack('>I', zlib.crc32(kind + data)))
        width, height = 3, 3
        rows = [bytes((x * 17 + y * 31) % 256 for x in range(width * channels))
                for y in range(height)]
        encoded = bytearray()
        for y, row in enumerate(rows):
            encoded.append(method)
            previous = rows[y - 1] if y else bytes(len(row))
            for x, value in enumerate(row):
                left = row[x - channels] if x >= channels else 0
                above = previous[x]
                diagonal = previous[x - channels] if x >= channels else 0
                if method == 0: prediction = 0
                elif method == 1: prediction = left
                elif method == 2: prediction = above
                elif method == 3: prediction = (left + above) // 2
                else:
                    estimate = left + above - diagonal
                    prediction = min((left, above, diagonal), key=lambda v: abs(estimate - v))
                encoded.append((value - prediction) % 256)
        header = struct.pack('>IIBBBBB', width, height, 8, 6 if channels == 4 else 2, 0, 0, 0)
        png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) +
               chunk(b'IDAT', zlib.compress(encoded)) + chunk(b'IEND', b''))
        expected = list(rows[1][channels:channels * 2])
        return png, expected if channels == 4 else expected + [255]

    def test_compositor_pixel_all_standard_rgb_and_rgba_filters(self):
        for channels in (3, 4):
            for method in range(5):
                with self.subTest(channels=channels, filter=method):
                    image, expected = self.png(method, channels)
                    self.assertEqual(harness.png_center_pixel(image), expected)

    def test_non_image_cannot_report_a_rendered_pixel(self):
        with self.assertRaises(harness.HarnessError):
            harness.png_center_pixel(b'not an image')


class UboBehaviorGateTests(unittest.TestCase):
    def evidence(self, blocked=True):
        token = "first-test"
        page = {"ready":"complete", "probe":{"token":token, "allowed":True, "blocked":not blocked}}
        paths = ["/ubo-probe", harness.UBO_ALLOWED_PATH]
        if not blocked:
            paths.append(harness.UBO_BLOCKED_PATH)
        requests = [(1.0, "http", path + "?token=" + token) for path in paths]
        return page, requests, token

    def test_block_and_disable_control_require_opposite_server_results(self):
        for blocked in (True, False):
            data = self.evidence(blocked)
            self.assertTrue(harness.grade_ubo_navigation(*data, blocked)[0])
            self.assertFalse(harness.grade_ubo_navigation(*data, not blocked)[0])

    def test_blocked_dom_without_server_observation_of_allowed_control_fails(self):
        page, requests, token = self.evidence()
        self.assertFalse(harness.grade_ubo_navigation(page, requests[:1], token, True)[0])

    def test_request_leaked_even_if_script_did_not_execute_fails(self):
        page, requests, token = self.evidence()
        requests.append((1.0, "http", harness.UBO_BLOCKED_PATH + "?token=" + token))
        self.assertFalse(harness.grade_ubo_navigation(page, requests, token, True)[0])

    def test_incomplete_document_cannot_claim_scripts_were_blocked(self):
        page, requests, token = self.evidence()
        page["ready"] = "loading"
        self.assertFalse(harness.grade_ubo_navigation(page, requests, token, True)[0])

    def test_previous_navigation_cannot_supply_current_control(self):
        page, requests, token = self.evidence()
        self.assertFalse(harness.grade_ubo_navigation(page, requests, "second-test", True)[0])

    def test_missing_page_or_script_marker_fails(self):
        page, requests, token = self.evidence()
        self.assertFalse(harness.grade_ubo_navigation(page, requests[1:], token, True)[0])
        page["probe"]["allowed"] = False
        self.assertFalse(harness.grade_ubo_navigation(page, requests, token, True)[0])

    def test_scriptless_page_cannot_be_a_passing_negative_control(self):
        page, requests, token = self.evidence(False)
        page["probe"]["blocked"] = False
        self.assertFalse(harness.grade_ubo_navigation(page, requests, token, False)[0])

    def test_both_scripts_are_parser_inserted_in_first_response(self):
        body, kind = harness.ubo_probe_response("/ubo-probe?token=first-test")
        self.assertIn("text/html", kind)
        self.assertIn((harness.UBO_BLOCKED_PATH + "?token=first-test").encode(), body)
        self.assertIn((harness.UBO_ALLOWED_PATH + "?token=first-test").encode(), body)
        self.assertNotIn(b"setTimeout", body)
        self.assertNotIn(b"fetch(", body)

    def test_fixture_rejects_html_and_javascript_in_token(self):
        for token in ("%22%3E%3Cscript%3E", "", "foo%26bar"):
            self.assertIsNone(harness.ubo_probe_response("/ubo-probe?token=" + token))


class AppInstallStateTests(unittest.TestCase):
    def test_failed_profile_clear_cannot_claim_a_fresh_install(self):
        class Device:
            def run(self, *args, **kwargs):
                return types.SimpleNamespace(stdout="Failed", stderr="")
        with tempfile.TemporaryDirectory() as work:
            app = harness.App(Device(), "org.redoubtbrowser", work)
            with self.assertRaises(harness.HarnessError):
                app.wipe()

    def test_keep_state_never_uninstalls_after_signing_mismatch(self):
        class Device:
            calls = []
            def run(self, *args, **kwargs):
                self.calls.append(args)
                return types.SimpleNamespace(stdout="", stderr="INSTALL_FAILED_UPDATE_INCOMPATIBLE")
        device = Device()
        with tempfile.TemporaryDirectory() as work:
            apk = Path(work) / "candidate.apk"
            apk.write_bytes(b"fixture")
            app = harness.App(device, "org.redoubtbrowser", work)
            with self.assertRaises(harness.HarnessError):
                app.install(str(apk), preserve_state=True)
        self.assertEqual(len(device.calls), 1)
        self.assertEqual(device.calls[0][0], "install")


class HttpsOnlyBehaviorGateTests(unittest.TestCase):
    def test_requires_active_default_and_real_visible_exception_control(self):
        prefs = {"enabled":True, "locked":False}
        info = {"ready":"complete", "marker":None, "continueVisible":True, "canAddException":True,
                "uri":"resource://android/assets/low_and_medium_risk_error_pages.html?showContinueHttp=true"}
        self.assertTrue(harness.grade_https_interstitial(prefs, info))
        for key, value in (("continueVisible", False), ("canAddException", False),
                           ("ready", "loading"), ("marker", "lw-smoke-page-ok"),
                           ("uri", "https://fixture/?showContinueHttp=true"),
                           ("uri", "resource://android/assets/low_and_medium_risk_error_pages.html?showContinueHttp=false")):
            with self.subTest(key=key):
                self.assertFalse(harness.grade_https_interstitial(prefs, {**info, key:value}))
        for key, value in (("enabled", False), ("locked", True)):
            with self.subTest(key=key):
                self.assertFalse(harness.grade_https_interstitial({**prefs, key:value}, info))

    def test_native_error_page_can_be_interactive_before_load_event_finishes(self):
        info = {"ready":"interactive", "marker":None, "continueVisible":True, "canAddException":True,
                "uri":"resource://android/assets/low_and_medium_risk_error_pages.html?showContinueHttp=true"}
        self.assertTrue(harness.grade_https_interstitial({"enabled":True, "locked":False}, info))

    def test_missing_error_page_evidence_cannot_pass_from_pref_alone(self):
        self.assertFalse(harness.grade_https_interstitial({"enabled":True, "locked":False}, {}))


class GraphicsAcceptanceIntegrationTests(unittest.TestCase):
    def report(self):
        return {'status': 'PASS', 'acceptanceComplete': True, 'suite': 'full',
                'transportConfig': {'transportOnly': True},
                'installed': {'apk': [{'sha256': 'actual-apk'}]},
                'checks': [{'name': name, 'status': 'PASS'} for name in (
                    'core-real-ui-consent-and-revoke',
                    'session-exceptions-expire-on-process-restart',
                    'remembered-exceptions-survive-process-restart',
                    'private-choices-isolated-and-cleared-on-last-private-close',
                    'frame-origin-port-and-revoke-isolation')]}

    def test_complete_bound_graphics_acceptance_passes(self):
        self.assertTrue(harness.grade_graphics_acceptance(0, self.report(), 'actual-apk'))

    def test_pending_subset_or_nonzero_exit_never_passes_baseline(self):
        for code in (1, 2, 3):
            self.assertFalse(harness.grade_graphics_acceptance(code, self.report(), 'actual-apk'))
        for key, value in (('status', 'PENDING'), ('suite', 'core-only'), ('acceptanceComplete', False)):
            report = self.report()
            report[key] = value
            self.assertFalse(harness.grade_graphics_acceptance(0, report, 'actual-apk'))

    def test_missing_lifetime_or_failed_frame_cannot_pass(self):
        report = self.report()
        report['checks'].pop()
        self.assertFalse(harness.grade_graphics_acceptance(0, report, 'actual-apk'))
        report = self.report()
        report['checks'][-1]['status'] = 'FAIL'
        self.assertFalse(harness.grade_graphics_acceptance(0, report, 'actual-apk'))

    def test_wrong_apk_or_injected_config_cannot_pass(self):
        self.assertFalse(harness.grade_graphics_acceptance(0, self.report(), 'other-apk'))
        report = self.report()
        report['transportConfig']['transportOnly'] = False
        self.assertFalse(harness.grade_graphics_acceptance(0, report, 'actual-apk'))


class InterruptedEvidenceTests(unittest.TestCase):
    def test_failed_or_interrupted_boot_stops_only_the_created_emulator(self):
        with tempfile.TemporaryDirectory() as work:
            apk = Path(work) / 'candidate.apk'
            apk.write_bytes(b'not installed: boot fails first')
            for error in (harness.HarnessError('controlled boot timeout'), KeyboardInterrupt()):
                with self.subTest(error=type(error).__name__), \
                     patch.object(harness, 'find_sdk', return_value='/fake-sdk'), \
                     patch.object(harness, 'find_adb', return_value='/fake-adb'), \
                     patch.object(harness, 'find_apk', return_value=str(apk)), \
                     patch.object(harness, 'apk_package', return_value='org.redoubtbrowser'), \
                     patch.object(harness, 'Adb') as adb, \
                     patch.object(harness, 'Emulator') as emulator, \
                     patch.dict(harness.os.environ, {'LW_SMOKE_EXTRA_PREFS': ''}):
                    emulator.return_value.boot.side_effect = error
                    with self.assertRaises(type(error)):
                        harness.main(['--emulator', '--keep-emulator', '--work', work])
                    emulator.return_value.stop.assert_called_once_with()
                    adb.return_value.run.assert_not_called()

    def test_socket_timeout_is_an_automation_failure_and_closes_transport(self):
        local, remote = socket.socketpair()
        try:
            local.settimeout(0.01)
            session = harness.Marionette.__new__(harness.Marionette)
            session.sock, session.buf, session.msgid = local, b'', 0
            with self.assertRaisesRegex(harness.HarnessError, 'transport failed'):
                session.cmd('WebDriver:Navigate', {'url': 'http://fixture/'})
            self.assertEqual(local.fileno(), -1)
        finally:
            local.close()
            remote.close()

    def test_later_connection_failure_preserves_earlier_failed_probe(self):
        with tempfile.TemporaryDirectory() as work:
            args = types.SimpleNamespace(json=str(Path(work) / 'result.json'))
            res = harness.Results()
            res.artifact = {'sha256': 'candidate-input'}
            res.checkpoint = lambda: harness.write_results(res, args, work, 'running')
            res.add('restart-control', False, 'unexpected document', {'url': 'about:blank'})
            checkpoint = json.loads(Path(args.json).read_text())
            self.assertEqual(checkpoint['status'], 'running')
            self.assertFalse(checkpoint['checks'][0]['ok'])
            harness.write_results(res, args, work, 'interrupted', 'connection closed')
            result = json.loads(Path(args.json).read_text())
            self.assertEqual(result['checks'], checkpoint['checks'])
            self.assertEqual(result['artifact'], res.artifact)
            self.assertEqual(result['status'], 'interrupted')
            self.assertEqual(result['error'], 'connection closed')



class LauncherStartGateTests(unittest.TestCase):
    READY = ('10-02 06:00:01.000  100  100 I LibreWolfUboPreinstaller: '
             + harness.UBO_READY_LOG)
    FAILED = ('10-02 06:00:31.000  100  100 E LibreWolfUboPreinstaller: '
              + harness.UBO_FAILED_LOG + '; browsing remains paused')
    DIALOG = '<node text="uBlock Origin setup failed" bounds="[0,0][1,1]" />'

    def test_ready_without_dialog_passes(self):
        result = harness.grade_launcher_phase('<hierarchy/>', self.READY, True)
        self.assertTrue(result['ok'], result)

    def test_failure_dialog_fails_even_with_an_earlier_ready_line(self):
        result = harness.grade_launcher_phase(self.DIALOG, self.READY, True)
        self.assertFalse(result['ok'])
        self.assertTrue(result['dialog'])

    def test_logged_failure_fails_without_a_visible_dialog(self):
        result = harness.grade_launcher_phase('<hierarchy/>', self.READY + '\n' + self.FAILED, True)
        self.assertFalse(result['ok'])

    def test_silence_is_not_readiness(self):
        result = harness.grade_launcher_phase('<hierarchy/>', '', True)
        self.assertFalse(result['ok'])
        self.assertIn('no readiness line was logged', result['problems'])

    def test_a_dead_app_fails(self):
        self.assertFalse(harness.grade_launcher_phase('<hierarchy/>', self.READY, False)['ok'])

    def test_unready_or_disabled_ready_state_is_not_the_positive_signal(self):
        line = 'I LibreWolfUboPreinstaller: uBlock Origin startup ready: Ready(installed=false, enabled=false)'
        self.assertFalse(harness.grade_launcher_phase('<hierarchy/>', line, True)['ok'])

    def test_launcher_component_comes_from_the_package_manager(self):
        adb = types.SimpleNamespace(shell=lambda cmd, timeout=None: 'priority=0\norg.example/.App\n')
        self.assertEqual(harness.launcher_component(adb, 'org.example'), 'org.example/.App')
        adb = types.SimpleNamespace(shell=lambda cmd, timeout=None: 'No activity found\n')
        with self.assertRaises(harness.HarnessError):
            harness.launcher_component(adb, 'org.example')

    def test_launcher_check_refuses_kept_state(self):
        with self.assertRaises(harness.HarnessError):
            harness.main(['--check-launcher-start', '--keep-state'])


class UboUserDisableGateTests(unittest.TestCase):
    """LW-M7-44: --check-ubo-user-disable grading."""
    PREFIX = '10-06 06:00:01.000  100  100 I LibreWolfUboPreinstaller: '
    USER = PREFIX + harness.UBO_USER_DISABLED_LOG
    READY_OFF = PREFIX + harness.UBO_READY_DISABLED_LOG
    READY_ON = PREFIX + harness.UBO_READY_LOG
    FAILED = PREFIX.replace(' I ', ' E ') + harness.UBO_FAILED_LOG + '; browsing remains paused'
    DIALOG = '<node text="uBlock Origin setup failed" bounds="[0,0][1,1]" />'
    grade = staticmethod(harness.grade_ubo_user_disable_phase)

    def test_user_disable_inside_the_wait_continues(self):
        result = self.grade('user-disable', '<hierarchy/>', self.USER + '\n' + self.READY_OFF, True, True)
        self.assertTrue(result['ok'], result)

    def test_user_disable_that_shows_the_dialog_fails(self):
        result = self.grade('user-disable', self.DIALOG, self.FAILED, True, False)
        self.assertFalse(result['ok'])
        self.assertTrue(result['dialog'])
        self.assertIn('no user-disabled readiness line was logged', result['problems'])

    def test_user_disable_needs_the_held_page_to_load(self):
        result = self.grade('user-disable', '<hierarchy/>', self.USER + '\n' + self.READY_OFF, True, False)
        self.assertFalse(result['ok'])

    def test_a_missed_window_is_never_a_pass(self):
        for name in ('user-disable', 'reload-control'):
            result = self.grade(name, '<hierarchy/>', self.READY_ON + '\n' + self.READY_OFF, True, True)
            self.assertFalse(result['ok'])
            self.assertIn('window missed', result['problems'][0])

    def test_reload_control_must_fail_closed(self):
        result = self.grade('reload-control', self.DIALOG, self.FAILED, True, False)
        self.assertTrue(result['ok'], result)
        for xml, log, page_ok in (('<hierarchy/>', self.FAILED, False),
                                  (self.DIALOG, '', False),
                                  (self.DIALOG, self.FAILED, True),
                                  (self.DIALOG, self.FAILED + '\n' + self.USER, False)):
            self.assertFalse(self.grade('reload-control', xml, log, True, page_ok)['ok'])

    def test_a_dead_app_fails(self):
        self.assertFalse(self.grade('user-disable', '<hierarchy/>',
                                    self.USER + '\n' + self.READY_OFF, False, True)['ok'])

    def test_check_refuses_kept_state(self):
        with self.assertRaises(harness.HarnessError):
            harness.main(['--check-ubo-user-disable', '--keep-state'])


PKG = 'org.redoubtbrowser'
os.environ.setdefault('LW_SMOKE_REPO', str(ROOT))


def ubo_notice_xml():
    child = lambda name, cls, text, clickable: (
        '<node resource-id="%s:id/%s" class="%s" text="%s" package="%s" clickable="%s" '
        'checkable="false" enabled="true" bounds="[900,1790][944,1840]"/>' % (PKG, name, cls, text, PKG, clickable))
    g = harness._graphics_module()
    return ('<hierarchy><node class="android.widget.RelativeLayout" package="%s" enabled="true" '
            'bounds="[0,1400][1080,1900]">' % PKG
            + child('icon', 'android.widget.ImageView', '', 'false')
            + child('title', 'android.widget.TextView', g.UBO_ADDED_TITLE, 'false')
            + child('description', 'android.widget.TextView', g.UBO_ADDED_DESCRIPTION, 'false')
            + child('confirm_button', 'android.widget.Button', 'OK', 'true')
            + '</node></hierarchy>')


TOOLBAR = ('<hierarchy><node resource-id="ADDRESSBAR_URL_BOX" class="android.view.View" '
           'package="%s" bounds="[100,100][900,200]"/></hierarchy>' % PKG)


class FakeUiAdb:
    """uiautomator dumps served in order; the last one repeats."""
    def __init__(self, dumps):
        self.dumps, self.taps = list(dumps), []

    def shell(self, cmd, timeout=None):
        if cmd.startswith('input tap'):
            self.taps.append(cmd)
        if cmd.startswith('cat '):
            return self.dumps.pop(0) if len(self.dumps) > 1 else self.dumps[0]
        return ''


class FirstRunNoticeTests(unittest.TestCase):
    def setUp(self):
        sleeper = patch.object(harness.time, 'sleep', lambda _s: None)
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def test_notice_is_acknowledged_once_before_the_toolbar_is_used(self):
        adb = FakeUiAdb([ubo_notice_xml(), TOOLBAR, TOOLBAR])
        _xml, pt, acknowledged = harness.toolbar_ready(adb, PKG)
        self.assertEqual(pt, (500, 150))
        self.assertTrue(acknowledged)
        self.assertEqual(adb.taps, ['input tap 922 1815'])

    def test_clean_toolbar_needs_two_matching_dumps_and_no_tap(self):
        adb = FakeUiAdb([TOOLBAR, TOOLBAR])
        _xml, pt, acknowledged = harness.toolbar_ready(adb, PKG)
        self.assertEqual((pt, acknowledged, adb.taps), ((500, 150), False, []))

    def test_notice_arriving_after_a_clean_dump_is_still_acknowledged(self):
        adb = FakeUiAdb([TOOLBAR, ubo_notice_xml(), TOOLBAR, TOOLBAR])
        _xml, pt, acknowledged = harness.toolbar_ready(adb, PKG)
        self.assertTrue(acknowledged)
        self.assertEqual(len(adb.taps), 1)

    def test_notice_that_does_not_close_is_a_harness_error(self):
        adb = FakeUiAdb([ubo_notice_xml()])
        clock = iter(range(0, 10000, 5))
        with patch.object(harness.time, 'time', lambda: next(clock)):
            with self.assertRaises(harness.HarnessError):
                harness.toolbar_ready(adb, PKG)
        self.assertEqual(len(adb.taps), 1)

    def test_generic_ok_is_never_tapped(self):
        ok = ('<hierarchy><node resource-id="%s:id/confirm_button" class="android.widget.Button" '
              'text="OK" package="%s" bounds="[0,0][10,10]"/></hierarchy>' % (PKG, PKG))
        adb = FakeUiAdb([ok])
        clock = iter(range(0, 10000, 5))
        with patch.object(harness.time, 'time', lambda: next(clock)):
            _xml, pt, acknowledged = harness.toolbar_ready(adb, PKG)
        self.assertEqual((pt, acknowledged, adb.taps), (None, False, []))

    def test_check_search_and_no_suggest_use_the_shared_toolbar_wait(self):
        for check in (harness.check_search, harness.check_no_suggest):
            self.assertIn('toolbar_ready', check.__code__.co_names)
        self.assertIn('wait_post_launch_quiet', harness.check_no_suggest.__code__.co_names)


def ubo_apk(background):
    xpi = io.BytesIO()
    with zipfile.ZipFile(xpi, 'w') as z:
        z.writestr('js/background.js', background)
    apk = io.BytesIO()
    with zipfile.ZipFile(apk, 'w') as z:
        z.writestr('assets/extensions/ublock_origin.xpi', xpi.getvalue())
    apk.seek(0)
    return apk


class UboUpdateScheduleTests(unittest.TestCase):
    def test_schedule_is_read_from_the_bundled_xpi(self):
        apk = ubo_apk("const hiddenSettingsDefault = {\n    autoUpdateAssetFetchPeriod: 5,\n"
                      "    autoUpdateDelayAfterLaunch: 37,\n    autoUpdatePeriod: 1,\n};")
        self.assertEqual(harness.ubo_update_schedule(apk),
                         {'autoUpdateDelayAfterLaunch': 37, 'autoUpdateAssetFetchPeriod': 5})

    def test_missing_default_is_a_harness_error_not_a_guess(self):
        with self.assertRaises(harness.HarnessError):
            harness.ubo_update_schedule(ubo_apk("autoUpdateDelayAfterLaunch: 37,"))


class PostLaunchQuietTests(unittest.TestCase):
    SCHEDULE = {'autoUpdateDelayAfterLaunch': 37, 'autoUpdateAssetFetchPeriod': 5}

    def run_wait(self, traffic, timeout=300):
        """traffic: {second: [row, ...]} -- rows appear at that clock second."""
        state = {'now': 0.0, 'size': 0}

        def sleep(seconds):
            state['now'] += seconds
            state['size'] += 1

        def payloads(offset):
            return [row for second, rows in traffic.items()
                    if offset <= second < state['now'] for row in rows]

        result = harness.wait_post_launch_quiet(
            payloads, lambda: state['now'], 0, 0.0, self.SCHEDULE, timeout=timeout,
            poll=1.0, clock=lambda: state['now'], sleep=sleep)
        return result

    @staticmethod
    def row(host, background=False, nbytes=100):
        return {'host': host, 'dst': '192.0.2.1', 'bytes': nbytes, 'background': background}

    def test_no_traffic_still_waits_for_ubo_launch_timer(self):
        result = self.run_wait({})
        self.assertTrue(result['settled'])
        self.assertGreaterEqual(result['waited_s'], 37 + harness.UBO_STARTUP_ALLOWANCE_S)

    def test_gap_between_list_fetches_is_not_taken_for_the_end(self):
        fetches = {second: [self.row('ublockorigin.github.io')] for second in range(43, 120, 7)}
        result = self.run_wait(fetches)
        self.assertTrue(result['settled'])
        self.assertGreaterEqual(result['waited_s'], max(fetches) + result['quiet_s'])
        self.assertEqual(result['hosts_bytes'], {'ublockorigin.github.io': 100 * len(fetches)})

    def test_background_security_flows_do_not_hold_the_wait(self):
        chatter = {second: [self.row('firefox.settings.services.mozilla.com', True)]
                   for second in range(0, 200, 3)}
        result = self.run_wait(chatter)
        self.assertTrue(result['settled'])
        self.assertEqual(result['hosts_bytes'], {})

    def test_never_quiet_reports_unsettled_and_exempts_nothing(self):
        endless = {second: [self.row(None)] for second in range(0, 400, 4)}
        result = self.run_wait(endless, timeout=120)
        self.assertFalse(result['settled'])
        self.assertIn('192.0.2.1', result['hosts_bytes'])

    def test_quiet_window_exceeds_several_fetch_periods(self):
        result = self.run_wait({})
        self.assertGreaterEqual(result['quiet_s'], 3 * self.SCHEDULE['autoUpdateAssetFetchPeriod'])


GUEST = '10.0.2.16'


def ipv4(src, dst, proto, transport):
    ip = bytes([0x45, 0]) + struct.pack('>H', 20 + len(transport))
    ip += bytes(4) + bytes([64, proto]) + bytes(2)
    ip += socket.inet_aton(src) + socket.inet_aton(dst)
    return bytes(12) + struct.pack('>H', 0x0800) + ip + transport


def segment(src, sport, dst, dport, payload=b'', flags=0x18):
    return ipv4(src, dst, 6, struct.pack('>HHII', sport, dport, 1, 1)
                + bytes([0x50, flags]) + bytes(6) + payload)


def datagram(src, sport, dst, dport, payload):
    return ipv4(src, dst, 17, struct.pack('>HHHH', sport, dport, 8 + len(payload), 0) + payload)


def tls_record(size, content_type=0x17):
    """One TLS 1.2/1.3 record of `size` bytes on the wire."""
    return bytes([content_type, 3, 3]) + struct.pack('>H', size - 5) + bytes(size - 5)


def dns_name(name):
    return b''.join(bytes([len(p)]) + p.encode() for p in name.split('.')) + b'\0'


def dns_query(name):
    return struct.pack('>HHHHHH', 0x1234, 0x0100, 1, 0, 0, 0) + dns_name(name) + struct.pack('>HH', 1, 1)


def dns_answer(name, address):
    question = dns_name(name) + struct.pack('>HH', 1, 1)
    answer = b'\xc0\x0c' + struct.pack('>HHIH', 1, 1, 60, 4) + socket.inet_aton(address)
    return struct.pack('>HHHHHH', 0x1234, 0x8180, 1, 1, 0, 0) + question + answer


class TypingFlowAttributionTests(unittest.TestCase):
    """Synthetic captures shaped like rc2's typing window (final-acceptance)."""
    AMO = ('151.101.65.91', 'services.addons.mozilla.org')
    SUGGEST = ('52.142.124.215', 'ac.duckduckgo.com')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'capture.pcap'
        self.path.write_bytes(struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
        self.clock = 1000

    def tearDown(self):
        self.temp.cleanup()

    def append(self, frame):
        self.clock += 1
        with self.path.open('ab') as f:
            f.write(struct.pack('<IIII', self.clock, 0, len(frame), len(frame)) + frame)
        return self.path.stat().st_size

    def offset(self):
        return self.path.stat().st_size

    def open_tls(self, server, port=48794, dport=443):
        """A full connection opened before typing: SYN, ClientHello, bulk reply."""
        address, host = server
        self.append(segment(GUEST, port, address, dport, flags=0x02))
        self.append(segment(address, dport, GUEST, port, flags=0x12))
        self.append(segment(GUEST, port, address, dport, hello(host)))
        self.append(segment(address, dport, GUEST, port, tls_record(1400)))
        self.append(segment(GUEST, port, address, dport, tls_record(300)))

    def attribute(self, start, end=None):
        return harness.attribute_typing_flows(str(self.path), {GUEST}, start,
                                              self.offset() if end is None else end,
                                              ['noai.duckduckgo.com', 'ac.duckduckgo.com'])

    def test_keepalive_bound_is_one_h2_control_frame_in_the_largest_tls_envelope(self):
        self.assertEqual(harness.H2_CONTROL_FRAME_BYTES, 17)
        self.assertEqual(harness.KEEPALIVE_RECORD_MAX, 46)
        for size in (24, 31, 39, 46):        # the rc2 alert and ping records
            self.assertTrue(harness.keepalive_sized(tls_record(size, 0x17)))
        self.assertFalse(harness.keepalive_sized(tls_record(47)))
        self.assertFalse(harness.keepalive_sized(tls_record(39) + tls_record(31)))
        self.assertFalse(harness.keepalive_sized(tls_record(39, 0x16)))
        self.assertFalse(harness.keepalive_sized(b'GET /ac/?q=lws HTTP/1.1\r\n\r\n'))

    def test_preexisting_keepalive_and_close_records_pass(self):
        self.open_tls(self.AMO, 39466)
        start = self.offset()
        self.append(segment(GUEST, 39466, self.AMO[0], 443, tls_record(46)))
        self.append(segment(self.AMO[0], 443, GUEST, 39466, tls_record(46)))
        self.append(segment(GUEST, 39466, self.AMO[0], 443, tls_record(46)))
        self.append(segment(GUEST, 39466, self.AMO[0], 443, tls_record(31, 0x15)))
        self.append(segment(GUEST, 39466, self.AMO[0], 443, flags=0x11))   # FIN, no payload
        result = self.attribute(start)
        self.assertEqual(result['typing_flows'], [])
        [flow] = result['flows']
        self.assertEqual((flow['verdict'], flow['opened'], flow['host']),
                         ('keepalive', 'before-typing', 'services.addons.mozilla.org'))
        self.assertEqual([n for _t, n in flow['window_out']], [46, 46, 31])
        self.assertEqual([n for _t, n in flow['window_in']], [46])
        # pcap_payloads still sees every packet; only the attribution passes them.
        self.assertEqual(len([r for r in harness.pcap_payloads(str(self.path), start, {GUEST})
                              if not r['background']]), 3)

    def test_new_connection_during_typing_fails(self):
        self.open_tls(self.AMO, 39466)
        start = self.offset()
        self.append(segment(GUEST, 51000, self.SUGGEST[0], 443, flags=0x02))
        self.append(segment(GUEST, 51000, self.SUGGEST[0], 443, hello(self.SUGGEST[1])))
        [flow] = self.attribute(start)['typing_flows']
        self.assertEqual(flow['host'], 'ac.duckduckgo.com')
        self.assertEqual(flow['opened'], 'during-typing')
        self.assertIn('new-connection', flow['reasons'])
        self.assertIn('search-or-suggest-host', flow['reasons'])

    def test_bare_syn_during_typing_fails_without_any_payload(self):
        start = self.offset()
        self.append(segment(GUEST, 51001, '192.0.2.7', 443, flags=0x02))
        [flow] = self.attribute(start)['typing_flows']
        self.assertEqual(flow['reasons'], ['new-connection'])

    def test_reused_four_tuple_with_a_new_syn_is_a_new_connection(self):
        self.open_tls(self.AMO, 39466)
        start = self.offset()
        self.append(segment(GUEST, 39466, self.AMO[0], 443, flags=0x02))
        self.append(segment(GUEST, 39466, self.AMO[0], 443, tls_record(39)))
        [flow] = self.attribute(start)['typing_flows']
        self.assertIn('new-connection', flow['reasons'])
        self.assertIsNone(flow['host'])

    def test_large_payload_on_an_old_connection_fails(self):
        self.open_tls(self.SUGGEST, 48516)
        self.open_tls(self.AMO, 39466)
        start = self.offset()
        self.append(segment(GUEST, 39466, self.AMO[0], 443, tls_record(47)))
        self.append(segment(GUEST, 48516, self.SUGGEST[0], 443, tls_record(39)))
        flows = {f['host']: f for f in self.attribute(start)['typing_flows']}
        self.assertEqual(flows['services.addons.mozilla.org']['reasons'], ['payload-exceeds-keepalive'])
        self.assertEqual(flows['services.addons.mozilla.org']['opened'], 'before-typing')
        # Even a keep-alive sized record to a suggestion host is typing traffic.
        self.assertEqual(flows['ac.duckduckgo.com']['reasons'], ['search-or-suggest-host'])

    def test_small_plaintext_or_coalesced_records_on_an_old_connection_fail(self):
        self.open_tls(self.AMO, 39466)
        self.append(segment(GUEST, 40080, '192.0.2.80', 80, flags=0x02))
        start = self.offset()
        self.append(segment(GUEST, 40080, '192.0.2.80', 80, b'GET /?q=lws HTTP/1.1\r\n\r\n'))
        self.append(segment(GUEST, 39466, self.AMO[0], 443, tls_record(39) + tls_record(24, 0x15)))
        reasons = {f['src_port']: f['reasons'] for f in self.attribute(start)['typing_flows']}
        self.assertEqual(reasons, {40080: ['payload-exceeds-keepalive'],
                                   39466: ['payload-exceeds-keepalive']})

    def test_dns_during_typing_fails_and_taints_the_resolved_address(self):
        self.open_tls(self.SUGGEST, 48516)
        start = self.offset()
        self.append(datagram(GUEST, 33333, '10.0.2.3', 53, dns_query('ac.duckduckgo.com')))
        self.append(datagram('10.0.2.3', 53, GUEST, 33333, dns_answer('ac.duckduckgo.com', self.SUGGEST[0])))
        # A keep-alive sized record to the just-resolved address is still typing traffic.
        self.append(segment(GUEST, 48516, self.SUGGEST[0], 443, tls_record(39)))
        flows = {f['protocol']: f for f in self.attribute(start)['typing_flows']}
        self.assertEqual(flows['udp']['dns_names'], ['ac.duckduckgo.com'])
        self.assertIn('dns-query', flows['udp']['reasons'])
        self.assertIn('resolved-during-typing', flows['tcp']['reasons'])
        self.assertEqual(flows['tcp']['resolved_during_typing'][0]['name'], 'ac.duckduckgo.com')

    def test_dns_over_tls_on_an_old_connection_fails(self):
        self.open_tls(('9.9.9.9', 'dns.quad9.net'), 41000, dport=853)
        start = self.offset()
        self.append(segment(GUEST, 41000, '9.9.9.9', 853, tls_record(39)))
        [flow] = self.attribute(start)['typing_flows']
        self.assertEqual(flow['reasons'], ['dns-query'])

    def test_os_noise_dns_keeps_its_existing_exemption(self):
        start = self.offset()
        self.append(datagram(GUEST, 33334, '10.0.2.3', 53, dns_query('connectivitycheck.gstatic.com')))
        result = self.attribute(start)
        self.assertEqual(result['typing_flows'], [])
        self.assertEqual(result['flows'][0]['verdict'], 'background')

    def test_udp_on_an_old_flow_is_never_a_keepalive(self):
        self.append(datagram(GUEST, 44444, '192.0.2.9', 443, b'\x40' + bytes(30)))
        start = self.offset()
        self.append(datagram(GUEST, 44444, '192.0.2.9', 443, b'\x40' + bytes(30)))
        [flow] = self.attribute(start)['typing_flows']
        self.assertEqual(flow['opened'], 'before-typing')
        self.assertIn('udp-datagram', flow['reasons'])

    def test_flow_first_seen_inside_the_window_is_not_preexisting(self):
        start = self.offset()
        self.append(segment(GUEST, 45000, '192.0.2.10', 443, tls_record(39)))
        [flow] = self.attribute(start)['typing_flows']
        self.assertEqual(flow['reasons'], ['not-open-before-typing'])

    def test_security_settings_flow_stays_background_by_sni_only(self):
        settings = ('151.101.129.91', 'firefox.settings.services.mozilla.com')
        self.open_tls(settings, 49408)
        start = self.offset()
        self.append(segment(GUEST, 49408, settings[0], 443, tls_record(400)))
        # Another flow to the same CDN address does not inherit the exemption.
        self.append(segment(GUEST, 49999, settings[0], 443, flags=0x02))
        result = self.attribute(start)
        verdicts = {f['src_port']: f['verdict'] for f in result['flows']}
        self.assertEqual(verdicts, {49408: 'background', 49999: 'typing-traffic'})

    def test_window_ending_inside_a_packet_is_inconclusive(self):
        start = self.offset()
        end = self.append(segment(GUEST, 45001, '192.0.2.11', 443, tls_record(39)))
        with self.assertRaises(harness.HarnessError):
            self.attribute(start, end - 3)

    def test_engine_hosts_include_the_default_suggestion_endpoint(self):
        with open(ROOT / 'assets/search-config-v2.json') as f:
            hosts = harness.search_endpoint_hosts(json.load(f)['data'])
        self.assertIn('ac.duckduckgo.com', hosts)
        self.assertIn('noai.duckduckgo.com', hosts)

    def test_negative_control_is_wired_to_the_command_line(self):
        self.assertIn('--no-suggest-negative-control', source)
        self.assertIn('negative_control=args.no_suggest_negative_control', source)



def ipv6(src, dst, proto, transport):
    ip = struct.pack('>IHBB', 6 << 28, len(transport), proto, 64)
    ip += socket.inet_pton(socket.AF_INET6, src) + socket.inet_pton(socket.AF_INET6, dst)
    return bytes(12) + struct.pack('>H', 0x86dd) + ip + transport


def dns_answer_aaaa(name, address):
    question = dns_name(name) + struct.pack('>HH', 28, 1)
    answer = b'\xc0\x0c' + struct.pack('>HHIH', 28, 1, 60, 16) + socket.inet_pton(socket.AF_INET6, address)
    return struct.pack('>HHHHHH', 0x1234, 0x8180, 1, 1, 0, 0) + question + answer


class UpdatePrivacyAttributionTests(unittest.TestCase):
    """check-update-privacy by name, per connection.  The shapes are the
    157.0-2 acceptance (run-37248744119) false positives and their opposites."""
    ATTACH = 'firefox-settings-attachments.cdn.mozilla.net'
    UPDATE = ('185.199.111.153', 'redoubtbrowser.org')
    GUEST6 = 'fec0::15'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'capture.pcap'
        self.path.write_bytes(struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
        self.clock = 1000
        self.port = 40000

    def tearDown(self):
        self.temp.cleanup()

    def append(self, frame):
        self.clock += 1
        with self.path.open('ab') as f:
            f.write(struct.pack('<IIII', self.clock, 0, len(frame), len(frame)) + frame)

    def offset(self):
        return self.path.stat().st_size

    def tls(self, address, host):
        self.port += 1
        self.append(segment(GUEST, self.port, address, 443, flags=0x02))
        self.append(segment(address, 443, GUEST, self.port, flags=0x12))
        self.append(segment(GUEST, self.port, address, 443, hello(host)))
        self.append(segment(address, 443, GUEST, self.port, tls_record(1400)))

    def syn6(self, address):
        self.port += 1
        self.append(ipv6(self.GUEST6, address, 6, struct.pack('>HHII', self.port, 443, 1, 0)
                         + bytes([0x50, 0x02]) + bytes(6)))

    def resolve(self, name, address):
        self.port += 1
        self.append(datagram(GUEST, self.port, '10.0.2.3', 53, dns_query(name)))
        reply = dns_answer_aaaa(name, address) if ':' in address else dns_answer(name, address)
        self.append(datagram('10.0.2.3', 53, GUEST, self.port, reply))

    def grade(self, off, on):
        flows = lambda w: harness.attribute_typing_flows(str(self.path), {GUEST, self.GUEST6}, *w)
        return harness.grade_update_privacy_flows(flows(off), flows(on), ['redoubtbrowser.org'])

    def window(self, fill):
        start = self.offset()
        fill()
        return (start, self.offset())

    def off_window(self):
        self.tls('151.101.1.91', self.ATTACH)
        self.tls('34.149.226.178', 'content-signature-2.cdn.mozilla.net')
        self.tls('185.199.109.153', 'ublockorigin.github.io')
        self.syn6('2600:1901:0:8d82::')

    def test_rotated_cdn_address_with_the_same_sni_passes(self):
        off = self.window(self.off_window)
        on = self.window(lambda: (self.tls(*self.UPDATE),
                                  self.tls('151.101.193.91', self.ATTACH)))
        result = self.grade(off, on)
        self.assertEqual(result['on_failed'], [])
        rows = {r['dst']: r for r in result['on_flows']}
        self.assertEqual(rows['151.101.193.91']['names'], {self.ATTACH: 'seen-with-check-off'})

    def test_update_host_passes_in_the_on_window_on_its_own_address(self):
        off = self.window(self.off_window)
        on = self.window(lambda: (self.resolve('redoubtbrowser.org', '2606:50c0:8000::153'),
                                  self.syn6('2606:50c0:8000::153'),
                                  self.tls(*self.UPDATE),
                                  self.syn6('2600:1901:0:8d82::')))
        result = self.grade(off, on)
        self.assertEqual(result['on_failed'], [])
        verdicts = {(r['dst'], r['port']): r['verdict'] for r in result['on_flows']}
        self.assertEqual(verdicts[('185.199.111.153', 443)], 'named')
        self.assertEqual(verdicts[('10.0.2.3', 53)], 'named')
        # A bare SYN is named by the DNS answer that gave the guest its address ...
        self.assertEqual(verdicts[('2606:50c0:8000::153', 443)], 'resolved')
        # ... or, carrying no payload, by the OFF window having contacted it too.
        self.assertEqual(verdicts[('2600:1901:0:8d82::', 443)], 'payload-free-seen-with-check-off')

    def test_new_third_party_host_fails_even_on_an_address_seen_with_check_off(self):
        off = self.window(self.off_window)
        on = self.window(lambda: (self.tls(*self.UPDATE),
                                  self.tls('151.101.1.91', 'tracker.example'),
                                  self.tls('203.0.113.9', 'telemetry.example')))
        result = self.grade(off, on)
        failed = {r['dst']: r for r in result['on_failed']}
        self.assertEqual(set(failed), {'151.101.1.91', '203.0.113.9'})
        self.assertEqual(failed['151.101.1.91']['names'], {'tracker.example': None})
        self.assertEqual(failed['151.101.1.91']['verdict'], 'new-name')
        self.assertIn('tracker.example', harness.describe_update_privacy_failure(failed['151.101.1.91']))

    def test_new_dns_query_fails(self):
        off = self.window(self.off_window)
        on = self.window(lambda: (self.tls(*self.UPDATE), self.resolve('telemetry.example', '203.0.113.9')))
        [row] = self.grade(off, on)['on_failed']
        self.assertEqual((row['port'], row['named_by']), (53, 'dns-query'))

    def test_unnamed_flows_need_a_name_or_must_be_payload_free_to_a_known_address(self):
        off = self.window(self.off_window)

        def on_fill():
            self.tls(*self.UPDATE)
            self.syn6('2001:db8::66')                          # new address, no name
            self.port += 1                                     # QUIC to a known address
            self.append(datagram(GUEST, self.port, '34.149.226.178', 443, b'\xc0' + bytes(40)))
            self.resolve('telemetry.example', '2001:db8::77')  # resolved, but to a new name
            self.syn6('2001:db8::77')
        result = self.grade(off, self.window(on_fill))
        failed = {(r['dst'], r['port']): r['verdict'] for r in result['on_failed']}
        self.assertEqual(failed, {('2001:db8::66', 443): 'unnamed',
                                  ('34.149.226.178', 443): 'unnamed',
                                  ('10.0.2.3', 53): 'new-name',
                                  ('2001:db8::77', 443): 'resolved-to-new-name'})

    def test_update_host_in_the_off_window_fails(self):
        def off_fill():
            self.off_window()
            self.tls(*self.UPDATE)
        off = self.window(off_fill)
        on = self.window(lambda: self.tls(*self.UPDATE))
        result = self.grade(off, on)
        self.assertEqual([f['host'] for f in result['off_update_flows']], ['redoubtbrowser.org'])
        self.assertNotIn('redoubtbrowser.org', result['off_names'])
        # A subdomain is the update host's too.
        off2 = self.window(lambda: self.tls('185.199.110.153', 'www.redoubtbrowser.org'))
        self.assertEqual(len(self.grade(off2, on)['off_update_flows']), 1)

    def test_shared_pages_address_in_the_off_window_is_not_an_update_contact(self):
        self.resolve('redoubtbrowser.org', '185.199.109.153')   # earlier in the capture
        off = self.window(self.off_window)                      # ublockorigin.github.io there
        on = self.window(lambda: self.tls(*self.UPDATE))
        result = self.grade(off, on)
        self.assertEqual(result['off_update_flows'], [])
        self.assertEqual(result['on_failed'], [])

    def test_check_uses_the_name_based_grading(self):
        body = source.split('def check_update_privacy(', 1)[1].split('\nNOT_IMPLEMENTED', 1)[0]
        self.assertIn('grade_update_privacy_flows(', body)
        self.assertIn('attribute_typing_flows(pcap, guest, off1, on_end)', body)
        self.assertNotIn('seen_off', body)


if __name__ == '__main__':
    unittest.main()
