import json
import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nowplaying import (normalize_metadata, get_mpv_metadata, parse_songrec,
                        recognition_provider, audd_recognize)

class TestNowPlaying(unittest.TestCase):
    def test_icy_case(self):
        self.assertEqual(normalize_metadata({'icy-title': 'Artista - Tema'}, 'Radio XYZ'), 'Artista - Tema')
        self.assertEqual(normalize_metadata({'icy-title': 'Radio XYZ'}, 'Radio XYZ'), '')
    def test_id3(self):
        self.assertEqual(normalize_metadata({'artist': 'Band', 'title': 'Song'}), 'Band — Song')
        self.assertEqual(normalize_metadata({'random': 'a'}), '')
        self.assertEqual(normalize_metadata({}), '')
    def test_songrec_response(self):
        self.assertEqual(parse_songrec(json.dumps({'track': {'subtitle': 'AC/DC', 'title': 'Thunderstruck'}})), 'AC/DC — Thunderstruck')
        self.assertEqual(parse_songrec('{}'), '')
    def test_ipc_response_and_event(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = str(Path(dirname) / 'socket')
            ready = threading.Event()
            def server():
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.bind(path)
                    s.listen(1)
                    ready.set()
                    client, _ = s.accept()
                    with client:
                        request = client.recv(1000)
                        self.assertIn(b'metadata', request)
                        client.sendall(b'{"event":"start-file"}\n')
                        client.sendall(b'{"request_id":8472,"error":"success","data":{"icy-title":"Mock - Track"}}\n')
            thread = threading.Thread(target=server)
            thread.start()
            ready.wait(timeout=2)
            self.assertEqual(get_mpv_metadata(path), {'icy-title':'Mock - Track'})
            thread.join(timeout=2)
    def test_provider_precedence_and_missing(self):
        def which(name):
            return '/bin/' + name if name in ('ffmpeg','songrec') else None
        with patch('nowplaying.shutil.which', side_effect=which):
            self.assertEqual(recognition_provider(), 'SongRec')
        with patch('nowplaying.shutil.which', return_value=None):
            self.assertIsNone(recognition_provider())
    def test_audd_mock_upload(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        with tempfile.TemporaryDirectory() as dirname:
            p = Path(dirname) / 'clip.wav'
            p.write_bytes(b'RIFF' + b'0' * 256)
            with patch('nowplaying.urllib.request.urlopen') as urlopen:
                urlopen.return_value.__enter__.return_value = Response()
                with patch('nowplaying.json.load', return_value={'status': 'success', 'result': {'artist':'Test','title':'Song'}}):
                    self.assertEqual(audd_recognize(p, 'TOKEN'), 'Test — Song')
                req = urlopen.call_args.args[0]
                self.assertEqual(req.full_url, 'https://api.audd.io/')
                self.assertIn(b'filename="radio.wav"', req.data)
                self.assertIn(b'TOKEN', req.data)

if __name__ == '__main__': unittest.main()
