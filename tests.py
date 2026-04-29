"""
Tests for tag_utils.py.

Run with:
    python -m pytest tests.py -v
    python -m unittest tests -v       (no pytest needed)
"""
import unittest
import tempfile
from pathlib import Path

from tag_utils import (
    SOFTWARE_MODES, DEFAULT_SOFTWARE,
    software_label, multi_genre_allowed,
    split_genres, join_genres,
    scan_genre_migration, migrate_genres,
)


# ── Minimal valid FLAC bytes ───────────────────────────────────────────────────
#
# FLAC requires fLaC magic + STREAMINFO to be parseable.
# MP3 tests use mutagen.id3.ID3 directly so no audio frames are needed.
#
# FLAC STREAMINFO = 34 bytes: block_sizes(4) + frame_sizes(6) + [sr+ch+bps+samples](8) + MD5(16)
# sr=44100Hz (20b), ch=1 (3b=000), bps=16 (5b=01111), total_samples=0, MD5=0
_MINIMAL_FLAC = (
    b"fLaC"
    b"\x80\x00\x00\x22"          # last metadata block (bit 7), STREAMINFO (type 0), length=34
    b"\x10\x00\x10\x00"          # min/max block size = 4096
    b"\x00\x00\x00\x00\x00\x00"  # min/max frame size = 0 (unknown)
    b"\x0a\xc4\x40\xf0"          # sample_rate=44100Hz + channels=1 + bps=16 + top 4b of samples
    b"\x00\x00\x00\x00"          # remaining 32 bits of total_samples = 0
    b"\x00" * 16                  # MD5 signature
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_mp3(path: str, genre: str) -> None:
    """Create an ID3-tagged file using mutagen.id3.ID3 (no audio frames required)."""
    from mutagen.id3 import ID3, TCON
    Path(path).write_bytes(b"")
    tags = ID3()
    tags.add(TCON(encoding=3, text=[genre]))
    tags.save(path)


def _read_mp3_genre(path: str) -> str:
    from mutagen.id3 import ID3
    tags = ID3(path)
    tcon = tags.get("TCON")
    return str(tcon.text[0]) if tcon and tcon.text else ""


def _make_flac(path: str, genre: str) -> None:
    """Write a minimal valid FLAC stream then attach a Vorbis genre tag."""
    from mutagen.flac import FLAC
    Path(path).write_bytes(_MINIMAL_FLAC)
    f = FLAC(path)
    if f.tags is None:
        f.add_tags()
    f["genre"] = [genre]
    f.save()


def _read_flac_genre(path: str) -> str:
    from mutagen.flac import FLAC
    f = FLAC(path)
    v = f.get("genre", [""])
    return v[0] if v else ""


# ── split_genres ───────────────────────────────────────────────────────────────

class TestSplitGenres(unittest.TestCase):

    def test_semicolon_with_space(self):
        self.assertEqual(split_genres("Uplifting Trance; Tech Trance"),
                         {"Uplifting Trance", "Tech Trance"})

    def test_semicolon_without_space(self):
        self.assertEqual(split_genres("Uplifting Trance;Tech Trance"),
                         {"Uplifting Trance", "Tech Trance"})

    def test_slash(self):
        self.assertEqual(split_genres("Uplifting Trance/Tech Trance"),
                         {"Uplifting Trance", "Tech Trance"})

    def test_single_genre(self):
        self.assertEqual(split_genres("Uplifting Trance"), {"Uplifting Trance"})

    def test_empty_string(self):
        self.assertEqual(split_genres(""), set())

    def test_whitespace_only(self):
        self.assertEqual(split_genres("   "), set())

    def test_strips_whitespace_around_values(self):
        self.assertEqual(split_genres("  Prog Trance ;  Tech Trance  "),
                         {"Prog Trance", "Tech Trance"})

    def test_three_genres_semicolon(self):
        self.assertEqual(split_genres("A; B; C"), {"A", "B", "C"})

    def test_three_genres_slash(self):
        self.assertEqual(split_genres("A/B/C"), {"A", "B", "C"})

    def test_semicolon_takes_priority_over_slash(self):
        # If both appear, semicolon wins (Traktor format takes precedence)
        result = split_genres("A; B/C")
        self.assertIn("A", result)
        self.assertIn("B/C", result)


# ── join_genres ────────────────────────────────────────────────────────────────

class TestJoinGenres(unittest.TestCase):

    def test_traktor_two_genres(self):
        self.assertEqual(join_genres(["Tech Trance", "Uplifting Trance"], "traktor"),
                         "Tech Trance; Uplifting Trance")

    def test_traktor_single(self):
        self.assertEqual(join_genres(["Uplifting Trance"], "traktor"), "Uplifting Trance")

    def test_traktor_empty(self):
        self.assertEqual(join_genres([], "traktor"), "")

    def test_rekordbox_keeps_first_only(self):
        self.assertEqual(join_genres(["Tech Trance", "Uplifting Trance"], "rekordbox"),
                         "Tech Trance")

    def test_rekordbox_single(self):
        self.assertEqual(join_genres(["Uplifting Trance"], "rekordbox"), "Uplifting Trance")

    def test_rekordbox_empty(self):
        self.assertEqual(join_genres([], "rekordbox"), "")

    def test_serato_slash(self):
        self.assertEqual(join_genres(["Tech Trance", "Uplifting Trance"], "serato"),
                         "Tech Trance/Uplifting Trance")

    def test_virtualdj_slash(self):
        self.assertEqual(join_genres(["Tech Trance", "Uplifting Trance"], "virtualdj"),
                         "Tech Trance/Uplifting Trance")

    def test_unknown_software_falls_back_to_traktor(self):
        self.assertEqual(join_genres(["A", "B"], "unknown"),
                         join_genres(["A", "B"], "traktor"))


# ── multi_genre_allowed ────────────────────────────────────────────────────────

class TestMultiGenreAllowed(unittest.TestCase):

    def test_traktor_allows_multi(self):
        self.assertTrue(multi_genre_allowed("traktor"))

    def test_rekordbox_disallows_multi(self):
        self.assertFalse(multi_genre_allowed("rekordbox"))

    def test_serato_allows_multi(self):
        self.assertTrue(multi_genre_allowed("serato"))

    def test_virtualdj_allows_multi(self):
        self.assertTrue(multi_genre_allowed("virtualdj"))

    def test_unknown_software_falls_back_to_traktor(self):
        self.assertEqual(multi_genre_allowed("unknown"), multi_genre_allowed("traktor"))


# ── software_label ─────────────────────────────────────────────────────────────

class TestSoftwareLabel(unittest.TestCase):

    def test_all_modes_have_labels(self):
        for key in SOFTWARE_MODES:
            lbl = software_label(key)
            self.assertIsInstance(lbl, str)
            self.assertGreater(len(lbl), 0)

    def test_unknown_falls_back(self):
        self.assertEqual(software_label("unknown"),
                         software_label(DEFAULT_SOFTWARE))


# ── Round-trip ─────────────────────────────────────────────────────────────────

class TestRoundTrip(unittest.TestCase):
    """Genres survive a split → join → split cycle."""

    def _rt(self, genres: set, software: str) -> set:
        return split_genres(join_genres(sorted(genres), software))

    def test_traktor_roundtrip(self):
        genres = {"Uplifting Trance", "Tech Trance"}
        self.assertEqual(self._rt(genres, "traktor"), genres)

    def test_serato_roundtrip(self):
        genres = {"Uplifting Trance", "Tech Trance"}
        self.assertEqual(self._rt(genres, "serato"), genres)

    def test_virtualdj_roundtrip(self):
        genres = {"Uplifting Trance", "Tech Trance"}
        self.assertEqual(self._rt(genres, "virtualdj"), genres)

    def test_rekordbox_drops_to_one(self):
        genres = {"Uplifting Trance", "Tech Trance"}
        result = self._rt(genres, "rekordbox")
        self.assertEqual(len(result), 1)
        self.assertIn(next(iter(result)), genres)

    def test_cross_format_traktor_to_serato(self):
        """A Traktor-formatted string can be read and re-joined for Serato."""
        traktor_str = "Uplifting Trance; Tech Trance"
        genres = split_genres(traktor_str)
        serato_str = join_genres(sorted(genres), "serato")
        self.assertNotIn(";", serato_str)
        self.assertIn("/", serato_str)
        self.assertEqual(split_genres(serato_str), genres)

    def test_cross_format_serato_to_traktor(self):
        """A Serato-formatted string can be read and re-joined for Traktor."""
        serato_str = "Uplifting Trance/Tech Trance"
        genres = split_genres(serato_str)
        traktor_str = join_genres(sorted(genres), "traktor")
        self.assertNotIn("/", traktor_str)
        self.assertIn(";", traktor_str)
        self.assertEqual(split_genres(traktor_str), genres)


# ── File-level migration (mutagen I/O) ────────────────────────────────────────

class TestMigrateMp3(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _mp3(self, name: str, genre: str) -> str:
        path = str(self.d / name)
        _make_mp3(path, genre)
        return path

    def test_traktor_to_serato_delimiter(self):
        path = self._mp3("a.mp3", "Uplifting Trance; Tech Trance")
        ok, errors = migrate_genres([path], "serato")
        self.assertEqual(ok, 1)
        self.assertEqual(errors, [])
        result = _read_mp3_genre(path)
        self.assertNotIn(";", result)
        self.assertIn("/", result)

    def test_serato_to_traktor_delimiter(self):
        path = self._mp3("a.mp3", "Uplifting Trance/Tech Trance")
        ok, errors = migrate_genres([path], "traktor")
        self.assertEqual(ok, 1)
        result = _read_mp3_genre(path)
        self.assertIn(";", result)
        self.assertNotIn("/", result)

    def test_traktor_to_rekordbox_truncates(self):
        path = self._mp3("a.mp3", "Uplifting Trance; Tech Trance")
        ok, errors = migrate_genres([path], "rekordbox")
        self.assertEqual(ok, 1)
        result = _read_mp3_genre(path)
        self.assertNotIn(";", result)
        self.assertNotIn("/", result)
        # Only one genre remains
        self.assertEqual(len(split_genres(result)), 1)

    def test_already_correct_format_skipped(self):
        """Files already in the target format are not rewritten."""
        path = self._mp3("a.mp3", "Uplifting Trance; Tech Trance")
        ok, errors = migrate_genres([path], "traktor")
        self.assertEqual(ok, 0)  # no change needed

    def test_empty_genre_skipped(self):
        path = self._mp3("a.mp3", "")
        ok, errors = migrate_genres([path], "serato")
        self.assertEqual(ok, 0)

    def test_single_genre_no_delimiter_change(self):
        """Single-genre tracks need no delimiter conversion for any software."""
        path = self._mp3("a.mp3", "Uplifting Trance")
        ok, _ = migrate_genres([path], "serato")
        self.assertEqual(ok, 0)
        ok2, _ = migrate_genres([path], "rekordbox")
        self.assertEqual(ok2, 0)

    def test_multiple_files(self):
        paths = [
            self._mp3("a.mp3", "Uplifting Trance; Tech Trance"),
            self._mp3("b.mp3", "Deep House; Acid House"),
            self._mp3("c.mp3", "Minimal Techno"),  # single — no change
        ]
        ok, errors = migrate_genres(paths, "serato")
        self.assertEqual(ok, 2)
        self.assertEqual(errors, [])


class TestMigrateFlac(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _flac(self, name: str, genre: str) -> str:
        path = str(self.d / name)
        _make_flac(path, genre)
        return path

    def test_traktor_to_serato(self):
        path = self._flac("a.flac", "Uplifting Trance; Tech Trance")
        ok, errors = migrate_genres([path], "serato")
        self.assertEqual(ok, 1)
        result = _read_flac_genre(path)
        self.assertIn("/", result)
        self.assertNotIn(";", result)

    def test_serato_to_traktor(self):
        path = self._flac("a.flac", "Uplifting Trance/Tech Trance")
        ok, errors = migrate_genres([path], "traktor")
        self.assertEqual(ok, 1)
        result = _read_flac_genre(path)
        self.assertIn(";", result)


# ── scan_genre_migration ───────────────────────────────────────────────────────

class TestScanGenreMigration(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _mp3(self, name: str, genre: str) -> str:
        path = str(self.d / name)
        _make_mp3(path, genre)
        return path

    def test_counts_files_needing_change(self):
        paths = [
            self._mp3("a.mp3", "Uplifting Trance; Tech Trance"),  # needs change
            self._mp3("b.mp3", "Uplifting Trance"),                # single, no change
        ]
        changed, lost = scan_genre_migration(paths, "serato")
        self.assertEqual(changed, 1)
        self.assertEqual(lost, 0)

    def test_counts_genres_lost_for_rekordbox(self):
        paths = [
            self._mp3("a.mp3", "Uplifting Trance; Tech Trance"),  # will lose Tech Trance
            self._mp3("b.mp3", "Uplifting Trance"),                # single, fine
        ]
        changed, lost = scan_genre_migration(paths, "rekordbox")
        self.assertEqual(changed, 1)
        self.assertEqual(lost, 1)

    def test_no_change_needed(self):
        paths = [self._mp3("a.mp3", "Uplifting Trance; Tech Trance")]
        changed, lost = scan_genre_migration(paths, "traktor")
        self.assertEqual(changed, 0)
        self.assertEqual(lost, 0)

    def test_empty_list(self):
        changed, lost = scan_genre_migration([], "serato")
        self.assertEqual(changed, 0)
        self.assertEqual(lost, 0)


# ── Folder format detection (feature #3) ──────────────────────────────────────
#
# When a folder is opened, the app scans all files for genre format mismatches
# with the current software setting, then offers to migrate them.
#
# _check_folder_format() in the main window calls:
#   1. scan_genre_migration(self._files, software) → detect
#   2. migrate_genres(self._files, software)       → fix (if user confirms)
#
# The Qt dialog (QMessageBox.question) is not tested here — the logic under
# it is covered end-to-end by the tests below.

class TestFolderFormatDetection(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _mp3(self, name: str, genre: str) -> str:
        path = str(self.d / name)
        _make_mp3(path, genre)
        return path

    def _flac(self, name: str, genre: str) -> str:
        path = str(self.d / name)
        _make_flac(path, genre)
        return path

    # ── Detection ──────────────────────────────────────────────────────────────

    def test_no_mismatch_when_all_correct_traktor(self):
        """Traktor-formatted folder → no migration needed when software=Traktor."""
        paths = [
            self._mp3("a.mp3", "Uplifting Trance; Tech Trance"),
            self._mp3("b.mp3", "Deep House"),
            self._flac("c.flac", "Minimal Techno"),
        ]
        changed, lost = scan_genre_migration(paths, "traktor")
        self.assertEqual(changed, 0)
        self.assertEqual(lost, 0)

    def test_no_mismatch_when_all_correct_serato(self):
        """Serato-formatted folder → no migration needed when software=Serato."""
        paths = [
            self._mp3("a.mp3", "Uplifting Trance/Tech Trance"),
            self._mp3("b.mp3", "Deep House"),
        ]
        changed, lost = scan_genre_migration(paths, "serato")
        self.assertEqual(changed, 0)
        self.assertEqual(lost, 0)

    def test_serato_format_detected_for_traktor(self):
        """Serato '/' genres detected when software=Traktor."""
        paths = [
            self._mp3("a.mp3", "Uplifting Trance/Tech Trance"),  # wrong format
            self._mp3("b.mp3", "Deep House"),                      # single — fine
        ]
        changed, lost = scan_genre_migration(paths, "traktor")
        self.assertEqual(changed, 1)
        self.assertEqual(lost, 0)

    def test_traktor_format_detected_for_serato(self):
        """Traktor ';' genres detected when software=Serato."""
        paths = [
            self._mp3("a.mp3", "Uplifting Trance; Tech Trance"),  # wrong format
            self._mp3("b.mp3", "Deep House"),                      # single — fine
        ]
        changed, lost = scan_genre_migration(paths, "serato")
        self.assertEqual(changed, 1)
        self.assertEqual(lost, 0)

    def test_multi_genre_detected_for_rekordbox(self):
        """Any multi-genre file is a mismatch when software=Rekordbox."""
        paths = [
            self._mp3("a.mp3", "Uplifting Trance; Tech Trance"),  # multi → needs truncation
            self._mp3("b.mp3", "Deep House"),                      # single — fine
        ]
        changed, lost = scan_genre_migration(paths, "rekordbox")
        self.assertEqual(changed, 1)
        self.assertEqual(lost, 1)  # one genre will be dropped

    def test_single_genre_files_never_a_mismatch(self):
        """Single-genre files need no delimiter conversion for any software."""
        paths = [self._mp3("a.mp3", "Uplifting Trance")]
        for sw in ["traktor", "serato", "rekordbox", "virtualdj"]:
            with self.subTest(software=sw):
                changed, lost = scan_genre_migration(paths, sw)
                self.assertEqual(changed, 0)
                self.assertEqual(lost, 0)

    def test_empty_folder(self):
        """Empty file list → nothing to detect."""
        changed, lost = scan_genre_migration([], "traktor")
        self.assertEqual(changed, 0)
        self.assertEqual(lost, 0)

    # ── Subfolder coverage ─────────────────────────────────────────────────────

    def test_files_from_subfolders_all_scanned(self):
        """Files from nested subfolders are all included in the scan (flat _files list)."""
        sub1 = self.d / "trance"
        sub2 = self.d / "trance" / "uplifting"
        sub1.mkdir(); sub2.mkdir()

        paths = [
            str(self.d / "root.mp3"),           # root, correct format
            str(sub1 / "mid.mp3"),               # one level deep, wrong format
            str(sub2 / "deep.mp3"),              # two levels deep, wrong format
        ]
        _make_mp3(paths[0], "Deep House")
        _make_mp3(paths[1], "Uplifting Trance/Tech Trance")   # Serato format
        _make_mp3(paths[2], "Psytrance/Goa Trance")            # Serato format

        changed, lost = scan_genre_migration(paths, "traktor")
        self.assertEqual(changed, 2)   # both subfolder files need updating
        self.assertEqual(lost, 0)

    def test_subfolders_migration_fixes_all(self):
        """Migration triggered from folder-open converts files at any depth."""
        sub = self.d / "house"
        sub.mkdir()

        paths = [
            str(self.d / "a.mp3"),
            str(sub / "b.mp3"),
        ]
        _make_mp3(paths[0], "Deep House/Acid House")     # Serato
        _make_mp3(paths[1], "Tech House/Classic House")  # Serato

        ok, errors = migrate_genres(paths, "traktor")
        self.assertEqual(ok, 2)
        self.assertEqual(errors, [])

        self.assertIn(";", _read_mp3_genre(paths[0]))
        self.assertIn(";", _read_mp3_genre(paths[1]))

    # ── Post-migration verification ────────────────────────────────────────────

    def test_migration_eliminates_all_mismatches(self):
        """After migration, re-scanning the same folder reports zero mismatches."""
        paths = [
            self._mp3("a.mp3", "Uplifting Trance/Tech Trance"),
            self._mp3("b.mp3", "Deep House/Disco House"),
            self._mp3("c.mp3", "Minimal Techno"),            # already fine
        ]

        changed, _ = scan_genre_migration(paths, "traktor")
        self.assertEqual(changed, 2)

        migrate_genres(paths, "traktor")

        changed, _ = scan_genre_migration(paths, "traktor")
        self.assertEqual(changed, 0)

    def test_correct_files_untouched_during_migration(self):
        """Files already in the correct format are not rewritten when folder is migrated."""
        paths = [
            self._mp3("wrong.mp3",   "Uplifting Trance/Tech Trance"),  # needs updating
            self._mp3("correct.mp3", "Deep House; Acid House"),          # already correct
            self._flac("also_wrong.flac", "Psytrance/Goa Trance"),      # needs updating
        ]

        ok, errors = migrate_genres(paths, "traktor")
        self.assertEqual(ok, 2)                                        # only 2 rewritten
        self.assertEqual(_read_mp3_genre(paths[1]), "Deep House; Acid House")  # unchanged

    def test_mixed_formats_in_folder(self):
        """Folder with both Traktor and Serato files — only mismatched ones updated."""
        paths = [
            self._mp3("serato.mp3",  "Uplifting Trance/Tech Trance"),  # wrong for Traktor
            self._mp3("traktor.mp3", "Deep House; Acid House"),          # correct for Traktor
            self._flac("serato.flac","Psytrance/Goa Trance"),           # wrong for Traktor
        ]

        changed, _ = scan_genre_migration(paths, "traktor")
        self.assertEqual(changed, 2)

        ok, _ = migrate_genres(paths, "traktor")
        self.assertEqual(ok, 2)

        self.assertIn(";", _read_mp3_genre(paths[0]))
        self.assertEqual(_read_mp3_genre(paths[1]), "Deep House; Acid House")
        self.assertIn(";", _read_flac_genre(paths[2]))

    def test_rekordbox_keeps_first_genre_alphabetically(self):
        """
        Rekordbox migration keeps the first genre alphabetically.
        This app writes genres sorted alphabetically, so the first stored genre
        is always the first alphabetically.
        """
        path = self._mp3("a.mp3", "Tech Trance; Uplifting Trance")  # alphabetical order

        ok, _ = migrate_genres([path], "rekordbox")
        self.assertEqual(ok, 1)
        self.assertEqual(_read_mp3_genre(path), "Tech Trance")        # T < U


if __name__ == "__main__":
    unittest.main(verbosity=2)
