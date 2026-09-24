#!/usr/bin/env python3
"""Package only the declared first native increment from private before/source trees."""
import argparse
import difflib
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    composition = json.loads((HERE / 'native-composition.json').read_text())
    expected = {item['path']: item['before_sha256'] for item in composition['files']}
    chunks, files = [], []
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name in composition['paths']:
                old = args.before / name
                before = old.read_bytes() if old.exists() else b''
                assert (sha(before) if old.exists() else None) == expected[name], name
                if old.exists():
                    entry = tarfile.TarInfo(name)
                    entry.size, entry.mode, entry.mtime = len(before), 0o644, 0
                    archive.addfile(entry, io.BytesIO(before))
                after = (args.source / name).read_bytes()
                if before == after:
                    continue
                chunks.extend(difflib.unified_diff(
                    before.decode().splitlines(keepends=True), after.decode().splitlines(keepends=True),
                    fromfile='a/' + name if old.exists() else '/dev/null', tofile='b/' + name, n=3))
                files.append({'path': name, 'before_sha256': sha(before) if old.exists() else None,
                              'after_sha256': sha(after), 'before_bytes': len(before), 'after_bytes': len(after)})
    # Match the repository's existing patches: an empty context line needs no
    # leading space, and must not create trailing whitespace in the patch file.
    patch = ''.join('\n' if line == ' \n' else line for line in chunks).encode()
    (ROOT / 'patches/android/session-cleanup.patch').write_bytes(patch)
    (HERE / 'native-source-baseline.tar.gz').write_bytes(stream.getvalue())
    manifest = {'source_composition_sha256': sha((HERE / 'native-composition.json').read_bytes()),
                'baseline_archive_sha256': sha(stream.getvalue()), 'patch_sha256': sha(patch), 'files': files,
                'target_status': 'NOT RUN: C++/IDL code generation, Kotlin compilation, cookie xpcshell and GeckoView instrumentation. Full-session/journal-success wiring remains absent.'}
    (HERE / 'native-source-files.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'PACKAGED {len(files)} source paths, patch SHA256 {sha(patch)}; no target pass claimed')


if __name__ == '__main__':
    main()
