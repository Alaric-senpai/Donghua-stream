"""16:10 poster tile: scrim, progress strip, badge and hover actions."""
from typing import TYPE_CHECKING, Any, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ..theme import (
    T_AMBER, T_BORDER, T_CARD, T_EMERALD, T_FONT, T_MUTED, T_PRIMARY,
    T_RAIL, T_SEC, T_TEXT,
)
from ..utils import pct
from .primitives import btn, icon_btn

if TYPE_CHECKING:
    from ..infrastructure.thumbnails import ThumbnailStore


class PosterWidget(QFrame):
    clicked = pyqtSignal(int)
    download_next = pyqtSignal(int)
    open_folder = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, series: Dict[str, Any], posters: Dict[int, str],
                 thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.series = series
        self.vid = posters.get(series["id"], "")
        self._pix: Optional[QPixmap] = None
        self.setFixedSize(216, 214)   # 16:10 poster @216 -> 216x135 + meta
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if self.vid:
            self._pix = thumbs.get(self.vid)
        dl = max(0, int(series.get("pending_episodes", 0) or 0))
        tot = int(series.get("total_episodes", 0) or 0)
        done = int(series.get("downloaded_episodes", 0) or 0)
        self._progress = pct(done, tot)

        # ---- action overlay (hover)
        self._hover_box = QWidget(self)
        hb = QHBoxLayout(self._hover_box)
        hb.setContentsMargins(10, 8, 10, 8)
        hb.setSpacing(6)
        self._hover_box.hide()
        pbtn = btn("▶  Download Next", "primary" if dl else "ghost", "Queue every pending episode")
        pbtn.setMinimumHeight(26)
        pbtn.setEnabled(dl > 0)
        pbtn.clicked.connect(lambda: self.download_next.emit(self.series["id"]))
        fbtn = icon_btn("⇗", "Open series folder")
        fbtn.clicked.connect(lambda: self.open_folder.emit(self.series["id"]))
        dbtn = icon_btn("␥", "Delete series")
        dbtn.clicked.connect(lambda: self.delete_requested.emit(self.series["id"]))
        hb.addWidget(pbtn, 1)
        hb.addWidget(fbtn)
        hb.addWidget(dbtn)

        # ---- meta labels under the poster
        self._title = QLabel(self.series["name"])
        self._title.setStyleSheet(f"color: {T_TEXT}; font-weight: 800; font-size: 12px;")
        self._sub = QLabel(f"{tot} EPS  ·  {done} ready")
        self._sub.setStyleSheet(f"color: {T_SEC}; font-size: 10px;")
        self._badge = None
        if tot and done == tot:
            self._badge = ("COMPLETE", T_EMERALD)
        elif dl and done == 0:
            self._badge = ("NEW", T_AMBER)
        elif dl:
            self._badge = (f"{dl} PENDING", T_PRIMARY)
        self._position_meta()

    def set_poster(self, pix: QPixmap) -> None:
        self._pix = pix
        self.update()

    def poster_id(self) -> str:
        return self.vid

    def _poster_h(self) -> int:
        return int(self.width() * 0.625)

    def _position_meta(self) -> None:
        w = self.width()
        ph = self._poster_h()
        self._hover_box.setGeometry(6, max(0, ph - 6), w - 12, 38)
        self._title.setGeometry(12, ph + 8, w - 24, 18)
        self._sub.setGeometry(12, ph + 26, w - 24, 14)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._position_meta()

    def enterEvent(self, ev) -> None:
        super().enterEvent(ev)
        self._hover_box.show()
        self._hover_box.raise_()

    def leaveEvent(self, ev) -> None:
        super().leaveEvent(ev)
        self._hover_box.hide()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.series["id"])
        super().mousePressEvent(ev)

    def paintEvent(self, ev) -> None:
        from PyQt6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ph = self._poster_h()
        w = self.width()

        # card body
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T_CARD))
        p.drawRoundedRect(0, 0, w, self.height(), 16, 16)

        # poster (cover-fit)
        if self._pix and not self._pix.isNull():
            img = self._pix.toImage()
            cw, ch = img.width(), img.height()
            scale = max(w / cw, ph / ch, 1e-6)
            tw, th = int(cw * scale), int(ch * scale)
            small = img.scaled(tw, th, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            dx = int((w - small.width()) / 2)
            dy = int((ph - small.height()) / 2)
            p.save()
            p.setClipRect(0, 0, w, ph)
            p.drawImage(dx, dy, small)
            p.restore()
        else:
            grad = QLinearGradient(0, 0, w, ph)
            grad.setColorAt(0, QColor("#122036"))
            grad.setColorAt(1, QColor(T_RAIL))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(0, 0, w, ph))
            p.setPen(QColor(T_MUTED))
            f = p.font()
            f.setPixelSize(30)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, ph), Qt.AlignmentFlag.AlignCenter, "▶")

        # gradient scrim on poster bottom
        scrim = QLinearGradient(0, float(ph - 70), 0, float(ph))
        scrim.setColorAt(0, QColor(2, 6, 23, 0))
        scrim.setColorAt(1, QColor(2, 6, 23, 200))
        p.fillRect(QRectF(0, ph - 70, w, 70), scrim)

        # dual-tone progress bar pinned to poster bottom
        if self._progress > 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#0e1a30"))
            p.drawRoundedRect(QRectF(10, ph - 10, w - 20, 5, ), 3, 3)
            p.setBrush(QColor(T_EMERALD if self._progress >= 100 else T_PRIMARY))
            p.drawRoundedRect(QRectF(10, ph - 10, max(6.0, (w - 20) * self._progress / 100.0), 5), 3, 3)

        # badge chip top-left
        if self._badge:
            label_, col = self._badge
            p.setFont(QFont(T_FONT, 8, QFont.Weight.Bold))
            fx = p.fontMetrics().horizontalAdvance(label_) + 16
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(col))
            p.drawRoundedRect(QRectF(10, 10, fx, 18), 9, 9)
            p.setPen(QColor("#04121f"))
            p.drawText(QRectF(10, 10, fx, 18), Qt.AlignmentFlag.AlignCenter, label_)

        p.setPen(QColor(T_PRIMARY if self._progress >= 100 else T_BORDER))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, self.height() - 1), 16, 16)

