"""Real local copy/I/O controls; no guest, native compiler or device runs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import driver
from grade import InvalidResult, grade_run, sha
import test_grade

spec = importlib.util.spec_from_file_location('private_source_wrapper', driver.HERE / 'in-vm.py')
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)


class SourceCopy(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'product'; self.source.mkdir()
        (self.source / 'body').write_text('reviewed source')
        for name in ['obj-x86_64', 'obj-arm64-v8a', '.gradle']:
            (self.source / name).mkdir(); (self.source / name / 'cache').write_text('keep in product')
        self.copy = self.root / 'copy'; self.receipt = self.root / 'receipt.json'
        self.manifest = self.root / 'manifest'; self.manifest.write_text('host fixture manifest')
        self.binding = self.bind(self.source, self.manifest)

    def bind(self, source, manifest):
        return {'manifest_sha256': sha(manifest), 'product_files': {'body': sha(source / 'body')}}

    def prepare(self):
        with patch.object(driver, 'source_binding', side_effect=self.bind):
            return wrapper.prepare_source_copy(self.source, self.copy, self.receipt, self.manifest, self.binding)

    def verify(self):
        with patch.object(driver, 'source_binding', side_effect=self.bind):
            return wrapper.verify_source_copy(self.source, self.copy, self.receipt, self.manifest, self.binding)

    def test_real_copy_has_independent_inodes_and_excludes_production_outputs(self):
        self.prepare(); self.verify()
        self.assertNotEqual((self.copy / 'body').stat().st_ino, (self.source / 'body').stat().st_ino)
        self.assertEqual(list(p.name for p in self.copy.iterdir()), ['body'])
        (self.copy / '.gradle').mkdir(); (self.copy / '.gradle' / 'cache').write_text('new private cache')
        self.verify()
        self.assertEqual((self.source / '.gradle' / 'cache').read_text(), 'keep in product')
        (self.copy / 'body').write_text('changed copy')
        self.assertEqual((self.source / 'body').read_text(), 'reviewed source')
        with self.assertRaisesRegex(InvalidResult, 'private source changed'): self.verify()

    def test_escaping_and_directory_symlinks_rejected_before_copy(self):
        (self.root / 'external').write_text('must not read through copy')
        (self.source / 'link').symlink_to(self.root / 'external')
        with self.assertRaisesRegex(InvalidResult, 'symlink escapes'): self.prepare()
        self.assertFalse(self.copy.exists())
        (self.source / 'link').unlink(); (self.source / 'link').symlink_to(self.source / '.gradle', target_is_directory=True)
        with self.assertRaisesRegex(InvalidResult, 'directory symlink'): self.prepare()

    def test_internal_file_symlink_is_dereferenced_without_a_production_write_link(self):
        (self.source / 'link').symlink_to(self.source / 'body')
        self.prepare()
        self.assertFalse((self.copy / 'link').is_symlink())
        (self.copy / 'link').write_text('independent')
        self.assertEqual((self.source / 'body').read_text(), 'reviewed source')

    def test_prior_or_failed_copy_is_preserved(self):
        with patch.object(wrapper.subprocess, 'run', side_effect=OSError('controlled copy failure')):
            with self.assertRaises(OSError): self.prepare()
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'FAIL')
        with self.assertRaisesRegex(InvalidResult, 'already exists'): self.prepare()

    def test_changed_production_or_receipt_cannot_reuse_copy(self):
        self.prepare()
        (self.source / 'body').write_text('other product')
        with self.assertRaisesRegex(InvalidResult, 'production source changed'): self.verify()
        (self.source / 'body').write_text('reviewed source')
        row = json.loads(self.receipt.read_text()); row['source_count'] += 1
        self.receipt.write_text(json.dumps(row))
        with self.assertRaisesRegex(InvalidResult, 'receipt differs'): self.verify()


class CompletedIdentity(unittest.TestCase):
    def test_changed_run_date_revision_and_missing_build_plan_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = {'build_date': '20260906190000', 'product_revision_operator_supplied': 'a' * 40}
            (root / 'plan.json').write_text(json.dumps(plan))
            build = dict(plan, plan_sha256=sha(root / 'plan.json'))
            driver.require_completed_identity(build, plan, root)
            for key, value in [('build_date', '20260907190000'), ('product_revision_operator_supplied', 'b' * 40)]:
                with self.subTest(key=key), self.assertRaisesRegex(InvalidResult, 'run differs'):
                    driver.require_completed_identity(build, dict(plan, **{key: value}), root)
            (root / 'plan.json').write_text('{}')
            with self.assertRaisesRegex(InvalidResult, 'plan changed'):
                driver.require_completed_identity(build, plan, root)

    def test_archived_plan_tampering_is_rejected_without_target_tree(self):
        fixture = test_grade.EvidenceBinding('test_bound_fresh_bytes')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.make_run(); grade_run(fixture.path)
        fixture.write('plan.json', {'build_date': '20260907190000'})
        with self.assertRaisesRegex(InvalidResult, 'plan changed'): grade_run(fixture.path)


if __name__ == '__main__':
    unittest.main()
