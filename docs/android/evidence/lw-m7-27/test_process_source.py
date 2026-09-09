"""Reject the real pre-correction process sources; native execution remains separate."""
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

import driver
from grade import InvalidResult


class ProcessSourceBindings(unittest.TestCase):
    def read_manifest(self, name):
        return {line[66:]: line[:64] for line in (driver.HERE / name).read_text().splitlines()}

    def overlay(self):
        return json.loads((driver.HERE / 'process-source-overlay.json').read_text())

    def test_only_six_reviewed_rows_change_and_four_supplements_are_preserved(self):
        before = self.read_manifest('pre-process-correction/proposed-native-test-source-sha256.txt')
        current = self.read_manifest('proposed-native-test-source-sha256.txt')
        product = self.read_manifest('composed-product-source-sha256.txt')
        extras = self.read_manifest('native-test-extra-source-sha256.txt')
        rows = self.overlay()['files']
        self.assertEqual(len(rows), 6)
        self.assertEqual(set(before), set(current))
        self.assertEqual({p for p in current if before[p] != current[p]}, {r['path'] for r in rows})
        self.assertEqual(current, product | extras)
        self.assertEqual((len(product), len(extras), len(current)), (245, 4, 249))
        for row in rows:
            self.assertEqual(before[row['path']], row['before_sha256'])
            self.assertEqual(current[row['path']], row['after_sha256'])

    def test_actual_failed_process_sources_cannot_pass_self_consistent_old_manifests(self):
        pins = json.loads(driver.HARNESS.read_text())['files']
        with tarfile.open(driver.HERE / 'process-before-source.tar.gz') as archive:
            for row in self.overlay()['files']:
                name = row['path']; data = archive.extractfile(name).read()
                self.assertEqual(hashlib.sha256(data).hexdigest(), row['before_sha256'])
                self.assertEqual(pins[name], row['after_sha256'])
                with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory); source = root / 'source'; target = source / name
                    target.parent.mkdir(parents=True); target.write_bytes(data)
                    manifest = root / 'manifest'; manifest.write_text(row['before_sha256'] + '  ' + name + '\n')
                    audited = root / 'audited'; audited.write_text(json.dumps({'files': {name: pins[name]}}))
                    requirements = {'product_paths': [name], 'xpcshell': [], 'instrumentation': [],
                                    'shutdown_instrumentation': {'expected_methods': []}}
                    with mock.patch.object(driver, 'reviewed_requirements', return_value=requirements), \
                         mock.patch.object(driver, 'HARNESS', audited), \
                         self.assertRaisesRegex(InvalidResult, 'audited harness changed'):
                        driver.source_binding(source, manifest)

    def test_actual_six_replacements_are_required_and_independently_audited(self):
        requirements = driver.reviewed_requirements()
        pins = json.loads(driver.HARNESS.read_text())['files']
        with tarfile.open(driver.HERE / 'process-source-overlay.tar.gz') as archive:
            self.assertEqual(len(archive.getmembers()), 6)
            for row in self.overlay()['files']:
                self.assertEqual(hashlib.sha256(archive.extractfile(row['path']).read()).hexdigest(), row['after_sha256'])
                self.assertEqual(pins[row['path']], row['after_sha256'])
                self.assertIn(row['path'], requirements['product_paths'])

    def test_native_inventory_and_private_copy_identity_fixes_remain_identical(self):
        before = json.loads((driver.HERE / 'pre-process-correction/requirements.json').read_text())
        current = driver.reviewed_requirements()
        for key in ['xpcshell', 'instrumentation', 'pending_xpcshell', 'shutdown_instrumentation']:
            self.assertEqual(current[key], before[key])
        hashes = json.loads((driver.HERE / 'pre-process-correction/driver-hashes.json').read_text())
        for name, digest in hashes.items():
            self.assertEqual(driver.sha(driver.HERE / name), digest)


if __name__ == '__main__':
    unittest.main()
