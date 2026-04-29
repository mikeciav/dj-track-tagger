"""
tag_utils.py — Software-specific genre handling and migration utilities.

Knows how each DJ application expects the genre (TCON) field to be formatted,
and provides helpers to convert between formats when the user switches software.
"""
from __future__ import annotations
from pathlib import Path

# ── Software mode definitions ──────────────────────────────────────────────────

SOFTWARE_MODES: dict[str, dict] = {
    "traktor":   {"label": "Traktor Pro 3", "genre_sep": ";",  "multi_genre": True},
    "rekordbox": {"label": "Rekordbox",      "genre_sep": None, "multi_genre": False},
    "serato":    {"label": "Serato DJ",      "genre_sep": "/",  "multi_genre": True},
    "virtualdj": {"label": "VirtualDJ",      "genre_sep": "/",  "multi_genre": True},
}

DEFAULT_SOFTWARE = "traktor"

_SUPPORTED = {".mp3", ".flac", ".aiff", ".aif", ".m4a", ".wav"}


def software_label(software: str) -> str:
    return SOFTWARE_MODES.get(software, SOFTWARE_MODES[DEFAULT_SOFTWARE])["label"]


def multi_genre_allowed(software: str) -> bool:
    return SOFTWARE_MODES.get(software, SOFTWARE_MODES[DEFAULT_SOFTWARE])["multi_genre"]


# ── Genre string helpers ───────────────────────────────────────────────────────

def split_genres(genre_str: str) -> set[str]:
    """
    Parse genres from a stored string, trying ; then / as delimiters.
    Returns a set — use when order doesn't matter (e.g. matching against a tag list).
    Lenient — handles files regardless of which software wrote them.
    """
    if not genre_str:
        return set()
    for delim in (";", "/"):
        if delim in genre_str:
            return {t.strip() for t in genre_str.split(delim) if t.strip()}
    s = genre_str.strip()
    return {s} if s else set()


def _ordered_genres(genre_str: str) -> list[str]:
    """
    Parse genres from a stored string preserving their original order.
    Used during migration to avoid rewriting files that are already in the correct format.
    """
    if not genre_str:
        return []
    for delim in (";", "/"):
        if delim in genre_str:
            return [t.strip() for t in genre_str.split(delim) if t.strip()]
    s = genre_str.strip()
    return [s] if s else []


def join_genres(genres: list[str], software: str) -> str:
    """Join an ordered list of genres into the correct string for the given software."""
    if not genres:
        return ""
    mode = SOFTWARE_MODES.get(software, SOFTWARE_MODES[DEFAULT_SOFTWARE])
    if not mode["multi_genre"] or mode["genre_sep"] is None:
        return genres[0]
    sep = mode["genre_sep"]
    joiner = "; " if sep == ";" else sep
    return joiner.join(genres)


# ── Mutagen file I/O ───────────────────────────────────────────────────────────
#
# We use format-specific classes instead of MutagenFile so that:
#  - ID3 (MP3/AIFF/WAV): mutagen.id3.ID3 — reads only the tag header, not audio frames
#  - FLAC: mutagen.flac.FLAC
#  - M4A: mutagen.mp4.MP4
# This avoids audio-frame validation and is more efficient for tag-only operations.

def _open_tags(path: str, ext: str):
    """
    Open the tag object for a file. Returns (obj, save_fn) or (None, None).
    save_fn() persists changes back to disk.
    """
    try:
        if ext in (".mp3", ".aiff", ".aif", ".wav"):
            from mutagen.id3 import ID3, ID3NoHeaderError
            try:
                obj = ID3(path)
            except ID3NoHeaderError:
                return None, None  # file has no ID3 header — nothing to migrate
            return obj, lambda: obj.save(path)
        if ext == ".flac":
            from mutagen.flac import FLAC
            obj = FLAC(path)
            return obj, lambda: obj.save()
        if ext == ".m4a":
            from mutagen.mp4 import MP4
            obj = MP4(path)
            return obj, lambda: obj.save()
    except Exception as e:
        print(f"[open_tags] {Path(path).name}: {e}")
    return None, None


def _read_genre_from(obj, ext: str) -> str:
    if ext in (".mp3", ".aiff", ".aif", ".wav"):
        tcon = obj.get("TCON")
        return str(tcon.text[0]) if tcon and tcon.text else ""
    if ext == ".flac":
        if obj.tags is None:
            return ""
        v = obj.tags.get("genre", [""])
        return v[0] if v else ""
    if ext == ".m4a":
        if obj.tags is None:
            return ""
        v = obj.tags.get("©gen", [])
        return str(v[0]) if v else ""
    return ""


def _write_genre_to(obj, ext: str, genre: str) -> None:
    from mutagen.id3 import TCON as _TCON
    if ext in (".mp3", ".aiff", ".aif", ".wav"):
        obj["TCON"] = _TCON(encoding=3, text=[genre])
    elif ext == ".flac":
        if obj.tags is None:
            obj.add_tags()
        obj["genre"] = [genre]
    elif ext == ".m4a":
        if obj.tags is None:
            obj.add_tags()
        obj.tags["©gen"] = [genre]


# ── Migration ──────────────────────────────────────────────────────────────────

def scan_genre_migration(files: list[str], new_software: str) -> tuple[int, int]:
    """
    Preview how many files would be affected by a software switch.

    Returns (files_changed, genres_lost):
    - files_changed: genre string will differ after conversion
    - genres_lost:   files that will lose extra genres (Rekordbox single-genre limit)
    """
    changed = 0
    lost = 0
    for path in files:
        try:
            ext = Path(path).suffix.lower()
            if ext not in _SUPPORTED:
                continue
            obj, _ = _open_tags(path, ext)
            if obj is None:
                continue
            genre_str = _read_genre_from(obj, ext)
            if not genre_str:
                continue
            genre_list = _ordered_genres(genre_str)
            new_genre = join_genres(genre_list, new_software)
            if new_genre != genre_str:
                changed += 1
                if not multi_genre_allowed(new_software) and len(genre_list) > 1:
                    lost += 1
        except Exception:
            pass
    return changed, lost


def migrate_genres(files: list[str], new_software: str) -> tuple[int, list[str]]:
    """
    Rewrite genre fields in all files for the target software format.

    Returns (success_count, error_paths).
    """
    success = 0
    errors: list[str] = []
    for path in files:
        try:
            ext = Path(path).suffix.lower()
            if ext not in _SUPPORTED:
                continue
            obj, save_fn = _open_tags(path, ext)
            if obj is None:
                continue
            genre_str = _read_genre_from(obj, ext)
            if not genre_str:
                continue
            genre_list = _ordered_genres(genre_str)
            new_genre = join_genres(genre_list, new_software)
            if new_genre == genre_str:
                continue
            _write_genre_to(obj, ext, new_genre)
            save_fn()
            success += 1
        except Exception as e:
            errors.append(path)
            print(f"[migrate_genres] {Path(path).name}: {e}")
    return success, errors
