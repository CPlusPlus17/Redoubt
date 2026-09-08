#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/android-smoke.sh -- the Redoubt smoke-test harness.
#
# Owner: LW-M2-07.  Documentation: docs/android/SMOKE.md -- read it before
# changing anything here, especially before adding a check.
#
# This file is a thin launcher.  The harness itself is the Python driver
# embedded below: it needs a Marionette client, a TLS server, a pcap parser and
# a DEX string-table reader, none of which are things to write in shell.  The
# shell half does what shell is good at: preflight the tools, unpack the
# harness and its fixtures into a work directory, and own the exit-code
# contract.
#
# EXIT CODES -- other scripts and CI depend on these.
#   0  every requested check passed
#   1  a check FAILED (this is a real defect in the build under test)
#   2  the harness could not run (missing tool, no device, no APK, ...)
#   3  a requested flag is recognised but NOT IMPLEMENTED -- never a pass
# ---------------------------------------------------------------------------
set -euo pipefail

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SELF")/.." && pwd)"
export LW_SMOKE_SELF="$SELF" LW_SMOKE_REPO="$REPO_ROOT"

WORK="${LW_SMOKE_WORK:-$HOME/.cache/librewolf-android-smoke}"

# --work has to be honoured before we unpack anything, so peek for it here.
prev=""
for a in "$@"; do
  case "$prev" in --work) WORK="$a" ;; esac
  case "$a" in --work=*) WORK="${a#--work=}" ;; esac
  prev="$a"
done
export LW_SMOKE_WORK="$WORK"

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then :; else
  # Preflight.  Fail as code 2 (harness cannot run), never as a silent pass.
  missing=""
  for t in python3 openssl; do
    command -v "$t" >/dev/null 2>&1 || missing="$missing $t"
  done
  if [ -n "$missing" ]; then
    echo "android-smoke: missing required host tool(s):$missing" >&2
    echo "android-smoke: openssl is needed to mint the throwaway CA for the https check;" >&2
    echo "               python3 (>=3.8) runs the harness itself." >&2
    exit 2
  fi
  pyver=$(python3 -c 'import sys;print("%d%02d"%sys.version_info[:2])')
  if [ "$pyver" -lt 308 ]; then
    echo "android-smoke: python3 >= 3.8 required, found $(python3 -V 2>&1)" >&2
    exit 2
  fi
fi

if ! mkdir -p "$WORK/harness" 2>/dev/null; then
  echo "android-smoke: cannot create the work directory $WORK/harness" >&2
  echo "android-smoke: set LW_SMOKE_WORK or pass --work to somewhere writable." >&2
  exit 2
fi
DRIVER="$WORK/harness/driver.py"

# The fixture video: 64x64 VP8 + Opus, 2 s, solid #1F66CC.  Embedded rather
# than fetched so the media checks never depend on the network, and rather than
# copied out of the Firefox tree so the harness does not need one.
cat > "$WORK/harness/fixture-video.b64" <<'VIDEOEOF'
GkXfo59ChoEBQveBAULygQRC84EIQoKEd2VibUKHgQRChYECGFOAZwEAAAAAAAv6EU2bdLpNu4tTq4QVSalmU6yBoU27i1OrhBZUrmtTrIHYTbuMU6uEElTDZ1OsggGLTbuMU6uEHFO7a1Osggvk7AEAAAAAAABZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVSalmsirXsYMPQkBNgI1MYXZmNjIuMTIuMTAyV0GNTGF2ZjYyLjEyLjEwMkSJiECfYAAAAAAAFlSua0CtrgEAAAAAAAA/14EBc8WIfIbenWbn0pKcgQAitZyDdW5kiIEAhoVWX1ZQOIOBASPjg4QHc1lA4JCwgUC6gUCagQJVsIRVuYEBrgEAAAAAAABc14ECc8WI7Bcq6bp4hkecgQAitZyDdW5kiIEAhoZBX09QVVNWqoNjLqBWu4QExLQAg4EC4ZGfgQG1iEDncAAAAAAAYmSBEGOik09wdXNIZWFkAQE4AYC7AAAAAAASVMNnQNZzc6BjwIBnyJpFo4dFTkNPREVSRIeNTGF2ZjYyLjEyLjEwMnNz1mPAi2PFiHyG3p1m59KSZ8ihRaOHRU5DT0RFUkSHlExhdmM2Mi4yOC4xMDIgbGlidnB4Z8ihRaOIRFVSQVRJT05Eh5MwMDowMDowMi4wMDAwMDAwMDAAc3PXY8CLY8WI7Bcq6bp4hkdnyKJFo4dFTkNPREVSRIeVTGF2YzYyLjI4LjEwMiBsaWJvcHVzZ8ihRaOIRFVSQVRJT05Eh5MwMDowMDowMi4wMDgwMDAwMDAAH0O2dUl354EAo5WCAACACINtgtAc/e3E7Ofzj6SSR5ijw4EAAIDQAwCdASpAAEAAAEcIhYWIhYSIAgICdaoD+AP6AgcaRkYBcMdIS8QA/vrEP/+zyYl0TD/s8v/8cybmGJ/xq4Cjm4IAFYAIpxpdhTxVwB7ZLmroqRO6edLq9EFR8KOWggApgAihH0T3yjUq59QLwvoVdkopgKOWggA9gAihONB3MqpcTn2qhro2yi/eQKOWggBRgAihONB3MqpejryAH7JeqqmvEKOUggBlgAihLxDkXfvfy1qQBbZ3mJCjlIIAeYAIoTjQdzKqXE+SrvaFS7NAo5aBAH0A0QEAARAQABgAGFgv9AAIjoAAo5OCAI2ACKE40Hcyql6QA3Nwu60Io5OCAKGACKE40Hcyqla9XtD5y3bgo5KCALWACKE40Hcyql5SjzJ3yfijlIIAyYAIoS8Q5F3738tzpTqjGadYo5qCAN2ACKFRfY0adc7Mw1wNBTz4282B8OoigKOTggDxgAihONB3MqpeUsoqWbzZcKOWgQD6ANEBAAEQEAAYABhYL/QACI6AAKORggEFgAihONB3MqpephLp89CjlIIBGYAIoTjQdzKqXo/UQ2MM4mUgo5OCAS2ACKEvEORd+8XekMY6ZoWgo5WCAUGACKFRfY0adc7MwzGPPbGmkGyjk4IBVYAIoTjQdzKqXlLKMNAPzTijk4IBaYAIoTjQdzKqVr1w+i9A2RijkIIBfYAIoTjQdzKqXo/UNPCjloEBdwDRAQABEBAAGAAYWC/0AAiOgACjkYIBkYAIoTjQdy9HjWZEUWqAo5GCAaWACKE40HcyqlxPwE+NbqORggG5gAihLxDkXfvcBreXloCjkoIBzYAIoouEr3qyfz8UR5qLQKOWggHhgAiioEQCgHx7TmQ12u3VMxo7WKOQggH1gAij0+Sx5bMdC72B4KOWgQH0ANEBAAEQEAAYABhYL/QACI6AAKOXggIJgAijyY78AjMGwkEX+LgJo79khUCjmoICHYAIpLTWrcv6g0Dyr7R3RoYIOHkPmY3Qo5GCAjGACKPT5LHls0BZEKmiOKOTggJFgAij0+Sx4nPFe5NYH0CFgKOSggJZgAg6lEWeLvsuzBXROby8o5CCAm2ACDquAmrKh/nFJrxuo5aBAnEA0QEAARAQABgAGFgv9AAIjoAAo4+CAoGACDtktZ4xOJpLUcCjj4IClYAIO2S1njEwRtG92aOQggKpgAg7ZLWeLzBVkO+zW6ORggK9gAg7ZLWeMTihTwKaQ5yjkYIC0YAIO2F2op5Kn9wRe83go5CCAuWACDtktZ4xMFplSg0Yo5aBAu4A0QEAARAQABgAGFgv9AAIjoAAo4+CAvmACDsf6GjLqv1EmDGjkYIDDYAIOpEGop5oDoRmwpndo46CAyGACDqURZ4vSwuNZKORggM1gAg6kQainktcqgiECF+jkIIDSYAIOpRFnjE8ztz+MYCjkYIDXYAIOpRFnjEwXXaAzfSAo5GCA3GACDqURZ4vMUdP2satuKOWgQNrANEBAAEQEBRgAGFgv9AAIjoAAKORggOFgAg6lEWeLwCfv4G+pPyjkYIDmYAIOpEGop5LXxjgH3zzo4+CA62ACDqURZ4xOJqU3WCjkoIDwYAIOpRFnjEwxt94ahgLDKORggPVgAg6kQainmdGVWoyKrCjj4ID6YAIOpRFni8wUrCjRqOWgQPoANEBAAEQEAAYABhYL/QACI6AAKOQggP9gAg6kQainmdiK8kyq6OQggQRgAg6lEWeMTig4Cl3gKORggQlgAg6lEWeMTBddoDN9ICjkYIEOYAIOpEGop5oGHUKXIZzo4+CBE2ACDqURZ4vWSyLWP+jkoIEYYAIOpEGop5oFLyBfyaE6KOWgQRlANEBAAEQEAAYABhYL/QACI6AAKOQggR1gAg6lEWeMTiarob2GKORggSJgAg6lEWeMTBG45r1HhijkYIEnYAIOpEGop5nRlVqMiqwo4+CBLGACDqURZ4vMFKwo0ajkIIExYAIOpEGop5nYivJMqujkIIE2YAIOpRFnjE4oOApd4CjloEE4gDRAQABEBAAGAAYWC/0AAiOgACjkYIE7YAIOpRFnjEwXXaAzfSAo5GCBQGACDqRBqKeaBh1ClyGc6OQggUVgAg6lEWeL1kr13L2sKOQggUpgAg6kQainmdRp2qqP6OQggU9gAg6lEWeMTiezFuF4KOSggVRgAg6lEWeMT1ApoRAlcvAo5GCBWWACDqRBqKeZ0ZVajIqsKOWgQVfANEBAAEQEAAYABhYL/QACI6AAKOQggV5gAg6lEWeLzAB6+FcQKOSggWNgAg6kQainnaAcb85Af6Ao4+CBaGACDqURZ4xOKe3JqKjkYIFtYAIOpRFnjEwWzVg+BFAo5SCBcmACDqRBqKeS+rU61HVrjVPgKOPggXdgAg6lEWeLzAOzr7Ao5aBBdwA0QEAARAQABgAGFgv9AAIjoAAo5KCBfGACDqRBqKeS+vOzoBw23GjkIIGBYAIOpRFnjEwWFiePWCjkYIGGYAIOpRFnjEwhSTREyXEo5OCBi2ACDqRBqKeaBZdib968iFQo46CBkGACDqURZ4vSwuNZKORggZVgAg6kQainmdW2dIQnuCjloEGWQDRAQABEBAAGAAYWC/0AAiOgACjkYIGaYAIOpRFnjE4qW5SuSBAo5GCBn2ACDqURZ4xMFwok9gl4KOSggaRgAg6kQainkvqxjiSjI6Qo4+CBqWACDqURZ4vSwuzvMCjk4IGuYAIOpEGop5L6qveCnw19ZCjkYIGzYAIOpRFnjE4n6zhTJqAo5aBBtYA0QEAARAQABgAGFgv9AAIjoAAo5CCBuGACDqURZ4xOKCz4xNMo5KCBvWACDqRBqKeaA6A0rw9PICjj4IHCYAIOpRFni8wUrCjRqORggcdgAg6kQainnW/tRiPJUijkYIHMYAIOpRFnjEwYEamH5zAo5GCB0WACDqURZ4xMF014sqNMKORggdZgAg6kQainmc6u/0BkPCjloEHUwDRAQABEBAAGAAYWC/0AAiOgACjj4IHbYAIOpRFni8wRHsIV6OSggeBgAg6kQainmgV1TxxUMEoo5CCB5WACDqURZ4xOJ+zlOAMo5GCB6mACDqURZ4xMF0YLq3joqORgge9gAg6kQainkqgQ5PERp6gn6GTggfRAAgGOmrBmo3PmEDxHQSybJuBB3WihADN/mAcU7trkbuPs4EAt4r3gQHxggJn8IEa
VIDEOEOF

cat > "$DRIVER" <<'PYDRIVEREOF'
#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# The Redoubt smoke harness.  Unpacked from
# scripts/android-smoke.sh; do not edit this copy, edit the script.
# ---------------------------------------------------------------------------
import argparse, base64, glob, hashlib, html, io, json, os, re, shutil, signal, socket, ssl, struct
import subprocess, sys, tempfile, threading, time, zipfile, zlib
import http.server
import urllib.parse

EXIT_OK, EXIT_FAIL, EXIT_HARNESS, EXIT_UNIMPLEMENTED = 0, 1, 2, 3

WORK = os.environ.get("LW_SMOKE_WORK") or os.path.expanduser("~/.cache/librewolf-android-smoke")
HARNESS = os.path.join(WORK, "harness")

def log(*a):
    # Everything human-facing goes to stderr: stdout is reserved for the
    # machine-readable payload (--pref-dump is diffed, --network-capture is
    # grepped), so a stray progress line there would corrupt a caller's gate.
    print("[smoke]", *a, file=sys.stderr, flush=True)

class HarnessError(Exception):
    """The harness could not run.  Never reported as a check failure."""

class Unimplemented(Exception):
    """A recognised flag with no implementation.  Never reported as a pass."""

# --------------------------------------------------------------------------
# adb
# --------------------------------------------------------------------------
class Adb:
    def __init__(self, exe, serial=None):
        self.exe, self.serial = exe, serial
    def _argv(self, args):
        a = [self.exe]
        if self.serial:
            a += ["-s", self.serial]
        return a + list(args)
    def run(self, *args, timeout=120, check=False):
        p = subprocess.run(self._argv(args), capture_output=True, text=True,
                           timeout=timeout, errors="replace")
        if check and p.returncode != 0:
            raise HarnessError("adb %s failed (%d): %s%s"
                               % (" ".join(args), p.returncode, p.stdout, p.stderr))
        return p
    def out(self, *args, **kw):
        return self.run(*args, **kw).stdout
    def shell(self, cmd, **kw):
        return self.out("shell", cmd, **kw)
    def devices(self):
        d = []
        for line in self.out("devices").splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                d.append(parts[0])
        return d

# --------------------------------------------------------------------------
# Marionette (the remote-control protocol Gecko already ships)
# --------------------------------------------------------------------------
class Marionette:
    def __init__(self, port, timeout=120):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=20)
        self.sock.settimeout(timeout)
        self.buf = b""
        self.msgid = 0
        self.hello = self._recv()
    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
    def _recv(self):
        while b":" not in self.buf:
            d = self.sock.recv(65536)
            if not d:
                raise HarnessError("marionette closed the connection")
            self.buf += d
        n, _, rest = self.buf.partition(b":")
        n = int(n)
        while len(rest) < n:
            d = self.sock.recv(65536)
            if not d:
                raise HarnessError("marionette closed the connection mid-packet")
            rest += d
        self.buf = rest[n:]
        return json.loads(rest[:n].decode("utf-8"))
    def cmd(self, name, params=None):
        self.msgid += 1
        mid = self.msgid
        payload = json.dumps([0, mid, name, params or {}]).encode("utf-8")
        self.sock.sendall(str(len(payload)).encode() + b":" + payload)
        while True:
            msg = self._recv()
            if isinstance(msg, list) and len(msg) == 4 and msg[0] == 1 and msg[1] == mid:
                if msg[2] is not None:
                    raise MarionetteError(name, msg[2])
                return msg[3]
    # convenience
    def script(self, js, args=None, chrome=False, sandbox="smoke"):
        self.cmd("Marionette:SetContext", {"value": "chrome" if chrome else "content"})
        r = self.cmd("WebDriver:ExecuteScript",
                     {"script": js, "args": args or [], "sandbox": sandbox})
        return r.get("value")
    def async_script(self, js, args=None, chrome=False, sandbox="smoke"):
        self.cmd("Marionette:SetContext", {"value": "chrome" if chrome else "content"})
        r = self.cmd("WebDriver:ExecuteAsyncScript",
                     {"script": js, "args": args or [], "sandbox": sandbox})
        return r.get("value")

class MarionetteError(Exception):
    def __init__(self, cmdname, err):
        self.cmdname, self.err = cmdname, err
        self.name = err.get("error", "?") if isinstance(err, dict) else "?"
        self.message = err.get("message", "") if isinstance(err, dict) else str(err)
        super().__init__("%s -> %s: %s" % (cmdname, self.name, self.message))

# --------------------------------------------------------------------------
# The local origin server.  http and https, same content, one throwaway CA.
# --------------------------------------------------------------------------
PROBE_PAGE = b"""<!doctype html><html><head><meta charset="utf-8">
<title>LibreWolf Android smoke</title></head>
<body><h1 id="marker">lw-smoke-page-ok</h1>
<video id="v" src="/fixture.webm" muted playsinline preload="auto"></video>
</body></html>"""

UBO_ID = "uBlock0@raymondhill.net"
UBO_FILTER_FILE = "assets/thirdparties/easylist/easylist.txt"
UBO_FILTER_RULE = "/banner_ads/*$~xmlhttprequest,domain=~clickbd.com"
UBO_BLOCKED_PATH = "/banner_ads/redoubt-probe.js"
UBO_ALLOWED_PATH = "/redoubt-allowed.js"

def ubo_probe_response(path):
    """Real parser-inserted subresources, served before Marionette connects.

    The blocked path matches a rule in the unmodified bundled EasyList. Both
    scripts have the same origin and type; disabling uBO must let both reach
    this server. No harness-created filter or extension is installed.
    """
    url = urllib.parse.urlsplit(path)
    token = urllib.parse.parse_qs(url.query).get("token", [""])[0]
    if not re.fullmatch(r"[a-z0-9-]+", token):
        return None
    if url.path == "/ubo-probe":
        body = ('<!doctype html><meta charset="utf-8"><title>uBO first page</title>'
                '<script>window.redoubtUboProbe={token:%s,blocked:false,allowed:false};</script>'
                '<script src="%s?token=%s"></script>'
                '<script src="%s?token=%s"></script>'
                '<p id="ubo-marker">uBO fixture complete</p>'
                % (json.dumps(token), UBO_BLOCKED_PATH, token, UBO_ALLOWED_PATH, token))
        return body.encode(), "text/html; charset=utf-8"
    if url.path in (UBO_BLOCKED_PATH, UBO_ALLOWED_PATH):
        key = "blocked" if url.path == UBO_BLOCKED_PATH else "allowed"
        return ("window.redoubtUboProbe.%s=true;" % key).encode(), "application/javascript"
    return None

class Origin:
    """Serves the probe page over http and https from the host, reachable from
    the emulator at 10.0.2.2.  Records every request it receives, which is what
    makes 'the page really loaded' a fact and not an inference."""
    def __init__(self, root, http_port, https_port, video):
        self.root = root
        self.http_port, self.https_port = http_port, https_port
        self.requests = []
        lock = threading.Lock()
        reqs = self.requests
        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, fmt, *a):
                pass
            def do_GET(self):
                with lock:
                    reqs.append((time.time(), self.scheme, self.path))
                ubo = ubo_probe_response(self.path)
                if ubo is not None:
                    body, ctype = ubo
                elif self.path.startswith("/fixture.webm"):
                    body, ctype = video, "video/webm"
                elif self.path.startswith("/empty"):
                    body, ctype = b"<!doctype html><title>e</title>", "text/html; charset=utf-8"
                else:
                    body, ctype = PROBE_PAGE, "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
        class HttpH(H):
            scheme = "http"
        class HttpsH(H):
            scheme = "https"
        # Loopback only.  The emulator's user-mode network maps 10.0.2.2 to the
        # host's loopback, so binding wider would only publish the probe page
        # and the throwaway certificate to the LAN.
        bind = os.environ.get("LW_SMOKE_BIND", "127.0.0.1")
        self.s1 = http.server.ThreadingHTTPServer((bind, http_port), HttpH)
        self.s2 = http.server.ThreadingHTTPServer((bind, https_port), HttpsH)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(os.path.join(root, "srv.pem"))
        self.s2.socket = ctx.wrap_socket(self.s2.socket, server_side=True)
        for s in (self.s1, self.s2):
            threading.Thread(target=s.serve_forever, daemon=True).start()
    def stop(self):
        for s in (self.s1, self.s2):
            try:
                s.shutdown()
            except Exception:
                pass
    def got(self, path_prefix, since=0.0):
        return [r for r in self.requests if r[2].startswith(path_prefix) and r[0] >= since]

