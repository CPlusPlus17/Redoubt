#!/usr/bin/env python3
"""Check that a Redoubt for Android build turns on uBlock Origin's cookie-notice lists.

    python3 scripts/android-cookie-banner-smoke.py --apk <redoubt.apk>
    python3 scripts/android-cookie-banner-smoke.py --tree <patched source tree>
    python3 scripts/android-cookie-banner-smoke.py --apk <redoubt.apk> --fetch

LW-M7-41. Firefox 156 removed the cookie banner service (157 has no
toolkit/components/cookiebanners and GeckoView's Cookie Banner Handling API is
gone), so the earlier version of this script -- an installed-release runner for
the packaged cookie-banner rules of LW-M7-13/22/23 -- had nothing left to test.
Its 153 text is in git history. Owner decision 2026-10-02: uBlock Origin's
cookie-notice lists replace the service, on by default and opt-out in uBO's own
settings. This script checks that chain in what the build actually ships:

  catalog   assets/uBOAssets.android.json is exactly what
            scripts/gen-ubo-assets-android.py derives from LibreWolf's
            assets/uBOAssets.json: the two cookie lists without "off", and an
            "assets.json" self-entry with no remote URL, so uBO never replaces
            the catalog it bootstrapped;
  pref      the librewolf.cfg the build packages (omni.ja
            defaults/autoconfig/librewolf.cfg in an APK, lw/librewolf.cfg in a
            tree) leaves librewolf.uBO.assetsBootstrapLocation at the
            commit-pinned URL gen-ubo-assets-android.py names -- the last call
            naming the pref wins, as autoconfig evaluates it;
  bundled   the uBO XPI the build packages knows both list keys, in uBO's
            "EasyList/uBO - Cookie Notices" group;
  migration the ExtensionStorageIDB.sys.mjs and Extension.sys.mjs the build
            packages (omni.ja modules/ in an APK, toolkit/components/extensions/
            in a tree) carry patches/android/ubo-cookie-lists-migration.patch:
            the hook, both list keys and its librewolf.uBO.cookieListsMigrated
            pref, and the startup branch that leaves uBO's storage backend
            unannounced while the migration is pending (without it the hook is
            never reached: upstream announces it for every migrated extension);
  hosted    (--fetch only, needs the network) the URL serves the same catalog.
            Until the pinned commit is on CPlusPlus17/Redoubt this is PENDING:
            uBO then falls back to the catalog inside its XPI, stock defaults.

What this does NOT prove: that a given device's uBO has the lists selected. uBO
reads the bootstrap location only on its first run, and a profile that ran a
153 beta keeps LibreWolf's catalog and its own selection; the migration patch
turns the lists on there once, on the first start of a build carrying it. On a
device, open uBO's dashboard, "Filter lists", "Annoyances": both "EasyList -
Cookie Notices" and "uBlock filters - Cookie Notices" are ticked on a fresh
install and after the first start of an upgraded profile.

Exit status: 0 all checks PASS, 1 a check FAILS, 3 nothing failed but a check
is PENDING.
"""

import argparse
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("gen_ubo_assets_android", ROOT / "scripts/gen-ubo-assets-android.py")
gen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen)

PREF = "librewolf.uBO.assetsBootstrapLocation"
CFG_IN_OMNI = "defaults/autoconfig/librewolf.cfg"
XPI_IN_APK = "assets/extensions/ublock_origin.xpi"
XPI_IN_TREE = "mobile/android/fenix/app/src/main/assets/extensions/ublock_origin.xpi"
CFG_IN_TREE = "lw/librewolf.cfg"
MIGRATION_IN_OMNI = "modules/ExtensionStorageIDB.sys.mjs"
MIGRATION_IN_TREE = "toolkit/components/extensions/ExtensionStorageIDB.sys.mjs"
MIGRATION_PREF = "librewolf.uBO.cookieListsMigrated"
STARTUP_IN_OMNI = "modules/Extension.sys.mjs"
STARTUP_IN_TREE = "toolkit/components/extensions/Extension.sys.mjs"
_STARTUP_BRANCH = re.compile(r"else\s+if\s*\(\s*lazy\.ExtensionStorageIDB\.redoubtMustSelectBackend\(\s*this\s*\)\s*\)")
# Whitespace-tolerant: the packager may reflow JavaScript.
_MIGRATION_HOOK = re.compile(r"\.then\(\s*\(\)\s*=>\s*redoubtMigrateUboCookieLists\(\s*extension\s*,\s*storagePrincipal\s*\)\s*\)")
PASS, FAIL, PENDING = "PASS", "FAIL", "PENDING"

