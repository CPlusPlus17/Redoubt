#!/usr/bin/env python3
"""Replay the scoped source candidate; this is not a target build or test runner."""

import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    manifest = json.loads((HERE / "source-files.json").read_text())
    patch = ROOT / "patches/android/sync-opt-in.patch"
    require(digest(patch.read_bytes()) == manifest["patch_sha256"], "candidate patch hash changed")
    helper = manifest["unmodified_test_helper"]
    require(digest((HERE / helper["retained_excerpt"]).read_bytes()) == helper["excerpt_sha256"],
            "upstream test-helper excerpt changed")
    paths = [item["path"] for item in manifest["files"]]
    touched = re.findall(r"^\+\+\+ b/(.+)$", patch.read_text(), re.M)
    require(len(touched) == len(set(touched)) and set(touched) == set(paths), "source scope mismatch")
    task = next(item for item in yaml.safe_load((ROOT / "docs/android/tasks.yaml").read_text())["tasks"]
                if item["id"] == "LW-M7-20")
    require(set(task["tree_paths"]) == set(paths), "declared task source scope differs")
    archive = (HERE / "scoped-pristine.tar.gz").read_bytes()
    require(digest(archive) == manifest["scoped_pristine_archive_sha256"], "pristine archive changed")
    for predecessor in manifest["scoped_predecessors"]:
        require(digest((ROOT / predecessor["path"]).read_bytes()) == predecessor["sha256"],
                f"predecessor changed: {predecessor['path']}")
    with tempfile.TemporaryDirectory(prefix="lw-m7-20-source-") as directory:
        destination = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(archive)), mode="r:") as retained:
            members = retained.getmembers()
            require({item.name for item in members} == set(manifest["scoped_pristine_files"]),
                    "archive/source inventory mismatch")
            require(len(members) == len(manifest["scoped_pristine_files"]), "duplicate archive path")
            for item in members:
                require(item.isfile() and not item.name.startswith("/") and ".." not in Path(item.name).parts,
                        "invalid retained member")
                data = retained.extractfile(item).read()
                require(digest(data) == manifest["scoped_pristine_files"][item.name], "pristine file hash changed")
                target = destination / item.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        for predecessor in manifest["scoped_predecessors"]:
            subprocess.run(
                ["git", "apply", *["--include=" + path for path in paths], str(ROOT / predecessor["path"])],
                cwd=destination, check=True, capture_output=True,
            )
        for item in manifest["files"]:
            target = destination / item["path"]
            require((digest(target.read_bytes()) if target.exists() else None) == item["before_sha256"],
                    f"pre-candidate source differs: {item['path']}")
        subprocess.run(["git", "apply", "--check", "--whitespace=error-all", str(patch)], cwd=destination, check=True, capture_output=True)
        subprocess.run(["git", "apply", str(patch)], cwd=destination, check=True, capture_output=True)
        for item in manifest["files"]:
            data = (destination / item["path"]).read_bytes()
            require(digest(data) == item["after_sha256"], f"final source differs: {item['path']}")
            if "/src/test/" in item["path"]:
                require(data.decode().count("@Test") == item["authored_tests"], "authored test count changed")
    print(f"SOURCE REPLAY PASS: {len(manifest['scoped_predecessors'])} scoped predecessors; "
          f"{len(paths)} final files match their individual pins.")
    print(f"AUTHORED KOTLIN TESTS: {sum(item['authored_tests'] for item in manifest['files'])}; "
          "NOT EXECUTED by this replay.")
    print("TARGET COMPILATION / APK RUNTIME: NOT RUN. See README.md for required acceptance evidence.")


if __name__ == "__main__":
    main()
