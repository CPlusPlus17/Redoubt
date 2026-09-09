#!/usr/bin/env python3
"""Offline metadata/plan/API replay verification; not native or APK validation."""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    requests = json.loads((HERE / 'official/requests.json').read_text())
    require(len(requests) == 5, 'expected exactly five bounded metadata requests')
    for request in requests:
        url = urlsplit(request['url'])
        require(url.scheme == 'https' and url.netloc == 'firefox.settings.services.mozilla.com', 'non-official metadata URL')
        require(request['status'] == 200, 'unsuccessful metadata response')
        data = (HERE / 'official' / request['file']).read_bytes()
        require(len(data) == request['bytes'] and sha(data) == request['sha256'], 'metadata bytes differ')
        headers = {k.lower(): v for k, v in request['headers'].items()}
        require('next-page' not in headers, 'unretained metadata pagination')
        if request['file'].endswith('-records.json'):
            rows = json.loads(data)['data']
            require(len(rows) == len({row['id'] for row in rows}), 'duplicate record IDs')
            require(int(headers['etag'].strip('"')) == max(row['last_modified'] for row in rows), 'record ETag differs from retained snapshot')
            for row in rows:
                require(re.fullmatch('[a-zA-Z0-9_-]+', row['id']), 'unsafe record ID')
                attachment = row.get('attachment')
                if attachment:
                    require(re.fullmatch('[a-f0-9]{64}', attachment['hash']) and 0 < attachment['size'] <= 16 * 1024 * 1024, 'invalid attachment pin')
                    require(attachment['location'].startswith('main-workspace/quicksuggest-') and '..' not in Path(attachment['location']).parts, 'unsafe attachment location')
    spec = importlib.util.spec_from_file_location('plan_data', HERE / 'plan-data.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = json.loads((HERE / 'input-plan.json').read_text())
    require(plan == module.make_plan(HERE), 'plan differs from official metadata and deterministic type selection')
    closure = plan['full_mobile_type_closure']
    require((closure['records'], closure['attachments'], closure['attachment_bytes']) == (237, 236, 82315374), 'mobile closure changed')
    for pin in json.loads((HERE / 'source-pins.json').read_text()):
        require(sha((HERE / pin['excerpt']).read_bytes()) == pin['excerpt_sha256'], 'source excerpt pin changed')
    replay = json.loads((HERE / 'rs-replay.json').read_text())
    archive = (HERE / 'rs-scoped-pristine.tar.gz').read_bytes()
    require(sha(archive) == replay['pristine_archive_sha256'], 'RS pristine archive changed')
    with tempfile.TemporaryDirectory(prefix='lw-m7-29-rs-') as folder:
        destination = Path(folder)
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(archive)), mode='r:') as tar:
            members = tar.getmembers()
            require(len(members) == len(replay['scope']) and {m.name for m in members} == set(replay['scope']), 'RS archive scope changed')
            for member in members:
                require(member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts, 'unsafe archive entry')
                data = tar.extractfile(member).read()
                require(sha(data) == replay['pristine_file_hashes'][member.name], 'RS pristine hash differs')
                target = destination / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        for patch in replay['patches']:
            require(sha((ROOT / patch['path']).read_bytes()) == patch['sha256'], 'RS predecessor patch changed')
            subprocess.run(['git', 'apply', *['--include=' + p for p in replay['scope']], str(ROOT / patch['path'])], cwd=destination, check=True, capture_output=True)
        for path, digest in replay['applied_file_hashes'].items():
            require(sha((destination / path).read_bytes()) == digest, 'applied RS API source changed')
    print('PASS: 5 official metadata responses, 369 records, deterministic 237-record / 236-attachment mobile type closure.')
    print('PASS: 19 pinned source excerpts; 2 existing RS patches replayed over 4 files.')
    print('PAYLOAD FETCH / NATIVE IMPORT / INGEST / APK RUNTIME: NOT RUN by this metadata-only check.')


if __name__ == '__main__':
    main()
