import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import migrate_previous_library, Library, DEFAULT_LIST
from radio import load_catalog
from nowplaying import audd_token, recognition_provider

class BrandTests(unittest.TestCase):
    def test_catalog_stats(self):
        items = load_catalog()
        self.assertEqual(len(items), 63396)
        self.assertEqual(len({(s['code'], s['country']) for s in items}), 229)
        self.assertEqual(sum(s['code'] == 'AR' for s in items), 1173)

    def test_legacy_data_migration_keeps_original(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d)/'old'; new = Path(d)/'new'
            old.mkdir()
            record = {'version': 2, 'collections': {DEFAULT_LIST: [{'id':'a','name':'Test','url':'https://example.org/radio.mp3'}]}}
            (old/'biblioteca.json').write_text(json.dumps(record), encoding='utf-8')
            (old/'historial_canciones.jsonl').write_text('history', encoding='utf-8')
            self.assertTrue(migrate_previous_library(new,old))
            self.assertFalse(migrate_previous_library(new,old))
            self.assertEqual(len(Library(new).stations()),1)
            self.assertEqual((old/'historial_canciones.jsonl').read_text(), 'history')
            self.assertTrue((new/'historial_canciones.jsonl').exists())
            # if destination exists, never replace edited content
            (new/'biblioteca.json').write_text('custom', encoding='utf-8')
            self.assertFalse(migrate_previous_library(new,old))
            self.assertEqual((new/'biblioteca.json').read_text(), 'custom')

    def test_new_audd_token_and_legacy_alias(self):
        with patch.dict(os.environ, {'LOBOVIEJO79_AUDD_TOKEN': 'new','DARKTUX_AUDD_TOKEN': 'old'}):
            self.assertEqual(audd_token(), 'new')
        with patch.dict(os.environ, {'LOBOVIEJO79_AUDD_TOKEN': '', 'DARKTUX_AUDD_TOKEN': 'old'}):
            self.assertEqual(audd_token(), 'old')
if __name__ == '__main__': unittest.main()
