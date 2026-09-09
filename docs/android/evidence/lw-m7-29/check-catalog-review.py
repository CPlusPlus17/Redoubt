#!/usr/bin/env python3
"""Check the pinned catalog against retained official records and host review receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CDN = 'https://firefox-settings-attachments.cdn.mozilla.net/'


def main():
    catalog = json.loads((ROOT / 'assets/firefox-suggest/catalog.json').read_text())
    snapshots = {name: {r['id']: r for r in json.loads((HERE / f'official/{name}-records.json').read_text())['data']}
                 for name in ('quicksuggest-amp', 'quicksuggest-other')}
    payloads = json.loads((HERE / 'payload-inspection.json').read_text())
    payloads_by_id = {r['id']: r for r in payloads}
    icons = json.loads((HERE / 'icon-inspection.json').read_text())
    icons_by_id = {r['id']: r for r in icons}
    assert len(payloads_by_id) == len(payloads) == len(catalog['datasets']) == 26
    assert len(icons_by_id) == len(icons) == len(catalog['icons']) == 67
    assert catalog['configuration'] == snapshots['quicksuggest-other'][catalog['configuration']['id']]
    used_icons = set()
    for dataset in catalog['datasets']:
        name = dataset['collection']
        assert dataset['record'] == snapshots[name][dataset['id']]
        observed = payloads_by_id[dataset['id']]
        attachment = dataset['record']['attachment']
        assert observed['sha256'] == attachment['hash'] and observed['bytes'] == attachment['size']
        assert observed['url'] == CDN + attachment['location'] and observed['status'] == 200
        assert observed['all_rows_have_required_fields'] is True
        assert set(dataset['icon_ids']) == {'icon-' + key for key in observed['icon_ids']}
        used_icons.update(dataset['icon_ids'])
        assert dataset['download_bytes'] == attachment['size'] + sum(icons_by_id[key]['bytes'] for key in dataset['icon_ids'])
        assert catalog['timestamps'][name] >= dataset['record']['last_modified']
    assert used_icons == set(icons_by_id)
    for record in catalog['icons']:
        observed = icons_by_id[record['id']]
        assert record == snapshots[observed['collection']][record['id']]
        attachment = record['attachment']
        assert observed['url'] == CDN + attachment['location'] and observed['status'] == 200
        assert observed['sha256'] == attachment['hash'] and observed['bytes'] == attachment['size']
        assert observed['magic_hex'].startswith(('89504e47', 'ffd8'))
        assert catalog['timestamps'][observed['collection']] >= record['last_modified']
    for retained in json.loads((HERE / 'implementation-sources.json').read_text()):
        assert hashlib.sha256((HERE / retained['excerpt']).read_bytes()).hexdigest() == retained['excerpt_sha256']
    print('CATALOG REVIEW PASS: 26 original official dataset records; exact 67-icon dependency graph; global configuration and timestamps.')
    print(f"Maximum selected download: {max(r['download_bytes'] for r in catalog['datasets']):,} bytes.")
    print('All 26 payload and 67 icon host fetch/hash receipts match catalog pins; only 2 payloads + 5 icons retain raw test fixtures.')
    print('Other payload inspection receipts are historical observations, not repeated native parsing. Android image decode and target ingestion NOT RUN.')


if __name__ == '__main__':
    main()
