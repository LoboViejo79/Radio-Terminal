"""Consulta ICY desde mpv y reconocimiento opcional bajo demanda.

No necesita paquetes Python externos. Solo cuando se solicita reconocimiento,
usa ffmpeg + SongRec o, alternativamente, ffmpeg + API AudD con token.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def normalize_metadata(metadata, station_name=''):
    """Devuelve título anunciado por el stream, nunca inventa canción."""
    if not isinstance(metadata, dict):
        return ''
    normalized = {str(k).lower().replace('_', '-'): str(v).strip() for k, v in metadata.items()
                  if v is not None}
    # Preferencia: título ICY por pista, no el nombre genérico del stream.
    title = next((normalized.get(k, '') for k in ('icy-title', 'streamtitle', 'stream-title')
                  if normalized.get(k)), '')
    if not title:
        artist = normalized.get('artist') or normalized.get('album-artist')
        track = normalized.get('title')
        if artist and track:
            title = f'{artist} — {track}'
        elif track:
            title = track
    title = ' '.join(title.replace('\n', ' ').replace('\r', ' ').split())[:220]
    # La emisora suele informar solo su propio nombre: no mostrarlo como canción.
    if title.casefold() == station_name.strip().casefold():
        return ''
    return title


def get_mpv_metadata(sock_path, timeout=0.35):
    """Lee propiedad metadata usando IPC JSON (solo socket local de mpv)."""
    request_id = 8472
    packet = (json.dumps({'command': ['get_property', 'metadata'], 'request_id': request_id}) + '\n').encode()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sk:
        sk.settimeout(timeout)
        sk.connect(str(sock_path))
        sk.sendall(packet)
        received = b''
        while len(received) < 65536:
            chunk = sk.recv(4096)
            if not chunk:
                break
            received += chunk
            while b'\n' in received:
                line, received = received.split(b'\n', 1)
                try:
                    resp = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                if resp.get('request_id') == request_id and resp.get('error') == 'success':
                    return resp.get('data') or {}
    return {}


def audd_token():
    """Nombre nuevo, con compatibilidad para variables de entornos anteriores."""
    return (os.environ.get('LOBOVIEJO79_AUDD_TOKEN') or
            os.environ.get('DARKTUX_AUDD_TOKEN') or '').strip()


def recognition_provider():
    if not shutil.which('ffmpeg'):
        return None
    if shutil.which('songrec'):
        return 'SongRec'
    if audd_token():
        return 'AudD'
    return None


def parse_songrec(raw):
    """Extrae artista/título del JSON de SongRec (varias versiones)."""
    data = json.loads(raw)
    if not isinstance(data, dict):
        return ''
    track = data.get('track') or data.get('result') or data
    if not isinstance(track, dict):
        return ''
    title = str(track.get('title') or track.get('song') or '').strip()
    artist = str(track.get('subtitle') or track.get('artist') or '').strip()
    return f'{artist} — {title}' if artist and title else (title or '')


def audd_recognize(wav_path, token):
    """Envía a AudD 12 s de audio *solo* tras pulsar I; admite cuotas/costos."""
    boundary = 'LoboViejo79-' + uuid.uuid4().hex
    audio = Path(wav_path).read_bytes()
    if len(audio) > 2_000_000:
        raise RuntimeError('La muestra de audio es demasiado grande')
    parts = []
    for key, value in [('api_token', token), ('return', '')]:
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode())
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                  'filename="radio.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode() + audio + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    req = urllib.request.Request('https://api.audd.io/', data=b''.join(parts),
                                 headers={'Content-Type': 'multipart/form-data; boundary=' + boundary,
                                          'User-Agent': 'LoboViejo79Radio/2.2'}, method='POST')
    with urllib.request.urlopen(req, timeout=24) as resp:
        payload = json.load(resp)
    if payload.get('status') != 'success':
        error = payload.get('error') or {}
        raise RuntimeError('AudD: ' + str(error.get('error_message') or 'solicitud rechazada')[:130])
    result = payload.get('result')
    if not isinstance(result, dict):
        return ''
    artist = str(result.get('artist') or '').strip()
    title = str(result.get('title') or '').strip()
    return f'{artist} — {title}' if artist and title else title


def recognize_stream(url):
    """Graba una muestra de 12 s del URL (no del micrófono), la reconoce y borra."""
    provider = recognition_provider()
    if not provider:
        raise RuntimeError('Necesitás ffmpeg y SongRec, o ffmpeg + LOBOVIEJO79_AUDD_TOKEN')
    if not (url.startswith('https://') or url.startswith('http://')):
        raise RuntimeError('URL de streaming no compatible')
    with tempfile.TemporaryDirectory(prefix='loboviejo79-identifica-') as directory:
        dest = Path(directory) / 'radio.wav'
        args = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-rw_timeout', '15000000', '-i', url, '-t', '12', '-vn',
                '-ac', '1', '-ar', '11025', '-c:a', 'pcm_s16le', str(dest)]
        try:
            p = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               timeout=35, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('La emisora no entregó audio a tiempo') from exc
        if p.returncode != 0 or not dest.is_file() or dest.stat().st_size < 20000:
            raise RuntimeError('No se pudo capturar audio del stream (quizás usa un formato no compatible)')
        if provider == 'SongRec':
            try:
                rec = subprocess.run(['songrec', 'audio-file-to-recognized-song', str(dest)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                     timeout=28, check=False)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError('SongRec no respondió a tiempo') from exc
            if rec.returncode:
                raise RuntimeError('SongRec no pudo analizar el audio')
            try:
                track = parse_songrec(rec.stdout)
            except ValueError as exc:
                raise RuntimeError('SongRec devolvió un resultado no válido') from exc
        else:
            track = audd_recognize(dest, audd_token())
        return track, provider