def mint_certs(root):
    """A throwaway CA and a leaf for IP:10.0.2.2, regenerated if absent."""
    ca_crt, ca_key = os.path.join(root, "ca.crt"), os.path.join(root, "ca.key")
    srv_pem = os.path.join(root, "srv.pem")
    if os.path.exists(ca_crt) and os.path.exists(srv_pem):
        return open(os.path.join(root, "ca.b64")).read().strip()
    def ossl(*args, stdin=None):
        p = subprocess.run(["openssl"] + list(args), capture_output=True, text=True, input=stdin)
        if p.returncode != 0:
            raise HarnessError("openssl %s failed: %s" % (args[0], p.stderr))
        return p.stdout
    ossl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", ca_key, "-out", ca_crt,
         "-days", "3650", "-subj", "/CN=LibreWolf Android smoke throwaway CA",
         "-addext", "basicConstraints=critical,CA:TRUE",
         "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    csr, key = os.path.join(root, "srv.csr"), os.path.join(root, "srv.key")
    ossl("req", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", csr, "-subj", "/CN=10.0.2.2")
    ext = os.path.join(root, "srv.ext")
    with open(ext, "w") as f:
        f.write("subjectAltName=IP:10.0.2.2,IP:127.0.0.1,DNS:localhost\n"
                "basicConstraints=CA:FALSE\n"
                "keyUsage=critical,digitalSignature,keyEncipherment\n"
                "extendedKeyUsage=serverAuth\n")
    crt = os.path.join(root, "srv.crt")
    ossl("x509", "-req", "-in", csr, "-CA", ca_crt, "-CAkey", ca_key, "-CAcreateserial",
         "-out", crt, "-days", "825", "-extfile", ext)
    with open(srv_pem, "w") as f:
        f.write(open(key).read() + open(crt).read())
    b64 = "".join(l.strip() for l in open(ca_crt) if not l.startswith("-----"))
    with open(os.path.join(root, "ca.b64"), "w") as f:
        f.write(b64)
    return b64

def build_probe_xpi(path):
    """A minimal unsigned WebExtension whose content script leaves a DOM marker,
    so 'installed' is proven by the extension actually running."""
    if os.path.exists(path):
        return path
    manifest = {
        "manifest_version": 2,
        "name": "LibreWolf smoke probe",
        "version": "1.0",
        "browser_specific_settings": {"gecko": {"id": "smoke-probe@librewolf.invalid"}},
        "content_scripts": [{"matches": ["<all_urls>"], "js": ["cs.js"], "run_at": "document_start"}],
    }
    cs = ('document.documentElement.setAttribute("data-lw-smoke-ext",'
          ' "alive-" + (typeof browser !== "undefined" ? "webext" : "noapi"));\n')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("cs.js", cs)
    return path

# --------------------------------------------------------------------------
# pcap: the network capture.  Parsed at the emulator's virtual NIC, so it sees
# everything the whole VM sends and cannot be evaded by the app.
# --------------------------------------------------------------------------
def _dns_name(b, off, depth=0):
    out = []
    while off < len(b) and depth < 8:
        l = b[off]
        if l == 0:
            off += 1
            break
        if l & 0xC0 == 0xC0:
            if off + 1 >= len(b):
                break
            out.append(_dns_name(b, ((l & 0x3F) << 8) | b[off + 1], depth + 1)[0])
            off += 2
            break
        out.append(b[off + 1:off + 1 + l].decode("latin1"))
        off += 1 + l
    return (".".join(x for x in out if x), off)

def _tls_sni(pl):
    if len(pl) < 45 or pl[0] != 0x16 or pl[5] != 0x01:
        return None
    try:
        record_end = 5 + struct.unpack(">H", pl[3:5])[0]
        hello_end = 9 + int.from_bytes(pl[6:9], "big")
        if hello_end > record_end or hello_end < 43:
            return None
        pl = pl[:hello_end]
        p = 43
        p += 1 + pl[p]
        p += 2 + struct.unpack(">H", pl[p:p + 2])[0]
        p += 1 + pl[p]
        if p + 2 > len(pl):
            return None
        end = p + 2 + struct.unpack(">H", pl[p:p + 2])[0]
        if end > hello_end:
            return None
        p += 2
        while p + 4 <= min(end, len(pl)):
            et, el = struct.unpack(">HH", pl[p:p + 4])
            p += 4
            if p + el > end:
                return None
            if et == 0:
                # A complete SNI is sufficient even when later ClientHello
                # extensions span another TCP segment. A truncated hostname
                # must never turn an attacker-controlled suffix into an
                # apparently allowlisted prefix.
                if p + el > len(pl) or el < 5 or pl[p + 2] != 0:
                    return None
                if struct.unpack(">H", pl[p:p + 2])[0] + 2 != el:
                    return None
                q = p + 3
                nl = struct.unpack(">H", pl[q:q + 2])[0]
                q += 2
                if not nl or q + nl > p + el:
                    return None
                return pl[q:q + nl].decode("ascii")
            p += el
    except Exception:
        return None
    return None

def pcap_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0

def ipv6_transport(ip):
    """Walk IPv6 extension headers; never silently discard a fragmented flow."""
    proto = ip[6]
    rest = ip[40:40 + struct.unpack(">H", ip[4:6])[0]]
    for _ in range(16):
        if proto in (0, 43, 60, 51):
            if len(rest) < 2:
                raise HarnessError("truncated IPv6 extension header")
            size = (rest[1] + 2) * 4 if proto == 51 else (rest[1] + 1) * 8
            if size > len(rest):
                raise HarnessError("truncated IPv6 extension body")
            proto, rest = rest[0], rest[size:]
        elif proto == 44:
            if len(rest) < 8 or struct.unpack(">H", rest[2:4])[0] & 0xfff9:
                raise HarnessError("fragmented IPv6 prevents payload attribution")
            proto, rest = rest[0], rest[8:]
        else:
            return proto, rest
    raise HarnessError("excessive IPv6 extension headers")

def pcap_events(path, start_offset=0):
    """Yield (ts, kind, detail, src_ip, dst_ip, dst_port).  kind is one of
    dns / sni / http / tcp-syn / udp.  The capture is taken at the virtual NIC
    and therefore contains BOTH directions -- callers must filter on src, or a
    DNS reply gets counted as an outbound request."""
    with open(path, "rb") as f:
        gh = f.read(24)
        if len(gh) < 24:
            raise HarnessError("capture has no complete pcap header")
        if gh[:4] not in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4"):
            raise HarnessError("unsupported pcap format for event audit")
        endian = "<" if gh[:4] == b"\xd4\xc3\xb2\xa1" else ">"
        if struct.unpack(endian + "I", gh[20:24])[0] != 1:
            raise HarnessError("event audit requires an Ethernet pcap")
        limit = os.fstat(f.fileno()).st_size
        while f.tell() < limit:
            if f.tell() + 16 > limit:
                raise HarnessError("capture ends inside a packet header")
            h = f.read(16)
            if len(h) < 16:
                raise HarnessError("capture packet header is incomplete")
            ts, tu, cl, _ol = struct.unpack(endian + "IIII", h)
            if cl != _ol or f.tell() + cl > limit:
                raise HarnessError("capture contains an incomplete packet")
            data = f.read(cl)
            if len(data) < cl:
                raise HarnessError("capture packet data is incomplete")
            if f.tell() <= start_offset:
                continue
            if len(data) < 34:
                continue
            ethernet_type = struct.unpack(">H", data[12:14])[0]
            if ethernet_type in (0x8100, 0x88a8):
                raise HarnessError("VLAN-tagged capture is unsupported; cannot audit all traffic")
            ip = data[14:]
            t = ts + tu / 1e6
            if ethernet_type == 0x0800:
                ihl = (ip[0] & 0x0F) * 4
                proto = ip[9]
                src = socket.inet_ntoa(ip[12:16])
                dst = socket.inet_ntoa(ip[16:20])
                rest = ip[ihl:]
            elif ethernet_type == 0x86dd and len(ip) >= 40:
                src = socket.inet_ntop(socket.AF_INET6, ip[8:24])
                dst = socket.inet_ntop(socket.AF_INET6, ip[24:40])
                proto, rest = ipv6_transport(ip)
                if proto not in (6, 17, 58):
                    yield (t, "ipv6-unparsed", "next-header=%d" % proto, src, dst, 0)
            else:
                continue
            if proto == 17 and len(rest) >= 8:
                dp = struct.unpack(">H", rest[2:4])[0]
                pl = rest[8:]
                if dp == 53 and len(pl) > 12:
                    o = 12
                    for _ in range(struct.unpack(">H", pl[4:6])[0]):
                        name, o = _dns_name(pl, o)
                        o += 4
                        if name:
                            yield (t, "dns", name, src, dst, dp)
                elif pl:
                    yield (t, "udp", "", src, dst, dp)
            elif proto == 6 and len(rest) >= 20:
                dp = struct.unpack(">H", rest[2:4])[0]
                pl = rest[((rest[12] >> 4) * 4):]
                if rest[13] & 0x02 and not rest[13] & 0x10:
                    yield (t, "tcp-syn", "", src, dst, dp)
                if pl:
                    sni = _tls_sni(pl)
                    if sni:
                        yield (t, "sni", sni, src, dst, dp)
                    elif pl[:4] in (b"GET ", b"POST", b"HEAD", b"PUT ") or pl[:7] == b"CONNECT":
                        txt = pl.decode("latin1", "replace")
                        lines = txt.split("\r\n")
                        host = ""
                        for line in lines:
                            if line.lower().startswith("host:"):
                                host = line[5:].strip()
                                break
                        yield (t, "http", (host + " " + lines[0])[:160], src, dst, dp)

# Traffic the Android system itself emits regardless of which browser is
# installed.  Kept deliberately short and Android-specific; every entry is a
# hostname or transport that Fenix has no reason to use.  See SMOKE.md.
OS_NOISE_HOSTS = (
    "connectivitycheck.gstatic.com",
    "time.android.com",
    "ipv4only.arpa",
    "www.gstatic.com",
    "clients3.google.com",
    "android.clients.google.com",
)
OS_NOISE_IPS = ("224.0.0.251", "255.255.255.255", "10.0.2.3", "10.0.2.15", "10.0.2.2")

def is_os_noise(kind, detail, dst, port):
    if kind == "dns":
        return detail.lower().rstrip(".") in OS_NOISE_HOSTS
    if kind in ("sni",):
        return detail.lower().rstrip(".") in OS_NOISE_HOSTS
    if kind == "http":
        h = detail.split(" ")[0].lower()
        return h in OS_NOISE_HOSTS
    if kind == "udp":
        return dst in OS_NOISE_IPS or port in (67, 68, 5353, 123, 546, 547)
    if kind == "tcp-syn":
        return dst in OS_NOISE_IPS
    return False

# These hosts carry the security collections explicitly retained by BETA.md
# E12. Exemption is by a connection's SNI, never by its CDN's shared IP address.
SECURITY_SETTINGS_HOSTS = (
    "firefox.settings.services.mozilla.com",
    "firefox-settings-attachments.cdn.mozilla.net",
    "content-signature-2.cdn.mozilla.net",
)

def pcap_payloads(path, start_offset, guest_ips, end_offset=None):
    """Outbound transport payloads, including data on already-open TLS flows.

    Scan from the header to retain earlier SNI and complete packet boundaries.
    A snapshot can end halfway through a packet; that packet belongs to the
    next snapshot once complete. Unknown flows remain visible and cannot pass
    as background merely because their destination shares an allowed CDN IP.
    """
    names, rows = {}, []
    with open(path, "rb") as f:
        gh = f.read(24)
        if len(gh) != 24:
            raise HarnessError("capture has no complete pcap header")
        magic = gh[:4]
        if magic not in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4"):
            raise HarnessError("unsupported pcap format for payload audit")
        endian = "<" if magic == b"\xd4\xc3\xb2\xa1" else ">"
        if struct.unpack(endian + "I", gh[20:24])[0] != 1:
            raise HarnessError("payload audit requires an Ethernet pcap")
        limit = os.fstat(f.fileno()).st_size if end_offset is None else end_offset
        while f.tell() + 16 <= limit:
            offset = f.tell()
            ts, us, size, original = struct.unpack(endian + "IIII", f.read(16))
            if f.tell() + size > limit:
                if end_offset is not None:
                    raise HarnessError("typing window ends inside a packet; attribution is inconclusive")
                break
            frame = f.read(size)
            if len(frame) != size:
                break
            packet_end = f.tell()
            if size != original:
                raise HarnessError("truncated packet prevents a complete payload audit")
            if len(frame) < 14:
                continue
            ether = struct.unpack(">H", frame[12:14])[0]
            if ether in (0x8100, 0x88a8):
                raise HarnessError("VLAN-tagged capture is unsupported; cannot audit all payloads")
            ip = frame[14:]
            if ether == 0x0800 and len(ip) >= 20:
                src, dst = socket.inet_ntoa(ip[12:16]), socket.inet_ntoa(ip[16:20])
                if src not in guest_ips:
                    continue
                if struct.unpack(">H", ip[6:8])[0] & 0x3fff:
                    raise HarnessError("fragmented outbound IPv4 prevents payload attribution")
                proto = ip[9]
                rest = ip[(ip[0] & 15) * 4:struct.unpack(">H", ip[2:4])[0]]
            elif ether == 0x86dd and len(ip) >= 40:
                src = socket.inet_ntop(socket.AF_INET6, ip[8:24])
                dst = socket.inet_ntop(socket.AF_INET6, ip[24:40])
                if src not in guest_ips:
                    continue
                proto, rest = ipv6_transport(ip)
                if proto not in (6, 17, 58):
                    raise HarnessError("outbound IPv6 extension header prevents payload attribution")
            else:
                continue
            if proto == 6 and len(rest) >= 20:
                sp, dp = struct.unpack(">HH", rest[:4])
                data = rest[(rest[12] >> 4) * 4:]
                flow = (src, sp, dst, dp)
                # A reused four-tuple starts a new connection when SYN appears.
                if rest[13] & 2 and not rest[13] & 16:
                    names.pop(flow, None)
                host = _tls_sni(data)
                if host:
                    names[flow] = host.lower().rstrip(".")
                host = names.get(flow)
            elif proto == 17 and len(rest) >= 8:
                sp, dp = struct.unpack(">HH", rest[:4])
                data, host = rest[8:], None
                if dp == 53 and len(data) > 12:
                    host = _dns_name(data, 12)[0].lower().rstrip(".")
            else:
                continue  # ICMP and pure link management carry no browser query.
            if not data or packet_end <= start_offset:
                continue
            background = (host in SECURITY_SETTINGS_HOSTS or host in OS_NOISE_HOSTS)
            if proto == 17 and dp != 53:
                # Port number alone does not establish OS ownership. Unknown
                # public unicast UDP stays suspect even on NTP/mDNS ports.
                background = background or (dst.lower() in ("224.0.0.251", "ff02::fb") and dp == 5353)
                background = background or (dst.lower() in ("255.255.255.255", "ff02::1:2")
                                             and dp in (67, 68, 546, 547))
            rows.append({"ts": ts + us / 1e6, "protocol": "tcp" if proto == 6 else "udp",
                         "src": src, "src_port": sp, "dst": dst, "port": dp,
                         "host": host, "bytes": len(data), "background": background})
        if end_offset is not None and f.tell() != limit:
            raise HarnessError("typing window ends inside a packet header; attribution is inconclusive")
    return rows

# --------------------------------------------------------------------------
# DEX string table -- for the APK static checks.  Reads the real string_ids
# table rather than grepping the file, so a hit is a genuine string constant.
# --------------------------------------------------------------------------
def dex_strings(blob):
    if blob[:4] not in (b"dex\n",):
        return
    endian_tag = struct.unpack("<I", blob[40:44])[0]
    e = "<" if endian_tag == 0x12345678 else ">"
    string_ids_size, string_ids_off = struct.unpack(e + "II", blob[56:64])
    for i in range(string_ids_size):
        off = struct.unpack(e + "I", blob[string_ids_off + i * 4: string_ids_off + i * 4 + 4])[0]
        p = off
        shift = 0
        val = 0
        while True:  # uleb128 utf16_size
            b = blob[p]
            p += 1
            val |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                break
        end = blob.index(b"\x00", p)
        yield blob[p:end].decode("utf-8", "replace")

def apk_dex_strings(apk):
    with zipfile.ZipFile(apk) as z:
        for n in z.namelist():
            if re.fullmatch(r"classes\d*\.dex", n):
                for s in dex_strings(z.read(n)):
                    yield s

def apk_entries(apk):
    with zipfile.ZipFile(apk) as z:
        return z.namelist()

# --------------------------------------------------------------------------
# DEX type_ids / method_ids / field_ids -- the OTHER structured tables.
#
# READ THIS BEFORE EXTENDING IT.  Two earlier attempts at LW-M4-16 were
# rejected, one of them for shipping a hand-rolled linear-sweep DISASSEMBLER
# whose opcode width table was wrong; a verifier drove it to a concrete false
# pass.  Nothing below decodes an instruction.  These are fixed-width index
# tables at offsets the dex header states outright:
#
#   type_ids    u32 descriptor_idx                      -> string_ids
#   method_ids  u16 class_idx, u16 proto_idx, u32 name_idx
#   field_ids   u16 class_idx, u16 type_idx,  u32 name_idx
#
# Reading them cannot desynchronise, because there is nothing to synchronise
# to: every entry is at a computed offset.  That is the whole reason this is
# allowed where a disassembler is not.  If you find yourself needing to know
# whether an instruction EXECUTES, stop -- that is the thing this file may not
# do, and the answer belongs in a different kind of evidence.
# --------------------------------------------------------------------------
def _dex_header(blob):
    """(endian, {table: (size, off)}) or None if this is not a dex."""
    if blob[:4] != b"dex\n":
        return None
    e = "<" if struct.unpack("<I", blob[40:44])[0] == 0x12345678 else ">"
    (s_sz, s_off, t_sz, t_off, p_sz, p_off,
     f_sz, f_off, m_sz, m_off, c_sz, c_off) = struct.unpack(e + "12I", blob[56:104])
    return e, {"string": (s_sz, s_off), "type": (t_sz, t_off), "proto": (p_sz, p_off),
               "field": (f_sz, f_off), "method": (m_sz, m_off), "class": (c_sz, c_off)}

def _dex_string_list(blob, e, tables):
    size, off = tables["string"]
    out = []
    for i in range(size):
        so = struct.unpack(e + "I", blob[off + i * 4: off + i * 4 + 4])[0]
        p = so
        shift = val = 0
        while True:  # uleb128 utf16_size
            b = blob[p]; p += 1
            val |= (b & 0x7F) << shift; shift += 7
            if not b & 0x80:
                break
        end = blob.index(b"\x00", p)
        out.append(blob[p:end].decode("utf-8", "replace"))
    return out

def dex_types_and_members(blob):
    """(type descriptors, {class descriptor: {member names}}) for one dex.

    Members are METHOD and FIELD names as the dex declares or references them.
    A minified build renames them; that is a real limit, and check_no_gms says
    so in its own detail line rather than letting a rename read as absence."""
    h = _dex_header(blob)
    if h is None:
        return [], {}
    e, tables = h
    S = _dex_string_list(blob, e, tables)
    t_sz, t_off = tables["type"]
    T = [S[struct.unpack(e + "I", blob[t_off + i * 4: t_off + i * 4 + 4])[0]]
         for i in range(t_sz)]
    members = {}
    for key, width in (("method", 8), ("field", 8)):
        sz, off = tables[key]
        for i in range(sz):
            cls_idx, _mid, name_idx = struct.unpack(e + "HHI", blob[off + i * width:
                                                                    off + i * width + width])
            members.setdefault(T[cls_idx], {"method": set(), "field": set()})[key].add(S[name_idx])
    return T, members

def apk_types_and_members(apk):
    types = set()
    members = {}
    with zipfile.ZipFile(apk) as z:
        for n in z.namelist():
            if not re.fullmatch(r"classes\d*\.dex", n):
                continue
            T, M = dex_types_and_members(z.read(n))
            types.update(T)
            for cls, kinds in M.items():
                slot = members.setdefault(cls, {"method": set(), "field": set()})
                slot["method"] |= kinds["method"]
                slot["field"] |= kinds["field"]
    return types, members

def apk_dep_version(apk, marker):
    """The version AGP stamps into META-INF/<group>_<artifact>.version.

    This is the one statement of a dependency's version that survives R8: it is
    a resource entry, not a class, so minification cannot rename it and
    shrinking cannot delete it.  Measured present and equal to 1.13.0 in both
    the debug and the release APKs, 2026-08-25."""
    try:
        with zipfile.ZipFile(apk) as z:
            return z.read(marker).decode("utf-8", "replace").strip()
    except KeyError:
        return None

def parse_semver(v):
    """(1,10,0,stable?) -- None if it does not parse.  The prerelease flag
    matters: androidx.activity 1.10.0-alpha01 still had the LIVE GMS path that
    1.10.0-alpha02 removed, so a prerelease OF the floor version is not the
    floor version."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:[-+](.+))?$", v.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) is None)

# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
class Results:
    def __init__(self):
        self.rows = []
        self.checkpoint = None
    def add(self, name, ok, detail, evidence=None):
        self.rows.append({"check": name, "ok": bool(ok), "detail": detail,
                          "evidence": evidence or {}})
        if self.checkpoint:
            self.checkpoint()
        log("%-22s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
    def failed(self):
        return [r for r in self.rows if not r["ok"]]

# --------------------------------------------------------------------------
# Device / emulator plumbing
# --------------------------------------------------------------------------
def find_sdk(explicit):
    # No path from one contributor's machine in this list: ~/lw-m2-04/sdk was here
    # and has been deleted for weeks, so the fallback was a trap -- the same defect
    # apk_search_dirs() below was fixed for. ~/Android/Sdk is the location the
    # Android Studio installer uses on every Linux machine, which is different from
    # somebody's scratch directory. Anywhere else: --sdk or $ANDROID_SDK_ROOT.
    for c in [explicit, os.environ.get("ANDROID_SDK_ROOT"), os.environ.get("ANDROID_HOME"),
              os.path.expanduser("~/Android/Sdk")]:
        if c and os.path.isdir(os.path.join(c, "platform-tools")):
            return c
    return None

def find_adb(sdk):
    if sdk:
        p = os.path.join(sdk, "platform-tools", "adb")
        if os.access(p, os.X_OK):
            return p
    p = shutil.which("adb")
    if p:
        return p
    raise HarnessError("no adb found. Pass --sdk DIR, or set ANDROID_SDK_ROOT.")

def find_apk(explicit, abi):
    # An explicitly named APK that is not there is an error, never a reason to
    # fall back to whatever else is lying around: a caller pointing at a build
    # that failed to produce an APK must not be handed a stale one.
    for named, where in ((explicit, "--apk"), (os.environ.get("LW_SMOKE_APK"), "LW_SMOKE_APK")):
        if named and not os.path.isfile(named):
            raise HarnessError("%s names %s, which does not exist. Refusing to fall back to "
                               "another APK." % (where, named))
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get("LW_SMOKE_APK"):
        cands.append(os.environ["LW_SMOKE_APK"])
    # Search the directories this REPO actually builds into, derived from
    # version.android/release.android the way scripts/android-apk.sh and
    # .github/workflows/android-release.yaml name them, plus anything the
    # caller points at with LW_SMOKE_APK_DIR.
    #
    # The previous list hardcoded ~/lw-m2-04/out-make/apk and ~/lw-m2-04/out/apk
    # -- one contributor's scratch tree, long deleted.  The error it raised then
    # named those two vanished paths, which reads as "the check is broken" when
    # what actually happened is "you did not say which APK".  A path assumption
    # about one machine is not a default; it is a trap for the next reader.
    searched = []
    for d in apk_search_dirs():
        searched.append(d)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".apk") and abi and abi in f:
                cands.append(os.path.join(d, f))
        for f in sorted(os.listdir(d)):
            if f.endswith(".apk") and "universal" in f:
                cands.append(os.path.join(d, f))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    raise HarnessError("no APK found for abi=%s. Pass --apk PATH, or set LW_SMOKE_APK "
                       "(one file) or LW_SMOKE_APK_DIR (a directory). Searched:\n  %s"
                       % (abi, "\n  ".join(searched) or "(nothing)"))

def apk_search_dirs():
    repo = os.environ.get("LW_SMOKE_REPO", ".")
    dirs = []
    if os.environ.get("LW_SMOKE_APK_DIR"):
        dirs.append(os.environ["LW_SMOKE_APK_DIR"])
    try:
        ver = open(os.path.join(repo, "version.android")).read().strip()
        rel = open(os.path.join(repo, "release.android")).read().strip()
    except OSError:
        ver = rel = None
    if ver and rel:
        # The name make android-package produces, in the repo and beside it.
        leaf = os.path.join("librewolf-android-apk-%s-%s" % (ver, rel), "apk")
        dirs.append(os.path.join(repo, leaf))
        dirs.append(os.path.join(os.path.dirname(os.path.abspath(repo)), leaf))
    dirs.append(os.path.join(repo, "out", "apk"))
    return dirs

def apk_package(apk):
    meta = os.path.join(os.path.dirname(apk), "output-metadata.json")
    if os.path.exists(meta):
        try:
            return json.load(open(meta))["applicationId"]
        except Exception:
            pass
    if os.environ.get("LW_SMOKE_PACKAGE"):
        return os.environ["LW_SMOKE_PACKAGE"]
    raise HarnessError("cannot determine the applicationId: no output-metadata.json next to %s. "
                       "Set LW_SMOKE_PACKAGE." % apk)

def _port_free(port):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p

class Emulator:
    def __init__(self, sdk, work, adb):
        self.sdk, self.work, self.adb = sdk, work, adb
        self.proc = None
        self.serial = None
        self.pcap = None
    def system_image(self):
        base = os.path.join(self.sdk, "system-images")
        if not os.path.isdir(base):
            return None
        best = None
        for api in sorted(os.listdir(base)):
            for tag in os.listdir(os.path.join(base, api)):
                d = os.path.join(base, api, tag, "x86_64")
                if not os.path.isdir(d):
                    continue
                # 'default' has no Google Play services -- the honest baseline
                # for a browser that intends to have zero GMS dependencies.
                rank = {"default": 0, "aosp_atd": 1, "android-desktop": 2}.get(tag, 3)
                cand = (rank, api, tag, "system-images/%s/%s/x86_64/" % (api, tag),
                        int(re.sub(r"\D", "", api) or 0))
                if best is None or cand[0] < best[0]:
                    best = cand
        return best
    def boot(self, avd_name="lw-smoke", timeout=300):
        img = self.system_image()
        if not img:
            raise HarnessError("no x86_64 system image under %s/system-images. "
                               "Install one with sdkmanager, or start an emulator yourself "
                               "and re-run without --emulator." % self.sdk)
        _rank, api, tag, sysdir, apinum = img
        # Some SDK distributions disable the legacy SwiftShader GLES library
        # while retaining ANGLE with the SwiftShader Vulkan backend.
        gpu_mode = ("swiftshader" if os.path.isdir(os.path.join(
            self.sdk, "emulator", "lib64", "gles_swiftshader")) else "swangle")
        avd_home = os.path.join(self.work, "avd")
        avd_dir = os.path.join(avd_home, avd_name + ".avd")
        os.makedirs(avd_dir, exist_ok=True)
        with open(os.path.join(avd_home, avd_name + ".ini"), "w") as f:
            f.write("avd.ini.encoding=UTF-8\npath=%s\npath.rel=avd/%s.avd\ntarget=%s\n"
                    % (avd_dir, avd_name, api))
        if not os.path.exists(os.path.join(avd_dir, "config.ini")):
            with open(os.path.join(avd_dir, "config.ini"), "w") as f:
                f.write("avd.ini.encoding = UTF-8\nabi.type = x86_64\nhw.cpu.arch = x86_64\n"
                        "hw.cpu.ncore = 4\nimage.sysdir.1 = %s\ntag.id = %s\n"
                        "AvdId = %s\navd.ini.displayname = %s\nhw.ramSize = 3072\n"
                        "hw.lcd.width = 1080\nhw.lcd.height = 1920\nhw.lcd.density = 420\n"
                        "disk.dataPartition.size = 6442450944\nhw.audioInput = no\n"
                        "hw.audioOutput = no\nhw.gpu.enabled = yes\nhw.gpu.mode = swiftshader\n"
                        "hw.keyboard = yes\nPlayStore.enabled = false\n"
                        "image.androidVersion.api = %d\nfastboot.forceColdBoot = yes\n"
                        % (sysdir, tag, avd_name, avd_name, apinum))
        # This AVD belongs to the harness. Migrate its old disabled-renderer
        # config as well as fresh AVDs: emulator 37 otherwise falls back to an
        # unsupported in-guest renderer before Android can boot.
        config_path = os.path.join(avd_dir, "config.ini")
        with open(config_path) as f:
            config = f.read()
        config = re.sub(r"(?m)^\s*hw\.gpu\.(?:enabled|mode)\s*=.*\n?", "", config)
        with open(config_path, "w") as f:
            f.write(config.rstrip() + "\nhw.gpu.enabled = yes\nhw.gpu.mode = %s\n" % gpu_mode)
        emu = os.path.join(self.sdk, "emulator", "emulator")
        if not os.access(emu, os.X_OK):
            raise HarnessError("no emulator binary at %s" % emu)
        self.pcap = os.path.join(self.work, "capture.pcap")
        if os.path.exists(self.pcap):
            os.remove(self.pcap)
        env = dict(os.environ,
                   ANDROID_SDK_ROOT=self.sdk, ANDROID_HOME=self.sdk,
                   ANDROID_AVD_HOME=avd_home,
                   ANDROID_EMULATOR_HOME=os.path.join(self.work, "emuhome"),
                   ANDROID_USER_HOME=os.path.join(self.work, "emuhome"))
        os.makedirs(env["ANDROID_EMULATOR_HOME"], exist_ok=True)
        port = None
        for cand in range(5584, 5552, -2):
            if _port_free(cand) and _port_free(cand + 1):
                port = cand
                break
        if port is None:
            raise HarnessError("no free emulator console port in 5554-5584; "
                               "stop an emulator or pass --serial to reuse one")
        self.serial = "emulator-%d" % port
        argv = [emu, "-avd", avd_name, "-no-window", "-no-audio", "-no-boot-anim",
                "-gpu", gpu_mode, "-no-snapshot", "-no-metrics",
                "-port", str(port), "-tcpdump", self.pcap]
        # By default the emulator resolves through the HOST's resolvers, which is
        # a measurement hazard rather than a convenience: this build machine's LAN
        # resolver answers incoming.telemetry.mozilla.org and ads.mozilla.org with
        # 0.0.0.0/::, so a capture taken here records the DNS question and never
        # the connection that would have followed. A first-run count from such a
        # run understates telemetry and must not be published. LW_SMOKE_DNS (or
        # --dns-server) points the emulator at a resolver that answers honestly.
        dns = os.environ.get("LW_SMOKE_DNS")
        if dns:
            argv += ["-dns-server", dns]
            log("emulator DNS forced to %s (bypassing the host's resolvers)" % dns)
        logf = open(os.path.join(self.work, "emulator.log"), "w")
        log("booting emulator %s (%s/%s, x86_64, %s), capture -> %s"
            % (avd_name, api, tag, gpu_mode, self.pcap))
        self.proc = subprocess.Popen(argv, stdout=logf, stderr=subprocess.STDOUT, env=env,
                                     start_new_session=True)
        self.adb.serial = self.serial
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise HarnessError("emulator exited early; see %s/emulator.log" % self.work)
            if self.serial in self.adb.devices():
                if self.adb.shell("getprop sys.boot_completed", timeout=30).strip() == "1":
                    log("emulator booted as %s" % self.serial)
                    return self.serial
            time.sleep(2)
        raise HarnessError("emulator did not boot within %ds; see %s/emulator.log"
                           % (timeout, self.work))
    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.adb.run("emu", "kill", timeout=30)
            except Exception:
                pass
            try:
                self.proc.wait(timeout=30)
            except Exception:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)

# --------------------------------------------------------------------------
# The app under test
# --------------------------------------------------------------------------
GV_CONFIG = """args:
  - "-remote-allow-system-access"
env:
  MOZ_MARIONETTE: "1"
prefs:
  remote.prefs.recommended: false
  marionette.port: 2828
"""

def keep_screen_awake(adb):
    """Stop the display from sleeping for the length of the run.

    Not cosmetic. Several checks idle deliberately -- --check-no-suggest waits
    --capture-seconds (60 by default) with a query sitting unsent in the toolbar,
    and --check-update-privacy idles twice -- and the emulator's screen_off_timeout
    is well under that. Once the display sleeps, `input keyevent` and `input tap`
    land nowhere: on 2026-09-06 --check-no-suggest failed its own positive control
    ("Enter produced NO outbound event in 15s") for exactly this reason, on a build
    whose search demonstrably worked -- --check-search, which never idles, ran a
    real query against the same APK minutes earlier. A harness that cannot keep the
    screen on cannot tell "nothing leaked" from "nothing happened", which is the one
    confusion this check exists to prevent.

    Both levers, because they fail differently: `svc power stayon true` holds a wake
    lock while charging (an emulator always reports charging) and is refused by some
    images' policy, while screen_off_timeout is a plain setting. Neither generates
    traffic, so a capture is unaffected. On a physical device this does change a
    user-visible setting, which is why it is logged.
    """
    try:
        adb.shell("svc power stayon true", timeout=60)
        adb.shell("settings put system screen_off_timeout 1800000", timeout=60)
        adb.shell("input keyevent KEYCODE_WAKEUP", timeout=60)
        state = adb.shell("dumpsys power | grep -m1 mWakefulness=", timeout=60).strip()
        log("display kept awake for this run (%s)" % (state or "wakefulness unknown"))
    except Exception as e:
        # Never fatal: a check that then fails on a dark screen reports its own
        # failure, which is a truthful result. Silently skipping would not be.
        log("WARNING: could not keep the display awake (%s); checks that idle may "
            "fail their positive controls" % e)


class App:
    def __init__(self, adb, pkg, work):
        self.adb, self.pkg, self.work = adb, pkg, work
        self.host_port = None
        self.uid = None
        self.extra_prefs = {}
        self._debuggable = None
        self._set_debug_app = False
    def install(self, apk, preserve_state=False):
        log("installing %s (%.0f MB)" % (os.path.basename(apk), os.path.getsize(apk) / 1e6))
        # -d allows a version DOWNGRADE. versionCode is derived from the build
        # timestamp, so it moves every Gradle run: testing a variant build (say one
        # carrying an update-check key) and then re-testing the shipping APK is a
        # downgrade, and without -d adb refuses with INSTALL_FAILED_VERSION_DOWNGRADE.
        # A smoke harness tests whichever artifact it is pointed at, in any order;
        # monotonic versions are a store's concern, not a test device's.
        p = self.adb.run("install", "-r", "-d", apk, timeout=900)
        # A rebuilt APK is usually signed by a DIFFERENT debug keystore: the build
        # image ships none, so each container generates its own (REPRODUCIBLE.md).
        # `adb install -r` then refuses with INSTALL_FAILED_UPDATE_INCOMPATIBLE
        # against the copy an earlier run left on the AVD, and because the AVD
        # persists in the work directory this hits every check on the first run
        # after any rebuild -- eight of them in a row on 2026-09-06, each reported
        # as "the harness could not run" with no hint that one uninstall fixes it.
        # Uninstalling is safe here: the harness wipes app data anyway (`--keep-state`
        # aside), so there is no state to preserve that a reinstall would not clear.
        blocked_by_existing = ("INSTALL_FAILED_UPDATE_INCOMPATIBLE",
                               "INSTALL_FAILED_VERSION_DOWNGRADE",
                               "INSTALL_FAILED_ALREADY_EXISTS")
        hit = next((e for e in blocked_by_existing if e in (p.stdout + p.stderr)), None)
        if hit:
            if preserve_state:
                raise HarnessError("adb install refused (%s); preserving existing app data. "
                                   "A state-preservation test must not uninstall the app." % hit)
            log("install refused (%s) because of the copy an earlier run left on this "
                "device; uninstalling %s and installing again" % (hit, self.pkg))
            self.adb.run("uninstall", self.pkg, timeout=300)
            p = self.adb.run("install", "-r", "-d", apk, timeout=900)
        if "Success" not in p.stdout:
            raise HarnessError("adb install failed: %s%s" % (p.stdout, p.stderr))
        if self.pkg not in self.adb.shell("pm list packages %s" % self.pkg, timeout=60):
            raise HarnessError("package %s is not present after install -- wrong applicationId?"
                               % self.pkg)
        self.uid = self.adb.shell("stat -c %%u /data/data/%s" % self.pkg, timeout=60).strip()
        # Start from an empty crash buffer, or a crash left by an earlier run
        # would be reported against this one.
        self.adb.run("logcat", "-b", "crash", "-c", timeout=60)
    def wipe(self):
        result = self.adb.run("shell", "pm", "clear", self.pkg, timeout=180, check=True)
        if result.stdout.strip() != "Success":
            raise HarnessError("pm clear did not confirm an empty app profile: %s%s"
                               % (result.stdout, result.stderr))
    def debuggable(self):
        """Is the INSTALLED package flagged debuggable?  Read from the package
        manager, never from the APK path or the build command."""
        if self._debuggable is None:
            out = self.adb.shell("dumpsys package %s | grep flags=" % self.pkg, timeout=60)
            self._debuggable = "DEBUGGABLE" in out
        return self._debuggable
    def push_debug_config(self):
        cfg = os.path.join(self.work, "geckoview-config.yaml")
        body = GV_CONFIG
        for k, v in sorted(self.extra_prefs.items()):
            body += "  %s: %s\n" % (k, json.dumps(v))
        with open(cfg, "w") as f:
            f.write(body)
        dst = "/data/local/tmp/%s-geckoview-config.yaml" % self.pkg
        self.adb.run("push", cfg, dst, timeout=60, check=True)
        self.adb.shell("chmod 644 " + dst, timeout=30)
        # GeckoRuntime.java:509 reads that file when the app is FLAG_DEBUGGABLE
        # **or** when it is the package named in Settings.Global.DEBUG_APP
        # (isApplicationCurrentDebugApp, :603-609).  A release-configured APK is
        # not debuggable, so without the second door the whole Marionette channel
        # is unavailable against the only build type LibreWolf ships -- which is
        # what left --check-aboutconfig with no runnable path.  set-debug-app does
        # NOT make the app debuggable: `dumpsys package` flags are unchanged, the
        # build type and Config.channel are unchanged, and `run-as` still refuses.
        # It only opens the debug-config door.  Cleared again in
        # remove_debug_config(), which main()'s finally always reaches.
        if not self.debuggable():
            self.adb.shell("am set-debug-app --persistent %s" % self.pkg, timeout=60)
            self._set_debug_app = True
            log("%s is not debuggable; opened GeckoView's debug config via "
                "Settings.Global.DEBUG_APP (am set-debug-app)" % self.pkg)
    def remove_debug_config(self):
        self.adb.shell("rm -f /data/local/tmp/%s-geckoview-config.yaml" % self.pkg, timeout=60)
        if self._set_debug_app:
            self.adb.shell("am clear-debug-app", timeout=60)
            self._set_debug_app = False

    def force_stop(self):
        self.adb.shell("am force-stop %s" % self.pkg, timeout=60)
    def start_home(self):
        self.adb.shell("am start -n %s/org.mozilla.fenix.HomeActivity" % self.pkg, timeout=90)
    def start_url(self, url):
        self.adb.shell("am start -a android.intent.action.VIEW -d '%s' "
                       "-n %s/org.mozilla.fenix.IntentReceiverActivity" % (url, self.pkg),
                       timeout=90)
    def guest_ips(self):
        out = self.adb.shell("ip -o -4 addr", timeout=60)
        ips = set(re.findall(r"inet (\d+\.\d+\.\d+\.\d+)/", out))
        out6 = self.adb.shell("ip -o -6 addr", timeout=60)
        ips.update(re.findall(r"inet6 ([0-9a-fA-F:]+)/", out6))
        ips.discard("127.0.0.1")
        ips.discard("::1")
        if not ips:
            raise HarnessError("could not read the device's own IPv4 addresses; "
                               "without them the capture cannot tell a request from a reply")
        # An AVD can acquire wlan0 after radio0 and route the search through its
        # new address. Keep both ends of every window, including retired IPs.
        self._guest_ip_history = getattr(self, "_guest_ip_history", set()) | ips
        return set(self._guest_ip_history)

    def alive(self):
        return bool(self.adb.shell("pidof %s" % self.pkg, timeout=30).strip())
    def crashed(self):
        out = self.adb.out("logcat", "-d", "-b", "crash", timeout=60)
        return self.pkg in out
    def rx_tx(self):
        """Cumulative bytes for this app's uid, from the kernel's own accounting."""
        if not self.uid:
            self.uid = self.adb.shell("stat -c %%u /data/data/%s" % self.pkg, timeout=60).strip()
        out = self.adb.out("shell", "dumpsys", "netstats", "detail", "--uid", timeout=120)
        rb = tb = 0
        take = False
        for line in out.splitlines():
            if "ident=[" in line:
                # Only the untagged (tag=0x0) buckets, or tagged traffic would
                # be double counted on top of the untagged total.
                take = bool(re.search(r"uid=%s " % re.escape(self.uid), line)) and "tag=0x0" in line
                continue
            if take:
                m = re.search(r"rb=(\d+) rp=\d+ tb=(\d+)", line)
                if m:
                    rb += int(m.group(1))
                    tb += int(m.group(2))
        return rb, tb
    def connect_marionette(self, timeout=180):
        self.host_port = free_port()
        self.adb.run("forward", "tcp:%d" % self.host_port, "tcp:2828", timeout=60, check=True)
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            m = None
            try:
                m = Marionette(self.host_port)
                m.cmd("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {}}})
                return m
            except Exception as e:
                if m:
                    m.close()
                last = e
                time.sleep(3)
        # Preserve the actual app state before outer cleanup or another suite
        # clears it. A failed automation connection is not a browser verdict.
        for name, command in (
                ("marionette-timeout-logcat.txt", ("logcat", "-d")),
                ("marionette-timeout-ui.txt", ("shell", "uiautomator", "dump", "/dev/tty"))):
            try:
                output = self.adb.out(*command, timeout=30)
                with open(os.path.join(self.work, name), "w") as f:
                    f.write(output)
            except Exception as diagnostic_error:
                log("could not save %s: %s" % (name, diagnostic_error))
        raise HarnessError("could not open a Marionette session on %s within %ds (%s). "
                           "Is this a debuggable build? The harness needs GeckoView's debug "
                           "config at /data/local/tmp/%s-geckoview-config.yaml to take effect."
                           % (self.pkg, timeout, last, self.pkg))

def open_session(app, url):
    """Start the app on a page and return a live Marionette session.
    Marionette's NewSession blocks until a Gecko window exists, and the Fenix
    home screen is not one -- so we always open a tab first."""
    app.push_debug_config()
    app.force_stop()
    time.sleep(1)
    app.start_url(url)
    m = app.connect_marionette()
    m.cmd("WebDriver:SetTimeouts", {"script": 60000, "pageLoad": 120000})
    return m

# --------------------------------------------------------------------------
# The probes
# --------------------------------------------------------------------------
JS_WEBGL = r"""
var out = {ok:false, stage:"start", creationErrors:[]};
try {
  var c = document.createElement("canvas"); c.width = 32; c.height = 32;
  c.addEventListener("webglcontextcreationerror",
    function(e){ out.creationErrors.push(String(e.statusMessage)); }, false);
  var gl = c.getContext("webgl2") || c.getContext("webgl") || c.getContext("experimental-webgl");
  out.stage = "getContext";
  if (!gl) { out.reason = "getContext returned null"; return out; }
  out.contextType = (typeof WebGL2RenderingContext !== "undefined" &&
                     gl instanceof WebGL2RenderingContext) ? "webgl2" : "webgl";
  out.vendor = gl.getParameter(gl.VENDOR);
  out.renderer = gl.getParameter(gl.RENDERER);
  out.version = gl.getParameter(gl.VERSION);
  var vs = gl.createShader(gl.VERTEX_SHADER);
  gl.shaderSource(vs, "attribute vec2 p; void main(){ gl_Position = vec4(p,0.0,1.0); }");
  gl.compileShader(vs);
  if (!gl.getShaderParameter(vs, gl.COMPILE_STATUS)) {
    out.reason = "vertex shader: " + gl.getShaderInfoLog(vs); return out; }
  var fs = gl.createShader(gl.FRAGMENT_SHADER);
  gl.shaderSource(fs, "precision mediump float; void main(){ gl_FragColor = vec4(0.2,0.4,0.6,1.0); }");
  gl.compileShader(fs);
  if (!gl.getShaderParameter(fs, gl.COMPILE_STATUS)) {
    out.reason = "fragment shader: " + gl.getShaderInfoLog(fs); return out; }
  var pr = gl.createProgram();
  gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
  if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) {
    out.reason = "link: " + gl.getProgramInfoLog(pr); return out; }
  gl.useProgram(pr);
  var buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
  var loc = gl.getAttribLocation(pr, "p");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  gl.viewport(0,0,32,32);
  gl.clearColor(0,0,0,1); gl.clear(gl.COLOR_BUFFER_BIT);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
  var px = new Uint8Array(4);
  gl.readPixels(16,16,1,1, gl.RGBA, gl.UNSIGNED_BYTE, px);
  out.pixel = [px[0],px[1],px[2],px[3]];
  out.glError = gl.getError();
  c.id = "lw-smoke-webgl-render";
  c.style.cssText = "position:fixed;left:0;top:0;width:128px;height:128px;z-index:2147483647";
  document.body.appendChild(c);
  out.stage = "readPixels";
  out.ok = true;
} catch (e) { out.reason = "exception: " + e; }
return out;
"""

def png_center_pixel(png):
    """Decode an 8-bit RGB/RGBA WebDriver screenshot with the standard library."""
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise HarnessError("WebDriver screenshot is not a PNG")
    pos, compressed, header = 8, bytearray(), None
    while pos + 12 <= len(png):
        size = struct.unpack(">I", png[pos:pos + 4])[0]
        kind, data = png[pos + 4:pos + 8], png[pos + 8:pos + 8 + size]
        if len(data) != size:
            raise HarnessError("truncated screenshot PNG")
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", data)
        elif kind == b"IDAT":
            compressed.extend(data)
        pos += size + 12
        if kind == b"IEND":
            break
    if not header:
        raise HarnessError("screenshot has no PNG image header")
    width, height, depth, color, compression, filtering, interlace = header
    if (not width or not height or depth != 8 or color not in (2, 6) or
            compression or filtering or interlace):
        raise HarnessError("unsupported screenshot PNG format: %r" % (header,))
    channels = 4 if color == 6 else 3
    stride = width * channels
    raw = zlib.decompress(compressed)
    if len(raw) != (stride + 1) * height:
        raise HarnessError("screenshot pixel data is incomplete")
    previous = bytearray(stride)
    for y in range(height // 2 + 1):
        offset = y * (stride + 1)
        method = raw[offset]
        row = bytearray(raw[offset + 1:offset + 1 + stride])
        if method not in range(5):
            raise HarnessError("unknown PNG row filter")
        for x in range(stride):
            a = row[x - channels] if x >= channels else 0
            b = previous[x]
            c = previous[x - channels] if x >= channels else 0
            if method == 1: predictor = a
            elif method == 2: predictor = b
            elif method == 3: predictor = (a + b) // 2
            elif method == 4:
                p = a + b - c
                distances = (abs(p - a), abs(p - b), abs(p - c))
                predictor = (a, b, c)[distances.index(min(distances))]
            else: predictor = 0
            row[x] = (row[x] + predictor) & 255
        previous = row
    pixel = list(previous[(width // 2) * channels:(width // 2 + 1) * channels])
    return pixel if channels == 4 else pixel + [255]

def check_webgl(m, res, forcefail=False):
    """Compile, draw and verify composited pixels without bypassing RFP.

    readPixels intentionally returns placeholder data when canvas extraction
    is blocked. WebDriver's privileged element screenshot sees the actual
    rendered canvas; no content permission or privacy pref is changed.
    """
    lw = m.script('return {prompt: Services.prefs.getPrefType("librewolf.webgl.prompt") ? '
                  'Services.prefs.getBoolPref("librewolf.webgl.prompt") : null, '
                  'type: Services.prefs.getPrefType("librewolf.webgl.prompt"), '
                  'locked: Services.prefs.prefIsLocked("librewolf.webgl.prompt")};', chrome=True)
    r = m.script(JS_WEBGL)
    expect = [51, 102, 153, 255] if not forcefail else [1, 2, 3, 4]
    rendered = None
    try:
        if r.get("ok") and r.get("glError") == 0:
            element = m.script('return document.getElementById("lw-smoke-webgl-render");')
            element_id = element["element-6066-11e4-a52e-4f735466cecf"]
            screenshot = m.cmd("WebDriver:TakeScreenshot", {"id": element_id, "full": False})
            png = base64.b64decode(screenshot["value"])
            with open(os.path.join(WORK, "webgl-render.png"), "wb") as f:
                f.write(png)
            rendered = png_center_pixel(png)
    finally:
        m.script('document.getElementById("lw-smoke-webgl-render")?.remove(); return true;')
    ok = bool(r.get("ok")) and r.get("glError") == 0 and rendered == expect
    if lw.get("type") == 0:
        ok = False
        why = ("librewolf.webgl.prompt DOES NOT EXIST in this build -- the L1 guard is gone. "
               "See docs/android/AGENTS.md landmine L1.")
    elif lw.get("prompt") is True:
        ok = False
        why = ("librewolf.webgl.prompt is TRUE on Android -- this is landmine L1 and every "
               "WebGL context in the build is dead. Pixel readback: %s" % (r.get("pixel"),))
    elif ok:
        why = "%s ctx, shader+draw composited %s; protected readPixels=%s, renderer=%r" % (
            r.get("contextType"), rendered, r.get("pixel"), r.get("renderer"))
    else:
        why = ("no verified rendered pixel (stage=%s reason=%s creationErrors=%s rendered=%s). "
               "librewolf.webgl.prompt=%s" % (
                   r.get("stage"), r.get("reason"), r.get("creationErrors"),
                   rendered, lw.get("prompt")))
    res.add("webgl", ok, why, {"gl": r, "composited_pixel": rendered,
                               "librewolf.webgl.prompt": lw})
    return ok

JS_VIDEO = r"""
var done = arguments[arguments.length-1];
var out = {events: [], ok: false};
var v = document.getElementById("v");
if (!v) { out.reason = "probe page has no <video>"; done(out); return; }
v.loop = true;
["error","stalled","abort","emptied"].forEach(function(n){
  v.addEventListener(n, function(){
    out.events.push(n + (v.error ? (":" + v.error.code + ":" + v.error.message) : ""));
  });
});
var t0 = Date.now(), startTime = v.currentTime;
v.play().then(function(){ out.play = "resolved"; }, function(e){ out.play = "rejected: " + e; });
var iv = setInterval(function(){
  out.currentTime = v.currentTime;
  out.readyState = v.readyState;
  out.videoWidth = v.videoWidth;
  out.videoHeight = v.videoHeight;
  out.paused = v.paused;
  out.decoded = v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality().totalVideoFrames : null;
  out.dropped = v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality().droppedVideoFrames : null;
  out.mediaError = v.error ? (v.error.code + ":" + v.error.message) : null;
  var advanced = (v.currentTime - startTime) > 0.25;
  if (v.readyState >= 3 && advanced && out.decoded >= 4) { out.ok = true; }
  if (out.ok || Date.now() - t0 > 30000) { clearInterval(iv); v.pause(); done(out); }
}, 250);
"""

WEBDRIVER_ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"

def click_page(m, css="#marker"):
    """A real click, so the document has user activation.  Measured: without
    this, three otherwise identical runs gave two passes and one
    `play() -> NotAllowedError` with zero decoded frames, on a build whose
    media.autoplay.default was 1 and blocking_policy 0 -- i.e. the block was
    not explained by the prefs and the probe was simply racy.  With the click,
    three consecutive runs passed.  A flaky check is a check nobody believes,
    so the gesture is not optional."""
    el = m.cmd("WebDriver:FindElement", {"using": "css selector", "value": css})
    m.cmd("WebDriver:ElementClick", {"id": el["value"][WEBDRIVER_ELEMENT_KEY]})

def check_video(m, res, origin, forcefail=False):
    since = time.time()
    autoplay = m.script('return {default: Services.prefs.getIntPref("media.autoplay.default", -1), '
                        'policy: Services.prefs.getIntPref("media.autoplay.blocking_policy", -1)};',
                        chrome=True)
    m.cmd("Marionette:SetContext", {"value": "content"})
    click_page(m)
    r = m.async_script(JS_VIDEO)
    r["autoplay_prefs"] = autoplay
    served = origin.got("/fixture.webm", since - 30)
    ok = bool(r.get("ok")) and bool(served) and not forcefail
    why = ("decoded %s frames, currentTime=%.3f readyState=%s %sx%s, origin served the file %d time(s)"
           % (r.get("decoded"), r.get("currentTime") or 0, r.get("readyState"),
              r.get("videoWidth"), r.get("videoHeight"), len(served))) if ok else (
          "no proof of decoding: %s (origin served the file %d time(s))"
          % (json.dumps(r)[:400], len(served)))
    res.add("video", ok, why, {"video": r, "origin_requests": len(served)})
    return ok

JS_GUM = r"""
var done = arguments[arguments.length-1];
var out = {t0: Date.now()};
out.hasMediaDevices = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
out.hasRTCPeerConnection = (typeof RTCPeerConnection !== "undefined");
if (!out.hasMediaDevices) { out.state = "no-api"; done(out); return; }
navigator.mediaDevices.getUserMedia({audio: true, video: true}).then(function(s){
  out.state = "granted";
  out.tracks = s.getTracks().map(function(t){ return t.kind + ":" + t.readyState; });
  s.getTracks().forEach(function(t){ t.stop(); });
  out.ms = Date.now() - out.t0; done(out);
}, function(e){
  out.state = "rejected"; out.error = e.name; out.message = String(e.message);
  out.ms = Date.now() - out.t0; done(out);
});
"""

# A getUserMedia call on a fresh profile raises TWO kinds of dialog, in order:
# Android's own runtime-permission grant dialog (camera, then microphone), and
# Fenix's site-permission doorhanger.  Both have to be answered or the promise
# never settles and the harness cannot tell "asked the user" from "hung".
DENY_BUTTON_IDS = (
    "com.android.permissioncontroller:id/permission_deny_button",
    "com.android.permissioncontroller:id/permission_deny_and_dont_ask_again_button",
    "com.android.packageinstaller:id/permission_deny_button",
    ":id/deny_button",
)

class PromptTapper(threading.Thread):
    """Answers permission dialogs from outside the browser, the way a user
    would.  Runs while the gUM promise is in flight, because Marionette can
    only carry one command at a time."""
    def __init__(self, adb, button_ids=DENY_BUTTON_IDS):
        super().__init__(daemon=True)
        self.adb, self.button_ids = adb, button_ids
        self.seen = False
        self.taps = 0
        self.dialogs = []
        self.stop_flag = False
        self.error = None
    def run(self):
        while not self.stop_flag:
            try:
                self.adb.shell("uiautomator dump /sdcard/lw-smoke-ui.xml", timeout=60)
                xml = self.adb.shell("cat /sdcard/lw-smoke-ui.xml", timeout=60)
                for bid in self.button_ids:
                    m = re.search(r'resource-id="([^"]*%s)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                                  % re.escape(bid), xml)
                    if not m:
                        continue
                    self.seen = True
                    if m.group(1) not in self.dialogs:
                        self.dialogs.append(m.group(1))
                    x = (int(m.group(2)) + int(m.group(4))) // 2
                    y = (int(m.group(3)) + int(m.group(5))) // 2
                    self.adb.shell("input tap %d %d" % (x, y), timeout=60)
                    self.taps += 1
                    break
            except Exception as e:
                self.error = str(e)
            time.sleep(1.0)

def check_gum(m, res, app, adb, forcefail=False):
    """The requirement is to distinguish a denial from a hang from a crash.
    Denial is a pass; a prompt that is never answered is not evidence either
    way, so the harness answers it and then insists the promise settles."""
    tapper = PromptTapper(adb)
    tapper.start()
    r, timed_out = None, False
    try:
        r = m.async_script(JS_GUM)
    except MarionetteError as e:
        if e.name in ("script timeout", "timeout"):
            timed_out = True
        else:
            raise
    finally:
        tapper.stop_flag = True
        time.sleep(1.2)
    alive = app.alive()
    crashed = app.crashed()
    if timed_out or (r or {}).get("state") is None:
        if crashed or not alive:
            verdict, ok = "CRASH: the content or parent process died during getUserMedia", False
        else:
            verdict, ok = ("HANG: getUserMedia never settled and the app is still alive "
                           "(prompt seen=%s, taps=%d)" % (tapper.seen, tapper.taps)), False
    elif r["state"] == "granted":
        ok = not forcefail
        verdict = "granted, tracks=%s in %sms (prompt seen=%s)" % (r.get("tracks"), r.get("ms"), tapper.seen)
    elif r["state"] == "rejected":
        ok = (not forcefail) and tapper.seen
        verdict = ("prompt(s) raised %s, harness tapped deny %d time(s), getUserMedia rejected "
                   "with %s in %sms" % (tapper.dialogs, tapper.taps, r.get("error"), r.get("ms"))
                   ) if tapper.seen else (
                   "rejected with %s in %sms but NO permission prompt was ever shown -- a "
                   "privacy browser must ask before it answers" % (r.get("error"), r.get("ms")))
    else:
        ok, verdict = False, "getUserMedia unavailable: %s" % json.dumps(r)[:300]
    res.add("getusermedia", ok, verdict,
            {"gum": r, "prompt_seen": tapper.seen, "taps": tapper.taps,
             "dialogs": tapper.dialogs, "alive": alive, "crashed": crashed})
    return ok

def grade_https_interstitial(prefs, info):
    return (prefs.get("enabled") is True and prefs.get("locked") is False
            and info.get("ready") == "complete" and info.get("marker") is None
            and info.get("continueVisible") is True and info.get("canAddException") is True)

def check_https_only(m, res, http_url, forcefail=False):
    prefs = m.script('return {enabled:Services.prefs.getBoolPref("dom.security.https_only_mode", false), '
                     'locked:Services.prefs.prefIsLocked("dom.security.https_only_mode")};', chrome=True)
    m.cmd("Marionette:SetContext", {"value":"content"})
    navigation_error = None
    try:
        m.cmd("WebDriver:Navigate", {"url":http_url})
    except MarionetteError as error:
        # Reaching a browser error page is expected. It must be the HTTPS-only
        # interstitial with its real exception control, not any navigation error.
        navigation_error = str(error)
    probe = r"""
      const b = document.getElementById("continueHttp");
      return {url:location.href, uri:document.documentURI, title:document.title,
              ready:document.readyState,
              marker:(document.getElementById("marker")||{}).textContent || null,
              continueVisible:!!b && b.getClientRects().length > 0,
              canAddException:typeof document.reloadWithHttpsOnlyException === "function"};
    """
    info = {}
    for _attempt in range(60):
        try:
            info = m.script(probe) or {}
            if info.get("ready") == "complete" and (
                info.get("marker") is not None or info.get("continueVisible") is True
            ):
                break
        except MarionetteError as error:
            if "Document was unloaded" not in str(error):
                raise
            info = {"transient_error":str(error)}
        time.sleep(0.25)
    enforced = grade_https_interstitial(prefs, info)
    res.add("https-only-interstitial", enforced and not forcefail,
            "HTTP must reach the HTTPS-only interstitial before the user grants an exception",
            {"prefs":prefs, "page":info, "navigation_error":navigation_error})
    if enforced:
        # A real user action, without setting a pref or adding a permission from
        # chrome script. The following HTTP page-load is the positive control.
        click_page(m, "#continueHttp")
        wait_for_initial_document(m, http_url)
    return enforced and not forcefail

def check_pageload(m, res, origin, http_url, https_url, forcefail=False):
    http_url += "?https-only-" + os.urandom(8).hex()
    ok_all = check_https_only(m, res, http_url, forcefail)
    for label, url, want_secure in (("page-load-http", http_url, False),
                                    ("page-load-https", https_url, True)):
        since = time.time()
        try:
            m.cmd("WebDriver:Navigate", {"url": url})
            info = m.script(
                'return {url: location.href, proto: location.protocol, '
                'secure: window.isSecureContext, ready: document.readyState, '
                'marker: (document.getElementById("marker")||{}).textContent, '
                'title: document.title};')
        except MarionetteError as e:
            res.add(label, False, "navigation failed: %s" % e)
            ok_all = False
            continue
        served = origin.got("/", since - 5)
        ok = (info.get("marker") == "lw-smoke-page-ok"
              and info.get("ready") == "complete"
              and bool(served)
              and info.get("secure") == want_secure
              and not forcefail)
        res.add(label, ok,
                "%s ready=%s secure=%s marker=%r, origin logged %d request(s)"
                % (info.get("url"), info.get("ready"), info.get("secure"),
                   info.get("marker"), len(served)),
                {"page": info, "origin_requests": len(served)})
        ok_all = ok_all and ok
    return ok_all

def check_extension(m, res, xpi_b64, https_url, forcefail=False):
    try:
        addon_id = m.cmd("Addon:Install", {"addon": xpi_b64, "temporary": True}).get("value")
    except MarionetteError as e:
        res.add("extension", False, "install rejected: %s" % e)
        return False
    try:
        m.cmd("WebDriver:Navigate", {"url": https_url + "?ext"})
        marker = m.script('return document.documentElement.getAttribute("data-lw-smoke-ext");')
        listed = m.script(r"""
          const done = arguments[arguments.length-1];
          return (async () => {
            const { AddonManager } = ChromeUtils.importESModule(
              "resource://gre/modules/AddonManager.sys.mjs");
            const all = await AddonManager.getAllAddons();
            return all.filter(a => a.type === "extension")
                      .map(a => ({id: a.id, name: a.name, active: a.isActive}));
          })();
        """, chrome=True)
        m.cmd("Marionette:SetContext", {"value": "content"})
        ok = (marker or "").startswith("alive-webext") and not forcefail
        why = ("installed %s and its content script ran on a real page (marker=%r); "
               "%d extensions active" % (addon_id, marker, len(listed or [])))
        if not ok:
            why = ("installed %s but its content script left no marker (marker=%r) -- "
                   "an extension that installs and does not run is not a working extension"
                   % (addon_id, marker))
        res.add("extension", ok, why, {"id": addon_id, "marker": marker, "addons": listed})
        return ok
    finally:
        try:
            m.cmd("Marionette:SetContext", {"value": "content"})
            m.cmd("Addon:Uninstall", {"id": addon_id})
        except Exception:
            pass

# --------------------------------------------------------------------------
# Pref dump
# --------------------------------------------------------------------------
# A fixed, curated list.  Fixed because LW-M3-05 diffs this output against a
# checked-in baseline, and a list that grows with the build would make every
# rebase a spurious diff.  Curated to prefs whose value is a security or
# privacy decision and is stable across profiles -- nothing with a client id,
# a timestamp or a random token in it.
PREF_LIST = [
    # landmine L1 and the WebGL family
    "librewolf.webgl.prompt", "librewolf.webgl.prompt.hide", "webgl.disabled",
    # fingerprinting
    "privacy.resistFingerprinting", "privacy.resistFingerprinting.pbmode",
    "privacy.fingerprintingProtection", "privacy.fingerprintingProtection.pbmode",
    "privacy.trackingprotection.enabled", "privacy.trackingprotection.fingerprinting.enabled",
    "privacy.trackingprotection.cryptomining.enabled",
    "privacy.donottrackheader.enabled", "privacy.globalprivacycontrol.enabled",
    "privacy.query_stripping.enabled",
    # cookies and storage isolation
    "network.cookie.cookieBehavior", "privacy.partition.network_state",
    # process isolation -- LW-M5-01 lives here
    "fission.autostart", "fission.webContentIsolationStrategy",
    # dns / speculative connections
    "network.dns.disablePrefetch", "network.predictor.enabled", "network.prefetch-next",
    "network.http.speculative-parallel-limit", "network.trr.mode", "network.trr.uri",
    "doh-rollout.enabled",
    # safebrowsing -- the Google endpoints
    "browser.safebrowsing.malware.enabled", "browser.safebrowsing.phishing.enabled",
    "browser.safebrowsing.downloads.remote.enabled",
    "browser.safebrowsing.provider.google4.updateURL",
    "browser.safebrowsing.provider.google4.gethashURL",
    # telemetry and data reporting -- LW-M4-01
    "toolkit.telemetry.enabled", "toolkit.telemetry.unified",
    "toolkit.telemetry.archive.enabled", "toolkit.telemetry.server",
    "datareporting.healthreport.uploadEnabled", "datareporting.policy.dataSubmissionEnabled",
    "app.shield.optoutstudies.enabled",
    # remote settings and suggestions -- LW-M4-08 / LW-M4-11
    "services.settings.server", "browser.search.suggest.enabled",
    "browser.search.update", "extensions.getAddons.showPane",
    # extensions
    "xpinstall.signatures.required", "extensions.blocklist.enabled",
    "extensions.webextensions.restrictedDomains",
    # tls / certificates
    "security.OCSP.require", "security.ssl.require_safe_negotiation",
    "security.enterprise_roots.enabled", "security.remote_settings.crlite_filters.enabled",
    # media and rtc
    "media.peerconnection.enabled", "media.peerconnection.ice.default_address_only",
    "media.eme.enabled", "media.gmp-gmpopenh264.enabled",
    # misc surface
    "dom.security.https_only_mode", "geo.enabled", "browser.contentblocking.category",
    "devtools.debugger.remote-enabled", "app.update.auto",
    # the autoconfig canary (LW-M3-08/LW-M3-11): lockPref'd by common.cfg, so a
    # build whose packaged librewolf.cfg failed to evaluate reads "missing" here,
    # and the one pref LW-M3-04's review moved to a real lock on Android.
    "librewolf.cfg.version", "network.lna.block_trackers",
]

JS_PREFDUMP = r"""
var names = arguments[0];
var out = [];
for (var i = 0; i < names.length; i++) {
  var n = names[i], t = Services.prefs.getPrefType(n), type = "missing", value = null;
  try {
    if (t === Services.prefs.PREF_BOOL)   { type = "bool";   value = Services.prefs.getBoolPref(n); }
    else if (t === Services.prefs.PREF_INT){ type = "int";    value = Services.prefs.getIntPref(n); }
    else if (t === Services.prefs.PREF_STRING) { type = "string"; value = Services.prefs.getStringPref(n); }
  } catch (e) { type = "error"; value = String(e); }
  out.push({name: n, type: type, value: value,
            locked: (t === 0 ? false : Services.prefs.prefIsLocked(n)),
            user: (t === 0 ? false : Services.prefs.prefHasUserValue(n))});
}
return out;
"""

JS_ALLPREFS = r"""
var out = {};
var names = Services.prefs.getChildList("");
for (var i = 0; i < names.length; i++) {
  var n = names[i], t = Services.prefs.getPrefType(n);
  try {
    if (t === Services.prefs.PREF_BOOL) out[n] = Services.prefs.getBoolPref(n);
    else if (t === Services.prefs.PREF_INT) out[n] = Services.prefs.getIntPref(n);
    else if (t === Services.prefs.PREF_STRING) out[n] = Services.prefs.getStringPref(n);
  } catch (e) {}
}
return out;
"""

# Prefs the harness itself sets, via the GeckoView debug config.  They are
# excluded from PREF_LIST on purpose; this constant exists so the harness can
# assert that overlap stays empty rather than trusting that it does.
HARNESS_SET_PREFS = ("remote.prefs.recommended", "marionette.port")

def do_pref_dump(m, work):
    overlap = set(PREF_LIST) & set(HARNESS_SET_PREFS)
    if overlap:
        raise HarnessError("the pref dump would report prefs the harness itself sets: %s"
                           % sorted(overlap))
    rows = m.script(JS_PREFDUMP, [PREF_LIST], chrome=True)
    lines = ["# librewolf-android-smoke pref-dump v1",
             "# name\ttype\tvalue\tlocked\tuser"]
    for r in sorted(rows, key=lambda r: r["name"]):
        v = r["value"]
        if isinstance(v, bool):
            v = "true" if v else "false"
        elif v is None:
            v = ""
        lines.append("%s\t%s\t%s\t%s\t%s" % (r["name"], r["type"], v,
                                             "locked" if r["locked"] else "-",
                                             "user" if r["user"] else "-"))
    text = "\n".join(lines) + "\n"
    path = os.path.join(work, "prefs.txt")
    with open(path, "w") as f:
        f.write(text)
    allprefs = m.script(JS_ALLPREFS, chrome=True)
    with open(os.path.join(work, "prefs-all.json"), "w") as f:
        json.dump(allprefs, f, indent=1, sort_keys=True)
    log("pref dump: %d curated prefs -> %s ; %d total prefs -> %s"
        % (len(rows), path, len(allprefs), os.path.join(work, "prefs-all.json")))
    return text, rows

# --------------------------------------------------------------------------
# Network capture
# --------------------------------------------------------------------------
def require_pcap(pcap):
    if not pcap or not os.path.exists(pcap):
        raise HarnessError(
            "no packet capture available. The capture is taken at the emulator's virtual NIC "
            "with 'emulator -tcpdump', so the harness must be the one that started the "
            "emulator: re-run with --emulator, or point LW_SMOKE_PCAP at the pcap of an "
            "emulator you started with -tcpdump yourself. Refusing to report an empty "
            "capture as a clean one.")

def summarise_capture(pcap, start_offset, harness_ports=(), guest_ips=()):
    """Outbound events only.  guest_ips comes from the device itself, so a
    packet counts as outbound exactly when the guest sent it."""
    rows = []
    for (ts, kind, detail, src, dst, port) in pcap_events(pcap, start_offset):
        if guest_ips and src not in guest_ips:
            continue
        harness = (dst == "10.0.2.2" and port in harness_ports)
        rows.append({"ts": ts, "kind": kind, "detail": detail, "src": src, "dst": dst,
                     "port": port, "harness": harness,
                     "os_noise": (not harness) and is_os_noise(kind, detail, dst, port)})
    return rows

def render_capture(rows):
    out = []
    for r in rows:
        out.append("%s\t%s\t%s\t%s:%d\t%s" % (
            time.strftime("%H:%M:%S", time.localtime(r["ts"])), r["kind"],
            r["detail"] or "-", r["dst"], r["port"],
            "harness-origin" if r.get("harness") else
            ("os-noise" if r["os_noise"] else "app-or-unknown")))
    return "\n".join(out) + ("\n" if out else "")

# --------------------------------------------------------------------------
# APK static checks
# --------------------------------------------------------------------------
def scan_apk(apk, needles):
    hits = {}
    for s in apk_dex_strings(apk):
        for n in needles:
            if n in s:
                hits.setdefault(n, set()).add(s[:120])
    entries = apk_entries(apk)
    return hits, entries

# --------------------------------------------------------------------------
# --check-no-gms  (LW-M4-05 does the removal; LW-M4-16 owns this contract)
#
# The gate is ZERO com.google.android.gms, and it has never been relaxed to a
# count.  Two strings nonetheless survive in the DEBUG artefact this repo
# builds, and this is the contract under which they -- and only they -- do not
# fail the build.  Read all of it before touching the constants below.
#
# WHAT THE TWO STRINGS ARE.  They are the VALUES of two static final fields,
#     GMS_ACTION_PICK_IMAGES  = "com.google.android.gms.provider.action.PICK_IMAGES"
#     GMS_EXTRA_PICK_IMAGES_MAX = "com.google.android.gms.provider.extra.PICK_IMAGES_MAX"
# on androidx.activity's ActivityResultContracts$PickVisualMedia.  They enter
# the APK inside a PREBUILT Maven class file.  There is no manifest attribute,
# no ProGuard keep rule, no resource and no source file of ours that carries
# them, so there is nothing for patches/android/no-gms.patch to delete: route
# "remove at source" is unavailable without vendoring a fork of an AndroidX
# core artifact.
#
# WHY A BARE ALLOWLIST OF THOSE TWO STRINGS IS NOT ENOUGH -- and this is the
# part that got two previous attempts rejected.  A verifier broke the string
# allowlist with a REAL artefact: androidx.activity 1.8.2, where getGmsPicker
# is LIVE CODE that hands off to the Play Services photo picker.  That live
# path references NO Lcom/google/android/gms/ descriptor at all; the same two
# string literals are its only trace.  So string-identical, behaviour-opposite:
# an allowlist keyed on the strings passes the version that actually calls Play
# Services.  Naming the strings does not make the exemption safe.
#
# WHAT MAKES IT SAFE.  The exemption is CONDITIONAL on the dependency version,
# and both conditions are read out of the artefact, never assumed:
#
#   (1) THE VERSION PIN, from META-INF/androidx.activity_activity.version.
#       AGP stamps it as a resource entry, so unlike a class it survives R8 --
#       measured present and "1.13.0" in BOTH the debug and the release APK.
#       The floor is 1.10.0.  That is not the pinned version and not a guess:
#       every stable release from 1.8.0 through 1.13.0 was fetched from
#       dl.google.com and its PickVisualMedia class parsed (2026-08-25).
#           1.8.0 .. 1.9.3      getGmsPicker$activity_release,
#                               isGmsPickerAvailable$activity_release   LIVE
#           1.10.0 .. 1.13.0    the two constants only                  INERT
#       The boundary is inside the 1.10.0 prerelease series -- 1.10.0-alpha01
#       is still LIVE, 1.10.0-alpha02 is the first build without the methods --
#       which is why parse_semver tracks the prerelease flag and why a
#       prerelease OF the floor version is rejected rather than rounded up.
#       Upstream replaced the path with SystemFallbackPicker; the GMS_* fields
#       are what it left behind.
#
#   (2) THE CLASS SHAPE, from the dex method_ids/field_ids tables.  On an
#       unminified build the declaring class must expose the two GMS-named
#       FIELDS and NO GMS-named METHOD.  1.8.2 fails this outright -- it
#       declares getGmsPicker$activity_release and
#       isGmsPickerAvailable$activity_release -- so the counterexample that
#       broke the old allowlist is caught here even if its version marker were
#       forged.  Measured on the debug APK: 9 methods, none GMS-named.
#
# WHAT THIS CANNOT SEE, stated because a green must not overclaim.  On a
# MINIFIED build R8 removes the class and both literals outright: measured on
# lw-fresh-2026-08-22's release APK, the descriptor is absent and the GMS string
# count is 0, so that build takes the unconditional-zero path and NEITHER
# condition is exercised.  A release green therefore says "R8 deleted it", which
# is the LW-M6-07 trap in miniature -- there, "provably zero-GMS" came from an
# APK that could not even boot.  Read a release PASS as evidence about the
# minifier, and a DEBUG pass as evidence about the dependency.  The debug
# artefact is the one that carries the exemption and the one to cite.
#
# The consequence worth stating: neither condition can catch a downgrade in a
# minified build, because there is nothing left to inspect.  What still holds
# there is the version marker, which is why (1) reads a resource entry rather
# than trusting the class alone -- but on a build where the strings are gone the
# check never asks.  A BUILD-TIME floor on gradle/libs.versions.toml would cover
# that gap; it is NOT implemented here and is recorded as an open item in
# docs/android/evidence/lw-m4-16/README.md, not silently assumed.
#
# NOTHING HERE DECODES AN INSTRUCTION.  "Is this string ever loaded" is not a
# question this file answers; see the dex-table comment above.
# --------------------------------------------------------------------------

# value -> the field it is the value of.  Exact match, not substring.
GMS_EXEMPT_STRINGS = {
    "com.google.android.gms.provider.action.PICK_IMAGES": "GMS_ACTION_PICK_IMAGES",
    "com.google.android.gms.provider.extra.PICK_IMAGES_MAX": "GMS_EXTRA_PICK_IMAGES_MAX",
}
GMS_EXEMPT_CLASS = "Landroidx/activity/result/contract/ActivityResultContracts$PickVisualMedia;"
GMS_EXEMPT_MARKER = "META-INF/androidx.activity_activity.version"
GMS_EXEMPT_FLOOR = (1, 10, 0)
GMS_EXEMPT_FLOOR_S = "1.10.0"

def _gms_version_ok(ver):
    """(ok, why).  A missing or unparseable marker is NOT a pass."""
    if ver is None:
        return False, ("%s is absent from the APK, so the androidx.activity version "
                       "cannot be established and the exemption cannot be granted"
                       % GMS_EXEMPT_MARKER)
    parsed = parse_semver(ver)
    if parsed is None:
        return False, "%s reads %r, which is not a version this check can compare" % (
            GMS_EXEMPT_MARKER, ver)
    triple, stable = parsed[:3], parsed[3]
    if triple < GMS_EXEMPT_FLOOR:
        return False, ("androidx.activity is %s, BELOW the %s floor at which "
                       "getGmsPicker/isGmsPickerAvailable were removed -- at this version "
                       "the two strings are a live Play Services hand-off, not dead constants"
                       % (ver, GMS_EXEMPT_FLOOR_S))
    if triple == GMS_EXEMPT_FLOOR and not stable:
        return False, ("androidx.activity is %s, a prerelease of the floor version; "
                       "1.10.0-alpha01 still carried the live GMS path, so prereleases of "
                       "%s are not accepted" % (ver, GMS_EXEMPT_FLOOR_S))
    return True, "androidx.activity %s >= %s" % (ver, GMS_EXEMPT_FLOOR_S)

def check_no_gms(apk, res):
    needles = ["com.google.android.gms", "com/google/android/gms", "Lcom/google/android/gms"]
    hits, entries = scan_apk(apk, needles)
    lib_hits = [e for e in entries if "gms" in e.lower()]
    found = set()
    for v in hits.values():
        found |= v
    types, members = apk_types_and_members(apk)
    gms_types = sorted(t for t in types if t.startswith("Lcom/google/android/gms/"))

    unexpected = sorted(s for s in found if s not in GMS_EXEMPT_STRINGS)
    exempted = sorted(s for s in found if s in GMS_EXEMPT_STRINGS)

    ver = apk_dep_version(apk, GMS_EXEMPT_MARKER)
    ver_ok, ver_why = _gms_version_ok(ver)

    slot = members.get(GMS_EXEMPT_CLASS)
    if slot is None:
        class_present = False
        gms_methods = []
        class_why = ("%s is not in the dex -- a minified build renames or deletes it, so the "
                     "class-shape condition had nothing to test here and this run rests on "
                     "the version marker alone" % GMS_EXEMPT_CLASS.split("/")[-1])
    else:
        class_present = True
        gms_methods = sorted(m for m in slot["method"] if "gms" in m.lower())
        gms_fields = sorted(f for f in slot["field"] if "gms" in f.lower())
        if gms_methods:
            class_why = ("%s declares GMS-named METHOD(S) %s -- that is the live Play Services "
                         "hand-off, not two dead constants"
                         % (GMS_EXEMPT_CLASS.split("/")[-1], gms_methods))
        else:
            class_why = ("%s declares the GMS-named fields %s and no GMS-named method (%d "
                         "methods total)" % (GMS_EXEMPT_CLASS.split("/")[-1], gms_fields,
                                             len(slot["method"])))

    # A GMS *class* reference is what a real Play Services dependency looks
    # like; no exemption covers one.
    reasons = []
    if lib_hits:
        reasons.append("%d gms apk entr(ies): %s" % (len(lib_hits), lib_hits[:3]))
    if gms_types:
        reasons.append("%d Lcom/google/android/gms/ type descriptor(s) in the dex: %s"
                       % (len(gms_types), gms_types[:3]))
    if unexpected:
        reasons.append("%d GMS string(s) outside the documented exemption: %s"
                       % (len(unexpected), unexpected[:3]))
    if exempted:
        if not ver_ok:
            reasons.append("the exemption does not hold: " + ver_why)
        if class_present and gms_methods:
            reasons.append("the exemption does not hold: " + class_why)

    ok = not reasons
    if ok and exempted:
        detail = ("0 GMS class references, 0 gms apk entries; %d string(s) exempted by exact "
                  "value, each a dead constant: %s. Exemption holds: %s; %s"
                  % (len(exempted),
                     "; ".join("%r (%s)" % (s, GMS_EXEMPT_STRINGS[s]) for s in exempted),
                     ver_why, class_why))
    elif ok:
        detail = ("no com.google.android.gms strings in any classes*.dex, no GMS class "
                  "references and no gms entries in the apk")
    else:
        detail = "; ".join(reasons) + " -- owned by LW-M4-16"

    res.add("check-no-gms", ok, detail,
            {"exempted": {s: GMS_EXEMPT_STRINGS[s] for s in exempted},
             "unexpected_strings": unexpected[:20],
             "gms_type_descriptors": gms_types[:20],
             "apk_entries": lib_hits[:20],
             "androidx_activity_version": ver,
             "version_floor": GMS_EXEMPT_FLOOR_S,
             "version_condition_ok": ver_ok,
             "declaring_class_present": class_present,
             "declaring_class_gms_methods": gms_methods,
             "hits": {k: sorted(v)[:20] for k, v in hits.items()}})
    return ok

def check_no_adjust(apk, res):
    needles = ["com.adjust.sdk", "com/adjust/sdk", "adjust_config",
               "com.android.vending.INSTALL_REFERRER"]
    hits, entries = scan_apk(apk, needles)
    total = sum(len(v) for v in hits.values())
    ok = total == 0
    res.add("check-no-adjust", ok,
            ("no Adjust or INSTALL_REFERRER strings in any classes*.dex" if ok else
             "%d Adjust/INSTALL_REFERRER strings in the dex string table (e.g. %s) -- "
             "owned by LW-M4-02" % (total, sorted(set().union(*hits.values()))[:3])),
            {"hits": {k: sorted(v)[:20] for k, v in hits.items()}})
    return ok

# --------------------------------------------------------------------------
# --check-no-remote-settings  (LW-M4-08)
#
# The gate: after a first-run capture, NONE of the three Remote Settings
# hosts may appear in the outbound traffic.  The Rust RemoteSettingsService
# (third_party/application-services/components/remote_settings/) is the
# channel Fenix uses, and patches/android/rs-blocker-android.patch closes
# it.  This check is the runtime proof that the patch did its job.
#
# THE INVERTED-GATE BUG THIS EXISTS TO PREVENT: an aborted or dead capture
# produces zero events, and "zero events" trivially contains no Remote
# Settings hostname.  A naive `not any(host in events)` passes on a dead
# capture.  This check therefore FAILS (exit 1) if the capture produced
# zero events, because we cannot distinguish "no traffic" from "the capture
# died".  A valid run must show at least one outbound event (proving the
# NIC tap is live) before we can assert "none of them is a Remote Settings
# host".  This is the same discipline as require_pcap, extended from
# "the file exists" to "the file has content".
# --------------------------------------------------------------------------
RS_HOSTS = (
    "firefox.settings.services.mozilla.com",
    "firefox-settings-attachments.cdn.mozilla.net",
    "content-signature-2.cdn.mozilla.net",
)

def check_no_remote_settings(pcap, start_offset, guest_ips, capture_seconds, res):
    """Network-based gate: the three Remote Settings hosts must not appear
    in outbound traffic during a first-run window.

    FAILS (exit 1, a real defect) if:
      - the capture produced zero events (dead capture — cannot distinguish
        'no RS traffic' from 'capture died'), or
      - any event's detail contains one of RS_HOSTS.

    PASSES only if the capture is confirmed live (>= 1 total event) AND
    no RS host appears in the app-originated events."""
    rows = summarise_capture(pcap, start_offset, guest_ips=guest_ips)
    total = len(rows)
    app_rows = [r for r in rows if not r["os_noise"] and not r.get("harness")]

    if total == 0:
        res.add("check-no-remote-settings", False,
                "CAPTURE PRODUCED ZERO EVENTS -- cannot distinguish 'no Remote "
                "Settings traffic' from 'the capture died'. An aborted capture "
                "prints no hostnames either, and this gate refuses to pass on "
                "that ambiguity. Re-run with a working capture (emulator "
                "-tcpdump).",
                {"total_events": 0, "app_events": 0})
        return False

    rs_hits = [r for r in app_rows
               if any(h in (r["detail"] or "").lower() for h in RS_HOSTS)]

    ok = not rs_hits
    res.add("check-no-remote-settings", ok,
            ("no Remote Settings host in %d app events (capture confirmed live: "
             "%d total events, %d app events)" % (len(app_rows), total, len(app_rows))
             if ok else
             "%d event(s) to a Remote Settings host: %s"
             % (len(rs_hits), sorted({r["detail"] for r in rs_hits})[:5])),
            {"total_events": total, "app_events": len(app_rows),
             "rs_hosts_checked": list(RS_HOSTS), "rs_hits": rs_hits[:50]})
    return ok

# --------------------------------------------------------------------------
# strings / branding  (LW-M4-12)
#
# The gate is deterministic and static: it reads the APK's resources.arsc with
# aapt2, then runs the l10n-strings patch's OWN checker (lw_brand_strings.py
# check-apk) over every string / plurals / string-array value.  A value FAILS
# iff a brand stem (Latin or non-Latin) still fires outside an enumerated
# url-keep host and outside the internal-key (value==name) exception.  That is
# exactly the acceptance criterion: no user-visible Firefox/Mozilla in the
# built APK, measured over resources -- not a scrape of two screens, which is
# what the earlier stub feared.  ui_brand_scan.py remains an evidence-only
# runtime walker; this aapt2 gate is the hard gate.
#
# The checker, the brand map and the l10n pin all live INSIDE
# patches/android/l10n-strings.patch (the source of truth for the build), so we
# extract them here at check time rather than trusting a copy that could drift.
# --------------------------------------------------------------------------
def find_aapt2(explicit, sdk):
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get("LW_SMOKE_AAPT2"):
        cands.append(os.environ["LW_SMOKE_AAPT2"])
    w = shutil.which("aapt2")
    if w:
        cands.append(w)
    if sdk:
        bt = os.path.join(sdk, "build-tools")
        if os.path.isdir(bt):
            def verkey(v):
                return [int(x) for x in re.findall(r"\d+", v)] or [0]
            for v in sorted((v for v in os.listdir(bt)
                             if os.path.isfile(os.path.join(bt, v, "aapt2"))),
                            key=verkey, reverse=True):
                cands.append(os.path.join(bt, v, "aapt2"))
    # AGP fetches aapt2 into the gradle transforms cache; search a bounded set
    # of gradle-home roots (never a whole-build-tree find, which times out).
    ghs = [os.path.join(os.environ.get("LW_SMOKE_REPO", "."), "out", "gradle-home", "caches"),
           os.path.expanduser("~/.gradle/caches")]
    if os.environ.get("LW_SMOKE_GRADLE_HOME"):
        ghs.insert(0, os.path.join(os.environ["LW_SMOKE_GRADLE_HOME"], "caches"))
    for gh in ghs:
        if os.path.isdir(gh):
            cands += glob.glob(os.path.join(gh, "*", "transforms", "*", "transformed",
                                            "aapt2-*linux", "aapt2"))
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    raise HarnessError("no aapt2 found to read resources.arsc. Pass --aapt2 PATH, or set "
                       "LW_SMOKE_AAPT2 / LW_SMOKE_GRADLE_HOME, or install an Android SDK "
                       "with build-tools. (Needed only by --check-strings.)")

def _extract_lw_brand(work):
    """Pull lw_brand_strings.py, brand-map.txt, android-l10n-pin.txt and
    ui_brand_scan.py out of patches/android/l10n-strings.patch into the work
    dir, so the check runs the patch's own code.  Returns a name->path dict."""
    patch = os.path.join(os.environ.get("LW_SMOKE_REPO", "."),
                         "patches", "android", "l10n-strings.patch")
    if not os.path.isfile(patch):
        raise HarnessError("cannot find %s (the --check-strings source of truth)" % patch)
    outdir = os.path.join(work, "lw-brand")
    os.makedirs(outdir, exist_ok=True)
    wanted = {"lw_brand_strings.py", "brand-map.txt", "android-l10n-pin.txt",
              "ui_brand_scan.py"}
    got = {}
    cur = None
    buf = []
    def flush():
        if cur in wanted and buf:
            p = os.path.join(outdir, cur)
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(buf) + "\n")
            got[cur] = p
    with open(patch, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("+++ b/"):
                flush()
                name = line[6:].strip().split("/")[-1]
                cur = name if name in wanted else None
                buf = []
            elif line.startswith("--- "):
                flush()
                cur, buf = None, []
            elif cur is not None and line.startswith("+"):
                buf.append(line[1:])
    flush()
    for need in wanted:
        if need not in got:
            raise HarnessError("--check-strings: %s is missing from l10n-strings.patch" % need)
    return got

# --------------------------------------------------------------------------
# --check-strings, the running-app half.
#
# The static half below reads the compiled resource table and is complete over
# it: every locale, every string/plurals/string-array row, including screens no
# walker ever reaches.  What it cannot see is text the app renders that does
# NOT come from a string resource, and it cannot prove the running app actually
# uses the rewritten table.  That is what this half is for.
#
# It is a TRAVERSAL, not a scrape of two screens: navigation is by deep link
# (so it does not depend on reading localised labels and works in Serbian and
# Malayalam), every screen it lands on is scrolled to the bottom, and every
# labelled clickable row is opened and scanned.  It still cannot be complete --
# no walker of a UI this size is -- so it REPORTS THE SCREENS IT VISITED BY
# NAME and the check's detail line states the count.  Coverage is auditable,
# never implied.
# --------------------------------------------------------------------------

# Locales whose android-l10n translations spell the mark in their own script,
# so a walker running in them exercises the non-Latin stems rather than the
# ASCII ones.  Used only when --strings-locale is given without a value list.
UI_SCAN_LOCALES = ("sr", "fa", "ml")

def apk_deeplink_scheme(aapt2, apk):
    """The app's own deep-link scheme, read from the APK's manifest.

    Not guessed and not hardcoded: LW-M4-07 changed it from Fenix's four
    per-variant schemes to a single `redoubt`, and a walker that navigated by a
    stale scheme would silently visit nothing and report a clean UI."""
    p = subprocess.run([aapt2, "dump", "xmltree", "--file", "AndroidManifest.xml", apk],
                       capture_output=True, text=True, timeout=300, errors="replace")
    if p.returncode != 0:
        raise HarnessError("aapt2 dump xmltree failed (%d): %s"
                           % (p.returncode, p.stderr[-300:]))
    seen = []
    for m in re.finditer(r'A: (?:http://schemas.android.com/apk/res/android:)?scheme'
                         r'\([^)]*\)="([^"]+)"', p.stdout):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    for s in seen:
        if s not in ("http", "https", "about", "javascript", "file", "content",
                     "data", "resource", "market", "samsungapps"):
            return s
    raise HarnessError("no deep-link scheme in the APK manifest (found %s); pass "
                       "--strings-scheme" % (seen or "none"))

def _device_locale(adb):
    for prop in ("persist.sys.locale", "ro.product.locale"):
        v = adb.shell("getprop %s" % prop, timeout=60).strip()
        if v:
            return v
    return "unknown"

def _set_device_locale(adb, tag, timeout=240):
    """Switch the device's system locale and wait for the restart.

    Needs a rootable (AOSP / -userdebug) image.  If root is refused the check
    raises rather than quietly walking the UI in English and calling that a
    locale sweep -- a check that reports coverage it did not have is the one
    outcome this harness must not produce."""
    r = adb.run("root", timeout=90)
    if "cannot run as root" in (r.stdout + r.stderr):
        raise HarnessError(
            "--strings-locale needs a rootable image to set persist.sys.locale; "
            "adb root was refused on this device (%s). Use an AOSP/userdebug "
            "emulator image, or drop --strings-locale and the runtime half will "
            "walk the UI in the device's current locale only."
            % (r.stdout + r.stderr).strip()[:120])
    time.sleep(2)
    adb.run("wait-for-device", timeout=120)
    adb.shell("setprop persist.sys.locale %s" % tag, timeout=60)
    adb.shell("stop", timeout=60)
    adb.shell("start", timeout=60)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if adb.shell("getprop sys.boot_completed", timeout=30).strip() == "1":
            time.sleep(6)
            got = _device_locale(adb)
            if got.split("-")[0].split("_")[0] != tag.split("-")[0].split("_")[0]:
                raise HarnessError("locale did not take: asked for %s, device reports %s"
                                   % (tag, got))
            return got
        time.sleep(3)
    raise HarnessError("device did not come back after switching locale to %s" % tag)

def _ui_scan_once(scan_py, brand_map, adb, pkg, scheme, label, work, depth, max_taps):
    """One traversal.  Returns (findings, allowed, screens, raw)."""
    argv = [sys.executable, scan_py, "--adb", adb.exe, "--package", pkg,
            "--scheme", scheme, "--map", brand_map, "--label", label,
            "--depth", str(depth), "--max-taps", str(max_taps)]
    if adb.serial:
        argv += ["--serial", adb.serial]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=7200,
                       errors="replace")
    raw = (p.stderr or "") + (p.stdout or "")
    with open(os.path.join(work, "ui-brand-scan-%s.log" % label), "w",
              encoding="utf-8", errors="replace") as f:
        f.write(raw)
    findings = [l.split("\t") for l in (p.stdout or "").splitlines()
                if l.startswith("BRANDED\t")]
    allowed = [l.split("\t") for l in (p.stdout or "").splitlines()
               if l.startswith("ALLOWED\t")]
    # The walker names every stop it made on stderr, "  [<screen>] N string(s)".
    screens = re.findall(r"^\s+\[([^\]]+)\] \d+ string\(s\)", p.stderr or "",
                         re.M)
    if not screens and p.returncode not in (0, 1):
        raise HarnessError("ui_brand_scan.py could not run (%d): %s"
                           % (p.returncode, raw.strip()[-400:]))
    return findings, allowed, screens, raw

