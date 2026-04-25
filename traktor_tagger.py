#!/usr/bin/env python3
"""
DJ Track Tagger  —  tag your library, play tracks, write Traktor Pro 3 compatible metadata.

Dependencies:   pip install PyQt6 mutagen python-vlc
Also needed:    VLC media player  (https://www.videolan.org/vlc/)

Keyboard:  Space=play/pause  ←/→=seek±10s  ↑/↓=prev/next track
Traktor:   Genre→TCON  Subgenre→TIT1(Grouping)  Vocals/Instruments/Mood→COMM(hashtags)
Note:      After tagging, do File→Check Consistency in Traktor to reload.
"""

import json
import math
import sys
from pathlib import Path
from typing import Optional

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import TCON, TIT1, COMM
except ImportError:
    print("ERROR: pip install mutagen"); sys.exit(1)

try:
    import vlc as _vlc
    VLC_OK = True
except ImportError:
    VLC_OK = False; _vlc = None

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QSplitter, QCheckBox,
    QGridLayout, QHBoxLayout, QVBoxLayout, QLineEdit, QFileDialog,
    QMessageBox, QDialog, QTextEdit, QMenu,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QBrush, QCursor, QShortcut, QKeySequence

SUPPORTED   = {".mp3", ".flac", ".aiff", ".aif", ".m4a", ".wav"}
SEEK_S      = 10
POLL_MS     = 350
COLS        = 6
CONFIG_FILE = Path(__file__).parent / "dj_tagger_config.json"

DEFAULT_CONFIG = {
    "categories": [
        {"name": "Genre", "field": "genre", "multi_select": True,
         "groups": [
             {"label": "Trance",  "tags": ["Prog Trance","Uplifting Trance","Psytrance","Hard Trance","Anjuna","Balearic Trance","Tech Trance","Classic Trance","Full-On Trance","Big Room Trance"]},
             {"label": "House",   "tags": ["Deep House","Tech House","Acid House","Prog House","Disco House","Classic House","Trop House","Latin House"]},
             {"label": "Techno",  "tags": ["Minimal Techno","Industrial","Hard Techno","Detroit Techno","Acid Techno","Melodic Techno"]},
         ]},
        {"name": "Vibe",        "field": "comment", "prefix": "",       "multi_select": True,
         "tags": [
             "Acid","Aggressive","Arpeggiated","Bouncy","Bright","Broken","Bwaahhh",
             "Chill","Classic","Dark","Dirty","Disco","Dreamy","Electro","Energetic",
             "Epic","Euphoric","Fun","Funny","Funky","Glitchy","Goofy","Grindy",
             "Hypnotic","Industrial","Jazzy","Joyful","Lovely",
             "Melodic","Moody","Mysterious","Percussive","Poppy","Psychedelic","Punchy",
             "Raw","Relaxed","Rolling","Sad","Sawtooth","Sharp","Soulful","Spacey","Spiritual","Squelchy","Techy","Tense",
             "Tough","Tribal","Tropical","Uplifting","Weird",
         ]},
        {"name": "Vocals",      "field": "comment", "prefix": "",       "multi_select": True,
         "tags": ["MaleVocal","FemaleVocal","NoVocal","Chant","Choir","RappedVocal","SampledVocal","SpokenWord","ChoppedVocal"]},
        {"name": "Instruments", "field": "comment", "prefix": "",       "multi_select": True,
         "tags": ["Brass","Claps","Flute","Guitar","Percussion","Piano","Saxophone","Strings"]},
    ]
}

C = {
    "bg":       "#111111",
    "panel":    "#1a1a1a",
    "panel2":   "#222222",
    "panel3":   "#2a2a2a",
    "border":   "#333333",
    "border2":  "#444444",
    "text":     "#e0e0e0",
    "text_dim": "#555555",
    "text_mid": "#888888",
    "text_inv": "#0a0a0a",
    "hover":    "#2e2e2e",
    "selected": "#ff5f1f",
    "accent":   "#ff5f1f",
    "pb_bg":    "#0d0d0d",
    "pb_fill":  "#ff5f1f",
    "pb_head":  "#ffffff",
    "cat": {
        "Genre":       "#ff5f1f",   # orange
        "Vibe":        "#f0c040",   # amber
        "Vocals":      "#40d490",   # green
        "Instruments": "#40aaff",   # blue
    },
}

# Font helpers
FONT_MONO = "\"Courier New\", \"SF Mono\", Menlo"
FONT_UI   = "\"Helvetica Neue\", Helvetica, Arial"


# ── TrackMeta ─────────────────────────────────────────────────────────────────

