"""Three-step Add Donghua registration wizard."""
import os
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QSpinBox, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

import db
from ..components.primitives import btn, chip_tag, label_caps, mk_label
from ..components.storage_card import StorageCard
from ..theme import T_CARD, T_MUTED, T_ON_PRIMARY, T_PRIMARY, T_ROSE, T_SEC, app_stylesheet
from ..utils import (
    QUALITY_OPTIONS, disk_free, human_size, parse_bulk_urls, quality_label,
    resolve_path,
)


class AddWizard(QDialog):
    series_created = pyqtSignal(int, list, bool, str)  # series_id, urls, download_now, quality

    def __init__(self, settings: Dict[str, str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Add Donghua — Registration Wizard")
        self.setMinimumSize(760, 640)
        self.setStyleSheet(app_stylesheet())
        self.created_id: Optional[int] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(14)

        head = QVBoxLayout()
        head.addWidget(mk_label("Register a Donghua", "titleLg"))
        head.addWidget(mk_label("Three quick steps: identity, storage, episodes.", "body", "muted"))
        root.addLayout(head)

        # ---- step pills
        pills_row = QHBoxLayout()
        pills_row.setSpacing(10)
        self.pills: List[QLabel] = []
        for i, name in enumerate(("1  Series identity", "2  Storage preferences",
                                  "3  Episodes & finish")):
            pill = chip_tag(name)
            pill.setStyleSheet(
                f"background: {T_CARD}; border: 1px solid #33415566;"
                f"border-radius: 999px; color: {T_SEC};"
                "font-size: 11px; font-weight: 700; padding: 3px 12px;")
            self.pills.append(pill)
            pills_row.addWidget(pill)
        pills_row.addStretch(1)
        root.addLayout(pills_row)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self._build_step1()
        self._build_step2()
        self._build_step3()

        # ---- navigation
        nav = QHBoxLayout()
        self.back_btn = btn("‹  Back", "ghost")
        self.back_btn.clicked.connect(self._go_back)
        self.next_btn = btn("Next  ›", "primary")
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)
        self._update_pills()

    # ---- step 1: identity ------------------------------------------------------
    def _build_step1(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(label_caps("Series title"))
        self.name_in = QLineEdit()
        self.name_in.setPlaceholderText("e.g. Throne of Seal")
        self.name_in.textChanged.connect(self._preview_key)
        lay.addWidget(self.name_in)
        self.key_prev = QLabel("")
        self.key_prev.setStyleSheet(f"color: {T_MUTED}; font-size: 11px; font-family: monospace;")
        lay.addWidget(self.key_prev)
        lay.addWidget(label_caps("Description / synopsis"))
        self.desc_in = QTextEdit()
        self.desc_in.setPlaceholderText("A short synopsis shown on the series detail page…")
        self.desc_in.setMinimumHeight(90)
        lay.addWidget(self.desc_in)
        lay.addStretch(1)
        self.stack.addWidget(page)

    def _preview_key(self, text: str) -> None:
        self.key_prev.setText(f"key → {db.sanitize_slug(text or '')}")

    # ---- step 2: storage ---------------------------------------------------
    def _build_step2(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(10)
        base = self.settings.get("global_save_dir", "~/Videos")
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.tile_videos = StorageCard("⌂", "Videos", os.path.expanduser("~/Videos"), recommended=True)
        self.tile_downloads = StorageCard("⤓", "Downloads", os.path.expanduser("~/Downloads"))
        self.tile_docs = StorageCard("▤", "Documents", os.path.expanduser("~/Documents"))
        self.tiles = [self.tile_videos, self.tile_downloads, self.tile_docs, None]
        tiles.addWidget(self.tile_videos)
        tiles.addWidget(self.tile_downloads)
        tiles.addWidget(self.tile_docs)
        custom_box = QVBoxLayout()
        self.tile_custom = StorageCard("✎", "Custom…", base)
        custom_box.addWidget(self.tile_custom)
        self.custom_path = QLineEdit()
        self.custom_path.setPlaceholderText("Type or browse a folder path…")
        self.custom_path.textChanged.connect(lambda t: self.tile_custom.set_dir(resolve_path(t)))
        brow = QHBoxLayout()
        brow.addWidget(self.custom_path, 1)
        browse = btn("Browse…", "ghost")
        browse.setMinimumHeight(28)

        def _pick():
            path = QFileDialog.getExistingDirectory(self, "Choose save location",
                                                    os.path.expanduser(self.custom_path.text() or base))
            if path:
                self.custom_path.setText(path)
        browse.clicked.connect(_pick)
        brow.addWidget(browse)
        custom_box.addWidget(self.custom_path)
        customw = QWidget()
        customw.setLayout(custom_box)
        tiles.addWidget(customw, 1)
        self.tiles[3] = self.tile_custom
        for t in self.tiles:
            t.toggled.connect(self._on_tile)
            t.refresh_free()
        self.tile_videos.setChecked(True)
        holder = QWidget()
        holder.setLayout(tiles)
        lay.addWidget(holder)

        self.subfolder_check = QCheckBox(
            "Create a per-donghua sub-folder inside the selected location (recommended)")
        self.subfolder_check.setChecked(True)
        lay.addWidget(self.subfolder_check)

        prev_row = QHBoxLayout()
        prev_row.addWidget(label_caps("Resolved folder"))
        self.path_prev = QLabel("")
        self.path_prev.setStyleSheet(f"color: {T_PRIMARY}; font-family: monospace; font-size: 12px;")
        prev_row.addWidget(self.path_prev, 1)
        self.free_prev = chip_tag("")
        prev_row.addWidget(self.free_prev)
        lay.addLayout(prev_row)

        qrow = QHBoxLayout()
        qrow.addWidget(label_caps("Preferred quality"))
        qual = QComboBox()
        qual.setObjectName("chip")
        for val, lab in QUALITY_OPTIONS:
            qual.addItem(lab, val)
        qual.setCurrentText(quality_label(self.settings.get("default_quality", "720p")))
        self.quality_box = qual
        qual.setFixedHeight(30)
        qrow.addWidget(qual)
        qrow.addStretch(1)
        lay.addLayout(qrow)
        lay.addStretch(1)
        self._current_tile_dir = self.tile_videos.dir()
        self.path_prev.setText(self._resolve_save_dir())
        self._update_free()
        self.stack.addWidget(page)

    def _on_tile(self, checked: bool) -> None:
        if not checked or not hasattr(self, "path_prev"):
            return
        src = self.sender()
        if src in self.tiles:
            self._current_tile_dir = src.dir()
        self.path_prev.setText(self._resolve_save_dir())
        self._update_free()

    def _resolve_save_dir(self) -> str:
        base = self._current_tile_dir
        name = self.name_in.text().strip()
        if self.subfolder_check.isChecked() and name:
            return os.path.join(base, db.sanitize_slug(name))
        return base

    def _update_free(self) -> None:
        free = disk_free(self._resolve_save_dir())
        self.free_prev.setText(f"{human_size(free)} free" if free is not None else "path unavailable")

    # ---- step 3: episodes ---------------------------------------------------
    def _build_step3(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(label_caps("Bulk paste episode links"))
        self.urls = QTextEdit()
        self.urls.setPlaceholderText(
            "One URL per line, optional title after '#':\nhttps://youtu.be/AAAAAAAAA  # Episode 1"
        )
        self.urls.setMinimumHeight(190)
        self.urls.textChanged.connect(self._step3_badge)
        lay.addWidget(self.urls)
        row = QHBoxLayout()
        self.badge = chip_tag("0 valid URLs  ·  0 duplicates")
        row.addWidget(self.badge)
        row.addStretch(1)
        self.start_at = QSpinBox()
        self.start_at.setRange(1, 99999)
        self.start_at.setValue(1)
        row.addWidget(label_caps("Start index"))
        row.addWidget(self.start_at)
        lay.addLayout(row)
        self.auto_dl = QCheckBox("Save & Download Immediately (queue all N videos now)")
        self.auto_dl.setChecked(True)
        lay.addWidget(self.auto_dl)
        lay.addStretch(1)
        self.stack.addWidget(page)

    def _step3_badge(self) -> None:
        items = parse_bulk_urls(self.urls.toPlainText())
        dups = sum(1 for i in items if i["dup"])
        self.badge.setText(f"{len(items)} valid URLs  ·  {dups} duplicated")
        self.badge.setStyleSheet(
            f"background: {'#10b98122' if items else '#f43f5e22'};"
            f"border: 1px solid {'#10b98166' if items else '#f43f5e66'};"
            "border-radius: 999px; color: #4edea3; font-size: 11px; font-weight: 700;"
            "padding: 2px 10px;")

    # ---- navigation ---------------------------------------------------------
    def _current_step(self) -> int:
        return self.stack.currentIndex()

    def _go_back(self) -> None:
        if self._current_step() > 0:
            self.stack.setCurrentIndex(self._current_step() - 1)
            self.next_btn.setText("Next  ›")
            self._update_pills()
        else:
            self.reject()

    def _go_next(self) -> None:
        step = self._current_step()
        if step == 0:
            if not self.name_in.text().strip():
                self.name_in.setFocus()
                self.name_in.setStyleSheet(f"border: 1px solid {T_ROSE};")
                return
            self.stack.setCurrentIndex(1)
            self.path_prev.setText(self._resolve_save_dir())
            self._update_free()
        elif step == 1:
            self.stack.setCurrentIndex(2)
            self.next_btn.setText("💾  Save & Finish")
        else:
            self._finish()

    def _update_pills(self) -> None:
        cur = self._current_step()
        for i, pill in enumerate(self.pills):
            if i == cur:
                pill.setStyleSheet(
                    f"background: {T_PRIMARY}; border-radius: 999px; color: {T_ON_PRIMARY};"
                    "font-size: 11px; font-weight: 800; padding: 3px 12px;")
            else:
                pill.setStyleSheet(
                    f"background: {T_CARD}; border: 1px solid #33415566;"
                    f"border-radius: 999px; color: {T_SEC};"
                    "font-size: 11px; font-weight: 700; padding: 3px 12px;")

    # ---- finish ---------------------------------------------------------
    def _finish(self) -> None:
        name = self.name_in.text().strip()
        save_dir = self._resolve_save_dir()
        try:
            os.makedirs(save_dir, exist_ok=True)
        except OSError as exc:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid folder", f"Cannot create folder:\n{exc}")
            return
        entries = parse_bulk_urls(self.urls.toPlainText())
        try:
            series = db.create_series(name, save_dir=save_dir,
                                      description=self.desc_in.toPlainText())
        except Exception as exc:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Database error", str(exc))
            return
        sid = int(series["id"])
        n = self.start_at.value()
        added = 0
        try:
            for e in entries:
                if e["dup"]:
                    continue
                db.add_episode(sid, e["url"], title=e["title"], episode_number=n)
                n += 1
                added += 1
        except Exception:
            pass
        self.created_id = sid
        urls = []
        if self.auto_dl.isChecked():
            urls = [e["url"] for e in entries if not e["dup"]]
            db.set_setting("global_save_dir", self._current_tile_dir)
        quality = self.quality_box.currentData()
        self.series_created.emit(sid, urls, bool(urls), quality)
        self.accept()

