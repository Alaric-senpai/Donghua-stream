"""Library: dense, searchable registry of every series."""
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget,
)

from ..components.empty_state import EmptyState
from ..components.primitives import btn, eyebrow, mk_label, vline
from ..components.series_cards import CompactSeriesRow
from ..components.stack_list import StackList
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import T_MUTED
from ..utils import human_size, pct


class LibraryView(QWidget):
    series_opened = pyqtSignal(int)
    series_download_all = pyqtSignal(int)
    series_folder = pyqtSignal(int)
    series_delete = pyqtSignal(int)
    add_requested = pyqtSignal()
    sync_requested = pyqtSignal()

    def __init__(self, thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs
        self._posters: Dict[int, str] = {}
        self._sizes: Dict[int, int] = {}
        self._all: List[Dict[str, Any]] = []
        self._query = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 14, 28, 18)
        root.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(10)
        tl = QVBoxLayout()
        tl.setSpacing(2)
        tl.addWidget(eyebrow("Every series"))
        tl.addWidget(mk_label("Library", "display"))
        tl.addWidget(mk_label(
            "Search the registry, inspect episode health and jump straight into a series.",
            "body", "muted"))
        head.addLayout(tl)
        head.addStretch(1)
        addb = btn("＋  Add Donghua", "primary", "Open the registration wizard")
        addb.setFixedHeight(34)
        addb.clicked.connect(self.add_requested.emit)
        head.addWidget(addb)
        root.addLayout(head)

        # ---- summary telemetry
        strip = QFrame()
        strip.setObjectName("subtleBar")
        strip.setFixedHeight(58)
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(16, 8, 16, 8)
        sl.setSpacing(18)
        self.stat_series = self._stat(sl, "SERIES", "0")
        sl.addWidget(vline())
        self.stat_eps = self._stat(sl, "EPISODES READY", "0 / 0")
        sl.addWidget(vline())
        self.stat_disk = self._stat(sl, "ON DISK", "—")
        sl.addStretch(1)
        root.addWidget(strip)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search by series name…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(34)
        self.search.setMaximumWidth(360)
        self.search.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search, 1)
        self.count_lbl = mk_label("", "small")
        toolbar.addStretch(1)
        toolbar.addWidget(self.count_lbl)
        root.addLayout(toolbar)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        self.host_lay = QVBoxLayout(host)
        self.host_lay.setContentsMargins(0, 2, 4, 0)
        self.host_lay.setSpacing(8)
        self.host = StackList(spacing=8)
        self.host_lay.addWidget(self.host)
        self.empty = EmptyState(
            "▤", "The registry is empty",
            "Add your first donghua to start tracking episodes and downloads.",
            "＋  Add Donghua")
        self.empty.action_requested.connect(self.add_requested.emit)
        self.host_lay.addWidget(self.empty)
        self.host_lay.addStretch(1)
        self.area.setWidget(host)
        root.addWidget(self.area, 1)

    @staticmethod
    def _stat(layout: QHBoxLayout, caption: str, value: str) -> QLabel:
        box = QVBoxLayout()
        box.setSpacing(1)
        cap = QLabel(caption)
        cap.setStyleSheet(
            f"color: {T_MUTED}; font-family: 'Fira Code'; font-size: 9px;")
        box.addWidget(cap)
        val = QLabel(value)
        val.setStyleSheet(
            "color: #f8fafc; font-family: 'Fira Code'; font-size: 16px; font-weight: 700;")
        box.addWidget(val)
        holder = QWidget()
        holder.setLayout(box)
        layout.addWidget(holder)
        return val

    # ---- data ---------------------------------------------------------------
    def load(self, series_list: List[Dict[str, Any]], posters: Dict[int, str]) -> None:
        self._posters = posters
        self._all = list(series_list)
        done = sum(int(s.get("downloaded_episodes", 0) or 0) for s in series_list)
        total = sum(int(s.get("total_episodes", 0) or 0) for s in series_list)
        self.stat_series.setText(str(len(series_list)))
        self.stat_eps.setText(f"{done} / {total}  ·  {pct(done, total)}%")
        self._rebuild()
        self.update_sizes(self._sizes)

    def _on_search(self, text: str) -> None:
        self._query = text.strip().lower()
        self._rebuild()

    def _rebuild(self) -> None:
        data = [s for s in self._all
                if not self._query or self._query in s.get("name", "").lower()]
        rows = [CompactSeriesRow(s, self._posters, self.thumbs) for s in data]
        for r in rows:
            r.clicked.connect(self.series_opened)
            r.download_next.connect(self.series_download_all)
            r.open_folder.connect(self.series_folder)
            r.delete_requested.connect(self.series_delete)
        self.host.set_items(rows)
        self.empty.setVisible(not rows)
        self.count_lbl.setText(f"{len(data)} of {len(self._all)} series")
        for r in rows:
            sid = r.series["id"]
            if sid in self._sizes:
                r.set_disk_size(self._sizes[sid])

    def update_sizes(self, sizes: Dict[int, int]) -> None:
        self._sizes.update(sizes)
        total = sum(self._sizes.get(s["id"], 0) for s in self._all)
        self.stat_disk.setText(human_size(total) if total else "—")
        for w in self.host.items:
            data = getattr(w, "series", None)
            if data and data["id"] in self._sizes:
                w.set_disk_size(self._sizes[data["id"]])

    def update_poster(self, vid: str, pix: QPixmap) -> None:
        for w in self.host.items:
            pw = getattr(w, "poster", None)
            if pw and getattr(pw, "vid", "") == vid:
                pw.set_poster(pix)
