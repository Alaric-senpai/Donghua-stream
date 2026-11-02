"""Library: dense, scannable registry of every series."""
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..components.poster_grid import PosterGrid
from ..components.primitives import _title_block, btn, mk_label
from ..components.series_cards import CompactSeriesRow
from ..infrastructure.thumbnails import ThumbnailStore


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
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 12, 28, 16)
        root.setSpacing(12)
        head = QHBoxLayout()
        head.addLayout(_title_block("Series Registry", "Every series, its folder and episode health at a glance."))
        head.addStretch(1)
        addb = btn("＋  Add Donghua", "primary")
        addb.clicked.connect(self.add_requested.emit)
        head.addWidget(addb)
        root.addLayout(head)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        self.host_lay = QVBoxLayout(host)
        self.host_lay.setContentsMargins(0, 4, 4, 0)
        self.host_lay.setSpacing(8)
        self.host = PosterGrid()
        self.host_lay.addWidget(self.host)
        self.host_lay.addStretch(1)
        self.empty = mk_label("No series registered yet — use Add Donghua.", "body", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.host_lay.addWidget(self.empty)
        self.area.setWidget(host)
        root.addWidget(self.area, 1)

    def load(self, series_list: List[Dict[str, Any]], posters: Dict[int, str]) -> None:
        self._posters = posters
        rows = [CompactSeriesRow(s, posters, self.thumbs) for s in series_list]
        for r in rows:
            r.clicked.connect(self.series_opened)
            r.download_next.connect(self.series_download_all)
            r.open_folder.connect(self.series_folder)
            r.delete_requested.connect(self.series_delete)
        self.host.set_items(rows)
        self.empty.setVisible(not rows)
        self.update_sizes(self._sizes)

    def update_sizes(self, sizes: Dict[int, int]) -> None:
        self._sizes.update(sizes)
        for w in self.host._items:
            data = getattr(w, "series", None)
            if data and data["id"] in self._sizes:
                w.set_disk_size(self._sizes[data["id"]])

    def update_poster(self, vid: str, pix: QPixmap) -> None:
        for w in self.host._items:
            pw = getattr(w, "poster", None)
            if pw and getattr(pw, "vid", "") == vid:
                pw.set_poster(pix)

