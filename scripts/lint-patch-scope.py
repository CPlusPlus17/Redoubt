#!/usr/bin/env python3
"""File-level patch-scope linter (LW-M0-08).

Reads assets/patches/{common,desktop,android}.txt, parses the ``--- a/x`` /
``+++ b/x`` headers of every patch listed there, and asserts:

  * common.txt   touches no desktop-only file and no Android-only file
  * desktop.txt  touches no Android-only file (in particular no ``mobile/``)
  * android.txt  touches no desktop-only file (in particular no ``browser/``)

WHY THE RULES ARE FILE-LEVEL AND NOT PREFIX-LEVEL
-------------------------------------------------
This is landmine L3 in docs/android/AGENTS.md, and it cuts both ways:

  * ``patches/ui-patches/neterror.patch`` looks like pure ``toolkit/`` and is
    not - it edits ``toolkit/themes/shared/desktop-jar.inc.mn``.  The desktop
    boundary is in the *filename*, inside a shared directory.  A ``toolkit/``
    prefix rule waves it through.
  * ``devtools/`` must be ALLOWED in common, because
    ``devtools/moz.build:11-16`` adds ``platform``/``server``/``shared``/
    ``startup`` to DIRS with no Android guard.  A ``devtools/`` deny rule
    would wrongly reject devtools-bypass.patch.
  * ...but ``devtools/client/`` inside that same allowed tree is desktop-only
    (``devtools/moz.build:5-8`` gates it on ``MOZ_DEVTOOLS == "all"``).

So scope is decided by matching individual files against explicit deny lists
with explicit exceptions, both carried as data below.  Every entry cites the
build file in the extracted Firefox tree that makes it true; if you add one,
cite yours the same way, or it cannot be reviewed.

Usage:
    python3 scripts/lint-patch-scope.py [--root DIR] [-v]

Exit codes:  0 = clean, 1 = scope violations found, 2 = could not run.
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
import textwrap
from pathlib import Path
from typing import Iterable, NamedTuple


# --------------------------------------------------------------------------
# Rule data
# --------------------------------------------------------------------------

class Rule(NamedTuple):
    """One scope rule.

    kind:
      "dir"  - path prefix, matched at a directory boundary ("browser/")
      "name" - glob against the BASENAME only; this is the file-level case
      "path" - glob against the whole path
    why: justification, with the tree file that proves it.
    """

    kind: str
    pattern: str
    why: str


class RuleSet(NamedTuple):
    label: str
    deny: tuple[Rule, ...]
    allow: tuple[Rule, ...]  # checked first; an allow match wins over any deny


# Line numbers below refer to firefox-153.0.4/ as extracted by scripts/mozfetch.sh.

DESKTOP_ONLY = RuleSet(
    label="desktop-only",
    deny=(
        Rule(
            "dir", "browser/",
            "Desktop chrome. browser/app.mozbuild:11 is what pulls /browser "
            "into the build; mobile/android/app.mozbuild never does. Nothing "
            "under browser/ exists in an Android build.",
        ),
        Rule(
            "dir", "devtools/client/",
            "devtools/moz.build:5-8 adds client/ only when MOZ_DEVTOOLS == "
            "'all', and browser/moz.configure:17 is the only imply_option for "
            "that. Android keeps the toolkit/moz.configure:41-46 default "
            "'server', so devtools/client/ is not traversed. Note this is a "
            "carve-out INSIDE an otherwise-common tree - see the allow list.",
        ),
        Rule(
            "name", "*desktop*",
            "LANDMINE L3. toolkit/themes/shared/desktop-jar.inc.mn sits in a "
            "'shared' directory and is desktop-only: it is included from "
            "toolkit/themes/osx/global/jar.mn:5 and "
            "toolkit/themes/shared/desktop-non-mac.jar.inc.mn:11, while "
            "toolkit/themes/moz.build:16-26 routes MOZ_BUILD_APP=mobile/android "
            "to toolkit/themes/mobile. Only the filename says so.",
        ),
        Rule(
            "name", "*.mm",
            "Objective-C++. Only compiled for MOZ_WIDGET_TOOLKIT in "
            "{cocoa, uikit} - e.g. toolkit/xre/moz.build:71-84 guards "
            "nsCommandLineServiceMac.mm behind 'cocoa'. Never built on Android.",
        ),
        Rule(
            "path", "*/macbuild/*",
            "macOS .app bundle scaffolding (Info.plist.in, MacOS-files.in). "
            "Consumed by the macOS packaging step only.",
        ),
        Rule(
            "name", "*.nsh",
            "NSIS installer script. Windows packaging only "
            "(browser/installer/windows/nsis/).",
        ),
        Rule(
            "name", "*.exe.manifest",
            "Windows side-by-side application manifest. Windows only.",
        ),
        Rule(
            "name", "AppxManifest*",
            "MSIX/Appx packaging manifest. Windows Store packaging only. "
            "msix.patch's python/mozbuild hunks were once believed common; "
            "LW-M1-05 disproved that by AST-comparing import-time state - "
            "repackaging/msix.py is only imported from inside repackage_msix(), "
            "and the one import-time delta in mach_commands.py is a "
            "@CommandArgument default that decorators merely store. The whole "
            "patch is desktop-only.",
        ),
        Rule(
            "dir", "widget/cocoa/",
            "widget/moz.build:59 gates widget/cocoa on toolkit == 'cocoa'.",
        ),
        Rule(
            "dir", "widget/gtk/",
            "widget/moz.build:72 gates widget/gtk on toolkit == 'gtk'.",
        ),
        Rule(
            "dir", "widget/windows/",
            "widget/moz.build:78 gates widget/windows on toolkit == 'windows'.",
        ),
        Rule(
            "dir", "toolkit/components/remote/",
            "The single-instance remote-control component. "
            "toolkit/components/remote/moz.build:25-58 compiles every backend "
            "under a MOZ_WIDGET_TOOLKIT guard (gtk/windows/cocoa); 'android' "
            "matches none of them. Denied as a directory with the "
            "unconditionally-built files allow-listed below, so a new "
            "toolkit-gated file added upstream is flagged by default rather "
            "than by omission.",
        ),
    ),
    allow=(
        Rule(
            "dir", "devtools/server/",
            "devtools/moz.build:11-16 adds server/ to DIRS unconditionally - "
            "the devtools server ships on Android. This is the explicit "
            "counterweight to the devtools/client/ deny above.",
        ),
        Rule(
            "dir", "devtools/shared/",
            "devtools/moz.build:11-16 adds shared/ to DIRS unconditionally.",
        ),
        Rule(
            "dir", "devtools/platform/",
            "devtools/moz.build:11-16 adds platform/ to DIRS unconditionally.",
        ),
        Rule(
            "dir", "devtools/startup/",
            "devtools/moz.build:11-16 adds startup/ to DIRS unconditionally "
            "(its own moz.build:8 gates only part of its contents).",
        ),
        Rule(
            "path", "toolkit/components/remote/nsRemoteService.cpp",
            "toolkit/components/remote/moz.build:8-10 - SOURCES, no toolkit "
            "guard. Built on Android.",
        ),
        Rule(
            "path", "toolkit/components/remote/nsIRemoteService.idl",
            "toolkit/components/remote/moz.build:18-20 - XPIDL_SOURCES, no "
            "toolkit guard.",
        ),
        Rule(
            "path", "toolkit/components/remote/components.conf",
            "toolkit/components/remote/moz.build:14-16 - XPCOM_MANIFESTS, no "
            "toolkit guard.",
        ),
        Rule(
            "path", "toolkit/components/remote/moz.build",
            "The build file itself is read on every platform.",
        ),
    ),
)

ANDROID_ONLY = RuleSet(
    label="android-only",
    deny=(
        Rule(
            "dir", "mobile/",
            "GeckoView, Fenix and Focus. browser/app.mozbuild:7-11 never adds "
            "mobile/; only mobile/android/app.mozbuild does. Absent from a "
            "desktop build.",
        ),
        Rule(
            "dir", "toolkit/themes/mobile/",
            "toolkit/themes/moz.build:16-26 selects themes/mobile only when "
            "MOZ_BUILD_APP == 'mobile/android'; desktop gets osx/linux/windows.",
        ),
        Rule(
            "dir", "widget/android/",
            "widget/moz.build:92 gates widget/android on toolkit in "
            "('android', 'uikit').",
        ),
    ),
    allow=(),
)


# Which rule sets apply to which list. This is the whole contract of the task:
#   common  -> must be buildable on BOTH, so both deny sets apply
#   desktop -> must not reach for Android-only files
#   android -> must not reach for desktop-only files
LIST_RULES: dict[str, tuple[RuleSet, ...]] = {
    "common": (DESKTOP_ONLY, ANDROID_ONLY),
    "desktop": (ANDROID_ONLY,),
    "android": (DESKTOP_ONLY,),
}


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

# Sentinels that a unified diff uses for "this side of the hunk has no file".
# Treating these as real paths is a real bug that shipped in an earlier
# throwaway classifier: a naive r"^(---|\+\+\+) [ab]?/?(\S+)" turns
# "--- /dev/null" into "dev/null", which matches no deny rule and is silently
# accepted as common scope. So the sentinel check happens on the RAW token,
# before any a/ or b/ prefix is stripped.
DIFF_NULL_PATHS = frozenset({"/dev/null", "dev/null", "nul", "NUL"})


class ParseError(Exception):
    pass


def read_patch_list(path: Path) -> list[str]:
    """Return the patch paths in a list file, skipping blanks and comments."""
    entries: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParseError(f"cannot read patch list {path}: {exc}") from exc
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if len(line.split()) != 1:
            raise ParseError(
                f"{path}:{lineno}: patch path contains whitespace: {line!r}"
            )
        entries.append(line)
    return entries


def patch_paths(patch: Path) -> list[str]:
    """Return the tree-relative files a patch touches, in first-seen order.

    Handles ``--- a/x`` / ``+++ b/x``, bare ``--- x``, git-style trailing
    tab+timestamp, and the /dev/null creation/deletion sentinel.
    """
    seen: dict[str, None] = {}
    saw_header = False
    try:
        text = patch.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ParseError(f"cannot read patch {patch}: {exc}") from exc

    for raw in text.splitlines():
        if raw.startswith("--- "):
            token = raw[4:]
        elif raw.startswith("+++ "):
            token = raw[4:]
        else:
            continue
        saw_header = True
        # Strip a trailing tab-separated timestamp, then surrounding space.
        token = token.split("\t", 1)[0].strip()
        if not token:
            continue
        # Sentinel check BEFORE prefix stripping - see DIFF_NULL_PATHS.
        if token in DIFF_NULL_PATHS:
            continue
        if token.startswith(("a/", "b/")):
            token = token[2:]
        token = token.lstrip("./")
        if not token or token in DIFF_NULL_PATHS:
            continue
        seen.setdefault(token, None)

    if not saw_header:
        raise ParseError(
            f"{patch}: no '--- ' / '+++ ' headers found - not a unified diff, "
            "or a format this linter does not understand. Refusing to report "
            "it as clean."
        )
    return list(seen)


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

def rule_matches(rule: Rule, path: str) -> bool:
    if rule.kind == "dir":
        prefix = rule.pattern if rule.pattern.endswith("/") else rule.pattern + "/"
        return path == prefix.rstrip("/") or path.startswith(prefix)
    if rule.kind == "name":
        return fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], rule.pattern)
    if rule.kind == "path":
        return fnmatch.fnmatchcase(path, rule.pattern)
    raise ParseError(f"unknown rule kind {rule.kind!r}")


def classify(path: str, ruleset: RuleSet) -> Rule | None:
    """Return the deny rule this path trips, or None (allow wins over deny)."""
    for allow in ruleset.allow:
        if rule_matches(allow, path):
            return None
    for deny in ruleset.deny:
        if rule_matches(deny, path):
            return deny
    return None


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

class Violation(NamedTuple):
    list_name: str
    patch: str
    path: str
    label: str
    rule: Rule


def lint(root: Path, verbose: bool = False) -> tuple[list[Violation], int]:
    violations: list[Violation] = []
    checked = 0
    for list_name, rulesets in LIST_RULES.items():
        list_file = root / "assets" / "patches" / f"{list_name}.txt"
        if not list_file.is_file():
            raise ParseError(f"missing patch list: {list_file}")
        for entry in read_patch_list(list_file):
            patch = root / entry
            if not patch.is_file():
                raise ParseError(
                    f"assets/patches/{list_name}.txt lists {entry}, "
                    f"which does not exist at {patch}"
                )
            paths = patch_paths(patch)
            checked += 1
            if verbose:
                print(f"  {list_name:<7} {entry} ({len(paths)} files)")
            for path in paths:
                if verbose:
                    print(f"            {path}")
                for ruleset in rulesets:
                    hit = classify(path, ruleset)
                    if hit is not None:
                        violations.append(
                            Violation(list_name, entry, path, ruleset.label, hit)
                        )
    return violations, checked


def wrap(text: str, indent: str, width: int = 78) -> Iterable[str]:
    return textwrap.wrap(
        text, width=width, initial_indent=indent, subsequent_indent=indent
    )


def report(violations: list[Violation], checked: int) -> None:
    print(
        f"lint-patch-scope: {len(violations)} scope violation(s) "
        f"across {checked} patch file(s)\n"
    )
    by_list: dict[str, list[Violation]] = {}
    for v in violations:
        by_list.setdefault(v.list_name, []).append(v)
    for list_name, group in by_list.items():
        print(f"assets/patches/{list_name}.txt")
        by_patch: dict[str, list[Violation]] = {}
        for v in group:
            by_patch.setdefault(v.patch, []).append(v)
        for patch, hits in by_patch.items():
            print(f"  {patch}")
            for v in hits:
                print(f"    {v.path}")
                print(f"      -> {v.label} [{v.rule.kind} {v.rule.pattern!r}]")
                for line in wrap(v.rule.why, "         "):
                    print(line)
        print()
    print(
        "A patch may only sit in a list whose targets build every file it "
        "touches.\nMove it to the right list, or split it (see the straddler "
        "table in\ndocs/android/PATCH-SCOPE.md), or - if the file really is "
        "built on the target -\nadd an allow entry to this script with the "
        "moz.build line that proves it."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root holding assets/patches/ and patches/ "
        "(default: the repo this script lives in)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="print every patch and every path it touches",
    )
    args = parser.parse_args(argv)

    try:
        violations, checked = lint(args.root.resolve(), args.verbose)
    except ParseError as exc:
        print(f"lint-patch-scope: error: {exc}", file=sys.stderr)
        return 2

    if violations:
        report(violations, checked)
        return 1

    print(f"lint-patch-scope: OK - {checked} patch file(s), no scope violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
