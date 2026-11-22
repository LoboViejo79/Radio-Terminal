<div align="center">

# 📻 LoboViejo79 Radio

### 🎧 Terminal Edition v2.2 · Escuchá radios del mundo directamente desde Linux

**Una aplicación portátil de terminal, con emisoras por país, favoritas, listas personales, visualizador de audio e identificación de canciones.**

[![Linux](https://img.shields.io/badge/OS-Linux-1793D1?logo=linux&logoColor=white)](https://kernel.org/)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Bash](https://img.shields.io/badge/Ejecuci%C3%B3n-radio.sh-4EAA25?logo=gnubash&logoColor=white)](#-instalación-y-ejecución)
[![Radios](https://img.shields.io/badge/Emisoras-63.396-00A6A6)](#-catálogo-de-radios)
[![YouTube](https://img.shields.io/badge/YouTube-LoboViejo79-FF0000?logo=youtube&logoColor=white)](https://www.youtube.com/@LoboViejo79)

**📺 Canal:** [YouTube — LoboViejo79](https://www.youtube.com/@LoboViejo79)

![Vista del reproductor LoboViejo79 Radio en terminal](assets/captura-terminal.png)

*Vista de la interfaz de terminal. Los títulos que aparecen dependen de los metadatos transmitidos por la emisora.*

</div>

---

## 📊 Catálogo de radios

| 🌍 Contenido | 📻 Cantidad |
|:--|--:|
| **Emisoras en el catálogo incluido** | **63.396** |
| **Grupos de país o código** | **229** |
| **Emisoras identificadas con código AR (Argentina)** | **1.173** |

> ℹ️ Estas cifras corresponden a la base de datos **incluida en esta versión**, no al número de radios activas comprobadas en tiempo real. Algunas URL pueden dejar de funcionar, cambiar o no transmitir metadatos. La consulta a Radio Browser requiere Internet.

## ✨ Funciones principales

- 🌎 **Explorar por países:** encontrá emisoras organizadas por país.
- 🔎 **Buscar radios:** filtrá por nombre o explorá el catálogo global.
- ❤️ **Mis favoritas:** guardá las emisoras que más escuchás y accedé a ellas con `F`.
- 📂 **Listas personalizadas:** creá colecciones, agregá/quita radios, renombrá listas y ordená sus elementos.
- 🔗 **Radios por URL:** agregá una emisora no incluida en el catálogo.
- 📤 **Exportación M3U8:** reproducí tus favoritas en otros programas o incorporalas a Jellyfin.
- 🎛️ **Control de reproducción:** iniciar, pausar, detener y ajustar volumen sin salir de la terminal.
- 📈 **Barras de sonido:** visualizador de audio basado en `cava`.
- 🎶 **Nombre del tema en reproducción:** lectura automática de metadatos ICY cuando la radio los proporciona.
- 🎤 **Identificación por audio opcional:** presioná `I` para intentar reconocer una canción usando SongRec o AudD.
- 💾 **Guardado permanente:** favoritas, listas e historial permanecen entre ejecuciones.
- 🧳 **Portátil:** no se instala la aplicación como paquete; se ejecuta mediante `radio.sh`.

## 🐧 Instalación y ejecución

**Distribuciones objetivo:** Fedora (incluida Fedora 45), Debian, Arch Linux y derivadas que dispongan de los paquetes indicados.

1. Descargá el código y descomprimí el ZIP, o cloná el repositorio cuando esté publicado.
2. Abrí una terminal en la carpeta del proyecto.
3. Ejecutá:

```bash
bash radio.sh
```

El lanzador comprueba `python3`, `mpv` y `cava`. Si falta algo, **solicita autorización antes de instalar** dependencias del sistema mediante `dnf`, `apt-get` o `pacman`; no necesita `pip` ni Gum. Para impedir cualquier intento de instalación:

```bash
LOBOVIEJO79_NO_INSTALL=1 bash radio.sh
```

Si preferís instalar las dependencias vos mismo:

| Distribución | Comando |
|:--|:--|
| 🟦 Fedora | `sudo dnf install python3 mpv cava` |
| 🌀 Debian | `sudo apt update && sudo apt install python3 mpv cava` |
| 🏹 Arch / CachyOS | `sudo pacman -S --needed python mpv cava` |

> 🛠️ En Arch, el ejecutable `python3` viene con el paquete `python`; si el lanzador no lo encuentra, instalá ese paquete manualmente. Necesitás una terminal UTF-8 (preferentemente de al menos 100 × 30 caracteres) y una salida de audio configurada.

## ⌨️ Guía de comandos y teclas

### 🗺️ Navegación y búsqueda

| Tecla | Acción |
|:--:|:--|
| `↑` / `↓` | Mover la selección |
| `j` / `k` | Alternativa para navegar |
| `Re Pág` / `Av Pág` | Moverse diez posiciones |
| `Enter` | Entrar a un país/lista o reproducir la radio elegida |
| `B` | 🌍 Explorar países |
| `G` | 🌐 Ver todas las emisoras |
| `/` | 🔎 Buscar o filtrar en la vista actual |
| `U` | 🔄 Actualizar emisoras del país actual desde Radio Browser (sesión actual) |
| `R` | 🔃 Refrescar la vista |
| `Esc` / `Retroceso` | Volver a la pantalla anterior |
| `?` / `H` | ❔ Mostrar ayuda en pantalla |
| `Q` | 🚪 Salir |

### ❤️ Favoritas y listas personales

| Tecla | Acción |
|:--:|:--|
| `F` | ❤️ Abrir **Mis favoritas** |
| `A` | ❤️ Agregar o quitar la radio seleccionada de favoritas |
| `L` | 📂 Ver las listas personalizadas |
| `N` | ➕ Crear una lista |
| `P` | 📌 Agregar la radio a una lista elegida |
| `T` | ✏️ Cambiar el nombre de la lista |
| `D` | 🗑️ Borrar una lista (con confirmación) |
| `X` | ➖ Quitar una radio de la lista actual (con confirmación) |
| `[` / `]` | ↕️ Subir o bajar una emisora dentro de una lista |
| `M` | 🔗 Añadir una emisora manualmente por URL |
| `E` | 📤 Exportar la lista a `.m3u8` |

### 🔊 Reproductor y música

| Tecla | Acción |
|:--:|:--|
| `Espacio` | ⏯️ Pausar o continuar |
| `+` / `-` | 🔉 Subir o bajar volumen |
| `S` | ⏹️ Detener reproducción |
| `I` | 🎶 Identificar la canción mediante análisis de audio, si está configurado |

## ❤️ Cómo crear tu lista de favoritas

1. Presioná `B` y elegí un país, o `G` para buscar globalmente.
2. Seleccioná una emisora y presioná `A` para guardarla.
3. Presioná `F` para ver **Mis favoritas**.
4. Usá `↑`/`↓` y `Enter` para escucharla.
5. Para organizarla, usá `[` y `]`, o `A` para quitarla.

Las favoritas se guardan automáticamente. Para organizar por temática, podés crear listas como **Rock**, **Noticias**, **Folklore** o **Deportes** con `N` y sumar emisoras con `P`.

## 🎵 ¿Qué canción está sonando?

**Método 1 — Automático:** si la radio publica información ICY, el reproductor muestra lo que anuncia la transmisión (por ejemplo, *David Bowie — The Jean Genie*). No requiere configurar una cuenta, pero algunas emisoras no emiten estos metadatos o envían información incorrecta.

**Método 2 — Reconocimiento manual:** mientras escuchás una radio, presioná `I`. Se abre una conexión adicional al stream y se obtiene una muestra de aproximadamente 12 segundos con `ffmpeg` para intentar reconocer el tema. La reproducción actual continúa.

Para habilitar este método opcional, necesitás `ffmpeg` y **una** de estas alternativas:

- **SongRec** instalado y disponible como comando `songrec` (su disponibilidad varía por distribución).
- **AudD** con un token propio de [AudD](https://dashboard.audd.io/). Puede tener cuotas o costos, según el servicio.

Instalación de `ffmpeg`, si no lo tenés:

```bash
# Fedora
sudo dnf install ffmpeg-free

# Debian
sudo apt install ffmpeg

# Arch
sudo pacman -S --needed ffmpeg
```

Ejemplo para iniciar con AudD sin guardar el token en el código:

```bash
read -rsp 'Token AudD: ' LOBOVIEJO79_AUDD_TOKEN; echo
export LOBOVIEJO79_AUDD_TOKEN
bash radio.sh
unset LOBOVIEJO79_AUDD_TOKEN
```

🔒 **Privacidad:** el reconocimiento por audio no se ejecuta continuamente. Solo si pulsás `I` se envía una huella o fragmento de audio al servicio de reconocimiento elegido. No se utiliza el micrófono.

## 🧰 Comandos útiles desde la terminal

Los siguientes comandos pueden ejecutarse sin abrir la interfaz (varios solo requieren Python):

| Comando | Para qué sirve |
|:--|:--|
| `bash radio.sh` | ▶️ Abrir reproductor |
| `bash radio.sh --check` | 🩺 Comprobar dependencias `python3`, `mpv`, `cava` (sin instalar) |
| `bash radio.sh --self-test` | 🔍 Comprobar catálogo local y biblioteca |
| `bash radio.sh --check-recognition` | 🎼 Verificar SongRec o AudD + `ffmpeg` |
| `bash radio.sh --list-favorites` | ❤️ Listar favoritas guardadas |
| `bash radio.sh --export-favorites` | 📤 Exportar favoritas a M3U8 en el directorio de exportaciones |
| `bash radio.sh --export-favorites "$HOME/favoritas.m3u8"` | 📁 Exportar a una ruta elegida |
| `LOBOVIEJO79_NO_INSTALL=1 bash radio.sh` | 🛑 Ejecutar sin permitir instalación automática de dependencias |

**Nota:** `--check-recognition` puede devolver un código distinto de cero si el reconocimiento opcional no está configurado; la reproducción normal sigue estando disponible.

## 📂 Archivos del proyecto

```text
loboviejo79-radio-2.2/
├── 📄 README.md                   # Presentación e instrucciones
├── 📸 assets/
│   └── captura-terminal.png       # Captura para GitHub
├── 📻 radio.sh                     # Ejecutable de inicio
├── 🐍 radio.py                     # Interfaz TUI y reproducción
├── 🗂️ library.py                   # Favoritas y listas
├── 🎶 nowplaying.py               # Metadatos y reconocimiento
├── 🌎 catalog.csv.gz              # 63.396 emisoras incluidas
├── 🧪 tests/                     # Pruebas automatizadas
└── .gitignore
```

### 💾 Dónde se guardan los datos

La app utiliza `~/.local/state/loboviejo79-radio/` (o `$XDG_STATE_HOME/loboviejo79-radio/`):

- `biblioteca.json`: favoritas y listas personalizadas.
- `historial_canciones.jsonl`: historial de títulos detectados.
- `exportaciones/`: listas M3U8 exportadas.

**Migración:** al iniciarse por primera vez, si encuentra datos de la versión anterior y el nuevo directorio todavía no existe, copia las favoritas, listas e historial sin borrar los originales. No sobrescribe una biblioteca ya existente. Para respaldar tus datos, copiá esa carpeta a otro disco.

### 📺 Usar favoritas en Jellyfin

```bash
bash radio.sh --export-favorites "$HOME/favoritas.m3u8"
```

Copiá el archivo al servidor donde está Jellyfin y configurá **TV en directo → Sintonizadores → M3U Tuner → Archivo o URL** con una ruta que Jellyfin pueda leer. Algunas radios solo emiten audio y su reproducción puede depender del cliente Jellyfin usado.

## 🧪 Pruebas y limitaciones

El proyecto incluye pruebas automáticas para carga de catálogo, gestión de listas/favoritas, migración de datos, metadatos y respuestas simuladas de reconocimiento. Para ejecutarlas:

```bash
python3 -m unittest discover -s tests -v
```

✅ Verificado: lectura del catálogo y pruebas automatizadas de software.  
⚠️ No se verificó la reproducción de cada radio, ni el reconocimiento real con los servidores de SongRec/AudD en esta entrega.  
📈 Las barras `cava` visualizan el monitor de audio PulseAudio/PipeWire del sistema, por lo que pueden reflejar otros sonidos además de la radio.

## 🚀 Publicar este proyecto en GitHub

1. Descomprimí `LoboViejo79_Radio_Terminal_v2.2_GitHub.zip`.
2. Creá un repositorio vacío en GitHub (por ejemplo, `loboviejo79-radio`).
3. En GitHub elegí **Add file → Upload files**.
4. Subí **los archivos y las carpetas que están dentro de `loboviejo79-radio-2.2/`**, incluido `assets/captura-terminal.png` y `catalog.csv.gz`.
5. Guardá los cambios. GitHub mostrará este README y su captura en la página principal.

**Importante:** subir el ZIP como un único archivo adjunto no publica el código de forma navegable; hay que extraerlo primero. No se incluye una licencia de uso explícita: elegí una (por ejemplo desde GitHub) si querés permitir la reutilización del proyecto por terceros.

## 🔗 Recursos y créditos

- 📻 [Radio Browser](https://www.radio-browser.info/) · [API](https://docs.radio-browser.info/)
- 🧰 [mpv](https://mpv.io/manual/stable/)
- 📈 [cava](https://github.com/karlstav/cava)
- 🎶 [SongRec](https://github.com/marin-m/SongRec) · [AudD](https://docs.audd.io/)
- 🎨 [Charm Gum](https://github.com/charmbracelet/gum) — inspiración de interfaz; **no es una dependencia**.

---

<div align="center">

**🐺 LoboViejo79 Radio — tecnología, Linux y música desde una terminal.**

📺 **[Visitar el canal de YouTube LoboViejo79](https://www.youtube.com/@LoboViejo79)**

</div>
