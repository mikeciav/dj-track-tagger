# Traktor Track Tagger

A desktop app for tagging your DJ library with genre, vibe, vocal, and instrument metadata — written to Traktor Pro 3 compatible ID3 fields.

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)

## Features

- Browse a folder of tracks and tag them with a click
- Tags written directly to file metadata (ID3, FLAC, M4A)
- Traktor Pro 3 compatible: Genre → `TCON`, Grouping → `TIT1`, tags → `COMM`
- Built-in audio player with seek, skip, and keyboard control
- Remembers your last folder on launch
- Configurable tag categories via `dj_tagger_config.json`

## Installation

### 1. Install VLC

Download and install [VLC media player](https://www.videolan.org/vlc/) for your OS. The Python bindings (`python-vlc`) link against the VLC libraries bundled in the app.

### 2. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Run

```bash
python3 traktor_tagger.py
```

## Usage

1. Click **OPEN FOLDER** to load a directory of tracks
2. **Single-click** a track to load its tags for editing
3. **Double-click** a track to load and play it
4. Check/uncheck tags — changes are saved automatically to the file
5. The bottom bar shows the currently playing track's details and active tags

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play / pause |
| `←` / `→` | Seek ±10 seconds |
| `↑` / `↓` | Previous / next track |

## Track list colours

- **Bright text** — track has been tagged
- **Dim text** — no tags set yet
- **Orange background** — currently playing
- **Dark orange background** — selected for editing

## Configuration

Tags are stored in `dj_tagger_config.json` alongside the script. Edit this file directly to add, remove, or reorganise tag categories and groups. Changes take effect on next launch.

## Traktor compatibility

After tagging, run **File → Check Consistency** in Traktor Pro 3 to reload the updated metadata.
