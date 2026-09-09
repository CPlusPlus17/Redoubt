#!/usr/bin/env python3
"""Dedicated test CA and loopback TLS bridge; never changes browser trust or DNS."""
import argparse
import hashlib
import http.client
import http.server
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess

ROOT = Path(__file__).resolve().parents[4]
NAMES = ('cookies.fixture.test', 'sub.cookies.fixture.test', 'duh.de')
HOP_HEADERS = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
               'te', 'trailer', 'transfer-encoding', 'upgrade', 'content-length'}
MAX_REQUEST, MAX_RESPONSE = 65536, 2 * 1024 * 1024


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(state):
    # A fixture key must never enter the shared repository or evidence archive.
    state = state.resolve()
    if state == ROOT or ROOT in state.parents:
        raise ValueError('Use a private state directory outside the repository')
    state.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(state, 0o700)
    previous = os.umask(0o077)
    try:
        run = secrets.token_hex(8)
        def openssl(*args):
            subprocess.run(['openssl', *args], cwd=state, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        openssl('req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256',
                '-nodes', '-sha256', '-days', '7', '-keyout', 'ca.key', '-out', 'ca.pem',
                '-subj', '/CN=Redoubt disposable cookie fixture ' + run,
                '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:0',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
        openssl('req', '-new', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256',
                '-nodes', '-sha256', '-keyout', 'server.key', '-out', 'server.csr',
                '-subj', '/CN=cookies.fixture.test')
        (state / 'server.ext').write_text(
            'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
            'extendedKeyUsage=serverAuth\nsubjectAltName=' + ','.join('DNS:' + n for n in NAMES) + '\n')
        openssl('x509', '-req', '-in', 'server.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key',
                '-set_serial', '0x' + secrets.token_hex(16), '-days', '7', '-sha256',
                '-extfile', 'server.ext', '-out', 'server.pem')
        openssl('x509', '-in', 'ca.pem', '-outform', 'DER', '-out', 'ca.der')
        openssl('verify', '-CAfile', 'ca.pem', '-verify_hostname', NAMES[0], 'server.pem')
        manifest = {'run': run, 'dns_names': list(NAMES), 'ca_der_sha256': sha(state / 'ca.der'),
                    'ca_pem_sha256': sha(state / 'ca.pem'), 'server_pem_sha256': sha(state / 'server.pem'),
                    'trust_scope': 'not installed; dedicated browser profile only',
                    'private_material': 'ca.key and server.key; never archive or publish'}
        (state / 'public-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return manifest
    finally:
        os.umask(previous)


def make_server(state, port, backend_port):
    if port == backend_port:
        raise ValueError('The TLS and HTTP ports must differ')
    manifest = json.loads((state / 'public-manifest.json').read_text())
    for name, field in [('ca.der', 'ca_der_sha256'), ('ca.pem', 'ca_pem_sha256'), ('server.pem', 'server_pem_sha256')]:
        if sha(state / name) != manifest[field]:
            raise ValueError('Changed fixture certificate: ' + name)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(state / 'server.pem', state / 'server.key')

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *_args):
            pass  # The native cookie runner owns request and challenge evidence.
        def do_GET(self):
            self.forward()
        def do_POST(self):
            self.forward()
        def forward(self):
            self.close_connection = True
            # Only origin-form paths and the pinned controlled hostnames are valid.
            if not self.path.startswith('/') or self.path.startswith('//'):
                self.send_error(400); return
            host = self.headers.get('Host', '').lower()
            if host not in NAMES and host not in {n + ':443' for n in NAMES}:
                self.send_error(421); return
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) > 1:
                self.send_error(400); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 <= length <= MAX_REQUEST:
                    self.send_error(413); return
            except ValueError:
                self.send_error(400); return
            self.connection.settimeout(15)
            connection = http.client.HTTPConnection('127.0.0.1', backend_port, timeout=15)
            try:
                body = self.rfile.read(length)
                if len(body) != length:
                    self.send_error(400); return
                headers = {key: value for key, value in self.headers.items() if key.lower() not in HOP_HEADERS}
                headers['Connection'] = 'close'
                connection.request(self.command, self.path, body=body, headers=headers)
                response = connection.getresponse()
                data = response.read(MAX_RESPONSE + 1)
                if len(data) > MAX_RESPONSE:
                    self.send_error(502); return
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key.lower() not in HOP_HEADERS:
                        self.send_header(key, value)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(data)
            except (OSError, http.client.HTTPException):
                self.send_error(502)
            finally:
                connection.close()

    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'serve'))
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--port', type=int, default=48762)
    parser.add_argument('--backend-port', type=int, default=48761)
    args = parser.parse_args()
    if any(not 1 <= port <= 65535 for port in (args.port, args.backend_port)):
        parser.error('Invalid port')
    if args.action == 'prepare':
        if not shutil.which('openssl'):
            parser.error('openssl unavailable')
        print(json.dumps(prepare(args.state)))
    else:
        server = make_server(args.state, args.port, args.backend_port)
        print(json.dumps({'listen': '127.0.0.1:' + str(args.port),
                          'backend': '127.0.0.1:' + str(args.backend_port), 'status': 'TLS_BRIDGE_ONLY'}), flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()

if __name__ == '__main__':
    main()
