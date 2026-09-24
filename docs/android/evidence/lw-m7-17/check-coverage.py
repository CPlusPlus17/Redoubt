#!/usr/bin/env python3
"""Check enumeration and input binding, never browser feature parity."""

import gzip
import hashlib
import importlib.util
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


def check_global_controls(coverage, followup, source):
    """Bind this scoped source review; these checks do not run its target code."""
    scope = {"graphics", "rfp-controls", "addon-updates", "network-controls"}
    current = followup["global_controls_followup"]
    require(current["review_receipt"] == "global-controls-followup/review.json",
            "unexpected global-controls review receipt")
    review = json.loads((HERE / current["review_receipt"]).read_text())
    require(set(current["scope"]) == set(review["scope"]) == scope,
            "global-controls review scope changed")
    require(current["repository_before_edit"] == review["repository_before_edit"] ==
            coverage["snapshot_commit"], "global-controls repository provenance changed")
    for item in (current, review):
        require(item["compile_verdict"].startswith("NOT RUN") and
                item["runtime_verdict"].startswith("NOT RUN"),
                "global-controls source review must not claim target success")
    require(review["unchanged_original_archive_sha256"] == source["archive_sha256"],
            "global-controls review relabels original source")
    archive = (HERE / "global-controls-followup/before-review.tar.gz").read_bytes()
    require(digest(archive) == review["before_review_archive_sha256"],
            "before-review archive changed")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
        names = [member.name for member in tf.getmembers()]
        require(len(names) == len(set(names)) and set(names) == {
            "coverage.json", "coverage-map.md", "followup-review.json", "check-coverage.py", "README.md",
        }, "before-review archive/member mismatch")
        require(all(member.isfile() for member in tf.getmembers()), "non-file before-review input")
        previous = json.loads(tf.extractfile("coverage.json").read())
        previous_map = tf.extractfile("coverage-map.md").read().decode()
    for key in ("desktop_patches", "policies", "pane_controls", "pane_registered_prefs", "pane_assets",
                "source_capture_commit"):
        require(coverage[key] == previous[key], f"global-controls review changed original mapping: {key}")
    require(set(coverage["counterparts"]) == set(previous["counterparts"]),
            "global-controls review changed counterpart inventory")
    actual_changes = {key for key in coverage["counterparts"]
                      if coverage["counterparts"][key] != previous["counterparts"][key]}
    require(actual_changes == scope, "global-controls review changed unrelated counterpart or omitted a control")
    required = review["required_repository_evidence"]
    require(set(required) == scope, "global-controls evidence scope changed")
    for key, paths in required.items():
        require({"repo:" + path for path in paths} <= set(coverage["counterparts"][key]["evidence"]),
                f"global-controls counterpart lacks reviewed dependency: {key}")

    manifests = {}
    for task, patch in (("35", "extension-update-controls"), ("36", "global-privacy-controls")):
        path = f"docs/android/evidence/lw-m7-{task}/source-files.json"
        manifest = json.loads((ROOT / path).read_text())
        require(manifest["patch_sha256"] ==
                coverage["repository_evidence"][f"patches/android/{patch}.patch"],
                f"global-controls source/patch lineage mismatch: {task}")
        manifests[task] = {item["path"]: item["after_sha256"] for item in manifest["files"]}
    unique(review["inspected_files"], "path", "global-controls inspected source")
    require({item["task"] for item in review["inspected_files"]} == set(manifests),
            "global-controls inspected source task missing")
    for item in review["inspected_files"]:
        require(manifests[item["task"]].get(item["path"]) == item["sha256"],
                f"global-controls inspected source pin changed: {item['path']}")

    def sections(markdown):
        return {match.group(1): match.group(2) for match in
                re.finditer(r"^### ([^\n]+)\n(.*?)(?=^### |\Z)", markdown, re.M | re.S)}

    markdown = sections((HERE / "coverage-map.md").read_text())
    old_markdown = sections(previous_map)
    require(set(markdown) == set(old_markdown), "readable counterpart inventory changed")
    labels = {"mixed_open": "Mixed open", "source_implemented_runtime_open": "Source implemented, runtime open"}
    for key in scope:
        item = coverage["counterparts"][key]
        require(f"**{labels[item['status']]}.** {item['android']}\n" in markdown[key] and
                f"**Remaining:** {item['remaining']}\n" in markdown[key],
                f"readable global-controls mapping differs: {key}")
    require(all(markdown[key] == old_markdown[key] for key in markdown if key not in scope),
            "global-controls review changed unrelated readable counterpart")


