#!/usr/bin/env python3
"""Reject documentation drift using temporary evidence copies, never target code."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
EVIDENCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("coverage_checker", EVIDENCE / "check-coverage.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def edit_json(root, name, edit):
    path = root / name
    value = json.loads(path.read_text())
    edit(value)
    path.write_text(json.dumps(value, indent=2) + "\n")


def check_copy(edit=None, expected=None):
    with tempfile.TemporaryDirectory(prefix="lw17-controls-check-") as tmp:
        root = Path(tmp) / "evidence"
        shutil.copytree(EVIDENCE, root)
        checker.HERE = root
        if edit:
            edit(root)
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                checker.check()
            except ValueError as error:
                if expected is None or expected not in str(error):
                    raise AssertionError(f"unexpected rejection: {error}") from error
                return
        if expected is not None:
            raise AssertionError(f"mutation accepted, expected: {expected}")


def stale_markdown(root):
    path = root / "coverage-map.md"
    path.write_text(path.read_text().replace(
        "LW-M7-36 implements Enable IPv6", "No Android IPv6 control exists", 1))


def omit_save_dependency(root):
    edit_json(root, "coverage.json", lambda value: value["counterparts"]["graphics"]["evidence"].remove(
        "repo:patches/android/extension-update-controls.patch"))


def wrong_inspected_hash(root):
    edit_json(root, "global-controls-followup/review.json", lambda value:
              value["inspected_files"][0].update(sha256="0" * 64))


def unrelated_counterpart(root):
    edit_json(root, "coverage.json", lambda value:
              value["counterparts"]["sync"].update(android="Unreviewed replacement."))


def false_compile(root):
    edit_json(root, "global-controls-followup/review.json", lambda value:
              value.update(compile_verdict="PASS"))


def false_runtime(root):
    edit_json(root, "followup-review.json", lambda value:
              value["global_controls_followup"].update(runtime_verdict="PASS"))


def wrong_historical_patch(root):
    edit_json(root, "followup-review.json", lambda value:
              value["added_repository_inputs"]["patches/android/canvas-webgl-permissions.patch"]
              ["compiler_followup"].update(previous_sha256="0" * 64))


def changed_before_archive(root):
    path = root / "global-controls-followup/before-review.tar.gz"
    path.write_bytes(path.read_bytes() + b"changed")


def altered_original_effect(root):
    edit_json(root, "coverage.json", lambda value:
              value["desktop_patches"][0]["effects"][0].update(effect="Unreviewed replacement."))


CASES = [
    (stale_markdown, "readable global-controls mapping differs: network-controls"),
    (omit_save_dependency, "global-controls counterpart lacks reviewed dependency: graphics"),
    (wrong_inspected_hash, "global-controls inspected source pin changed:"),
    (unrelated_counterpart, "global-controls review changed unrelated counterpart"),
    (false_compile, "global-controls source review must not claim target success"),
    (false_runtime, "global-controls source review must not claim target success"),
    (wrong_historical_patch, "historical reviewed patch is not pinned:"),
    (changed_before_archive, "before-review archive changed"),
    (altered_original_effect, "global-controls review changed original mapping: desktop_patches"),
]

if __name__ == "__main__":
    check_copy()
    print("PASS: unmodified evidence accepted")
    for edit, expected in CASES:
        check_copy(edit, expected)
        print(f"PASS: {edit.__name__} rejected")
    print(f"{len(CASES)} negative controls passed; no target code executed.")
