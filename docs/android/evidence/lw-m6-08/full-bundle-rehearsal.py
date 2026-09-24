#!/usr/bin/env python3
"""Rehearse the final complete signing bundle using a new disposable key only.

Run from any directory. The copied bundle, generated test key, certificate,
test signing document, and signed APKs are deleted when the run ends.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[4]
SOURCE = REPO / "librewolf-android-apk-153.0esr-1-beta-20260908/apk"
ABIS = ("arm64-v8a", "armeabi-v7a", "universal", "x86_64")
TOOLS = ("apksigner.jar", "sign.sh", "android-verify-signature.sh", "SIGNING.md")
spec = importlib.util.spec_from_file_location("signing_test_helpers", REPO / "scripts/tests/test-android-signing.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bundle_hashes(folder):
    return {str(path.relative_to(folder)): digest(path)
            for path in sorted(folder.rglob("*")) if path.is_file()}


def run(command, **kwargs):
    print("COMMAND:", shlex.join(map(str, command)), flush=True)
    result = helpers.invoke(list(map(str, command)), **kwargs)
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
    print("EXIT:", result.returncode, flush=True)
    helpers.require_success(result)
    return result.stdout


print("Full final-candidate signing rehearsal; disposable key only.", flush=True)
print("Started UTC:", datetime.now(timezone.utc).isoformat(), flush=True)
print("Source bundle:", SOURCE, flush=True)
print("Harness SHA-256:", digest(Path(__file__)), flush=True)
print("PTY helper SHA-256:", digest(REPO / "scripts/tests/test-android-signing.py"), flush=True)
run(["java", "-version"])
before = bundle_hashes(SOURCE)
print("SOURCE BUNDLE BEFORE:", json.dumps(before, sort_keys=True, indent=2), flush=True)
assert len([name for name in before if name.endswith("-release-unsigned.apk")]) == 4
for abi in ABIS:
    path = SOURCE / f"fenix-{abi}-release-unsigned.apk"
    print("FULL APK BYTES:", path.name, path.stat().st_size, flush=True)
    assert path.stat().st_size > 100_000_000, "full candidate required; reduced fixtures are forbidden"

cache = Path.home() / ".cache"
cache.mkdir(exist_ok=True)
temporary_path = None
try:
    with tempfile.TemporaryDirectory(prefix="redoubt-full-signing-", dir=cache) as temporary:
        temporary_path = Path(temporary)
        bundle = temporary_path / "complete bundle with spaces"
        caller = temporary_path / "outside bundle caller"
        bundle.mkdir()
        caller.mkdir()
        run(["cp", "-a", "--reflink=auto", str(SOURCE) + "/.", bundle])
        assert bundle_hashes(bundle) == before
        password = secrets.token_urlsafe(32)
        key_env = dict(os.environ, LW_REHEARSAL_KEY_PASSWORD=password)
        key = temporary_path / "temporary-test-key.p12"
        cert = temporary_path / "temporary-public-certificate.der"
        run([
            "keytool", "-genkeypair", "-keystore", key, "-storetype", "PKCS12",
            "-storepass:env", "LW_REHEARSAL_KEY_PASSWORD", "-keyalg", "RSA", "-keysize", "4096",
            "-sigalg", "SHA384withRSA", "-validity", "1", "-alias", "disposable-test",
            "-dname", "CN=Disposable full Redoubt bundle rehearsal,O=Not a release key",
        ], env=key_env)
        run([
            "keytool", "-exportcert", "-keystore", key, "-storetype", "PKCS12",
            "-storepass:env", "LW_REHEARSAL_KEY_PASSWORD", "-alias", "disposable-test", "-file", cert,
        ], env=key_env)
        fingerprint = ":".join(digest(cert).upper()[i:i + 2] for i in range(0, 64, 2))
        (bundle / "SIGNING.md").write_text(
            "# Disposable full-bundle test certificate; not a release identity\n\n"
            f"SHA-256 fingerprint\n    {fingerprint}\n\n"
        )
        helpers.checksum_manifest(bundle, TOOLS, "SHA256SUMS.tools")
        print("TEMPORARY PUBLIC TEST FINGERPRINT:", fingerprint, flush=True)
        print("TEST COPY TOOLS MANIFEST:\n" + (bundle / "SHA256SUMS.tools").read_text(), flush=True)
        signing = run([bundle / "sign.sh", os.path.relpath(key, caller)], cwd=caller, password=password)
        assert signing.count("Keystore password for signer #1:") == 4
        signed = [bundle / f"fenix-{abi}-release.apk" for abi in ABIS]
        assert all(path.is_file() for path in signed)
        assert not list(bundle.glob("*.idsig"))
        assert not list(bundle.glob(".redoubt-sign.*"))
        env = dict(os.environ, APKSIGNER=str(bundle / "apksigner.jar"))
        intake = run([
            bundle / "android-verify-signature.sh", "--unsigned-dir", SOURCE,
            "--signing-doc", bundle / "SIGNING.md", *signed,
        ], env=env, cwd=caller)
        assert intake.count("ZIP payload matches candidate") == 4
        run(["sha256sum", "-c", "SHA256SUMS.signed"], cwd=bundle)
        for path in signed:
            details = run(["java", "-jar", bundle / "apksigner.jar", "verify", "--verbose", "--print-certs", path])
            assert "Verified using v1 scheme (JAR signing): false" in details
            assert "Verified using v2 scheme (APK Signature Scheme v2): true" in details
            assert "Verified using v3 scheme (APK Signature Scheme v3): true" in details
            assert fingerprint.replace(":", "").lower() in details.lower()
        print("SIGNED OUTPUT SHA-256:", json.dumps({p.name: digest(p) for p in signed}, indent=2), flush=True)
        for abi in ABIS:
            name = f"fenix-{abi}-release-unsigned.apk"
            assert digest(bundle / name) == before[name]
        print("RESULT: all four full APKs signed interactively; v1 false; v2/v3 true; temporary test fingerprint matched; payloads match actual final candidate.", flush=True)
finally:
    after = bundle_hashes(SOURCE)
    print("SOURCE BUNDLE AFTER:", json.dumps(after, sort_keys=True, indent=2), flush=True)
    print("SOURCE BUNDLE UNCHANGED:", before == after, flush=True)
    print("TEMPORARY WORKSPACE REMOVED:", temporary_path is not None and not temporary_path.exists(), flush=True)
    print("Finished UTC:", datetime.now(timezone.utc).isoformat(), flush=True)
    assert before == after
    assert temporary_path is not None and not temporary_path.exists()
