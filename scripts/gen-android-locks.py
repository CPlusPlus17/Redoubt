#!/usr/bin/env python3
"""
gen-android-locks.py — generate the must-lock pref list from the Fenix sources.

Owner: LW-M3-04.

Any pref Fenix writes at runtime (stage 5b, GeckoView:SetDefaultPrefs) must be
locked in autoconfig, or our value is transient.  This script parses the two
Java files that declare the Pref fields Fenix commits, plus the constructed
SafeBrowsingProvider names that are invisible to a literal grep, and emits the
sorted must-lock list.

Usage:
    python3 scripts/gen-android-locks.py            # write the list to docs/android/must-lock.txt
    python3 scripts/gen-android-locks.py --check    # regenerate, diff against stored copy, exit 0 on no diff
    python3 scripts/gen-android-locks.py --stdout   # print to stdout instead of writing

Tree resolution follows board.py's convention: honour LW_TREE (relative paths
resolved against the repo root), otherwise glob for a single extracted tree.
Error on ambiguity rather than picking the first match.
"""

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "docs" / "android" / "must-lock.txt"

GV_PREF_DECLARERS = (
    "mobile/android/geckoview/src/main/java/org/mozilla/geckoview/GeckoRuntimeSettings.java",
    "mobile/android/geckoview/src/main/java/org/mozilla/geckoview/ContentBlocking.java",
)


def resolve_tree():
    """Resolve the extracted Firefox tree, following board.py's convention."""
    override = os.environ.get("LW_TREE")
    if override:
        cands = [Path(override) if Path(override).is_absolute() else REPO / override]
    else:
        cands = sorted(set(
            p.parent for pattern in ("firefox-*/mobile", "librewolf-*/mobile")
            for p in REPO.glob(pattern)
        ))
    if not cands:
        print("error: no extracted Firefox tree found", file=sys.stderr)
        print("       (extract one, or set LW_TREE=/path/to/firefox-<version>)", file=sys.stderr)
        sys.exit(2)
    if len(cands) > 1:
        print("error: more than one extracted Firefox tree — refusing to guess:", file=sys.stderr)
        for c in cands:
            print(f"         {c}", file=sys.stderr)
        print("       set LW_TREE=<one of these> and re-run", file=sys.stderr)
        sys.exit(2)
    tree = cands[0]
    if not (tree / "mobile").is_dir():
        print(f"error: {tree} has no mobile/ directory", file=sys.stderr)
        sys.exit(2)
    return tree


def extract_literal_prefs(java_text):
    """Extract all literal pref names from new Pref<>(...) and new PrefWithoutDefault<>(...).

    Returns (pref_names, pref_without_default_names)."""
    # Pattern: new Pref<Type>("name", default) or new Pref<>("name", default)
    # Also: new Pref<Type>(\n  "name", ...) — the name may be on the next line
    # Also: new PrefWithoutDefault<Type>("name") or new PrefWithoutDefault<>("name")

    pref_names = set()
    pwd_names = set()

    # Match new Pref<...>( "literal_string", ...
    # The name is the first string literal argument.
    # Handle both: new Pref<>("name", val) and new Pref<Type>(\n  "name", val)
    for m in re.finditer(
        r'new\s+Pref<[^>]*>\s*\(\s*"([^"]+)"',
        java_text
    ):
        pref_names.add(m.group(1))

    # Match new PrefWithoutDefault<...>( "literal_string"
    for m in re.finditer(
        r'new\s+PrefWithoutDefault<[^>]*>\s*\(\s*"([^"]+)"',
        java_text
    ):
        pwd_names.add(m.group(1))

    return pref_names, pwd_names


def extract_sb_provider_names(java_text):
    """Extract the constructed SafeBrowsingProvider pref names.

    Finds:
      1. The ROOT constant
      2. The suffix patterns (ROOT + mName + ".suffix")
      3. The default provider names (from withName("...") in DEFAULT_PROVIDERS)

    Returns a set of fully-constructed pref names, plus the (root, suffixes, providers)
    tuple so the caller can emit the rule rather than just the expansion."""
    # ROOT constant
    m = re.search(r'private\s+static\s+final\s+String\s+ROOT\s*=\s*"([^"]+)"', java_text)
    if not m:
        raise RuntimeError("Could not find ROOT constant in ContentBlocking.java")
    root = m.group(1)

    # Suffixes: new Pref<>(ROOT + mName + ".suffix", ...)
    suffixes = []
    for m in re.finditer(r'new\s+Pref<[^>]*>\s*\(\s*ROOT\s*\+\s*mName\s*\+\s*"(\.[^"]+)"', java_text):
        suffixes.append(m.group(1))
    if not suffixes:
        raise RuntimeError("Could not find SafeBrowsingProvider suffix patterns")

    # Default provider names: from the static field definitions at the top of the class
    # public static final SafeBrowsingProvider GOOGLE_*_PROVIDER = SafeBrowsingProvider.withName("name")
    providers = set()
    for m in re.finditer(
        r'public\s+static\s+final\s+SafeBrowsingProvider\s+\w+\s*=\s*\n?\s*SafeBrowsingProvider\.withName\("([^"]+)"',
        java_text
    ):
        providers.add(m.group(1))
    if not providers:
        raise RuntimeError("Could not find default SafeBrowsingProvider names")

    # Construct the full names
    names = set()
    for prov in providers:
        for suffix in suffixes:
            names.add(root + prov + suffix)

    return names, root, suffixes, sorted(providers)


