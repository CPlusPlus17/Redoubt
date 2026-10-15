#!/usr/bin/env python3
"""LW-M7-39 (from lw-m7-51): serves eme-probe.html and play.html, and stores each POST /seen/<tag> body as OUT/<tag>.json. usage: eme-server.py PORT OUTDIR"""
import http.server, os, sys, urllib.parse
PORT, OUT = int(sys.argv[1]), sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ("/", "/eme-probe.html", "/play.html"):
            body = open(os.path.join(HERE, "play.html" if p == "/play.html" else "eme-probe.html"), "rb").read()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
        elif p == "/plain.html":
            body = b"<!doctype html><meta charset=utf-8><title>plain page</title><p>plain page, no script</p>"
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        n = int(self.headers.get("Content-Length", 0)); data = self.rfile.read(n)
        if p.startswith("/seen/"):
            tag = urllib.parse.unquote(p[6:]).replace("/", "_")
            open(os.path.join(OUT, tag + ".json"), "wb").write(data)
        self.send_response(204); self.end_headers()
    def log_message(self, fmt, *a):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % a))
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
