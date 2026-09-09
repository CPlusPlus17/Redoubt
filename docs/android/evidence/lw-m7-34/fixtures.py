#!/usr/bin/env python3
"""Offline verification of original AMO update fixtures; network only with --fetch.

This never invokes Gecko, adb, an installer, a signer, or a signature bypass.
Matching ZIP signature entries/hashes cannot establish Gecko's signedState.
"""
import argparse
import ast
import datetime
import hashlib
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ALLOWED_HOSTS = {'addons.mozilla.org', 'addons.cdn.mozilla.net'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def safe_url(url):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname in ALLOWED_HOSTS and
            parsed.port in (None, 443) and not parsed.username and not parsed.password,
            'Unexpected download host or insecure URL: ' + url)


class MozillaRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def fetch(url, target, limit):
    """Create original bytes plus a transport receipt; do not replace old evidence."""
    receipt_path = target.with_suffix(target.suffix + '.fetch.json')
    if target.exists():
        require(receipt_path.is_file(), 'Existing original has no fetch receipt: ' + str(target))
        return
    require(not receipt_path.exists(), 'Receipt exists without its original: ' + str(receipt_path))
    safe_url(url)
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Redoubt-official-fixture-audit/1.0', 'Accept-Encoding': 'identity'})
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with urllib.request.build_opener(MozillaRedirects()).open(request, timeout=45) as response:
        safe_url(response.geturl())
        require(response.status == 200, 'Download did not return HTTP 200')
        data = response.read(limit + 1)
        require(len(data) <= limit, 'Response exceeds the bounded expected size')
        require(response.headers.get('Content-Encoding', 'identity') == 'identity', 'Unexpected response content encoding')
        receipt = {'requested_url': url, 'final_url': response.geturl(), 'status': response.status,
            'retrieved_utc': started, 'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'sha256': sha(data), 'size': len(data), 'tls_verification': 'urllib default system CA verification',
            'headers': {key: response.headers.get(key) for key in
                ['Content-Type', 'Content-Length', 'ETag', 'Last-Modified', 'Date']}}
    # Writing downloaded bytes as received is deliberately separate from parsing.
    with target.open('xb') as output:
        output.write(data)
    write_json(receipt_path, receipt)


def receipt_for(path, url):
    data = path.read_bytes()
    receipt = read_json(path.with_suffix(path.suffix + '.fetch.json'))
    require(receipt.get('requested_url') == url and receipt.get('status') == 200, 'Wrong original response provenance')
    safe_url(receipt.get('final_url', ''))
    require(receipt.get('size') == len(data) and receipt.get('sha256') == sha(data), 'Original bytes differ from fetch receipt')
    return data, receipt


