#!/usr/bin/env python3
"""Derive assets/uBOAssets.android.json from LibreWolf's assets/uBOAssets.json.

LibreWolf's registry points its own "assets.json" entry at LibreWolf's Codeberg
main branch, so every later uBO registry update polls LibreWolf's servers.
Android keeps LibreWolf's list definitions and default selection byte for byte,
and replaces only that entry with the one stock uBO ships (pinned 1.74.0
assets/assets.json), so after first install the registry updates like any uBO
install's. settings/android.cfg points librewolf.uBO.assetsBootstrapLocation at
this file on a fixed Redoubt commit.

    python3 scripts/gen-ubo-assets-android.py          # write
    python3 scripts/gen-ubo-assets-android.py --check  # exit 1 if stale
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/uBOAssets.json'
TARGET = ROOT / 'assets/uBOAssets.android.json'

# uBlock Origin 1.74.0, assets/assets.json, entry "assets.json".
STOCK_REGISTRY_ENTRY = {
    'content': 'internal',
    'updateAfter': 13,
    'contentURL': [
        'https://raw.githubusercontent.com/gorhill/uBlock/master/assets/assets.json',
        'assets/assets.json',
    ],
    'cdnURLs': [
        'https://ublockorigin.github.io/uAssetsCDN/ublock/assets.json',
        'https://ublockorigin.pages.dev/ublock/assets.json',
        'https://cdn.jsdelivr.net/gh/gorhill/uBlock@master/assets/assets.json',
    ],
}


def derive():
    registry = json.loads(SOURCE.read_text())
    assert registry['assets.json']['content'] == 'internal', 'unexpected LibreWolf registry entry'
    registry['assets.json'] = STOCK_REGISTRY_ENTRY
    text = json.dumps(registry, indent=2, ensure_ascii=False) + '\n'
    assert 'codeberg.org' not in text, 'a list still points at LibreWolf infrastructure'
    return text


def main():
    text = derive()
    if '--check' in sys.argv[1:]:
        if not TARGET.exists() or TARGET.read_text() != text:
            sys.exit(f'{TARGET.relative_to(ROOT)} is stale: run {Path(__file__).relative_to(ROOT)}')
        print(f'ok: {TARGET.relative_to(ROOT)} matches {SOURCE.relative_to(ROOT)}')
        return
    TARGET.write_text(text)
    print(f'wrote {TARGET.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
