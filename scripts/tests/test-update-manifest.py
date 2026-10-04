#!/usr/bin/env python3
"""Tests for the update-check publishing side, with THROWAWAY keys only.

scripts/update-manifest.py (generate / verify / fetch) and
scripts/sign-update-manifest.sh (the owner's signer) are driven end to end:
generate -> sign -> verify, plus every way the chain must refuse. Keys are
made here with openssl in a temporary directory and deleted afterwards; no
real key is read. Needs python3 and openssl; `cryptography`, if installed,
adds an independent signature check.

The app-side counterpart is scripts/tests/test-update-check-jvm.sh, which runs
the patch's own Kotlin against the same tools.
"""

import http.server
import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
import importlib.util  # noqa: E402  (the script's name has a dash)

_spec = importlib.util.spec_from_file_location("update_manifest", ROOT / "scripts" / "update-manifest.py")
um = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(um)

FIX = ROOT / "scripts" / "tests" / "fixtures" / "update-manifest"
BETA5 = FIX / "beta5-output-metadata.json"
BETA6 = FIX / "beta6-output-metadata.json"
SIGNER = ROOT / "scripts" / "sign-update-manifest.sh"
TOOL = ROOT / "scripts" / "update-manifest.py"
BETA5_CODES = (2016188256, 2016188258, 2016188262, 2016188263)
BETA6_CODES = (2016188448, 2016188450, 2016188454, 2016188455)
PASSPHRASE = "disposable-test-passphrase"