def inspect_fixture(spec, pins):
    version = spec['version']
    metadata_path = HERE/f'amo-version-{version}.json'
    xpi_path = HERE/f'ublock_origin-{version}.xpi'
    raw_metadata, metadata_receipt = receipt_for(metadata_path, spec['metadata_url'])
    metadata = json.loads(raw_metadata)
    file = metadata['file']
    require(metadata['id'] == spec['version_id'] and metadata['version'] == version and
            metadata['channel'] == 'listed', 'Wrong AMO version identity/channel')
    require(file['id'] == spec['file_id'] and file['url'] == spec['url'] and file['status'] == 'public',
            'Wrong AMO file identity or status')
    require(file['hash'] == 'sha256:' + spec['sha256'] and file['size'] == spec['size'],
            'AMO metadata differs from the pinned original bytes')
    require(metadata['compatibility']['android']['min'] == spec['android_min_version'] and
            metadata['compatibility']['android']['max'] == '*' and
            metadata['compatibility']['firefox'] == {'min': '115.0', 'max': '*'},
            'Unexpected AMO Android/Firefox compatibility')
    raw_xpi, xpi_receipt = receipt_for(xpi_path, spec['url'])
    require(len(raw_xpi) == spec['size'] and sha(raw_xpi) == spec['sha256'], 'XPI differs from official pinned hash/size')
    with zipfile.ZipFile(io.BytesIO(raw_xpi)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate ZIP entry is ambiguous')
        require(archive.testzip() is None, 'XPI ZIP integrity check failed')
        raw_manifest = archive.read('manifest.json')
        manifest = json.loads(raw_manifest)
        settings = manifest.get('browser_specific_settings', manifest.get('applications', {}))
        require(settings['gecko']['id'] == pins['addon_id'] and manifest['version'] == version,
                'Manifest ID/version differs from the fixture')
        require(settings['gecko_android']['strict_min_version'] == spec['android_min_version'] and
                settings['gecko']['strict_min_version'] == '115.0',
                'Manifest Android minimum differs from official metadata')
        raw_filter = archive.read(pins['filter_path'])
        lines = raw_filter.decode('utf-8').splitlines()
        matching = [index+1 for index, line in enumerate(lines) if line == pins['filter_rule']]
        require(matching, 'Actual parser fixture filter rule is absent')
        signatures = [{'path': name, 'size': len(archive.read(name)), 'sha256': sha(archive.read(name))}
                      for name in names if name.startswith('META-INF/')]
        require(signatures, 'Original fixture has no retained META-INF entries')
    return {'version': version, 'addon_id': pins['addon_id'], 'path': xpi_path.name,
        'sha256': sha(raw_xpi), 'size': len(raw_xpi), 'original_xpi_unmodified': True,
        'metadata': {'path': metadata_path.name, 'sha256': sha(raw_metadata), 'size': len(raw_metadata),
            'url': spec['metadata_url'], 'version_id': metadata['id'], 'file_id': file['id'],
            'channel': metadata['channel'], 'file_status': file['status'], 'compatibility': metadata['compatibility'],
            'is_mozilla_signed_extension': file.get('is_mozilla_signed_extension')},
        'manifest': {'member': 'manifest.json', 'sha256': sha(raw_manifest), 'size': len(raw_manifest),
            'manifest_version': manifest['manifest_version'], 'version': manifest['version'],
            'browser_specific_settings': settings, 'permissions': manifest.get('permissions', []),
            'optional_permissions': manifest.get('optional_permissions', []),
            'host_permissions': manifest.get('host_permissions', []), 'incognito': manifest.get('incognito')},
        'parser_filter': {'member': pins['filter_path'], 'sha256': sha(raw_filter), 'size': len(raw_filter),
            'rule': pins['filter_rule'], 'line_numbers_1_based': matching},
        'zip_signature_entries_observed': signatures,
        'gecko_signed_state': 'PENDING: no Gecko signature verification executed',
        'transport_receipts': [metadata_path.name+'.fetch.json', xpi_path.name+'.fetch.json']}


def verify(pins):
    # Bind the fixture's rule to the actual existing parser acceptance code.
    module = ast.parse((ROOT/'scripts/android-addon-state-smoke.py').read_text())
    constants = {node.targets[0].id: ast.literal_eval(node.value) for node in module.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in ('FILTER_FILE', 'FILTER_RULE')}
    require(constants == {'FILTER_FILE': pins['filter_path'], 'FILTER_RULE': pins['filter_rule']},
            'Prepared rule differs from the current real parser harness input')
    packaged = read_json(ROOT/'assets/ubo-extension.json')
    newer = pins['fixtures'][1]
    require(packaged['id'] == pins['addon_id'] and all(packaged[key] == newer[key]
        for key in ('version', 'url', 'sha256', 'size', 'android_min_version')), 'New fixture differs from the packaged pin')
    records = [inspect_fixture(spec, pins) for spec in pins['fixtures']]
    permission_fields = ('permissions', 'optional_permissions', 'host_permissions')
    return {'schema': 1, 'task': 'LW-M7-34', 'status': 'FIXTURES_VERIFIED_TARGET_PENDING',
        'offline_bytes_verified': True, 'target_acceptance_complete': False,
        'packaged_pin_sha256': sha((ROOT/'assets/ubo-extension.json').read_bytes()),
        'parser_harness_sha256': sha((ROOT/'scripts/android-addon-state-smoke.py').read_bytes()),
        'fixtures': records,
        'same_manifest_permission_lists': all(records[0]['manifest'][key] == records[1]['manifest'][key] for key in permission_fields),
        'pending': ['Gecko version comparator must establish 1.74.0 > 1.73.0',
            'ordinary Gecko signedState verification of both unchanged files',
            'actual Fenix file-picker older-to-newer completion and retained choices',
            'normal/private parser and independent server evidence after update/restart']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true', help='explicitly fetch missing original metadata/XPIs from pinned AMO URLs')
    parser.add_argument('--write-receipt', action='store_true', help='write derived inspection.json; original downloads are never overwritten')
    args = parser.parse_args()
    pins = read_json(HERE/'fixture-pins.json')
    require([item['version'] for item in pins['fixtures']] == ['1.73.0', '1.74.0'], 'Unexpected fixture pair')
    if args.fetch:
        for spec in pins['fixtures']:
            fetch(spec['metadata_url'], HERE/f"amo-version-{spec['version']}.json", 1_000_000)
            fetch(spec['url'], HERE/f"ublock_origin-{spec['version']}.xpi", spec['size'])
    report = verify(pins)
    if args.write_receipt:
        write_json(HERE/'inspection.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
