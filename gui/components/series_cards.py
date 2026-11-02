"""Catalog cards: poster grid card and the full-width registry row."""
from typing import Any, Dict, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from ..icons import icon
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import (
    F_BODY, T_AMBER2, T_EMERALD2, T_MUTED, T_PRIMARY, T_ROSE2, T_SEC, T_TEXT,
)
from ..utils import human_size
from .poster import PosterWidget
from .primitives import chip_tag, icon_btn
from .thumb import PosterThumb


def _short(text: str, limit: int = 48) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class SeriesCard(QFrame):
    """Poster tile with a compact metadata block underneath."""

    clicked = pyqtSignal(int)
    WIDTH = 208
    HEIGHT = 196

    def __init__(self, series: Dict[str, Any], posters: Dict[int, str],
                 thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.series = series
        self.setObjectName("seriesCard")
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{series.get('name', '')}\nClick to open the series")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.poster = PosterWidget(series, posters, thumbs)
        lay.addWidget(self.poster)

        meta = QWidget()
        ml = QVBoxLayout(meta)
        ml.setContentsMargins(12, 7, 12, 9)
        ml.setSpacing(2)

        title = QLabel()
        title.setStyleSheet(f"color: {T_TEXT}; font-weight: 700; font-size: 13px;")
        font = QFont(F_BODY)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        title.setFont(font)
        title.setText(QFontMetrics(font).elidedText(
            series.get("name", "") or "Untitled", Qt.TextElideMode.ElideRight,
            self.WIDTH - 24))
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        ml.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(5)
        tot = int(series.get("total_episodes", 0) or 0)
        done = int(series.get("downloaded_episodes", 0) or 0)
        pend = int(series.get("pending_episodes", 0) or 0)
        if tot and done >= tot:
            dot_color = T_EMERALD2
        elif pend:
            dot_color = T_PRIMARY
        else:
            dot_color = T_AMBER2
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {dot_color}; font-size: 8px;")
        row.addWidget(dot)
        sub = QLabel(f"{tot} EPS  ·  {done} ready")
        sub.setStyleSheet(f"color: {T_MUTED}; font-size: 10px;")
        row.addWidget(sub)
        row.addStretch(1)
        self.disk_lbl = QLabel("…")
        self.disk_lbl.setStyleSheet(f"color: {T_MUTED}; font-size: 9px; font-family: 'Fira Code';")
        self.disk_lbl.setToolTip("Disk usage of the series folder")
        row.addWidget(self.disk_lbl)
        ml.addLayout(row)
        lay.addWidget(meta, 1)

        self.poster.clicked.connect(self.clicked.emit)

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(int(self.series["id"]))
        super().mousePressEvent(ev)

    def set_disk_size(self, size: int) -> None:
        self.disk_lbl.setText(human_size(max(0, int(size or 0))))


class CompactSeriesRow(QFrame):
    """Scannable full-width registry row: artwork, identity, health, actions."""

    clicked = pyqtSignal(int)
    download_next = pyqtSignal(int)
    open_folder = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    HEIGHT = 78

    def __init__(self, series: Dict[str, Any], posters: Dict[int, str],
                 thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.series = series
        self.setObjectName("listRow")
        self.setFixedHeight(self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{series.get('name', '')}\nClick to open the series")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        vid = posters.get(series["id"], "")
        self.poster = PosterThumb(thumbs, vid, radius=8)
        self.poster.setFixedSize(104, 58)
        lay.addWidget(self.poster)

        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(_short(series.get("name", ""), 62))
        name.setStyleSheet(f"color: {T_TEXT}; font-weight: 700; font-size: 14px;")
        name.setToolTip(series.get("name", ""))
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        info.addWidget(name)
        created = str(series.get("created_at") or "")[:10]
        key = series.get("key") or ""
        bits = []
        if key:
            bits.append(str(key))
        if created:
            bits.append(f"added {created}")
        meta = QLabel("  ·  ".join(bits) or "Donghua")
        meta.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
        meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        info.addWidget(meta)
        col = QWidget()
        col.setLayout(info)
        col.setMinimumWidth(120)
        col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(col, 1)

        done = int(series.get("downloaded_episodes", 0) or 0)
        pend = int(series.get("pending_episodes", 0) or 0)
        tot = int(series.get("total_episodes", 0) or 0)
        tone = "emerald" if tot and done == tot else ("sky" if pend and done else "default")
        lay.addWidget(chip_tag(f"{done}/{tot} ready", tone))
        if pend:
            lay.addWidget(chip_tag(f"{pend} pending", "amber"))

        self.disk_lbl = QLabel("…")
        self.disk_lbl.setStyleSheet(
            f"color: {T_MUTED}; font-size: 10px; font-family: 'Fira Code';")
        self.disk_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.disk_lbl.setFixedWidth(72)
        self.disk_lbl.setToolTip("Disk usage of the series folder")
        lay.addWidget(self.disk_lbl)

        dl = icon_btn("", "Download all pending episodes")
        dl.setIcon(icon("download", T_PRIMARY, 15))
        dl.setIconSize(QSize(15, 15))
        dl.clicked.connect(lambda: self.download_next.emit(int(self.series["id"])))
        folder = icon_btn("", "Open series folder")
        folder.setIcon(icon("folder", T_SEC, 15))
        folder.setIconSize(QSize(15, 15))
        folder.clicked.connect(lambda: self.open_folder.emit(int(self.series["id"])))
        delete = icon_btn("", "Delete series", danger=True)
        delete.setIcon(icon("trash", T_ROSE2, 15))
        delete.setIconSize(QSize(15, 15))
        delete.clicked.connect(lambda: self.delete_requested.emit(int(self.series["id"])))
        for b in (dl, folder, delete):
            lay.addWidget(b)

        chevron = QLabel()
        chevron.setPixmap(icon("chevron-right", T_MUTED, 16).pixmap(16, 16))
        lay.addWidget(chevron)

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(int(self.series["id"]))
        super().mousePressEvent(ev)

    def set_disk_size(self, size: int) -> None:
        self.disk_lbl.setText(human_size(max(0, int(size or 0))))