# defaultPref("name", "value") / lockPref(...) / pref(...), spread over lines or
# not. Values here are plain string literals; anything else is reported, not guessed.
_CALL = re.compile(r'\b(defaultPref|lockPref|pref)\(\s*"([^"]+)"\s*,\s*("(?:[^"\\]|\\.)*"|[^)]*?)\s*\)', re.S)
# A string literal or a comment; comments are blanked, strings kept ("https://"
# is not a comment).
_TOKEN = re.compile(r'"(?:[^"\\\n]|\\.)*"|/\*.*?\*/|//[^\n]*', re.S)


def strip_comments(text):
    return _TOKEN.sub(lambda m: m.group(0) if m.group(0).startswith('"') else " ", text)


def effective_pref(cfg_text, name):
    """(verb, value) of the last call naming `name`, comments ignored; None if no call does."""
    found = None
    for verb, pref, raw in _CALL.findall(strip_comments(cfg_text)):
        if pref == name:
            found = (verb, json.loads(raw) if raw.startswith('"') else raw)
    return found


def read_apk(apk):
    with zipfile.ZipFile(apk) as archive:
        names = set(archive.namelist())
        omni = next((n for n in ("assets/omni.ja", "omni.ja") if n in names), None)
        if omni is None:
            raise ValueError(f"{apk} has no omni.ja")
        with zipfile.ZipFile(io.BytesIO(archive.read(omni))) as inner:
            cfg = inner.read(CFG_IN_OMNI).decode("utf-8")
            migration = (inner.read(MIGRATION_IN_OMNI).decode("utf-8"),
                         inner.read(STARTUP_IN_OMNI).decode("utf-8"))
        if XPI_IN_APK not in names:
            raise ValueError(f"{apk} has no {XPI_IN_APK}")
        return cfg, io.BytesIO(archive.read(XPI_IN_APK)), migration


def read_tree(tree):
    return (Path(tree, CFG_IN_TREE).read_text(encoding="utf-8"), Path(tree, XPI_IN_TREE),
            (Path(tree, MIGRATION_IN_TREE).read_text(encoding="utf-8"),
             Path(tree, STARTUP_IN_TREE).read_text(encoding="utf-8")))


def check_catalog(results):
    source = json.loads(gen.SOURCE.read_text(encoding="utf-8"))
    want = gen.render(gen.derive(source))
    have = gen.TARGET.read_text(encoding="utf-8") if gen.TARGET.exists() else ""
    if have != want:
        results.append((FAIL, "catalog", f"{gen.TARGET.name} is not what gen-ubo-assets-android.py derives"))
        return
    catalog = json.loads(have)
    on = [k for k in gen.COOKIE_LISTS if "off" not in catalog[k]]
    remote = gen.self_update_urls(catalog)
    ok = on == list(gen.COOKIE_LISTS) and not remote
    results.append((PASS if ok else FAIL, "catalog",
                    f"{gen.TARGET.name} selects {', '.join(on) or 'nothing'} by default; "
                    + (f"uBO would replace it from {', '.join(remote)}" if remote
                       else "no self-update URL, uBO keeps the bootstrapped catalog")))


