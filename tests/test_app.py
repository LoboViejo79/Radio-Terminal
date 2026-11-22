import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import Library, DEFAULT_LIST
from radio import App
from test_library import RADIO_A, RADIO_B


class TestApp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.library = Library(Path(self.temp.name))
        class FakeScreen:
            pass
        self.app = App(FakeScreen(), [RADIO_A, RADIO_B], self.library)
        self.addCleanup(self.app.player.close)

    def test_shortcut_actions_fav_and_playlists(self):
        self.app.switch('global')
        self.assertEqual(len(self.app.items), 2)
        first = self.app.selected_station()
        self.app.toggle_fav()
        self.assertTrue(self.library.contains(DEFAULT_LIST, first))
        self.app.switch('favorites')
        self.assertEqual(self.app.items[0]['id'], first['id'])
        self.app.toggle_fav()
        self.assertEqual(len(self.app.items), 0)

    def test_add_to_named_collection(self):
        self.library.create('Noticias')
        self.app.switch('global')
        chosen = self.app.selected_station()
        self.app.choose = lambda title, options: options.index('Noticias')
        self.app.add_to_playlist()
        self.assertEqual(self.library.stations('Noticias')[0]['id'], chosen['id'])
        self.app.switch('playlists')
        self.assertIn('Noticias', self.app.items)
        self.app.sel = self.app.items.index('Noticias')
        self.app.enter()
        self.assertEqual(self.app.mode, 'playlist')
        self.assertEqual(self.app.selected_station()['id'], chosen['id'])

    def test_reorder_selected_and_migration_persistence(self):
        self.library.add(DEFAULT_LIST, RADIO_A)
        self.library.add(DEFAULT_LIST, RADIO_B)
        self.app.switch('favorites')
        self.app.sel = 1
        self.app.reorder(-1)
        self.assertEqual(self.app.sel, 0)
        self.assertEqual(self.library.stations()[0]['id'], 'b')


if __name__ == '__main__':
    unittest.main()
