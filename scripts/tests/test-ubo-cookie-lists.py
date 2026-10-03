#!/usr/bin/env python3
"""Offline tests for LW-M7-41: uBO's cookie-notice lists on by default on Android.

Covers scripts/gen-ubo-assets-android.py (the catalog derivation and the
bundled-XPI key check) and scripts/android-cookie-banner-smoke.py (reading the
packaged librewolf.cfg and XPI out of an APK or a tree). No network: --fetch is
exercised with a fake opener.
"""

import contextlib
import importlib.util
import io
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import zipfile


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = load("gen_ubo_assets_android", "scripts/gen-ubo-assets-android.py")
smoke = load("cookie_lists_smoke", "scripts/android-cookie-banner-smoke.py")
GROUP = gen.COOKIE_GROUP


def cookie_entry(title):
    return {"content": "filters", "group": "annoyances", "parent": GROUP, "off": True, "title": title,
            "contentURL": "https://example.invalid/" + title}


def catalog():
    return {
        "assets.json": {"content": "internal", "updateAfter": 13, "contentURL": "https://librewolf.invalid/a.json"},
        "ublock-filters": {"content": "filters", "group": "default", "title": "uBlock filters"},
        "adguard-cookies": cookie_entry("AdGuard - Cookie Notices"),
        "fanboy-cookiemonster": cookie_entry("EasyList - Cookie Notices"),
        "ublock-cookies-easylist": cookie_entry("uBlock filters - Cookie Notices"),
    }


def xpi_bytes(assets):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr("assets/assets.json", json.dumps(assets))
    return buffer.getvalue()


CFG = """null;
/** a comment naming defaultPref("librewolf.uBO.assetsBootstrapLocation", "https://commented.invalid/") */
defaultPref(
  "librewolf.uBO.assetsBootstrapLocation",
  "https://librewolf.invalid/raw/uBOAssets.json"
); // common.cfg
// defaultPref("librewolf.uBO.assetsBootstrapLocation", "https://line-comment.invalid/");
defaultPref(
  "librewolf.uBO.assetsBootstrapLocation",
  "%s"
);
""" % gen.ANDROID_CATALOG_URL


# ExtensionStorageIDB.sys.mjs as the migration patch leaves it: its added lines.
MODULE = "\n".join(line[1:] for line in
                   (ROOT / "patches/android/ubo-cookie-lists-migration.patch").read_text().splitlines()
                   if line.startswith("+") and not line.startswith("+++"))


