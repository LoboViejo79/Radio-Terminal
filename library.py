"""Biblioteca local: favoritos y listas reproducibles de LoboViejo79 Radio.

Sin dependencias externas. Las escrituras son atómicas y se conserva el archivo
favoritos.json de la versión 1.0 durante la migración.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

DEFAULT_LIST = 'Mis favoritas'
_STATE_ROOT = Path(os.environ.get('XDG_STATE_HOME') or (Path.home() / '.local/state'))
STATE_DIR = _STATE_ROOT / 'loboviejo79-radio'
# Ruta histórica: se consulta solamente para importar favoritos y listas existentes.
LEGACY_STATE_DIR = _STATE_ROOT / 'darktux-radio'


def migrate_previous_library(destination=STATE_DIR, origin=LEGACY_STATE_DIR):
    """Copia datos conocidos una única vez, sin borrar ni modificar la versión previa.

    Jamás reemplaza una biblioteca existente en el directorio de destino.
    """
    destination, origin = Path(destination), Path(origin)
    if destination.exists() or not origin.is_dir():
        return False
    valid = ('biblioteca.json', 'favoritos.json', 'historial_canciones.jsonl')
    if not any((origin / name).is_file() for name in valid):
        return False
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name in valid:
        f = origin / name
        if f.is_file() and not f.is_symlink():
            shutil.copy2(f, destination / name)
            (destination / name).chmod(0o600)
    old_export = origin / 'exportaciones'
    if old_export.is_dir() and not old_export.is_symlink():
        for f in old_export.glob('*.m3u8'):
            if f.is_file() and not f.is_symlink():
                target = destination / 'exportaciones'
                target.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copy2(f, target / f.name)
    return True



def valid_stream(url):
    """Admitir solo URL HTTP(S); no procesar esquemas locales o comandos."""
    from urllib.parse import urlsplit
    if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 for c in url):
        return False
    try:
        part = urlsplit(url)
        return part.scheme in ('http', 'https') and bool(part.hostname)
    except ValueError:
        return False


def station_record(raw):
    if not isinstance(raw, dict):
        raise ValueError('Registro de emisora no válido')
    url = str(raw.get('url') or '').strip()
    if not valid_stream(url):
        raise ValueError('La emisora no tiene una URL HTTP(S) válida')
    name = str(raw.get('name') or 'Sin nombre').strip()[:160]
    name = ''.join(ch for ch in name if ch.isprintable()) or 'Sin nombre'
    ident = str(raw.get('id') or raw.get('stationuuid') or url).strip() or url
    return {
        'id': ident[:512], 'name': name,
        'country': str(raw.get('country') or 'Sin país').strip()[:100],
        'code': str(raw.get('code') or raw.get('countrycode') or '??').strip().upper()[:10],
        'url': url,
        'codec': str(raw.get('codec') or '')[:24],
        'bitrate': str(raw.get('bitrate') or '')[:16],
        'votes': int(raw.get('votes') or 0) if str(raw.get('votes') or '0').lstrip('-').isdigit() else 0,
    }


def playlist_name(text):
    name = ' '.join(str(text or '').split())
    if not name or len(name) > 55 or any(ord(c) < 32 or c in '/\\' for c in name):
        raise ValueError('Usá un nombre de entre 1 y 55 caracteres, sin barras')
    return name


def file_name(name):
    norm = re.sub(r'[^\w .-]', '_', name, flags=re.UNICODE).strip(' ._')[:70]
    return (norm or 'lista') + '.m3u8'


class Library:
    def __init__(self, directory=STATE_DIR):
        self.directory = Path(directory).expanduser()
        if self.directory == STATE_DIR:
            migrate_previous_library()
        self.path = self.directory / 'biblioteca.json'
        self.legacy_path = self.directory / 'favoritos.json'
        self.collections = {DEFAULT_LIST: []}
        self.migrated = False
        self.load()

    def load(self):
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(data, dict) or data.get('version') != 2:
                    raise ValueError('Versión de biblioteca no reconocida')
                groups = data.get('collections')
                if not isinstance(groups, dict) or DEFAULT_LIST not in groups:
                    raise ValueError('Falta la lista Mis favoritas')
                result = {}
                for name, records in groups.items():
                    playlist_name(name)
                    if not isinstance(records, list):
                        raise ValueError('Formato inválido para la lista ' + name)
                    seen = set()
                    result[name] = []
                    for rec in records:
                        station = station_record(rec)
                        if station['id'] not in seen:
                            result[name].append(station)
                            seen.add(station['id'])
                self.collections = result
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError(f'No se puede leer {self.path}: {exc}. No se sobrescribió.') from exc
        elif self.legacy_path.is_file():
            try:
                data = json.loads(self.legacy_path.read_text(encoding='utf-8'))
                if not isinstance(data, dict):
                    raise ValueError('Se esperaba un mapa de favoritas')
                self.collections[DEFAULT_LIST] = [station_record(rec) for rec in data.values()]
            except (OSError, ValueError, TypeError) as exc:
                raise RuntimeError(f'No se puede migrar {self.legacy_path}: {exc}') from exc
            self.save()
            self.migrated = True

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = json.dumps({'version': 2, 'collections': self.collections}, ensure_ascii=False, indent=2) + '\n'
        temp = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.directory,
                                             prefix='.biblioteca-', suffix='.tmp', delete=False) as f:
                temp = Path(f.name)
                os.chmod(temp, 0o600)
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            temp.replace(self.path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    def names(self):
        return list(self.collections)

    def stations(self, name=DEFAULT_LIST):
        return list(self.collections[name])

    def contains(self, name, station):
        ident = station['id'] if isinstance(station, dict) else station
        return any(s['id'] == ident for s in self.collections[name])

    def add(self, name, station):
        record = station_record(station)
        if self.contains(name, record):
            return False
        self.collections[name].append(record)
        self.save()
        return True

    def remove(self, name, station):
        ident = station['id'] if isinstance(station, dict) else station
        records = self.collections[name]
        kept = [s for s in records if s['id'] != ident]
        if len(kept) == len(records):
            return False
        self.collections[name] = kept
        self.save()
        return True

    def toggle_favorite(self, station):
        if self.contains(DEFAULT_LIST, station):
            self.remove(DEFAULT_LIST, station)
            return False
        self.add(DEFAULT_LIST, station)
        return True

    def create(self, name):
        name = playlist_name(name)
        if any(n.casefold() == name.casefold() for n in self.collections):
            raise ValueError('Ya existe una lista con ese nombre')
        self.collections[name] = []
        self.save()
        return name

    def rename(self, original, new_name):
        if original == DEFAULT_LIST:
            raise ValueError('No se puede cambiar el nombre de Mis favoritas')
        new_name = playlist_name(new_name)
        if any(n != original and n.casefold() == new_name.casefold() for n in self.collections):
            raise ValueError('Ese nombre ya está en uso')
        if original not in self.collections:
            raise ValueError('No existe esa lista')
        self.collections = {new_name if n == original else n: v for n, v in self.collections.items()}
        self.save()
        return new_name

    def delete(self, name):
        if name == DEFAULT_LIST:
            raise ValueError('No se puede borrar Mis favoritas')
        del self.collections[name]
        self.save()

    def move(self, name, station, offset):
        records = self.collections[name]
        ident = station['id'] if isinstance(station, dict) else station
        index = next((i for i, s in enumerate(records) if s['id'] == ident), None)
        if index is None or not (0 <= index + offset < len(records)):
            return False
        records[index], records[index + offset] = records[index + offset], records[index]
        self.save()
        return True

    def export_m3u(self, name=DEFAULT_LIST, destination=None):
        if name not in self.collections:
            raise ValueError('Lista no encontrada')
        path = Path(destination).expanduser() if destination else self.directory / 'exportaciones' / file_name(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ['#EXTM3U']
        for st in self.collections[name]:
            title = st['name'].replace('\r', ' ').replace('\n', ' ')
            country = st['country'].replace('"', "'").replace('\r', ' ').replace('\n', ' ')
            lines.append(f'#EXTINF:-1 group-title="{country}",{title}')
            lines.append(st['url'])
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return path
