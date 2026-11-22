import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import DEFAULT_LIST, Library, station_record, valid_stream

RADIO_A = {'id': 'a', 'name': 'Radio Norte', 'url': 'https://example.org/a.mp3',
           'country': 'Argentina', 'code': 'AR', 'codec': 'MP3', 'bitrate': '128', 'votes': 11}
RADIO_B = {'id': 'b', 'name': 'Radio Sur', 'url': 'https://example.org/b.mp3',
           'country': 'Chile', 'code': 'CL', 'codec': 'MP3', 'bitrate': '128', 'votes': 10}
RADIO_C = {'id': 'c', 'name': 'Radio Central', 'url': 'https://example.org/c.mp3',
           'country': 'Paraguay', 'code': 'PY', 'codec': 'OGG', 'bitrate': '64', 'votes': 8}


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'estado'
        self.db = Library(self.path)

    def test_add_remove_fav_and_persist(self):
        self.assertTrue(self.db.add(DEFAULT_LIST, RADIO_A))
        self.assertFalse(self.db.add(DEFAULT_LIST, RADIO_A))
        self.assertTrue(self.db.add(DEFAULT_LIST, RADIO_B))
        self.assertEqual([s['id'] for s in self.db.stations()], ['a', 'b'])
        other = Library(self.path)
        self.assertTrue(other.contains(DEFAULT_LIST, 'a'))
        self.assertFalse(other.toggle_favorite(RADIO_A))
        self.assertEqual([s['id'] for s in Library(self.path).stations()], ['b'])

    def test_create_rename_delete_playlists_independent(self):
        self.db.create('Rock Nacional')
        self.db.add(DEFAULT_LIST, RADIO_A)
        self.db.add('Rock Nacional', RADIO_A)
        self.db.add('Rock Nacional', RADIO_B)
        self.db.rename('Rock Nacional', 'Rock en español')
        self.assertEqual([s['id'] for s in Library(self.path).stations('Rock en español')], ['a', 'b'])
        self.db.delete('Rock en español')
        self.assertEqual([s['id'] for s in self.db.stations()], ['a'])
        with self.assertRaises(ValueError):
            self.db.delete(DEFAULT_LIST)
        with self.assertRaises(ValueError):
            self.db.create('mis favoritas')

    def test_move_up_and_down_persists(self):
        for radio in (RADIO_A, RADIO_B, RADIO_C):
            self.db.add(DEFAULT_LIST, radio)
        self.assertTrue(self.db.move(DEFAULT_LIST, RADIO_C, -1))
        self.assertTrue(self.db.move(DEFAULT_LIST, RADIO_C, -1))
        self.assertFalse(self.db.move(DEFAULT_LIST, RADIO_C, -1))
        self.assertEqual([s['id'] for s in Library(self.path).stations()], ['c', 'a', 'b'])
        self.assertTrue(self.db.move(DEFAULT_LIST, RADIO_C, +1))
        self.assertEqual([s['id'] for s in Library(self.path).stations()], ['a', 'c', 'b'])

    def test_export_playlist(self):
        self.db.add(DEFAULT_LIST, RADIO_A)
        self.db.add(DEFAULT_LIST, RADIO_B)
        outfile = self.db.export_m3u()
        self.assertTrue(outfile.is_file())
        content = outfile.read_text(encoding='utf-8')
        self.assertTrue(content.startswith('#EXTM3U\n'))
        self.assertIn('Radio Norte', content)
        self.assertIn('https://example.org/a.mp3', content)
        self.assertLess(content.index('Radio Norte'), content.index('Radio Sur'))

    def test_import_favorites_v1_without_overwriting(self):
        old = {RADIO_A['id']: RADIO_A, RADIO_B['id']: RADIO_B}
        self.path.mkdir(parents=True, exist_ok=True)
        origin = self.path / 'favoritos.json'
        origin.write_text(json.dumps(old, ensure_ascii=False), encoding='utf-8')
        before = origin.read_bytes()
        migrated = Library(self.path)
        self.assertTrue(migrated.migrated)
        self.assertEqual([r['id'] for r in migrated.stations()], ['a', 'b'])
        self.assertEqual(origin.read_bytes(), before)
        self.assertFalse(Library(self.path).migrated)

    def test_corrupt_data_not_overwritten(self):
        self.db.add(DEFAULT_LIST, RADIO_A)
        origin = self.db.path
        origin.write_text('{ERROR JSON', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            Library(self.path)
        self.assertEqual(origin.read_text(), '{ERROR JSON')

    def test_validation(self):
        for bad in ('file:///etc/passwd', 'ftp://example.org', 'javascript:alert(1)',
                    'https://example.org/some path', '--no-config', 'http://'):
            self.assertFalse(valid_stream(bad), bad)
        self.assertTrue(valid_stream('https://example.org/stream?foo=bar'))
        with self.assertRaises(ValueError):
            self.db.create('Rock/Pop')
        with self.assertRaises(ValueError):
            station_record({'url': 'file:///etc/passwd'})


if __name__ == '__main__':
    unittest.main()