class DeriveTests(unittest.TestCase):
    def test_exactly_three_differences(self):
        source = catalog()
        out = gen.derive(source)
        self.assertEqual(out["assets.json"]["contentURL"], [])
        for key in gen.COOKIE_LISTS:
            self.assertNotIn("off", out[key])
        self.assertTrue(out["adguard-cookies"]["off"], "only the EasyList/uBO pair is enabled")
        for key in gen.COOKIE_LISTS:
            out[key]["off"] = True
        out["assets.json"]["contentURL"] = source["assets.json"]["contentURL"]
        self.assertEqual(out, source)
        self.assertTrue(source["fanboy-cookiemonster"]["off"], "the input is not modified")

    def test_catalog_never_updates_itself(self):
        # uBO refreshes its catalog from the catalog's own assets.json entry;
        # a file cannot name the commit that pins it, so it names nothing.
        source = catalog()
        source["assets.json"]["cdnURLs"] = ["https://cdn.invalid/a.json"]
        out = gen.derive(source)
        self.assertNotIn("cdnURLs", out["assets.json"])
        self.assertEqual(gen.self_update_urls(out), [])
        self.assertEqual(gen.self_update_urls(source),
                         ["https://librewolf.invalid/a.json", "https://cdn.invalid/a.json"])
        shipped = json.loads(gen.TARGET.read_text(encoding="utf-8"))
        self.assertEqual(gen.self_update_urls(shipped), [])
        for key in gen.COOKIE_LISTS:
            self.assertTrue(shipped[key]["contentURL"], "the lists keep their upstream URLs")

    def test_missing_or_moved_list_is_an_error(self):
        source = catalog()
        del source["ublock-cookies-easylist"]
        with self.assertRaises(gen.CatalogError):
            gen.derive(source)
        source = catalog()
        source["fanboy-cookiemonster"]["parent"] = "Something else"
        with self.assertRaises(gen.CatalogError):
            gen.derive(source)

    def test_checked_in_catalog_is_current(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gen.main(["--check"]), 0)

    def test_pin_is_a_commit_that_serves_the_current_catalog(self):
        # Re-pin reminder: after the catalog changes, CATALOG_COMMIT (and
        # settings/android.cfg) must name the commit that carries the change.
        self.assertRegex(gen.CATALOG_COMMIT, r"^[0-9a-f]{40}$", "pin a full commit hash, never a branch")
        self.assertEqual(gen.ANDROID_CATALOG_URL, gen.pinned_url(gen.CATALOG_COMMIT))
        shown = subprocess.run(["git", "-C", str(ROOT), "show", f"{gen.CATALOG_COMMIT}:{gen.CATALOG_PATH}"],
                               capture_output=True)
        if shown.returncode != 0:
            self.skipTest(f"commit {gen.CATALOG_COMMIT} is not in this clone")
        self.assertEqual(shown.stdout.decode("utf-8"), gen.TARGET.read_text(encoding="utf-8"),
                         f"{gen.CATALOG_COMMIT} no longer serves {gen.CATALOG_PATH}: re-pin")

    def test_settings_bootstrap_from_the_pin(self):
        cfg = ROOT / "settings/android.cfg"
        if not cfg.exists():
            self.skipTest("settings submodule not checked out")
        found = smoke.effective_pref(cfg.read_text(encoding="utf-8"), smoke.PREF)
        self.assertEqual(found, ("defaultPref", gen.ANDROID_CATALOG_URL))

    def test_bundled_xpi_check(self):
        with tempfile.TemporaryDirectory() as scratch:
            good, bad = Path(scratch, "good.xpi"), Path(scratch, "bad.xpi")
            good.write_bytes(xpi_bytes(catalog()))
            without = catalog()
            del without["fanboy-cookiemonster"]
            bad.write_bytes(xpi_bytes(without))
            self.assertEqual(set(gen.check_xpi(good)), set(gen.COOKIE_LISTS))
            with self.assertRaises(gen.CatalogError):
                gen.check_xpi(bad)


