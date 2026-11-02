"""Catalog cards: poster grid card and the compact registry row."""
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import T_HOVER, T_MUTED
from ..utils import human_size
from .poster import PosterWidget
from .primitives import chip_tag


class SeriesCard(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, series: Dict[str, Any], posters: Dict[int, str],
                 thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.series = series
        self.poster = None
        self.setObjectName("card")
        self.setFixedSize(216, 274)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 10)
        lay.setSpacing(4)
        self.poster = PosterWidget(series, posters, thumbs)
        self.poster.setFixedSize(216, 214)
        lay.addWidget(self.poster, 0, Qt.AlignmentFlag.AlignHCenter)

        row = QHBoxLayout()
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(6)
        tot = int(series.get("total_episodes", 0) or 0)
        dl = int(series.get("downloaded_episodes", 0) or 0)
        left = QLabel(f"{max(0, tot - dl)} left")
        left.setStyleSheet(f"color: {T_MUTED}; font-size: 10px;")
        row.addWidget(left)
        row.addStretch(1)
        self.disk_lbl = QLabel("scanning…")
        self.disk_lbl.setStyleSheet(f"color: {T_MUTED}; font-size: 10px;")
        self.disk_lbl.setToolTip("Disk usage of the series folder")
        row.addWidget(self.disk_lbl)
        wrap = QWidget()
        wrap.setLayout(row)
        lay.addWidget(wrap)
        self.poster.clicked.connect(self.clicked.emit)

    def set_disk_size(self, size: int) -> None:
        self.disk_lbl.setText(human_size(size))


class CompactSeriesRow(QFrame):
    clicked = pyqtSignal(int)
    download_next = pyqtSignal(int)
    open_folder = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, series: Dict[str, Any], posters: Dict[int, str],
                 thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.series = series
        self.setObjectName("card")
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"QFrame#card:hover {{ background: {T_HOVER}; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)

        pw = PosterWidget(series, posters, thumbs)
        pw.setFixedSize(82, 60)
        pw._badge = None
        pw._hover_box.hide()
        lay.addWidget(pw)
        pw.clicked.connect(self.clicked.emit)
        pw.download_next.connect(self.download_next.emit)
        pw.open_folder.connect(self.open_folder.emit)
        pw.delete_requested.connect(self.delete_requested.emit)

        info = QVBoxLayout()
        info.setSpacing(1)
        name = QLabel(series["name"])
        name.setStyleSheet("font-weight: 800; font-size: 14px;")
        info.addWidget(name)
        created = str(series.get("created_at") or "")[:10]
        meta = QLabel(f"Added {created}" if created else "Donghua")
        meta.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
        info.addWidget(meta)
        col = QWidget()
        col.setLayout(info)
        lay.addWidget(col, 1)

        done = int(series.get("downloaded_episodes", 0) or 0)
        pend = int(series.get("pending_episodes", 0) or 0)
        tot = int(series.get("total_episodes", 0) or 0)
        tone = "emerald" if tot and done == tot else ("sky" if pend and done else "default")
        lay.addWidget(chip_tag(f"{done}/{tot} ready", tone))
        if pend:
            lay.addWidget(chip_tag(f"{pend} pending", "amber"))
        self.disk_lbl = QLabel("…")
        self.disk_lbl.setStyleSheet(f"color: {T_MUTED}; font-size: 11px; min-width: 64px;")
        self.disk_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.disk_lbl)

    def set_disk_size(self, size: int) -> None:
        self.disk_lbl.setText(human_size(size))

