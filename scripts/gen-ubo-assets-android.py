#!/usr/bin/env python3
"""Derive Redoubt for Android's uBlock Origin filter-list catalog.

    python3 scripts/gen-ubo-assets-android.py           # rewrite the catalog
    python3 scripts/gen-ubo-assets-android.py --check   # exit 1 if it is stale
    python3 scripts/gen-ubo-assets-android.py --check --xpi ublock_origin.xpi

Owner decision 2026-10-02 (docs/android/TRACK.md): Firefox 156 removed the
cookie banner service, so Android turns on uBlock Origin's cookie-notice lists
instead -- by default, and opt-out in uBO's own "Filter lists" pane.

uBO selects a list on first run when its catalog entry (assets.json) has no
"off" key; that is how LibreWolf's scripts/update-ubo-assets.sh enables
curben-phishing and adguard-spyware-url. assets/uBOAssets.json is LibreWolf's
catalog and keeps the cookie lists off, so this script writes
assets/uBOAssets.android.json from it with exactly three differences:

  * no "off" on the two members of uBO's "EasyList/uBO - Cookie Notices"
    group, fanboy-cookiemonster ("EasyList - Cookie Notices") and
    ublock-cookies-easylist ("uBlock filters - Cookie Notices");
  * the "assets.json" entry's contentURL is ANDROID_CATALOG_URL, the URL
    settings/android.cfg gives librewolf.uBO.assetsBootstrapLocation, so uBO's
    periodic catalog refresh keeps reading this file. If it pointed back at
    LibreWolf's catalog, the refresh would see the two lists stop being
    defaults and uBO would remove them from the selection.

--xpi checks that both keys, and their group, exist in the assets.json inside
the uBO XPI the build bundles (assets/ubo-extension.json pins it): a key uBO
does not know is a list nobody gets.
"""

import argparse
import json
from pathlib import Path
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/uBOAssets.json"
TARGET = ROOT / "assets/uBOAssets.android.json"
ANDROID_CATALOG_URL = "https://raw.githubusercontent.com/CPlusPlus17/Redoubt/main/assets/uBOAssets.android.json"
COOKIE_GROUP = "EasyList/uBO – Cookie Notices"
COOKIE_LISTS = ("fanboy-cookiemonster", "ublock-cookies-easylist")


class CatalogError(ValueError):
    """The source catalog or the bundled uBO does not have what we enable."""


def derive(catalog):
    """Return the Android catalog for LibreWolf's `catalog` (a parsed dict)."""
    out = json.loads(json.dumps(catalog))
    if not isinstance(out.get("assets.json"), dict):
        raise CatalogError("catalog has no assets.json entry")
    out["assets.json"]["contentURL"] = ANDROID_CATALOG_URL
    for key in COOKIE_LISTS:
        entry = out.get(key)
        if not isinstance(entry, dict) or entry.get("content") != "filters":
            raise CatalogError(f"catalog has no filter list {key!r}")
        if entry.get("parent") != COOKIE_GROUP:
            raise CatalogError(f"{key!r} is no longer in uBO's {COOKIE_GROUP!r} group")
        entry.pop("off", None)
    return out


def render(catalog):
    return json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"


def check_xpi(path):
    """Every enabled key exists, as a filter list in the cookie group, in the XPI's own catalog."""
    with zipfile.ZipFile(path) as archive:
        bundled = json.loads(archive.read("assets/assets.json"))
    for key in COOKIE_LISTS:
        entry = bundled.get(key)
        if not isinstance(entry, dict) or entry.get("content") != "filters":
            raise CatalogError(f"the bundled uBO ({path}) does not know the filter list {key!r}")
        if entry.get("parent") != COOKIE_GROUP:
            raise CatalogError(f"the bundled uBO puts {key!r} outside {COOKIE_GROUP!r}")
    return {key: bundled[key]["title"] for key in COOKIE_LISTS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="do not write; fail if the catalog is stale")
    parser.add_argument("--xpi", type=Path, help="also check the keys against this uBO XPI")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--target", type=Path, default=TARGET)
    args = parser.parse_args(argv)
    try:
        text = render(derive(json.loads(args.source.read_text(encoding="utf-8"))))
        if args.xpi:
            for key, title in check_xpi(args.xpi).items():
                print(f"bundled uBO knows {key}: {title}")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.check:
        current = args.target.read_text(encoding="utf-8") if args.target.exists() else None
        if current != text:
            print(f"error: {args.target} is stale; run {Path(__file__).name} without --check", file=sys.stderr)
            return 1
        print(f"ok: {args.target.name} enables {', '.join(COOKIE_LISTS)} by default")
        return 0
    args.target.write_text(text, encoding="utf-8")
    print(f"wrote {args.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