class TrackMeta:
    def __init__(self, path: str):
        self.path = path
        self.ext  = Path(path).suffix.lower()
        self.title = self.artist = self.bpm = self.year = self.album = self.mix = ""
        self.genre = self.grouping = self.comment = ""
        self._read()

    def _read(self):
        try:
            f = MutagenFile(self.path, easy=False)
            if f is None or f.tags is None: return
            t = f.tags
            if self.ext in (".mp3", ".aiff", ".aif", ".wav"):
                self.title    = self._s(t, "TIT2"); self.artist   = self._s(t, "TPE1")
                self.bpm      = self._s(t, "TBPM"); self.genre    = self._s(t, "TCON")
                self.grouping = self._s(t, "TIT1")
                self.year     = self._s(t, "TDRC"); self.album    = self._s(t, "TALB")
                self.mix      = self._s(t, "TIT3")
                ck = [k for k in t.keys() if k.startswith("COMM")]
                if ck:
                    fr = t[ck[0]]; self.comment = str(fr.text[0]) if fr.text else ""
            elif self.ext == ".flac":
                self.title    = self._v(t,"title");    self.artist   = self._v(t,"artist")
                self.bpm      = self._v(t,"bpm");      self.genre    = self._v(t,"genre")
                self.grouping = self._v(t,"grouping"); self.comment  = self._v(t,"comment")
                self.year     = self._v(t,"date");     self.album    = self._v(t,"album")
                self.mix      = self._v(t,"version")
            elif self.ext == ".m4a":
                self.title    = self._m(t,"©nam"); self.artist   = self._m(t,"©ART")
                self.bpm      = self._m(t,"tmpo"); self.genre    = self._m(t,"©gen")
                self.grouping = self._m(t,"©grp"); self.comment  = self._m(t,"©cmt")
                self.year     = self._m(t,"©day"); self.album    = self._m(t,"©alb")
                self.mix      = self._m(t,"----:com.apple.iTunes:VERSION")
        except Exception as e:
            print(f"[read] {Path(self.path).name}: {e}")

    @staticmethod
    def _s(t, k):
        fr = t.get(k); tx = getattr(fr, "text", None) if fr else None
        return str(tx[0]) if tx else ""

    @staticmethod
    def _v(t, k):
        v = t.get(k.lower(), t.get(k.upper(), [""])); return v[0] if v else ""

    @staticmethod
    def _m(t, k):
        v = t.get(k); return str(v[0]) if v else ""

    def save(self, genre: str, grouping: str, comment: str) -> bool:
        try:
            f = MutagenFile(self.path, easy=False)
            if f is None: return False
            if f.tags is None: f.add_tags()
            if self.ext in (".mp3", ".aiff", ".aif", ".wav"):
                f.tags["TCON"] = TCON(encoding=3, text=[genre])
                f.tags["TIT1"] = TIT1(encoding=3, text=[grouping])
                for k in [k for k in f.tags.keys() if k.startswith("COMM")]: del f.tags[k]
                f.tags.add(COMM(encoding=3, lang="eng", desc="", text=[comment]))
            elif self.ext == ".flac":
                f.tags["genre"] = [genre]; f.tags["grouping"] = [grouping]; f.tags["comment"] = [comment]
            elif self.ext == ".m4a":
                f.tags["©gen"] = [genre]; f.tags["©grp"] = [grouping]; f.tags["©cmt"] = [comment]
            f.save()
            self.genre = genre; self.grouping = grouping; self.comment = comment
            return True
        except Exception as e:
            print(f"[save] {Path(self.path).name}: {e}"); return False


# ── Config ────────────────────────────────────────────────────────────────────

class Config:
    def __init__(self):
        self.data = self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as fh: return json.load(fh)
            except: pass
        return json.loads(json.dumps(DEFAULT_CONFIG))

    def save(self):
        with open(CONFIG_FILE, "w") as fh: json.dump(self.data, fh, indent=2)

    @property
    def categories(self): return self.data["categories"]

    @staticmethod
    def _cat_tags(cat: dict) -> list:
        """Return all tags for a category, flattening groups if present."""
        if "groups" in cat:
            return [tag for g in cat["groups"] for tag in g["tags"]]
        return cat.get("tags", [])

    def parse(self, meta: TrackMeta) -> dict:
        out = {}
        for cat in self.categories:
            n, field = cat["name"], cat["field"]
            all_tags = self._cat_tags(cat)
            if field == "genre":
                saved = {t.strip() for t in meta.genre.split(";") if t.strip()}
                out[n] = {t for t in all_tags if t in saved}
            elif field == "grouping":
                out[n] = {t.strip() for t in meta.grouping.split(";") if t.strip()}
            elif field == "comment":
                px = cat.get("prefix", "#"); toks = set(meta.comment.split())
                out[n] = {tag for tag in all_tags if (px + tag) in toks}
        return out

    def build(self, selected: dict) -> tuple:
        gp, grp, comm = [], [], []
        for cat in self.categories:
            n, field = cat["name"], cat["field"]
            chosen = sorted(selected.get(n, set()))
            if field == "genre":      gp.extend(chosen)
            elif field == "grouping": grp.extend(chosen)
            elif field == "comment":
                px = cat.get("prefix", "#"); comm.extend(px + t for t in chosen)
        return "; ".join(gp), "; ".join(grp), " ".join(comm)


# ── Player ────────────────────────────────────────────────────────────────────

class Player:
    def __init__(self):
        self._ok = False; self._instance = self._player = None
        if VLC_OK:
            try:
                self._instance = _vlc.Instance("--no-video", "--quiet")
                self._player   = self._instance.media_player_new()
                self._ok = True
            except Exception as e: print(f"[vlc init] {e}")

    @property
    def available(self): return self._ok

    def load(self, path: str):
        if not self._ok: return
        m = self._instance.media_new(path)
        self._player.set_media(m)

    def play(self):
        if self._ok: self._player.play()

    def toggle(self):
        if not self._ok: return
        if self._player.is_playing(): self._player.pause()
        else: self._player.play()

    def stop(self):
        if self._ok: self._player.stop()

    def is_playing(self) -> bool:
        return self._ok and bool(self._player.is_playing())

    def get_pos_ms(self) -> int:
        if not self._ok: return 0
        t = self._player.get_time(); return max(0, t) if t is not None and t >= 0 else 0

    def get_len_ms(self) -> int:
        if not self._ok: return 0
        l = self._player.get_length(); return max(0, l) if l is not None and l > 0 else 0

    def seek_ms(self, ms: int):
        if not self._ok: return
        l = self.get_len_ms()
        if l > 0: self._player.set_time(max(0, min(ms, l - 500)))

    def seek_delta(self, s: float): self.seek_ms(self.get_pos_ms() + int(s * 1000))

    def is_ended(self) -> bool:
        return self._ok and (self._player.get_state() == _vlc.State.Ended)


# ── Progress bar ──────────────────────────────────────────────────────────────

