#!/usr/bin/env python3
"""Replay pinned translation packaging and actual JS source tests; no runtime claim."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/android/evidence/lw-m7-16'
PATCH = ROOT / 'patches/android/translation-assets.patch'
spec = importlib.util.spec_from_file_location('translation_package', ROOT / 'scripts/package-translation-assets.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class PackageTests(unittest.TestCase):
    def test_verified_inputs(self):
        catalog = package.verify_inputs()
        self.assertEqual(len(catalog['models']), 377)

    def test_offline_stage_matches_reviewed_bytes_on_repeat(self):
        with tempfile.TemporaryDirectory() as scratch:
            for _ in range(2):
                package.package(Path(scratch) / 'data')
                for name in ('catalog.json', 'bergamot-translator.wasm.zst'):
                    self.assertEqual((Path(scratch) / 'data' / name).read_bytes(), (package.ASSETS / name).read_bytes())

    def test_missing_and_corrupt_inputs_do_not_stage(self):
        for missing in (True, False):
            for name in ('catalog.json', 'bergamot-translator.wasm.zst'):
                with self.subTest(missing=missing, name=name), tempfile.TemporaryDirectory() as scratch:
                    inputs = Path(scratch) / 'inputs'
                    inputs.mkdir()
                    for asset in ('catalog.json', 'bergamot-translator.wasm.zst'):
                        data = (package.ASSETS / asset).read_bytes()
                        if asset == name:
                            if missing:
                                continue
                            data = bytes([data[0] ^ 1]) + data[1:]
                        (inputs / asset).write_bytes(data)
                    destination = Path(scratch) / 'output'
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        package.package(destination, inputs)
                    self.assertFalse(destination.exists())

    def test_extra_or_truncated_input_fails_exact_pin(self):
        data = (package.ASSETS / 'catalog.json').read_bytes()
        for changed in (data[:-1], data + b'\n'):
            with self.assertRaises(ValueError):
                package.verify_bytes(changed, package.CATALOG_SIZE, package.CATALOG_SHA256)

    def test_make_prerequisites_are_android_only(self):
        with tempfile.TemporaryDirectory() as scratch:
            probe = Path(scratch) / 'probe.mk'
            probe.write_text("translation-input-probe:\n\t@printf '%s\\n' '$(android_translation_inputs)'\n")
            for target in ('desktop', 'android'):
                result = subprocess.run(['make', '--no-print-directory', '-s', '-f', 'Makefile', '-f', str(probe),
                                         'TARGETS=' + target, 'translation-input-probe'],
                                        cwd=ROOT, capture_output=True, text=True, check=True)
                actual = result.stdout.strip().split()
                expected = [] if target == 'desktop' else [
                    'scripts/package-translation-assets.py', 'assets/translations/catalog.json',
                    'assets/translations/bergamot-translator.wasm.zst', 'assets/translations/provenance.json',
                ]
                self.assertEqual(actual, expected)

    def test_provenance_pins_match_the_fixed_packager_pins(self):
        pin = json.loads((package.ASSETS / 'provenance.json').read_text())
        self.assertEqual(pin['catalog']['sha256'], package.CATALOG_SHA256)
        self.assertEqual(pin['wasm']['sha256'], package.WASM_SHA256)
        self.assertEqual(pin['wasm']['decompressed_sha256'], package.WASM_DECOMPRESSED_SHA256)
        for receipt in pin['upstream_collections'].values():
            name = receipt['url'].split('/collections/')[1].split('/')[0]
            original = (EVIDENCE / (name + '.json')).read_bytes()
            self.assertEqual(sha(original), receipt['sha256'])
            self.assertEqual(len(original), receipt['size'])
            self.assertFalse(any(key.lower() == 'next-page' for key in receipt['headers']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='check actual patched source instead of reconstructing originals')
    parser.add_argument('--apk', type=Path, help='add an exact packaged catalog/WASM/module comparison')
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PackageTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    inventory = json.loads((EVIDENCE / 'source-files.json').read_text())['files']
    originals = {entry['path']: entry for entry in inventory if entry['before_sha256']}
    with tempfile.TemporaryDirectory(prefix='lw-m7-16-source-') as scratch:
        source = args.source.resolve() if args.source else Path(scratch)
        if not args.source:
            with tarfile.open(EVIDENCE / 'source-baseline.tar.gz') as archive:
                assert {member.name for member in archive} == set(originals)
                for member in archive:
                    assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                    data = archive.extractfile(member).read()
                    assert sha(data) == originals[member.name]['before_sha256']
                    dest = source / member.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
            result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(PATCH)], cwd=source, capture_output=True, text=True, check=True)
            assert 'offset' not in result.stdout and 'fuzz' not in result.stdout
            print('PASS patch applies with zero fuzz and no offsets', flush=True)
        for entry in inventory:
            data = (source / entry['path']).read_bytes()
            assert sha(data) == entry['after_sha256'], entry['path']
            if entry['path'].endswith(('.js', '.mjs')):
                subprocess.run(['node', '--check', str(source / entry['path'])], check=True)
        if not args.source:
            package.package(source / 'toolkit/components/translations/android-data')
        subprocess.run(['node', str(ROOT / 'scripts/tests/test-translation-assets.js'), str(source)], check=True)
        if args.apk:
            with zipfile.ZipFile(args.apk) as apk:
                with zipfile.ZipFile(io.BytesIO(apk.read('assets/omni.ja'))) as omni:
                    prefix = 'chrome/toolkit/content/global/translations/android-data/'
                    for asset in ('catalog.json', 'bergamot-translator.wasm.zst'):
                        assert omni.read(prefix + asset) == (package.ASSETS / asset).read_bytes()
                    packaged = {
                        'toolkit/components/translations/AndroidTranslationAssets.sys.mjs': 'modules/translations/AndroidTranslationAssets.sys.mjs',
                        'toolkit/components/translations/TranslationsUtils.mjs': 'chrome/toolkit/content/global/translations/TranslationsUtils.mjs',
                        'mobile/shared/modules/geckoview/GeckoViewTranslations.sys.mjs': 'modules/geckoview/GeckoViewTranslations.sys.mjs',
                    }
                    for actor in ('TranslationsParent', 'TranslationsChild', 'TranslationsEngineChild'):
                        packaged[f'toolkit/components/translations/actors/{actor}.sys.mjs'] = f'actors/{actor}.sys.mjs'
                    for original, resource in packaged.items():
                        assert omni.read(resource) == (source / original).read_bytes(), resource
            print('PASS APK pinned resources and production JS; APK SHA256=' + sha(args.apk.read_bytes()))
        print('PASS static/source checks; target compilation, Gecko tests, real DOM translation and offline restart remain pending')


if __name__ == '__main__':
    main()
