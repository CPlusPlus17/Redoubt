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
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
VIDEOEOF

cat > "$DRIVER" <<'PYDRIVEREOF'
#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# The Redoubt smoke harness.  Unpacked from
# scripts/android-smoke.sh; do not edit this copy, edit the script.
# ---------------------------------------------------------------------------
import argparse, base64, json, os, re, shutil, signal, socket, ssl, struct
import subprocess, sys, tempfile, threading, time, zipfile
import http.server

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
                if self.path.startswith("/fixture.webm"):
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
        p = 43
        p += 1 + pl[p]
        p += 2 + struct.unpack(">H", pl[p:p + 2])[0]
        p += 1 + pl[p]
        if p + 2 > len(pl):
            return None
        end = min(p + 2 + struct.unpack(">H", pl[p:p + 2])[0], len(pl))
        p += 2
        while p + 4 <= end:
            et, el = struct.unpack(">HH", pl[p:p + 4])
            p += 4
            if et == 0:
                q = p + 3
                nl = struct.unpack(">H", pl[q:q + 2])[0]
                q += 2
                return pl[q:q + nl].decode("latin1")
            p += el
    except Exception:
        return None
    return None

def pcap_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0

def pcap_events(path, start_offset=0):
    """Yield (ts, kind, detail, src_ip, dst_ip, dst_port).  kind is one of
    dns / sni / http / tcp-syn / udp.  The capture is taken at the virtual NIC
    and therefore contains BOTH directions -- callers must filter on src, or a
    DNS reply gets counted as an outbound request."""
    with open(path, "rb") as f:
        gh = f.read(24)
        if len(gh) < 24:
            return
        endian = "<" if gh[:4] in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        if start_offset > 24:
            f.seek(start_offset)
        while True:
            h = f.read(16)
            if len(h) < 16:
                break
            ts, tu, cl, _ol = struct.unpack(endian + "IIII", h)
            data = f.read(cl)
            if len(data) < cl:
                break
            if len(data) < 34 or struct.unpack(">H", data[12:14])[0] != 0x0800:
                continue
            ip = data[14:]
            ihl = (ip[0] & 0x0F) * 4
            proto = ip[9]
            src = socket.inet_ntoa(ip[12:16])
            dst = socket.inet_ntoa(ip[16:20])
            rest = ip[ihl:]
            t = ts + tu / 1e6
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
        return dst in OS_NOISE_IPS or port in (67, 68, 5353, 123)
    if kind == "tcp-syn":
        return dst in OS_NOISE_IPS
    return False

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
# Results
# --------------------------------------------------------------------------
class Results:
    def __init__(self):
        self.rows = []
    def add(self, name, ok, detail, evidence=None):
        self.rows.append({"check": name, "ok": bool(ok), "detail": detail,
                          "evidence": evidence or {}})
        log("%-22s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
    def failed(self):
        return [r for r in self.rows if not r["ok"]]

# --------------------------------------------------------------------------
# Device / emulator plumbing
# --------------------------------------------------------------------------
def find_sdk(explicit):
    for c in [explicit, os.environ.get("ANDROID_SDK_ROOT"), os.environ.get("ANDROID_HOME"),
              os.path.expanduser("~/lw-m2-04/sdk"), os.path.expanduser("~/Android/Sdk")]:
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
    for d in [os.path.expanduser("~/lw-m2-04/out-make/apk"),
              os.path.expanduser("~/lw-m2-04/out/apk"),
              os.path.join(os.environ.get("LW_SMOKE_REPO", "."), "out", "apk")]:
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".apk") and abi and abi in f:
                    cands.append(os.path.join(d, f))
            for f in sorted(os.listdir(d)):
                if f.endswith(".apk") and "universal" in f:
                    cands.append(os.path.join(d, f))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    raise HarnessError("no APK found for abi=%s. Pass --apk PATH or set LW_SMOKE_APK. "
                       "Looked in ~/lw-m2-04/out-make/apk and ~/lw-m2-04/out/apk." % abi)

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
                        "hw.audioOutput = no\nhw.gpu.enabled = no\nhw.gpu.mode = off\n"
                        "hw.keyboard = yes\nPlayStore.enabled = false\n"
                        "image.androidVersion.api = %d\nfastboot.forceColdBoot = yes\n"
                        % (sysdir, tag, avd_name, avd_name, apinum))
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
                "-gpu", "swiftshader_indirect", "-no-snapshot", "-no-metrics",
                "-port", str(port), "-tcpdump", self.pcap]
        logf = open(os.path.join(self.work, "emulator.log"), "w")
        log("booting emulator %s (%s/%s, x86_64), capture -> %s" % (avd_name, api, tag, self.pcap))
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

