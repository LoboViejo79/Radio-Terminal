"""Tests sin usar emisoras externas: grabación mock + streaming HTTP local."""
import http.server
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recording import Recorder, safe_filename, recording_directory
from radio import App
from library import Library

STATION = {'id': 'radio-test', 'name': 'FM / Rock: Buenos Aires!',
           'url': 'http://127.0.0.1:9999/radio.mp3', 'code': 'AR', 'country': 'Argentina',
           'codec': 'MP3', 'votes': 5}


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_slug_removes_path_traversal(self):
        self.assertEqual(safe_filename('../ Radio Ñandú / 🎧'), 'Radio_Nandu')
        self.assertEqual(safe_filename('❤'), 'Emisora')

    def test_custom_directory(self):
        with patch.dict(os.environ, {'LOBOVIEJO79_RECORD_DIR': self.tmp.name}):
            self.assertEqual(recording_directory(), Path(self.tmp.name))

    def test_missing_ffmpeg_does_not_start(self):
        rec = Recorder(Path(self.tmp.name))
        with patch('recording.shutil.which', return_value=None):
            result, notice = rec.start(STATION)
        self.assertFalse(result)
        self.assertIn('ffmpeg', notice)
        self.assertIsNone(rec.proc)

    def test_rec_requires_current_station(self):
        class FakeScreen:
            pass
        app = App(FakeScreen(), [STATION], Library(Path(self.tmp.name) / 'library'))
        self.addCleanup(app.player.close)
        app.toggle_recording()
        self.assertIn('Primero reproducí', app.msg)
        app.player.current = STATION
        with patch.object(app.player.recorder, 'start', return_value=(True, '● REC iniciada')) as start:
            app.toggle_recording()
        start.assert_called_once_with(STATION)
        self.assertIn('● REC', app.msg)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg y ffprobe requeridos')
    def test_real_ffmpeg_grabs_audio_from_local_http_stream(self):
        """Stream de audio HTTP local: comprobación real de archivo y cierre limpio."""
        root = Path(self.tmp.name)
        sample = root / 'sample.mp3'
        generate = subprocess.run(
            ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
             '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100:duration=5',
             '-c:a', 'libmp3lame', '-b:a', '64k', str(sample)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15)
        if generate.returncode:
            self.skipTest('ffmpeg de pruebas sin libmp3lame')
        payload = sample.read_bytes()

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'audio/mpeg')
                self.end_headers()
                try:
                    while True:
                        for index in range(0, len(payload), 800):
                            self.wfile.write(payload[index:index + 800])
                            self.wfile.flush()
                            time.sleep(.085)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        loop = threading.Thread(target=server.serve_forever, daemon=True)
        loop.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        rec = Recorder(root / 'grabaciones')
        self.addCleanup(rec.stop)
        station = {**STATION, 'url': f'http://127.0.0.1:{server.server_port}/stream.mp3'}
        ok, info = rec.start(station)
        self.assertTrue(ok, info)
        self.assertTrue(rec.active)
        path = rec.path
        self.assertTrue(path.name.endswith('.mka'))
        self.assertIn('FM_Rock_Buenos_Aires', path.name)
        # El stream HTTP transmite datos reales a velocidad aproximada 1x.
        time.sleep(2.5)
        stop_text = rec.stop()
        self.assertIn('Grabación guardada:', stop_text, stop_text)
        self.assertGreater(path.stat().st_size, 1000)
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries',
             'stream=codec_name', '-of', 'default=noprint_wrappers=1', str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('codec_name=mp3', result.stdout)
        self.assertFalse(rec.active)
        self.assertEqual(list(rec.folder.glob('*.log')), [])


if __name__ == '__main__':
    unittest.main()
