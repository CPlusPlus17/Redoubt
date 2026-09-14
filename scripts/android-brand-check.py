#!/usr/bin/env python3
"""LW-M4-07 gate: every Firefox brand image in the tree has a Redoubt replacement.

Owner: LW-M4-07. Reads for: docs/android/PATCH-SCOPE.md.

WHY THIS EXISTS. On 2026-09-08 a fully signed beta candidate shipped the Firefox
flame as its home-screen wordmark, the word "Firefox" beside it, and eight
user-selectable Firefox app icons -- past every gate this project owns. None of
them looks at images: --check-strings reads the string table and the rendered
settings text and says so in its own output; --check-scope, check-patch-order and
check-patchfail care whether patches apply, not what they contain.

WHAT IT CHECKS, and why at source level rather than against an APK: aapt2
re-encodes webp on the way in (measured: 14,428 bytes becomes 14,784), so a byte
comparison against the shipped resource is not available. More usefully, the
failure worth catching is an upstream REBASE ADDING brand art nobody noticed --
and that is visible in the tree, before a build, without a device.

So: every drawable whose name marks it as brand art must have a replacement in
assets/android-brand/. A new Firefox logo arriving upstream fails this
immediately, with the path to regenerate.

This does NOT verify the replacements look right -- that is a human reading the
diff, and the generator prints what it wrote.

EXIT CODES
  0  every brand image in the tree is covered
  1  at least one is not -- a real gap, the gate going red
  2  could not run (no tree, no replacement set)
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPLACEMENTS = REPO / "assets" / "android-brand"

# Names that mark a file as brand art. Deliberately broader than the set that
# exists today: the point is to catch what upstream adds next.
BRAND = re.compile(
    r"(firefox|fenix_(?:logo|search_widget)|wordmark|"
    r"ic_launcher_foreground_|mozac_ic_logo_firefox)",
    re.IGNORECASE,
)
# Brand-SHAPED names that are not Mozilla marks. Each is here because it was
# looked at, not because the name seemed harmless:
#   cc_logo_*        payment-network marks (Visa, JCB, ...) -- not ours to change
#   logo_chrome/safari/google, google_lens
#                    other browsers' marks, shown in import and search UI, where
#                    replacing them with Redoubt's would be a lie
#   fenix_error_*    a magnifying glass over clouds. "fenix" is the codename in
#                    the filename; the artwork carries no mark. Rendered and
#                    looked at on 2026-09-13 rather than guessed from the name.
EXEMPT = re.compile(
    r"(cc_logo|logo_chrome|logo_safari|logo_google|google_lens|fenix_error)",
    re.IGNORECASE,
)
# Modules this project actually ships. focus-android is Firefox Focus, a separate
# app we do not build -- its wordmarks never reach our APK, and rewriting them
# would be noise in every rebase.
SHIPPED_MODULES = ("fenix", "android-components")
IMAGE_SUFFIXES = {".xml", ".webp", ".png", ".jpg", ".svg"}



# Gecko's branding is a separate layer from Fenix's resources and a separate
# failure: assets/mozconfig.android builds --with-branding=mobile/android/
# branding/unofficial, whose upstream contents name the product "Fennec", the
# vendor "Mozilla" and the family "Firefox", and ship a fennec-fox logo. Those
# are compiled into omni.ja and travel in the APK.
#
# Checked by VALUE, after patching, rather than by file coverage: the question
# is not "did we write a file here" but "does the artifact still say Fennec".
GECKO_BRANDING = Path("branding") / "unofficial"
MOZILLA_MARKS = re.compile(r"\b(fennec|mozilla|firefox)\b", re.IGNORECASE)


def check_gecko_branding(root: Path) -> list:
    """Brand VALUES in the Gecko branding directory, with comments ignored."""
    problems = []
    base = root / GECKO_BRANDING
    if not base.is_dir():
        return ["mobile/android/%s is missing -- upstream moved Gecko's Android "
                "branding; regenerate the replacement set" % GECKO_BRANDING]

    text_files = {
        "locales/en-US/brand.ftl": r"^\s*-?[A-Za-z][A-Za-z0-9_-]*\s*=\s*(.+)$",
        "locales/en-US/brand.properties": r"^\s*[A-Za-z][A-Za-z0-9_]*\s*=\s*(.+)$",
        "configure.sh": r'^\s*MOZ_APP_DISPLAYNAME\s*=\s*"?([^"]+)"?\s*$',
    }
    for rel, pattern in text_files.items():
        path = base / rel
        if not path.exists():
            problems.append("%s/%s is missing" % (GECKO_BRANDING, rel))
            continue
        rx = re.compile(pattern)
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            m = rx.match(line)
            if m and MOZILLA_MARKS.search(m.group(1)):
                problems.append("%s/%s:%d still a Mozilla mark: %s"
                                % (GECKO_BRANDING, rel, lineno, line.strip()))

    for name in ("about.png", "favicon32.png", "favicon64.png"):
        if not (base / "content" / name).exists():
            problems.append("%s/content/%s is missing" % (GECKO_BRANDING, name))
        elif not (REPLACEMENTS / GECKO_BRANDING / "content" / name).exists():
            problems.append("%s/content/%s has no Redoubt replacement checked in"
                            % (GECKO_BRANDING, name))
    return problems


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: android-brand-check.py <extracted-tree>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve() / "mobile" / "android"
    if not root.is_dir():
        print("error: no mobile/android under %s -- extract a tree first "
              "(`make dir TARGETS=android`)" % sys.argv[1], file=sys.stderr)
        return 2
    if not REPLACEMENTS.is_dir():
        print("error: %s is missing -- the replacement set IS the gate"
              % REPLACEMENTS.relative_to(REPO), file=sys.stderr)
        return 2

    covered = {str(p.relative_to(REPLACEMENTS))
               for p in REPLACEMENTS.rglob("*") if p.is_file()}

    found, uncovered = 0, []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in IMAGE_SUFFIXES:
            continue
        rel = path.relative_to(root)
        if rel.parts[0] not in SHIPPED_MODULES:
            continue
        parent = path.parent.name
        if not (parent.startswith("drawable") or parent.startswith("mipmap")):
            continue
        if EXEMPT.search(path.stem) or not BRAND.search(path.stem):
            continue
        found += 1
        if str(path.relative_to(root)) not in covered:
            uncovered.append(path.relative_to(root))

    print("# %d brand image(s) in the tree, %d replacement(s) checked in"
          % (found, len(covered)))
    if uncovered:
        print("error: %d brand image(s) have NO Redoubt replacement:" % len(uncovered))
        for p in uncovered[:20]:
            print("         %s" % p)
        if len(uncovered) > 20:
            print("         ... and %d more" % (len(uncovered) - 20))
        print("       Regenerate the set against this tree and review the result:")
        print("         python3 scripts/gen-android-brand.py %s" % sys.argv[1])
        print("       Shipping without this is how the 2026-09-08 candidate came to")
        print("       carry the Firefox flame on its home screen.")
        return 1

    stale = sorted(covered - {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()})
    if stale:
        print("warn:  %d replacement(s) no longer match a file in the tree "
              "(upstream removed or renamed them):" % len(stale))
        for p in stale[:10]:
            print("         %s" % p)
        print("       Harmless to ship -- the copy step asserts destinations exist and")
        print("       would have failed first -- but regenerate to keep the set honest.")

    gecko = check_gecko_branding(root)
    if gecko:
        print("error: Gecko's branding layer still carries Mozilla marks:")
        for g in gecko:
            print("         %s" % g)
        print("       These compile into omni.ja and ship in the APK, where")
        print("       --check-strings cannot see them. Regenerate:")
        print("         python3 scripts/gen-android-brand.py %s" % sys.argv[1])
        return 1
    print("ok: %d brand image(s) replaced, and Gecko's branding names no Mozilla mark"
          % found)
    return 0


if __name__ == "__main__":
    sys.exit(main())