def _shipped_text(apk, dump_path):
    """Every text this APK could possibly render out of its own bytes: the
    compiled resource values, and the DEX string constants.

    A branded string seen on screen is classified against this set, and the
    classification is what makes the runtime half both strict and non-vacuous:

      * present here  -> the build SHIPS that text. It is a resource the rewrite
        missed, or a brand literal hardcoded in Kotlin (which the resource-table
        half cannot see at all).  That is a defect and it FAILS.
      * absent here   -> the app rendered text it does not ship. It came over the
        network or out of a profile, so no change to this tree can remove it;
        it is REPORTED with its screen, and the owning task is named.

    The distinction is mechanical.  It is not an allowlist and there is nothing
    in it to soften: adding a brand string anywhere in the APK moves it into the
    failing class, not out of it."""
    vals = set()
    with open(dump_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r'\s*\([^)]*\)\s+["\'](.*)["\']\s*$', line)
            if m:
                vals.add(m.group(1))
    for s in apk_dex_strings(apk):
        vals.add(s)
    return vals

def _is_shipped(value, shipped):
    """True if the on-screen text comes from something this APK ships.

    Compared after collapsing whitespace, and also as a substring of a shipped
    value, because Android renders a format string with its arguments already
    substituted and a TextView may show only part of one."""
    v = re.sub(r"\s+", " ", value).strip()
    if not v:
        return True
    if v in shipped:
        return True
    for s in shipped:
        if len(s) >= 12 and (v in s or s in v):
            return True
    return False

