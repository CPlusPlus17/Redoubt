#!/usr/bin/env python3
"""Check enumeration and input binding, never browser feature parity."""

import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(rows, key, label):
    values = [row[key] for row in rows]
    require(len(values) == len(set(values)), f"duplicate {label}")
    return set(values)


def leaves(value, pointer=""):
    if isinstance(value, dict):
        for key, item in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            yield from leaves(item, pointer + "/" + escaped)
    else:
        # An array is one exact, ordered value. No element can be omitted.
        yield pointer, value


def check():
    inputs = json.loads((HERE / "input-inventory.json").read_text())
    coverage = json.loads((HERE / "coverage.json").read_text())
    source = json.loads((HERE / "source-evidence.json").read_text())
    searches = json.loads(gzip.decompress((HERE / "bounded-searches.json.gz").read_bytes()))
    require(coverage["runtime_verdict"].startswith("NOT RUN"), "audit must not claim a live verdict")
    require(coverage["snapshot_commit"] == source["repository_commit"], "mixed source snapshots")
    patch_list = (ROOT / "assets/patches/desktop.txt").read_bytes()
    require(digest(patch_list) == inputs["patch_list_sha256"], "desktop patch list changed; re-audit")
    paths = [line.split("#", 1)[0].strip() for line in patch_list.decode().splitlines()]
    paths = [path for path in paths if path]
    require(len(paths) == len(set(paths)), "duplicate registered desktop patch")
    mapped = unique(coverage["desktop_patches"], "path", "desktop mapping")
    inventory = unique(inputs["desktop_patches"], "path", "desktop input")
    require(set(paths) == mapped == inventory, "unmapped or extra desktop patch")
    require(len(paths) == inputs["desktop_patch_count"], "desktop input count mismatch")
    original = {entry["path"]: entry for entry in inputs["desktop_patches"]}
    references = []
    effect_count = 0
    for entry in coverage["desktop_patches"]:
        path = entry["path"]
        raw = (ROOT / path).read_bytes()
        require(digest(raw) == entry["sha256"] == original[path]["sha256"], f"patch changed: {path}")
        tree_paths = sorted(set(re.findall(r"^\+\+\+ b/(.+)$", raw.decode(), re.M)))
        require(tree_paths == sorted(entry["tree_paths"]) == sorted(original[path]["tree_paths"]),
                f"desktop tree paths differ: {path}")
        require(entry["effects"], f"no semantic effects: {path}")
        for effect in entry["effects"]:
            require(effect["effect"].strip() and effect["counterparts"], f"empty effect: {path}")
            references.extend(effect["counterparts"])
            effect_count += 1

    archive = (HERE / "inspected-source.tar.gz").read_bytes()
    require(digest(archive) == source["archive_sha256"], "source archive hash mismatch")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
        members = tf.getmembers()
        names = [member.name for member in members]
        require(len(names) == len(set(names)), "duplicate archived source")
        expected = {item["archive_member"] for item in source["sources"].values()}
        require(set(names) == expected, "source archive/member index mismatch")
        for key, item in source["sources"].items():
            member = tf.getmember(item["archive_member"])
            require(member.isfile(), f"non-file archived source: {key}")
            raw = tf.extractfile(member).read()
            require(digest(raw) == item["sha256"], f"archived source changed: {key}")
            if key == "settings-distribution/policies.json":
                policy_raw = raw
        require(digest(policy_raw) == inputs["policy_sha256"], "policy input hash mismatch")
        policies = json.loads(policy_raw)["policies"]
    require(policies == inputs["policies"], "policy values differ from input inventory")
    require(set(policies) == set(coverage["policies"]), "unmapped or extra policy key")
    require(len(policies) == inputs["policy_count"], "policy count mismatch")
    all_leaves = []
    for entry in coverage["policies"].values():
        require(entry["effect"].strip() and entry["leaves"], "empty policy effect")
        all_leaves.extend(entry["leaves"])
        for leaf in entry["leaves"]:
            require(leaf["effect"].strip() and leaf["counterparts"], "empty policy leaf")
            references.extend(leaf["counterparts"])
    unique(all_leaves, "pointer", "policy leaf")
    require(dict(leaves(policies)) == {leaf["pointer"]: leaf["value"] for leaf in all_leaves},
            "unmapped, extra or changed policy subkey/value")

    # The settings submodule is optional for replay because exact source bytes
    # are preserved. If populated, verify it too; do not silently accept drift.
    settings_file = ROOT / inputs["policy_file"]
    if settings_file.is_file():
        require(digest(settings_file.read_bytes()) == inputs["policy_sha256"],
                "working settings policy changed; re-audit")
    index = subprocess.check_output(["git", "ls-files", "--stage", "settings"], cwd=ROOT, text=True)
    require(index.split()[1] == source["settings_commit"], "settings gitlink changed; re-audit")

    pane_assets = unique(coverage["pane_assets"], "path", "pane asset")
    require(pane_assets == set(inputs["copied_pane_assets"]), "unmapped copied pane asset")
    for item in coverage["pane_assets"]:
        require(digest((ROOT / item["path"]).read_bytes()) == item["sha256"] ==
                inputs["copied_pane_assets"][item["path"]], f"pane asset changed: {item['path']}")
        require(item["effect"].strip(), "pane asset has no effect mapping")
        references.extend(item["counterparts"])
    js = (ROOT / "patches/pref-pane/librewolf.js").read_text()
    xhtml = (ROOT / "patches/pref-pane/librewolf.inc.xhtml").read_text()
    controls = set(re.findall(r'Preferences\.addSetting\(\{\s*id:\s*"([^"]+)"', js))
    controls.update(re.findall(r'<button\s+id="([^"]+)"', xhtml))
    require(controls == unique(coverage["pane_controls"], "id", "pane control"),
            "unmapped or extra copied pane setting/button")
    active_js = "\n".join(line.split("//", 1)[0] for line in js.splitlines())
    registrations = set(re.findall(r'\{\s*id:\s*"([^"]+)"\s*,\s*type:', active_js))
    require(registrations == unique(coverage["pane_registered_prefs"], "pref", "pane pref"),
            "unmapped or extra pane pref registration")
    for item in coverage["pane_controls"] + coverage["pane_registered_prefs"]:
        require(item["counterparts"], "pane effect lacks counterpart")
        references.extend(item["counterparts"])

    query_ids = unique(searches["queries"], "id", "absence search")
    require(all(query["exit_code"] in (0, 1) and not query["stderr"] for query in searches["queries"]),
            "a captured search failed")
    counterparts = coverage["counterparts"]
    require(set(references) <= set(counterparts), "unknown counterpart reference")
    used_repo_refs = set()
    for key, item in counterparts.items():
        require(item["status"] in {"desktop_boundary", "source_implemented_runtime_open", "mixed_open", "open_gap"},
                f"unsupported/overstated status: {key}")
        require(item["android"].strip() and item["remaining"].strip() and item["evidence"],
                f"counterpart lacks claim, limits or evidence: {key}")
        for ref in item["evidence"]:
            kind, value = ref.split(":", 1)
            if kind == "source":
                require(value in source["sources"], f"unknown source: {ref}")
            elif kind == "repo":
                used_repo_refs.add(value)
                require(value in coverage["repository_evidence"], f"unpinned repository source: {ref}")
            elif kind == "search":
                require(value in query_ids or value == "fenix-locales", f"unknown search: {ref}")
            else:
                raise ValueError(f"unknown evidence reference: {ref}")
    require(used_repo_refs == set(coverage["repository_evidence"]), "unused or missing repo input hash")
    for path, expected in coverage["repository_evidence"].items():
        require(digest((ROOT / path).read_bytes()) == expected, f"Android counterpart input changed: {path}")
    print(f"COVERAGE INPUTS VERIFIED: {len(paths)} desktop patches / {effect_count} effect groups; "
          f"{len(policies)} policy keys / {len(all_leaves)} exact leaves; "
          f"{len(pane_assets)} copied assets / {len(controls)} controls / {len(registrations)} pref registrations.")
    print(f"Pinned evidence: {len(source['sources'])} archived source files, "
          f"{len(used_repo_refs)} repository counterpart inputs, {len(query_ids)} bounded searches.")
    print("RUNTIME PARITY: NOT TESTED by this audit. Open gaps and proof obligations remain in coverage.json.")


if __name__ == "__main__":
    try:
        check()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, tarfile.TarError) as error:
        print(f"COVERAGE CHECK FAILED: {error}", file=sys.stderr)
        sys.exit(1)