class ProgressBar(QWidget):
    seeked = pyqtSignal(float)
    PAD = 12; BAR_H = 5; R = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._frac = 0.0
        self._dragging = False

    def set_fraction(self, v: float):
        self._frac = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(C["pb_bg"]))
        cy = h // 2
        x0 = self.PAD + self.R
        x1 = w - self.PAD - self.R
        if x1 <= x0: return
        hh = self.BAR_H // 2
        p.fillRect(x0, cy - hh, x1 - x0, self.BAR_H, QColor(C["border"]))
        fx = x0 + int((x1 - x0) * self._frac)
        if fx > x0:
            p.fillRect(x0, cy - hh, fx - x0, self.BAR_H, QColor(C["pb_fill"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(C["pb_head"])))
        p.drawEllipse(QPoint(fx, cy), self.R, self.R)

    def _frac_at(self, x: float) -> float:
        x0 = self.PAD + self.R
        x1 = self.width() - self.PAD - self.R
        return max(0.0, min(1.0, (x - x0) / max(1, x1 - x0)))

    def mousePressEvent(self, e):
        self._dragging = True
        f = self._frac_at(e.position().x())
        self.set_fraction(f); self.seeked.emit(f)

    def mouseMoveEvent(self, e):
        if self._dragging:
            f = self._frac_at(e.position().x())
            self.set_fraction(f); self.seeked.emit(f)

    def mouseReleaseEvent(self, _):
        self._dragging = False


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent, config: Config, on_save):
        super().__init__(parent)
        self.config_ = config
        self.on_save = on_save
        self._idx = 0
        self.setWindowTitle("Category Settings")
        self.setMinimumSize(680, 500)
        self.setModal(True)
        self.setStyleSheet(f"background: {C['bg']}; color: {C['text']};")
        self._build()

    def _btn(self, text, callback, accent=False):
        b = QPushButton(text)
        if accent:
            b.setStyleSheet(f"background:{C['accent']};color:{C['text_inv']};border:none;padding:5px 12px;border-radius:3px;")
        else:
            b.setStyleSheet(f"background:{C['panel2']};color:{C['text']};border:none;padding:5px 12px;border-radius:3px;")
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        b.clicked.connect(callback)
        return b

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Left: category list
        left = QWidget()
        left.setFixedWidth(190)
        left.setStyleSheet(f"background:{C['panel']};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 8, 6, 6)

        lbl = QLabel("Categories")
        lbl.setStyleSheet(f"color:{C['text_dim']};font-size:10px;font-weight:bold;")
        ll.addWidget(lbl)

        self._lb = QListWidget()
        self._lb.setStyleSheet(f"""
            QListWidget{{background:{C['panel2']};color:{C['text']};border:none;font-size:11px;outline:none;}}
            QListWidget::item{{padding:4px 6px;}}
            QListWidget::item:selected{{background:{C['accent']};color:{C['text_inv']};}}
            QListWidget::item:hover:!selected{{background:{C['hover']};}}
        """)
        self._lb.currentRowChanged.connect(self._sel)
        ll.addWidget(self._lb)

        br = QHBoxLayout()
        br.addWidget(self._btn("+ Cat", self._add))
        br.addWidget(self._btn("− Cat", self._del))
        ll.addLayout(br)
        layout.addWidget(left)

        # Right: editor
        right = QWidget()
        right.setStyleSheet(f"background:{C['bg']};")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        rl.addWidget(QLabel("Category name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setStyleSheet(f"background:{C['panel2']};color:{C['text']};border:none;padding:4px;font-size:11px;")
        rl.addWidget(self._name_edit)

        rl.addWidget(QLabel("Tags (one per line):"))
        self._tags_edit = QTextEdit()
        self._tags_edit.setStyleSheet(f"background:{C['panel2']};color:{C['text']};border:none;font-size:11px;")
        rl.addWidget(self._tags_edit)

        bl = QHBoxLayout()
        bl.addStretch()
        bl.addWidget(self._btn("Cancel", self.reject))
        bl.addWidget(self._btn("Save changes", self._save, accent=True))
        rl.addLayout(bl)
        layout.addWidget(right)

        self._refresh()
        if self.config_.categories:
            self._lb.setCurrentRow(0)

    def _refresh(self):
        self._lb.clear()
        for c in self.config_.categories:
            self._lb.addItem(c["name"])

    def _sel(self, row):
        if row >= 0:
            self._idx = row
            cat = self.config_.categories[row]
            self._name_edit.setText(cat["name"])
            if "groups" in cat:
                lines = []
                for g in cat["groups"]:
                    lines.append(f"# {g['label']}")
                    lines.extend(g["tags"])
                self._tags_edit.setPlainText("\n".join(lines))
            else:
                self._tags_edit.setPlainText("\n".join(cat.get("tags", [])))

    def _flush(self):
        cat = self.config_.categories[self._idx]
        cat["name"] = self._name_edit.text().strip()
        lines = [l.strip() for l in self._tags_edit.toPlainText().splitlines()]
        # Parse groups (lines starting with # are group headers)
        groups, current = [], None
        flat = []
        for line in lines:
            if not line: continue
            if line.startswith("#"):
                if current: groups.append(current)
                current = {"label": line[1:].strip(), "tags": []}
            else:
                (current["tags"] if current else flat).append(line)
        if current: groups.append(current)
        if groups:
            cat["groups"] = groups
            cat.pop("tags", None)
        else:
            cat["tags"] = flat
            cat.pop("groups", None)

    def _add(self):
        self._flush()
        self.config_.categories.append({
            "name": "New Category", "field": "comment",
            "prefix": "#NEW_", "multi_select": True, "tags": []
        })
        self._refresh()
        self._lb.setCurrentRow(len(self.config_.categories) - 1)

    def _del(self):
        if len(self.config_.categories) <= 1:
            QMessageBox.warning(self, "Cannot delete", "Need at least one category.")
            return
        self.config_.categories.pop(self._idx)
        self._idx = max(0, self._idx - 1)
        self._refresh()
        self._lb.setCurrentRow(self._idx)

    def _save(self):
        self._flush(); self._refresh(); self.config_.save(); self.on_save(); self.accept()


# ── Main App ──────────────────────────────────────────────────────────────────

class DJTagger(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DJ Track Tagger")
        self.resize(1140, 800)
        self.setMinimumSize(900, 620)

        self.config_   = Config()
        self.player_   = Player()
        self.track_    : Optional[TrackMeta] = None
        self.selected_ : dict = {}
        self._files      : list = []
        self._cur_idx    : Optional[int] = None   # track whose tags are displayed
        self._play_idx   : Optional[int] = None   # track currently playing
        self._tagged_idxs: set = set()            # indices of tracks with any tags
        self._idx_to_item: dict = {}              # file index → QTreeWidgetItem
        self._vars       : dict = {}              # {cat_name: {tag: QCheckBox}}

        self._build_ui()
        self._setup_shortcuts()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(POLL_MS)

        if not self.player_.available:
            self._status("⚠  VLC not found — playback disabled.  pip install python-vlc  +  install VLC.")

        # Restore last folder (deferred so the window is visible first)
        last = self.config_.data.get("last_folder", "")
        if last and Path(last).is_dir():
            QTimer.singleShot(0, lambda: self._load_folder(last))

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {C['bg']}; color: {C['text']};
                font-family: "Helvetica Neue", Helvetica, Arial;
            }}
            QScrollBar:vertical {{
                background: {C['panel']}; width: 6px; border: none; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {C['border2']}; min-height: 32px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {C['text_mid']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            QScrollBar:horizontal {{ height: 0; }}
            QToolTip {{
                background: {C['panel3']}; color: {C['text']}; border: 1px solid {C['border2']};
                font-size: 10px; padding: 3px 6px;
            }}
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────
        top = QFrame()
        top.setFixedHeight(48)
        top.setStyleSheet(f"""
            background: {C['panel']};
            border-bottom: 2px solid {C['accent']};
        """)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(16, 0, 10, 0)
        tl.setSpacing(10)

        # Logo mark — a small orange square before the title
        mark = QLabel("▮")
        mark.setStyleSheet(f"color:{C['accent']};font-size:10px;")
        tl.addWidget(mark)

        ttl = QLabel("DJ TRACK TAGGER")
        ttl.setStyleSheet(f"""
            color: {C['text']};
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 3px;
        """)
        tl.addWidget(ttl)

        # Vertical divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setFixedHeight(20)
        div.setStyleSheet(f"color:{C['border2']};background:{C['border2']};margin:0 4px;")
        tl.addWidget(div)

        self._folder_lbl = QLabel("no folder loaded")
        self._folder_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:10px;font-style:italic;")
        tl.addWidget(self._folder_lbl)
        tl.addStretch()

        tl.addWidget(self._tbtn("⚙  CATEGORIES", self._open_settings))
        tl.addWidget(self._tbtn("▶  OPEN FOLDER", self._open_folder, accent=True))
        root.addWidget(top)

        # ── Main split ────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{C['border']};}}")

        # Left panel: track list only
        left = QWidget()
        left.setStyleSheet(f"background:{C['panel']};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        hdr = QWidget()
        hdr.setFixedHeight(30)
        hdr.setStyleSheet(f"background:{C['panel']};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(10, 0, 10, 0)
        trk_lbl = QLabel("TRACKS")
        trk_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:9px;font-weight:bold;")
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:9px;")
        hl.addWidget(trk_lbl); hl.addStretch(); hl.addWidget(self._count_lbl)
        ll.addWidget(hdr)

        self._file_list = QTreeWidget()
        self._file_list.setHeaderHidden(True)
        self._file_list.setIndentation(16)
        self._file_list.setAnimated(True)
        self._file_list.setRootIsDecorated(False)
        self._file_list.setStyleSheet(f"""
            QTreeWidget {{
                background: {C['panel2']};
                border: none; font-size: 11px; outline: none;
                font-family: "Helvetica Neue", Helvetica, Arial;
            }}
            QTreeWidget::item {{
                padding: 5px 6px;
                border-bottom: 1px solid {C['border']};
            }}
            QTreeWidget::item:selected {{
                background: #3a1800;
                color: {C['text']};
                border-left: 2px solid {C['accent']};
            }}
            QTreeWidget::item:hover:!selected {{
                background: {C['hover']};
            }}
            QTreeWidget::branch {{
                background: {C['panel2']};
                image: none;
                border-image: none;
            }}
            QTreeWidget::branch:!has-children:has-siblings,
            QTreeWidget::branch:!has-children:!has-siblings {{
                background: {C['panel2']};
                border-left: 1px solid {C['border2']};
            }}
        """)
        self._file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._file_list.itemClicked.connect(self._on_item_clicked)
        self._file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        ll.addWidget(self._file_list)
        splitter.addWidget(left)

        # Right panel: scrollable tag checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{C['bg']};}}")

        self._tag_container = QWidget()
        self._tag_container.setStyleSheet(f"background:{C['bg']};")
        self._tag_layout = QVBoxLayout(self._tag_container)
        self._tag_layout.setContentsMargins(0, 0, 0, 16)
        self._tag_layout.setSpacing(0)
        self._tag_layout.addStretch()

        scroll.setWidget(self._tag_container)
        splitter.addWidget(scroll)

        splitter.setSizes([340, 800])
        root.addWidget(splitter, 1)

        # ── Three-panel bottom bar ────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C['border2']};")
        root.addWidget(sep)

        bottom = QFrame()
        bottom.setStyleSheet(f"background:{C['pb_bg']};")
        bottom.setFixedHeight(104)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)

        def _vdiv():
            d = QFrame()
            d.setFrameShape(QFrame.Shape.VLine)
            d.setStyleSheet(f"background:{C['border2']};color:{C['border2']};")
            return d

        # ── Left: track details (same width as track list) ────────────────
        det_panel = QWidget()
        det_panel.setFixedWidth(340)
        det_panel.setStyleSheet(f"background:{C['pb_bg']};")
        dpl = QVBoxLayout(det_panel)
        dpl.setContentsMargins(14, 10, 14, 10)
        dpl.setSpacing(3)

        self._det_title = QLabel("— select a track —")
        self._det_title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:bold;background:transparent;")
        self._det_title.setWordWrap(True)
        dpl.addWidget(self._det_title)

        self._det_artist = QLabel("")
        self._det_artist.setStyleSheet(f"color:{C['text']};font-size:13px;background:transparent;")
        dpl.addWidget(self._det_artist)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(12)
        self._det_album = QLabel("")
        self._det_album.setStyleSheet(f"color:{C['text_mid']};font-size:10px;font-style:italic;background:transparent;")
        self._det_year = QLabel("")
        self._det_year.setStyleSheet(f"color:{C['text_mid']};font-size:10px;background:transparent;")
        meta_row.addWidget(self._det_album)
        meta_row.addWidget(self._det_year)
        meta_row.addStretch()
        dpl.addLayout(meta_row)
        dpl.addStretch()
        bl.addWidget(det_panel)
        bl.addWidget(_vdiv())

        # ── Middle: transport controls ────────────────────────────────────
        ctrl_panel = QWidget()
        ctrl_panel.setFixedWidth(270)
        ctrl_panel.setStyleSheet(f"background:{C['pb_bg']};")
        cpl = QVBoxLayout(ctrl_panel)
        cpl.setContentsMargins(12, 8, 12, 8)
        cpl.setSpacing(0)

        self._prog = ProgressBar()
        self._prog.seeked.connect(self._scrub)
        cpl.addWidget(self._prog)

        self._time_lbl = QLabel("0:00 / 0:00")
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_lbl.setStyleSheet(f"""
            color: {C['text']}; font-size: 13px;
            font-family: "Courier New", Menlo;
            background: {C['pb_bg']}; letter-spacing: 1px;
            padding: 0; margin: 0; border: none;
        """)
        self._time_lbl.setContentsMargins(0, 0, 0, 0)
        cpl.addWidget(self._time_lbl)
        cpl.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(2)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        def tb(text, cb, big=False, accent=False):
            b = QPushButton(text)
            col = C["accent"] if accent else C["text_mid"]
            sz  = 24 if big else 17
            b.setStyleSheet(f"""
                QPushButton{{background:transparent;color:{col};border:none;font-size:{sz}px;padding:2px 10px;}}
                QPushButton:hover{{background:{C['panel2']};border-radius:3px;}}
            """)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.clicked.connect(cb)
            return b

        btn_row.addWidget(tb("⏮", self._prev))
        btn_row.addWidget(tb("⏪", lambda: self.player_.seek_delta(-SEEK_S)))
        self._play_btn = tb("▶", self._play_pause, big=True, accent=True)
        btn_row.addWidget(self._play_btn)
        btn_row.addWidget(tb("⏩", lambda: self.player_.seek_delta(+SEEK_S)))
        btn_row.addWidget(tb("⏭", self._next))
        cpl.addLayout(btn_row)
        bl.addWidget(ctrl_panel)
        bl.addWidget(_vdiv())

        # ── Right: selected tags summary ──────────────────────────────────
        # Layout: Genre and Vibe each on their own line; Vocals + Instruments share a line
        tags_panel = QWidget()
        tags_panel.setStyleSheet(f"background:{C['pb_bg']};")
        tpl = QVBoxLayout(tags_panel)
        tpl.setContentsMargins(16, 10, 16, 10)
        tpl.setSpacing(5)

        self._tag_row_lbls = {}   # cat_name → QLabel (value)
        cats = self.config_.categories

        def _tag_row(cat_names_in_row):
            """Build one horizontal row with prefix+value labels for each category."""
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            rhl = QHBoxLayout(row_w)
            rhl.setContentsMargins(0, 0, 0, 0)
            rhl.setSpacing(6)
            for i, name in enumerate(cat_names_in_row):
                color = C["cat"].get(name, C["accent"])
                pfx = QLabel(name.upper() + ":")
                pfx.setStyleSheet(
                    f"color:{color};font-size:10px;font-weight:bold;"
                    f"letter-spacing:1px;background:transparent;"
                )
                val = QLabel("—")
                val.setStyleSheet(f"color:{C['text_dim']};font-size:11px;background:transparent;")
                self._tag_row_lbls[name] = val
                rhl.addWidget(pfx)
                # Last cat in row stretches; others are fixed
                if i == len(cat_names_in_row) - 1:
                    rhl.addWidget(val, 1)
                else:
                    rhl.addWidget(val)
                    rhl.addSpacing(16)
            return row_w

        # First two categories (Genre, Vibe): one per row
        for cat in cats[:2]:
            tpl.addWidget(_tag_row([cat["name"]]))
        # Remaining categories (Vocals, Instruments): share one row
        if len(cats) > 2:
            tpl.addWidget(_tag_row([c["name"] for c in cats[2:]]))

        tpl.addStretch()
        bl.addWidget(tags_panel, 1)

        root.addWidget(bottom)

        # ── Status bar ────────────────────────────────────────────────────
        sb = self.statusBar()
        sb.setStyleSheet(f"""
            background: {C['panel']};
            color: {C['text_mid']};
            font-size: 9px;
            font-family: "Courier New", Menlo;
            border-top: 1px solid {C['border']};
            padding-left: 4px;
        """)
        self._status("ready — open a folder to begin")

        self._rebuild_tag_panels()

    def _tbtn(self, text, cb, accent=False):
        b = QPushButton(text)
        if accent:
            b.setStyleSheet(f"""
                QPushButton{{
                    background:{C['accent']};color:{C['text_inv']};border:none;
                    font-size:9px;font-weight:bold;letter-spacing:1px;
                    padding:6px 14px;border-radius:2px;
                }}
                QPushButton:hover{{background:#e84a0a;}}
                QPushButton:pressed{{background:#cc3a00;}}
            """)
        else:
            b.setStyleSheet(f"""
                QPushButton{{
                    background:{C['panel3']};color:{C['text_mid']};
                    border:1px solid {C['border']};
                    font-size:9px;letter-spacing:1px;
                    padding:6px 14px;border-radius:2px;
                }}
                QPushButton:hover{{background:{C['border']};color:{C['text']};}}
                QPushButton:pressed{{background:{C['panel2']};}}
            """)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        b.clicked.connect(cb)
        return b

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Space"), self).activated.connect(self._play_pause)
        QShortcut(QKeySequence("Left"),  self).activated.connect(lambda: self.player_.seek_delta(-SEEK_S))
        QShortcut(QKeySequence("Right"), self).activated.connect(lambda: self.player_.seek_delta(+SEEK_S))
        QShortcut(QKeySequence("Up"),    self).activated.connect(self._prev)
        QShortcut(QKeySequence("Down"),  self).activated.connect(self._next)

    # ── Tag panels ────────────────────────────────────────────────────────────

    def _rebuild_tag_panels(self):
        # Clear all widgets (leave the trailing stretch)
        while self._tag_layout.count() > 1:
            item = self._tag_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._vars.clear()
        for cat in self.config_.categories:
            self._build_cat_panel(cat)
        self._refresh_checks()

    def _build_cat_panel(self, cat: dict):
        name  = cat["name"]
        color = C["cat"].get(name, C["accent"])
        self._vars[name] = {}

        wrapper = QWidget()
        wrapper.setStyleSheet(f"background:{C['bg']};")
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(12, 16, 12, 0)
        wl.setSpacing(0)

        # Header — solid colored left border, subtle label
        hdr = QFrame()
        hdr.setStyleSheet(f"""
            background: {C['panel']};
            border-left: 3px solid {color};
            border-top: 1px solid {C['border']};
        """)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(10, 6, 10, 6)
        mode_txt = "SINGLE SELECT" if not cat.get("multi_select", True) else "MULTI SELECT"
        name_lbl = QLabel(name.upper())
        name_lbl.setStyleSheet(f"color:{color};font-size:10px;font-weight:bold;letter-spacing:2px;background:transparent;border:none;")
        mode_lbl = QLabel(mode_txt)
        mode_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:8px;letter-spacing:1px;background:transparent;border:none;")
        hl.addWidget(name_lbl)
        hl.addStretch()
        hl.addWidget(mode_lbl)
        wl.addWidget(hdr)

        # Checkbox area — either grouped or flat
        cb_style = f"""
            QCheckBox{{
                color:{C['text_mid']};font-size:11px;background:transparent;spacing:6px;
            }}
            QCheckBox::indicator{{
                width:13px;height:13px;background:{C['panel3']};
                border:1px solid {C['border2']};border-radius:1px;
            }}
            QCheckBox::indicator:checked{{background:{color};border:1px solid {color};}}
            QCheckBox:hover{{color:{color};}}
            QCheckBox:checked{{color:{C['text']};font-weight:bold;}}
        """

        def _make_cb(tag):
            cb = QCheckBox(tag)
            cb.setStyleSheet(cb_style)
            cb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            cb.stateChanged.connect(lambda state, n=name, t=tag, c=cb: self._on_check(n, t, c))
            cb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            cb.customContextMenuRequested.connect(lambda pos, n=name, t=tag: self._tag_ctx(n, t))
            self._vars[name][tag] = cb
            return cb

        if "groups" in cat:
            # Render each group with its own sub-header + grid
            groups_w = QWidget()
            groups_w.setStyleSheet(f"background:{C['panel2']};")
            gvl = QVBoxLayout(groups_w)
            gvl.setContentsMargins(0, 0, 0, 0)
            gvl.setSpacing(0)

            for gi, group in enumerate(cat["groups"]):
                # Group sub-header
                gh = QWidget()
                gh.setStyleSheet(f"background:{C['panel3']};")
                ghl = QHBoxLayout(gh)
                ghl.setContentsMargins(22, 4, 10, 4)
                glbl = QLabel(group["label"].upper())
                glbl.setStyleSheet(f"color:{color};font-size:8px;font-weight:bold;letter-spacing:2px;background:transparent;")
                ghl.addWidget(glbl)
                ghl.addStretch()
                gvl.addWidget(gh)

                # Group checkbox grid
                grid_w = QWidget()
                grid_w.setStyleSheet(f"background:{C['panel2']};")
                grid = QGridLayout(grid_w)
                grid.setContentsMargins(10, 6, 10, 8)
                grid.setHorizontalSpacing(6)
                grid.setVerticalSpacing(4)
                n_rows = math.ceil(len(group["tags"]) / COLS)
                for i, tag in enumerate(group["tags"]):
                    grid.addWidget(_make_cb(tag), i % n_rows, i // n_rows)
                for col in range(COLS):
                    grid.setColumnStretch(col, 1)
                gvl.addWidget(grid_w)

                # Thin separator between groups (not after last)
                if gi < len(cat["groups"]) - 1:
                    sep = QFrame()
                    sep.setFrameShape(QFrame.Shape.HLine)
                    sep.setStyleSheet(f"background:{C['border']};max-height:1px;")
                    gvl.addWidget(sep)

            wl.addWidget(groups_w)
        else:
            # Flat grid
            grid_w = QWidget()
            grid_w.setStyleSheet(f"background:{C['panel2']};border-left:3px solid {color};")
            grid = QGridLayout(grid_w)
            grid.setContentsMargins(10, 8, 10, 8)
            grid.setHorizontalSpacing(6)
            grid.setVerticalSpacing(4)
            n_rows = math.ceil(len(cat["tags"]) / COLS)
            for i, tag in enumerate(cat["tags"]):
                grid.addWidget(_make_cb(tag), i % n_rows, i // n_rows)
            for col in range(COLS):
                grid.setColumnStretch(col, 1)
            wl.addWidget(grid_w)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color:{C['border']};background:{C['border']};max-height:1px;")
        wl.addWidget(div)

        # Insert before trailing stretch
        self._tag_layout.insertWidget(self._tag_layout.count() - 1, wrapper)

    def _tag_ctx(self, cat_name: str, tag: str):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu{{background:{C['panel2']};color:{C['text']};border:1px solid {C['border']};}}
            QMenu::item:selected{{background:{C['accent']};color:{C['text_inv']};}}
        """)
        menu.addAction(f'Remove "{tag}" from list').triggered.connect(
            lambda: self._remove_tag(cat_name, tag))
        menu.exec(QCursor.pos())

    def _add_tag(self, cat_name: str, entry: QLineEdit):
        tag = entry.text().strip()
        if not tag: return
        cat = next(c for c in self.config_.categories if c["name"] == cat_name)
        all_tags = Config._cat_tags(cat)
        if tag not in all_tags:
            if "groups" in cat:
                cat["groups"][-1]["tags"].append(tag)   # append to last group
            else:
                cat["tags"].append(tag)
            self.config_.save()
            self._rebuild_tag_panels()
        entry.clear()

    def _remove_tag(self, cat_name: str, tag: str):
        cat = next(c for c in self.config_.categories if c["name"] == cat_name)
        if "groups" in cat:
            for g in cat["groups"]:
                if tag in g["tags"]: g["tags"].remove(tag)
        elif tag in cat.get("tags", []):
            cat["tags"].remove(tag)
        if cat_name in self.selected_: self.selected_[cat_name].discard(tag)
        self.config_.save()
        self._rebuild_tag_panels()

    # ── Checkbox logic ────────────────────────────────────────────────────────

    def _on_check(self, cat_name: str, tag: str, cb: QCheckBox):
        if self.track_ is None:
            cb.blockSignals(True); cb.setChecked(False); cb.blockSignals(False)
            self._status("⚠  Select a track first."); return
        cat  = next(c for c in self.config_.categories if c["name"] == cat_name)
        tags = self.selected_.setdefault(cat_name, set())
        if cb.isChecked():
            if not cat.get("multi_select", True):
                for t, other in self._vars[cat_name].items():
                    if t != tag:
                        other.blockSignals(True); other.setChecked(False); other.blockSignals(False)
                        tags.discard(t)
            tags.add(tag)
        else:
            tags.discard(tag)
        self._autosave()

    def _refresh_checks(self):
        for cat in self.config_.categories:
            n = cat["name"]
            chosen = self.selected_.get(n, set())
            for tag, cb in self._vars.get(n, {}).items():
                cb.blockSignals(True)
                cb.setChecked(tag in chosen)
                cb.blockSignals(False)

    # ── Playback ──────────────────────────────────────────────────────────────

    def _play_pause(self):
        if not self.player_.available:
            self._status("⚠  VLC unavailable."); return
        # If nothing is playing yet but a track is selected, start playing it
        if not self.player_.is_playing() and self._play_idx is None and self._cur_idx is not None:
            self._play_track(self._cur_idx); return
        if self.track_ is None:
            self._status("⚠  Select a track first."); return
        self.player_.toggle()
        self._play_btn.setText("⏸" if self.player_.is_playing() else "▶")

    def _prev(self): self._step(-1)
    def _next(self): self._step(+1)

    def _step(self, delta: int):
        if not self._files: return
        # Step relative to the playing track, not the viewed track
        idx = self._play_idx if self._play_idx is not None else (self._cur_idx if self._cur_idx is not None else -1)
        new = max(0, min(len(self._files) - 1, idx + delta))
        self._play_track(new)

    def _scrub(self, fraction: float):
        l = self.player_.get_len_ms()
        if l > 0: self.player_.seek_ms(int(fraction * l))

    def _poll(self):
        if self.player_.available:
            pos = self.player_.get_pos_ms()
            lng = self.player_.get_len_ms()
            if lng > 0:
                self._prog.set_fraction(pos / lng)
                self._time_lbl.setText(f"{self._fmt(pos)} / {self._fmt(lng)}")
            if self.player_.is_ended():
                self._step(+1)
            self._play_btn.setText("⏸" if self.player_.is_playing() else "▶")

    @staticmethod
    def _fmt(ms: int) -> str:
        s = ms // 1000; m = s // 60; s %= 60; return f"{m}:{s:02d}"

    # ── File list ─────────────────────────────────────────────────────────────

    def _open_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select music folder")
        if not path: return
        self._load_folder(path)

    def _load_folder(self, path: str):
        if not Path(path).is_dir(): return
        root_path = Path(path)
        self._folder_lbl.setText(root_path.name)
        self.player_.stop()
        self.track_ = None; self._cur_idx = None; self._play_idx = None; self.selected_ = {}
        self._refresh_checks()
        self._update_detail()

        # Persist last folder
        self.config_.data["last_folder"] = path
        self.config_.save()

        self._files = []
        self._tagged_idxs.clear()
        self._idx_to_item.clear()
        self._file_list.blockSignals(True)
        self._file_list.clear()

        def _add_dir(parent, dir_path: Path):
            """Recursively populate tree. Folders first, then files, both sorted."""
            try:
                entries = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            except PermissionError:
                return
            for entry in entries:
                if entry.is_dir():
                    folder_item = QTreeWidgetItem(parent, [f"+ 📁  {entry.name}"])
                    folder_item.setForeground(0, QColor(C["text_mid"]))
                    font = folder_item.font(0)
                    font.setBold(True)
                    folder_item.setFont(0, font)
                    folder_item.setData(0, Qt.ItemDataRole.UserRole, None)
                    _add_dir(folder_item, entry)
                    # Remove empty folders
                    if folder_item.childCount() == 0:
                        parent.removeChild(folder_item)
                    else:
                        folder_item.setExpanded(False)
                elif entry.suffix.lower() in SUPPORTED:
                    idx = len(self._files)
                    self._files.append(str(entry))
                    try:
                        tagged = any(v for v in self.config_.parse(TrackMeta(str(entry))).values())
                    except Exception:
                        tagged = False
                    if tagged:
                        self._tagged_idxs.add(idx)
                    track_item = QTreeWidgetItem(parent, [entry.stem])
                    track_item.setData(0, Qt.ItemDataRole.UserRole, idx)
                    track_item.setForeground(0, QColor(C["text"] if tagged else C["text_dim"]))
                    self._idx_to_item[idx] = track_item

        self._status(f"Loading…")
        QApplication.processEvents()
        _add_dir(self._file_list.invisibleRootItem(), root_path)
        self._file_list.blockSignals(False)

        self._count_lbl.setText(f"{len(self._files)}")
        self._status(f"{len(self._files)} track(s) found.  Click to view tags · double-click to play.")

    def _on_item_clicked(self, item: "QTreeWidgetItem"):
        """Single click — show tags for track items; toggle expand for folder items."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is None:
            self._toggle_folder(item)
            return
        self._select_track(idx)

    def _on_item_double_clicked(self, item: "QTreeWidgetItem"):
        """Double click — play a track item; toggle expand on folder items."""
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is None:
            self._toggle_folder(item)
            return
        self._play_track(idx)

    def _toggle_folder(self, item: "QTreeWidgetItem"):
        expanded = not item.isExpanded()
        item.setExpanded(expanded)
        t = item.text(0)
        if expanded and t.startswith("+ 📁  "):
            item.setText(0, "- 📁  " + t[len("+ 📁  "):])
        elif not expanded and t.startswith("- 📁  "):
            item.setText(0, "+ 📁  " + t[len("- 📁  "):])

    def _select_track(self, idx: int):
        """Load tags for a track without interrupting playback."""
        if idx < 0 or idx >= len(self._files): return
        self._cur_idx = idx
        path = self._files[idx]
        self.track_    = TrackMeta(path)
        self.selected_ = self.config_.parse(self.track_)
        self._refresh_checks()
        self._update_detail()
        self._status(f"→  {Path(path).name}")

    def _play_track(self, idx: int):
        """Double-click / keyboard nav — start playing this track."""
        if idx < 0 or idx >= len(self._files): return

        # Update view if not already on this track
        if self._cur_idx != idx:
            self._select_track(idx)
            item = self._idx_to_item.get(idx)
            if item:
                self._file_list.blockSignals(True)
                self._file_list.setCurrentItem(item)
                self._file_list.blockSignals(False)

        # Move the playing highlight
        if self._play_idx is not None and self._play_idx != idx:
            self._refresh_item_colors(self._play_idx)
        self._play_idx = idx
        item = self._idx_to_item.get(idx)
        if item:
            item.setBackground(0, QColor(C["accent"]))
            item.setForeground(0, QColor(C["text"]))

        if self.player_.available:
            self.player_.stop()
            self.player_.load(self._files[idx])
            self.player_.play()
            self._play_btn.setText("⏸")
        self._status(f"▶  {Path(self._files[idx]).name}")

    def _refresh_item_colors(self, idx: int):
        """Restore a non-playing item to its normal tagged/untagged colours."""
        item = self._idx_to_item.get(idx)
        if not item: return
        item.setBackground(0, QColor(0, 0, 0, 0))
        item.setForeground(0, QColor(C["text"] if idx in self._tagged_idxs else C["text_dim"]))

    # ── Save ──────────────────────────────────────────────────────────────────

    def _autosave(self):
        if not self.track_: return
        genre, grouping, comment = self.config_.build(self.selected_)
        ok = self.track_.save(genre, grouping, comment)
        if ok and self._cur_idx is not None:
            has_tags = any(v for v in self.selected_.values())
            if has_tags:
                self._tagged_idxs.add(self._cur_idx)
            else:
                self._tagged_idxs.discard(self._cur_idx)
            # Only update colours if this item isn't the playing one (keep orange highlight)
            if self._cur_idx != self._play_idx:
                self._refresh_item_colors(self._cur_idx)
        self._update_detail()
        self._status(f"✓  Saved → {Path(self.track_.path).name}" if ok
                     else "✗  Save failed — check file permissions.")

    # ── Detail panel ──────────────────────────────────────────────────────────

    def _update_detail(self):
        # ── Track details (left panel) ────────────────────────────────────
        if not self.track_:
            self._det_title.setText("— select a track —")
            self._det_artist.setText("")
            self._det_album.setText("")
            self._det_year.setText("")
            for lbl in self._tag_row_lbls.values():
                lbl.setText("—")
                lbl.setStyleSheet(f"color:{C['text_dim']};font-size:11px;background:transparent;")
            return
        t = self.track_
        title = t.title or Path(t.path).stem
        full_title = f"{title} — {t.mix}" if t.mix else title
        self._det_title.setText(full_title)
        self._det_artist.setText(t.artist or "")
        self._det_album.setText(t.album or "")
        self._det_year.setText(t.year or "")

        # ── Selected tags (right panel) ───────────────────────────────────
        for cat in self.config_.categories:
            name   = cat["name"]
            chosen = sorted(self.selected_.get(name, set()))
            lbl    = self._tag_row_lbls.get(name)
            if lbl is None:
                continue
            if chosen:
                lbl.setText(" · ".join(chosen))
                lbl.setStyleSheet(f"color:{C['text']};font-size:11px;background:transparent;")
            else:
                lbl.setText("—")
                lbl.setStyleSheet(f"color:{C['text_dim']};font-size:11px;background:transparent;")

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        SettingsDialog(self, self.config_, self._on_settings_saved).exec()

    def _on_settings_saved(self):
        self.selected_ = self.config_.parse(self.track_) if self.track_ else {}
        self._rebuild_tag_panels()

    def _status(self, msg: str):
        self.statusBar().showMessage(msg)

    def closeEvent(self, e):
        self.player_.stop()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Fusion style: consistent cross-platform rendering, no Aqua interference
    window = DJTagger()
    window.show()
    sys.exit(app.exec())