class App:
    def __init__(self, adb, pkg, work):
        self.adb, self.pkg, self.work = adb, pkg, work
        self.host_port = None
        self.uid = None
        self.extra_prefs = {}
        self._debuggable = None
        self._set_debug_app = False
    def install(self, apk, reinstall=True):
        log("installing %s (%.0f MB)" % (os.path.basename(apk), os.path.getsize(apk) / 1e6))
        p = self.adb.run("install", "-r", apk, timeout=900)
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
        self.adb.shell("pm clear %s" % self.pkg, timeout=180)
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
        ips.discard("127.0.0.1")
        if not ips:
            raise HarnessError("could not read the device's own IPv4 addresses; "
                               "without them the capture cannot tell a request from a reply")
        return ips

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
            try:
                m = Marionette(self.host_port)
                m.cmd("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {}}})
                return m
            except Exception as e:
                last = e
                time.sleep(3)
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
  out.stage = "readPixels";
  out.ok = true;
} catch (e) { out.reason = "exception: " + e; }
return out;
"""

def check_webgl(m, res, forcefail=False):
    """The L1 canary.  A live context is not enough -- the whole point of L1 is
    that a broken build still creates objects and silently renders nothing, so
    this compiles a shader, draws, and reads the pixel back."""
    lw = m.script('return {prompt: Services.prefs.getPrefType("librewolf.webgl.prompt") ? '
                  'Services.prefs.getBoolPref("librewolf.webgl.prompt") : null, '
                  'type: Services.prefs.getPrefType("librewolf.webgl.prompt"), '
                  'locked: Services.prefs.prefIsLocked("librewolf.webgl.prompt")};', chrome=True)
    r = m.script(JS_WEBGL)
    expect = [51, 102, 153, 255] if not forcefail else [1, 2, 3, 4]
    ok = bool(r.get("ok")) and r.get("pixel") == expect
    if lw.get("type") == 0:
        ok = False
        why = ("librewolf.webgl.prompt DOES NOT EXIST in this build -- the L1 guard is gone. "
               "See docs/android/AGENTS.md landmine L1.")
    elif lw.get("prompt") is True:
        ok = False
        why = ("librewolf.webgl.prompt is TRUE on Android -- this is landmine L1 and every "
               "WebGL context in the build is dead. Pixel readback: %s" % (r.get("pixel"),))
    elif ok:
        why = "%s ctx, shader+draw+readPixels gave %s, renderer=%r" % (
            r.get("contextType"), r.get("pixel"), r.get("renderer"))
    else:
        why = ("no verified pixel (stage=%s reason=%s creationErrors=%s pixel=%s). "
               "librewolf.webgl.prompt=%s -- if that is false the cause is the GL stack "
               "under the emulator, not L1." % (
                   r.get("stage"), r.get("reason"), r.get("creationErrors"),
                   r.get("pixel"), lw.get("prompt")))
    res.add("webgl", ok, why, {"gl": r, "librewolf.webgl.prompt": lw})
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

def check_pageload(m, res, origin, http_url, https_url, forcefail=False):
    ok_all = True
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

def check_no_gms(apk, res):
    needles = ["com.google.android.gms", "com/google/android/gms", "Lcom/google/android/gms"]
    hits, entries = scan_apk(apk, needles)
    lib_hits = [e for e in entries if "gms" in e.lower()]
    total = sum(len(v) for v in hits.values())
    ok = total == 0 and not lib_hits
    res.add("check-no-gms", ok,
            ("no com.google.android.gms strings in any classes*.dex and no gms entries in the apk"
             if ok else
             "%d distinct GMS strings in the dex string table (e.g. %s) and %d apk entries -- "
             "owned by LW-M4-05" % (total, sorted(list(hits.get(needles[0], set()) |
                                                       hits.get(needles[1], set())))[:3],
                                    len(lib_hits))),
            {"hits": {k: sorted(v)[:20] for k, v in hits.items()}, "apk_entries": lib_hits[:20]})
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
JS_ABOUTCONFIG_TOGGLE = r"""
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
      li.querySelector(".pref-button.toggle").click();
      setTimeout(function(){
        const nameDiv = li.querySelector(".pref-name");
        done({found: true, before: before, after: val ? val.value : null,
              locked: nameDiv.hasAttribute("locked"),
              lockIcon: getComputedStyle(nameDiv).backgroundImage,
              disabled: val ? val.hasAttribute("disabled") : null,
              waitedMs: Date.now() - t0});
      }, 600);
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
    ev = {}
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
        page = m.async_script(JS_ABOUTCONFIG_PAGE)
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
        toggled = m.async_script(JS_ABOUTCONFIG_TOGGLE, [name])
        ev["edit"] = toggled
        after = m.script('return Services.prefs.getBoolPref(arguments[0], null);',
                         [name], chrome=True)
    except MarionetteError as e:
        raise HarnessError("the edit probe could not run on a loaded about:config: %s" % e)
    ev["edit"]["prefAfterToggle"] = after
    edit_ok = bool(toggled.get("found")) and after is True

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

