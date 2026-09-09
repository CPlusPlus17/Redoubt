#!/usr/bin/env python3
"""Regression for a warmed objdir mixing earlier fat and current ABI output."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT/'scripts/android-fat-aar.sh').read_text()
FUNCTION = re.search(r'^isolate_maven_repository\(\) \{.*?^\}', SOURCE, re.M | re.S).group()


class MavenPublicationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.obj = Path(self.temporary.name)/'object directory'
        (self.obj/'gradle').mkdir(parents=True)

    def run_isolation(self, prefix=''):
        script = 'die() { echo "$*" >&2; exit 1; }\nlog() { :; }\n' + prefix + FUNCTION
        script += '\nisolate_maven_repository "$1" x86_64\n'
        return subprocess.run(['bash', '-c', script, 'test', str(self.obj)], capture_output=True, text=True)

    def publish(self, path, contents):
        target = self.obj/'gradle/maven'/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)

    def test_cold_build_has_no_prior_publication(self):
        self.assertEqual(self.run_isolation().returncode, 0)
        self.assertEqual(list((self.obj/'gradle').iterdir()), [])

    def test_warmed_fat_and_old_abi_are_preserved_outside_new_publication(self):
        old = {'geckoview-default-omni/153/merged.aar': b'older fat native code',
               'geckoview-default-omni-x86_64/152/old.aar': b'old ABI native code',
               'geckoview-default-omni/153/merged.pom': b'old metadata'}
        for name, contents in old.items():
            self.publish(name, contents)
        self.assertEqual(self.run_isolation().returncode, 0)
        self.assertFalse((self.obj/'gradle/maven').exists())
        self.publish('geckoview-default-omni-x86_64/153/current.aar', b'new ABI native code')
        current = list((self.obj/'gradle/maven').rglob('*.aar'))
        self.assertEqual([p.name for p in current], ['current.aar'])
        previous, = (self.obj/'gradle').glob('maven-before-x86_64.*')
        self.assertEqual({str(p.relative_to(previous/'maven')): p.read_bytes()
                          for p in (previous/'maven').rglob('*') if p.is_file()}, old)

    def test_repeated_build_preserves_each_prior_publication(self):
        for value in [b'first', b'second']:
            self.publish('version/artifact.aar', value)
            self.assertEqual(self.run_isolation().returncode, 0)
        self.assertEqual({p.read_bytes() for p in (self.obj/'gradle').rglob('artifact.aar')},
                         {b'first', b'second'})
        self.assertFalse((self.obj/'gradle/maven').exists())

    def test_failed_move_aborts_and_keeps_original(self):
        self.publish('version/artifact.aar', b'preserve')
        self.assertNotEqual(self.run_isolation('mv() { return 9; }\n').returncode, 0)
        self.assertEqual((self.obj/'gradle/maven/version/artifact.aar').read_bytes(), b'preserve')


if __name__ == '__main__':
    unittest.main()