def check_pref(results, cfg_text):
    found = effective_pref(cfg_text, PREF)
    if found is None:
        results.append((FAIL, "pref", f"the packaged librewolf.cfg never sets {PREF}"))
    elif found[1] != gen.ANDROID_CATALOG_URL:
        results.append((FAIL, "pref", f"{PREF} ends as {found[0]}({found[1]!r}), not the Android catalog"))
    else:
        results.append((PASS, "pref", f"{PREF} ends as {found[0]}({found[1]!r})"))


def check_bundled(results, xpi):
    try:
        titles = gen.check_xpi(xpi)
    except (gen.CatalogError, KeyError, zipfile.BadZipFile, OSError) as error:
        results.append((FAIL, "bundled", str(error)))
        return
    results.append((PASS, "bundled", "bundled uBO knows " + "; ".join(f"{k} ({t})" for k, t in titles.items())))


def check_migration(results, modules):
    module_text, startup_text = modules
    missing = [what for what, ok in (
        ("the selectBackend hook", _MIGRATION_HOOK.search(module_text)),
        ("redoubtMustSelectBackend", "redoubtMustSelectBackend(extension)" in module_text),
        ("Extension.sys.mjs's startup branch", _STARTUP_BRANCH.search(startup_text)),
        (f'"{MIGRATION_PREF}"', f'"{MIGRATION_PREF}"' in module_text),
        *((f'"{key}"', f'"{key}"' in module_text) for key in gen.COOKIE_LISTS),
    ) if not ok]
    if missing:
        results.append((FAIL, "migration", "the packaged modules lack " + ", ".join(missing)
                        + ": profiles that predate the Android catalog never get the lists"))
    else:
        results.append((PASS, "migration", "ExtensionStorageIDB.sys.mjs + Extension.sys.mjs turn the lists on once in "
                        f"older profiles ({MIGRATION_PREF})"))


def check_hosted(results, opener=urllib.request.urlopen):
    try:
        with opener(gen.ANDROID_CATALOG_URL, timeout=30) as response:
            served = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        results.append((PENDING, "hosted", f"{gen.ANDROID_CATALOG_URL} answers HTTP {error.code}; "
                        "uBO falls back to the catalog in its XPI until the pinned commit is on CPlusPlus17/Redoubt"))
        return
    except (urllib.error.URLError, OSError) as error:
        results.append((PENDING, "hosted", f"could not fetch {gen.ANDROID_CATALOG_URL}: {error}"))
        return
    same = json.loads(served) == json.loads(gen.TARGET.read_text(encoding="utf-8"))
    results.append((PASS if same else FAIL, "hosted",
                    "the hosted catalog matches the repository" if same else
                    "the hosted catalog differs from assets/uBOAssets.android.json"))


def main(argv=None, opener=urllib.request.urlopen):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--apk", type=Path, help="a built Redoubt APK")
    where.add_argument("--tree", type=Path, help="a patched source tree (scripts/librewolf-patches.py --targets=android)")
    parser.add_argument("--fetch", action="store_true", help="also fetch the hosted catalog")
    parser.add_argument("--json", type=Path, help="write the results here as JSON")
    args = parser.parse_args(argv)

    results = []
    check_catalog(results)
    try:
        cfg_text, xpi, migration = read_apk(args.apk) if args.apk else read_tree(args.tree)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as error:
        results.append((FAIL, "build", f"cannot read the build: {error}"))
    else:
        check_pref(results, cfg_text)
        check_bundled(results, xpi)
        check_migration(results, migration)
    if args.fetch:
        check_hosted(results, opener)

    for status, name, detail in results:
        print(f"{status:7} {name:8} {detail}")
    if args.json:
        args.json.write_text(json.dumps([{"status": s, "check": n, "detail": d} for s, n, d in results], indent=2) + "\n")
    statuses = {s for s, _, _ in results}
    return 1 if FAIL in statuses else 3 if PENDING in statuses else 0


if __name__ == "__main__":
    sys.exit(main())
