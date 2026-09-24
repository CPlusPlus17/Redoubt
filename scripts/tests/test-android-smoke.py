#!/usr/bin/env python3
"""Regression tests for capture evidence that handshake-only parsing missed."""
from pathlib import Path
import json
import socket
import struct
import tempfile
import types
import unittest
from unittest.mock import patch
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


if __name__ == '__main__':
    unittest.main()
