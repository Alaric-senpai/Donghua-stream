"""Settings: storage, formats, network, auth and database/daemon."""
import os
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSpinBox, QVBoxLayout,
    QWidget,
)

import db
from ..components.primitives import btn, label_caps, mk_label
from ..components.storage_card import StorageCard
from ..theme import T_MUTED, T_SEC
from ..utils import (
    BROWSER_OPTIONS, CONTAINER_OPTIONS, QUALITY_OPTIONS, disk_free,
    human_size, load_settings, resolve_path, set_setting,
)


class SectionCard(QFrame):
    def __init__(self, title: str, sub: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        lay.addWidget(mk_label(title, "titleMd"))
        if sub:
            lay.addWidget(mk_label(sub, "body", "muted"))


class SettingsView(QWidget):
    test_connection = pyqtSignal()
    resync_requested = pyqtSignal()
    settings_changed = pyqtSignal(str)     # key that changed
    toast = pyqtSignal(str, bool)

    def __init__(self, settings: Optional[Dict[str, str]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.s: Dict[str, str] = dict(settings or load_settings())
        self._widgets: Dict[str, QWidget] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 8, 28, 16)
        outer.setSpacing(12)
        outer.addWidget(mk_label("Settings & Storage Preferences", "titleLg"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        root = QVBoxLayout(host)
        root.setContentsMargins(0, 4, 8, 4)
        root.setSpacing(14)

        # ---- 1. Storage & Directories
        sec1 = SectionCard("Storage & Directories",
                           "Where new episodes are saved. A per-donghua sub-folder keeps every series self-contained.")
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.t_videos = StorageCard("⌂", "Videos", os.path.expanduser("~/Videos"), recommended=True)
        self.t_downloads = StorageCard("⤓", "Downloads", os.path.expanduser("~/Downloads"))
        self.t_docs = StorageCard("▤", "Documents", os.path.expanduser("~/Documents"))
        self.t_custom = StorageCard("✎", "Custom…", self.s.get("global_save_dir", "~/Videos"))
        self.tiles = [self.t_videos, self.t_downloads, self.t_docs, self.t_custom]
        for t in self.tiles:
            tiles.addWidget(t)
            t.toggled.connect(self._tile_picked)
        customw = QWidget()
        cw = QVBoxLayout(customw)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(6)
        cw.addWidget(self.t_custom)
        self.custom_path = QLineEdit()
        self.custom_path.setPlaceholderText("Type or browse any folder…")
        self.custom_path.textChanged.connect(lambda p: self.t_custom.set_dir(resolve_path(p)))
        brow = QHBoxLayout()
        brow.addWidget(self.custom_path, 1)
        browse = btn("Browse…", "ghost", "")
        browse.setMinimumHeight(28)

        def _pick():
            path = QFileDialog.getExistingDirectory(self, "Global save location",
                                                    os.path.expanduser(self.custom_path.text() or "~"))
            if path:
                self.custom_path.setText(path)
                self.t_custom.setChecked(True)
        browse.clicked.connect(_pick)
        brow.addWidget(browse)
        cw.addLayout(brow)
        tiles.addWidget(customw, 1)
        self.tiles[3] = self.t_custom
        for t in self.tiles:
            t.refresh_free()
        holder = QWidget()
        holder.setLayout(tiles)
        sec1.layout().addWidget(holder)
        current_dir = self.s.get("global_save_dir", "~/Videos")
        matched = False
        for t in self.tiles[:-1]:
            if t.dir() == current_dir:
                t.setChecked(True)
                matched = True
        if matched:
            self.t_custom.set_dir(current_dir)
            self.custom_path.setText(current_dir)
        else:
            self.t_custom.setChecked(True)
            self.custom_path.setText(current_dir)
        self.subfolder_chk = QCheckBox("Use a per-donghua sub-folder inside the save location")
        self.subfolder_chk.setChecked(self.s.get("per_series_subfolder", "1") == "1")
        self.subfolder_chk.toggled.connect(
            lambda v: self._save("per_series_subfolder", "1" if v else "0"))
        sec1.layout().addWidget(self.subfolder_chk)
        root.addWidget(sec1)

        # ---- 2. Quality & Formats
        sec2 = SectionCard("Quality & Formats", "Applied to every new download unless a series overrides it.")
        self._mk_field(sec2, "Default quality", "default_quality", ("combo", QUALITY_OPTIONS))
        self._mk_field(sec2, "Container format", "default_container", ("combo", CONTAINER_OPTIONS))
        root.addWidget(sec2)

        # ---- 3. Network & Downloader
        sec3 = SectionCard("Network & Downloader", "Retries, bandwidth ceiling, subtitle language track.")
        self._mk_field(sec3, "Max retries per video", "max_retries", ("spin", 1, 20))
        self._mk_field(sec3, "Subtitle languages", "sub_langs", ("text", "en, zh-Hans"))
        rate_box = QHBoxLayout()
        rate_box.addWidget(label_caps("Rate limit (MB/s, 0 = unlimited)"))
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0, 500)
        self.rate_spin.setDecimals(1)
        try:
            self.rate_spin.setValue(float(self.s.get("rate_limit_mb", "0") or 0))
        except (TypeError, ValueError):
            self.rate_spin.setValue(0.0)
        self.rate_spin.setSuffix(" MB/s")
        self.rate_spin.setFixedWidth(150)
        self.rate_spin.valueChanged.connect(lambda v: self._save("rate_limit_mb", str(v)))
        rate_row = QWidget()
        rate_row.setLayout(rate_box)
        self._insert_widgets(sec3, [rate_row, self.rate_spin])
        root.addWidget(sec3)

        # ---- 4. Browser & Auth
        sec4 = SectionCard("Browser & Auth", "Which local browser profile yt-dlp should reuse for cookies.")
        self._mk_field(sec4, "Cookies source", "browser_cookies", ("combo", [b for b in BROWSER_OPTIONS if b[0] != "safari"]))
        root.addWidget(sec4)

        # ---- 5. Database & Daemon
        sec5 = SectionCard("Database & Daemon", "Postgres catalog behind the app, and the download daemon.")
        try:
            import yt_dlp
            engine_ver = yt_dlp.version.__version__
        except Exception:
            engine_ver = "unknown"
        info = QLabel(
            f"DB: donghua_db @ {getattr(db, 'DB_CONFIG', {}).get('host', 'localhost')}  ·  "
            f"user {getattr(db, 'DB_CONFIG', {}).get('user', '-')}  ·  "
            f"engine yt-dlp {engine_ver}")
        info.setStyleSheet(f"color: {T_SEC}; font-size: 12px; font-family: monospace;")
        self._insert_widgets(sec5, [info])
        dbrow = QHBoxLayout()
        test_btn = btn("⚡  Test Connection", "ghost", "Ping the database now")
        test_btn.clicked.connect(self.test_connection.emit)
        resync_btn = btn("⟳  Force Re-Sync", "ghost", "Re-sync every series against its downloaded.txt")
        resync_btn.clicked.connect(self.resync_requested.emit)
        dbrow.addWidget(test_btn)
        dbrow.addWidget(resync_btn)
        dbrow.addStretch(1)
        dbw = QWidget()
        dbw.setLayout(dbrow)
        self._insert_widgets(sec5, [dbw])
        root.addWidget(sec5)

        # ---- reset
        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        reset = btn("Reset to Defaults", "danger", "Restore every setting to the shipped default")
        reset.clicked.connect(self._reset)
        reset_row.addWidget(reset)
        root.addLayout(reset_row)
        root.addStretch(1)

        scroll.setWidget(host)
        outer.addWidget(scroll, 1)
        self._widget_map = self._widgets

    # ---- helpers ----------------------------------------------------------
    def _mk_field(self, sec: SectionCard, label: str, key: str,
                  spec: tuple) -> None:
        kind = spec[0]
        if kind == "combo":
            widget = QComboBox()
            widget.setObjectName("chip")
            widget.setFixedHeight(30)
            for val, lab in spec[1]:
                widget.addItem(lab, val)
            idx = widget.findData(self.s.get(key, ""))
            widget.setCurrentIndex(idx if idx >= 0 else 0)
            widget.currentIndexChanged.connect(
                lambda _i, k=key, w=widget: self._save(k, str(w.currentData())))
            self._widgets[key] = widget
        elif kind == "spin":
            widget = QSpinBox()
            widget.setRange(*spec[1:3])
            widget.setFixedWidth(120)
            try:
                widget.setValue(int(self.s.get(key, "3") or 3))
            except (TypeError, ValueError):
                widget.setValue(3)
            widget.valueChanged.connect(lambda v, k=key: self._save(k, str(v)))
            self._widgets[key] = widget
        elif kind == "text":
            widget = QLineEdit(self.s.get(key, ""))
            widget.setFixedWidth(220)
            widget.editingFinished.connect(
                lambda w=widget, k=key: self._save(k, w.text().strip() or "en"))
            self._widgets[key] = widget
        else:
            return
        row = QHBoxLayout()
        row.addWidget(label_caps(label))
        row.addStretch(1)
        row.addWidget(widget)
        wrap = QWidget()
        wrap.setLayout(row)
        sec.layout().addWidget(wrap)

    def _insert_widgets(self, sec: SectionCard, widgets: List[QWidget]) -> None:
        for w in widgets:
            sec.layout().addWidget(w)

    def _tile_picked(self, checked: bool) -> None:
        if not checked:
            return
        src = self.sender()
        if src in self.tiles:
            self._save("global_save_dir", src.dir())

    def _save(self, key: str, value: str) -> None:
        self.s[key] = value
        if set_setting(key, value):
            self.settings_changed.emit(key)
            self.toast.emit(f"Saved: {key.replace('_', ' ')} = {value}", True)
        else:
            self.toast.emit(f"Could not save {key}", False)

    def _reset(self) -> None:
        for key, value in db.DEFAULT_SETTINGS.items():
            set_setting(key, value)
            self.s[key] = value
        if set_setting("per_series_subfolder", "1"):
            self.s["per_series_subfolder"] = "1"
        self.settings_changed.emit("*")
        self.toast.emit("Settings restored to defaults.", True)

