#!/usr/bin/env python3
"""Tests for scripts/fdroid-pages.py (LW-M6-03) and site-check's F-Droid rules.

Hermetic: a throwaway RSA key made with openssl signs the index JARs the way
fdroidserver does (MANIFEST.MF -> .SF -> detached PKCS#7), the "APKs" are small
zips, and apksigner is a stub that reports the certificate a test chooses.
No network: assemble runs with --cache/--offline. The real download path, real
fdroidserver output and a real F-Droid client are exercised in
docs/android/evidence/lw-m6-03/.

Run: python3 scripts/tests/test-fdroid-pages.py      (needs python3 + openssl)
"""
import base64
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "fdroid-pages.py"
REL_FP = "6414eb334681cf6e929034b56a062d2b8da090822172f7a3952c85fdd1283bd0"
TAG = "android-157.0-2"


def b64sha(data):
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


class Fixture:
    def __init__(self, tmp):
        self.tmp = pathlib.Path(tmp)
        self.site = self.tmp / "site"
        self.repo = self.site / "fdroid" / "repo"
        self.repo.mkdir(parents=True)
        (self.site / "index.html").write_text("<!doctype html><title>x</title>")
        self.cache = self.tmp / "cache"
        self.cache.mkdir()
        self.key, self.cert = self.make_key("repo")
        self.pin = self.tmp / "repo-fingerprint"
        self.pin.write_text(self.cert_fp(self.cert) + "\n")
        self.apks = {}
        for code, abi in ((2016188480, "armeabi-v7a"), (2016188482, "arm64-v8a"), (2016188486, "x86_64")):
            name = f"org.redoubtbrowser_{code}.apk"
            p = self.cache / name
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("AndroidManifest.xml", f"fake {abi} {code}" + "x" * 1000)
            self.apks[name] = (abi, hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_size)
        self.stub = self.tmp / "apksigner"
        self.stub.write_text(
            "#!/bin/sh\n"
            "printf 'Verifies\\nVerified using v1 scheme (JAR signing): false\\n"
            "Verified using v2 scheme (APK Signature Scheme v2): true\\n"
            "Verified using v3 scheme (APK Signature Scheme v3): true\\n"
            "Number of signers: 1\\n"
            "Signer #1 certificate SHA-256 digest: %s\\n' \"${STUB_FP:-" + REL_FP + "}\"\n")
        self.stub.chmod(0o755)
        self.write_index()

    def make_key(self, name):
        key, cert = self.tmp / f"{name}.key", self.tmp / f"{name}.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key,
                        "-out", cert, "-days", "2", "-subj", f"/CN=throwaway {name}"],
                       check=True, capture_output=True)
        return key, cert

    def cert_fp(self, cert):
        der = subprocess.run(["openssl", "x509", "-in", cert, "-outform", "DER"],
                             check=True, capture_output=True).stdout
        return hashlib.sha256(der).hexdigest()

    def sign_jar(self, jar, member, data, key=None, cert=None):
        key, cert = key or self.key, cert or self.cert
        mf = f"Manifest-Version: 1.0\r\n\r\nName: {member}\r\nSHA-256-Digest: {b64sha(data)}\r\n\r\n".encode()
        crlf2 = b"\r\n\r\n"
        section = b64sha(mf.split(crlf2)[1] + crlf2)
        sf = (f"Signature-Version: 1.0\r\nCreated-By: 1.0 (Android)\r\nSHA-256-Digest-Manifest: {b64sha(mf)}\r\n\r\n"
              f"Name: {member}\r\nSHA-256-Digest: {section}\r\n\r\n").encode()
        sfp = self.tmp / "x.sf"
        sfp.write_bytes(sf)
        sig = subprocess.run(["openssl", "cms", "-sign", "-binary", "-noattr", "-outform", "DER",
                              "-signer", cert, "-inkey", key, "-in", sfp, "-md", "sha256"],
                             check=True, capture_output=True).stdout
        with zipfile.ZipFile(jar, "w") as z:
            z.writestr(member, data)
            z.writestr("META-INF/MANIFEST.MF", mf)
            z.writestr("META-INF/REDOUBT-.SF", sf)
            z.writestr("META-INF/REDOUBT-.RSA", sig)

    def write_index(self, signer=REL_FP, v1_drop=None):
        versions = {}
        for name, (abi, sha, size) in self.apks.items():
            versions[sha] = {"file": {"name": "/" + name, "sha256": sha, "size": size},
                             "manifest": {"versionCode": int(name[19:-4]), "versionName": "157.0-2-default",
                                          "nativecode": [abi], "signer": {"sha256": [signer]}}}
        v2 = json.dumps({"repo": {"address": "https://redoubtbrowser.org/fdroid/repo"},
                         "packages": {"org.redoubtbrowser": {"versions": versions}}}).encode()
        (self.repo / "index-v2.json").write_bytes(v2)
        entry = json.dumps({"timestamp": 1, "version": 30000,
                            "index": {"name": "/index-v2.json", "sha256": hashlib.sha256(v2).hexdigest(),
                                      "size": len(v2), "numPackages": 1}}).encode()
        (self.repo / "entry.json").write_bytes(entry)
        self.sign_jar(self.repo / "entry.jar", "entry.json", entry)
        v1 = json.dumps({"packages": {"org.redoubtbrowser": [
            {"apkName": n, "hash": s, "hashType": "sha256"} for n, (_, s, _) in self.apks.items() if n != v1_drop]}})
        (self.repo / "index-v1.json").write_text(v1)
        self.sign_jar(self.repo / "index-v1.jar", "index-v1.json", v1.encode())
        (self.site / "fdroid" / "sources.json").write_text(json.dumps({"apks": {
            n: {"url": f"https://github.com/CPlusPlus17/Redoubt/releases/download/{TAG}/fenix-{abi}-release.apk",
                "tag": TAG} for n, (abi, _, _) in self.apks.items()}}))

    def run(self, *args, env=None):
        return subprocess.run([sys.executable, TOOL, *args, "--site", self.site,
                               "--repo-fingerprint-file", self.pin],
                              capture_output=True, text=True,
                              env={**os.environ, "APKSIGNER": str(self.stub), **(env or {})})

    def assemble(self, *extra, env=None):
        out = self.tmp / "out"
        shutil.rmtree(out, ignore_errors=True)
        return self.run("assemble", "--out", out, "--cache", self.cache, "--offline", *extra, env=env)


class FdroidPagesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.f = Fixture(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def assertRefused(self, r, text):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(text, r.stderr)

    def test_good_repository_checks_and_assembles(self):
        r = self.f.run("check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.f.assemble()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for name, (_, sha, _) in self.f.apks.items():
            got = hashlib.sha256((self.f.tmp / "out/fdroid/repo" / name).read_bytes()).hexdigest()
            self.assertEqual(got, sha)
        self.assertTrue((self.f.tmp / "out/index.html").is_file())

    def test_no_repository_is_a_plain_copy(self):
        shutil.rmtree(self.f.site / "fdroid")
        r = self.f.assemble()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no F-Droid repository committed", r.stdout)

    def test_index_signed_by_another_key_is_refused(self):
        key, cert = self.f.make_key("other")
        entry = (self.f.repo / "entry.json").read_bytes()
        self.f.sign_jar(self.f.repo / "entry.jar", "entry.json", entry, key, cert)
        self.assertRefused(self.f.run("check"), "the pinned repository fingerprint is")

    def test_index_v2_edited_after_signing_is_refused(self):
        p = self.f.repo / "index-v2.json"
        p.write_bytes(p.read_bytes().replace(b"157.0-2-default", b"157.0-9-default"))
        self.assertRefused(self.f.run("check"), "sha256/size differ from the signed entry.json")

    def test_entry_json_member_edited_inside_jar_is_refused(self):
        jar = self.f.repo / "entry.jar"
        with zipfile.ZipFile(jar) as z:
            items = {n: z.read(n) for n in z.namelist()}
        items["entry.json"] = items["entry.json"].replace(b'"timestamp": 1', b'"timestamp": 2')
        with zipfile.ZipFile(jar, "w") as z:
            for n, d in items.items():
                z.writestr(n, d)
        self.assertRefused(self.f.run("check"), "MANIFEST.MF does not carry the SHA-256 digest of entry.json")

    def test_apk_not_signed_by_release_key_in_index_is_refused(self):
        self.f.write_index(signer="00" * 32)
        self.assertRefused(self.f.run("check"), "not the release key")

    def test_v1_and_v2_disagree_is_refused(self):
        self.f.write_index(v1_drop="org.redoubtbrowser_2016188486.apk")
        self.assertRefused(self.f.run("check"), "do not list the same APKs")

    def test_tampered_apk_fails_the_deploy(self):
        name = "org.redoubtbrowser_2016188486.apk"
        p = self.f.cache / name
        data = bytearray(p.read_bytes())
        data[100] ^= 0xFF
        p.write_bytes(bytes(data))
        self.assertRefused(self.f.assemble(), f"{name}: not in the cache with sha256")

    def test_missing_apk_fails_the_deploy(self):
        (self.f.cache / "org.redoubtbrowser_2016188480.apk").unlink()
        self.assertRefused(self.f.assemble(), "--offline forbids a download")

    def test_over_budget_fails_before_anything_is_fetched(self):
        r = self.f.assemble("--max-bytes", "3000")
        self.assertRefused(r, "over the 3000-byte limit")
        self.assertFalse((self.f.tmp / "out").exists())

    def test_wrong_release_certificate_fails_the_deploy(self):
        self.assertRefused(self.f.assemble(env={"STUB_FP": "ab" * 32}), "release certificate")

    def test_committed_apk_is_refused(self):
        shutil.copy(self.f.cache / "org.redoubtbrowser_2016188480.apk", self.f.repo)
        self.assertRefused(self.f.run("check"), "APKs are committed under site/")

    def test_source_outside_the_release_is_refused(self):
        p = self.f.site / "fdroid" / "sources.json"
        s = json.loads(p.read_text())
        s["apks"]["org.redoubtbrowser_2016188480.apk"]["url"] = "https://example.org/x.apk"
        p.write_text(json.dumps(s))
        self.assertRefused(self.f.run("check"), "is not a Redoubt release asset")

    def test_missing_pin_is_refused(self):
        self.f.pin.unlink()
        self.assertRefused(self.f.run("check"), "does not pin the repository fingerprint")


if __name__ == "__main__":
    unittest.main(verbosity=2)
