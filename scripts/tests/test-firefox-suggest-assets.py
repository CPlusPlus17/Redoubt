#!/usr/bin/env python3
"""Host-only adversarial checks for the real offline Suggest asset packager."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('suggest_packager', ROOT / 'scripts/package-firefox-suggest.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class SuggestAssetTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='lw-m7-29-assets-')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.assets = self.root / 'assets'
        shutil.copytree(packager.ASSETS, self.assets)

    def test_actual_pins_and_complete_retained_fixture_graph(self):
        raw, catalog, fixtures = packager.verify_inputs(self.assets)
        self.assertEqual(packager.CATALOG_BYTES, len(raw))
        self.assertEqual(26, len(catalog['datasets']))
        self.assertIn('data-wikipedia-en', fixtures)
        self.assertIn('sponsored-suggestions-de-phone', fixtures)

    def test_catalog_corruption_cannot_be_reauthorized_by_editing_provenance(self):
        path = self.assets / 'catalog.json'
        path.write_bytes(path.read_bytes().replace(b'"format":1', b'"format":2', 1))
        with self.assertRaises(ValueError): packager.verify_inputs(self.assets)

    def test_wrong_compressed_fixture_fails_before_decompression(self):
        path = next((self.assets / 'testing').iterdir())
        path.write_bytes(b'not a gzip stream')
        with self.assertRaises(ValueError): packager.verify_inputs(self.assets)

    def test_missing_fixture_is_not_silently_omitted(self):
        next((self.assets / 'testing').iterdir()).unlink()
        with self.assertRaises(FileNotFoundError): packager.verify_inputs(self.assets)

    def test_provenance_cannot_replace_the_required_payload_fixture_with_an_icon(self):
        path = self.assets / 'provenance.json'
        value = json.loads(path.read_text())
        value['testing_only_fixtures'] = [r for r in value['testing_only_fixtures'] if r['id'] != 'data-wikipedia-en']
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): packager.verify_inputs(self.assets)

    def test_unexpected_production_payload_is_rejected(self):
        (self.assets / 'unreviewed-payload.json').write_text('[]')
        with self.assertRaises(ValueError): packager.verify_inputs(self.assets)

    def test_staging_uses_actual_macro_paths_and_no_payload_in_fenix_assets(self):
        source = self.root / 'source'
        native = source / packager.RS
        (native / 'src').mkdir(parents=True)
        (native / 'src/client.rs').write_text('existing upstream client')
        count = packager.stage(source, self.assets)
        self.assertEqual(13, count)
        self.assertEqual((source / 'mobile/android/fenix/app/src/main/assets/firefox-suggest-catalog.json').read_bytes(),
                         (native / 'dumps/main/redoubt-suggest-catalog.json').read_bytes())
        for collection in ('quicksuggest-amp', 'quicksuggest-other'):
            seed = json.loads((native / f'dumps/main/{collection}.json').read_text())
            self.assertEqual(0, seed['timestamp'])
            self.assertEqual('0', (native / f'dumps/main/{collection}.timestamp').read_text().strip())
            self.assertTrue(all('attachment' not in row for row in seed['data']))
        self.assertEqual(1, len(list((source / 'mobile/android/fenix/app/src/main/assets').iterdir())))
        self.assertEqual('existing upstream client', (native / 'src/client.rs').read_text())

    def test_failed_validation_stages_nothing(self):
        (self.assets / 'catalog.json').write_text('{}')
        destination = self.root / 'source'
        with self.assertRaises(ValueError): packager.stage(destination, self.assets)
        self.assertFalse(destination.exists())

    def test_wrong_extracted_tree_fails_closed(self):
        destination = self.root / 'wrong-source'
        with self.assertRaises(ValueError): packager.stage(destination, self.assets)
        self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
