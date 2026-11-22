#!/usr/bin/env python3
"""LoboViejo79 Radio 2.2 — favoritas, listas y reconocimiento de canciones."""
import csv
import curses
import gzip
import json
import threading
import queue
from datetime import datetime
import locale
import os
import select
import socket
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from library import Library, DEFAULT_LIST, STATE_DIR, station_record, valid_stream
from nowplaying import normalize_metadata, get_mpv_metadata, recognition_provider, recognize_stream

BASE = Path(__file__).resolve().parent
API_HOSTS = ('de1.api.radio-browser.info', 'nl1.api.radio-browser.info', 'at1.api.radio-browser.info')


def clean(t):
    return ''.join(ch for ch in unicodedata.normalize('NFKD', str(t)) if not unicodedata.combining(ch)).casefold()


def short(s, n):
    s = str(s).replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    return s[:max(0, n - 1)] + ('…' if len(s) > n else '') if n > 0 else ''


def load_catalog():
    stations = []
    with gzip.open(BASE / 'catalog.csv.gz', 'rt', encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            url = (r.get('url') or '').strip()
            if not valid_stream(url):
                continue
            stations.append(station_record({**r, 'id': r.get('stationuuid') or url}))
    return stations


def radio_api(path, timeout=5):
    for host in API_HOSTS:
        try:
            req = urllib.request.Request('https://' + host + path,
                                         headers={'User-Agent': 'LoboViejo79Radio/2.2 (desktop terminal player)'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except (OSError, ValueError):
            continue
    raise RuntimeError('Los servidores Radio Browser no respondieron')

class Player:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='loboviejo79-radio-')
        self.sock = str(Path(self.tmp.name) / 'mpv.sock')
        self.proc = None
        self.volume = 65
        self.paused = False
        self.current = None
        self.error = ''
        self.cava = None
        self.cava_buf = b''
        self.bars = [0] * 32
        self.last_bars = 0
        self.now_playing = ''
        self.track_source = ''
        self.last_metadata_check = 0.0
        self.cava_conf = Path(self.tmp.name) / 'cava.conf'
        self.cava_conf.write_text('[general]\n' 'bars = 32\n' 'framerate = 20\n'
                                  '[input]\n' 'method = pulse\n' 'source = auto\n'
                                  '[output]\n' 'method = raw\n' 'raw_target = /dev/stdout\n'
                                  'data_format = ascii\n' 'ascii_max_range = 12\n', encoding='utf-8')
    def play(self, st):
        self.stop()
        self.current = st
        self.error = ''
        self.paused = False
        self.now_playing = ''
        self.track_source = ''
        self.last_metadata_check = 0.0
        # '--' ensures the URL is never interpreted as a command-line switch.
        args = ['mpv', '--no-config', '--no-video', '--really-quiet', '--terminal=no',
                '--idle=yes', '--force-window=no', '--cache=yes', '--cache-secs=10',
                '--network-timeout=15', '--volume=' + str(self.volume),
                '--input-ipc-server=' + self.sock]
        try:
            self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            for _ in range(30):
                if Path(self.sock).exists(): break
                if self.proc.poll() is not None: raise RuntimeError('mpv terminó inesperadamente')
                time.sleep(.05)
            self.command(['loadfile', st['url'], 'replace'])
        except (OSError, RuntimeError) as exc:
            self.error = str(exc)
        self.start_cava()
    def command(self, cmd):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sk:
                sk.settimeout(.5)
                sk.connect(self.sock)
                sk.sendall((json.dumps({'command': cmd}) + '\n').encode())
            return True
        except OSError:
            self.error = 'No se pudo comunicar con mpv'
            return False
    def poll_metadata(self):
        if not self.current or not self.proc or self.proc.poll() is not None:
            return ''
        if time.monotonic() - self.last_metadata_check < 2.5:
            return ''
        self.last_metadata_check = time.monotonic()
        try:
            title = normalize_metadata(get_mpv_metadata(self.sock), self.current['name'])
        except (OSError, ValueError):
            return ''
        if title and (title != self.now_playing or self.track_source != 'ICY'):
            self.now_playing = title
            self.track_source = 'ICY'
            return title
        return ''

    def change_vol(self, d):
        self.volume = max(0, min(100, self.volume + d))
        if self.proc: self.command(['set_property', 'volume', self.volume])
    def pause(self):
        if self.proc:
            self.paused = not self.paused
            self.command(['set_property', 'pause', self.paused])
    def start_cava(self):
        if self.cava and self.cava.poll() is None: return
        try:
            self.cava = subprocess.Popen(['cava', '-p', str(self.cava_conf)], stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, bufsize=0, start_new_session=True)
            os.set_blocking(self.cava.stdout.fileno(), False)
        except OSError:
            self.error = 'Cava no pudo iniciarse'
    def poll_bars(self):
        if not self.cava or self.cava.poll() is not None: return
        try:
            while select.select([self.cava.stdout], [], [], 0)[0]:
                chunk = os.read(self.cava.stdout.fileno(), 65536)
                if not chunk: break
                self.cava_buf += chunk
                if len(self.cava_buf) > 16000: self.cava_buf = self.cava_buf[-16000:]
            if b'\n' in self.cava_buf:
                *lines, self.cava_buf = self.cava_buf.split(b'\n')
                # latest line preserves responsiveness if frames accumulate
                values = lines[-1].decode('ascii', errors='ignore').strip().strip(';').split(';')
                nums = [max(0, min(12, int(float(v)))) for v in values if v.strip()]
                if nums: self.bars = nums[:64]; self.last_bars = time.monotonic()
        except (OSError, ValueError): pass
    def stop(self):
        if self.proc:
            self.proc.terminate()
            try: self.proc.wait(timeout=.5)
            except subprocess.TimeoutExpired: self.proc.kill(); self.proc.wait()
        self.proc = None
        self.current = None
        self.paused = False
        self.now_playing = ''
        self.track_source = ''
        try: Path(self.sock).unlink(missing_ok=True)
        except OSError: pass
    def close(self):
        self.stop()
        if self.cava:
            self.cava.terminate()
            try: self.cava.wait(timeout=.5)
            except subprocess.TimeoutExpired: self.cava.kill(); self.cava.wait()
        self.tmp.cleanup()

class App:
    """Interfaz en pantalla completa. Estado de listas separado del catálogo."""
    def __init__(self, screen, stations, library):
        self.scr = screen
        self.all = stations
        self.library = library
        self.countries = Counter((s['code'], s['country']) for s in stations)
        self.codes = sorted(self.countries, key=lambda x: clean(x[1]))
        self.code = None
        self.query = ''
        self.mode = 'countries'
        self.list_name = DEFAULT_LIST
        self.items = []
        self.sel = 0
        self.scroll = 0
        self.player = Player()
        self.msg = 'F: favoritas   I: identificar canción   L: listas   ?: ayuda'
        self.ident_queue = queue.Queue()
        self.ident_thread = None
        self.last_track_written = None

        if library.migrated:
            self.msg = 'Se importaron tus favoritas de la versión 1.0 sin borrar el archivo anterior.'
        self.refresh()

    def remember_track(self, title, source, station):
        if not title or not station:
            return
        stamp = (station.get('id'), title)
        if stamp == self.last_track_written:
            return
        self.last_track_written = stamp
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
            dest = STATE_DIR / 'historial_canciones.jsonl'
            with os.fdopen(os.open(dest, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600), 'a', encoding='utf-8') as stream:
                stream.write(json.dumps({'fecha': datetime.now().astimezone().isoformat(timespec='seconds'),
                                         'radio': station['name'], 'cancion': title, 'origen': source},
                                        ensure_ascii=False) + '\n')
        except OSError:
            pass  # historial opcional; nunca interrumpe la reproducción

    def identify_current(self):
        station = self.player.current
        if not station:
            self.msg = 'Primero reproducí una emisora con Enter.'
            return
        if self.ident_thread and self.ident_thread.is_alive():
            self.msg = 'Ya se está identificando una muestra de audio…'
            return
        provider = recognition_provider()
        if not provider:
            self.msg = 'Falta ffmpeg + SongRec o un token AudD. Consultá el README.'
            return
        self.msg = f'Escuchando 12 segundos para identificar con {provider}…'
        def worker(record):
            try:
                song, origin = recognize_stream(record['url'])
                self.ident_queue.put((record['id'], song, origin, None))
            except Exception as exc:
                self.ident_queue.put((record['id'], '', '', str(exc)))
        self.ident_thread = threading.Thread(target=worker, args=(dict(station),), daemon=True)
        self.ident_thread.start()

    def poll_recognition(self):
        while True:
            try:
                radio_id, track, provider, error = self.ident_queue.get_nowait()
            except queue.Empty:
                return
            if not self.player.current or self.player.current['id'] != radio_id:
                continue  # la persona cambió de emisora durante el análisis
            if error:
                self.msg = 'No se pudo identificar: ' + error
            elif not track:
                self.msg = 'No se reconoció la canción. Probá cuando suene otro tema.'
            else:
                self.player.now_playing = track
                self.player.track_source = provider
                self.msg = '♪ Identificada por ' + provider + ': ' + track
                self.remember_track(track, provider, self.player.current)

    def switch(self, mode, name=None):
        self.mode = mode
        if name is not None:
            self.list_name = name
        self.query = ''
        self.refresh()

    def refresh(self, keep_id=None):
        if self.mode == 'countries':
            self.items = [c for c in self.codes if clean(self.query) in clean(c[1] + ' ' + c[0])]
        elif self.mode == 'playlists':
            self.items = [name for name in self.library.names() if clean(self.query) in clean(name)]
        elif self.mode in ('favorites', 'playlist'):
            name = DEFAULT_LIST if self.mode == 'favorites' else self.list_name
            self.items = [s for s in self.library.stations(name)
                          if clean(self.query) in clean(s['name'] + ' ' + s['country'] + ' ' + s['code'])]
        else:
            raw = self.all if self.mode == 'global' else [s for s in self.all if s['code'] == self.code]
            q = clean(self.query)
            self.items = [s for s in raw if q in clean(s['name'] + ' ' + s['country'] + ' ' + s['codec'])]
            self.items.sort(key=lambda s: (-s.get('votes', 0), clean(s['name'])))
        self.sel = 0
        self.scroll = 0
        if keep_id is not None:
            for i, record in enumerate(self.items):
                if isinstance(record, dict) and record.get('id') == keep_id:
                    self.sel = i
                    break

    def selected_station(self):
        if not self.items or self.mode in ('countries', 'playlists'):
            return None
        return self.items[self.sel]

    def enter(self):
        if not self.items:
            self.msg = 'No hay elementos para seleccionar.'
            return
        item = self.items[self.sel]
        if self.mode == 'countries':
            self.code = item[0]
            self.switch('stations')
        elif self.mode == 'playlists':
            self.switch('favorites' if item == DEFAULT_LIST else 'playlist', item)
        else:
            self.player.play(item)
            self.msg = 'Conectando: ' + item['name']

    def toggle_fav(self):
        selected = self.selected_station()
        if not selected:
            self.msg = 'Seleccioná una emisora antes de pulsar A.'
            return
        try:
            added = self.library.toggle_favorite(selected)
        except (OSError, ValueError) as exc:
            self.msg = 'No se pudo guardar: ' + str(exc)
            return
        self.msg = ('♥ Agregada a Mis favoritas: ' if added else 'Eliminada de Mis favoritas: ') + selected['name']
        if self.mode == 'favorites':
            previous = self.sel
            self.refresh(keep_id=selected['id'])
            self.sel = min(previous, max(0, len(self.items) - 1))

    def remove_from_list(self):
        station = self.selected_station()
        if not station or self.mode not in ('favorites', 'playlist'):
            self.msg = 'Usá X desde Mis favoritas o dentro de una lista personal.'
            return
        name = DEFAULT_LIST if self.mode == 'favorites' else self.list_name
        if not self.confirm(f'¿Quitar "{short(station["name"], 35)}" de "{short(name, 22)}"?'):
            self.msg = 'Operación cancelada.'
            return
        old_selection = self.sel
        try:
            self.library.remove(name, station)
            self.refresh()
            self.sel = min(old_selection, max(0, len(self.items) - 1))
            self.msg = f'Emisora quitada de {name}. No se borró de otras listas.'
        except OSError as exc:
            self.msg = f'No se pudo modificar la lista: {exc}'

    def new_playlist(self):
        name = self.prompt('Nombre de la nueva lista: ', maxlen=55)
        if name is None:
            return
        try:
            new_name = self.library.create(name)
            self.switch('playlist', new_name)
            self.msg = f'Lista "{new_name}" creada. Elegí una radio y pulsá P para agregarla.'
        except (ValueError, OSError) as exc:
            self.msg = str(exc)

    def rename_playlist(self):
        if self.mode == 'playlists' and self.items:
            name = self.items[self.sel]
        elif self.mode == 'playlist':
            name = self.list_name
        else:
            self.msg = 'Entrá a Mis listas (L) para renombrar una lista.'
            return
        if name == DEFAULT_LIST:
            self.msg = 'La lista principal Mis favoritas conserva su nombre.'
            return
        new = self.prompt('Nuevo nombre de lista: ', default=name, maxlen=55)
        if new is None:
            return
        try:
            self.library.rename(name, new)
            if self.mode == 'playlist':
                self.list_name = new
            self.refresh()
            self.msg = f'Lista renombrada a {new}.'
        except (ValueError, OSError) as exc:
            self.msg = str(exc)

    def delete_playlist(self):
        if self.mode == 'playlists' and self.items:
            name = self.items[self.sel]
        elif self.mode == 'playlist':
            name = self.list_name
        else:
            self.msg = 'Para borrar una lista, abrí Mis listas (L).'
            return
        if name == DEFAULT_LIST:
            self.msg = 'Mis favoritas no se puede borrar. Podés quitar emisoras con X.'
            return
        if not self.confirm(f'¿Borrar la lista "{short(name, 34)}"?'):
            return
        try:
            self.library.delete(name)
            if self.mode == 'playlist':
                self.switch('playlists')
            else:
                self.refresh()
            self.msg = f'Lista "{name}" eliminada. Las demás listas siguen intactas.'
        except (ValueError, OSError) as exc:
            self.msg = str(exc)

    def add_to_playlist(self):
        station = self.selected_station()
        if not station:
            self.msg = 'Elegí una radio y presioná P para agregarla a una lista.'
            return
        options = self.library.names()
        index = self.choose('Elegí una lista para agregar la emisora', options)
        if index is None:
            return
        name = options[index]
        try:
            added = self.library.add(name, station)
            self.msg = (f'✓ {station["name"]} agregada a "{name}".' if added
                        else f'Esa emisora ya está en "{name}".')
        except (OSError, ValueError) as exc:
            self.msg = str(exc)

    def reorder(self, offset):
        station = self.selected_station()
        if not station or self.mode not in ('favorites', 'playlist'):
            self.msg = 'El orden manual se modifica dentro de Mis favoritas o una lista.'
            return
        if self.query:
            self.msg = 'Limpiá el filtro (/) para reordenar sin ocultar emisoras.'
            return
        name = DEFAULT_LIST if self.mode == 'favorites' else self.list_name
        try:
            if self.library.move(name, station, offset):
                self.refresh(keep_id=station['id'])
                self.msg = 'Orden guardado automáticamente.'
            else:
                self.msg = 'Ya estás en el primer o último lugar.'
        except OSError as exc:
            self.msg = 'No se pudo reordenar: ' + str(exc)

    def manual_station(self):
        name = self.prompt('Nombre de la emisora: ', maxlen=90)
        if not name:
            return
        url = self.prompt('URL del stream (https://...): ', maxlen=500)
        if url is None:
            return
        if not valid_stream(url):
            self.msg = 'La URL debe ser HTTP(S) y no contener espacios.'
            return
        country = self.prompt('País (opcional): ', maxlen=70)
        if country is None:
            return
        st = {'id': 'manual:' + url, 'name': name, 'country': country or 'Personal',
              'code': '★', 'url': url, 'codec': '', 'bitrate': '', 'votes': 0}
        try:
            added = self.library.add(DEFAULT_LIST, st)
            self.switch('favorites')
            self.refresh(keep_id=st['id'])
            self.msg = ('Emisora personalizada guardada en favoritas.' if added
                        else 'Esa URL ya estaba guardada en tus favoritas.')
        except (OSError, ValueError) as exc:
            self.msg = str(exc)

    def export_playlist(self):
        name = self.list_name if self.mode == 'playlist' else DEFAULT_LIST
        if self.mode == 'playlists' and self.items:
            name = self.items[self.sel]
        try:
            path = self.library.export_m3u(name)
            self.msg = f'Lista exportada ({len(self.library.stations(name))} emisoras): {path}'
        except (OSError, ValueError) as exc:
            self.msg = 'No se pudo exportar: ' + str(exc)

    def update_online(self):
        if self.mode != 'stations':
            self.msg = 'Para actualizar, abrí primero un país (B > Enter).'
            return
        self.msg = 'Consultando Radio Browser…'
        self.render()
        try:
            path = ('/json/stations/bycountrycodeexact/' + urllib.parse.quote(self.code)
                    + '?hidebroken=true&order=votes&reverse=true&limit=500')
            new = radio_api(path)
            if not isinstance(new, list):
                raise ValueError('La API no devolvió una lista de emisoras')
            found = {}
            for s in new:
                if not isinstance(s, dict):
                    continue
                url = s.get('url_resolved') or s.get('url') or ''
                if not valid_stream(url):
                    continue
                st = station_record({**s, 'id': s.get('stationuuid') or url, 'url': url})
                found[st['id']] = st
            if not found:
                raise ValueError('La API no devolvió emisoras utilizables')
            self.all = [r for r in self.all if r['code'] != self.code] + list(found.values())
            self.query = ''
            self.refresh()
            self.msg = f'Actualizadas {len(found)} radios de {self.code} (solo sesión actual).'
        except (RuntimeError, ValueError, OSError) as exc:
            self.msg = 'No se pudo actualizar; catálogo local intacto: ' + str(exc)

    def prompt(self, title, default='', maxlen=90):
        """Campo de texto. Devuelve None cuando se cancela con Escape."""
        h, w = self.scr.getmaxyx()
        if h < 12 or w < 40:
            self.msg = 'Ampliá la terminal para escribir.'
            return None
        chars = list(default)
        previous_timeout = 70
        try:
            curses.curs_set(1)
            self.scr.timeout(-1)
            while True:
                h, w = self.scr.getmaxyx()
                row = h - 3
                self.scr.move(row, 0)
                self.scr.clrtoeol()
                self.put(row, 1, short(title, w - 3), curses.A_BOLD | curses.color_pair(1))
                self.scr.move(row + 1, 0)
                self.scr.clrtoeol()
                self.put(row + 1, 2, short(''.join(chars), w - 5))
                pos = min(len(''.join(chars)), max(0, w - 6))
                self.scr.move(row + 1, 2 + pos)
                self.scr.refresh()
                try:
                    key = self.scr.get_wch()
                except curses.error:
                    continue
                if key in ('\n', '\r', curses.KEY_ENTER, 10, 13):
                    return ''.join(chars).strip()
                if key in ('\x1b', 27):
                    return None
                if key in (curses.KEY_BACKSPACE, curses.KEY_DC, '\x7f', '\b', 127, 8):
                    if chars:
                        chars.pop()
                elif isinstance(key, str) and key.isprintable() and len(chars) < maxlen:
                    chars.append(key)
        finally:
            try: curses.curs_set(0)
            except curses.error: pass
            self.scr.timeout(previous_timeout)

    def confirm(self, title):
        h, w = self.scr.getmaxyx()
        self.scr.timeout(-1)
        try:
            self.put(h - 3, 1, ' ' * (w - 3))
            self.put(h - 3, 1, short(title + ' [s/N]', w - 3), curses.A_BOLD | curses.color_pair(1))
            self.scr.refresh()
            key = self.scr.getch()
            return key in (ord('s'), ord('S'), ord('y'), ord('Y'))
        finally:
            self.scr.timeout(70)

    def choose(self, title, options):
        """Selector modal sin bibliotecas TUI externas."""
        if not options:
            return None
        selection = 0
        offset = 0
        self.scr.timeout(-1)
        try:
            while True:
                h, w = self.scr.getmaxyx()
                area = min(len(options), max(1, h - 9), 12)
                width = min(w - 4, 68)
                x = max(1, (w - width) // 2)
                y = max(1, (h - area - 4) // 2)
                for row in range(area + 4):
                    self.put(y + row, x, ' ' * width, curses.color_pair(4))
                self.put(y, x + 2, short(title, width - 4), curses.A_BOLD | curses.color_pair(4))
                self.put(y + 1, x + 2, '↑ ↓: elegir · Enter: aceptar · Esc: cancelar', curses.color_pair(4))
                if selection < offset:
                    offset = selection
                elif selection >= offset + area:
                    offset = selection - area + 1
                for k, idx in enumerate(range(offset, min(offset + area, len(options)))):
                    text = f'{idx + 1:>2}. {options[idx]}'
                    attr = curses.A_REVERSE | curses.A_BOLD if selection == idx else curses.color_pair(4)
                    self.put(y + k + 2, x + 2, short(text, width - 4), attr)
                self.scr.refresh()
                key = self.scr.getch()
                if key in (27, ord('q'), ord('Q')):
                    return None
                if key in (10, 13, curses.KEY_ENTER):
                    return selection
                if key in (curses.KEY_UP, ord('k')):
                    selection = max(0, selection - 1)
                elif key in (curses.KEY_DOWN, ord('j')):
                    selection = min(len(options) - 1, selection + 1)
        finally:
            self.scr.timeout(70)

    def help(self):
        message = [
            'LOBOVIEJO79 RADIO • AYUDA',
            'F: Mis favoritas     A: marcar / desmarcar favorita',
            'L: Mis listas        N: crear nueva lista',
            'P: agregar radio a una lista   X: quitar radio de lista',
            'T: renombrar lista   D: borrar lista (con confirmación)',
            '[: subir posición de radio   ]: bajar posición',
            'M: agregar radio propia por URL     E: exportar M3U8',
            'B: países  G: todas las radios  /: buscar  U: actualizar país',
            'I: identificar audio (SongRec o AudD) | canción ICY automática',
            'Enter: abrir / escuchar     Espacio: pausar',
            '+ -: volumen    S: detener    Q: salir',
            'Esc / Retroceso: volver   ?: mostrar esta ayuda',
            'Presioná cualquier tecla para cerrar la ayuda…',
        ]
        self.scr.timeout(-1)
        try:
            while True:
                self.render()
                h, w = self.scr.getmaxyx()
                if h < len(message) + 3 or w < 58:
                    self.put(h - 3, 1, 'Ampliá la terminal para mostrar ayuda.')
                    self.scr.refresh()
                    self.scr.getch()
                    return
                top = max(2, (h - len(message) - 2) // 2)
                width = min(w - 2, 78)
                x = (w - width) // 2
                for row in range(len(message) + 2):
                    self.put(top + row, x, ' ' * width, curses.color_pair(4))
                for i, line in enumerate(message):
                    self.put(top + i + 1, x + 2, line, curses.A_BOLD if i == 0 else curses.color_pair(4))
                self.scr.refresh()
                self.scr.getch()
                return
        finally:
            self.scr.timeout(70)

    def search(self):
        query = self.prompt('Buscar / filtrar (vacío = ver todas): ', default=self.query, maxlen=90)
        if query is not None:
            self.query = query
            self.refresh()

    def back(self):
        if self.mode == 'stations':
            self.switch('countries')
        elif self.mode == 'playlist':
            self.switch('playlists')
        else:
            self.switch('countries')

    def put(self, y, x, val, attr=0):
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h or x >= w or x < 0:
            return
        try:
            self.scr.addnstr(y, x, str(val), max(0, w - x - 1), attr)
        except curses.error:
            pass

    def render(self):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        if h < 20 or w < 58:
            self.put(0, 0, 'Ampliá la terminal (mínimo 58×20)')
            self.scr.refresh()
            return
        self.put(0, 1, '◉ LOBOVIEJO79 RADIO 2.2  |  TERMINAL EDITION', curses.A_BOLD | curses.color_pair(1))
        self.put(1, 2, f'♥ {len(self.library.stations()):,} favoritas    ' +
                 f'♫ {len(self.library.names())} listas    {len(self.all):,} emisoras / {len(self.codes)} grupos  |  YouTube @LoboViejo79'.replace(',', '.'), curses.color_pair(2))
        titles = {
            'countries': 'EXPLORAR PAÍSES',
            'stations': f'EMISORAS DE {self.code}',
            'global': 'TODAS LAS RADIOS',
            'favorites': '♥ MIS FAVORITAS',
            'playlists': '♫ MIS LISTAS',
            'playlist': '♫ ' + self.list_name.upper(),
        }
        self.put(3, 2, f'{titles[self.mode]}   •   {len(self.items):,} elementos   •   buscar: {self.query or "—"}',
                 curses.A_BOLD)
        bottom = h - 11
        visible = max(1, bottom - 4)
        if self.sel < self.scroll:
            self.scroll = self.sel
        if self.sel >= self.scroll + visible:
            self.scroll = self.sel - visible + 1
        for row, idx in enumerate(range(self.scroll, min(len(self.items), self.scroll + visible)), 4):
            item = self.items[idx]
            if self.mode == 'countries':
                code, country = item
                line = f' {code:<3}   {country:<39} {self.countries[item]:>6} radios'
            elif self.mode == 'playlists':
                qty = len(self.library.stations(item))
                icon = '♥' if item == DEFAULT_LIST else '♫'
                line = f' {icon} {item:<50} {qty:>5} emisoras'
            else:
                mark = '♥' if self.library.contains(DEFAULT_LIST, item) else '·'
                playing = '▶' if (self.player.current and self.player.current['id'] == item['id']) else ' '
                line = (f' {playing}{mark} {short(item["name"], 46):<46} '
                        f'{item["code"]:<3} {item.get("codec", ""):<6} {item.get("bitrate", "")} kbps')
            attr = curses.A_REVERSE | curses.A_BOLD if idx == self.sel else (curses.color_pair(2) if idx % 2 == 0 else 0)
            self.put(row, 1, short(line, w - 3), attr)
        if not self.items:
            help_text = ('No hay listas. Creá una con N.' if self.mode == 'playlists'
                         else 'Tu lista está vacía. Buscá emisoras con B o G y guardalas con A / P.'
                         if self.mode in ('favorites', 'playlist')
                         else 'Sin resultados. Probá otra búsqueda.')
            self.put(5, 2, help_text, curses.color_pair(2))
        if len(self.items) > visible:
            self.put(bottom - 1, 2, f'{self.scroll + 1}–{min(len(self.items), self.scroll + visible)} de {len(self.items)}', curses.A_DIM)
        self.put(bottom, 1, '─' * (w - 3), curses.color_pair(1))
        cur = self.player.current
        status = ('⏸ PAUSA' if self.player.paused else '▶ EN VIVO') if cur else '■ SIN REPRODUCIR'
        self.put(bottom + 1, 2, f'{status}  •  {short(cur["name"], max(5, w - 32)) if cur else "Elegí una radio y pulsá Enter"}',
                 curses.A_BOLD | curses.color_pair(1))
        track = self.player.now_playing if cur else ''
        provider = self.player.track_source if track else ''
        self.put(bottom + 2, 2, '♪ SUENA: ' + short(track, max(12, w - 23)) +
                 (f' [{provider}]' if provider else '') if track else '♪ SUENA: esperando datos de la emisora · I para identificar',
                 curses.A_BOLD | curses.color_pair(3))
        self.put(bottom + 3, 2, f'VOLUMEN {self.player.volume:3d}%  ' +
                 '▓' * (self.player.volume // 5) + '░' * (20 - self.player.volume // 5))
        self.player.poll_bars()
        levels = self.player.bars if cur and not self.player.paused else [0] * 32
        num = min(len(levels), max(1, (w - 6) // 2))
        for i in range(num):
            val = levels[int(i * len(levels) / num)]
            for row in range(3):
                band = min(4, max(0, val - 4 * (2 - row)))
                symbol = (' ', '▂', '▄', '▆', '█')[band]
                self.put(bottom + 4 + row, 2 + i * 2, symbol, curses.color_pair(3 if row == 0 else 1))
        self.put(h - 3, 2, short(self.player.error or self.msg, w - 5), curses.A_DIM)
        self.put(h - 2, 2, short('F ♥ favoritas  A ♥ guardar  I identificar  L listas  N nueva  M URL  E exportar  ? ayuda', w - 5),
                 curses.A_BOLD)
        self.put(h - 1, 2, short('↑↓ elegir  Enter escuchar  / buscar  B países  G todas  [ ] ordenar  +/- volumen  Q salir', w - 5),
                 curses.A_DIM)
        self.scr.refresh()

    def run(self):
        curses.curs_set(0)
        curses.use_default_colors()
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_WHITE, -1)
        curses.init_pair(3, curses.COLOR_GREEN, -1)
        curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)
        self.scr.keypad(True)
        self.scr.timeout(70)
        try:
            while True:
                new_title = self.player.poll_metadata()
                if new_title:
                    self.remember_track(new_title, 'ICY', self.player.current)
                self.poll_recognition()
                self.render()
                k = self.scr.getch()
                if k == -1:
                    continue
                if k in (ord('q'), ord('Q')):
                    break
                if k in (curses.KEY_DOWN, ord('j')):
                    self.sel = min(max(0, len(self.items) - 1), self.sel + 1)
                elif k in (curses.KEY_UP, ord('k')):
                    self.sel = max(0, self.sel - 1)
                elif k == curses.KEY_NPAGE:
                    self.sel = min(max(0, len(self.items) - 1), self.sel + 10)
                elif k == curses.KEY_PPAGE:
                    self.sel = max(0, self.sel - 10)
                elif k in (10, 13, curses.KEY_ENTER):
                    self.enter()
                elif k == ord('/'):
                    self.search()
                elif k in (ord('b'), ord('B')):
                    self.switch('countries')
                elif k in (ord('g'), ord('G')):
                    self.switch('global')
                elif k in (ord('f'), ord('F')):
                    self.switch('favorites')
                elif k in (ord('l'), ord('L')):
                    self.switch('playlists')
                elif k in (ord('a'), ord('A')):
                    self.toggle_fav()
                elif k in (ord('p'), ord('P')):
                    self.add_to_playlist()
                elif k in (ord('n'), ord('N')):
                    self.new_playlist()
                elif k in (ord('t'), ord('T')):
                    self.rename_playlist()
                elif k in (ord('d'), ord('D')):
                    self.delete_playlist()
                elif k in (ord('x'), ord('X')):
                    self.remove_from_list()
                elif k in (ord('m'), ord('M')):
                    self.manual_station()
                elif k in (ord('e'), ord('E')):
                    self.export_playlist()
                elif k == ord('['):
                    self.reorder(-1)
                elif k == ord(']'):
                    self.reorder(1)
                elif k in (ord('u'), ord('U')):
                    self.update_online()
                elif k in (ord('?'), ord('h'), ord('H')):
                    self.help()
                elif k in (ord('r'), ord('R')):
                    self.refresh()
                elif k in (curses.KEY_BACKSPACE, 127, 27):
                    self.back()
                elif k == ord(' '):
                    self.player.pause()
                elif k in (ord('+'), ord('=')):
                    self.player.change_vol(5)
                elif k == ord('-'):
                    self.player.change_vol(-5)
                elif k in (ord('s'), ord('S')):
                    self.player.stop()
                elif k in (ord('i'), ord('I')):
                    self.identify_current()
        finally:
            self.player.close()


def main():
    locale.setlocale(locale.LC_ALL, '')
    if '--check-recognition' in sys.argv:
        provider = recognition_provider()
        print('Reconocimiento opcional:', provider or 'no configurado')
        print('ICY automático: disponible con mpv, sin credenciales')
        if not provider:
            print('Para identificar por audio: ffmpeg + songrec, o ffmpeg + LOBOVIEJO79_AUDD_TOKEN')
        return 0 if provider else 1
    if '--self-test' in sys.argv:
        stations = load_catalog()
        print('Catálogo:', len(stations), 'emisoras /', len({s['code'] for s in stations}), 'países')
        print('Muestra:', stations[0]['name'] if stations else '<vacío>')
        lib = Library()
        print('Biblioteca:', len(lib.stations()), 'favoritas /', len(lib.names()), 'listas')
        return 0 if stations else 1
    if '--list-favorites' in sys.argv:
        lib = Library()
        for s in lib.stations():
            print(f'{s["name"]} ({s["country"]}) | {s["url"]}')
        print(f'Total: {len(lib.stations())} favoritas')
        return 0
    if '--export-favorites' in sys.argv:
        index = sys.argv.index('--export-favorites')
        destination = sys.argv[index + 1] if len(sys.argv) > index + 1 else None
        path = Library().export_m3u(DEFAULT_LIST, destination)
        print('Favoritas exportadas:', path)
        return 0
    try:
        stations = load_catalog()
        lib = Library()
        if not stations:
            print('El catálogo local está vacío.', file=sys.stderr)
            return 1
        curses.wrapper(lambda s: App(s, stations, lib).run())
        return 0
    except (OSError, UnicodeError, csv.Error, ValueError, RuntimeError) as exc:
        print('LoboViejo79 Radio:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
