#!/usr/bin/env python3
"""Replay privacy-defaults' shared files in both orders in disposable scratch.

Only the two required source files are copied out of the pristine Android
archive. Existing patches are applied in list order to make the exact baseline;
each partner is then reversed before trying both orders with fuzz disabled.
The source archive and any existing build tree are never modified.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def sections(path):
    text = path.read_text()
    headers = list(re.finditer(
        r"^--- (?:a/(\S+)|/dev/null)[^\n]*\n"
        r"\+\+\+ (?:b/(\S+)|/dev/null)[^\n]*\n", text, re.M,
    ))
    result = {}
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        part = re.split(r"^diff ", text[header.start():end], flags=re.M)[0]
        result[header.group(2) or header.group(1)] = part
    return result


def apply(directory, content, reverse=False):
    command = ["patch", "--batch", "--fuzz=0", "-p1"]
    if reverse:
        command.append("--reverse")
    result = subprocess.run(command, input=content, cwd=directory,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    return {"command": command, "exit_status": result.returncode,
            "output": result.stdout}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[5]
    new_name = "patches/android/privacy-defaults.patch"
    sequence = []
    for target in ("common", "android"):
        for line in (repo / f"assets/patches/{target}.txt").read_text().splitlines():
            name = line.split("#", 1)[0].strip()
            if name:
                sequence.append(name)
    assert sequence[-1] == new_name, "Privacy patch must be last for this replay"
    patch_sections = {name: sections(repo / name) for name in sequence}
    new_sections = patch_sections[new_name]
    partners = {name: sorted(set(parts) & set(new_sections))
                for name, parts in patch_sections.items() if name != new_name}
    partners = {name: files for name, files in partners.items() if files}
    files = sorted({path for paths in partners.values() for path in paths})
    evidence = {
        "source_archive": str(args.archive.resolve()),
        "source_archive_sha256": digest(args.archive),
        "patch_sha256": {name: digest(repo / name) for name in sequence},
        "sequence": sequence, "baseline": [], "pairs": [],
    }
    with tempfile.TemporaryDirectory(prefix="privacy-pairs-", dir=args.scratch_root) as scratch:
        root = Path(scratch)
        pristine = root / "pristine"
        pristine.mkdir()
        missing = set(files)
        with tarfile.open(args.archive, "r|xz") as archive:
            for member in archive:
                matched = next((path for path in missing
                                if member.name.endswith("/" + path)), None)
                if matched is None:
                    continue
                assert member.isfile(), member.name
                target = pristine / matched
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                missing.remove(matched)
                if not missing:
                    break
        assert not missing, missing
        evidence["pristine_source_sha256"] = {path: digest(pristine / path) for path in files}
        baseline = root / "baseline"
        shutil.copytree(pristine, baseline)
        for name in sequence[:-1]:
            content = "".join(patch_sections[name][path]
                              for path in files if path in patch_sections[name])
            if not content:
                continue
            result = apply(baseline, content)
            evidence["baseline"].append({"patch": name, **result})
            assert result["exit_status"] == 0, (name, result)
        evidence["baseline_source_sha256"] = {path: digest(baseline / path) for path in files}
        for name, shared in partners.items():
            pair = {"partner": name, "shared_files": shared, "orders": {}}
            before = root / Path(name).stem
            before.mkdir()
            for path in shared:
                target = before / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(baseline / path, target)
            old_part = "".join(patch_sections[name][path] for path in shared)
            new_part = "".join(new_sections[path] for path in shared)
            pair["reverse_partner"] = apply(before, old_part, reverse=True)
            assert pair["reverse_partner"]["exit_status"] == 0, pair
            for label, ordered in (("partner_then_privacy", (old_part, new_part)),
                                   ("privacy_then_partner", (new_part, old_part))):
                directory = root / (Path(name).stem + "-" + label)
                shutil.copytree(before, directory)
                results = [apply(directory, part) for part in ordered]
                pair["orders"][label] = {
                    "steps": results,
                    "source_sha256": {path: digest(directory / path) for path in shared},
                }
            forward = pair["orders"]["partner_then_privacy"]
            backward = pair["orders"]["privacy_then_partner"]
            pair["byte_identical"] = forward["source_sha256"] == backward["source_sha256"]
            pair["both_orders_pass"] = all(
                step["exit_status"] == 0
                for result in pair["orders"].values() for step in result["steps"]
            )
            evidence["pairs"].append(pair)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    for pair in evidence["pairs"]:
        print(f"{pair['partner']}: both_orders_pass={pair['both_orders_pass']} "
              f"byte_identical={pair['byte_identical']}")
    return 0 if all(pair["both_orders_pass"] and pair["byte_identical"]
                    for pair in evidence["pairs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
