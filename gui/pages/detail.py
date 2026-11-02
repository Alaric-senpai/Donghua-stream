"""Series detail: identity, sync progress and the episode registry."""
import os
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

import db
from ..components.episode_row import EpisodeRow
from ..components.poster_grid import PosterGrid
from ..components.primitives import (
    btn, chip_tag, icon_btn, label_caps, mk_label, styled_bar,
)
from ..dialogs.add_urls import AddUrlsDialog
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import T_MUTED, T_PRIMARY, T_ROSE, T_SEC, app_stylesheet
from ..utils import QUALITY_OPTIONS, human_size, pct, resolve_path


class SeriesDetailView(QWidget):
    back_requested = pyqtSignal()
    download_urls_requested = pyqtSignal(int, list, str)   # series_id, urls, quality
    open_folder = pyqtSignal(str)
    sync_series = pyqtSignal(int)
    episode_changed = pyqtSignal(int)                      # series_id → refresh
    toast = pyqtSignal(str, bool)

    TABS = [("pending", "Queued"), ("downloaded", "Downloaded"), ("failed", "Failed")]

    def __init__(self, thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs
        self.series: Dict[str, Any] = {}
        self._episodes: List[Dict[str, Any]] = []
        self._tab = "all"
        self._query = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 8, 28, 16)
        root.setSpacing(12)

        # ---- top info card
        info = QFrame()
        info.setObjectName("card")
        il = QHBoxLayout(info)
        il.setContentsMargins(20, 18, 20, 18)
        il.setSpacing(20)

        self.poster = QLabel()
        self.poster.setFixedSize(240, 150)
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setStyleSheet("border-radius: 12px; background: #122036;")
        il.addWidget(self.poster)

        mid = QVBoxLayout()
        mid.setSpacing(6)
        top = QHBoxLayout()
        self.chip_eps = chip_tag("0 EPS", "sky")
        self.chip_status = chip_tag("", "emerald")
        top.addWidget(self.chip_eps)
        top.addWidget(self.chip_status)
        top.addStretch(1)
        self.edit_btn = icon_btn("✎", "Edit series name / description / folder")
        self.edit_btn.clicked.connect(self._edit_series)
        top.addWidget(self.edit_btn)
        mid.addLayout(top)
        self.title = mk_label("—", "titleLg")
        mid.addWidget(self.title)
        self.sub = mk_label("", "body", "muted")
        mid.addWidget(self.sub)
        tags = QHBoxLayout()
        tags.setSpacing(6)
        for tname in ("Donghua", "Ongoing"):
            tags.addWidget(chip_tag(tname))
        self.tags_row = tags
        mid.addLayout(tags)

        path_row = QHBoxLayout()
        self.path_lab = mk_label("", "codePill")
        self.path_lab.setStyleSheet(f"color: {T_PRIMARY}; font-family: monospace; font-size: 12px;")
        path_row.addWidget(self.path_lab, 1)
        openb = btn("⇗  Open in File Manager", "ghost", "")
        openb.setMinimumHeight(30)
        openb.clicked.connect(lambda: self.open_folder.emit(self.series.get("save_dir", "")))
        path_row.addWidget(openb)
        mid.addLayout(path_row)
        il.addLayout(mid, 1)

        # ---- sync progress column
        syncbox = QVBoxLayout()
        syncbox.setSpacing(6)
        self.disk_line = mk_label("0 GB used  ·  0 of 0 cached", "titleSm")
        syncbox.addWidget(self.disk_line)
        self.sync_bar = styled_bar("primary")
        syncbox.addWidget(self.sync_bar)
        progress_row = QHBoxLayout()
        progress_row.addWidget(label_caps("Sync Progress"))
        progress_row.addStretch(1)
        self.sync_pct = mk_label("0% Complete", "titleMd")
        progress_row.addWidget(self.sync_pct)
        syncbox.addLayout(progress_row)
        counts_row = QHBoxLayout()
        counts_row.setSpacing(8)
        self.chip_local = chip_tag("LOCAL FILES  ·  0", "emerald")
        self.chip_queue = chip_tag("QUEUE  ·  0", "amber")
        counts_row.addWidget(self.chip_local)
        counts_row.addWidget(self.chip_queue)
        counts_row.addStretch(1)
        syncbox.addLayout(counts_row)

        qlab = label_caps("Quality")
        syncbox.addWidget(qlab)
        self.quality = QComboBox()
        self.quality.setObjectName("chip")
        for val, lab in QUALITY_OPTIONS:
            self.quality.addItem(lab, val)
        self.quality.setFixedHeight(30)
        syncbox.addWidget(self.quality)

        dl_all = btn("▶  Download All Pending", "primary")
        dl_all.clicked.connect(self._download_all)
        syncbox.addWidget(dl_all)
        verify = btn("⚡  Verify / Scan Disk", "ghost")
        verify.clicked.connect(lambda: self.sync_series.emit(self.series_id))
        syncbox.addWidget(verify)
        addurls = btn("＋  Add Episode URLs", "ghost")
        addurls.clicked.connect(self._quick_import)
        syncbox.addWidget(addurls)
        il.addLayout(syncbox)
        root.addWidget(info)

        # ---- registry tabs
        reg_head = QHBoxLayout()
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self.tab_buttons: Dict[str, QPushButton] = {}
        for key, name in [("all", "All")] + self.TABS:
            b = QPushButton(name)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(key == "all")
            self._tab_group.addButton(b)
            b.clicked.connect(lambda _=False, k=key: self.set_tab(k))
            self.tab_buttons[key] = b
            reg_head.addWidget(b)
        reg_head.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter episodes…")
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(self._render_rows)
        reg_head.addWidget(self.search)
        root.addLayout(reg_head)

        self.rows_host = PosterGrid()
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        hl = QVBoxLayout(host)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.rows_host)
        hl.addStretch(1)
        self.empty = mk_label("No episodes in this bucket.", "body", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(self.empty)
        self.area.setWidget(host)
        root.addWidget(self.area, 1)

    # ---- data ---------------------------------------------------------------
    @property
    def series_id(self) -> int:
        return int(self.series.get("id", 0) or 0)

    def load(self, series: Dict[str, Any], poster_vid: str) -> None:
        self.series = series
        vid = poster_vid or ""
        pix = self.thumbs.get(vid) if vid else None
        if pix and not pix.isNull():
            self.poster.setPixmap(
                pix.scaled(self.poster.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation))
        tot = int(series.get("total_episodes", 0) or 0)
        done = int(series.get("downloaded_episodes", 0) or 0)
        pend = int(series.get("pending_episodes", 0) or 0)
        self.chip_eps.setText(f"{tot} EPS")
        self.chip_status.setText("COMPLETE" if tot and done >= tot else
                                 ("AUTO-TRACKING: Active" if pend else "NOT STARTED"))
        self.title.setText(series.get("name") or "")
        self.sub.setText(f"Key: {series.get('key', '')}  ·  Added {str(series.get('created_at') or '')[:10]}")
        self.path_lab.setText((series.get("save_dir") or "").replace(os.path.expanduser("~"), "~"))
        try:
            self._episodes = db.get_episodes(self.series_id) or []
        except Exception as exc:
            self._episodes = []
            self.toast.emit(f"Could not load episodes: {exc}", False)
        n_failed = sum(1 for e in self._episodes if e.get("status") == "failed")
        self.tab_buttons["failed"].setText(f"Failed ({n_failed})")
        self.render_stats()

    def render_stats(self) -> None:
        tot = len(self._episodes)
        done = sum(1 for e in self._episodes if e.get("status") == "downloaded")
        failed = sum(1 for e in self._episodes if e.get("status") == "failed")
        pend = tot - done - failed
        self.disk_line.setText("scanning disk…" if tot else "No episodes yet")
        self.sync_bar.setValue(pct(done, tot))
        self.sync_pct.setText(f"{pct(done, tot)}% Complete")
        self.chip_local.setText(f"LOCAL FILES  ·  {done}")
        self.chip_queue.setText(f"QUEUE  ·  {max(0, pend)}" + (f"  ·  {failed} FAILED" if failed else ""))
        self._render_rows()

    def update_disk_line(self, size: int) -> None:
        done = sum(1 for e in self._episodes if e.get("status") == "downloaded")
        self.disk_line.setText(f"{human_size(size)} used  ·  {done} of {len(self._episodes)} cached")

    def set_tab(self, key: str) -> None:
        self._tab = key
        self._render_rows()

    def _render_rows(self) -> None:
        text = (self.search.text() or "").strip().lower()
        rows = []
        for i, e in enumerate(self._episodes):
            st = e.get("status") or "pending"
            if self._tab != "all" and self._tab != st:
                continue
            if text and text not in (e.get("title") or "").lower() and text not in (e.get("url") or "").lower():
                continue
            rows.append(EpisodeRow(e, i))
            last = rows[-1]
            last.download.connect(self._download_one)
            last.copy_url.connect(self._copy)
            last.edit_ep.connect(self._edit_episode)
            last.del_ep.connect(self._delete_episode)
            last.retry.connect(self._download_one)
        self.rows_host.set_items(rows)
        self.empty.setVisible(not rows)

    # ---- row handlers -------------------------------------------------------
    def _copy(self, url: str) -> None:
        QApplication.clipboard().setText(url)
        self.toast.emit("URL copied to clipboard.", True)

    def _download_one(self, ep: Dict[str, Any]) -> None:
        self.download_urls_requested.emit(self.series_id,
                                          [ep.get("url")], self.quality.currentData())

    def _download_all(self) -> None:
        urls = [e["url"] for e in self._episodes if e.get("status") != "downloaded"]
        if not urls:
            self.toast.emit("Every episode is already downloaded.", True)
            return
        self.download_urls_requested.emit(self.series_id, urls, self.quality.currentData())

    def _quick_import(self) -> None:
        next_num = len(self._episodes) + 1
        dlg = AddUrlsDialog(self.series, next_num, self)
        got = dlg.collect()
        if not got:
            return
        mode, entries, _start, _auto = got
        self._save_entries(entries)
        if mode == "download":
            self.download_urls_requested.emit(
                self.series_id, [e["url"] for e in entries], self.quality.currentData())

    def _save_entries(self, entries: List[Dict[str, Any]]) -> None:
        added = skipped = 0
        for e in entries:
            try:
                res = db.add_episode(self.series_id, e["url"], title=e.get("title", ""),
                                     episode_number=e.get("num"))
                added += 1 if res else 0
            except Exception:
                skipped += 1
        self.toast.emit(f"Imported: {added} added · {skipped} skipped", True)
        self.episode_changed.emit(self.series_id)

    def _edit_episode(self, ep: Dict[str, Any]) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Episode")
        dlg.setStyleSheet(app_stylesheet())
        lay = QVBoxLayout(dlg)
        lay.addWidget(mk_label("Episode details", "titleMd"))
        title_in = QLineEdit(ep.get("title") or "")
        title_in.setPlaceholderText("Title")
        num_in = QSpinBox()
        num_in.setRange(0, 99999)
        num_in.setValue(int(ep.get("episode_number") or 0))
        url_in = QLineEdit(ep.get("url") or "")
        for lab, widget in (("Title", title_in), ("Episode number", num_in), ("URL", url_in)):
            row = QHBoxLayout()
            row.addWidget(label_caps(lab))
            row.addWidget(widget, 1)
            wrap = QWidget()
            wrap.setLayout(row)
            lay.addWidget(wrap)
        bb = QHBoxLayout()
        bb.addStretch(1)
        c = btn("Cancel", "ghost")
        c.clicked.connect(dlg.reject)
        s = btn("Save", "primary")
        s.clicked.connect(dlg.accept)
        bb.addWidget(c)
        bb.addWidget(s)
        lay.addLayout(bb)
        if dlg.exec() == 1:
            try:
                db.update_episode_fields(
                    ep["id"],
                    title=title_in.text(),
                    episode_number=num_in.value() or None,
                    url=url_in.text() if url_in.text() else None,
                )
                self.toast.emit("Episode updated.", True)
                self.episode_changed.emit(self.series_id)
            except Exception as exc:
                self.toast.emit(f"Update failed: {exc}", False)

    def _delete_episode(self, ep: Dict[str, Any]) -> None:
        try:
            db.delete_episode(ep["id"])
            self.toast.emit(f"Removed #{ep.get('episode_number') or '?'} from the registry.", True)
            self.episode_changed.emit(self.series_id)
        except Exception as exc:
            self.toast.emit(f"Delete failed: {exc}", False)

    def _edit_series(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Series")
        dlg.setStyleSheet(app_stylesheet())
        dlg.setMinimumWidth(460)
        lay = QVBoxLayout(dlg)
        lay.addWidget(mk_label("Series details", "titleMd"))
        name_in = QLineEdit(self.series.get("name") or "")
        desc_in = QTextEdit(self.series.get("description") or "")
        desc_in.setMinimumHeight(70)
        dir_row = QHBoxLayout()
        dir_in = QLineEdit((self.series.get("save_dir") or "").replace(os.path.expanduser("~"), "~"))
        browse = btn("Browse…", "ghost")
        browse.setMinimumHeight(30)

        def _pick():
            path = QFileDialog.getExistingDirectory(dlg, "Series folder",
                                                    os.path.expanduser(dir_in.text()))
            if path:
                dir_in.setText(path)
        browse.clicked.connect(_pick)
        dir_row.addWidget(dir_in, 1)
        dir_row.addWidget(browse)
        for lab, wrap in (("Name", name_in), ("Description", desc_in)):
            row = QVBoxLayout()
            row.addWidget(label_caps(lab))
            row.addWidget(wrap)
            holder = QWidget()
            holder.setLayout(row)
            lay.addWidget(holder)
        lay.addWidget(label_caps("Save folder"))
        row = QWidget()
        row.setLayout(dir_row)
        lay.addWidget(row)
        bb = QHBoxLayout()
        bb.addStretch(1)
        c = btn("Cancel", "ghost")
        c.clicked.connect(dlg.reject)
        s = btn("Save", "primary")
        s.clicked.connect(dlg.accept)
        bb.addWidget(c)
        bb.addWidget(s)
        lay.addLayout(bb)
        if dlg.exec() == 1:
            try:
                db.update_series(self.series_id,
                                 name=name_in.text() or None,
                                 description=desc_in.toPlainText(),
                                 save_dir=resolve_path(dir_in.text()) if dir_in.text() else None)
                self.toast.emit("Series updated.", True)
                self.episode_changed.emit(self.series_id)
            except Exception as exc:
                self.toast.emit(f"Update failed: {exc}", False)

