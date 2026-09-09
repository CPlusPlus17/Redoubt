#!/usr/bin/env python3
"""Verify and stage the small pinned Suggest catalog; never download payloads."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets/firefox-suggest'
CATALOG_SHA256 = '4960be774112710a938ec47bfea0588697dd35de445aea909be675595ae503aa'
CATALOG_BYTES = 52962
RS = Path('third_party/application-services/components/remote_settings')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check_bytes(data, size, digest):
    require(len(data) == size and hashlib.sha256(data).hexdigest() == digest, 'Pinned Suggest bytes differ')


def verify_inputs(asset_dir=ASSETS):
    data = (asset_dir / 'catalog.json').read_bytes()
    check_bytes(data, CATALOG_BYTES, CATALOG_SHA256)
    catalog = json.loads(data)
    require(catalog['format'] == 1 and len(catalog['datasets']) == 26 and len(catalog['icons']) == 67, 'Wrong catalog shape')
    provenance = json.loads((asset_dir / 'provenance.json').read_text())
    require(provenance['catalog_sha256'] == CATALOG_SHA256 and provenance['catalog_bytes'] == CATALOG_BYTES, 'Catalog provenance differs')
    records = {r['id']: r for r in catalog['icons']}
    records.update({d['id']: d['record'] for d in catalog['datasets']})
    require(len(records) == 93, 'Duplicate catalog ID')
    for dataset in catalog['datasets']:
        require(dataset['id'] == dataset['record']['id'], 'Dataset record ID differs')
        required = [dataset['record']] + [records[key] for key in dataset['icon_ids']]
        require(sum(r['attachment']['size'] for r in required) == dataset['download_bytes'], 'Incorrect displayed download size')
        require(len(dataset['icon_ids']) == len(set(dataset['icon_ids'])), 'Duplicate icon dependency')
    fixtures = {}
    for fixture in provenance['testing_only_fixtures']:
        record = records[fixture['id']]
        require(fixture['path'] == 'testing/' + fixture['id'] + '.gz', 'Unsafe fixture path')
        compressed = (asset_dir / fixture['path']).read_bytes()
        check_bytes(compressed, fixture['compressed_bytes'], fixture['compressed_sha256'])
        raw = gzip.decompress(compressed)
        check_bytes(raw, record['attachment']['size'], record['attachment']['hash'])
        check_bytes(raw, fixture['bytes'], fixture['sha256'])
        fixtures[fixture['id']] = raw
    expected_fixture_ids = {'sponsored-suggestions-de-phone', 'data-wikipedia-en'}
    for dataset in catalog['datasets']:
        if dataset['id'] in ('sponsored-suggestions-de-phone', 'data-wikipedia-en'):
            expected_fixture_ids.update(dataset['icon_ids'])
    require(set(fixtures) == expected_fixture_ids, 'Missing or unexpected test fixture')
    for dataset in catalog['datasets']:
        if dataset['id'] in fixtures:
            actual = {'icon-' + row['icon'] for row in json.loads(fixtures[dataset['id']])}
            require(actual == set(dataset['icon_ids']), 'Fixture icon graph differs')
            require(actual <= fixtures.keys(), 'Fixture icon bytes absent')
    expected = {'catalog.json', 'provenance.json'} | {f['path'] for f in provenance['testing_only_fixtures']}
    require({str(p.relative_to(asset_dir)) for p in asset_dir.rglob('*') if p.is_file()} == expected, 'Unexpected asset or bundled production payload')
    return data, catalog, fixtures


def stage(source_tree, asset_dir=ASSETS):
    data, catalog, fixtures = verify_inputs(asset_dir)
    source_tree = Path(source_tree)
    require((source_tree / RS / 'src/client.rs').is_file(), 'Missing native RS client; wrong source destination')
    outputs = {
        RS / 'dumps/main/redoubt-suggest-catalog.json': data,
        Path('mobile/android/fenix/app/src/main/assets/firefox-suggest-catalog.json'): data,
        # Zero is deliberately a baseline seed, not a claimed official timestamp.
        # Any successfully installed collection timestamp wins over this seed.
        RS / 'dumps/main/quicksuggest-other.json': (json.dumps({'data': [catalog['configuration']], 'timestamp': 0}, separators=(',', ':')) + '\n').encode(),
        RS / 'dumps/main/quicksuggest-other.timestamp': b'0\n',
        RS / 'dumps/main/quicksuggest-amp.json': b'{"data":[],"timestamp":0}\n',
        RS / 'dumps/main/quicksuggest-amp.timestamp': b'0\n',
    }
    outputs.update({RS / 'test-data/redoubt-suggest' / key: value for key, value in fixtures.items()})
    for path, value in outputs.items():
        target = source_tree / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix='.suggest-', dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(value)
        os.replace(temporary, target)
    return len(outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-tree', type=Path)
    args = parser.parse_args()
    if args.source_tree:
        count = stage(args.source_tree)
        print(f'PASS staged {count} pinned Suggest catalog/config/test-fixture files; no production attachment payloads or network')
    else:
        verify_inputs()
        print('PASS verified Suggest catalog: 26 datasets, 67 icon pins, 7 test-only fixtures; no network')


if __name__ == '__main__':
    main()