# Mozilla's search partner / attribution parameters.  Measured on this build:
# a real query typed into the Fenix toolbar produced
# https://www.google.com/search?client=firefox-b-m&q=... -- client=firefox-b-m
# is exactly the kind of code LW-M4-06 has to remove.
PARTNER_CODE_RE = re.compile(r"[?&](client|pc|channel|form|tag|partner|ref|hspart|hsimp)=([^&]*)", re.I)

# The Fenix address bar.  Compose test tag first, then the older view ids, so
# this keeps working across the toolbar rewrite that is in flight upstream.
URLBAR_IDS = ("ADDRESSBAR_URL_BOX",
              "mozac_browser_toolbar_url_view",
              "org.mozilla.fenix.debug:id/toolbar")

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

def check_search(m, res, adb, apk):
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
    engines, plugins = apk_search_engines(apk)
    has_mojeek = any("mojeek" in p.lower() for p in plugins)
    host = re.sub(r"^https?://", "", url).split("/")[0]
    ok = not codes and has_mojeek
    res.add("check-search", ok,
            ("real query went to %s with no partner/attribution parameter; Mojeek is in the "
             "shipped engine set (%d plugins)" % (host, len(plugins)) if ok else
             "real query URL %s carries %s and Mojeek present=%s (%d shipped searchplugins) "
             "-- owned by LW-M4-06"
             % (url[:160], ["%s=%s" % c for c in codes] or "no partner code", has_mojeek,
                len(plugins))),
            {"url": url, "partner_codes": ["%s=%s" % c for c in codes],
             "mojeek": has_mojeek, "plugins": plugins[:400]})
    return ok

NOT_IMPLEMENTED = {
    "--check-no-suggest": (
        "LW-M4-11. Needs keystroke-level evidence: type into the Fenix toolbar (a Kotlin view, "
        "not a Gecko urlbar, so Marionette cannot reach it) and prove no request leaves before "
        "Enter. Driving it with 'input text' plus a capture window is possible; a version that "
        "only reads browser.search.suggest.enabled would pass on a build that still calls "
        "merino, which is the failure this gate exists to catch."),
    "--check-strings": (
        "LW-M4-12. Needs a traversal of the whole Fenix UI, not a scrape of two screens. A "
        "uiautomator dump of the home screen and settings root would pass today on a build "
        "whose deeper screens still say Firefox, and a green gate that shallow is worse than "
        "no gate."),
    "--check-update-privacy": (
        "LW-M6-06. There is no update-check implementation to test yet; the check has to be "
        "written against the endpoint and the opt-in UI that task builds."),
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
    for f in ("ubo", "search", "no-gms", "no-adjust", "aboutconfig", "no-suggest",
              "strings", "update-privacy"):
        ap.add_argument("--check-" + f, action="store_true")
    args = ap.parse_args(argv)

    for flag, why in NOT_IMPLEMENTED.items():
        if getattr(args, flag[2:].replace("-", "_")):
            print("android-smoke: %s is NOT IMPLEMENTED and is not a pass.\n  %s"
                  % (flag, why), file=sys.stderr)
            return EXIT_UNIMPLEMENTED

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
    pkg = apk_package(apk)
    log("apk=%s" % apk)
    log("package=%s" % pkg)

    static_only = (args.check_no_gms or args.check_no_adjust) and not (
        args.emulator or args.serial or args.pref_dump or args.network_capture
        or args.first_run_capture or args.check_ubo or args.check_search
        or args.check_aboutconfig or args.self_test)
    if args.check_no_gms:
        check_no_gms(apk, res)
    if args.check_no_adjust:
        check_no_adjust(apk, res)
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
    try:
        app.install(apk)
        if not args.keep_state:
            app.wipe()

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
                    {"events": app_rows[:200], "uid_rx": rb1 - rb0, "uid_tx": tb1 - tb0})
            return finish(res, args, work)

        # ---- the origin server and the browsing session -------------------
        ca_b64 = mint_certs(os.path.join(work, "harness"))
        video = base64.b64decode(open(os.path.join(HARNESS, "fixture-video.b64")).read())
        http_port, https_port = free_port(), free_port()
        origin = Origin(os.path.join(work, "harness"), http_port, https_port, video)
        http_url = "http://10.0.2.2:%d/" % http_port
        https_url = "https://10.0.2.2:%d/" % https_port
        log("origin: %s and %s" % (http_url, https_url))

        cap_off = pcap_size(pcap) if pcap else 0
        m = open_session(app, http_url)
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
            _ok, m = check_aboutconfig(m, res, app, apk, http_url)
            return finish(res, args, work)
        if args.check_ubo:
            check_ubo(m, res)
            return finish(res, args, work)
        if args.check_search:
            check_search(m, res, adb, apk)
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
        if emu and not args.keep_emulator:
            emu.stop()
        elif emu:
            log("emulator left running as %s (capture: %s)" % (emu.serial, emu.pcap))

def finish(res, args, work):
    extra = globals().get("_EXTRA_PREFS") or {}
    payload = {"checks": res.rows, "work": work, "injected_prefs": extra,
               "tainted": bool(extra)}
    path = args.json or os.path.join(work, "result.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=1)
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
