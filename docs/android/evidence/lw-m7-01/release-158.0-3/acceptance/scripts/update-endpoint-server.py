#!/usr/bin/env python3
"""Local stand-in for https://redoubtbrowser.org/update/android/ (acceptance probe only).

Serves DIR/latest.json and DIR/latest.json.sig over TLS with a certificate for
redoubtbrowser.org issued by a throwaway CA made for this test, and logs every
request (method, path, every header) as one JSON line to LOG. Anything else is a
404. Reached from the emulator through `adb reverse tcp:443 tcp:PORT` and Gecko's
network.dns.localDomains -- see update-check-probe.py.

usage: update-endpoint-server.py PORT CERT KEY DIR LOG
"""
import http.server, json, os, ssl, sys, time

port, cert, key, root, logpath = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
FILES = {"/update/android/latest.json": "latest.json", "/update/android/latest.json.sig": "latest.json.sig"}


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        name = FILES.get(self.path)
        body = None
        if name and os.path.exists(os.path.join(root, name)):
            body = open(os.path.join(root, name), "rb").read()
        with open(logpath, "a") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "client": self.client_address[0],
                                "method": self.command, "path": self.path, "http": self.request_version,
                                "headers": [[k, v] for k, v in self.headers.items()],
                                "status": 200 if body is not None else 404,
                                "bytes": len(body) if body is not None else 0}) + "\n")
        if body is None:
            body = b"not found\n"
            self.send_response(404)
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/json" if self.path.endswith(".json") else "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(cert, key)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
print("serving %s on 127.0.0.1:%d" % (root, port), flush=True)
srv.serve_forever()