def check_strings_ui(res_evidence, work, brand, adb, pkg, scheme, locales,
                     depth, max_taps, shipped=None):
    """The running-app traversal.  Returns (ok, summary, evidence)."""
    scan_py, brand_map = brand["ui_brand_scan.py"], brand["brand-map.txt"]
    # ui_brand_scan.py imports lw_brand_strings from its own directory; both
    # were extracted side by side, so that import resolves to the patch's copy.
    started = _device_locale(adb)
    runs = []
    ok = True
    try:
        for tag in locales:
            if tag != "device":
                log("check-strings: switching device locale to %s" % tag)
                got = _set_device_locale(adb, tag)
            else:
                got = started
            log("check-strings: walking the running UI in %s" % got)
            findings, allowed, screens, _raw = _ui_scan_once(
                scan_py, brand_map, adb, pkg, scheme, tag, work, depth, max_taps)
            hits = [dict(zip(("kind", "locale", "screen", "attr",
                              "resource_id", "value"), f)) for f in findings]
            for h in hits:
                h["shipped_by_this_apk"] = (shipped is None
                                            or _is_shipped(h["value"], shipped))
            ours = [h for h in hits if h["shipped_by_this_apk"]]
            remote = [h for h in hits if not h["shipped_by_this_apk"]]
            runs.append({"locale": tag, "device_locale": got,
                         "screens_visited": screens,
                         "screen_count": len(screens),
                         "branded": ours,
                         "branded_not_shipped_by_this_apk": remote,
                         "allowed_url_rows": len(allowed)})
            if ours:
                ok = False
            log("check-strings: %s -- %d screen(s) visited, %d branded string(s) this "
                "APK ships, %d branded string(s) it does not ship (remote content), "
                "%d enumerated url-keep row(s)"
                % (got, len(screens), len(ours), len(remote), len(allowed)))
            for h in remote:
                log("check-strings: REPORTED (not shipped by this APK, so no change "
                    "to this tree removes it) [%s] %r"
                    % (h["screen"], h["value"][:120]))
    finally:
        if locales != ["device"] and started != "unknown":
            try:
                _set_device_locale(adb, started)
            except Exception as e:
                log("check-strings: could not restore the device locale to %s (%s)"
                    % (started, e))
    total_screens = sum(r["screen_count"] for r in runs)
    total_branded = sum(len(r["branded"]) for r in runs)
    total_remote = sum(len(r["branded_not_shipped_by_this_apk"]) for r in runs)
    remote_examples = sorted({h["value"][:110]
                              for r in runs
                              for h in r["branded_not_shipped_by_this_apk"]})
    summary = ("running-app traversal: %d screen stop(s) across %d locale(s) (%s), "
               "%d branded string(s) shipped by this APK, %d branded string(s) NOT "
               "shipped by it%s. Screens the walker never reached are not covered by "
               "this half -- result.json lists every stop by name"
               % (total_screens, len(runs),
                  ", ".join(r["device_locale"] for r in runs),
                  total_branded, total_remote,
                  (" (remote content, reported not gated: %s)"
                   % "; ".join(repr(v) for v in remote_examples[:2]))
                  if remote_examples else ""))
    res_evidence["ui_scan"] = {"ran": True, "runs": runs,
                               "started_locale": started,
                               "note": ("a traversal, not a proof of completeness: the "
                                        "screens actually visited are listed per run. "
                                        "A branded string this APK does not ship is "
                                        "reported, not gated -- no change to this tree "
                                        "can remove it.")}
    return ok, summary

