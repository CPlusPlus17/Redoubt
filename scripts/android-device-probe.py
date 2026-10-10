#!/usr/bin/env python3
"""Serve the RFP coherence probe to a real phone and grade what it reports.

The smoke harness (scripts/android-smoke.sh --check-rfp-coherence) measures
fingerprinting coherence on an emulator through Marionette. A phone has no
Marionette, and an emulator cannot show a real device's screen, fonts, GPU or
time zone. This script closes that gap for docs/android/DEVICE-CHECKS.md:

  1. run it on a computer on the same network as the phone;
  2. open the printed http:// URL in Redoubt on the phone;
  3. Redoubt shows its HTTPS-only page (this is check 1 of DEVICE-CHECKS.md);
     tap "Continue to HTTP site";
  4. the page reports back and this script prints the graded result and
     writes the full report as JSON.

It uses the probe page, the expected values and the grader embedded in
scripts/android-smoke.sh, so the phone and the emulator are graded alike. It
serves only that page and its worker, loads nothing from anywhere else, and
keeps serving after the first report until Ctrl-C, for the
exception-scope step.

Usage: scripts/android-device-probe.py [--bind 0.0.0.0] [--port 8765] [--out FILE]
"""
import argparse
import http.server
import json
import pathlib
import socket
import sys
import threading
import time
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_harness():
    source = (ROOT / "scripts" / "android-smoke.sh").read_text()
    source = source.split("<<'PYDRIVEREOF'\n", 1)[1].split("\nPYDRIVEREOF", 1)[0]
    module = types.ModuleType("android_smoke")
    exec(compile(source, "android-smoke.sh embedded Python", "exec"), module.__dict__)
    return module


def lan_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # TEST-NET-1: no packet is sent for a UDP connect
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def render(ok, items, report):
    lines = ["RFP coherence on the device: %s" % ("PASS" if ok else "FAIL")]
    for i in items:
        lines.append("  %-4s %-58s got %s" % ("ok" if i["ok"] else "FAIL", i["name"],
                                              json.dumps(i["got"])[:90]))
    lines.append("recorded only (not graded):")
    for key in ("window", "screen", "fontsDetected", "webgl", "canvas", "media", "audioSampleRate",
                "language", "webdriver"):
        lines.append("  %-16s %s" % (key, json.dumps(report.get(key))[:160]))
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bind", default="0.0.0.0", help="address to listen on (default all)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--out", default="rfp-device-report.json")
    ap.add_argument("--major", help="Firefox major version the phone runs (default: from the "
                                    "report's own Firefox/ token, then checked against the spoof)")
    args = ap.parse_args(argv)
    h = load_harness()
    state = {"headers": {}, "report": None}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):
            print("[probe] %s %s" % (self.address_string(), fmt % a), file=sys.stderr)

        def do_GET(self):
            hit = h.rfp_probe_response(self.path)
            if hit is None:
                self.send_error(404)
                return
            if self.path.startswith("/rfp-probe"):
                state["headers"] = {k.lower(): v for k, v in self.headers.items()}
            body, ctype = hit
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not self.path.startswith("/rfp-report"):
                self.send_error(404)
                return
            n = int(self.headers.get("Content-Length") or 0)
            if n > 1 << 20:
                self.send_error(413)
                return
            state["report"] = json.loads(self.rfile.read(n) or b"{}")
            self.send_response(204)
            self.end_headers()

    server = http.server.ThreadingHTTPServer((args.bind, args.port), Handler)
    server.timeout = 1
    # A second origin (port + 1) for DEVICE-CHECKS.md step 6: an HTTPS-only
    # exception granted for the first port must not cover this one.
    other = http.server.ThreadingHTTPServer((args.bind, args.port + 1), Handler)
    threading.Thread(target=other.serve_forever, daemon=True).start()
    host = lan_address() if args.bind == "0.0.0.0" else args.bind
    print("Open this in Redoubt on the phone, then tap 'Continue to HTTP site':\n\n"
          "    http://%s:%d/rfp-probe?post=1\n\n"
          "Second origin for the exception-scope step (must show the interstitial):\n"
          "    http://%s:%d/rfp-probe\n" % (host, args.port, host, args.port + 1), file=sys.stderr)
    try:
        while state["report"] is None:
            server.handle_request()
    except KeyboardInterrupt:
        return 2
    report = state["report"]
    ua = str(report.get("userAgent", ""))
    major = args.major or (ua.rsplit("Firefox/", 1)[-1].split(".")[0] if "Firefox/" in ua else "?")
    ok, items = h.grade_rfp_coherence(report, state["headers"], major)
    print(render(ok, items, report))
    out = {"when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ok": ok, "items": items,
           "report": report, "request_headers": state["headers"], "major": major}
    pathlib.Path(args.out).write_text(json.dumps(out, indent=1))
    print("full report: %s" % args.out, file=sys.stderr)
    print("Still serving both origins for the exception-scope step; Ctrl-C when done.",
          file=sys.stderr)
    try:
        while True:
            server.handle_request()
    except KeyboardInterrupt:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