def run(*cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def keypair(tmp, name, curve="P-256", passphrase=None):
    key = tmp / (name + ".pem")
    cmd = ["openssl", "genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:" + curve,
           "-pkeyopt", "ec_param_enc:named_curve", "-out", key]
    if passphrase:
        cmd += ["-aes-256-cbc", "-pass", "pass:" + passphrase]
    subprocess.run([str(c) for c in cmd], check=True, capture_output=True)
    passin = ["-passin", "pass:" + passphrase] if passphrase else []
    der = subprocess.run(["openssl", "pkey", "-in", str(key)] + passin + ["-pubout", "-outform", "DER"],
                         check=True, capture_output=True).stdout
    pub = tmp / (name + ".pub")
    import base64
    pub.write_text(base64.b64encode(der).decode() + "\n")
    return key, pub


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="redoubt-update-test-")
        self.tmp = Path(self._tmp.name)
        self.key, self.pub = keypair(self.tmp, "throwaway")

    def tearDown(self):
        self._tmp.cleanup()

    def generate(self, name="latest.json", metadata=BETA6, tag="android-157.0-1-beta.6", *extra):
        out = self.tmp / name
        r = run(sys.executable, TOOL, "generate", "--metadata", metadata, "--tag", tag,
                "--published", "2026-10-05T00:00:00Z", "--out", out, *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return out

    def sign(self, doc, key=None, pin=None):
        return run(SIGNER, key or self.key, doc, pin or self.pub)

    def verdict(self, doc, version="157.0-1-default", code=0, pub=None):
        pub_der = um.decode_pubkey((pub or self.pub).read_text())
        sig = Path(str(doc) + ".sig")
        return um.app_verdict(doc.read_bytes(), sig.read_bytes() if sig.exists() else b"", pub_der, version, code)[0]


class Generate(Base):
    def test_document_shape(self):
        doc = json.loads(self.generate().read_text())
        self.assertEqual(doc, {
            "latest_version": "157.0-1-beta.6",
            "version_code": min(BETA6_CODES),
            "download_url": "https://github.com/CPlusPlus17/Redoubt/releases/tag/android-157.0-1-beta.6",
            "release_notes_url": "https://github.com/CPlusPlus17/Redoubt/releases/tag/android-157.0-1-beta.6",
            "published_at": "2026-10-05T00:00:00Z",
        })

    def test_deterministic_ascii_with_trailing_newline(self):
        a = self.generate("a.json").read_bytes()
        b = self.generate("b.json").read_bytes()
        self.assertEqual(a, b)
        self.assertTrue(a.endswith(b"}\n"))
        a.decode("ascii")

    def test_refusals(self):
        bad_meta = self.tmp / "bad.json"
        meta = json.loads(BETA6.read_text())
        cases = []
        cases.append((BETA6, "android-158.0-1-beta.6", "versionName"))          # tag vs APKs
        cases.append((BETA6, "157.0-1-beta.6", "android-<firefox>"))             # tag shape
        m = json.loads(json.dumps(meta)); m["elements"] = m["elements"][1:]
        cases.append((m, "android-157.0-1-beta.6", "expected exactly"))          # missing ABI
        m = json.loads(json.dumps(meta)); m["elements"][0]["versionName"] = "157.0-2-default"
        cases.append((m, "android-157.0-1-beta.6", "disagree"))
        m = json.loads(json.dumps(meta)); m["variantName"] = "debug"
        cases.append((m, "android-157.0-1-beta.6", "only release"))
        m = json.loads(json.dumps(meta)); m["applicationId"] = "org.mozilla.fenix"
        cases.append((m, "android-157.0-1-beta.6", "applicationId"))
        for metadata, tag, message in cases:
            if isinstance(metadata, dict):
                bad_meta.write_text(json.dumps(metadata))
                metadata = bad_meta
            r = run(sys.executable, TOOL, "generate", "--metadata", metadata, "--tag", tag)
            self.assertEqual(r.returncode, 2, (tag, message, r.stdout))
            self.assertIn(message, r.stderr)
        r = run(sys.executable, TOOL, "generate", "--metadata", BETA6, "--tag", "android-157.0-1-beta.6",
                "--download-url", "http://example.org/x.apk")
        self.assertEqual(r.returncode, 2)
        self.assertIn("https", r.stderr)

    def test_will_not_orphan_a_signature(self):
        doc = self.generate()
        self.assertEqual(self.sign(doc).returncode, 0)
        r = run(sys.executable, TOOL, "generate", "--metadata", BETA6, "--tag", "android-157.0-1-beta.6",
                "--out", doc, "--force")
        self.assertEqual(r.returncode, 2)
        self.assertIn("move it aside", r.stderr)


class SignAndVerify(Base):
    def test_round_trip_and_the_app_decision(self):
        doc = self.generate()
        r = self.sign(doc)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Verified OK", r.stdout)
        sig = Path(str(doc) + ".sig").read_text()
        self.assertEqual(sig.count("\n"), 1)
        for code in BETA5_CODES:
            self.assertEqual(self.verdict(doc, code=code), "update")
        for code in BETA6_CODES:
            self.assertEqual(self.verdict(doc, code=code), "uptodate")
        # CLI, including the cross-check against the release's own metadata.
        r = run(sys.executable, TOOL, "verify", doc, "--pubkey", "@" + str(self.pub), "--metadata", BETA6)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run(sys.executable, TOOL, "verify", doc, "--pubkey", "@" + str(self.pub), "--metadata", BETA5)
        self.assertEqual(r.returncode, 1)
        self.assertIn("MISMATCH", r.stdout)

    def test_independent_verifier(self):
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec
        except ImportError:
            self.skipTest("python cryptography not installed")
        import base64
        doc = self.generate()
        self.assertEqual(self.sign(doc).returncode, 0)
        key = serialization.load_der_public_key(base64.b64decode(self.pub.read_text()))
        sig = base64.b64decode(Path(str(doc) + ".sig").read_text().strip())
        key.verify(sig, doc.read_bytes(), ec.ECDSA(hashes.SHA256()))  # raises on failure

    def test_tampering_is_no_result(self):
        doc = self.generate()
        self.assertEqual(self.sign(doc).returncode, 0)
        sig = Path(str(doc) + ".sig").read_bytes()
        original = doc.read_bytes()
        for mutated in (original.replace(b"CPlusPlus17", b"CPlusPlus18"),
                        original.replace(b"2016188448", b"2016188449"),
                        original + b" ",
                        original[:-1]):
            doc.write_bytes(mutated)
            self.assertEqual(self.verdict(doc, code=BETA5_CODES[0]), "noresult")
        doc.write_bytes(original)
        sigpath = Path(str(doc) + ".sig")
        for bad in (sig[:20] + b"\n", b"", b"not*base64\n", b"QUJD\n"):
            sigpath.write_bytes(bad)
            self.assertEqual(self.verdict(doc, code=BETA5_CODES[0]), "noresult")
        # Surrounding whitespace is trimmed by the app, so it must not matter.
        sigpath.write_bytes(b"  " + sig.strip() + b"\r\n\n")
        self.assertEqual(self.verdict(doc, code=BETA5_CODES[0]), "update")

    def test_other_key_is_no_result(self):
        doc = self.generate()
        self.assertEqual(self.sign(doc).returncode, 0)
        _, other_pub = keypair(self.tmp, "other")
        self.assertEqual(self.verdict(doc, code=BETA5_CODES[0], pub=other_pub), "noresult")

    def test_signer_refuses_a_key_that_is_not_the_pinned_one(self):
        doc = self.generate()
        other, _ = keypair(self.tmp, "other")
        r = self.sign(doc, key=other)
        self.assertEqual(r.returncode, 2)
        self.assertIn("does NOT verify", r.stderr)
        self.assertFalse(Path(str(doc) + ".sig").exists())

    def test_signer_refusals(self):
        doc = self.generate()
        # Not P-256.
        _, p384 = keypair(self.tmp, "p384", curve="P-384")
        r = self.sign(doc, pin=p384)
        self.assertEqual(r.returncode, 2)
        self.assertIn("P-256", r.stderr)
        # Missing pinned key.
        r = self.sign(doc, pin=self.tmp / "absent.pub")
        self.assertEqual(r.returncode, 2)
        # Oversized and non-document inputs.
        big = self.tmp / "big.json"
        big.write_text('{"latest_version": "1", "download_url": "https://x/", "pad": "%s"}' % ("x" * 70000))
        self.assertEqual(self.sign(big).returncode, 2)
        junk = self.tmp / "junk.json"
        junk.write_text("{}")
        self.assertEqual(self.sign(junk).returncode, 2)
        # Never overwrites an existing signature.
        self.assertEqual(self.sign(doc).returncode, 0)
        r = self.sign(doc)
        self.assertEqual(r.returncode, 2)
        self.assertIn("already exists", r.stderr)

    def test_passphrase_protected_key_through_a_terminal(self):
        """The owner's key is encrypted; openssl must be able to prompt."""
        key, pub = keypair(self.tmp, "encrypted", passphrase=PASSPHRASE)
        doc = self.generate()
        pid, fd = pty.fork()
        if pid == 0:
            os.execv(str(SIGNER), [str(SIGNER), str(key), str(doc), str(pub)])
        output, answered, deadline = b"", False, time.time() + 60
        while time.time() < deadline:
            ready, _, _ = select.select([fd], [], [], 1)
            if not ready:
                continue
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            output += chunk
            if not answered and b"pass phrase" in output.lower().replace(b"passphrase", b"pass phrase"):
                os.write(fd, (PASSPHRASE + "\n").encode())
                answered = True
        _, status = os.waitpid(pid, 0)
        self.assertTrue(answered, output.decode(errors="replace"))
        self.assertEqual(os.waitstatus_to_exitcode(status), 0, output.decode(errors="replace"))
        self.assertEqual(self.verdict(doc, code=BETA5_CODES[0], pub=pub), "update")


class Mirror(unittest.TestCase):
    """The Python mirror must agree with UpdateCheckerTest's cases."""

    def test_is_newer(self):
        t, f = self.assertTrue, self.assertFalse
        t(um.is_newer("157.0-2", "157.0-1"))
        t(um.is_newer("154.0", "153.9.1"))
        t(um.is_newer("153.1.0esr-1", "153.0esr-3"))
        f(um.is_newer("157.0-1", "157.0-1"))
        f(um.is_newer("157.0-1", "157.0-2"))
        f(um.is_newer("latest", "157.0-1"))
        t(um.is_newer("157.0.1-1", "157.0-2"))
        f(um.is_newer("157.0-2", "157.0.1-1"))
        t(um.is_newer("158.0-1", "157.0.2-3"))
        t(um.is_newer("157.0-1", "153.4.0esr-1"))
        f(um.is_newer("153.4.0esr-2", "157.0-1"))

    def test_offers(self):
        doc = {"latest_version": "157.0-1-beta.6", "version_code": 2016188448}
        self.assertTrue(um.offers(doc, "157.0-1-default", 2016188263))
        self.assertFalse(um.offers(doc, "157.0-1-default", 2016188448))
        self.assertFalse(um.offers(doc, "1-default", 2016190000))
        self.assertTrue(um.offers(doc, "153.4.0esr-1-default", 0))
        self.assertTrue(um.offers(dict(doc, version_code=0), "157.0-1", 2016188263))

    def test_parse(self):
        ok = b'{"latest_version": " 157.0-2 ", "download_url": "https://x/", "version_code": -5}'
        self.assertEqual(um.parse(ok)["latest_version"], "157.0-2")
        self.assertEqual(um.parse(ok)["version_code"], 0)
        self.assertIsNone(um.parse(b'{"latest_version": "1", "download_url": "http://x/"}'))
        self.assertIsNone(um.parse(b'{"latest_version": "", "download_url": "https://x/"}'))
        self.assertIsNone(um.parse(b'[1]'))
        self.assertIsNone(um.parse(b'\xff'))


class Fetch(Base):
    """`fetch` refuses redirects and non-2xx, as the app does."""

    def serve(self, routes):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                status, body, headers = routes.get(self.path, (404, b"", {}))
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return "http://127.0.0.1:%d" % srv.server_port

    def test_fetch(self):
        doc = self.generate()
        self.assertEqual(self.sign(doc).returncode, 0)
        body, sig = doc.read_bytes(), Path(str(doc) + ".sig").read_bytes()
        base = self.serve({
            "/update/android/latest.json": (200, body, {}),
            "/update/android/latest.json.sig": (200, sig, {}),
            "/moved/latest.json": (301, b"", {"Location": "/update/android/latest.json"}),
            "/moved/latest.json.sig": (301, b"", {"Location": "/update/android/latest.json.sig"}),
        })
        r = run(sys.executable, TOOL, "fetch", "--url", base + "/update/android/latest.json",
                "--pubkey", "@" + str(self.pub), "--expect-tag", "android-157.0-1-beta.6")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run(sys.executable, TOOL, "fetch", "--url", base + "/update/android/latest.json",
                "--pubkey", "@" + str(self.pub), "--expect-tag", "android-157.0-1-beta.7")
        self.assertEqual(r.returncode, 1)
        r = run(sys.executable, TOOL, "fetch", "--url", base + "/moved/latest.json", "--pubkey", "@" + str(self.pub))
        self.assertEqual(r.returncode, 2)
        self.assertIn("301", r.stderr)


if __name__ == "__main__":
    for tool in ("openssl",):
        if not shutil.which(tool):
            sys.exit("%s is required" % tool)
    unittest.main()