class SmokeTests(unittest.TestCase):
    def test_last_call_wins_and_comments_are_ignored(self):
        self.assertEqual(smoke.effective_pref(CFG, smoke.PREF), ("defaultPref", gen.ANDROID_CATALOG_URL))
        self.assertIsNone(smoke.effective_pref(CFG, "no.such.pref"))
        locked = CFG + 'lockPref("librewolf.uBO.assetsBootstrapLocation", "https://other.invalid/");\n'
        self.assertEqual(smoke.effective_pref(locked, smoke.PREF), ("lockPref", "https://other.invalid/"))

    def apk(self, scratch, cfg, assets, module=None):
        omni = io.BytesIO()
        with zipfile.ZipFile(omni, "w") as archive:
            archive.writestr(smoke.CFG_IN_OMNI, cfg)
            archive.writestr(smoke.MIGRATION_IN_OMNI, MODULE if module is None else module)
        path = Path(scratch, "redoubt.apk")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("assets/omni.ja", omni.getvalue())
            archive.writestr(smoke.XPI_IN_APK, xpi_bytes(assets))
        return path

    def run_main(self, argv, opener=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = smoke.main(argv, opener) if opener else smoke.main(argv)
        return code, out.getvalue()

    def test_apk_passes(self):
        with tempfile.TemporaryDirectory() as scratch:
            code, out = self.run_main(["--apk", str(self.apk(scratch, CFG, catalog()))])
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("PASS"), 4, out)

    def test_apk_without_the_migration_fails(self):
        for module in ("export var ExtensionStorageIDB = {};\n",
                       MODULE.replace('"ublock-cookies-easylist"', '"other"')):
            with tempfile.TemporaryDirectory() as scratch:
                code, out = self.run_main(["--apk", str(self.apk(scratch, CFG, catalog(), module))])
            self.assertEqual(code, 1, out)
            self.assertIn("FAIL    migration", out)

    def test_apk_with_librewolf_catalog_fails(self):
        cfg = CFG.replace(gen.ANDROID_CATALOG_URL, "https://librewolf.invalid/raw/uBOAssets.json")
        with tempfile.TemporaryDirectory() as scratch:
            code, out = self.run_main(["--apk", str(self.apk(scratch, cfg, catalog()))])
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL    pref", out)

    def test_bundled_uBO_without_the_lists_fails(self):
        assets = catalog()
        del assets["ublock-cookies-easylist"]
        with tempfile.TemporaryDirectory() as scratch:
            code, out = self.run_main(["--apk", str(self.apk(scratch, CFG, assets))])
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL    bundled", out)

    def test_tree_mode(self):
        with tempfile.TemporaryDirectory() as scratch:
            tree = Path(scratch)
            (tree / smoke.CFG_IN_TREE).parent.mkdir(parents=True)
            (tree / smoke.CFG_IN_TREE).write_text(CFG)
            (tree / smoke.XPI_IN_TREE).parent.mkdir(parents=True)
            (tree / smoke.XPI_IN_TREE).write_bytes(xpi_bytes(catalog()))
            (tree / smoke.MIGRATION_IN_TREE).parent.mkdir(parents=True)
            (tree / smoke.MIGRATION_IN_TREE).write_text(MODULE)
            code, out = self.run_main(["--tree", str(tree)])
        self.assertEqual(code, 0, out)

    def test_missing_build_input_fails(self):
        with tempfile.TemporaryDirectory() as scratch:
            code, out = self.run_main(["--tree", scratch])
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL    build", out)

    def test_unpublished_catalog_is_pending_not_pass(self):
        def not_found(url, timeout):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        with tempfile.TemporaryDirectory() as scratch:
            code, out = self.run_main(["--apk", str(self.apk(scratch, CFG, catalog())), "--fetch"], not_found)
        self.assertEqual(code, 3, out)
        self.assertIn("PENDING hosted", out)

    def test_hosted_catalog_must_match(self):
        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        served = json.loads(gen.TARGET.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as scratch:
            apk = str(self.apk(scratch, CFG, catalog()))
            code, out = self.run_main(["--apk", apk, "--fetch"],
                                      lambda url, timeout: Response(json.dumps(served).encode()))
            self.assertEqual(code, 0, out)
            served["fanboy-cookiemonster"]["off"] = True
            code, out = self.run_main(["--apk", apk, "--fetch"],
                                      lambda url, timeout: Response(json.dumps(served).encode()))
        self.assertEqual(code, 1, out)


class MigrationTests(unittest.TestCase):
    """patches/android/ubo-cookie-lists-migration.patch: the one-time switch-on."""

    PATCH = ROOT / "patches/android/ubo-cookie-lists-migration.patch"

    def test_patch_names_the_generator_lists(self):
        text = self.PATCH.read_text()
        start = text.index("+const REDOUBT_UBO_COOKIE_LISTS = [")
        block = text[start:text.index("+];", start)]
        self.assertEqual(tuple(re.findall(r'"([^"]+)"', block)), gen.COOKIE_LISTS)

    def test_registered_once_after_ubo_patches(self):
        lines = [line.split("#", 1)[0].strip()
                 for line in (ROOT / "assets/patches/android.txt").read_text().splitlines()]
        lines = [line for line in lines if line]
        name = "patches/android/ubo-cookie-lists-migration.patch"
        self.assertEqual(lines.count(name), 1)
        self.assertGreater(lines.index(name), lines.index("patches/android/ubo-preinstall.patch"))

    def test_migration_javascript(self):
        result = subprocess.run(["node", str(ROOT / "scripts/tests/test-ubo-cookie-lists-migration.js"),
                                 str(self.PATCH)], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