def check():
    inputs = json.loads((HERE / "input-inventory.json").read_text())
    coverage = json.loads((HERE / "coverage.json").read_text())
    source = json.loads((HERE / "source-evidence.json").read_text())
    followup = json.loads((HERE / "followup-review.json").read_text())
    searches = json.loads(gzip.decompress((HERE / "bounded-searches.json.gz").read_bytes()))
    require(coverage["runtime_verdict"].startswith("NOT RUN"), "audit must not claim a live verdict")
    require(coverage["source_capture_commit"] == source["repository_commit"] ==
            followup["source_capture_commit"] == followup["original_repository_snapshot"],
            "original source capture provenance changed")
    require(coverage["snapshot_commit"] == followup["audited_repository_snapshot"],
            "followup repository snapshot mismatch")
    require(followup["archived_source_sha256"] == source["archive_sha256"],
            "followup relabels the archived source")
    require(followup["compile_verdict"].startswith("NOT RUN") and
            followup["runtime_verdict"].startswith("NOT RUN"),
            "source followup must not claim compilation or live behavior")
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
    changed = followup["changed_previously_pinned_inputs"]
    added = followup["added_repository_inputs"]
    require(not set(changed) & set(added), "followup input both added and changed")
    # Every followup retains separate pending target acceptance. Task35/36 add
    # automatic updates and global privacy controls without a runtime verdict.
    require(set(followup["counterparts_changed"]) == {
        "graphics", "translations", "home", "sync", "firefox-suggest", "extension-types", "default-bookmarks",
        "rfp-controls", "addon-updates", "network-controls",
    },
            "followup counterpart scope changed")
    for path, item in (changed | added).items():
        require(item["sha256"] == coverage["repository_evidence"].get(path),
                f"followup input not pinned: {path}")
        reviewed_path = path
        correction = item.get("compiler_followup", {})
        if "original_reviewed_patch" in correction:
            reviewed_path = correction["original_reviewed_patch"]
            require(coverage["repository_evidence"].get(reviewed_path) == correction["previous_sha256"],
                    f"historical reviewed patch is not pinned: {path}")
            require(correction["evidence"] in coverage["repository_evidence"],
                    f"compiler correction is not pinned: {path}")
            overlay = json.loads((ROOT / correction["evidence"]).read_text())
            require(overlay["old_patch_sha256"] == correction["previous_sha256"] and
                    overlay["patch_sha256"] == correction.get("result_patch_sha256", item["sha256"]), f"compiler correction lineage differs: {path}")
            require(len(overlay["files"]) == 1, f"compiler correction scope differs: {path}")
            corrected = overlay["files"][0]
            body = str(Path(correction["evidence"]).parent / Path(corrected["path"]).name)
            require(coverage["repository_evidence"].get(body) == corrected["after_sha256"],
                    f"compiler correction body differs: {path}")
        if "historical_reviewed_patch" in item:
            reviewed_path = item["historical_reviewed_patch"]
        for start, end in item["reviewed_lines"]:
            require(1 <= start <= end <= len((ROOT / reviewed_path).read_text().splitlines()),
                    f"followup reviewed range invalid: {path}")
    for path, item in changed.items():
        require(item["previous_sha256"] != item["sha256"], f"unchanged followup input: {path}")
    check_global_controls(coverage, followup, source)
    spec = importlib.util.spec_from_file_location("fixture_lineage", HERE / "check-fixture-lineage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE, module.ROOT = HERE, ROOT
    module.check(coverage, followup)
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
