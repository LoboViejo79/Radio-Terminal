#!/usr/bin/env bash
# LoboViejo79 Radio 2.3: lanzador portátil en Linux (sin instalación de la app).
set -Eeuo pipefail
cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")"
export PYTHONIOENCODING=utf-8
export LANG="${LANG:-C.UTF-8}"

# Las consultas/exportaciones locales no requieren instalar mpv ni cava.
case "${1:-}" in
  --self-test|--list-favorites|--export-favorites|--check-recognition)
    if ! command -v python3 >/dev/null 2>&1; then
      echo 'Se necesita Python 3 para esta operación.' >&2
      exit 1
    fi
    exec python3 "$(pwd)/radio.py" "$@"
    ;;
esac

if [[ ! -t 0 || ! -t 1 ]]; then
  echo 'LoboViejo79 Radio necesita una terminal interactiva. Para exportar, usá --export-favorites.' >&2
  exit 1
fi

need=(python3 mpv cava ffmpeg)
missing=()
for bin in "${need[@]}"; do
  command -v "$bin" >/dev/null 2>&1 || missing+=("$bin")
done
if ((${#missing[@]})); then
  echo "Faltan componentes necesarios: ${missing[*]}"
  if [[ "${1:-}" == '--check' ]]; then
    exit 1
  fi
  if [[ "${LOBOVIEJO79_NO_INSTALL:-${DARKTUX_NO_INSTALL:-0}}" == 1 ]]; then
    echo 'Instalación automática deshabilitada (LOBOVIEJO79_NO_INSTALL=1).' >&2
    exit 1
  fi
  echo 'Podés instalar los paquetes que faltan usando el gestor de tu distribución.'
  read -r -p '¿Autorizás instalar las dependencias faltantes? [s/N] ' answer
  [[ "$answer" =~ ^[sSyY]$ ]] || exit 1
  installer=()
  if [[ $EUID -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then installer=(sudo)
    elif command -v doas >/dev/null 2>&1; then installer=(doas)
    else echo 'Se necesita sudo/doas para instalar dependencias.' >&2; exit 1; fi
  fi
  if command -v dnf >/dev/null 2>&1; then
    # Fedora distribuye el ejecutable ffmpeg en el paquete ffmpeg-free.
    fedora_pkgs=()
    for bin in "${missing[@]}"; do
      if [[ "$bin" == ffmpeg ]]; then fedora_pkgs+=(ffmpeg-free)
      else fedora_pkgs+=("$bin")
      fi
    done
    "${installer[@]}" dnf install -y "${fedora_pkgs[@]}"
  elif command -v apt-get >/dev/null 2>&1; then
    "${installer[@]}" apt-get update
    "${installer[@]}" apt-get install -y "${missing[@]}"
  elif command -v pacman >/dev/null 2>&1; then
    # En Arch el paquete se llama «python», aunque su comando sea «python3».
    arch_pkgs=()
    for bin in "${missing[@]}"; do
      if [[ "$bin" == python3 ]]; then arch_pkgs+=(python)
      else arch_pkgs+=("$bin")
      fi
    done
    "${installer[@]}" pacman -S --needed --noconfirm "${arch_pkgs[@]}"
  else
    echo 'Gestor de paquetes no reconocido. Instalá python3, mpv, cava y ffmpeg manualmente.' >&2
    exit 1
  fi
fi
for bin in "${need[@]}"; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Falta $bin tras comprobar las dependencias." >&2; exit 1; }
done
if [[ "${1:-}" == '--check' ]]; then
  echo 'OK: python3, mpv, cava y ffmpeg están disponibles.'
  exit 0
fi
if [[ ! -f catalog.csv.gz || ! -f radio.py || ! -f library.py || ! -f nowplaying.py || ! -f recording.py ]]; then
  echo 'Faltan archivos del programa. Mantené radio.sh, radio.py, library.py, nowplaying.py, recording.py y catalog.csv.gz juntos.' >&2
  exit 1
fi
exec python3 "$(pwd)/radio.py" "$@"
