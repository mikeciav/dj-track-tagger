# DJ Track Tagger

A desktop app for tagging your DJ library with genre, vibe, vocal, and instrument metadata — written directly to file metadata and compatible with the major DJ applications.

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Tests](https://github.com/mikeciav/dj-track-tagger/actions/workflows/tests.yml/badge.svg)

## Features

- Browse a folder of tracks (including subfolders) and tag them with a click
- Tags written directly to file metadata (ID3, FLAC, M4A)
- Supports **Traktor Pro 3**, **Rekordbox**, **Serato DJ**, and **VirtualDJ**
- Built-in audio player with seek, skip, and keyboard control
- Remembers your last folder on launch
- Configurable tag categories via `dj_tagger_config.json`

## Software support

Select your target DJ software in **Settings**. The app writes genre metadata in the format each application expects:

| Software | Genre format | Notes |
|---|---|---|
| Traktor Pro 3 | `; ` separated | Run File → Check Consistency after tagging |
| Rekordbox | Single genre | Multi-select disabled; one genre per track |
| Serato DJ | `/` separated | |
| VirtualDJ | `/` separated | Right-click → Reload Tag after tagging |

When you switch software, the app offers to reformat genres across your current folder. When you open a folder, it detects any format mismatches and offers to migrate them automatically.

## Installation

### 1. Install VLC

Download and install [VLC media player](https://www.videolan.org/vlc/) for your OS. The Python bindings (`python-vlc`) link against the VLC libraries bundled in the app.

### 2. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Run

```bash
python3 dj_track_tagger.py
```

## Usage

1. Click **OPEN FOLDER** to load a directory of tracks
2. Click **SETTINGS** to choose your target DJ software and manage tag categories
3. **Single-click** a track to load its tags for editing
4. **Double-click** a track to load and play it
5. Check/uncheck tags — changes are saved automatically to the file
6. The bottom bar shows the currently playing track's details and active tags

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
- **Dark orange tint** — selected for editing

## Configuration

Tags are stored in `dj_tagger_config.json` alongside the script. Edit this file directly to add, remove, or reorganise tag categories and groups. Changes take effect on next launch.

## Running tests

```bash
python3 -m unittest tests -v
```

## Reloading tags in your DJ software

After saving tags, your DJ software may need to re-read the file metadata:

| Software | How to reload |
|---|---|
| Traktor Pro 3 | File → Check Consistency |
| Rekordbox | Right-click the track → Reload Tags |
| Serato DJ | Drag the track out of your library and back in, or re-scan the folder |
| VirtualDJ | Right-click the track → Reload Tag |
