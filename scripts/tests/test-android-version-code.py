#!/usr/bin/env python3
"""Exercise the compiled Android Config class, not a reimplementation.

Run after a Gradle build with --classes <config/classes/kotlin/main> and
--gradle-home <build's gradle-home>. Only a temporary Java caller is compiled.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--classes', required=True, type=Path)
parser.add_argument('--gradle-home', required=True, type=Path)
args = parser.parse_args()
classes = args.classes.resolve()
if not (classes / 'Config.class').is_file():
    parser.error(f'compiled Config.class missing: {classes}')
jars = sorted(args.gradle_home.resolve().glob('wrapper/dists/gradle-*/**/lib/kotlin-stdlib-*.jar'))
if not jars:
    parser.error('Gradle distribution Kotlin stdlib not found')
classpath = os.pathsep.join(map(str, [classes, jars[-1]]))


class VersionCodeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory(prefix='redoubt-version-code-')
        probe = Path(cls.work.name) / 'VersionCodeProbe.java'
        probe.write_text('''public class VersionCodeProbe {
    public static void main(String[] args) {
        System.out.println(Config.generateFennecVersionCode(args[0]));
    }
}
''')
        subprocess.run(['javac', '-cp', classpath, str(probe)], check=True,
                       capture_output=True, text=True)
        cls.cp = os.pathsep.join([classpath, cls.work.name])

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def probe(self, build_date, abi='arm64-v8a', timezone='UTC'):
        env = os.environ.copy()
        env['TZ'] = timezone
        if build_date is None:
            env.pop('MOZ_BUILD_DATE', None)
        else:
            env['MOZ_BUILD_DATE'] = build_date
        return subprocess.run(['java', '-cp', self.cp, 'VersionCodeProbe', abi],
                              env=env, capture_output=True, text=True)

    def code(self, build_date, abi='arm64-v8a', timezone='UTC'):
        result = self.probe(build_date, abi, timezone)
        self.assertEqual(result.returncode, 0, result.stderr)
        return int(result.stdout.strip())

    def test_fixed_release_code_and_abi_precedence(self):
        # Fixed public release input; the expected integers are independent
        # fixtures, including the universal and architecture selection bits.
        expected = {'armeabi-v7a': 2016183064, 'arm64-v8a': 2016183066,
                    'x86_64': 2016183070, 'universal': 2016183071}
        for abi, version in expected.items():
            with self.subTest(abi=abi):
                self.assertEqual(self.code('20260906190000', abi), version)

    def test_next_release_hour_advances_code(self):
        for abi in ('armeabi-v7a', 'arm64-v8a', 'x86_64', 'universal'):
            with self.subTest(abi=abi):
                self.assertEqual(self.code('20260906200000', abi) -
                                 self.code('20260906190000', abi), 8)

    def test_subhour_rebuilds_keep_code(self):
        self.assertEqual(self.code('20260906190000'), self.code('20260906195959'))

    def test_host_timezone_does_not_change_code(self):
        for zone in ('UTC', 'Europe/Zurich', 'America/Los_Angeles', 'Pacific/Kiritimati'):
            with self.subTest(timezone=zone):
                self.assertEqual(self.code('20260906190000', timezone=zone), 2016183066)

    def test_missing_malformed_impossible_and_out_of_range_dates_fail(self):
        for build_date in (None, '', '2026090619000', '202609061900000',
                           '2026090619000x', '20260230000000', '20261301000000',
                           '20260906240000', '20141227235959', '20300101000000'):
            with self.subTest(build_date=build_date):
                result = self.probe(build_date)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertTrue(result.stderr.strip())


if __name__ == '__main__':
    unittest.main(argv=[__file__], verbosity=2)
