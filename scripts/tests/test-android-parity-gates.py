#!/usr/bin/env python3
"""Black-box regression checks for the static network and RFP gate wrappers."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
NETWORK = '''defaultPref("dom.security.https_only_mode.upgrade_local", true);
defaultPref("dom.security.https_only_mode_error_page_user_suggestions", true);
defaultPref("network.trr.mode", 5);
defaultPref("network.trr.uri", "https://dns10.quad9.net/dns-query");
defaultPref("network.trr.default_provider_uri", "https://doh.dns4all.eu/dns-query");
defaultPref("security.pki.crlite_mode", 2);
defaultPref("security.OCSP.enabled", 0);
pref("security.tls.enable_0rtt_data", false);
pref("security.tls.version.enable-deprecated", false);
defaultPref("security.ssl.require_safe_negotiation", true);
'''
RFP = '''defaultPref("privacy.resistFingerprinting", true);
defaultPref("privacy.resistFingerprinting.block_mozAddonManager", true);
defaultPref("privacy.globalprivacycontrol.enabled", true);
'''


class ParityGates(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="redoubt-parity-gates-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        (self.root / "settings").mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.sdk = self.root / "sdk"
        (self.sdk / "platform-tools").mkdir(parents=True)
        self.adb_log = self.root / "adb-invocations.txt"
        self.adb = self.sdk / "platform-tools/adb"
        self.adb.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$ADB_LOG"\necho device\n')
        self.adb.chmod(0o755)
        self.apk = self.root / "candidate.apk"
        self.apk.write_bytes(b"fixture; never installed")
        for area in ("network", "rfp"):
            shutil.copy2(ROOT / f"scripts/android-{area}-check.sh", self.root / "scripts")
        self.good = {"network": NETWORK, "rfp": RFP}
        self.key = {
            "network": "dom.security.https_only_mode.upgrade_local",
            "rfp": "privacy.resistFingerprinting",
        }

    def run_gate(self, area, *args, config=None):
        (self.root / "settings/common.cfg").write_text(
            self.good[area] if config is None else config
        )
        (self.root / "settings/android.cfg").write_text("// No overrides.\n")
        return self.invoke(area, *args)

    def invoke(self, area, *args):
        env = os.environ.copy()
        env["PATH"] = str(self.bin) + os.pathsep + env["PATH"]
        env["ADB_LOG"] = str(self.adb_log)
        return subprocess.run(
            ["bash", str(self.root / f"scripts/android-{area}-check.sh"), *map(str, args)],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )

    def assert_exit(self, result, code):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)

    def test_static_pass_cannot_claim_live_parity(self):
        for area in self.good:
            with self.subTest(area=area):
                result = self.run_gate(area)
                self.assert_exit(result, 0)
                self.assertIn("OVERALL: CONFIGURED ONLY", result.stdout)
                self.assertIn("live behavior UNMEASURED", result.stdout)
                self.assertNotIn("OVERALL: PASS", result.stdout)

    def test_connected_adb_without_probes_stays_pending(self):
        for area in self.good:
            with self.subTest(area=area):
                result = self.run_gate(
                    area, "--serial", "emulator-fixture", "--sdk", self.sdk, "--apk", self.apk
                )
                self.assert_exit(result, 3)
                self.assertIn("adb is connected", result.stdout)
                self.assertIn("honoured layer PENDING", result.stdout)
                self.assertNotIn("OVERALL: PASS", result.stdout)
        calls = self.adb_log.read_text().splitlines()
        self.assertEqual(calls, ["-s emulator-fixture get-state"] * 2)

    def test_partial_device_inputs_stay_pending(self):
        for area in self.good:
            with self.subTest(area=area):
                self.assert_exit(self.run_gate(area, "--serial", "fixture"), 3)
        self.assertFalse(self.adb_log.exists())

    def test_missing_apk_stays_pending_without_contacting_adb(self):
        for area in self.good:
            with self.subTest(area=area):
                result = self.run_gate(
                    area, "--serial", "fixture", "--sdk", self.sdk,
                    "--apk", self.root / "missing.apk",
                )
                self.assert_exit(result, 3)
                self.assertIn("APK does not exist", result.stdout)
        self.assertFalse(self.adb_log.exists())

    def test_unreachable_device_stays_pending(self):
        self.adb.write_text("#!/bin/sh\nexit 1\n")
        for area in self.good:
            with self.subTest(area=area):
                result = self.run_gate(
                    area, "--serial", "fixture", "--sdk", self.sdk, "--apk", self.apk
                )
                self.assert_exit(result, 3)
                self.assertIn("not reachable", result.stdout)

    def test_missing_cfg_is_failure(self):
        for area in self.good:
            with self.subTest(area=area):
                result = self.run_gate(area, "--cfg", self.root / "missing.cfg")
                self.assert_exit(result, 1)
                self.assertIn("FAIL [cfg input]", result.stdout)

    def test_missing_android_cfg_cannot_pass_with_good_common(self):
        for area in self.good:
            with self.subTest(area=area):
                self.run_gate(area)
                (self.root / "settings/android.cfg").unlink()
                self.assert_exit(self.invoke(area), 1)

    def test_cfg_read_errors_are_failures(self):
        for area in self.good:
            with self.subTest(area=area):
                self.assert_exit(self.run_gate(area, "--cfg", self.root / "settings"), 1)
                (self.root / "invalid.cfg").write_bytes(b"\xff")
                self.assert_exit(self.invoke(area, "--cfg", self.root / "invalid.cfg"), 1)

    def test_commented_good_cfg_is_not_configuration(self):
        for area in self.good:
            for prefix, suffix in (("/*\n", "*/\n"), ("// ", "")):
                with self.subTest(area=area, prefix=prefix):
                    cfg = self.good[area]
                    if prefix == "// ":
                        cfg = "\n".join("// " + line for line in cfg.splitlines())
                    else:
                        cfg = prefix + cfg + suffix
                    self.assert_exit(self.run_gate(area, config=cfg), 1)

    def test_commented_override_cannot_rescue_weakened_pref(self):
        for area in self.good:
            key = self.key[area]
            for comment in (f'// lockPref("{key}", true);\n', f'/* lockPref("{key}", true); */\n'):
                with self.subTest(area=area, comment=comment):
                    cfg = self.good[area] + f'defaultPref("{key}", false);\n' + comment
                    self.assert_exit(self.run_gate(area, config=cfg), 1)

    def test_pref_looking_string_does_not_override_value(self):
        for area in self.good:
            with self.subTest(area=area):
                key = self.key[area]
                cfg = self.good[area] + f'defaultPref("{key}", false);\n'
                cfg += f'defaultPref("irrelevant", `lockPref("{key}", true);`);\n'
                self.assert_exit(self.run_gate(area, config=cfg), 1)

    def test_multiline_calls_and_comments_preserve_url_strings(self):
        for area in self.good:
            with self.subTest(area=area):
                cfg = "null;\n/* comment */\n" + self.good[area].replace(
                    "defaultPref(", "defaultPref /* inline */ (\n"
                )
                cfg += 'setEnv("UNUSED", 1);\nclearPref("absent");\n'
                self.assert_exit(self.run_gate(area, config=cfg), 0)

    def test_lock_pref_is_recognized(self):
        for area in self.good:
            with self.subTest(area=area):
                cfg = self.good[area].replace("defaultPref(", "lockPref(").replace("\npref(", "\nlockPref(")
                self.assert_exit(self.run_gate(area, config=cfg), 0)

    def test_default_branch_cannot_overwrite_user_branch(self):
        for area in self.good:
            with self.subTest(area=area):
                key = self.key[area]
                cfg = self.good[area] + f'pref("{key}", false);\ndefaultPref("{key}", true);\n'
                self.assert_exit(self.run_gate(area, config=cfg), 1)

    def test_default_and_user_writes_cannot_override_lock(self):
        for area in self.good:
            with self.subTest(area=area):
                key = self.key[area]
                cfg = self.good[area] + f'lockPref("{key}", true);\ndefaultPref("{key}", false);\npref("{key}", false);\n'
                self.assert_exit(self.run_gate(area, config=cfg), 0)
                self.assert_exit(self.run_gate(area, config=cfg + f'unlockPref("{key}");\n'), 1)

    def test_lock_replaces_previous_locked_value(self):
        for area in self.good:
            with self.subTest(area=area):
                key = self.key[area]
                cfg = self.good[area] + f'lockPref("{key}", true);\nlockPref("{key}", false);\n'
                self.assert_exit(self.run_gate(area, config=cfg), 1)

    def test_clear_pref_restores_default(self):
        for area in self.good:
            with self.subTest(area=area):
                key = self.key[area]
                cfg = self.good[area] + f'pref("{key}", false);\nclearPref("{key}");\n'
                self.assert_exit(self.run_gate(area, config=cfg), 0)

    def test_user_write_equal_to_default_does_not_shadow_later_default(self):
        for area in self.good:
            with self.subTest(area=area):
                key = self.key[area]
                cfg = self.good[area] + f'pref("{key}", true);\ndefaultPref("{key}", false);\n'
                self.assert_exit(self.run_gate(area, config=cfg), 1)
                cfg = self.good[area] + f'defaultPref("{key}", false);\npref("{key}", false);\ndefaultPref("{key}", true);\n'
                self.assert_exit(self.run_gate(area, config=cfg), 0)

    def test_android_override_is_applied_after_common(self):
        for area in self.good:
            with self.subTest(area=area):
                self.run_gate(area)
                (self.root / "settings/android.cfg").write_text(f'defaultPref("{self.key[area]}", false);\n')
                self.assert_exit(self.invoke(area), 1)

    def test_unsupported_or_malformed_javascript_fails_closed(self):
        for area in self.good:
            for suffix in (
                "/* unclosed comment", 'defaultPref("unterminated, true);',
                'if (false) { defaultPref("x", true); }',
                'defaultPref("x", compute());', 'defaultPref("x", `${expression}`);',
                'defaultPref("x", true)',
            ):
                with self.subTest(area=area, suffix=suffix):
                    result = self.run_gate(area, config=self.good[area] + suffix)
                    self.assert_exit(result, 1)
                    self.assertIn("FAIL [cfg input]", result.stdout)

    def test_boolean_preferences_require_booleans(self):
        for area in self.good:
            for value in ('"true"', "1"):
                with self.subTest(area=area, value=value):
                    cfg = self.good[area] + f'defaultPref("{self.key[area]}", {value});\n'
                    self.assert_exit(self.run_gate(area, config=cfg), 1)

    def test_doh_explicit_off_is_the_configured_default(self):
        result = self.run_gate("network")
        self.assert_exit(result, 0)
        self.assertIn("5 = explicit off", result.stdout)
        self.assertIn("opt-in queries and DNS fallback", result.stdout)
        for mode in (0, 2, 3, 4):
            with self.subTest(mode=mode):
                cfg = NETWORK + f'defaultPref("network.trr.mode", {mode});\n'
                self.assert_exit(self.run_gate("network", config=cfg), 1)

    def test_revocation_requires_enforcement_without_ocsp_fallback(self):
        for override in (
            'defaultPref("security.pki.crlite_mode", 3);',
            'defaultPref("security.OCSP.enabled", false);',
        ):
            with self.subTest(override=override):
                self.assert_exit(self.run_gate("network", config=NETWORK + override), 1)

    def test_https_main_and_compiled_tls_default_are_explicitly_unmeasured(self):
        result = self.run_gate("network")
        self.assert_exit(result, 0)
        self.assertIn("effective Fenix HTTPS-only setting", result.stdout)
        self.assertIn("compiled default UNMEASURED", result.stdout)
        self.assert_exit(self.run_gate("network", config=NETWORK + 'defaultPref("dom.security.https_only_mode", false);'), 1)

    def test_self_test_accepts_both_positive_controls(self):
        for area in self.good:
            with self.subTest(area=area):
                result = self.run_gate(area, "--self-test")
                self.assert_exit(result, 0)
                self.assertIn("positive control accepted", result.stdout)
                self.assertIn("selected cfg accepted", result.stdout)

    def test_self_test_rejects_bad_selected_positive_control(self):
        for area in self.good:
            with self.subTest(area=area):
                cfg = self.good[area] + f'defaultPref("{self.key[area]}", false);\n'
                result = self.run_gate(area, "--self-test", config=cfg)
                self.assert_exit(result, 2)
                self.assertIn("selected cfg rejected", result.stdout)

    def test_self_test_cannot_skip_missing_selected_cfg(self):
        for area in self.good:
            with self.subTest(area=area):
                result = self.run_gate(area, "--self-test", "--cfg", self.root / "missing.cfg")
                self.assert_exit(result, 2)

    def test_self_test_detects_constant_or_broken_checker(self):
        fake_python = self.bin / "python3"
        for exit_code in (0, 1, 2):
            fake_python.write_text(f"#!/bin/sh\nexit {exit_code}\n")
            fake_python.chmod(0o755)
            for area in self.good:
                with self.subTest(area=area, checker_exit=exit_code):
                    result = self.run_gate(area, "--self-test")
                    self.assert_exit(result, 2)
                    self.assertIn("SELF-TEST FAILED", result.stdout)

    def test_usage_errors_are_distinct(self):
        for area in self.good:
            for option in ("--cfg", "--serial", "--sdk", "--apk", "--unknown"):
                with self.subTest(area=area, option=option):
                    self.assert_exit(self.invoke(area, option), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
