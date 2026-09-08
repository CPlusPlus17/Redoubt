#!/usr/bin/env python3
"""Validate and stage reviewed Android translation inputs without network access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets/translations'
CATALOG_SHA256 = 'ce8c163e97d9d5b136cd673f7e63684dada00b45514442bf282b387174100d96'
CATALOG_SIZE = 245592
WASM_SHA256 = '327fcfc7b7e9d95f6fa0844ebf899cfc05469872ef02d3aef5783182839a6255'
WASM_SIZE = 1211955
WASM_DECOMPRESSED_SHA256 = 'f38ef807636a7c994afedaab7ff8ffe0d590d21897f05139f747b80fd7bbe926'
WASM_DECOMPRESSED_SIZE = 4960506


def verify_bytes(data, size, digest):
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Pinned translation input differs in size or SHA256')


def verify_inputs(asset_dir=ASSETS):
    catalog_bytes = (asset_dir / 'catalog.json').read_bytes()
    verify_bytes(catalog_bytes, CATALOG_SIZE, CATALOG_SHA256)
    catalog = json.loads(catalog_bytes)
    assert set(catalog) == {'format', 'models', 'wasm'} and catalog['format'] == 1
    assert len(catalog['models']) == 377 and len(catalog['wasm']) == 1
    records = catalog['models'] + catalog['wasm']
    assert len({record['id'] for record in records}) == len(records)
    wasm = (asset_dir / 'bergamot-translator.wasm.zst').read_bytes()
    verify_bytes(wasm, WASM_SIZE, WASM_SHA256)
    record = catalog['wasm'][0]
    assert record['attachment']['hash'] == WASM_SHA256 and record['attachment']['size'] == WASM_SIZE
    assert record['decompressedHash'] == WASM_DECOMPRESSED_SHA256
    assert record['decompressedSize'] == WASM_DECOMPRESSED_SIZE
    assert record['version'] == '4.0' and record['license'] == 'MPL-2.0'
    # Hash validation precedes invocation; the decoder only receives the exact
    # reviewed 1.2 MB input. It cannot be used to unpack an unpinned archive.
    decompressed = subprocess.run(
        ['zstd', '--decompress', '--stdout', '--quiet'], input=wasm,
        capture_output=True, timeout=30, check=True,
    ).stdout
    verify_bytes(decompressed, WASM_DECOMPRESSED_SIZE, WASM_DECOMPRESSED_SHA256)
    assert decompressed[:4] == b'\0asm'
    return catalog


def package(destination, asset_dir=ASSETS):
    catalog = verify_inputs(asset_dir)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.translations-', dir=destination.parent) as scratch:
        for name in ('catalog.json', 'bergamot-translator.wasm.zst'):
            staged = Path(scratch) / name
            shutil.copyfile(asset_dir / name, staged)
            os.replace(staged, destination / name)
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-dir', type=Path, help='stage into this extracted source directory')
    args = parser.parse_args()
    catalog = package(args.asset_dir) if args.asset_dir else verify_inputs()
    print(f'PASS verified offline translation inputs: {len(catalog["models"])} model records, '
          'WASM 4.0 compressed/decompressed pins; no network fetch')


if __name__ == '__main__':
    main()
