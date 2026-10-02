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
  * the "assets.json" entry (the catalog's own update location) has no
    remote URL -- "contentURL": [] and no cdnURLs -- so uBO never refreshes
    the catalog after bootstrapping it. See "Self-entry" below.

Self-entry. uBO 1.75.0 reads librewolf.uBO.assetsBootstrapLocation (its
adminSettings.assetsBootstrapLocation) only when it has no catalog yet
(getAssetSourceRegistry, js/assets.js); from then on it refreshes the catalog
like any other asset, from the catalog's OWN "assets.json" entry, every
updateAfter (13) days (getUpdateCandidates/getRemote, js/assets.js). Whatever
that entry names is therefore the real long-term trust anchor, not the
bootstrap URL. It can name none of the candidates:

  * this file at a commit (immutable): impossible -- a file cannot contain the
    hash of the commit that contains it; naming an older commit would make
    the refresh roll the catalog back;
  * a branch of Redoubt (e.g. main): mutable, which the owner rejected;
  * upstream uBO's or LibreWolf's catalog (what uBO and LibreWolf desktop
    use): both keep the cookie lists "off", and on a catalog refresh uBO
    REMOVES from the user's selection every list that stops being a default
    (onAssetsUpdated 'assets.json-updated', js/storage.js), so the lists
    would silently switch off within 13 days.

So the entry has no remote URL: getUpdateCandidates skips an asset whose
hasRemoteURL is not true, and the catalog uBO bootstrapped from the pinned URL
is the one it keeps. The filter lists themselves still update from their own
upstream contentURLs; only the list of lists is frozen. The cost: a catalog
change reaches fresh installs only (re-pin, below); an installed uBO keeps the
catalog it started with.

Re-pinning (docs/android/TRACK.md, "The catalog URL is pinned to a commit"): the pinned URL names
the Redoubt commit that carries this file, so it is set in a LATER commit:

  1. regenerate (this script, or update-ubo-assets.sh) and commit the catalog
     alone: commit A;
  2. set CATALOG_COMMIT below to A's full hash, and settings/android.cfg's
     librewolf.uBO.assetsBootstrapLocation to pinned_url(A) (a
     Redoubt-settings commit, then the gitlink): commit B.
  scripts/tests/test-ubo-cookie-lists.py fails between 1 and 2 (the pinned
  commit no longer serves the current catalog) -- that is the reminder.
  A must reach CPlusPlus17/Redoubt unchanged: never rebase or squash it.

--xpi checks that both keys, and their group, exist in the assets.json inside
the uBO XPI the build bundles (assets/ubo-extension.json pins it): a key uBO
does not know is a list nobody gets.
"""

import argparse
import json
from pathlib import Path
import re
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/uBOAssets.json"
CATALOG_PATH = "assets/uBOAssets.android.json"
TARGET = ROOT / CATALOG_PATH
RAW_BASE = "https://raw.githubusercontent.com/CPlusPlus17/Redoubt"


def pinned_url(commit):
    """The raw URL that serves this catalog as of Redoubt `commit`."""
    return f"{RAW_BASE}/{commit}/{CATALOG_PATH}"


# The Redoubt commit whose CATALOG_PATH settings/android.cfg bootstraps uBO
# from. Re-pin (module docstring) whenever the catalog changes.
CATALOG_COMMIT = "612fac026e238ebac8745b6b9ed0922790473f21"
ANDROID_CATALOG_URL = pinned_url(CATALOG_COMMIT)
_EXTERNAL = re.compile(r"^(?:[a-z-]+)://")
COOKIE_GROUP = "EasyList/uBO – Cookie Notices"
COOKIE_LISTS = ("fanboy-cookiemonster", "ublock-cookies-easylist")


class CatalogError(ValueError):
    """The source catalog or the bundled uBO does not have what we enable."""


def derive(catalog):
    """Return the Android catalog for LibreWolf's `catalog` (a parsed dict)."""
    out = json.loads(json.dumps(catalog))
    if not isinstance(out.get("assets.json"), dict):
        raise CatalogError("catalog has no assets.json entry")
    out["assets.json"]["contentURL"] = []
    out["assets.json"].pop("cdnURLs", None)
    for key in COOKIE_LISTS:
        entry = out.get(key)
        if not isinstance(entry, dict) or entry.get("content") != "filters":
            raise CatalogError(f"catalog has no filter list {key!r}")
        if entry.get("parent") != COOKIE_GROUP:
            raise CatalogError(f"{key!r} is no longer in uBO's {COOKIE_GROUP!r} group")
        entry.pop("off", None)
    return out


def self_update_urls(catalog):
    """The remote URLs uBO would refresh `catalog` itself from (none is the goal).

    Mirrors uBO 1.75.0's js/assets.js: registerAssetSource sets hasRemoteURL
    when a contentURL matches reIsExternalPath (any "scheme://"), and
    getRemote then also tries the cdnURLs. Both are reported.
    """
    entry = catalog.get("assets.json") or {}
    urls = []
    for field in ("contentURL", "cdnURLs"):
        value = entry.get(field) or []
        urls += [value] if isinstance(value, str) else list(value)
    return [url for url in urls if isinstance(url, str) and _EXTERNAL.match(url)]


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
