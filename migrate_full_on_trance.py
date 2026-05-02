"""
One-shot migration: replace "Full-On Trance" genre with "Tech Trance" in all
audio files under a given folder (recursive).

Usage:
    python3 migrate_full_on_trance.py [folder]

Defaults to the last_folder recorded in dj_tagger_config.json when no
folder argument is given.  The software setting from the config is used to
determine the correct genre separator when re-joining genres.
"""

import json
import sys
from pathlib import Path

from tag_utils import (
    join_genres,
    _open_tags, _read_genre_from, _write_genre_to,
)

AUDIO_EXTS = {".mp3", ".aiff", ".aif", ".wav", ".flac", ".m4a"}
OLD_TAG = "Full-On Trance"
NEW_TAG = "Tech Trance"


def migrate(folder: str, software: str) -> None:
    root = Path(folder)
    changed = 0
    skipped = 0
    errors = 0

    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in AUDIO_EXTS:
            continue

        ext = path.suffix.lower()
        obj, save_fn = _open_tags(str(path), ext)
        if obj is None:
            continue

        genre_str = _read_genre_from(obj, ext)
        raw_genres = _ordered_genres(genre_str)

        if OLD_TAG not in raw_genres:
            skipped += 1
            continue

        new_genres = [NEW_TAG if g == OLD_TAG else g for g in raw_genres]

        new_genre_str = join_genres(new_genres, software)

        try:
            _write_genre_to(obj, ext, new_genre_str)
            save_fn()
            print(f"  updated: {path.name}  ({genre_str!r} -> {new_genre_str!r})")
            changed += 1
        except Exception as e:
            print(f"  ERROR:   {path.name}: {e}")
            errors += 1

    print(f"\nDone — {changed} updated, {skipped} skipped (no match), {errors} errors.")


def _ordered_genres(genre_str: str) -> list[str]:
    """Return genres as an ordered list, trying ; then / as delimiter."""
    s = genre_str.strip()
    if not s:
        return []
    for delim in (";", "/"):
        if delim in s:
            return [t.strip() for t in s.split(delim) if t.strip()]
    return [s]


if __name__ == "__main__":
    config_path = Path(__file__).parent / "dj_tagger_config.json"
    with open(config_path) as f:
        config = json.load(f)

    software = config.get("software", "traktor")

    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = config.get("last_folder", "")
        if not folder:
            print("No folder specified and no last_folder in config.")
            sys.exit(1)

    print(f'Scanning "{folder}" for tracks tagged "{OLD_TAG}" ...\n')
    migrate(folder, software)
