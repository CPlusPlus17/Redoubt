#!/usr/bin/env python3
"""Local driver contract tests; temporary files only, never a guest acceptance run."""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import stage as s


class FileContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='current245-stage-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()

    def put(self, name, data=b'old'):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_full_hash_and_absence_check_rejects_changed_input(self):
        path = self.put('a')
        s.source_checks(self.source, {'a': s.v.sha(b'old'), 'new': None})
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'source hash differs'):
            s.source_checks(self.source, {'a': s.v.sha(b'old'), 'new': None})

    def test_expected_absence_rejects_regular_file_or_broken_symlink(self):
        path = self.put('new')
        with self.assertRaisesRegex(ValueError, 'expected source absence'):
            s.source_checks(self.source, {'new': None})
        path.unlink()
        path.symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            s.source_checks(self.source, {'new': None})

    def test_escape_and_symlink_parents_never_write_outside_source(self):
        external = self.root / 'outside'
        external.mkdir()
        (self.source / 'link').symlink_to(external)
        for name in ('../outside/a', '/absolute', 'a/../b', 'link/a'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                s.install_body(self.source, name, None, b'new')
        self.assertEqual(list(external.iterdir()), [])

    def test_replacement_preserves_mode_and_unselected_files(self):
        path = self.put('nested/a')
        path.chmod(0o751)
        untouched = self.put('untouched', b'keep')
        s.install_body(self.source, 'nested/a', s.v.sha(b'old'), b'new')
        self.assertEqual(path.read_bytes(), b'new')
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o751)
        self.assertEqual(untouched.read_bytes(), b'keep')
        self.assertEqual([p.name for p in path.parent.iterdir()], ['a'])

    def test_create_builds_declared_parent_and_uses_regular_0644_file(self):
        s.install_body(self.source, 'new/tree/a', None, b'created')
        path = self.source / 'new/tree/a'
        self.assertEqual(path.read_bytes(), b'created')
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

    def test_concurrent_create_fails_without_overwriting_other_writer(self):
        original_link = os.link
        def competing_create(temporary, target):
            target.write_bytes(b'external')
            original_link(temporary, target)
        with patch.object(s.os, 'link', side_effect=competing_create), self.assertRaises(FileExistsError):
            s.install_body(self.source, 'a', None, b'ours')
        self.assertEqual((self.source / 'a').read_bytes(), b'external')
        self.assertEqual([p.name for p in self.source.iterdir()], ['a'])

    def test_changed_replacement_fails_before_mutation(self):
        path = self.put('a', b'external')
        with self.assertRaisesRegex(ValueError, 'source hash differs'):
            s.install_body(self.source, 'a', s.v.sha(b'old'), b'ours')
        self.assertEqual(path.read_bytes(), b'external')

    def test_directory_sync_failure_is_not_acknowledged_as_success(self):
        path = self.put('a')
        real_fsync = os.fsync
        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError('directory sync failed')
            real_fsync(fd)
        with patch.object(s.os, 'fsync', side_effect=fail_directory), self.assertRaisesRegex(OSError, 'directory sync failed'):
            s.install_body(self.source, 'a', s.v.sha(b'old'), b'new')
        # Rename happened; the stage must retain an attempted-write marker and
        # fail rather than pretend that this post-rename error rolled it back.
        self.assertEqual(path.read_bytes(), b'new')
        self.assertEqual([p.name for p in self.source.iterdir()], ['a'])

    def test_backup_contains_only_replacements_with_exact_bytes_and_mode(self):
        path = self.put('a')
        path.chmod(0o640)
        self.put('retained', b'keep')
        folder = self.root / 'evidence'
        folder.mkdir()
        plan = {'rows': {'a': {'action': 'replace-if-before-matches'},
                         'retained': {'action': 'retain-bound-input'}, 'new': {'action': 'create-if-absent'}},
                'before': {'a': s.v.sha(b'old'), 'retained': s.v.sha(b'keep'), 'new': None}}
        receipt = s.backup_replacements(self.source, plan, folder)
        self.assertEqual(receipt['count'], 1)
        archive = s.c.checked(receipt['archive'])
        self.assertEqual(s.v.unpack(archive.read_bytes()), {'a': b'old'})
        index = json.loads(s.c.checked(receipt['files']).read_text())
        self.assertEqual(index, [{'path': 'a', 'sha256': s.v.sha(b'old'), 'bytes': 3, 'mode': 0o640}])
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed before backup'):
            s.backup_replacements(self.source, plan, folder)

    def fake_execution(self):
        """Mock guest admission only; run real driver filesystem/progress logic."""
        self.put('a')
        out = self.root / 'evidence'
        handoff = self.root / 'handoff'
        handoff.mkdir()
        for name in ('receipt.json', 'proposed-staging.json', 'expected-current167-source-sha256.txt'):
            (handoff / name).write_text('{}\n')
        config_path = self.root / 'config.json'
        config = {'prerequisites': {'preserved_files': []}}
        config_path.write_text(json.dumps(config))
        plan = {'before': {'a': s.v.sha(b'old')}, 'final': {'a': s.v.sha(b'new')},
                'rows': {'a': {'action': 'replace-if-before-matches', 'after_sha256': s.v.sha(b'new')}},
                'bodies': {'a': b'new'}}
        stack = ExitStack()
        self.addCleanup(stack.close)
        for target, key, value in ((s, 'OUT', out), (s.c, 'SOURCE', self.source), (s.v, 'HANDOFF', handoff)):
            stack.enter_context(patch.object(target, key, value))
        for key, value in (('own_service', {}), ('prerequisites', config['prerequisites']),
                           ('checked_config', (config, plan)), ('check_preserved', None)):
            stack.enter_context(patch.object(s, key, return_value=value))
        stack.enter_context(patch.object(s.c, 'guest_guard'))
        stack.enter_context(patch.object(s, 'backup_replacements', return_value={'count': 43}))
        return config_path, out

    def test_failed_admission_does_not_create_evidence_or_mutate_source(self):
        config_path, out = self.fake_execution()
        with patch.object(s, 'prerequisites', side_effect=ValueError('runtime not terminal')), self.assertRaisesRegex(ValueError, 'runtime not terminal'):
            s.execute(config_path, 'unused-mocked-config-hash')
        self.assertFalse(out.exists())
        self.assertEqual((self.source / 'a').read_bytes(), b'old')

    def test_post_rename_failure_retains_attempt_and_failed_receipt(self):
        config_path, out = self.fake_execution()
        original_install = s.install_body
        def fail_after_install(*args):
            original_install(*args)
            raise OSError('injected after rename')
        with patch.object(s, 'install_body', side_effect=fail_after_install), self.assertRaisesRegex(OSError, 'after rename'):
            s.execute(config_path, 'unused-mocked-config-hash')
        result = json.loads((out / 'receipt.json').read_text())
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['applied'], [])
        self.assertEqual(result['attempting']['path'], 'a')
        self.assertEqual(result['attempting']['before_sha256'], s.v.sha(b'old'))
        self.assertIn('finished', result)
        self.assertFalse((out / 'source-sha256.txt').exists())
        self.assertEqual((self.source / 'a').read_bytes(), b'new')

    def test_existing_evidence_rejects_automatic_retry(self):
        config_path, out = self.fake_execution()
        out.mkdir()
        (out / 'receipt.json').write_text('{"status":"FAIL"}\n')
        with self.assertRaisesRegex(ValueError, 'output already exists'):
            s.execute(config_path, 'unused-mocked-config-hash')
        self.assertEqual(json.loads((out / 'receipt.json').read_text())['status'], 'FAIL')
        self.assertEqual((self.source / 'a').read_bytes(), b'old')


class ArchiveContracts(unittest.TestCase):
    def archive(self, members):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for member in members:
                archive.addfile(member, io.BytesIO(b'x'))
        return stream.getvalue()

    def test_duplicate_and_link_members_are_rejected(self):
        regular = tarfile.TarInfo('a')
        regular.size = 1
        link = tarfile.TarInfo('link')
        link.type, link.linkname = tarfile.SYMTYPE, 'a'
        for members in ([regular, regular], [link]):
            with self.subTest(members=members), self.assertRaises(ValueError):
                s.v.unpack(self.archive(members))

    def test_parent_escape_archive_member_is_rejected(self):
        member = tarfile.TarInfo('../outside')
        member.size = 1
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            s.v.unpack(self.archive([member]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
