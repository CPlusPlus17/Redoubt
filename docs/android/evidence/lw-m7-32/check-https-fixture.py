#!/usr/bin/env python3
"""Exercise real TLS and fixed-loopback forwarding without an Android/browser claim."""
from contextlib import closing
import http.client
import http.server
import importlib.util
import json
from pathlib import Path
import secrets
import socket
import ssl
import tempfile
import threading

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cookie_https', HERE / 'https-fixture.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
challenge = secrets.token_hex(32)
requests = []

class Backend(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass
    def do_GET(self):
        requests.append({'path': self.path, 'host': self.headers.get('Host'), 'cookie': self.headers.get('Cookie')})
        data = json.dumps({'challenge': challenge, 'path': self.path}).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

backend = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Backend)
threading.Thread(target=backend.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix='lw32-tls-') as tmp:
        state = Path(tmp) / 'private'
        manifest = fixture.prepare(state)
        assert state.stat().st_mode & 0o077 == 0
        assert all((state / key).stat().st_mode & 0o077 == 0 for key in ('ca.key', 'server.key'))
        server = fixture.make_server(state, 0, backend.server_port)
        assert server.server_address[0] == '127.0.0.1'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def connect(name='cookies.fixture.test', trusted=True):
            context = ssl.create_default_context(cafile=str(state / 'ca.pem')) if trusted else ssl.create_default_context()
            client = http.client.HTTPSConnection(name, server.server_port, context=context, timeout=10)
            client._create_connection = lambda _addr, *args, **kwargs: socket.create_connection(('127.0.0.1', server.server_port), timeout=10)
            return client
        try:
            for name in fixture.NAMES:
                with closing(connect(name)) as client:
                    client.request('GET', '/fixture-registration', headers={'Host': name, 'Cookie': 'cookie_dismiss=true'})
                    response = client.getresponse()
                    assert response.status == 200
                    assert json.loads(response.read())['challenge'] == challenge
                    assert requests[-1] == {'path': '/fixture-registration', 'host': name, 'cookie': 'cookie_dismiss=true'}
            print('PASS clean certificate/hostname validation and cookie-preserving forwarding for all three controlled origins')
            for name, trusted in [('wrong.fixture.test', True), ('cookies.fixture.test', False)]:
                try:
                    with closing(connect(name, trusted)) as client:
                        client.request('GET', '/', headers={'Host': name})
                    raise AssertionError('Invalid TLS peer was accepted')
                except ssl.SSLCertVerificationError:
                    pass
            print('PASS untrusted CA and wrong hostname rejected by real TLS verification')
            count = len(requests)
            for path, headers, expected in [('/', {'Host': 'unrelated.example'}, 421),
                    ('https://unrelated.example/', {'Host': fixture.NAMES[0]}, 400),
                    ('/', {'Host': fixture.NAMES[0], 'Content-Length': str(fixture.MAX_REQUEST + 1)}, 413)]:
                with closing(connect()) as client:
                    client.request('GET', path, headers=headers)
                    response = client.getresponse()
                    assert response.status == expected
                    response.read()
            assert len(requests) == count
            print('PASS unrelated Host, proxy-form URL and oversized request rejected before local backend access')
            print('BROWSER MAPPING/TRUST/COOKIE BEHAVIOR: NOT RUN; fixture keys deleted with temporary directory')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
finally:
    backend.shutdown()
    backend.server_close()