def check_strings(apk, res, aapt2, work, adb=None, pkg=None, scheme=None,
                  locales=None, depth=1, max_taps=14):
    brand = _extract_lw_brand(work)
    py, brand_map, pin = (brand["lw_brand_strings.py"], brand["brand-map.txt"],
                          brand["android-l10n-pin.txt"])
    dump = os.path.join(work, "aapt2-resources.txt")
    p = subprocess.run([aapt2, "dump", "resources", apk],
                       stdout=open(dump, "w", encoding="utf-8", errors="replace"),
                       stderr=subprocess.PIPE, text=True, timeout=300)
    if p.returncode != 0:
        raise HarnessError("aapt2 dump resources failed (%d): %s" % (p.returncode, p.stderr[-400:]))
    r = subprocess.run([sys.executable, py, "--map", brand_map, "--pin", pin,
                        "check-apk", "--dump", dump],
                       capture_output=True, text=True, timeout=600)
    # The checker (like the rest of the patch) sends human output to stderr.
    out = (r.stderr or r.stdout or "").strip().splitlines()
    tail = out[-1] if out else ""
    stats = next((ln for ln in out if "unexplained" in ln), "")
    rows = next((ln for ln in out if "text rows" in ln), "")
    static_ok = r.returncode == 0
    ev = {"aapt2": aapt2, "dump_rows": stats, "checker_tail": tail,
          "checker_exit": r.returncode, "checker_output": out[:40],
          "checker_stdout": (r.stdout or "").strip()[:800]}

    # ---- half 1: the compiled resource table, complete over every locale ---
    static_txt = ("resource table (%s): %s"
                  % (re.sub(r"^\[[^\]]*\]\s*", "", rows) or "aapt2 dump",
                     re.sub(r"^\[[^\]]*\]\s*", "", stats) or "no counts reported"))

    # ---- half 2: the running app, if there is one to run against ----------
    ui_ok, ui_txt = True, None
    if adb is not None and pkg:
        shipped = _shipped_text(apk, dump)
        ev["shipped_text_values"] = len(shipped)
        ui_ok, ui_txt = check_strings_ui(ev, work, brand, adb, pkg, scheme,
                                         locales or ["device"], depth, max_taps,
                                         shipped=shipped)
    else:
        ev["ui_scan"] = {"ran": False,
                         "why": "no device: --check-strings was run without "
                                "--emulator or --serial"}
        ui_txt = ("running-app traversal: NOT RUN (no device -- pass --emulator or "
                  "--serial). This run covers the compiled resource surface ONLY; "
                  "text the app renders from anywhere other than a string resource "
                  "is not covered by it")

    ok = static_ok and ui_ok
    if ok:
        detail = "%s; %s" % (static_txt, ui_txt)
    else:
        why = []
        if not static_ok:
            why.append("the aapt2 gate found unexplained Firefox/Mozilla brand "
                       "value(s) in the built APK's resource table (%s)" % stats)
        if not ui_ok:
            hits = [b for run in ev["ui_scan"]["runs"] for b in run["branded"]]
            why.append("the running-app traversal saw %d branded string(s) that this "
                       "APK ships, e.g. %s"
                       % (len(hits),
                          "; ".join("%s [%s] %r" % (h["locale"], h["screen"],
                                                    h["value"][:90])
                                    for h in hits[:3])))
        detail = "%s -- owned by LW-M4-12" % "; ".join(why)
    res.add("check-strings", ok, detail, ev)
    return ok

