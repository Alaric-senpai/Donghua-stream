"""Painted thumbnail + small poster artwork helpers (rounded, cover-fit)."""
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QWidget

if TYPE_CHECKING:
    from ..infrastructure.thumbnails import ThumbnailStore


class PosterThumb(QWidget):
    """Rounded cover-fit artwork with a quiet fallback — used outside the grid."""

    def __init__(self, thumbs: "ThumbnailStore", vid: str = "",
                 radius: int = 10, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs
        self.vid = vid or ""
        self._radius = radius
        self._pix: Optional[QPixmap] = None
        if self.vid:
            self._pix = thumbs.get(self.vid)
        self.setMinimumSize(48, 36)

    def set_poster(self, pix: QPixmap) -> None:
        self._pix = pix
        self.update()

    # Compatibility with the old QLabel-based detail poster.
    setPixmap = set_poster

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5),
                            self._radius, self._radius)
        p.setClipPath(path)
        if self._pix and not self._pix.isNull():
            img = self._pix.toImage()
            if img.width() and img.height():
                scale = max(rect.width() / img.width(), rect.height() / img.height(), 1e-6)
                small = img.scaled(
                    int(img.width() * scale), int(img.height() * scale),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                p.drawImage(int((rect.width() - small.width()) / 2),
                            int((rect.height() - small.height()) / 2), small)
        else:
            grad = QLinearGradient(0, 0, rect.width(), rect.height())
            grad.setColorAt(0.0, QColor("#16233b"))
            grad.setColorAt(1.0, QColor("#0b1222"))
            p.fillRect(rect, grad)
            p.setPen(QColor("#475569"))
            f = p.font()
            f.setPixelSize(22)
            p.setFont(f)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "▶")
        p.setClipping(False)
        p.setPen(QColor(71, 85, 105, 120))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5),
                          self._radius, self._radius)
        p.end()
