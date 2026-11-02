"""Series detail: identity, sync health and the episode registry."""
import os
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy, QSpinBox,
    QTextEdit, QVBoxLayout, QWidget,
)

import db
from ..components.empty_state import EmptyState
from ..components.episode_row import EpisodeRow
from ..components.primitives import (
    btn, chip_tag, eyebrow, icon_btn, label_caps, mk_label, styled_bar, vline,
)
from ..components.stack_list import StackList
from ..components.thumb import PosterThumb
from ..dialogs.add_urls import AddUrlsDialog
from ..icons import icon
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import (
    T_AMBER2, T_AMBER_LINE, T_AMBER_SOFT, T_EMERALD2, T_EMERALD_LINE,
    T_EMERALD_SOFT, T_ON_PRIMARY, T_PRIMARY, T_PRIMARY_LINE, T_PRIMARY_SOFT,
    T_SEC, app_stylesheet,
)
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
        root.setContentsMargins(28, 12, 28, 18)
        root.setSpacing(12)

        # ---- identity + sync health
        info = QFrame()
        info.setObjectName("card")
        info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        il = QHBoxLayout(info)
        il.setContentsMargins(18, 18, 18, 18)
        il.setSpacing(18)

        self.poster = PosterThumb(thumbs, "", radius=12)
        self.poster.setFixedSize(232, 145)
        il.addWidget(self.poster, 0, Qt.AlignmentFlag.AlignTop)

        mid = QVBoxLayout()
        mid.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.chip_eps = chip_tag("0 EPS", "sky")
        self.chip_status = chip_tag("", "emerald")
        top.addWidget(self.chip_eps)
        top.addWidget(self.chip_status)
        top.addStretch(1)
        self.edit_btn = icon_btn("", "Edit series name / description / folder")
        self.edit_btn.setIcon(icon("edit", T_SEC, 15))
        self.edit_btn.setIconSize(QSize(15, 15))
        self.edit_btn.clicked.connect(self._edit_series)
        top.addWidget(self.edit_btn)
        mid.addLayout(top)
        self.title = mk_label("—", "titleXl")
        mid.addWidget(self.title)
        self.sub = mk_label("", "body", "muted")
        mid.addWidget(self.sub)
        self.desc = mk_label("", "body")
        self.desc.setWordWrap(True)
        self.desc.setMaximumWidth(600)
        self.desc.setMaximumHeight(36)
        mid.addWidget(self.desc)
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_lab = mk_label("", "codePill")
        self.path_lab.setToolTip("Series save folder")
        path_row.addWidget(self.path_lab, 1)
        openb = btn("Open Folder", "ghost", "Reveal this series folder in the file manager",
                    small=True)
        openb.setIcon(icon("folder", T_SEC, 13))
        openb.setIconSize(QSize(13, 13))
        openb.clicked.connect(lambda: self.open_folder.emit(self.series.get("save_dir", "")))
        path_row.addWidget(openb)
        mid.addLayout(path_row)

        stats = QFrame()
        stats.setObjectName("subtleBar")
        stats.setFixedHeight(50)
        sl = QHBoxLayout(stats)
        sl.setContentsMargins(14, 5, 14, 5)
        sl.setSpacing(16)
        self.stat_total = self._stat_col(sl, "Episodes")
        sl.addWidget(vline())
        self.stat_ready = self._stat_col(sl, "Ready")
        sl.addWidget(vline())
        self.stat_pending = self._stat_col(sl, "Pending")
        sl.addWidget(vline())
        self.stat_failed = self._stat_col(sl, "Failed")
        sl.addStretch(1)
        mid.addWidget(stats)
        mid.addStretch(1)
        il.addLayout(mid, 1)

        # ---- sync panel
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedWidth(296)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.setSpacing(7)
        pl.addWidget(label_caps("Sync status"))
        pct_row = QHBoxLayout()
        pct_row.setSpacing(6)
        self.sync_pct = QLabel("0%")
        self.sync_pct.setStyleSheet(
            "font-family: 'Fira Code'; font-size: 22px; font-weight: 700; color: #f8fafc;")
        pct_row.addWidget(self.sync_pct)
        pct_row.addWidget(mk_label("complete", "small"))
        pct_row.addStretch(1)
        pl.addLayout(pct_row)
        self.sync_bar = styled_bar("primary")
        pl.addWidget(self.sync_bar)
        self.disk_line = mk_label("No episodes yet", "small")
        pl.addWidget(self.disk_line)
        counts_row = QHBoxLayout()
        counts_row.setSpacing(6)
        self.chip_local = chip_tag("LOCAL  ·  0", "emerald")
        self.chip_queue = chip_tag("QUEUE  ·  0", "amber")
        counts_row.addWidget(self.chip_local)
        counts_row.addWidget(self.chip_queue)
        counts_row.addStretch(1)
        pl.addLayout(counts_row)
        pl.addWidget(label_caps("Download quality"))
        self.quality = QComboBox()
        self.quality.setObjectName("chip")
        for val, lab in QUALITY_OPTIONS:
            self.quality.addItem(lab, val)
        self.quality.setFixedHeight(30)
        pl.addWidget(self.quality)
        dl_all = btn("Download All Pending", "primary")
        dl_all.setIcon(icon("play", T_ON_PRIMARY, 13))
        dl_all.setIconSize(QSize(13, 13))
        dl_all.clicked.connect(self._download_all)
        pl.addWidget(dl_all)
        pair = QHBoxLayout()
        pair.setSpacing(6)
        verify = btn("Verify", "ghost", "Re-scan the archive on disk", small=True)
        verify.setIcon(icon("rotate", T_SEC, 13))
        verify.setIconSize(QSize(13, 13))
        verify.clicked.connect(lambda: self.sync_series.emit(self.series_id))
        addurls = btn("URLs", "ghost", "Import more episode URLs", small=True)
        addurls.setIcon(icon("plus", T_SEC, 13))
        addurls.setIconSize(QSize(13, 13))
        addurls.clicked.connect(self._quick_import)
        pair.addWidget(verify)
        pair.addWidget(addurls)
        pl.addLayout(pair)
        il.addWidget(panel, 0, Qt.AlignmentFlag.AlignTop)
        root.addWidget(info)

        # ---- registry toolbar
        reg_head = QHBoxLayout()
        reg_head.setSpacing(8)
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(eyebrow("Episode registry"))
        self.reg_count = mk_label("", "small")
        title_col.addWidget(self.reg_count)
        reg_head.addLayout(title_col)
        reg_head.addSpacing(12)
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self.tab_buttons: Dict[str, QPushButton] = {}
        for key, name in [("all", "All")] + self.TABS:
            b = btn(name, "chip", small=True)
            b.setCheckable(True)
            b.setFixedHeight(30)
            b.setChecked(key == "all")
            self._tab_group.addButton(b)
            b.clicked.connect(lambda _=False, k=key: self.set_tab(k))
            self.tab_buttons[key] = b
            reg_head.addWidget(b)
        reg_head.addStretch(1)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Filter episodes…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(32)
        self.search.setFixedWidth(230)
        self.search.textChanged.connect(self._render_rows)
        reg_head.addWidget(self.search)
        root.addLayout(reg_head)

        self.rows_host = StackList(spacing=6)
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        hl = QVBoxLayout(host)
        hl.setContentsMargins(0, 0, 4, 0)
        hl.setSpacing(8)
        hl.addWidget(self.rows_host)
        self.empty = EmptyState(
            "≡", "No episodes in this bucket",
            "Try another tab or clear the filter to see the full registry.")
        hl.addWidget(self.empty)
        hl.addStretch(1)
        self.area.setWidget(host)
        root.addWidget(self.area, 1)

    # ---- data ---------------------------------------------------------------
    @property
    def series_id(self) -> int:
        return int(self.series.get("id", 0) or 0)

    def set_poster(self, pix: QPixmap) -> None:
        self.poster.set_poster(pix)

    @staticmethod
    def _stat_col(layout: QHBoxLayout, caption: str) -> QLabel:
        box = QVBoxLayout()
        box.setSpacing(0)
        cap = QLabel(caption.upper())
        cap.setObjectName("statCap")
        val = QLabel("0")
        val.setObjectName("statValue")
        box.addWidget(cap)
        box.addWidget(val)
        wrap = QWidget()
        wrap.setLayout(box)
        layout.addWidget(wrap)
        return val

    def set_quality_silent(self, value: str) -> None:
        idx = self.quality.findData(value)
        if idx >= 0:
            self.quality.blockSignals(True)
            self.quality.setCurrentIndex(idx)
            self.quality.blockSignals(False)

    def load(self, series: Dict[str, Any], poster_vid: str) -> None:
        self.series = series
        vid = poster_vid or ""
        self.poster.vid = vid
        pix = self.thumbs.get(vid) if vid else None
        self.poster.set_poster(pix if pix and not pix.isNull() else QPixmap())
        tot = int(series.get("total_episodes", 0) or 0)
        done = int(series.get("downloaded_episodes", 0) or 0)
        pend = int(series.get("pending_episodes", 0) or 0)
        self.chip_eps.setText(f"{tot} EPS")
        if tot and done >= tot:
            self.chip_status.setText("COMPLETE")
            self._set_status_tone("emerald")
        elif pend:
            self.chip_status.setText(f"{done} OF {tot} DOWNLOADED")
            self._set_status_tone("sky")
        else:
            self.chip_status.setText("NOT STARTED")
            self._set_status_tone("amber")
        self.title.setText(series.get("name") or "")
        self.sub.setText(
            f"Key: {series.get('key', '')}  ·  Added {str(series.get('created_at') or '')[:10]}")
        self.desc.setText((series.get("description") or "").strip()
                          or "No synopsis recorded yet.")
        self.path_lab.setText((series.get("save_dir") or "").replace(os.path.expanduser("~"), "~"))
        try:
            self._episodes = db.get_episodes(self.series_id) or []
        except Exception as exc:
            self._episodes = []
            self.toast.emit(f"Could not load episodes: {exc}", False)
        self.render_stats()

    def _set_status_tone(self, tone: str) -> None:
        tones = {
            "emerald": (T_EMERALD_SOFT, T_EMERALD_LINE, T_EMERALD2),
            "amber": (T_AMBER_SOFT, T_AMBER_LINE, T_AMBER2),
            "sky": (T_PRIMARY_SOFT, T_PRIMARY_LINE, T_PRIMARY),
        }
        bg, line, fg = tones.get(tone, tones["sky"])
        self.chip_status.setStyleSheet(
            f"background: {bg}; border: 1px solid {line}; border-radius: 8px;"
            f"color: {fg}; font-size: 10px; font-weight: 700; padding: 2px 8px;"
        )

    def render_stats(self) -> None:
        tot = len(self._episodes)
        done = sum(1 for e in self._episodes if e.get("status") == "downloaded")
        failed = sum(1 for e in self._episodes if e.get("status") == "failed")
        queued = sum(1 for e in self._episodes
                     if e.get("status") in ("pending", "queued"))
        pct_done = pct(done, tot)
        self.disk_line.setText("scanning disk…" if tot else "No episodes yet")
        self.sync_bar.setValue(pct_done)
        self.sync_pct.setText(f"{pct_done}%")
        self.chip_local.setText(f"LOCAL  ·  {done}")
        self.chip_queue.setText(
            f"QUEUE  ·  {queued}" + (f"  ·  {failed} FAILED" if failed else ""))
        self.stat_total.setText(str(tot))
        self.stat_ready.setText(str(done))
        self.stat_pending.setText(str(queued))
        self.stat_failed.setText(str(failed))
        self.reg_count.setText(f"{tot} episodes tracked")
        self.tab_buttons["all"].setText(f"All ({tot})")
        self.tab_buttons["pending"].setText(f"Queued ({queued})")
        self.tab_buttons["downloaded"].setText(f"Downloaded ({done})")
        self.tab_buttons["failed"].setText(f"Failed ({failed})")
        self._render_rows()

    def update_disk_line(self, size: int) -> None:
        done = sum(1 for e in self._episodes if e.get("status") == "downloaded")
        self.disk_line.setText(
            f"{human_size(max(0, int(size or 0)))} used  ·  {done} of {len(self._episodes)} cached")

    def set_tab(self, key: str) -> None:
        self._tab = key
        btn_ = self.tab_buttons.get(key)
        if btn_ is not None:
            btn_.setChecked(True)
        self._render_rows()

    def _render_rows(self) -> None:
        text = (self.search.text() or "").strip().lower()
        rows = []
        for i, e in enumerate(self._episodes):
            st = e.get("status") or "pending"
            if self._tab == "pending" and st not in ("pending", "queued"):
                continue
            if self._tab in ("downloaded", "failed") and self._tab != st:
                continue
            if text and text not in (e.get("title") or "").lower() \
                    and text not in (e.get("url") or "").lower():
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
        dlg.setMinimumWidth(520)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(8)
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
        dlg.setMinimumWidth(480)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(8)
        lay.addWidget(mk_label("Series details", "titleMd"))
        name_in = QLineEdit(self.series.get("name") or "")
        desc_in = QTextEdit(self.series.get("description") or "")
        desc_in.setMinimumHeight(70)
        dir_row = QHBoxLayout()
        dir_in = QLineEdit((self.series.get("save_dir") or "").replace(os.path.expanduser("~"), "~"))
        browse = btn("Browse…", "ghost", small=True)

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
