"""Cinematic 16:10 artwork tile with hover actions, badge and progress."""
from typing import TYPE_CHECKING, Any, Dict, Optional

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap,
)
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QWidget

from ..icons import icon
from ..theme import (
    F_BODY, T_AMBER, T_EMERALD, T_LINE_STRONG, T_ON_PRIMARY, T_PRIMARY,
    T_ROSE2, T_SEC,
)
from ..utils import pct
from .primitives import btn, icon_btn

if TYPE_CHECKING:
    from ..infrastructure.thumbnails import ThumbnailStore


class PosterWidget(QFrame):
    """The artwork itself. Title/meta live in the parent SeriesCard."""

    clicked = pyqtSignal(int)
    download_next = pyqtSignal(int)
    open_folder = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    WIDTH = 208
    HEIGHT = 130
    RADIUS = 12

    def __init__(self, series: Dict[str, Any], posters: Dict[int, str],
                 thumbs: "ThumbnailStore", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.series = series
        self.vid = posters.get(series["id"], "")
        self._pix: Optional[QPixmap] = None
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if self.vid:
            self._pix = thumbs.get(self.vid)
        dl = max(0, int(series.get("pending_episodes", 0) or 0))
        tot = int(series.get("total_episodes", 0) or 0)
        done = int(series.get("downloaded_episodes", 0) or 0)
        self._progress = pct(done, tot)
        self._pending = dl
        self._badge = None
        if tot and done == tot:
            self._badge = ("COMPLETE", T_EMERALD, "#032b1c")
        elif dl and done == 0:
            self._badge = ("NEW", T_AMBER, "#2a1a02")
        elif dl:
            self._badge = (f"{dl} PENDING", T_PRIMARY, T_ON_PRIMARY)

        # ---- hover action tray
        self._hover_box = QWidget(self)
        self._hover_box.setObjectName("posterActions")
        self._hover_box.setStyleSheet(
            "QWidget#posterActions { background: rgba(2,6,23,215);"
            "border: 1px solid rgba(51,65,85,160); border-radius: 8px; }"
        )
        hb = QHBoxLayout(self._hover_box)
        hb.setContentsMargins(6, 4, 6, 4)
        hb.setSpacing(6)
        self._dl_btn = btn("Download", "primary", "Queue every pending episode", small=True)
        self._dl_btn.setFixedHeight(26)
        self._dl_btn.setIcon(icon("download", T_ON_PRIMARY, 12))
        self._dl_btn.setIconSize(QSize(12, 12))
        self._dl_btn.setEnabled(dl > 0)
        self._dl_btn.clicked.connect(lambda: self.download_next.emit(self.series["id"]))
        fbtn = icon_btn("", "Open series folder")
        fbtn.setFixedSize(26, 26)
        fbtn.setIcon(icon("folder", T_SEC, 13))
        fbtn.setIconSize(QSize(13, 13))
        fbtn.clicked.connect(lambda: self.open_folder.emit(self.series["id"]))
        dbtn = icon_btn("", "Delete series", danger=True)
        dbtn.setFixedSize(26, 26)
        dbtn.setIcon(icon("trash", T_ROSE2, 13))
        dbtn.setIconSize(QSize(13, 13))
        dbtn.clicked.connect(lambda: self.delete_requested.emit(self.series["id"]))
        hb.addWidget(self._dl_btn, 1)
        hb.addWidget(fbtn)
        hb.addWidget(dbtn)
        self._hover_box.hide()

    def set_poster(self, pix: QPixmap) -> None:
        self._pix = pix
        self.update()

    def poster_id(self) -> str:
        return self.vid

    def _art_path(self) -> QPainterPath:
        w, h = self.width(), self.height()
        r = self.RADIUS
        path = QPainterPath()
        path.moveTo(0, r)
        path.quadTo(0, 0, r, 0)
        path.lineTo(w - r, 0)
        path.quadTo(w, 0, w, r)
        path.lineTo(w, h)
        path.lineTo(0, h)
        path.closeSubpath()
        return path

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._hover_box.setGeometry(8, self.height() - 38, self.width() - 16, 30)

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

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = self._art_path()
        p.setClipPath(path)

        if self._pix and not self._pix.isNull():
            scaled = self._pix.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int((self.width() - scaled.width()) / 2),
                         int((self.height() - scaled.height()) / 2), scaled)
        else:
            grad = QLinearGradient(0, 0, self.width(), self.height())
            grad.setColorAt(0.0, QColor("#16233b"))
            grad.setColorAt(1.0, QColor("#0b1222"))
            p.fillRect(rect, grad)
            p.setPen(QColor("#475569"))
            f = p.font()
            f.setPixelSize(26)
            p.setFont(f)
            p.drawText(rect.adjusted(0, 0, 0, -8),
                       Qt.AlignmentFlag.AlignCenter, "▶")

        scrim = QLinearGradient(0, self.height() - 62, 0, self.height())
        scrim.setColorAt(0.0, QColor(2, 6, 23, 0))
        scrim.setColorAt(1.0, QColor(2, 6, 23, 190))
        p.fillRect(QRectF(0, self.height() - 62, self.width(), 62), scrim)

        if self._progress > 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#0a1424"))
            p.drawRect(QRectF(0, self.height() - 4, self.width(), 4))
            p.setBrush(QColor(T_EMERALD if self._progress >= 100 else T_PRIMARY))
            p.drawRect(QRectF(0, self.height() - 4,
                              self.width() * self._progress / 100.0, 4))

        if self._badge:
            label_, bg, fg = self._badge
            font = QFont(F_BODY)
            font.setPixelSize(9)
            font.setWeight(QFont.Weight.Bold)
            p.setFont(font)
            fm = p.fontMetrics()
            bw = fm.horizontalAdvance(label_) + 14
            badge_rect = QRectF(9, 9, bw, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(bg))
            p.drawRoundedRect(badge_rect, 6, 6)
            p.setPen(QColor(fg))
            p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, label_)

        p.setClipping(False)
        p.setPen(QColor(T_LINE_STRONG))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()