def generate(tree):
    """Parse both Java files and return the full must-lock list (sorted)."""
    all_names = set()
    diagnostics = {}

    for rel in GV_PREF_DECLARERS:
        path = tree / rel
        if not path.is_file():
            raise RuntimeError(f"Missing file: {path}")
        text = path.read_text(encoding="utf-8")

        pref_names, pwd_names = extract_literal_prefs(text)
        all_names.update(pref_names)
        all_names.update(pwd_names)
        diagnostics[rel] = {
            "Pref": sorted(pref_names),
            "PrefWithoutDefault": sorted(pwd_names),
        }

        # SafeBrowsingProvider constructed names (only in ContentBlocking.java)
        if "ContentBlocking.java" in rel:
            sb_names, root, suffixes, providers = extract_sb_provider_names(text)
            all_names.update(sb_names)
            diagnostics[rel]["SafeBrowsingProvider"] = {
                "root": root,
                "suffixes": suffixes,
                "providers": providers,
                "expanded": sorted(sb_names),
            }

    return sorted(all_names), diagnostics


def main():
    args = sys.argv[1:]
    check = "--check" in args
    stdout = "--stdout" in args

    tree = resolve_tree()
    names, diag = generate(tree)

    # Cross-check counts against the user's stated numbers
    total_pref = sum(len(d["Pref"]) for d in diag.values())
    total_pwd = sum(len(d["PrefWithoutDefault"]) for d in diag.values())
    total_sb = sum(len(d.get("SafeBrowsingProvider", {}).get("expanded", [])) for d in diag.values())

    print(f"# gen-android-locks: parsed {tree.name}", file=sys.stderr)
    print(f"#   new Pref<>:            {total_pref} names", file=sys.stderr)
    print(f"#   new PrefWithoutDefault: {total_pwd} names", file=sys.stderr)
    if total_sb:
        for rel, d in diag.items():
            if "SafeBrowsingProvider" in d:
                sb = d["SafeBrowsingProvider"]
                print(f"#   SafeBrowsingProvider:  {len(sb['expanded'])} constructed names "
                      f"({len(sb['providers'])} providers x {len(sb['suffixes'])} suffixes)",
                      file=sys.stderr)
    print(f"#   TOTAL:                 {len(names)} unique pref names", file=sys.stderr)

    if stdout:
        for name in names:
            print(name)
        return 0

    if check:
        if not OUTPUT.is_file():
            print(f"error: {OUTPUT} does not exist — run without --check first", file=sys.stderr)
            return 1
        stored = OUTPUT.read_text(encoding="utf-8").strip().splitlines()
        stored = [l.strip() for l in stored if l.strip() and not l.startswith("#")]
        if stored == names:
            print(f"ok: {len(names)} must-lock prefs unchanged", file=sys.stderr)
            return 0
        else:
            added = set(names) - set(stored)
            removed = set(stored) - set(names)
            print(f"error: must-lock list has changed ({len(added)} added, {len(removed)} removed)",
                  file=sys.stderr)
            if added:
                print("  added:", file=sys.stderr)
                for n in sorted(added):
                    print(f"    + {n}", file=sys.stderr)
            if removed:
                print("  removed:", file=sys.stderr)
                for n in sorted(removed):
                    print(f"    - {n}", file=sys.stderr)
            return 1

    # Default: write the file
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("# Must-lock pref list — generated by scripts/gen-android-locks.py (LW-M3-04)\n")
        f.write("# Do not edit by hand. Regenerate: python3 scripts/gen-android-locks.py\n")
        f.write("# Verify unchanged: python3 scripts/gen-android-locks.py --check\n")
        f.write(f"# Source: {tree.name}\n")
        f.write(f"# Counts: {total_pref} Pref<> + {total_pwd} PrefWithoutDefault<>"
                f"{' + ' + str(total_sb) + ' SafeBrowsingProvider' if total_sb else ''}"
                f" = {len(names)} total\n\n")
        for name in names:
            f.write(name + "\n")
    print(f"wrote {len(names)} must-lock prefs to {OUTPUT.relative_to(REPO)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