# --------------------------------------------------------------------------
# about:config  (LW-M4-09)
#
# READ THIS BEFORE CHANGING A SELECTOR HERE.  Android's about:config is NOT
# desktop's.  docshell/base/nsAboutRedirector.cpp:106-113 maps about:config to
# chrome://global/content/aboutconfig/aboutconfig.html only #ifndef
# MOZ_WIDGET_ANDROID; the #else arm maps it to
# chrome://geckoview/content/config.xhtml.  toolkit/components/moz.build:103-113
# adds "aboutconfig" to DIRS only when MOZ_BUILD_APP != "mobile/android", so
# toolkit's page -- the one that owns the "Proceed with Caution" interstitial,
# its browser.aboutConfig.showWarning pref and #about-config-search -- is not
# built for Android at all and is absent from the APK's omni.ja.
#
# The first version of this check asked for
#     document.querySelector("#about-config-search, #warningTitle, .toggleButton")
# which is desktop's markup, three selectors that exist in NEITHER page shipped
# on Android.  It therefore reported
#     check-aboutconfig FAIL  url=about:config recognised-ui=False
# on a build where about:config demonstrably works -- measured on a running
# release-configured APK: readyState "complete", title "about:config", 30
# .pref-item rows in #prefs-container, and that querySelector returning null in
# the same session.  A gate that cannot go green on a correct build is as
# useless as one that cannot go red on a broken one.
#
# What the page really is (mobile/shared/chrome/geckoview/config.xhtml and
# config.js in the ESR tree the Android build tracks -- NOT the desktop tarball
# in the repo root, which is a different Firefox version whose copy of this file
# has already been refactored to id-based listeners):
#   * landmarks  #filter-input, #prefs-container, #new-pref-item, #content
#   * rows       #prefs-container > li.pref-item[name="<pref>"], 30 at a time
#                (config.js:10 PREFS_BUFFER_MAX), more on scroll
#   * a row's toggle is  .pref-button.toggle  -> AboutConfig.toggleBoolPref
#                (config.js:456), which early-returns at :461 for a locked pref
#   * locked rows get .pref-name[locked] (config.js:708-710), drawn as a padlock
#                by config.css:210-217
#   * about:config?filter=<string> is supported natively (config.js:228-232)
#
# WHAT THIS CHECK ASSERTS, and what each assertion would catch:
#   1. the build is release-configured -- refused otherwise, see below
#   2. the navigation lands on about:config at all.  An unpatched release build
#      pushes general.aboutConfig.enable=false, nsAboutRedirector.cpp:285-288
#      returns NS_ERROR_NOT_AVAILABLE, and this navigation times out.
#   3. it is GeckoView's editor, not an error document that merely has that URL
#   4. the editor listed real prefs (>= 20 rows).  Catches a page that renders
#      its chrome and then dies.
#   5. general.aboutConfig.enable is true ON THE DEFAULT BRANCH with no user
#      value -- i.e. it is the BUILD's configuration.  Catches a green produced
#      by a stale profile, a user_pref, or anything the harness itself did.
#   6. an edit made through the page's own toggle button reaches the pref
#      service.  Catches a page whose JS is broken.
#   7. that edit survives a real app restart (acceptance line 3).
# The interstitial is reported, never required: Android has never had one, and
# if a future build grows one this check clicks through it instead of failing.
# --------------------------------------------------------------------------
JS_ABOUTCONFIG_PAGE = r"""
  const done = arguments[arguments.length-1];
  const t0 = Date.now();
  // If a build ever grows desktop's interstitial, click through it rather than
  // fail: this check is about reachability, not about the safety copy.
  const warn = document.querySelector("#warningButton, button.primary[data-l10n-id*='warning']");
  if (warn) { try { warn.click(); } catch (e) {} }
  // Poll for a FULLY populated list, not merely a non-empty one: config.js
  // fills #prefs-container 30 rows at a time (PREFS_BUFFER_MAX) and then sets
  // each row's value 100 ms later, so "one row is there" is a race, while
  // "twenty rows are there" is the page having actually worked.  On a broken
  // page this still returns at the 30 s cap with whatever count it has, and the
  // >= 20 assertion in Python is what fails.
  (function poll(){
    const rows = document.querySelectorAll("#prefs-container .pref-item").length;
    if (rows >= 20 || Date.now() - t0 > 30000) {
      done({url: location.href, title: document.title, readyState: document.readyState,
            rows: rows, waitedMs: Date.now() - t0,
            landmarks: {"#filter-input": !!document.querySelector("#filter-input"),
                        "#prefs-container": !!document.querySelector("#prefs-container"),
                        "#new-pref-item": !!document.querySelector("#new-pref-item")},
            interstitial: !!document.querySelector("#warningTitle, #showWarningNextTime"),
            desktopMarkup: !!document.querySelector("#about-config-search"),
            body: document.body ? document.body.textContent.replace(/\s+/g," ").slice(0,160) : null});
    } else setTimeout(poll, 250);
  })();
"""

# Filtering is done through the page's own #filter-input, NOT by navigating to
# about:config?filter=<name>.  The query form works, but a second navigation
# while the first document is still settling loses the race and Marionette
# reports "javascript error: Document was unloaded" -- observed.  One navigation,
# then drive the search box the way a user does: config.xhtml wires
# oninput="AboutConfig.bufferFilterInput()", which settles after
# FILTER_CHANGE_TRIGGER (200 ms) and rebuilds the list.
JS_ABOUTCONFIG_FILTER = r"""
  const done = arguments[arguments.length-1];
  const name = arguments[0];
  const t0 = Date.now();
  const filter = document.getElementById("filter-input");
  filter.value = name;
  filter.dispatchEvent(new Event("input", {bubbles: true}));
  (function poll(){
    const li = document.querySelector('#prefs-container .pref-item[name="' + name + '"]');
    if (li && li.querySelector(".pref-button.toggle")) {
      const val = li.querySelector(".pref-value");
      const before = val ? val.value : null;
      const nameDiv = li.querySelector(".pref-name");
      const state = {found: true, before: before,
                     locked: nameDiv.hasAttribute("locked"),
                     lockIcon: getComputedStyle(nameDiv).backgroundImage,
                     disabled: val ? val.hasAttribute("disabled") : null,
                     waitedMs: Date.now() - t0};
      done(state);
    } else if (Date.now() - t0 > 30000) {
      done({found: false, waitedMs: Date.now() - t0,
            rows: document.querySelectorAll("#prefs-container .pref-item").length});
    } else setTimeout(poll, 250);
  })();
"""

JS_PREF_FACTS = r"""
  const S = Services.prefs;
  const n = "general.aboutConfig.enable";
  return {type: S.getPrefType(n), value: S.getBoolPref(n, null),
          defaultValue: S.getDefaultBranch("").getBoolPref(n, null),
          locked: S.prefIsLocked(n), hasUserValue: S.prefHasUserValue(n),
          lockedPrefCount: S.getChildList("").filter(p => S.prefIsLocked(p)).length,
          cfgVersion: S.getCharPref("librewolf.cfg.version", "ABSENT")};
"""

def probe_aboutconfig_readonly(m, script, args=None):
    # GeckoView can replace the initial document just after Navigate returns.
    # Only this read-only probe is safe to retry; never replay a toggle whose
    # first invocation may already have changed the preference.
    unloaded = []
    for attempt in range(3):
        try:
            page = m.async_script(script, args)
            page["documentUnloadRetries"] = unloaded
            return page
        except MarionetteError as e:
            if "javascript error: Document was unloaded" not in str(e) or attempt == 2:
                raise
            unloaded.append(str(e))
            time.sleep(0.5)

def probe_aboutconfig_page(m):
    return probe_aboutconfig_readonly(m, JS_ABOUTCONFIG_PAGE)

def wait_for_initial_document(m, url):
    # NewSession only promises a Gecko window. Fenix's launch intent can still
    # be loading its first URL, which would overwrite a subsequent navigation.
    # Wait for that actual document before exercising about:config.
    last = None
    for _attempt in range(60):
        try:
            last = m.script('return {url: location.href, uri: document.documentURI, '
                            'ready: document.readyState};')
            if last.get("url") == url and last.get("uri") == url and last.get("ready") == "complete":
                return last
        except MarionetteError as e:
            if "javascript error: Document was unloaded" not in str(e):
                raise
            last = {"error": str(e)}
        time.sleep(0.25)
    raise HarnessError("initial browser document did not finish loading before about:config: %s" % last)

def check_aboutconfig(m, res, app, apk, reopen_url):
    """See the block comment above.  Returns (ok, marionette) -- the session is
    replaced part-way through, because acceptance asks that an edit survive a
    restart and a restart ends the session."""
    # LW-M4-09's acceptance is about a RELEASE-configured build.  On a debug
    # build about:config is already on (GeckoProvider.kt gates it on
    # isBeta || isNightlyOrDebug), so a pass here would prove nothing.  Refuse.
    if app.debuggable():
        raise Unimplemented(
            "--check-aboutconfig on a DEBUGGABLE build proves nothing: GeckoProvider.kt gates "
            "aboutConfigEnabled on (isBeta || isNightlyOrDebug), so about:config is already on "
            "here for a reason that has nothing to do with LW-M4-09. Build a release-configured "
            "APK (./mach gradle fenix:assembleRelease -PdisableOptimization) and point this run "
            "at it with --apk or LW_SMOKE_APK -- the default APK search only ever finds the "
            "debug build. (%s)" % os.path.basename(apk))
    ev = {"initialDocument": wait_for_initial_document(m, reopen_url)}
    # Created BEFORE the page loads -- see the edit step below for why.  The name
    # carries the epoch so it is unique per run, and so that it is a name
    # GeckoView cannot be declaring (landmine L2b: GeckoView:ResetUserPrefs
    # clears the user branch for the prefs GeckoView knows about, and a green
    # from a name it could clear would prove nothing about persistence).
    name = "librewolf.smoke.aboutconfig.%d" % int(time.time())
    m.script('Services.prefs.setBoolPref(arguments[0], false); return true;', [name], chrome=True)
    try:
        m.cmd("Marionette:SetContext", {"value": "content"})
        # A short page-load timeout on purpose.  When the pref is false
        # nsAboutRedirector never produces a channel and this navigation simply
        # never lands, so the failure mode is a timeout -- and it has to come
        # back as a check FAILURE (exit 1) inside the harness's own socket
        # timeout, not as a socket read error that escapes as a traceback.
        m.cmd("WebDriver:SetTimeouts", {"pageLoad": 45000})
        m.cmd("WebDriver:Navigate", {"url": "about:config"})
        m.cmd("WebDriver:SetTimeouts", {"pageLoad": 120000})
    except MarionetteError as e:
        # This is what an unpatched release build looks like: the pref is false,
        # nsAboutRedirector refuses the channel and the navigation never lands.
        # Say WHY, from the pref service, rather than leaving the reader to guess.
        try:
            facts = m.script(JS_PREF_FACTS, chrome=True)
        except Exception:
            facts = {}
        res.add("check-aboutconfig", False,
                "navigation to about:config did not complete (%s); general.aboutConfig.enable "
                "reads value=%s default-branch=%s -- an unpatched release build pushes false "
                "here from GeckoProvider.kt and nsAboutRedirector.cpp:285-288 then refuses the "
                "channel. Owned by LW-M4-09."
                % (e, facts.get("value"), facts.get("defaultValue")),
                {"navigate_error": str(e), "pref": facts})
        return False, m
    try:
        page = probe_aboutconfig_page(m)
        ev["page"] = page
        facts = m.script(JS_PREF_FACTS, chrome=True)
        ev["pref"] = facts
    except MarionetteError as e:
        # The navigation DID land, so this is not the defect signature -- it is
        # the probe failing to run.  Exit 2 ("the check did not happen"), never
        # exit 1, or a harness bug would be reported as a defect in the build.
        raise HarnessError("about:config loaded but the probe could not run: %s" % e)

    url_ok = str(page.get("url", "")).startswith("about:config")
    ui_ok = all(page.get("landmarks", {}).values())
    rows_ok = page.get("rows", 0) >= 20
    # The value has to be the BUILD's, not the profile's: on the default branch,
    # with no user value.  GeckoView commits this pref from
    # RuntimeSettings.Pref.addToBundle on every startup (mIsSet ? mValue :
    # defaultValue, and GeckoRuntimeSettings.java:768 declares the default
    # false), so the only writer of that branch is the GeckoProvider.kt call
    # site LW-M4-09 patches.
    pref_ok = (facts.get("value") is True and facts.get("defaultValue") is True
               and facts.get("hasUserValue") is False)

    # An edit through the page's own UI, on a pref this check creates, so that a
    # value left behind by anything else cannot be mistaken for the page working.
    # It was created before the navigation above, because AboutConfig.init()
    # builds its list once from Services.prefs.getChildList("") at load time.
    try:
        toggled = probe_aboutconfig_readonly(m, JS_ABOUTCONFIG_FILTER, [name])
        # Filtering can be repeated after a document replacement because it
        # does not edit a pref. Keep the actual UI click separate and single
        # shot, so a retry can never silently undo an edit that already landed.
        toggled["clicked"] = m.script('const row = document.querySelector('
                    '\'#prefs-container .pref-item[name="\' + arguments[0] + \'"]\');'
                    'const button = row && row.querySelector(".pref-button.toggle");'
                    'if (!button) return false; button.click(); return true;', [name])
        ev["edit"] = toggled
        after = m.script('return Services.prefs.getBoolPref(arguments[0], null);',
                         [name], chrome=True)
    except MarionetteError as e:
        try:
            ev["atEditError"] = m.script('return {url: location.href, uri: document.documentURI};')
            ev["prefAtEditError"] = m.script('return Services.prefs.getBoolPref(arguments[0], null);',
                                            [name], chrome=True)
        except Exception:
            pass
        raise HarnessError("the edit probe could not run on a loaded about:config: %s; evidence=%s" % (e, ev))
    ev["edit"]["prefAfterToggle"] = after
    edit_ok = bool(toggled.get("found")) and toggled.get("clicked") is True and after is True

    # ...and it has to survive a restart.  savePrefFile is the flush a clean
    # shutdown does; force-stop is a kill, and this check is about the edit, not
    # about Gecko's flush timing.
    restart_ok = False
    if edit_ok:
        m.script('Services.prefs.savePrefFile(null); return true;', chrome=True)
        time.sleep(2)
        m.close()
        app.force_stop()
        time.sleep(2)
        app.start_url(reopen_url)
        m = app.connect_marionette()
        m.cmd("WebDriver:SetTimeouts", {"script": 60000, "pageLoad": 120000})
        back = m.script('const S = Services.prefs;'
                        'return {value: S.getBoolPref(arguments[0], null),'
                        ' hasUserValue: S.prefHasUserValue(arguments[0])};', [name], chrome=True)
        ev["afterRestart"] = back
        restart_ok = back.get("value") is True and back.get("hasUserValue") is True
        m.script('Services.prefs.clearUserPref(arguments[0]); return true;', [name], chrome=True)

    ok = url_ok and ui_ok and rows_ok and pref_ok and edit_ok and restart_ok
    if ok:
        detail = ("about:config reachable on a release-configured build: %d pref rows, "
                  "general.aboutConfig.enable=true on the default branch (no user value), "
                  "an edit through the page's own toggle survived a restart. "
                  "%d prefs locked; interstitial present=%s (Android ships none)."
                  % (page.get("rows"), facts.get("lockedPrefCount"), page.get("interstitial")))
    else:
        why = []
        if not url_ok:
            why.append("url=%s" % page.get("url"))
        if not ui_ok:
            why.append("GeckoView about:config landmarks missing %s (this page is "
                       "chrome://geckoview/content/config.xhtml, NOT desktop's aboutconfig.html)"
                       % [k for k, v in page.get("landmarks", {}).items() if not v])
        if not rows_ok:
            why.append("only %s pref rows rendered" % page.get("rows"))
        if not pref_ok:
            why.append("general.aboutConfig.enable value=%s default=%s hasUserValue=%s"
                       % (facts.get("value"), facts.get("defaultValue"), facts.get("hasUserValue")))
        if not edit_ok:
            why.append("an edit through the page's toggle button did not reach the pref service "
                       "(row found=%s, pref after=%s)" % (toggled.get("found"), after))
        elif not restart_ok:
            why.append("the edit did not survive a restart (%s)" % ev.get("afterRestart"))
        detail = "; ".join(why) + " -- owned by LW-M4-09"
    res.add("check-aboutconfig", ok, detail, ev)
    return ok, m

def check_ubo(m, res):
    listed = m.script(r"""
      const done = arguments[arguments.length-1];
      return (async () => {
        const { AddonManager } = ChromeUtils.importESModule(
          "resource://gre/modules/AddonManager.sys.mjs");
        const all = await AddonManager.getAllAddons();
        return all.map(a => ({id: a.id, name: a.name, type: a.type,
                              active: a.isActive, userDisabled: a.userDisabled}));
      })();
    """, chrome=True)
    pref = m.script('var n="librewolf.uBO.assetsBootstrapLocation";'
                    'return {type: Services.prefs.getPrefType(n), '
                    'value: Services.prefs.getPrefType(n) ? Services.prefs.getStringPref(n) : null};',
                    chrome=True)
    ubo = [a for a in (listed or []) if "ublock" in (a["id"] + a["name"]).lower()]
    ok = bool(ubo) and ubo[0]["active"]
    res.add("check-ubo", ok,
            ("uBlock Origin present and active: %s" % ubo[0] if ok else
             "no uBlock Origin among the %d installed add-ons -- owned by LW-M4-04. "
             "librewolf.uBO.assetsBootstrapLocation: %s"
             % (len(listed or []), "unset" if pref.get("type") == 0 else pref.get("value"))),
            {"addons": listed, "assetsBootstrapLocation": pref})
    return ok

# The add-on ID is uBlock0@raymondhill.net — Raymond Hill's, and the one this repo
# already uses at settings/distribution/policies.json:50. It was uBlock0@uvrove.com
# here and in patches/android/ubo-preinstall.patch until 2026-08-27; that ID exists
# nowhere else in the project or upstream, so this gate could never have gone green
# against genuine uBO, and WOULD have gone green against an add-on carrying the made-up
# ID. Both halves of a gate keyed on an identifier have to use the same identifier the
# rest of the system does.
def check_ubo_preinstall(m, res):
    """Verify uBlock Origin is PREINSTALLED -- present in the add-on registry
    by its exact ID and active -- and report the assets bootstrap location the
    build declares for it.  Unlike check_ubo, this does not substring-match the
    name and it does not require the harness to have installed anything: a green
    here means the build ships uBlock Origin, not that this run added it."""
    listed = m.script(r"""
      return (async () => {
        const { AddonManager } = ChromeUtils.importESModule(
          "resource://gre/modules/AddonManager.sys.mjs");
        return await AddonManager.getAllAddons().then(addons =>
          addons.map(a => ({id: a.id, name: a.name, active: a.isActive})));
      })();
    """, chrome=True)
    pref = m.script('var n="librewolf.uBO.assetsBootstrapLocation";'
                    'return {type: Services.prefs.getPrefType(n), '
                    'value: Services.prefs.getPrefType(n) ? Services.prefs.getStringPref(n) : null};',
                    chrome=True)
    boot = pref.get("value") if pref.get("type") else None
    ubo = [a for a in (listed or []) if a.get("id") == "uBlock0@raymondhill.net"]
    ok = bool(ubo) and bool(ubo[0]["active"])
    res.add("check-ubo-preinstall", ok,
            ("uBlock Origin preinstalled and active: %s (bootstrap location: %s)"
             % (ubo[0], boot) if ok else
             "uBlock Origin (uBlock0@raymondhill.net) is not installed or is not active among "
             "the %d add-ons on record (bootstrap location: %s) -- owned by LW-M4-04"
             % (len(listed or []), boot)),
            {"addons": listed, "bootstrap_location": boot})
    return ok

def ubo_bundle_evidence(apk):
    """Bind a behavior probe to the exact packaged, pinned filter input."""
    with zipfile.ZipFile(apk) as archive:
        pin = json.loads(archive.read("assets/extensions/ubo-extension.json"))
        xpi = archive.read("assets/extensions/ublock_origin.xpi")
    digest = hashlib.sha256(xpi).hexdigest()
    if digest != pin.get("sha256") or len(xpi) != pin.get("size"):
        raise HarnessError("bundled uBO bytes do not match their packaged pin")
    with zipfile.ZipFile(io.BytesIO(xpi)) as extension:
        manifest = json.loads(extension.read("manifest.json"))
        addon_id = manifest.get("browser_specific_settings", {}).get("gecko", {}).get("id")
        if addon_id is None:
            addon_id = manifest.get("applications", {}).get("gecko", {}).get("id")
        filters = extension.read(UBO_FILTER_FILE)
        if UBO_FILTER_RULE not in filters.decode().splitlines():
            raise HarnessError("the bundled EasyList no longer contains the probe rule")
        if addon_id != UBO_ID or pin.get("id") != UBO_ID or manifest.get("version") != pin.get("version"):
            raise HarnessError("bundled uBO ID/version does not match its pin")
    return {"pin": pin, "xpi_sha256": digest, "filter_path": UBO_FILTER_FILE,
            "filter_sha256": hashlib.sha256(filters).hexdigest(), "filter_rule": UBO_FILTER_RULE}

