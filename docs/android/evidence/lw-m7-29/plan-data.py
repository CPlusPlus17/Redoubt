"""Deterministic metadata-only plan; does not download or stage runtime assets."""
import collections
import json
from pathlib import Path

COLLECTIONS = ('quicksuggest-amp', 'quicksuggest-other')
RS_PREFIX = 'third_party/application-services/components/remote_settings/'
CDN = 'https://firefox-settings-attachments.cdn.mozilla.net/'


def make_plan(here):
    requests = json.loads((here / 'official/requests.json').read_text())
    output = {'format': 1, 'status': 'PREPARATION ONLY; no payloads installed or bundled',
              'recommended_delivery': 'explicit selected downloads into validated native cache; implementation pending',
              'attachment_bytes_verified': False, 'payload_icon_references_verified': False,
              'native_ingestion_executed': False, 'collections': {}}
    for collection in COLLECTIONS:
        records = json.loads((here / f'official/{collection}-records.json').read_text())['data']
        request = next(r for r in requests if r['file'] == f'{collection}-records.json')
        headers = {k.lower(): v for k, v in request['headers'].items()}
        timestamp = int(headers['etag'].strip('"'))
        stats = collections.defaultdict(lambda: {'records': 0, 'attachment_bytes': 0})
        selected = []
        for row in records:
            key = row['type'] + ('-' + row['form_factor'] if row['type'] == 'amp' else '')
            stats[key]['records'] += 1
            stats[key]['attachment_bytes'] += row.get('attachment', {}).get('size', 0)
            keep = (row['type'] == 'icon' or
                    collection == 'quicksuggest-amp' and row['type'] == 'amp' and row['form_factor'] == 'phone' or
                    collection == 'quicksuggest-other' and row['type'] in ('wikipedia', 'configuration'))
            if not keep:
                continue
            item = {'id': row['id'], 'type': row['type'], 'last_modified': row['last_modified'],
                    'filter_expression': row.get('filter_expression'), 'attachment_downloaded': False}
            if 'attachment' in row:
                attachment = row['attachment']
                item['attachment'] = attachment
                item['download_url'] = CDN + attachment['location']
                item['packaged_key'] = row['id']
                item['proposed_packaged_paths'] = [RS_PREFIX + 'dumps/main/attachments/' + collection + '/' + row['id'] + suffix
                                                  for suffix in ('', '.meta.json')]
                item['proposed_sidecar'] = {k: attachment[k] for k in ('location', 'hash', 'size')}
            else:
                item['inline_configuration'] = row.get('configuration')
            selected.append(item)
        output['collections'][collection] = {
            'records_endpoint_timestamp': timestamp,
            'metadata_endpoint_timestamp': json.loads((here / f'official/{collection}-metadata.json').read_text())['data']['last_modified'],
            'source_record_count': len(records), 'source_type_totals': dict(sorted(stats.items())),
            'selected_record_count': len(selected),
            'selected_attachment_count': sum('attachment' in r for r in selected),
            'selected_attachment_bytes': sum(r.get('attachment', {}).get('size', 0) for r in selected),
            'conservative_selected_records': sorted(selected, key=lambda r: r['id']),
            'proposed_packaged_collection_paths': [RS_PREFIX + 'dumps/main/' + collection + suffix for suffix in ('.json', '.timestamp')],
        }
    output['full_mobile_type_closure'] = {
        'records': sum(c['selected_record_count'] for c in output['collections'].values()),
        'attachments': sum(c['selected_attachment_count'] for c in output['collections'].values()),
        'attachment_bytes': sum(c['selected_attachment_bytes'] for c in output['collections'].values()),
        'interpretation': 'Conservative sizing alternative only, not an approved bulk APK input set. Includes every icon record of both selected collections; payload references have not been inspected.',
    }
    output['first_payload_inspection_proposal'] = {
        'records': ['sponsored-suggestions-de-phone', 'data-wikipedia-de'],
        'payload_bytes': sum(r['attachment']['size'] for c in output['collections'].values()
                             for r in c['conservative_selected_records']
                             if r['id'] in ('sponsored-suggestions-de-phone', 'data-wikipedia-de')),
        'condition': 'Then inspect native schemas and exact icon references, and fetch only their pinned icon closure before declaring an install fixture complete.',
        'downloaded': False,
    }
    return output


if __name__ == '__main__':
    print(json.dumps(make_plan(Path(__file__).resolve().parent), indent=2))
