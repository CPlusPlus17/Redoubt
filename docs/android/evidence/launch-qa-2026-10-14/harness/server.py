"""Serve the QA video page and its clips on 127.0.0.1, and record POST /report bodies.

usage: python3 -I server.py WWW_DIR RESULTS_JSONL PORT
"""
import http.server
import json
import sys
import time
from functools import partial

www, results, port = sys.argv[1], sys.argv[2], int(sys.argv[3])


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/report":
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
        try:
            record = json.loads(body)
        except ValueError:
            record = {"raw": body.decode("utf-8", "replace")}
        record["received"] = time.strftime("%H:%M:%S")
        with open(results, "a") as f:
            f.write(json.dumps(record) + "\n")
        self.send_response(204)
        self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


server = http.server.ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=www))
server.serve_forever()
