#!/usr/bin/env python3
"""Exercise offline signing with real apksigner and disposable, generated keys.

Needs java, keytool, and a Redoubt APK whose binary AndroidManifest.xml can be copied.
The reduced fixture is sufficient for APK signature verification, not installation.
No release keystore is opened. Override inputs with --apk and --apksigner.
"""

import argparse
import hashlib
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "librewolf-android-apk-153.0esr-1-unsigned/apk"
ABIS = ("arm64-v8a", "armeabi-v7a", "universal", "x86_64")
TOOLS = ("apksigner.jar", "sign.sh", "android-verify-signature.sh", "SIGNING.md")
PASSWORD = "disposable-test-password"
INPUTS = None


def invoke(command, *, env=None, cwd=None, password=None):
    """Feed interactive keystore prompts individually, as the offline user does."""
    if password is None:
        return subprocess.run(command, env=env, cwd=cwd, input="", text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=90)
    master, slave = pty.openpty()
    process = subprocess.Popen(command, env=env, cwd=cwd, stdin=slave,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    os.close(slave)
    output = b""
    answered = 0
    deadline = time.monotonic() + 90
    try:
        while True:
            if time.monotonic() > deadline:
                process.kill()
                raise TimeoutError(output.decode(errors="replace"))
            if select.select([process.stdout], [], [], 0.2)[0]:
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    break
                output += chunk
                prompts = output.count(b"Keystore password for signer #1:")
                while answered < prompts:
                    os.write(master, (password + "\n").encode())
                    answered += 1
        code = process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        os.close(master)
    return subprocess.CompletedProcess(command, code, output.decode(errors="replace"))


def require_success(result):
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {result.args}\n{result.stdout}")
    return result.stdout


def checksum_manifest(folder, names, manifest):
    lines = [f"{hashlib.sha256((folder / name).read_bytes()).hexdigest()}  {name}\n"
             for name in names]
    (folder / manifest).write_text("".join(lines))


class SigningIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(prefix="lw-m6-08-signing-")
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.root = Path(cls.scratch.name)
        cls.java = shutil.which("java")
        cls.keytool = shutil.which("keytool")
        if not cls.java or not cls.keytool:
            raise RuntimeError("java and keytool are required; missing tools are not a pass")
        cls.jar = cls.root / "signer tools with spaces" / "apksigner.jar"
        cls.jar.parent.mkdir()
        shutil.copy2(INPUTS.apksigner, cls.jar)
        cls.env = dict(os.environ, APKSIGNER=str(cls.jar))
        cls.verifier = ROOT / "scripts/android-verify-signature.sh"
        cls.tiny = cls.root / "reduced unsigned.apk"
        with zipfile.ZipFile(INPUTS.apk) as source, zipfile.ZipFile(cls.tiny, "w") as out:
            out.writestr("AndroidManifest.xml", source.read("AndroidManifest.xml"))
            out.writestr("signature-fixture.txt", "Temporary signing fixture, not installable.\n")
        cls.keys = []
        cls.docs = []
        for index in range(2):
            key = cls.root / f"throwaway key {index}.p12"
            require_success(invoke([
                cls.keytool, "-genkeypair", "-keystore", str(key), "-storetype", "PKCS12",
                "-storepass", PASSWORD, "-keyalg", "RSA", "-keysize", "2048",
                "-validity", "1", "-alias", "test", "-dname", "CN=Disposable signing integration test",
            ]))
            certificate = cls.root / f"public cert {index}.der"
            require_success(invoke([
                cls.keytool, "-exportcert", "-keystore", str(key), "-storetype", "PKCS12",
                "-storepass", PASSWORD, "-alias", "test", "-file", str(certificate),
            ]))
            digest = hashlib.sha256(certificate.read_bytes()).hexdigest().upper()
            fingerprint = ":".join(digest[i:i + 2] for i in range(0, len(digest), 2))
            doc = cls.root / f"public SIGNING {index}.md"
            doc.write_text(f"SHA-256 fingerprint\n    {fingerprint}\n\n")
            cls.keys.append(key)
            cls.docs.append(doc)
        cls.signed = {}
        for label, v1, v3 in [("correct", False, True), ("v2-only", False, False),
                              ("with-v1", True, True)]:
            apk = cls.root / f"{label}.apk"
            require_success(invoke([
                cls.java, "-jar", str(cls.jar), "sign", "--ks", str(cls.keys[0]),
                "--ks-type", "PKCS12", "--ks-pass", f"pass:{PASSWORD}",
                "--v1-signing-enabled", str(v1).lower(), "--v2-signing-enabled", "true",
                "--v3-signing-enabled", str(v3).lower(), "--v4-signing-enabled", "false",
                "--out", str(apk), str(cls.tiny),
            ]))
            cls.signed[label] = apk
        print(f"Fixture: {INPUTS.apk} -> {cls.tiny.stat().st_size} byte reduced APK", flush=True)
        print("Cryptography: real apksigner; two generated temporary keys; no release key access", flush=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="case-", dir=self.root))
        self.bundle = self.work / "bundle with spaces"
        self.bundle.mkdir()
        self.caller = self.work / "outside bundle"
        self.caller.mkdir()

    def verify(self, *apks, doc=None, env=None, extra=()):
        return invoke([str(self.verifier), *extra, "--signing-doc", str(doc or self.docs[0]),
                       *(str(apk) for apk in apks)], env=env or self.env, cwd=self.caller)

    def assert_result(self, result, status, text):
        self.assertEqual(result.returncode, status, result.stdout)
        self.assertIn(text, result.stdout)

    def prepare_bundle(self, doc=None):
        shutil.copy2(self.jar, self.bundle / "apksigner.jar")
        shutil.copy2(self.verifier, self.bundle / "android-verify-signature.sh")
        shutil.copy2(ROOT / "docs/android/evidence/lw-m6-01/sign.sh", self.bundle / "sign.sh")
        shutil.copy2(doc or self.docs[0], self.bundle / "SIGNING.md")
        for abi in ABIS:
            shutil.copy2(self.tiny, self.bundle / f"fenix-{abi}-release-unsigned.apk")
        checksum_manifest(self.bundle, [f"fenix-{abi}-release-unsigned.apk" for abi in ABIS], "SHA256SUMS")
        checksum_manifest(self.bundle, TOOLS, "SHA256SUMS.tools")

    def sign_bundle(self, *, env=None):
        return invoke([str(self.bundle / "sign.sh"), os.path.relpath(self.keys[0], self.caller)],
                      cwd=self.caller, env=env, password=PASSWORD)

    def sign_fixture(self, source, output):
        require_success(invoke([
            self.java, "-jar", str(self.jar), "sign", "--ks", str(self.keys[0]),
            "--ks-type", "PKCS12", "--ks-pass", f"pass:{PASSWORD}",
            "--v1-signing-enabled", "false", "--v2-signing-enabled", "true",
            "--v3-signing-enabled", "true", "--v4-signing-enabled", "false",
            "--out", str(output), str(source),
        ]))

    def intake_copy(self):
        signed = self.work / "fenix-arm64-v8a-release.apk"
        shutil.copy2(self.signed["correct"], signed)
        return signed

    def assert_no_outputs(self):
        self.assertEqual(list(self.bundle.glob("fenix-*-release.apk")), [])
        self.assertFalse((self.bundle / "SHA256SUMS.signed").exists())
        self.assertEqual(list(self.bundle.glob(".redoubt-sign.*")), [])

    def test_complete_handoff_outside_bundle_with_spaces(self):
        self.prepare_bundle()
        original = {abi: (self.bundle / f"fenix-{abi}-release-unsigned.apk").read_bytes() for abi in ABIS}
        # Python is an optional intake dependency, never an offline-signing one.
        guard = self.work / "no python for offline signing"
        guard.mkdir()
        python = guard / "python3"
        python.write_text("#!/bin/sh\necho 'offline signing invoked Python' >&2\nexit 37\n")
        python.chmod(0o755)
        env = dict(os.environ, PATH=str(guard) + os.pathsep + os.environ["PATH"])
        self.assert_result(self.sign_bundle(env=env), 0, "Verified all four APKs")
        outputs = sorted(self.bundle.glob("fenix-*-release.apk"))
        self.assertEqual(len(outputs), 4)
        self.assert_result(self.verify(*outputs, extra=("--unsigned-dir", str(self.bundle))),
                           0, "ZIP payload matches candidate")
        manifest = (self.bundle / "SHA256SUMS.signed").read_text().splitlines()
        self.assertEqual(len(manifest), 4)
        for line in manifest:
            digest, name = line.split()
            self.assertEqual(digest, hashlib.sha256((self.bundle / name).read_bytes()).hexdigest())
        for abi in ABIS:
            self.assertEqual(original[abi], (self.bundle / f"fenix-{abi}-release-unsigned.apk").read_bytes())
        self.assertEqual(list(self.bundle.glob("*.idsig")), [])

    def test_correct_signature(self):
        self.assert_result(self.verify(self.signed["correct"]), 0, "fingerprint matches")

    def test_intake_rejects_correctly_signed_changed_payload_and_manifest(self):
        self.prepare_bundle()
        for changed_entry in ("signature-fixture.txt", "AndroidManifest.xml"):
            with self.subTest(changed_entry=changed_entry):
                changed = self.work / "modified unsigned.apk"
                with zipfile.ZipFile(self.tiny) as source, zipfile.ZipFile(changed, "w") as target:
                    for entry in source.infolist():
                        contents = source.read(entry)
                        if entry.filename == changed_entry:
                            if changed_entry == "AndroidManifest.xml":
                                before = "org.redoubtbrowser".encode("utf-16le")
                                after = "org.redoubtbrowzer".encode("utf-16le")
                                self.assertIn(before, contents, "fixture needs a Redoubt manifest")
                                contents = contents.replace(before, after)
                            else:
                                contents = contents.replace(b"Temporary", b"temporary")
                        target.writestr(entry, contents)
                signed = self.work / "fenix-arm64-v8a-release.apk"
                self.sign_fixture(changed, signed)
                self.assert_result(self.verify(signed), 0, "PASS")
                self.assert_result(self.verify(signed, extra=("--unsigned-dir", str(self.bundle))),
                                   1, f"ZIP payload differs: {changed_entry}")

    def test_intake_missing_counterpart(self):
        self.prepare_bundle()
        signed = self.intake_copy()
        (self.bundle / "fenix-arm64-v8a-release-unsigned.apk").unlink()
        self.assert_result(self.verify(signed, extra=("--unsigned-dir", str(self.bundle))),
                           2, "candidate APK missing")

    def test_intake_unknown_signed_filename(self):
        self.prepare_bundle()
        self.assert_result(self.verify(self.signed["correct"], extra=("--unsigned-dir", str(self.bundle))),
                           2, "no candidate counterpart")

    def test_intake_duplicate_zip_names(self):
        self.prepare_bundle()
        signed = self.intake_copy()
        candidate = self.bundle / "fenix-arm64-v8a-release-unsigned.apk"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(candidate, "a") as archive:
                contents = archive.read("signature-fixture.txt")
                archive.writestr("signature-fixture.txt", contents)
        checksum_manifest(self.bundle, [f"fenix-{abi}-release-unsigned.apk" for abi in ABIS], "SHA256SUMS")
        self.assert_result(self.verify(signed, extra=("--unsigned-dir", str(self.bundle))),
                           1, "duplicate ZIP entry names")

    def test_intake_failed_candidate_checksum(self):
        self.prepare_bundle()
        signed = self.intake_copy()
        with (self.bundle / "fenix-arm64-v8a-release-unsigned.apk").open("ab") as file:
            file.write(b"changed after checksumming")
        self.assert_result(self.verify(signed, extra=("--unsigned-dir", str(self.bundle))),
                           1, "candidate checksum mismatch")

    def test_intake_incomplete_candidate_manifest(self):
        self.prepare_bundle()
        signed = self.intake_copy()
        manifest = self.bundle / "SHA256SUMS"
        manifest.write_text("".join(manifest.read_text().splitlines(keepends=True)[:-1]))
        self.assert_result(self.verify(signed, extra=("--unsigned-dir", str(self.bundle))),
                           1, "must list all four candidate APKs")

    def test_intake_empty_directory_cannot_disable_binding(self):
        self.assert_result(self.verify(self.signed["correct"], extra=("--unsigned-dir", "")),
                           2, "needs a nonempty path")

    def test_wrong_fingerprint(self):
        self.assert_result(self.verify(self.signed["correct"], doc=self.docs[1]), 1, "WRONG KEY")

    def test_v2_only(self):
        self.assert_result(self.verify(self.signed["v2-only"]), 1, "NO v3 signature")

    def test_unexpected_v1(self):
        self.assert_result(self.verify(self.signed["with-v1"]), 1, "v1 signature present")

    def test_corrupt_apk(self):
        corrupt = self.work / "corrupt.apk"
        data = bytearray(self.signed["correct"].read_bytes())
        offset = data.index(b"Temporary signing fixture")
        data[offset] ^= 1
        corrupt.write_bytes(data)
        self.assert_result(self.verify(corrupt), 1, "apksigner could not verify")

    def test_missing_apk_and_mixed_status(self):
        self.assert_result(self.verify(self.work / "missing.apk"), 2, "no such file")
        self.assert_result(self.verify(self.work / "missing.apk", self.signed["v2-only"]), 2, "NO v3")

    def test_missing_signing_document(self):
        self.assert_result(self.verify(self.signed["correct"], doc=self.work / "missing.md"), 2, "is missing")

    def test_executable_signer_path_with_spaces(self):
        wrapper = self.work / "apksigner executable with spaces"
        wrapper.write_text(f"#!/bin/sh\nexec {shlex.quote(self.java)} -jar {shlex.quote(str(self.jar))} \"$@\"\n")
        wrapper.chmod(0o755)
        self.assert_result(self.verify(self.signed["correct"], env=dict(self.env, APKSIGNER=str(wrapper))), 0, "PASS")

    def test_selftest_requires_real_positive_and_wrong_key_results(self):
        result = self.verify(self.tiny, extra=("--self-test",))
        self.assert_result(result, 0, "correct key, v2 + v3, no v1 accepted")
        self.assertIn("correctly signed but wrong key is still rejected", result.stdout)

    def test_handoff_wrong_key_produces_no_final_outputs(self):
        self.prepare_bundle(doc=self.docs[1])
        self.assert_result(self.sign_bundle(), 1, "WRONG KEY")
        self.assert_no_outputs()

    def test_missing_manifests(self):
        self.prepare_bundle()
        for manifest in ("SHA256SUMS", "SHA256SUMS.tools"):
            with self.subTest(manifest=manifest):
                contents = (self.bundle / manifest).read_bytes()
                (self.bundle / manifest).unlink()
                self.assert_result(self.sign_bundle(), 2, f"{manifest} is missing")
                self.assert_no_outputs()
                (self.bundle / manifest).write_bytes(contents)

    def test_missing_apk_from_bundle(self):
        self.prepare_bundle()
        (self.bundle / "fenix-arm64-v8a-release-unsigned.apk").unlink()
        self.assert_result(self.sign_bundle(), 2, "missing unsigned APK")
        self.assert_no_outputs()

    def test_apk_without_android_manifest_cannot_be_signed(self):
        self.prepare_bundle()
        apk = self.bundle / "fenix-arm64-v8a-release-unsigned.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr("fixture.txt", "No AndroidManifest.xml")
        checksum_manifest(self.bundle, [f"fenix-{abi}-release-unsigned.apk" for abi in ABIS], "SHA256SUMS")
        result = self.sign_bundle()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("AndroidManifest.xml", result.stdout)
        self.assert_no_outputs()

    def test_missing_tool_from_bundle(self):
        self.prepare_bundle()
        (self.bundle / "android-verify-signature.sh").unlink()
        self.assert_result(self.sign_bundle(), 2, "is not next to this script")
        self.assert_no_outputs()

    def test_changed_apk_fails_checksum(self):
        self.prepare_bundle()
        with (self.bundle / "fenix-arm64-v8a-release-unsigned.apk").open("ab") as file:
            file.write(b"modified after checksum")
        result = self.sign_bundle()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("FAILED", result.stdout)
        self.assert_no_outputs()

    def test_manifest_filename_is_literal(self):
        self.prepare_bundle()
        manifest = self.bundle / "SHA256SUMS"
        manifest.write_text(manifest.read_text().replace("unsigned.apk", "unsignedXapk", 1))
        self.assert_result(self.sign_bundle(), 2, "has no unique checksum")
        self.assert_no_outputs()

    def test_duplicate_tool_cannot_replace_omitted_tool(self):
        self.prepare_bundle()
        manifest = self.bundle / "SHA256SUMS.tools"
        lines = manifest.read_text().splitlines(keepends=True)
        manifest.write_text("".join([lines[0], lines[1], lines[1], lines[3]]))
        self.assert_result(self.sign_bundle(), 2, "has no unique checksum")
        self.assert_no_outputs()

    def test_existing_output_not_overwritten(self):
        self.prepare_bundle()
        prior = self.bundle / "fenix-arm64-v8a-release.apk"
        prior.write_bytes(b"prior signed output")
        self.assert_result(self.sign_bundle(), 2, "already exists")
        self.assertEqual(prior.read_bytes(), b"prior signed output")

    def test_signing_tool_failure_status_propagates(self):
        self.prepare_bundle()
        path = self.work / "failing java on PATH"
        path.mkdir()
        java = path / "java"
        java.write_text("#!/bin/sh\necho 'injected signing tool failure' >&2\nexit 37\n")
        java.chmod(0o755)
        env = dict(os.environ, PATH=str(path) + os.pathsep + os.environ["PATH"])
        self.assert_result(self.sign_bundle(env=env), 37, "injected signing tool failure")
        self.assert_no_outputs()

    def test_late_signing_failure_keeps_complete_set_unpublished(self):
        self.prepare_bundle()
        path = self.work / "java wrapper"
        path.mkdir()
        counter = self.work / "signing count"
        counter.write_text("0\n")
        java = path / "java"
        java.write_text(
            '#!/bin/sh\nif [ "${3:-}" = sign ]; then\n'
            f'  count=$(cat {shlex.quote(str(counter))})\n'
            '  count=$((count + 1))\n'
            f'  printf "%s\\n" "$count" > {shlex.quote(str(counter))}\n'
            '  if [ "$count" -eq 2 ]; then echo "injected second-signature failure" >&2; exit 37; fi\n'
            f'fi\nexec {shlex.quote(self.java)} "$@"\n'
        )
        java.chmod(0o755)
        env = dict(os.environ, PATH=str(path) + os.pathsep + os.environ["PATH"])
        self.assert_result(self.sign_bundle(env=env), 37, "injected second-signature failure")
        self.assertEqual(counter.read_text().strip(), "2")
        self.assert_no_outputs()

    def test_verifier_tool_failure_is_not_success(self):
        wrapper = self.work / "broken signer"
        wrapper.write_text("#!/bin/sh\nexit 37\n")
        wrapper.chmod(0o755)
        env = dict(self.env, APKSIGNER=str(wrapper))
        self.assert_result(self.verify(self.signed["correct"], env=env), 1, "could not verify")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, default=BUNDLE / "fenix-x86_64-release-unsigned.apk")
    parser.add_argument("--apksigner", type=Path, default=BUNDLE / "apksigner.jar")
    INPUTS, remaining = parser.parse_known_args()
    for value in (INPUTS.apk, INPUTS.apksigner):
        if not value.is_file():
            parser.error(f"required input is missing: {value}")
    if INPUTS.apksigner.suffix != ".jar":
        parser.error("--apksigner must point to apksigner.jar")
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
