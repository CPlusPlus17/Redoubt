#!/usr/bin/env python3
"""Hermetic tests for scripts/ci-vm-boxb/prune-tree-cache.py (box B tree caches).

Each case builds a fake LW_CI_ROOT in a temporary directory, points
LW_PRUNE_ALLOWED_ROOT at it (the script refuses any other root) and checks
which tree-<version>-<release> directories survive. No network, no VM.

Usage: python3 scripts/tests/test-boxb-prune-tree-cache.py
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts/ci-vm-boxb/prune-tree-cache.py"


class PruneTreeCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "redoubt-ci"
        self.root.mkdir()
        for d in ("tarballs", "out", "gradle-home"):
            (self.root / d).mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def mk(self, *names):
        for n in names:
            (self.root / n / "obj").mkdir(parents=True)
            (self.root / n / "obj" / "f").write_text("x" * 100)

    def run_it(self, current, *extra, allowed=None):
        env = dict(os.environ, LW_PRUNE_ALLOWED_ROOT=str(allowed or self.root))
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), "--current", current, *extra],
            env=env, capture_output=True, text=True)

    def left(self):
        return sorted(p.name for p in self.root.iterdir())

    # The box B state of 2026-10-14, before 158.0-2's tree exists.
    def test_dry_run_deletes_nothing(self):
        self.mk("tree-157.0-3", "tree-157.0.1-1", "tree-158.0-1")
        before = self.left()
        r = self.run_it("158.0-2", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.left(), before)
        self.assertIn("would remove", r.stdout)
        self.assertIn("tree-157.0-3", r.stdout)
        self.assertIn("tree-157.0.1-1", r.stdout)
        self.assertIn("keep   tree-158.0-1", r.stdout)
        self.assertIn("2 tree(s) to remove", r.stdout)

    def test_keeps_current_and_previous_when_current_not_built(self):
        self.mk("tree-157.0-3", "tree-157.0.1-1", "tree-158.0-1")
        r = self.run_it("158.0-2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.left(), ["gradle-home", "out", "tarballs", "tree-158.0-1"])

    def test_keeps_current_and_previous_when_current_built(self):
        self.mk("tree-157.0-3", "tree-157.0.1-1", "tree-158.0-1", "tree-158.0-2")
        r = self.run_it("158.0-2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([n for n in self.left() if n.startswith("tree-")],
                         ["tree-158.0-1", "tree-158.0-2"])

    def test_numeric_not_string_order(self):
        # As strings, "157.0.1-1" < "157.0-3" would be wrong, and 99 > 158.
        self.mk("tree-99.0-1", "tree-157.0-3", "tree-157.0.1-1")
        r = self.run_it("157.0.1-1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([n for n in self.left() if n.startswith("tree-")],
                         ["tree-157.0-3", "tree-157.0.1-1"])

    def test_current_is_kept_even_if_older(self):
        # A rebuild of an older release must not delete its own tree.
        self.mk("tree-157.0-3", "tree-158.0-1", "tree-158.0-2")
        r = self.run_it("157.0-3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([n for n in self.left() if n.startswith("tree-")],
                         ["tree-157.0-3", "tree-158.0-1", "tree-158.0-2"])

    def test_nothing_to_do(self):
        self.mk("tree-158.0-1")
        r = self.run_it("158.0-2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("0 tree(s) removed", r.stdout)

    def test_odd_names_and_symlinks_left_alone(self):
        self.mk("tree-150.0-1", "tree-158.0-1", "tree-158.0-2")
        outside = pathlib.Path(self.tmp.name) / "outside"
        (outside / "keepme").mkdir(parents=True)
        os.symlink(outside, self.root / "tree-100.0-1")
        (self.root / "tree-junk").mkdir()
        (self.root / "tree-151.0-1.partial").mkdir()
        (self.root / "tree-152.0-1").write_text("a file")
        r = self.run_it("158.0-2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((outside / "keepme").is_dir())
        left = self.left()
        self.assertNotIn("tree-150.0-1", left)
        for n in ("tree-100.0-1", "tree-junk", "tree-151.0-1.partial", "tree-152.0-1",
                  "tree-158.0-1", "tree-158.0-2", "tarballs", "out", "gradle-home"):
            self.assertIn(n, left)

    def test_refuses_other_root(self):
        self.mk("tree-150.0-1", "tree-158.0-1")
        other = pathlib.Path(self.tmp.name) / "elsewhere"
        other.mkdir()
        r = self.run_it("158.0-2", allowed=other)
        self.assertEqual(r.returncode, 2)
        self.assertIn("refusing", r.stderr)
        self.assertIn("tree-150.0-1", self.left())

    def test_default_allowed_root_is_the_runner_cache(self):
        env = {k: v for k, v in os.environ.items() if k != "LW_PRUNE_ALLOWED_ROOT"}
        self.mk("tree-150.0-1")
        r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), "--current", "158.0-2"],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("/home/runner/actions-runner/redoubt-ci", r.stderr)
        self.assertIn("tree-150.0-1", self.left())

    def test_bad_input(self):
        self.assertEqual(self.run_it("158.0").returncode, 2)
        self.assertEqual(self.run_it("158.0-2", "--keep", "1").returncode, 2)

    def test_missing_root_is_fine(self):
        env = dict(os.environ, LW_PRUNE_ALLOWED_ROOT=str(self.root))
        r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root / "nope"), "--current", "158.0-2"],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
