#!/usr/bin/env python3
"""Offline tests for the build's uBO trust boundary and asset packaging.

ZIP fixtures contain placeholder signature files, not valid signatures. These
tests exercise build validation; real signature verification belongs to Gecko.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("fetch_ubo", ROOT / "scripts/fetch-ubo-extension.py")
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)


class Download(io.BytesIO):
    def geturl(self):
        return "https://addons.mozilla.org/fixture.xpi"


class UboExtensionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="lw-m3-07-ubo-test-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.pin = fetcher.read_pin(ROOT / "assets/ubo-extension.json")
        self.manifest = {
            "manifest_version": 2,
            "version": self.pin["version"],
            "browser_specific_settings": {
                "gecko": {"id": self.pin["id"]},
                "gecko_android": {"strict_min_version": self.pin["android_min_version"]},
            },
        }
        self.xpi = self.root / "fixture.xpi"
        self.make_fixture()
        self.cache = self.root / "cache"
        self.assets = self.root / "main/assets"
        self.assets.mkdir(parents=True)

    def make_fixture(self, *, missing=None):
        with zipfile.ZipFile(self.xpi, "w") as archive:
            archive.writestr("manifest.json", json.dumps(self.manifest))
            for name in fetcher.SIGNATURE_FILES:
                if name != missing:
                    archive.writestr(name, b"signature verification is performed by Gecko")
            archive.writestr("background.js", b"/* fixture, never installed */")
        self.pin["size"] = self.xpi.stat().st_size
        self.pin["sha256"] = hashlib.sha256(self.xpi.read_bytes()).hexdigest()

    def cache_fixture(self):
        self.cache.mkdir()
        cached = self.cache / (self.pin["sha256"] + ".xpi")
        cached.write_bytes(self.xpi.read_bytes())
        return cached

    def write_pin(self):
        path = self.root / "pin.json"
        path.write_text(json.dumps(self.pin))
        return path

    def test_valid_fixture_and_packaging_preserve_every_byte_and_metadata(self):
        original = self.xpi.read_bytes()
        fetcher.validate_xpi(self.xpi, self.pin)
        packaged = fetcher.package_xpi(self.xpi, self.pin, self.assets)
        self.assertEqual(packaged.read_bytes(), original)
        self.assertEqual(self.xpi.read_bytes(), original)
        self.assertEqual(json.loads((self.assets / fetcher.METADATA_ASSET).read_text()), self.pin)
        self.assertEqual(sorted(p.name for p in packaged.parent.iterdir()),
                         ["ublock_origin.xpi", "ubo-extension.json"])

    def test_corrupt_hash_is_rejected(self):
        contents = bytearray(self.xpi.read_bytes())
        contents[-1] ^= 1
        self.xpi.write_bytes(contents)
        with self.assertRaisesRegex(fetcher.ValidationError, "SHA-256 mismatch"):
            fetcher.validate_xpi(self.xpi, self.pin)

    def test_corrupt_size_is_rejected(self):
        self.xpi.write_bytes(self.xpi.read_bytes()[:-1])
        with self.assertRaisesRegex(fetcher.ValidationError, "size mismatch"):
            fetcher.validate_xpi(self.xpi, self.pin)

    def test_wrong_guid_with_matching_digest_is_rejected(self):
        self.manifest["browser_specific_settings"]["gecko"]["id"] = "impostor@example.invalid"
        self.make_fixture()
        with self.assertRaisesRegex(fetcher.ValidationError, "wrong extension ID"):
            fetcher.validate_xpi(self.xpi, self.pin)

    def test_wrong_version_with_matching_digest_is_rejected(self):
        self.manifest["version"] = "0.0.0"
        self.make_fixture()
        with self.assertRaisesRegex(fetcher.ValidationError, "manifest version differs"):
            fetcher.validate_xpi(self.xpi, self.pin)

    def test_missing_android_support_is_rejected(self):
        del self.manifest["browser_specific_settings"]["gecko_android"]
        self.make_fixture()
        with self.assertRaisesRegex(fetcher.ValidationError, "lacks explicit Android support"):
            fetcher.validate_xpi(self.xpi, self.pin)

    def test_android_minimum_must_match_reviewed_pin(self):
        self.manifest["browser_specific_settings"]["gecko_android"]["strict_min_version"] = "999.0"
        self.make_fixture()
        with self.assertRaisesRegex(fetcher.ValidationError, "Android minimum version differs"):
            fetcher.validate_xpi(self.xpi, self.pin)

    def test_missing_signature_material_is_rejected(self):
        self.make_fixture(missing="META-INF/mozilla.rsa")
        with self.assertRaisesRegex(fetcher.ValidationError, "lacks required member: META-INF/mozilla.rsa"):
            fetcher.validate_xpi(self.xpi, self.pin)

    def test_pin_rejects_mutable_url_wrong_id_and_asset_escape(self):
        for key, value in (("url", "https://addons.mozilla.org/firefox/downloads/latest/ublock-origin/latest.xpi"),
                           ("id", "impostor@example.invalid"),
                           ("asset", "../outside.xpi"),
                           ("size", True), ("schema", True)):
            with self.subTest(key=key):
                broken = dict(self.pin, **{key: value})
                path = self.root / "broken-pin.json"
                path.write_text(json.dumps(broken))
                with self.assertRaises(fetcher.ValidationError):
                    fetcher.read_pin(path)

    def test_valid_cache_is_accepted_without_network(self):
        cached = self.cache_fixture()
        with mock.patch.object(fetcher.urllib.request, "build_opener") as opener:
            for offline in (True, False):
                self.assertEqual(fetcher.fetch_xpi(self.pin, self.cache, offline=offline), cached)
        opener.assert_not_called()

    def test_corrupt_cache_is_rejected_even_when_download_is_allowed(self):
        cached = self.cache_fixture()
        cached.write_bytes(b"damaged cache")
        with mock.patch.object(fetcher.urllib.request, "build_opener") as opener:
            for offline in (True, False):
                with self.subTest(offline=offline):
                    with self.assertRaisesRegex(fetcher.ValidationError, "size mismatch"):
                        fetcher.fetch_xpi(self.pin, self.cache, offline=offline)
        opener.assert_not_called()
        self.assertEqual(cached.read_bytes(), b"damaged cache")

    def test_offline_cache_miss_does_not_create_cache_or_fetch(self):
        with mock.patch.object(fetcher.urllib.request, "build_opener") as opener:
            with self.assertRaisesRegex(fetcher.ValidationError, "no cached uBO XPI for offline use"):
                fetcher.fetch_xpi(self.pin, self.cache, offline=True)
        opener.assert_not_called()
        self.assertFalse(self.cache.exists())

    def test_successful_download_is_validated_then_cached(self):
        original = self.xpi.read_bytes()
        with mock.patch.object(fetcher.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = Download(original)
            cached = fetcher.fetch_xpi(self.pin, self.cache)
        self.assertEqual(cached.read_bytes(), original)
        self.assertEqual(list(self.cache.iterdir()), [cached])
        self.assertEqual(opener.return_value.open.call_args.args[0].full_url, self.pin["url"])

    def test_failed_download_leaves_no_artifact_or_partial(self):
        with mock.patch.object(fetcher.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = urllib.error.URLError("fixture network failure")
            with self.assertRaisesRegex(urllib.error.URLError, "fixture network failure"):
                fetcher.fetch_xpi(self.pin, self.cache)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_truncated_or_oversize_download_leaves_no_artifact(self):
        original = self.xpi.read_bytes()
        for downloaded, message in ((original[:-1], "size mismatch"),
                                    (original + b"extra", "exceeds the pinned size")):
            with self.subTest(message=message):
                with mock.patch.object(fetcher.urllib.request, "build_opener") as opener:
                    opener.return_value.open.return_value = Download(downloaded)
                    with self.assertRaisesRegex(fetcher.ValidationError, message):
                        fetcher.fetch_xpi(self.pin, self.cache)
                self.assertEqual(list(self.cache.iterdir()), [])

    def test_redirect_to_plain_http_is_rejected(self):
        with self.assertRaisesRegex(fetcher.ValidationError, "non-HTTPS URL"):
            fetcher.HTTPSRedirectHandler().redirect_request(None, None, 302, "Found", {},
                                                          "http://example.invalid/fixture.xpi")

    def test_missing_fenix_assets_directory_fails_closed(self):
        missing = self.root / "renamed/assets"
        with self.assertRaisesRegex(fetcher.ValidationError, "Fenix asset directory is missing"):
            fetcher.package_xpi(self.xpi, self.pin, missing)
        self.assertFalse(missing.exists())

    def test_copy_changed_after_validation_does_not_replace_packaged_assets(self):
        packaged = fetcher.package_xpi(self.xpi, self.pin, self.assets)
        previous = packaged.read_bytes()
        original_copy = fetcher.shutil.copyfile

        def corrupt_copy(source, destination):
            original_copy(source, destination)
            Path(destination).write_bytes(b"changed while copying")

        with mock.patch.object(fetcher.shutil, "copyfile", side_effect=corrupt_copy):
            with self.assertRaisesRegex(fetcher.ValidationError, "size mismatch"):
                fetcher.package_xpi(self.xpi, self.pin, self.assets)
        self.assertEqual(packaged.read_bytes(), previous)
        self.assertEqual(json.loads((self.assets / fetcher.METADATA_ASSET).read_text()), self.pin)

    def test_cli_existing_input_packages_offline_without_populating_cache(self):
        args = ["--pin-file", str(self.write_pin()), "--xpi", str(self.xpi),
                "--asset-dir", str(self.assets), "--cache-dir", str(self.cache), "--offline"]
        with mock.patch.object(fetcher.urllib.request, "build_opener") as opener:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(fetcher.main(args), 0)
        opener.assert_not_called()
        self.assertFalse(self.cache.exists())
        self.assertEqual((self.assets / self.pin["asset"]).read_bytes(), self.xpi.read_bytes())

    def test_cli_bad_input_returns_failure_without_publishing_assets(self):
        self.xpi.write_bytes(b"corrupted")
        args = ["--pin-file", str(self.write_pin()), "--xpi", str(self.xpi), "--asset-dir", str(self.assets)]
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            self.assertEqual(fetcher.main(args), 1)
        self.assertIn("uBO XPI size mismatch", output.getvalue())
        self.assertEqual(list(self.assets.iterdir()), [])

    def test_fetcher_dry_run_never_fetches_or_creates_directories(self):
        args = ["--pin-file", str(self.write_pin()), "--cache-dir", str(self.cache),
                "--asset-dir", str(self.root / "absent/assets"), "--no-execute"]
        with mock.patch.object(fetcher.urllib.request, "build_opener") as opener:
            with mock.patch.object(fetcher.tempfile, "NamedTemporaryFile") as temporary:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(fetcher.main(args), 0)
        opener.assert_not_called()
        temporary.assert_not_called()
        self.assertFalse(self.cache.exists())
        self.assertFalse((self.root / "absent").exists())

    def test_patcher_dry_run_is_android_only_and_never_executes_or_creates_tempdir(self):
        patcher = ROOT / "scripts/librewolf-patches.py"
        original_cwd = Path.cwd()
        self.addCleanup(os.chdir, original_cwd)
        os.chdir(self.root)
        for target in ("android", "desktop"):
            with self.subTest(target=target):
                output = io.StringIO()
                with mock.patch.object(sys, "argv", [str(patcher), "--no-execute", "--targets", target, "153.0esr", "fixture"]):
                    with mock.patch("subprocess.run") as execute, mock.patch("os.system") as shell:
                        with mock.patch("tempfile.TemporaryDirectory") as temporary:
                            with contextlib.redirect_stdout(output):
                                with self.assertRaises(SystemExit) as exited:
                                    runpy.run_path(str(patcher), run_name="__main__")
                self.assertEqual(exited.exception.code, 0)
                execute.assert_not_called()
                shell.assert_not_called()
                temporary.assert_not_called()
                self.assertEqual("fetch-ubo-extension.py" in output.getvalue(), target == "android")
                self.assertFalse((self.root / "librewolf-153.0esr-fixture").exists())
                self.assertEqual(Path.cwd(), self.root)


if __name__ == "__main__":
    unittest.main()
