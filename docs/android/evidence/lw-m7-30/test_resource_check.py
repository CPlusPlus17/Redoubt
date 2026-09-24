"""Reject false packaged-resource success; these are host parser/ZIP tests."""
from pathlib import Path
import importlib.util
import json
import subprocess
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('shortcut_check', Path(__file__).with_name('check-source.py'))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
EMPTY = b'{\n  "data": []\n}\n'
EXPECTED = check.sha(EMPTY)
HEADER = 'Binary APK\nPackage name=org.redoubtbrowser id=7f\n  type raw id=13 entryCount=2\n'
ENTRY = '    resource 0x7f130005 raw/initial_shortcuts\n'
DEFAULT = '      () (file) res/GA.json\n'
TAIL = '    resource 0x7f130007 raw/other\n      () (file) res/other.json\n'
DUMP = HEADER + ENTRY + DEFAULT + TAIL


class ResourceCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.apk = Path(self.tmp.name) / 'candidate.apk'

    def write_apk(self, members=None):
        if members is None:
            members = [('resources.arsc', b'host fixture only'), ('res/GA.json', EMPTY)]
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.apk, 'w') as archive:
                for name, value in members:
                    archive.writestr(name, value)

    def validate(self, dump=DUMP):
        return check.check_packaged_bytes(self.apk, check.resolve_resource(dump), EXPECTED)

    def test_optimized_mapping(self):
        self.write_apk()
        self.assertEqual(self.validate()['mappings'][0],
                         {'configuration': '', 'member': 'res/GA.json', 'size': 17, 'sha256': EXPECTED})

    def test_unoptimized_mapping_still_requires_table(self):
        self.write_apk([('resources.arsc', b'fixture'), ('res/raw/initial_shortcuts.json', EMPTY)])
        self.validate(DUMP.replace('res/GA.json', 'res/raw/initial_shortcuts.json'))
        with self.assertRaisesRegex(ValueError, 'exactly one resource entry'):
            self.validate(DUMP.replace('raw/initial_shortcuts', 'raw/another'))

    def test_matching_unrelated_bytes_cannot_replace_missing_member(self):
        self.write_apk([('resources.arsc', b'fixture'), ('res/unrelated.json', EMPTY)])
        with self.assertRaisesRegex(ValueError, 'missing or duplicate mapped'):
            self.validate()

    def test_matching_unrelated_bytes_cannot_replace_incorrect_resource(self):
        self.write_apk([('resources.arsc', b'fixture'), ('res/GA.json', b'{"data":["Google"]}'),
                        ('res/unrelated.json', EMPTY)])
        with self.assertRaisesRegex(ValueError, 'bytes/schema mismatch'):
            self.validate()

    def test_all_configurations_checked(self):
        second = '      (ja) (file) res/JP.json\n'
        self.write_apk([('resources.arsc', b'fixture'), ('res/GA.json', EMPTY),
                        ('res/JP.json', b'{"data":["region default"]}')])
        with self.assertRaisesRegex(ValueError, 'bytes/schema mismatch: res/JP.json'):
            self.validate(HEADER + ENTRY + DEFAULT + second + TAIL)
        self.write_apk([('resources.arsc', b'fixture'), ('res/GA.json', EMPTY), ('res/JP.json', EMPTY)])
        self.assertEqual(len(self.validate(HEADER + ENTRY + DEFAULT + second + TAIL)['mappings']), 2)

    def test_duplicate_zip_member_or_resource_table(self):
        for duplicate in ['resources.arsc', 'res/GA.json']:
            with self.subTest(duplicate=duplicate):
                self.write_apk([('resources.arsc', b'fixture'), ('res/GA.json', EMPTY), (duplicate, EMPTY)])
                with self.assertRaisesRegex(ValueError, 'duplicate'):
                    self.validate()

    def test_missing_table(self):
        self.write_apk([('res/GA.json', EMPTY)])
        with self.assertRaisesRegex(ValueError, 'missing or duplicate APK resource table'):
            self.validate()

    def test_duplicate_entry_or_package_or_configuration(self):
        for dump in [DUMP + ENTRY + DEFAULT, DUMP + HEADER, HEADER + ENTRY + DEFAULT + DEFAULT]:
            with self.subTest(dump=dump):
                with self.assertRaises(ValueError):
                    check.resolve_resource(dump)

    def test_wrong_package_and_resource_prefix(self):
        for dump in [DUMP.replace('org.redoubtbrowser', 'org.unrelated'),
                     DUMP.replace('0x7f130005', '0x80130005'),
                     DUMP.replace('raw/initial_shortcuts', 'raw/initial_shortcuts_other')]:
            with self.subTest(dump=dump):
                with self.assertRaises(ValueError):
                    check.resolve_resource(dump)

    def test_missing_default_and_unsupported_values(self):
        for value in ['      (ja) (file) res/GA.json\n', '      () @0x7f130004\n',
                      '      () "res/GA.json"\n', '']:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    check.resolve_resource(HEADER + ENTRY + value + TAIL)

    def test_unsafe_member_paths(self):
        for member in ['../res/GA.json', '/res/GA.json', 'res/../GA.json', 'res//GA.json',
                       'res/./GA.json', 'res/GA\\file.json', 'assets/GA.json']:
            with self.subTest(member=member):
                with self.assertRaisesRegex(ValueError, 'unsafe resource ZIP path'):
                    check.resolve_resource(DUMP.replace('res/GA.json', member))

    def test_schema_and_exact_bytes_both_required(self):
        for content in [b'{"data":[]}', b'{"data":[],"other":1}', b'not JSON']:
            self.write_apk([('resources.arsc', b'fixture'), ('res/GA.json', content)])
            with self.assertRaisesRegex(ValueError, 'bytes/schema mismatch'):
                self.validate()

    def test_aapt2_failure_is_not_resource_success(self):
        self.write_apk()
        tool = Path(self.tmp.name) / 'tool'
        tool.write_bytes(b'host boundary fixture')
        with patch.object(check.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['aapt2'])):
            with self.assertRaises(subprocess.CalledProcessError):
                check.check_apk(self.apk, tool, EXPECTED)

    def test_apk_replaced_during_dump_is_rejected(self):
        self.write_apk()
        tool = Path(self.tmp.name) / 'tool'
        tool.write_bytes(b'host boundary fixture')

        def run(command, **kwargs):
            if command[1] == 'version':
                return subprocess.CompletedProcess(command, 0, 'fixture version', '')
            self.write_apk([('resources.arsc', b'replacement'), ('res/GA.json', EMPTY)])
            return subprocess.CompletedProcess(command, 0, DUMP, '')

        with patch.object(check.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(ValueError, 'APK changed during inspection'):
                check.check_apk(self.apk, tool, EXPECTED)

    def test_aapt2_diagnostics_fail_closed(self):
        self.write_apk()
        tool = Path(self.tmp.name) / 'tool'
        tool.write_bytes(b'host boundary fixture')
        result = subprocess.CompletedProcess(['aapt2'], 0, DUMP, 'warning: malformed table')
        with patch.object(check.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(ValueError, 'emitted diagnostics'):
                check.check_apk(self.apk, tool, EXPECTED)


if __name__ == '__main__':
    unittest.main()