def read_ubo_addon(m):
    return m.script(r"""
      return (async () => {
        const { AddonManager } = ChromeUtils.importESModule(
          "resource://gre/modules/AddonManager.sys.mjs");
        const a = await AddonManager.getAddonByID(arguments[0]);
        if (!a) return null;
        const p = WebExtensionPolicy.getByID(a.id);
        return {id:a.id, version:a.version, active:a.isActive,
                userDisabled:a.userDisabled, signedState:a.signedState,
                amoSigned:a.signedState === AddonManager.SIGNEDSTATE_SIGNED,
                isBuiltin:a.isBuiltin, privateBrowsingAllowed:p?.privateBrowsingAllowed,
                blockingResponseListeners:p?.extension?.redoubtBlockingResponseListeners?.size || 0};
      })();
    """, [UBO_ID], chrome=True)

def grade_ubo_navigation(page, requests, token, blocked):
    """Require completed script execution AND independent server observations."""
    blocked_hits = [r for r in requests if r[2] == UBO_BLOCKED_PATH + "?token=" + token]
    allowed_hits = [r for r in requests if r[2] == UBO_ALLOWED_PATH + "?token=" + token]
    page_hits = [r for r in requests if r[2] == "/ubo-probe?token=" + token]
    state = page.get("probe") or {}
    ok = (page.get("ready") == "complete" and state.get("token") == token
          and state.get("allowed") is True and bool(allowed_hits) and bool(page_hits)
          and state.get("blocked") is (not blocked)
          and bool(blocked_hits) is (not blocked))
    return ok, {"page": page, "page_requests": page_hits,
                "blocked_requests": blocked_hits, "allowed_requests": allowed_hits}

def measure_ubo_navigation(m, res, origin, token, blocked, label):
    page = m.script('return {url:location.href, uri:document.documentURI, '
                    'ready:document.readyState, '
                    'probe:(window.wrappedJSObject || window).redoubtUboProbe || null};')
    ok, evidence = grade_ubo_navigation(page or {}, list(origin.requests), token, blocked)
    evidence["expected_blocked"] = blocked
    res.add(label, ok, "bundled-list script %s; allowed script must execute and reach the origin"
            % ("blocked" if blocked else "allowed with uBO disabled or absent"), evidence)
    return ok

def run_ubo_behavior(app, adb, apk, origin, res, lifecycle=False):
    """The incoming first URL starts a fresh browser and immediately requests scripts.

    ADB reverse reaches the server through Android loopback, which Gecko exempts
    from HTTPS-only without a preference override (nsHTTPSOnlyUtils.cpp). The
    JavaScript runs before the harness attaches. The final DOM and origin logs
    therefore retain evidence even if installation completes after the request.
    Lifecycle mutations below use the real AddonManager API, not Fenix UI.
    """
    bundle = ubo_bundle_evidence(apk)
    remote_port = origin.http_port
    adb.run("reverse", "tcp:%d" % remote_port, "tcp:%d" % origin.http_port, check=True)
    base = "http://127.0.0.1:%d/ubo-probe?token=" % remote_port
    m = None
    try:
        token = "first-" + os.urandom(8).hex()
        m = open_session(app, base + token)
        wait_for_initial_document(m, base + token)
        first_ok = measure_ubo_navigation(m, res, origin, token, True, "ubo-first-navigation")
        addon = read_ubo_addon(m)
        addon_ok = (bool(addon) and addon.get("active") is True
                    and addon.get("userDisabled") is False and addon.get("amoSigned") is True
                    and addon.get("isBuiltin") is False
                    and addon.get("version") == bundle["pin"]["version"])
        res.add("ubo-preinstalled-signature", addon_ok,
                "the pinned ordinary AMO-signed add-on must be active on first navigation",
                {"addon": addon, "bundle": bundle})
        if not lifecycle or not first_ok or not addon_ok:
            return

        # This is also the negative control for the block assertion: the same
        # resource must reach the server and execute after uBO is disabled.
        m.script(r"""
          return (async () => {
            const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
            await (await AddonManager.getAddonByID(arguments[0])).disable();
            return true;
          })();
        """, [UBO_ID], chrome=True)
        for label, restart in (("ubo-disabled-control", False), ("ubo-disabled-restart", True)):
            token = label + "-" + os.urandom(8).hex()
            if restart:
                m.close()
                m = open_session(app, base + token)
            else:
                m.cmd("Marionette:SetContext", {"value":"content"})
                m.cmd("WebDriver:Navigate", {"url":base + token})
            wait_for_initial_document(m, base + token)
            measure_ubo_navigation(m, res, origin, token, False, label)
            a = read_ubo_addon(m)
            res.add(label + "-state", bool(a) and a.get("userDisabled") is True and not a.get("active"),
                    "the installed add-on retains its disabled state", {"addon":a})

        m.script(r"""
          return (async () => {
            const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
            await (await AddonManager.getAddonByID(arguments[0])).uninstall();
            return true;
          })();
        """, [UBO_ID], chrome=True)
        for label, reinstall in (("ubo-removed-restart", False), ("ubo-removed-apk-reinstall", True)):
            m.close()
            app.force_stop()
            if reinstall:
                app.install(apk, preserve_state=True)
            token = label + "-" + os.urandom(8).hex()
            m = open_session(app, base + token)
            wait_for_initial_document(m, base + token)
            measure_ubo_navigation(m, res, origin, token, False, label)
            a = read_ubo_addon(m)
            res.add(label + "-state", a is None, "a removed add-on stays absent", {"addon":a})
    finally:
        if m:
            m.close()
        adb.run("reverse", "--remove", "tcp:%d" % remote_port)

# Mozilla's search partner / attribution parameters.  Measured on this build:
# a real query typed into the Fenix toolbar produced
# https://www.google.com/search?client=firefox-b-m&q=... -- client=firefox-b-m
# is exactly the kind of code LW-M4-06 has to remove.
PARTNER_CODE_RE = re.compile(r"[?&](client|pc|channel|form|tag|partner|ref|hspart|hsimp)=([^&]*)", re.I)

# The Fenix address bar.  Compose test tag first, then the older view ids, so
# this keeps working across the toolbar rewrite that is in flight upstream.
URLBAR_IDS = ("ADDRESSBAR_URL_BOX",
              "mozac_browser_toolbar_url_view",
              "org.redoubtbrowser.debug:id/toolbar")

