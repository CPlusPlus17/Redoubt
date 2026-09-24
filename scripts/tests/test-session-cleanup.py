#!/usr/bin/env python3
"""Reconstruct exact native cleanup inputs and validate source/test definitions.

This deliberately cannot grade target-native or Android execution as passed.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'docs/android/evidence/lw-m7-37'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def receipt_patch(current, pinned_sha256):
    """The patch this receipt was captured with. After the 153.3.0esr rebase
    (docs/android/evidence/esr-153.3/rebase.json) the current file differs; its
    stored pre-rebase copy replays this 153.0esr receipt, and only if the
    rebase receipt binds both hashes."""
    if sha(current.read_bytes()) == pinned_sha256:
        return current
    rebase = json.loads((ROOT / 'docs/android/evidence/esr-153.3/rebase.json').read_text())
    entry = rebase['patches'][str(current.relative_to(ROOT))]
    assert sha(current.read_bytes()) == entry['after_sha256'], 'patch changed since the ESR rebase receipt'
    before = ROOT / entry['before_copy']
    assert sha(before.read_bytes()) == entry['before_sha256'] == pinned_sha256
    return before


def unpack(path, destination, selected=None, prefix=''):
    with tarfile.open(path) as archive:
        for entry in archive:
            if not entry.isfile() or not entry.name.startswith(prefix):
                continue
            name = entry.name[len(prefix):]
            assert name and not Path(name).is_absolute() and '..' not in Path(name).parts
            if selected is not None and name not in selected:
                continue
            output = destination / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.extractfile(entry).read())


def command(argv, cwd):
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout + result.stderr


def main():
    manifest = json.loads((HERE / 'native-source-files.json').read_text())
    composition = json.loads((HERE / 'native-composition.json').read_text())
    assert sha((HERE / 'native-composition.json').read_bytes()) == manifest['source_composition_sha256']
    patch = receipt_patch(ROOT / 'patches/android/session-cleanup.patch', manifest['patch_sha256'])
    assert sha((HERE / 'native-source-baseline.tar.gz').read_bytes()) == manifest['baseline_archive_sha256']
    assert sha((HERE / 'current-capture/guest-source.tar.gz').read_bytes()) == composition['capture_archive_sha256']
    spec = importlib.util.spec_from_file_location('ordering_sections',
        ROOT / 'docs/android/evidence/lw-m7-35/check-ordering.py')
    sections = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sections)
    with tempfile.TemporaryDirectory(prefix='lw-m7-37-native-') as scratch:
        scratch = Path(scratch)
        source = scratch / 'source'
        source.mkdir()
        unpack(HERE / 'current-capture/guest-source.tar.gz', source, composition['paths'], 'source/')
        for item in composition['files']:
            path = source / item['path']
            assert (sha(path.read_bytes()) if path.exists() else None) == item['capture_sha256'], item['path']
        for predecessor in composition['predecessors']:
            if not predecessor['shared_paths']:
                continue  # Historical review of a predecessor with no overlap.
            path = receipt_patch(ROOT / predecessor['patch'], predecessor['sha256'])
            selected = sections.sections(path)
            scoped = scratch / 'predecessor.patch'
            scoped.write_text(''.join(selected[name] for name in predecessor['shared_paths']))
            output = command(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(scoped)], source)
            assert 'offset' not in output and 'fuzz' not in output, output
        for item in composition['files']:
            path = source / item['path']
            assert (sha(path.read_bytes()) if path.exists() else None) == item['before_sha256'], item['path']
        baseline = scratch / 'baseline'
        baseline.mkdir()
        unpack(HERE / 'native-source-baseline.tar.gz', baseline)
        for path in baseline.rglob('*'):
            if path.is_file():
                assert path.read_bytes() == (source / path.relative_to(baseline)).read_bytes()
        print('PASS actual captured source + scoped corrected35 inputs; all before hashes and retained baseline match')
        assert sorted(sections.sections(patch)) == sorted(item['path'] for item in manifest['files'])
        output = command(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], source)
        assert 'offset' not in output and 'fuzz' not in output, output
        for item in manifest['files']:
            assert sha((source / item['path']).read_bytes()) == item['after_sha256'], item['path']
        print('PASS all 15 declared source outputs; exact replay without offsets/fuzz')
        parser_inputs = json.loads((HERE / 'native-parser-inputs.json').read_text())
        assert sha((HERE / 'native-parser-inputs.tar.gz').read_bytes()) == parser_inputs['archive_sha256']
        parsers = scratch / 'parsers'
        unpack(HERE / 'native-parser-inputs.tar.gz', parsers)
        for item in parser_inputs['files']:
            assert sha((parsers / item['path']).read_bytes()) == item['sha256']
        sys.path[:0] = [str(parsers / name) for name in (
            'third_party/python/ply', 'xpcom/idl-parser', 'dom/bindings/parser')]
        from xpidl import xpidl
        import WebIDL
        name = 'netwerk/cookie/nsICookieManager.idl'
        xpidl.IDLParser().parse((source / name).read_text(), name)
        frame = (source / 'dom/chrome-webidl/FrameLoader.webidl').read_text()
        parser = WebIDL.Parser(outputdir=str(scratch))
        parser.parse(frame, 'FrameLoader.webidl')
        method = re.search(r'(\[[^\]]+\]\s+Promise<undefined>\s+whenDestroyed\(\);)', frame).group(1)
        parser = WebIDL.Parser(outputdir=str(scratch))
        parser.parse('[Global=Window, Exposed=Window] interface Window {}; '
                     '[ChromeOnly, Exposed=Window] interface FrameProbe { ' + method + ' };')
        parser.finish()
        print('PASS pinned XPIDL/WebIDL parsers and new-method semantics; imported-type code generation remains target work')
        js = 'netwerk/cookie/test/unit/test_cookie_session_cleanup.js'
        test_api = 'mobile/android/geckoview/src/androidTest/assets/web_extensions/test-support/test-api.js'
        for name in (js, test_api):
            command(['node', '--check', str(source / name)], scratch)
        schema = json.loads((source / test_api.replace('test-api.js', 'test-schema.json')).read_text())
        functions = [item['name'] for item in schema[0]['functions']]
        assert len(set(functions)) == len(functions)
        assert all(name in functions for name in ('prepareFrameDestructionProbe', 'finishFrameDestructionProbe',
                                                 'runInProcessFrameDestructionProbe', 'runPrefSaveFileAsyncIOTest'))
        config = tomllib.loads((source / 'netwerk/cookie/test/unit/xpcshell.toml').read_text())
        assert 'test_cookie_session_cleanup.js' in config
        tasks = re.findall(r'add_task\(async function (\w+)\(', (source / js).read_text())
        kotlin = source / 'mobile/android/geckoview/src/androidTest/java/org/mozilla/geckoview/test/SessionCleanupTest.kt'
        methods = re.findall(r'@Test\s+(?:@[^\n]+\s+)*fun\s+(\w+)\(', kotlin.read_text())
        assert len(set(tasks)) == 9 and len(set(methods)) == 5
        print('PASS JS syntax, JSON/TOML, inherited35 test API and 9 cookie / 5 frame target test definitions')
    print('PENDING native C++/IDL code generation and Kotlin compilation; actual cookie xpcshell/GeckoView execution.')
    print('PENDING all-writer/cache admission, remaining category acknowledgments, retention coordinator and durable journal; no full cleanup-success claim.')


if __name__ == '__main__':
    main()
