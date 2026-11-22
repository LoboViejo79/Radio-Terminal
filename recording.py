"""Grabación opcional de audio streaming para LoboViejo79 Radio.

Captura directamente la fuente HTTP(S) con FFmpeg, sin depender de la
salida del monitor de audio ni de una grabadora de pantalla.
"""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import unicodedata


def recording_directory() -> Path:
    """Ruta elegida por el usuario; valor por defecto portable entre distros."""
    raw = os.environ.get('LOBOVIEJO79_RECORD_DIR', '').strip()
    return Path(raw).expanduser().resolve() if raw else Path.home() / 'Grabaciones' / 'LoboViejo79-Radio'


def safe_filename(text: str) -> str:
    """Evita barras, opciones de shell y nombres no válidos."""
    ascii_name = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    cleaned = re.sub(r'[^A-Za-z0-9_-]+', '_', ascii_name).strip('_-')
    return cleaned[:64] or 'Emisora'


class Recorder:
    """Una única grabación activa, finalizada limpiamente al detenerla."""

    def __init__(self, folder: Path | None = None):
        self.folder = Path(folder) if folder is not None else recording_directory()
        self.proc: subprocess.Popen | None = None
        self.path: Path | None = None
        self.started_at: float | None = None
        self.station_id: str | None = None
        self._log_handle = None
        self._log_path: Path | None = None

    @property
    def active(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    @property
    def elapsed(self) -> int:
        return max(0, int(time.monotonic() - self.started_at)) if self.started_at is not None else 0

    @property
    def elapsed_label(self) -> str:
        secs = self.elapsed
        return f'{secs // 3600:02}:{secs // 60 % 60:02}:{secs % 60:02}'

    def _close_log(self) -> None:
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None

    def _error_text(self) -> str:
        self._close_log()
        if not self._log_path or not self._log_path.is_file():
            return ''
        try:
            # No mostrar un mensaje inmenso en la TUI.
            return self._log_path.read_text(encoding='utf-8', errors='replace')[-350:].strip().splitlines()[-1]
        except (OSError, IndexError):
            return ''

    def _cleanup_log(self) -> None:
        self._close_log()
        if self._log_path:
            try:
                self._log_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._log_path = None

    def start(self, station: dict) -> tuple[bool, str]:
        """Inicia una grabación de la URL reproducida; devuelve (éxito, aviso)."""
        if self.proc is not None:
            return False, 'Ya hay una grabación en curso.'
        url = str(station.get('url', '')).strip()
        if not url.startswith(('http://', 'https://')) or any(ch.isspace() for ch in url):
            return False, 'La URL de la emisora no es válida para grabar.'
        if not shutil.which('ffmpeg'):
            return False, 'Falta ffmpeg. Instalalo con dnf, apt o pacman para grabar.'
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')
            target = self.folder / f'{safe_filename(station.get("name", "Emisora"))}_{timestamp}.mka'
            # Matroska Audio admite los códecs habituales de radio (MP3, AAC, Opus...).
            # Copiamos los paquetes de audio sin pérdida por recompresión.
            args = [
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostats', '-n',
                '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
                '-i', url, '-map', '0:a:0', '-vn', '-c:a', 'copy',
                '-f', 'matroska', str(target),
            ]
            self._log_path = self.folder / (target.stem + '.ffmpeg.log')
            self._log_handle = self._log_path.open('w', encoding='utf-8')
            self.proc = subprocess.Popen(args, stdin=subprocess.PIPE,
                                         stdout=subprocess.DEVNULL,
                                         stderr=self._log_handle,
                                         start_new_session=True)
            self.path = target
            self.station_id = station.get('id') or url
            self.started_at = time.monotonic()
            return True, f'● REC iniciada: {target.name}'
        except OSError as exc:
            self.proc = None
            self.path = None
            self.started_at = None
            self.station_id = None
            self._cleanup_log()
            return False, f'No se pudo iniciar la grabación: {exc}'

    def poll(self) -> str | None:
        """Detecta ffmpeg finalizado accidentalmente, sin bloquear la interfaz."""
        if self.proc is None or self.proc.poll() is None:
            return None
        code = self.proc.returncode
        path = self.path
        detail = self._error_text()
        try:
            bytes_written = path.stat().st_size if path else 0
        except OSError:
            bytes_written = 0
        good = bool(bytes_written > 0 and code == 0)
        self.proc = None
        self.path = None
        self.started_at = None
        self.station_id = None
        self._cleanup_log()
        if good:
            return f'Grabación finalizada: {path}'
        if path and not bytes_written:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        return 'La grabación terminó sin audio válido.' + (f' {detail}' if detail else '')

    def stop(self) -> str | None:
        """Finalización ordenada de Matroska. No elimina un archivo con audio."""
        proc = self.proc
        if proc is None:
            return None
        if proc.poll() is None:
            try:
                # El comando q permite a ffmpeg cerrar el contenedor correctamente.
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.write(b'q\n')
                    proc.stdin.flush()
                proc.wait(timeout=5)
            except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                if proc.poll() is None:
                    try:
                        proc.send_signal(signal.SIGINT)
                        proc.wait(timeout=4)
                    except (OSError, subprocess.TimeoutExpired):
                        if proc.poll() is None:
                            proc.terminate()
                            try:
                                proc.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                                proc.wait()
        if proc.stdin:
            proc.stdin.close()
        path = self.path
        detail = self._error_text()
        size = 0
        try:
            size = path.stat().st_size if path else 0
        except OSError:
            pass
        self.proc = None
        self.path = None
        self.started_at = None
        self.station_id = None
        self._cleanup_log()
        if size > 0:
            return f'⏹ Grabación guardada: {path} ({size / 1024 / 1024:.1f} MB)'
        if path:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        return 'No se guardó audio de la emisora.' + (f' {detail}' if detail else '')