def _node_bounds(xml, ident):
    m = re.search(r'resource-id="[^"]*%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                  % re.escape(ident), xml)
    if not m:
        return None
    return ((int(m.group(1)) + int(m.group(3))) // 2,
            (int(m.group(2)) + int(m.group(4))) // 2)

def apk_search_engines(apk):
    """The engine list Fenix actually ships, read out of the APK."""
    try:
        with zipfile.ZipFile(apk) as z:
            data = json.loads(z.read("assets/search/list.json"))
            plugins = sorted(set(re.sub(r"^assets/searchplugins/|\.xml$", "", n)
                                 for n in z.namelist()
                                 if n.startswith("assets/searchplugins/") and n.endswith(".xml")))
        return data, plugins
    except KeyError:
        return None, []

def check_search(m, res, adb, apk, app=None, scheme=None):
    """LW-M4-06's acceptance says 'verified from a real query', and it has to be:
    Services.search DOES NOT EXIST in GeckoView (measured -- the chrome script
    raises "Services.search is undefined"), so the engine list is not readable
    from Gecko at all.  Fenix owns it, so the query has to be typed into the
    Fenix toolbar like a user would."""
    token = "lwsmokeq%d" % int(time.time() % 100000)
    adb.shell("uiautomator dump /sdcard/lw-smoke-ui.xml", timeout=60)
    xml = adb.shell("cat /sdcard/lw-smoke-ui.xml", timeout=60)
    pt = None
    for ident in URLBAR_IDS:
        pt = _node_bounds(xml, ident)
        if pt:
            break
    if not pt:
        raise HarnessError("could not find the Fenix address bar in the UI tree (tried %s). "
                           "Without it there is no way to run a real query, and a static scan "
                           "of the shipped engine list would not satisfy LW-M4-06."
                           % ", ".join(URLBAR_IDS))
    adb.shell("input tap %d %d" % pt, timeout=60)
    time.sleep(2)
    adb.shell("input text %s" % token, timeout=60)
    time.sleep(1)
    adb.shell("input keyevent 66", timeout=60)
    url = None
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            u = m.cmd("WebDriver:GetCurrentURL").get("value", "")
        except MarionetteError:
            u = ""
        if token in u:
            url = u
            break
        time.sleep(1.5)
    if not url:
        adb.shell("uiautomator dump /sdcard/lw-smoke-ui.xml", timeout=60)
        x2 = adb.shell("cat /sdcard/lw-smoke-ui.xml", timeout=60)
        mm = re.search(r'text="(https?://[^"]*%s[^"]*)"' % token, x2)
        url = mm.group(1).replace("&amp;", "&") if mm else None
    if not url:
        res.add("check-search", False,
                "the typed query never produced a URL containing %r -- search did not run" % token)
        return False
    codes = PARTNER_CODE_RE.findall(url)
    host = re.sub(r"^https?://", "", url).split("/")[0]
    # The legacy bundle (assets/search/list.json + searchplugins/*.xml) is what
    # an APK scan sees, and since search-config.patch it is unreachable: Fenix
    # builds its list from the app-services search-config-v2 dump.  Reported as
    # context only; the engine set the user gets is read off the running app.
    _engines, plugins = apk_search_engines(apk)
    expected, expected_default = expected_engines()
    shown, shown_default = [], None
    if app is not None and scheme:
        _deeplink(adb, app.pkg, scheme, "settings_search_engine")
        sxml, spt = _find_row(adb, "Default search engine")
        if spt:
            after = sxml[sxml.find('text="Default search engine"') + 20:]
            m2 = re.search(r'text="([^"]+)"', after)
            shown_default = html.unescape(m2.group(1)) if m2 else None
            adb.shell("input tap %d %d" % spt, timeout=60)
            time.sleep(2.5)
            shown = _ui_texts(_ui_dump(adb))
            adb.shell("input keyevent 4", timeout=60)
        adb.shell("input keyevent 4", timeout=60)
    missing = [n for n in expected if n not in shown]
    default_ok = bool(expected_default) and shown_default == expected_default
    ok = not codes and not missing and default_ok
    res.add("check-search", ok,
            ("real query went to %s with no partner/attribution parameter; Settings > Search "
             "lists every LibreWolf engine (%s) and the default is %r, as in "
             "assets/search-config-v2.json" % (host, ", ".join(expected), shown_default))
            if ok else
            ("real query URL %s carries %s; engines missing from the running app's list: %s "
             "(shown: %s); default shown=%r expected=%r -- owned by LW-M4-06"
             % (url[:160], ["%s=%s" % c for c in codes] or "no partner code",
                missing or "none", shown[:12], shown_default, expected_default)),
            {"url": url, "partner_codes": ["%s=%s" % c for c in codes],
             "expected_engines": expected, "expected_default": expected_default,
             "shown_engine_screen": shown[:60], "shown_default": shown_default,
             "legacy_bundle_plugins": len(plugins)})
    return ok


# --------------------------------------------------------------------------
# Fenix UI helpers shared by the search gates (LW-M4-06 / LW-M4-11).  The
# toolbar and the settings screens are Kotlin/Compose views: Marionette cannot
# see them, so the evidence comes from uiautomator dumps and the packet capture.
# --------------------------------------------------------------------------
def _ui_dump(adb):
    adb.shell("uiautomator dump /sdcard/lw-smoke-ui.xml", timeout=60)
    return adb.shell("cat /sdcard/lw-smoke-ui.xml", timeout=60)

def _text_bounds(xml, text):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(text), xml)
    if not m:
        return None
    return ((int(m.group(1)) + int(m.group(3))) // 2,
            (int(m.group(2)) + int(m.group(4))) // 2)

def _ui_texts(xml):
    return [html.unescape(t) for t in re.findall(r'text="([^"]*)"', xml) if t]

def _screen_size(adb):
    m = re.search(r"(\d+)x(\d+)", adb.shell("wm size", timeout=30))
    return (int(m.group(1)), int(m.group(2))) if m else (1080, 1920)

def _find_row(adb, text, max_scrolls=6):
    """(xml, centre) of the first node whose text is exactly `text`, scrolling the
    screen down when it is below the fold.  centre is None when it never appears."""
    w, h = _screen_size(adb)
    xml = ""
    for _ in range(max_scrolls + 1):
        xml = _ui_dump(adb)
        pt = _text_bounds(xml, text)
        if pt:
            return xml, pt
        adb.shell("input swipe %d %d %d %d 300" % (w // 2, int(h * 0.78), w // 2, int(h * 0.3)),
                  timeout=60)
        time.sleep(1.2)
    return xml, None

def _switch_after(xml, text):
    """Checked state of the first android.widget.Switch that follows the node
    carrying `text` -- a SwitchPreferenceCompat row lays its widget out after
    its title.  None when there is no such row."""
    i = xml.find('text="%s"' % text)
    if i < 0:
        return None
    m = re.search(r'class="android.widget.Switch"[^>]*checkable="true"[^>]*checked="(true|false)"',
                  xml[i:])
    return None if not m else (m.group(1) == "true")

def _deeplink(adb, pkg, scheme, path):
    """Same intent the strings walker uses: HomeDeepLinkIntentProcessor maps
    <scheme>://settings_search_engine to the Search settings screen."""
    adb.shell("am start -a android.intent.action.VIEW -d '%s://%s' %s" % (scheme, path, pkg),
              timeout=90)
    time.sleep(3)

def deeplink_scheme(args, sdk, apk):
    """The APK's own scheme when aapt2 is around to read it; otherwise the one
    LW-M4-07's branding.patch registers, said out loud."""
    if args.strings_scheme:
        return args.strings_scheme
    try:
        return apk_deeplink_scheme(find_aapt2(args.aapt2, sdk), apk)
    except HarnessError as e:
        log("deep-link scheme: aapt2 unavailable (%s); assuming 'redoubt' (branding.patch). "
            "If the deep link opens nothing the checks below FAIL, they do not pass." % e)
        return "redoubt"

def expected_engines():
    """LibreWolf's engine set for an all-regions-and-locales user and its global
    default, read from the SAME asset scripts/librewolf-patches.py ships into
    the app-services dump -- so the gate compares the running app against what
    the repository says, not against a list written into the harness."""
    path = os.path.join(os.environ.get("LW_SMOKE_REPO", "."), "assets", "search-config-v2.json")
    with open(path) as f:
        cfg = json.load(f)
    names, by_id, default_id = [], {}, None
    for r in cfg["data"]:
        if r.get("recordType") == "engine":
            by_id[r["identifier"]] = r["base"]["name"]
            if any((v.get("environment") or {}).get("allRegionsAndLocales")
                   for v in r.get("variants", [])):
                names.append(r["base"]["name"])
        elif r.get("recordType") == "defaultEngines":
            default_id = r.get("globalDefault")
    return names, by_id.get(default_id)

# Hosts of the sponsored top-sites feed.  In 153 "Contile" is the MARS / Mozilla
# ads client at ads.mozilla.org (measured by LW-M4-10, see no-onboarding.patch);
# the old contile host is kept so a rebase that brings it back is still caught.
SPONSORED_TILE_HOSTS = ("ads.mozilla.org", "contile.services.mozilla.com")

def check_no_suggest(app, adb, pcap, capture_seconds, res, scheme):
    """Check typing payloads as well as handshakes, with a real search control."""
    from urllib.parse import urlsplit, parse_qs
    require_pcap(pcap)
    with open(os.path.join(os.environ.get("LW_SMOKE_REPO", "."),
                           "assets", "search-config-v2.json")) as f:
        config = json.load(f)["data"]
    default_id = next(r["globalDefault"] for r in config
                      if r.get("recordType") == "defaultEngines")
    search = next(r["base"]["urls"]["search"] for r in config
                  if r.get("identifier") == default_id)
    search_host = urlsplit(search["base"]).hostname
    search_param = search.get("searchTermParamName", "q")
    app.push_debug_config()
    app.force_stop()
    time.sleep(1)
    guest = app.guest_ips()
    off_all = pcap_size(pcap)
    app.start_home()
    time.sleep(8)
    xml = _ui_dump(adb)
    pt = next((p for ident in URLBAR_IDS for p in [_node_bounds(xml, ident)] if p), None)
    if not pt:
        raise HarnessError("could not find the Fenix address bar; typing check cannot run")
    adb.shell("input tap %d %d" % pt, timeout=60)
    time.sleep(2)
    token = "lwsmokeq%d" % int(time.time() % 100000)
    off_typing = pcap_size(pcap)
    for chunk in (token[:3], token[3:7], token[7:]):
        adb.shell("input text %s" % chunk, timeout=60)
        time.sleep(1.5)
    log("check-no-suggest: typed %r into the toolbar; idling %ds WITHOUT pressing Enter "
        "(device addresses: %s)" % (token, capture_seconds, ", ".join(sorted(guest))))
    time.sleep(capture_seconds)
    off_enter = pcap_size(pcap)
    guest.update(app.guest_ips())
    typing_rows = summarise_capture(pcap, off_typing, guest_ips=guest)
    typing_app = [r for r in typing_rows if not r["os_noise"] and not r.get("harness")]
    typing_payloads = pcap_payloads(pcap, off_typing, guest, off_enter)
    suspect_payloads = [r for r in typing_payloads if not r["background"]]
    sys.stdout.write(render_capture(typing_rows))

    # Enter alone commits the original query. Retyping a character here could
    # turn an accidental suggestion request into the supposed search control.
    adb.shell("input keyevent 66", timeout=60)
    deadline = time.time() + max(90, capture_seconds * 2)
    search_bytes, enter_payloads = 0, []
    while time.time() < deadline:
        time.sleep(3)
        guest.update(app.guest_ips())
        enter_payloads = pcap_payloads(pcap, off_enter, guest)
        search_bytes = sum(r["bytes"] for r in enter_payloads
                           if r["host"] == search_host and r["protocol"] == "tcp")
        if search_bytes:
            break
    dpcap = pcap_size(pcap) - off_enter
    log("check-no-suggest: post-Enter window closed -- %d outbound payload bytes on "
        "%s connections, %d total capture bytes" % (search_bytes, search_host, dpcap))
    # Payload bytes alone can be unrelated traffic. Marionette must also read
    # the submitted token from the actual default engine's query URL.
    url, document = "", {}
    if search_bytes:
        session = app.connect_marionette()
        try:
            deadline = time.time() + 30
            while time.time() < deadline:
                url = session.cmd("WebDriver:GetCurrentURL").get("value", "")
                parsed = urlsplit(url)
                document = session.script('return {uri: document.documentURI, '
                                          'ready: document.readyState, title: document.title};')
                document_url = urlsplit(document.get("uri", ""))
                if (parsed.hostname == search_host and
                        token in parse_qs(parsed.query).get(search_param, []) and
                        document_url.hostname == search_host and
                        token in parse_qs(document_url.query).get(search_param, []) and
                        document.get("ready") == "complete"):
                    break
                time.sleep(1)
        finally:
            session.close()
    parsed = urlsplit(url)
    document_url = urlsplit(document.get("uri", ""))
    searched = (search_bytes > 0 and parsed.hostname == search_host and
                token in parse_qs(parsed.query).get(search_param, []) and
                document_url.hostname == search_host and
                token in parse_qs(document_url.query).get(search_param, []) and
                document.get("ready") == "complete")
    log("check-no-suggest: post-Enter navigation %r" % url)

    guest.update(app.guest_ips())
    all_rows = summarise_capture(pcap, off_all, guest_ips=guest)
    sponsored = [r for r in all_rows
                 if any(h in (r["detail"] or "").lower() for h in SPONSORED_TILE_HOSTS)]
    _deeplink(adb, app.pkg, scheme, "settings_search_engine")
    sxml, spt = _find_row(adb, "Show search suggestions")
    switch = _switch_after(sxml, "Show search suggestions") if spt else None
    toggled = {}
    if switch is False:
        position = _switch_bounds_after(sxml, "Show search suggestions")
        if position:
            try:
                adb.shell("input tap %d %d" % position, timeout=60)
                time.sleep(1.5)
                toggled["on"] = _switch_after(_ui_dump(adb), "Show search suggestions")
            finally:
                current = _ui_dump(adb)
                if _switch_after(current, "Show search suggestions") is True:
                    position = _switch_bounds_after(current, "Show search suggestions")
                    if position:
                        adb.shell("input tap %d %d" % position, timeout=60)
                        time.sleep(1.5)
                toggled["restored_off"] = _switch_after(_ui_dump(adb), "Show search suggestions") is False
    adb.shell("input keyevent 4", timeout=60)

    problems = []
    if suspect_payloads:
        problems.append("typing emitted %d outbound payload bytes on %d packet(s), "
                        "including reused TLS connections; quiet typing is unproven: %s"
                        % (sum(r["bytes"] for r in suspect_payloads), len(suspect_payloads),
                           sorted({r["host"] or r["dst"] for r in suspect_payloads})[:6]))
    if not searched:
        problems.append("search control unproven: %d payload bytes to %s, current URL=%r"
                        % (search_bytes, search_host, url))
    if sponsored:
        problems.append("%d event(s) to a sponsored-tile host: %s"
                        % (len(sponsored), sorted({r["detail"] for r in sponsored})[:4]))
    if switch is None:
        problems.append("no 'Show search suggestions' switch found in Settings > Search")
    elif switch:
        problems.append("'Show search suggestions' reads ON by default")
    elif toggled.get("on") is not True or toggled.get("restored_off") is not True:
        problems.append("'Show search suggestions' ON/OFF round trip failed: %r" % toggled)
    ok = not problems
    res.add("check-no-suggest", ok,
            ("typed %r: no outbound transport payload outside explicitly identified "
             "security-settings/OS background flows for %ds; Enter produced %d payload "
             "bytes to %s and the actual URL contains the submitted query; no sponsored "
             "host; 'Show search suggestions' OFF by default and ON/OFF round trip verified"
             % (token, capture_seconds, search_bytes, search_host)) if ok else
            "; ".join(problems) + " -- owned by LW-M4-11",
            {"token": token, "url_after_enter": url, "search_document": document,
             "typing_events": typing_app[:100],
             "typing_payloads": typing_payloads, "enter_payloads": enter_payloads,
             "sponsored_events": sponsored[:50], "suggestions_switch": switch,
             "suggestions_toggle_round_trip": toggled,
             "typing_capture_offset": off_typing, "enter_capture_offset": off_enter,
             "app_capture_offset": off_all, "guest_ips": sorted(guest),
             "post_enter_pcap_bytes": dpcap, "post_enter_search_payload_bytes": search_bytes,
             "capture_seconds": capture_seconds})
    return ok

# LW-M6-06.  The update host, overridable for a build made with
# -PlwUpdateCheckEndpoint pointing somewhere else.
UPDATE_CHECK_HOSTS = tuple(h for h in (os.environ.get("LW_SMOKE_UPDATE_HOST", ""), "redoubtbrowser.org") if h)

def _switch_bounds_after(xml, text):
    i = xml.find('text="%s"' % text)
    if i < 0:
        return None
    m = re.search(r'class="android.widget.Switch"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml[i:])
    if not m:
        return None
    return ((int(m.group(1)) + int(m.group(3))) // 2, (int(m.group(2)) + int(m.group(4))) // 2)

def check_update_privacy(app, adb, pcap, capture_seconds, res, scheme):
    """LW-M6-06.  Measured on the running build, from the emulator's own capture:
      OFF  (the default): launch, idle, open Settings -- no event to an update
           host.  This is the store-build invariant too: a build made without a
           verification key has no "Check for updates" row at all.
      ON   (only if the row exists; flipped through the UI like a user would):
           relaunch and idle -- the update host is contacted, and NOTHING else
           that was not already seen in the OFF window.  The endpoint need not
           resolve: the DNS query alone shows the check ran and where it went."""
    require_pcap(pcap)
    app.force_stop()
    time.sleep(1)
    guest = app.guest_ips()

    def hits(rows):
        return [r for r in rows if not r["os_noise"] and not r.get("harness")
                and any(h in (r["detail"] or "").lower() for h in UPDATE_CHECK_HOSTS)]

    # ---- OFF ------------------------------------------------------------
    off0 = pcap_size(pcap)
    app.start_home()
    time.sleep(max(15, capture_seconds // 2))
    _deeplink(adb, app.pkg, scheme, "settings_privacy")
    time.sleep(2)
    sxml, spt = _find_row(adb, "Check for updates", max_scrolls=16)
    compiled_in = spt is not None
    time.sleep(5)
    guest.update(app.guest_ips())
    rows_off = summarise_capture(pcap, off0, guest_ips=guest)
    app_off = [r for r in rows_off if not r["os_noise"] and not r.get("harness")]
    off_hits = hits(rows_off)
    seen_off = {(r["detail"] or r["dst"]) for r in app_off}
    if not rows_off:
        res.add("check-update-privacy", False,
                "CAPTURE PRODUCED ZERO EVENTS in the OFF window -- a dead capture contains no "
                "update host either, and this gate refuses to pass on that ambiguity",
                {"total_events": 0})
        return False

    problems = []
    evidence = {"compiled_in": compiled_in, "hosts_checked": list(UPDATE_CHECK_HOSTS),
                "off_window_app_events": app_off[:100], "off_window_update_hits": off_hits[:20]}
    if off_hits:
        problems.append("%d event(s) to an update host with the check OFF (or absent): %s"
                        % (len(off_hits), sorted({r["detail"] for r in off_hits})[:4]))

    # ---- ON -------------------------------------------------------------
    if compiled_in:
        state = _switch_after(sxml, "Check for updates")
        if state is None:
            problems.append("'Check for updates' row found but no switch after it")
        elif state:
            problems.append("'Check for updates' reads ON by default")
        else:
            sw = _switch_bounds_after(sxml, "Check for updates")
            adb.shell("input tap %d %d" % sw, timeout=60)
            time.sleep(1.5)
            now_on = _switch_after(_ui_dump(adb), "Check for updates")
            evidence["switch_after_tap"] = now_on
            if not now_on:
                problems.append("tapping the switch did not turn it on")
            else:
                app.force_stop()
                time.sleep(1)
                off1 = pcap_size(pcap)
                app.start_home()
                log("check-update-privacy: switch ON, relaunched; idling %ds" % max(30, capture_seconds // 2))
                time.sleep(max(30, capture_seconds // 2))
                guest.update(app.guest_ips())
                rows_on = summarise_capture(pcap, off1, guest_ips=guest)
                app_on = [r for r in rows_on if not r["os_noise"] and not r.get("harness")]
                on_hits = hits(rows_on)
                new_hosts = sorted({(r["detail"] or r["dst"]) for r in app_on} - seen_off
                                   - {r["detail"] for r in on_hits})
                evidence["on_window_app_events"] = app_on[:100]
                evidence["on_window_update_hits"] = on_hits[:20]
                evidence["on_window_new_hosts_not_update"] = new_hosts
                sys.stdout.write(render_capture(rows_on))
                if not on_hits:
                    problems.append("switch ON, relaunched, and NO event to an update host in the "
                                    "window -- the check did not run, so nothing about it is proven")
                if new_hosts:
                    problems.append("with the check ON, %d host(s) appeared that the OFF window did not "
                                    "have and that are not the update host: %s" % (len(new_hosts), new_hosts[:6]))
                # leave the profile as we found it
                _deeplink(adb, app.pkg, scheme, "settings_privacy")
                sxml2, spt2 = _find_row(adb, "Check for updates", max_scrolls=16)
                if spt2 and _switch_after(sxml2, "Check for updates"):
                    adb.shell("input tap %d %d" % _switch_bounds_after(sxml2, "Check for updates"), timeout=60)
    ok = not problems
    res.add("check-update-privacy", ok,
            (("update check compiled in: OFF by default, no update-host traffic across launch + "
              "Settings (%d app events); switched ON through the UI, the update host was "
              "contacted on relaunch and nothing else new" % len(app_off))
             if compiled_in else
             ("no 'Check for updates' row (compiled out, as a store build should be) and no "
              "update-host traffic across launch + Settings (%d app events)" % len(app_off)))
            if ok else "; ".join(problems) + " -- owned by LW-M6-06",
            evidence)
    return ok

NOT_IMPLEMENTED = {
}

# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv):
    ap = argparse.ArgumentParser(prog="android-smoke.sh", add_help=True,
                                 description="Redoubt smoke-test harness "
                                             "(see docs/android/SMOKE.md)")
    ap.add_argument("--emulator", action="store_true",
                    help="boot a headless x86_64 emulator with packet capture and use it")
    ap.add_argument("--serial", help="use this already-running device/emulator")
    ap.add_argument("--sdk", help="Android SDK root")
    ap.add_argument("--apk", help="APK to test")
    ap.add_argument("--work", help="work directory (default $HOME/.cache/librewolf-android-smoke)")
    ap.add_argument("--abi", default="x86_64", help="preferred APK ABI (default x86_64)")
    ap.add_argument("--aapt2", help="aapt2 binary for --check-strings (default: auto-detect)")
    # --check-strings, running-app half (LW-M4-12).
    ap.add_argument("--strings-locale", action="append", metavar="BCP47",
                    help="run --check-strings' running-app traversal in this system "
                         "locale as well; repeatable. Bare --strings-locale-sweep uses "
                         "the transliterating set %s. Needs a rootable image."
                         % ",".join(UI_SCAN_LOCALES))
    ap.add_argument("--strings-locale-sweep", action="store_true",
                    help="shorthand for --strings-locale on each of %s plus the "
                         "device's own locale" % ",".join(UI_SCAN_LOCALES))
    ap.add_argument("--strings-scheme", default=None,
                    help="deep-link scheme the build under test registers "
                         "(default: read from the APK)")
    ap.add_argument("--strings-depth", type=int, default=1,
                    help="levels of clickable rows the traversal opens below each "
                         "deep-linked screen (default 1)")
    ap.add_argument("--strings-max-taps", type=int, default=14,
                    help="cap on rows the traversal opens per screen (default 14)")
    ap.add_argument("--dns-server",
                    help="resolver for the emulator to use, e.g. 9.9.9.9. Without it the "
                         "emulator uses the host's resolvers, which on a machine whose LAN "
                         "resolver sinkholes telemetry hosts silently understates a capture. "
                         "Also settable as LW_SMOKE_DNS.")
    ap.add_argument("--keep-emulator", action="store_true", help="leave the emulator running")
    ap.add_argument("--keep-state", action="store_true",
                    help="do not wipe app data before the run")
    ap.add_argument("--json", help="write the full machine-readable result here")
    ap.add_argument("--capture-seconds", type=int, default=60,
                    help="idle window for --network-capture / --first-run-capture")
    ap.add_argument("--pref-dump", action="store_true")
    ap.add_argument("--network-capture", action="store_true")
    ap.add_argument("--first-run-capture", action="store_true")
    ap.add_argument("--self-test", action="store_true",
                    help="prove the harness reports failure when a probe fails")
    for f in ("ubo", "ubo-preinstall", "ubo-lifecycle", "search", "no-gms", "no-adjust",
              "aboutconfig", "no-suggest", "strings", "update-privacy",
              "no-remote-settings", "https-only"):
        ap.add_argument("--check-" + f, action="store_true")
    args = ap.parse_args(argv)
    if (args.check_ubo_preinstall or args.check_ubo_lifecycle) and args.keep_state:
        raise HarnessError("uBO first-install checks require an empty app profile; omit --keep-state")

    for flag, why in NOT_IMPLEMENTED.items():
        if getattr(args, flag[2:].replace("-", "_")):
            print("android-smoke: %s is NOT IMPLEMENTED and is not a pass.\n  %s"
                  % (flag, why), file=sys.stderr)
            return EXIT_UNIMPLEMENTED

    if args.dns_server:
        os.environ["LW_SMOKE_DNS"] = args.dns_server
    work = args.work or WORK
    os.makedirs(work, exist_ok=True)
    res = Results()

    # A deliberate escape hatch for negative controls -- see SMOKE.md, "proving
    # a check can fail".  It is loud, it is recorded, and a run that used it can
    # never report success, so it cannot be used to make a gate go green.
    extra_prefs = {}
    if os.environ.get("LW_SMOKE_EXTRA_PREFS"):
        extra_prefs = json.loads(os.environ["LW_SMOKE_EXTRA_PREFS"])
        log("!" * 60)
        log("DIAGNOSTIC RUN: injecting prefs into the app at startup: %s"
            % json.dumps(extra_prefs, sort_keys=True))
        log("This run cannot report success. It is not a gate.")
        log("!" * 60)
    globals()["_EXTRA_PREFS"] = extra_prefs

    # ---- static checks first: they need only the APK ----------------------
    sdk = find_sdk(args.sdk)
    adb = Adb(find_adb(sdk), args.serial or os.environ.get("ANDROID_SERIAL"))
    apk = find_apk(args.apk, args.abi)
    with open(apk, "rb") as artifact:
        res.artifact = {"path":os.path.abspath(apk),
                        "sha256":hashlib.file_digest(artifact, "sha256").hexdigest(),
                        "size":os.path.getsize(apk)}
    harness_path = os.path.join(os.environ.get("LW_SMOKE_REPO", "."), "scripts/android-smoke.sh")
    if os.path.isfile(harness_path):
        with open(harness_path, "rb") as driver:
            res.artifact["harness_sha256"] = hashlib.file_digest(driver, "sha256").hexdigest()
    res.checkpoint = lambda: write_results(res, args, work, "running")
    res.checkpoint()
    pkg = apk_package(apk)
    log("apk=%s" % apk)
    log("package=%s" % pkg)

    static_only = (args.check_no_gms or args.check_no_adjust or args.check_strings) and not (
        args.emulator or args.serial or args.pref_dump or args.network_capture
        or args.first_run_capture or args.check_ubo or args.check_search
        or args.check_aboutconfig or args.check_no_suggest or args.check_update_privacy
        or args.check_ubo_preinstall or args.check_ubo_lifecycle or args.check_https_only or args.self_test)
    if args.check_no_gms:
        check_no_gms(apk, res)
    if args.check_no_adjust:
        check_no_adjust(apk, res)
    # --check-strings has two halves (LW-M4-12).  The resource-table half needs
    # only the APK and runs here; the running-app traversal needs the app
    # installed, so with a device it runs from the device section below.
    strings_on_device = args.check_strings and (args.emulator or args.serial
                                                or os.environ.get("ANDROID_SERIAL"))
    if args.check_strings and not strings_on_device:
        check_strings(apk, res, find_aapt2(args.aapt2, sdk), work)
    if static_only:
        return finish(res, args, work)

    # ---- device ----------------------------------------------------------
    emu = None
    pcap = os.environ.get("LW_SMOKE_PCAP")
    if args.emulator:
        emu = Emulator(sdk, work, adb)
        emu.boot()
        pcap = emu.pcap
    else:
        devs = adb.devices()
        if not devs:
            raise HarnessError("no device. Pass --emulator to have the harness boot one, "
                               "or start one yourself and pass --serial.")
        if adb.serial is None:
            if len(devs) > 1:
                raise HarnessError("%d devices attached; pass --serial" % len(devs))
            adb.serial = devs[0]
        log("using device %s" % adb.serial)

    app = App(adb, pkg, work)
    app.extra_prefs = extra_prefs
    origin = None
    m = None
    bootstrap_reverse = None
    try:
        app.install(apk, preserve_state=args.keep_state)
        if not args.keep_state:
            app.wipe()
        keep_screen_awake(adb)

        # ---- --check-strings with a device: resource table AND a UI walk ---
        if strings_on_device:
            locs = list(args.strings_locale or [])
            if args.strings_locale_sweep:
                locs = ["device"] + [l for l in UI_SCAN_LOCALES if l not in locs] + locs
            aapt2 = find_aapt2(args.aapt2, sdk)
            scheme = args.strings_scheme or apk_deeplink_scheme(aapt2, apk)
            log("check-strings: deep-link scheme %s" % scheme)
            check_strings(apk, res, aapt2, work, adb=adb, pkg=pkg, scheme=scheme,
                          locales=locs or ["device"], depth=args.strings_depth,
                          max_taps=args.strings_max_taps)
            return finish(res, args, work)

        # ---- first-run capture: nothing may leave before the first URL ----
        if args.first_run_capture:
            require_pcap(pcap)
            app.push_debug_config()
            app.force_stop()
            time.sleep(2)
            rb0, tb0 = app.rx_tx()
            off = pcap_size(pcap)
            guest = app.guest_ips()
            log("first-run window: launching the home screen and idling %ds "
                "(device addresses: %s)" % (args.capture_seconds, ", ".join(sorted(guest))))
            app.start_home()
            time.sleep(args.capture_seconds)
            guest.update(app.guest_ips())
            if pcap_size(pcap) <= off:
                raise HarnessError("no captured packets in first-run window; capture readiness is unproven")
            rows = summarise_capture(pcap, off, guest_ips=guest)
            rb1, tb1 = app.rx_tx()
            app_rows = [r for r in rows if not r["os_noise"] and not r.get("harness")]
            ok = not app_rows
            sys.stdout.write(render_capture(rows))
            res.add("first-run-capture", ok,
                    ("no non-OS traffic in %ds between install and the first navigation "
                     "(app uid bytes rx+%d tx+%d)" % (args.capture_seconds, rb1 - rb0, tb1 - tb0))
                    if ok else
                    ("%d outbound event(s) before any navigation, e.g. %s (app uid bytes "
                     "rx+%d tx+%d) -- owned by LW-M4-10"
                     % (len(app_rows), sorted({r["detail"] or r["dst"] for r in app_rows})[:8],
                        rb1 - rb0, tb1 - tb0)),
                    {"events": app_rows[:200], "uid_rx": rb1 - rb0, "uid_tx": tb1 - tb0,
                     "capture_offset": off, "capture_end": pcap_size(pcap),
                     "guest_ips": sorted(guest)})
            return finish(res, args, work)

        # ---- --check-no-remote-settings: the three RS hosts must be absent ----
        if args.check_no_remote_settings:
            require_pcap(pcap)
            app.push_debug_config()
            app.force_stop()
            time.sleep(2)
            off = pcap_size(pcap)
            guest = app.guest_ips()
            log("check-no-remote-settings: launching the home screen and idling %ds "
                "(device addresses: %s)" % (args.capture_seconds, ", ".join(sorted(guest))))
            app.start_home()
            time.sleep(args.capture_seconds)
            guest.update(app.guest_ips())
            if pcap_size(pcap) <= off:
                raise HarnessError("no captured packets in Remote Settings window; capture readiness is unproven")
            sys.stdout.write(render_capture(
                summarise_capture(pcap, off, guest_ips=guest)))
            ok = check_no_remote_settings(pcap, off, guest, args.capture_seconds, res)
            res.rows[-1]["evidence"].update({"capture_offset": off,
                                          "capture_end": pcap_size(pcap),
                                          "guest_ips": sorted(guest)})
            return finish(res, args, work)

        # ---- --check-no-suggest: nothing leaves the toolbar before Enter ----
        if args.check_no_suggest:
            check_no_suggest(app, adb, pcap, args.capture_seconds, res,
                             deeplink_scheme(args, sdk, apk))
            return finish(res, args, work)

        # ---- --check-update-privacy: opt-in, and silent when off (LW-M6-06) ----
        if args.check_update_privacy:
            check_update_privacy(app, adb, pcap, args.capture_seconds, res,
                                 deeplink_scheme(args, sdk, apk))
            return finish(res, args, work)

        # ---- the origin server and the browsing session -------------------
        ca_b64 = mint_certs(os.path.join(work, "harness"))
        video = base64.b64decode(open(os.path.join(HARNESS, "fixture-video.b64")).read())
        http_port, https_port = free_port(), free_port()
        origin = Origin(os.path.join(work, "harness"), http_port, https_port, video)
        http_url = "http://10.0.2.2:%d/" % http_port
        https_url = "https://10.0.2.2:%d/" % https_port
        log("origin: %s and %s" % (http_url, https_url))

        if args.check_ubo_preinstall or args.check_ubo_lifecycle:
            run_ubo_behavior(app, adb, apk, origin, res, lifecycle=args.check_ubo_lifecycle)
            return finish(res, args, work)

        # Start on loopback so a secure-by-default browser can create its first
        # session without a certificate exception or weakening HTTPS-only.
        bootstrap_reverse = "tcp:%d" % http_port
        adb.run("reverse", bootstrap_reverse, bootstrap_reverse, check=True)
        bootstrap_url = "http://127.0.0.1:%d/empty" % http_port

        cap_off = pcap_size(pcap) if pcap else 0
        m = open_session(app, bootstrap_url)
        wait_for_initial_document(m, bootstrap_url)
        build = m.script('return {version: Services.appinfo.version, '
                         'buildID: Services.appinfo.appBuildID, name: Services.appinfo.name, '
                         'os: Services.appinfo.OS};', chrome=True)
        log("under test: %s %s buildID=%s" % (build["name"], build["version"], build["buildID"]))
        # Trust the throwaway CA for this profile so the https check exercises a
        # real chain validation instead of an acceptInsecureCerts bypass.
        m.script('const db = Cc["@mozilla.org/security/x509certdb;1"]'
                 '.getService(Ci.nsIX509CertDB);'
                 'return db.addCertFromBase64(arguments[0], "CTu,CTu,CTu").commonName;',
                 [ca_b64], chrome=True)
        m.cmd("Marionette:SetContext", {"value": "content"})

        # ---- flag-driven single-purpose runs ------------------------------
        if args.pref_dump:
            text, rows = do_pref_dump(m, work)
            sys.stdout.write(text)
            missing = [r["name"] for r in rows if r["type"] == "missing"]
            res.add("pref-dump", True,
                    "%d prefs dumped (%d missing in this build: %s)"
                    % (len(rows), len(missing), ", ".join(missing[:6]) or "none"),
                    {"missing": missing})
            return finish(res, args, work)

        if args.network_capture:
            require_pcap(pcap)
            log("capture window: browsing for %ds" % args.capture_seconds)
            off = pcap_size(pcap)
            m.cmd("WebDriver:Navigate", {"url": http_url})
            time.sleep(args.capture_seconds)
            rows = summarise_capture(pcap, off, (http_port, https_port), app.guest_ips())
            sys.stdout.write(render_capture(rows))
            res.add("network-capture", True,
                    "%d events (%d outside the OS-noise allowlist and not to the harness "
                    "origin) in %ds"
                    % (len(rows), len([r for r in rows
                                       if not r["os_noise"] and not r["harness"]]),
                       args.capture_seconds),
                    {"events": rows[:400]})
            return finish(res, args, work)

        if args.check_aboutconfig:
            # The session is replaced by the restart this check performs, so the
            # finally block below cleans up the live one.
            _ok, m = check_aboutconfig(m, res, app, apk, bootstrap_url)
            return finish(res, args, work)
        if args.check_https_only:
            check_pageload(m, res, origin, http_url, https_url)
            return finish(res, args, work)
        if args.check_ubo:
            check_ubo(m, res)
            return finish(res, args, work)
        if args.check_search:
            check_search(m, res, adb, apk, app, deeplink_scheme(args, sdk, apk))
            return finish(res, args, work)

        # ---- the default suite --------------------------------------------
        ff = args.self_test
        check_pageload(m, res, origin, http_url, https_url, forcefail=ff)
        check_webgl(m, res, forcefail=ff)
        m.cmd("WebDriver:Navigate", {"url": https_url})
        check_video(m, res, origin, forcefail=ff)
        check_gum(m, res, app, adb, forcefail=ff)
        check_extension(m, res, base64.b64encode(
            open(build_probe_xpi(os.path.join(work, "harness", "probe.xpi")), "rb").read()
        ).decode(), https_url, forcefail=ff)
        text, rows = do_pref_dump(m, work)
        canary = {r["name"]: r for r in rows}.get("librewolf.webgl.prompt")
        res.add("pref-dump", canary is not None and canary["type"] != "missing",
                "written to %s (%d prefs; librewolf.webgl.prompt=%s)"
                % (os.path.join(work, "prefs.txt"), len(rows),
                   canary["value"] if canary else "ABSENT"),
                {"path": os.path.join(work, "prefs.txt")})
        if args.self_test:
            # The point of --self-test: every probe above ran with forcefail, so
            # the run MUST be red. A green run here means the harness cannot see
            # failure at all, and every gate built on it is decorative.
            broken = [r["check"] for r in res.rows if r["ok"] and r["check"] != "pref-dump"]
            if broken:
                log("SELF-TEST FAILED: these probes reported PASS while being fed a "
                    "deliberately wrong expectation: %s" % broken)
                return EXIT_FAIL
            log("SELF-TEST OK: every probe reported failure when fed a wrong expectation")
            return EXIT_OK
        return finish(res, args, work)
    except Exception as error:
        write_results(res, args, work, "interrupted", str(error))
        raise
    finally:
        # Leave nothing behind that changes how the app behaves afterwards: the
        # debug config would keep Marionette listening on every later launch,
        # and the throwaway CA would stay trusted in the profile.
        if m:
            try:
                m.script('const db = Cc["@mozilla.org/security/x509certdb;1"]'
                         '.getService(Ci.nsIX509CertDB);'
                         'for (const c of db.getCerts()) {'
                         '  if (c.commonName === "LibreWolf Android smoke throwaway CA")'
                         '    db.deleteCertificate(c);'
                         '} return true;', chrome=True)
            except Exception:
                pass
            m.close()
        try:
            app.remove_debug_config()
            app.force_stop()
        except Exception:
            pass
        if origin:
            origin.stop()
        if bootstrap_reverse:
            adb.run("reverse", "--remove", bootstrap_reverse)
        if emu and not args.keep_emulator:
            emu.stop()
        elif emu:
            log("emulator left running as %s (capture: %s)" % (emu.serial, emu.pcap))

def write_results(res, args, work, status, error=None):
    extra = globals().get("_EXTRA_PREFS") or {}
    payload = {"checks": res.rows, "work": work, "injected_prefs": extra,
               "tainted": bool(extra), "artifact":getattr(res, "artifact", None),
               "status": status, "error": error}
    path = args.json or os.path.join(work, "result.json")
    temporary = path + ".tmp"
    with open(temporary, "w") as f:
        json.dump(payload, f, indent=1)
    os.replace(temporary, path)
    return path

def finish(res, args, work):
    path = write_results(res, args, work, "completed")
    extra = globals().get("_EXTRA_PREFS") or {}
    bad = res.failed()
    log("-" * 60)
    log("%d check(s) run, %d failed. Detail: %s" % (len(res.rows), len(bad), path))
    for r in bad:
        log("  FAILED %-20s %s" % (r["check"], r["detail"]))
    if bad:
        return EXIT_FAIL
    if extra:
        log("every check passed, but LW_SMOKE_EXTRA_PREFS injected %s -- a run that "
            "changes the configuration under test is a diagnostic, not a gate."
            % json.dumps(extra, sort_keys=True))
        return EXIT_HARNESS
    return EXIT_OK

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Unimplemented as e:
        print("android-smoke: NOT IMPLEMENTED -- %s" % e, file=sys.stderr)
        sys.exit(EXIT_UNIMPLEMENTED)
    except HarnessError as e:
        print("android-smoke: harness error -- %s" % e, file=sys.stderr)
        sys.exit(EXIT_HARNESS)
    except KeyboardInterrupt:
        print("android-smoke: interrupted", file=sys.stderr)
        sys.exit(EXIT_HARNESS)
PYDRIVEREOF

exec python3 "$DRIVER" "$@"
