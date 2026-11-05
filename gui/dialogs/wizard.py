"""Three-step Add Donghua registration wizard."""
import os
import traceback
from typing import Dict, List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

import db
from .error_dialog import report_error
from ..components.primitives import btn, chip_tag, label_caps, mk_label
from ..components.storage_card import StorageCard
from ..theme import T_MUTED, T_ON_PRIMARY, T_PRIMARY, T_ROSE, T_SEC, app_stylesheet
from ..utils import (
    QUALITY_OPTIONS, disk_free, human_size, parse_bulk_urls, resolve_path,
)


def _display_path(path: str) -> str:
    return (path or "").replace(os.path.expanduser("~"), "~")


class AddWizard(QDialog):
    series_created = pyqtSignal(int, list, bool, str)  # series_id, urls, download_now, quality

    def __init__(self, settings: Dict[str, str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Add Donghua — Registration Wizard")
        self.setMinimumSize(820, 660)
        self.setStyleSheet(app_stylesheet())
        self.created_id: Optional[int] = None
        self._loading = True
        self._storage_guard = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(14)

        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(mk_label("Register a Donghua", "titleLg"))
        head.addWidget(mk_label(
            "Three quick steps: identity, storage, episodes.", "body", "muted"))
        root.addLayout(head)

        # ---- step pills
        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)
        self.pills: List[QLabel] = []
        for name in ("1  Series identity", "2  Storage preferences",
                     "3  Episodes & finish"):
            pill = chip_tag(name)
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
        nav.setSpacing(8)
        self.back_btn = btn("Cancel", "ghost")
        self.back_btn.clicked.connect(self._go_back)
        self.next_btn = btn("Next  ›", "primary")
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        self.step_hint = mk_label("", "small")
        nav.addWidget(self.step_hint)
        nav.addSpacing(4)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)

        self._update_pills()
        self._loading = False

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
        self.key_prev = mk_label("", "small")
        self.key_prev.setStyleSheet(
            f"color: {T_MUTED}; font-family: 'Fira Code'; font-size: 10px;")
        lay.addWidget(self.key_prev)
        lay.addSpacing(2)
        lay.addWidget(label_caps("Description / synopsis"))
        self.desc_in = QTextEdit()
        self.desc_in.setPlaceholderText(
            "A short synopsis shown on the series detail page…")
        self.desc_in.setMinimumHeight(140)
        lay.addWidget(self.desc_in)
        self.identity_hint = mk_label(
            "Only the title is required — you can add a synopsis later from the series page.",
            "small")
        lay.addWidget(self.identity_hint)
        lay.addStretch(1)
        self.stack.addWidget(page)

    def _preview_key(self, text: str) -> None:
        slug = db.sanitize_slug(text or "")
        self.key_prev.setText(f"folder key → {slug or '—'}")
        self.name_in.setStyleSheet("")

    # ---- step 2: storage ---------------------------------------------------
    def _build_step2(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(label_caps("Series save location"))

        base = self.settings.get("global_save_dir", os.path.expanduser("~/Videos"))
        tiles = QGridLayout()
        tiles.setHorizontalSpacing(10)
        tiles.setVerticalSpacing(10)
        self.tile_videos = StorageCard(
            "⌂", "Videos", os.path.expanduser("~/Videos"), recommended=True)
        self.tile_downloads = StorageCard(
            "⤓", "Downloads", os.path.expanduser("~/Downloads"))
        self.tile_docs = StorageCard(
            "▤", "Documents", os.path.expanduser("~/Documents"))
        self.tile_custom = StorageCard("✎", "Custom…", os.path.expanduser(base))
        self.tiles = [self.tile_videos, self.tile_downloads,
                      self.tile_docs, self.tile_custom]
        for i, t in enumerate(self.tiles):
            tiles.addWidget(t, i // 2, i % 2)
            t.toggled.connect(self._on_tile)
        holder = QWidget()
        holder.setLayout(tiles)
        lay.addWidget(holder)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        self.custom_path = QLineEdit()
        self.custom_path.setPlaceholderText("Or type / browse any folder…")
        self.custom_path.textChanged.connect(self._on_custom_typed)
        self.custom_path.editingFinished.connect(self._on_custom_commit)
        browse = btn("Browse…", "ghost", "Choose a custom save location", small=True)
        browse.clicked.connect(self._pick_custom)
        custom_row.addWidget(self.custom_path, 1)
        custom_row.addWidget(browse)
        lay.addLayout(custom_row)

        self.subfolder_check = QCheckBox(
            "Create a per-donghua sub-folder inside the selected location (recommended)")
        self.subfolder_check.setChecked(True)
        self.subfolder_check.toggled.connect(lambda _v: self._refresh_preview())
        lay.addWidget(self.subfolder_check)

        prev = QWidget()
        prev.setObjectName("panel")
        prev_lay = QVBoxLayout(prev)
        prev_lay.setContentsMargins(14, 10, 14, 10)
        prev_lay.setSpacing(3)
        cap_row = QHBoxLayout()
        cap_row.setSpacing(8)
        cap_row.addWidget(label_caps("Resolved folder"))
        cap_row.addStretch(1)
        self.free_prev = chip_tag("", "sky")
        cap_row.addWidget(self.free_prev)
        prev_lay.addLayout(cap_row)
        self.path_prev = QLabel("")
        self.path_prev.setStyleSheet(
            f"color: {T_PRIMARY}; font-family: 'Fira Code'; font-size: 11px;")
        self.path_prev.setWordWrap(True)
        prev_lay.addWidget(self.path_prev)
        lay.addWidget(prev)

        qrow = QHBoxLayout()
        qrow.setSpacing(10)
        qrow.addWidget(label_caps("Preferred quality"))
        qual = QComboBox()
        qual.setObjectName("chip")
        for val, lab in QUALITY_OPTIONS:
            qual.addItem(lab, val)
        idx = qual.findData(self.settings.get("default_quality", "720p"))
        qual.setCurrentIndex(idx if idx >= 0 else 1)
        qual.setFixedHeight(30)
        qual.setMinimumWidth(160)
        self.quality_box = qual
        qrow.addWidget(qual)
        qrow.addStretch(1)
        lay.addLayout(qrow)
        lay.addStretch(1)

        # ---- initial selection: match the global base when possible
        current = os.path.expanduser(base)
        match: Optional[StorageCard] = None
        for t in self.tiles[:-1]:
            if os.path.normpath(t.dir()) == os.path.normpath(current):
                match = t
                break
        if match is None:
            match = self.tile_custom
            self.tile_custom.set_dir(current)
        self.custom_path.setText(_display_path(current))
        self._select_tile(match)
        for t in self.tiles:
            t.refresh_free()
        self._refresh_preview()
        self.stack.addWidget(page)

    # ---- step 2 plumbing ---------------------------------------------------
    def _select_tile(self, chosen: StorageCard) -> None:
        self._storage_guard = True
        try:
            for t in self.tiles:
                t.setChecked(t is chosen)
        finally:
            self._storage_guard = False

    def _on_tile(self, checked: bool) -> None:
        if not checked or self._loading or self._storage_guard:
            return
        src = self.sender()
        if src not in self.tiles:
            return
        self._select_tile(src)
        if src is self.tile_custom:
            text = self.custom_path.text().strip()
            if not text:
                text = _display_path(self.settings.get(
                    "global_save_dir", os.path.expanduser("~/Videos")))
                self.custom_path.setText(text)
            src.set_dir(resolve_path(text))
        self._refresh_preview()

    def _on_custom_typed(self, text: str) -> None:
        if not text.strip():
            return
        self.tile_custom.set_dir(resolve_path(text))
        if self.tile_custom.isChecked():
            self._refresh_preview()

    def _on_custom_commit(self) -> None:
        text = self.custom_path.text().strip()
        if not text:
            return
        self.tile_custom.set_dir(resolve_path(text))
        self._select_tile(self.tile_custom)
        self._refresh_preview()

    def _pick_custom(self) -> None:
        start = os.path.expanduser(self.custom_path.text().strip() or "~")
        path = QFileDialog.getExistingDirectory(self, "Choose save location", start)
        if path:
            self.custom_path.setText(path)
            self.tile_custom.set_dir(path)
            self._select_tile(self.tile_custom)
            self._refresh_preview()

    def _active_dir(self) -> str:
        for t in self.tiles:
            if t.isChecked():
                return t.dir()
        return self.tile_videos.dir()

    def _resolve_save_dir(self) -> str:
        base = self._active_dir()
        name = self.name_in.text().strip()
        if self.subfolder_check.isChecked() and name:
            return os.path.join(base, db.sanitize_slug(name))
        return base

    def _refresh_preview(self) -> None:
        if not hasattr(self, "path_prev"):
            return
        self.path_prev.setText(_display_path(self._resolve_save_dir()))
        free = disk_free(self._active_dir())
        self.free_prev.setText(
            f"{human_size(free)} free" if free is not None else "path unavailable")

    # ---- step 3: episodes ---------------------------------------------------
    def _build_step3(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(label_caps("Bulk paste episode links"))
        self.urls = QTextEdit()
        self.urls.setObjectName("codeInput")
        self.urls.setPlaceholderText(
            "One URL per line, optional title after '#':\n"
            "https://youtu.be/AAAAAAAAA  # Episode 1")
        self.urls.setMinimumHeight(290)
        self.urls.textChanged.connect(self._step3_badge)
        lay.addWidget(self.urls)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.badge = chip_tag("0 valid URLs  ·  0 duplicates")
        row.addWidget(self.badge)
        row.addStretch(1)
        row.addWidget(label_caps("Start index"))
        self.start_at = QSpinBox()
        self.start_at.setRange(1, 99999)
        self.start_at.setValue(1)
        self.start_at.setFixedWidth(110)
        row.addWidget(self.start_at)
        lay.addLayout(row)
        self.auto_dl = QCheckBox(
            "Save and download immediately (queue every new video now)")
        self.auto_dl.setChecked(True)
        lay.addWidget(self.auto_dl)
        lay.addStretch(1)
        self.stack.addWidget(page)

    def _step3_badge(self) -> None:
        items = parse_bulk_urls(self.urls.toPlainText())
        dups = sum(1 for i in items if i["dup"])
        self.badge.setText(
            f"{len(items)} valid URLs  ·  {dups} duplicated  ·  {len(items) - dups} new")
        ok = bool(items)
        self.badge.setStyleSheet(
            f"background: {'rgba(16,185,129,26)' if ok else 'rgba(244,63,94,26)'};"
            f"border: 1px solid {'rgba(16,185,129,105)' if ok else 'rgba(244,63,94,105)'};"
            f"border-radius: 8px; color: {'#4edea3' if ok else '#fda4af'};"
            "font-size: 10px; font-weight: 700; padding: 2px 8px;")

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
            self.name_in.setStyleSheet("")
            self.stack.setCurrentIndex(1)
            self._refresh_preview()
        elif step == 1:
            self.stack.setCurrentIndex(2)
            self.next_btn.setText("💾  Save and Finish")
        else:
            self._finish()
        self._update_pills()

    def _update_pills(self) -> None:
        cur = self._current_step()
        for i, pill in enumerate(self.pills):
            if i == cur:
                pill.setStyleSheet(
                    f"background: {T_PRIMARY}; border: 1px solid {T_PRIMARY};"
                    f"border-radius: 8px; color: {T_ON_PRIMARY};"
                    "font-size: 10px; font-weight: 800; padding: 3px 10px;")
            elif i < cur:
                pill.setStyleSheet(
                    "background: rgba(16,185,129,26); border: 1px solid rgba(16,185,129,105);"
                    "border-radius: 8px; color: #4edea3;"
                    "font-size: 10px; font-weight: 700; padding: 3px 10px;")
            else:
                pill.setStyleSheet(
                    "background: rgba(30,41,59,180);"
                    "border: 1px solid rgba(51,65,85,90);"
                    f"border-radius: 8px; color: {T_SEC};"
                    "font-size: 10px; font-weight: 700; padding: 3px 10px;")
        self.back_btn.setText("Cancel" if cur == 0 else "‹  Back")
        self.step_hint.setText(f"Step {cur + 1} of 3")

    # ---- finish ---------------------------------------------------------
    def _finish(self) -> None:
        name = self.name_in.text().strip()
        if not name:
            self.stack.setCurrentIndex(0)
            self._update_pills()
            return
        save_dir = self._resolve_save_dir()
        try:
            os.makedirs(save_dir, exist_ok=True)
        except OSError as exc:
            report_error(
                self, "Invalid folder",
                f"The save folder could not be created:\n{exc}\n\n"
                "Pick another folder or fix its permissions, then try again.",
                traceback.format_exc())
            return
        entries = parse_bulk_urls(self.urls.toPlainText())
        try:
            series = db.create_series(
                name, save_dir=save_dir, description=self.desc_in.toPlainText())
        except Exception:
            report_error(
                self, "Database error",
                "The series could not be saved to the catalog. Copy these "
                "details when reporting it.",
                traceback.format_exc())
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
        urls: List[str] = []
        if self.auto_dl.isChecked():
            urls = [e["url"] for e in entries if not e["dup"]]
        quality = self.quality_box.currentData()
        self.series_created.emit(sid, urls, bool(urls), quality)
        self.accept()
