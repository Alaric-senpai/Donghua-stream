"""Explore card: 16:9 YouTube artwork, metadata and library actions."""
from typing import Any, Dict, Optional

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from ..icons import icon
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import (
    F_BODY, T_CARD_SOFT, T_LINE_STRONG, T_MUTED, T_PRIMARY,
    T_SEC, T_TEXT,
)
from .primitives import btn, icon_btn


def _elide(text: str, width: int, size: int = 12,
           weight: QFont.Weight = QFont.Weight.Normal) -> str:
    font = QFont(F_BODY)
    font.setPixelSize(size)
    font.setWeight(weight)
    return QFontMetrics(font).elidedText(
        (text or "").strip(), Qt.TextElideMode.ElideRight, max(10, width))


class VideoThumb(QWidget):
    """Rounded 16:9 artwork with a duration pill painted on top."""

    def __init__(self, thumbs: ThumbnailStore, video: Dict[str, Any],
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs
        self.video = video
        self.key = f"yt:{video.get('id', '')}"
        self._pix: Optional[QPixmap] = thumbs.get_url(
            self.key, str(video.get("thumbnail") or ""))
        self.setFixedHeight(162)

    def update_poster(self, key: str, pix: QPixmap) -> bool:
        if key != self.key:
            return False
        self._pix = pix
        self.update()
        return True

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 11, 11)
        p.setClipPath(path)

        if self._pix and not self._pix.isNull():
            img = self._pix.toImage()
            if img.width() and img.height():
                scale = max(rect.width() / img.width(),
                            rect.height() / img.height(), 1e-6)
                scaled = img.scaled(
                    int(img.width() * scale), int(img.height() * scale),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                p.drawImage(int((rect.width() - scaled.width()) / 2),
                            int((rect.height() - scaled.height()) / 2), scaled)
        else:
            grad = QLinearGradient(0, 0, rect.width(), rect.height())
            grad.setColorAt(0.0, QColor("#16233b"))
            grad.setColorAt(1.0, QColor("#0b1222"))
            p.fillRect(rect, grad)
            p.setPen(QColor("#475569"))
            f = p.font()
            f.setPixelSize(30)
            p.setFont(f)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "▶")

        # Bottom scrim keeps the duration pill readable on bright artwork.
        scrim = QLinearGradient(0, rect.height() - 58, 0, rect.height())
        scrim.setColorAt(0.0, QColor(2, 6, 23, 0))
        scrim.setColorAt(1.0, QColor(2, 6, 23, 190))
        p.fillRect(QRectF(0, rect.height() - 58, rect.width(), 58), scrim)

        duration = str(self.video.get("duration_text") or "")
        if duration and duration != "—":
            p.setFont(QFont(F_BODY, 8, QFont.Weight.DemiBold))
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(duration) + 12
            pill = QRectF(rect.width() - tw - 9, rect.height() - 25, tw, 17)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(2, 6, 23, 215))
            p.drawRoundedRect(pill, 5, 5)
            p.setPen(QColor(T_TEXT))
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, duration)

        p.setClipping(False)
        p.setPen(QColor(T_LINE_STRONG))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 11, 11)
        p.end()


class VideoCard(QFrame):
    """Fixed-width video tile used by both Explore rails."""

    add_requested = pyqtSignal(dict)
    download_requested = pyqtSignal(dict)
    open_requested = pyqtSignal(dict)

    WIDTH = 296
    HEIGHT = 274

    def __init__(self, video: Dict[str, Any], thumbs: ThumbnailStore,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.video = dict(video or {})
        self.setObjectName("videoCard")
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(
            f"{self.video.get('title', '')}\n"
            f"{self.video.get('channel', '')}\n"
            "Open on YouTube")
        self.setStyleSheet(
            f"QFrame#videoCard {{ background: {T_CARD_SOFT};"
            f" border: 1px solid rgba(51,65,85,55); border-radius: 14px; }}"
            f"QFrame#videoCard:hover {{ background: #1b2942;"
            f" border-color: rgba(56,189,248,110); }}"
            f"QFrame#videoCard QLabel {{ background: transparent; }}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(7)

        self.thumb = VideoThumb(thumbs, self.video)
        lay.addWidget(self.thumb)

        title = QLabel(_elide(self.video.get("title", ""), self.WIDTH - 24, 13,
                              QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {T_TEXT}; font-size: 13px; font-weight: 700;")
        title.setToolTip(self.video.get("title", ""))
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(title)

        channel = QLabel(_elide(self.video.get("channel", "YouTube"),
                                self.WIDTH - 24, 11))
        channel.setStyleSheet(f"color: {T_SEC}; font-size: 11px;")
        channel.setToolTip(self.video.get("channel", ""))
        channel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(channel)

        meta_bits = [self.video.get("views_text", "")]
        age = self.video.get("age_text", "")
        if age:
            meta_bits.append(age)
        meta = QLabel("  ·  ".join(bit for bit in meta_bits if bit))
        meta.setStyleSheet(
            f"color: {T_MUTED}; font-family: 'Fira Code'; font-size: 9px;")
        lay.addWidget(meta)
        lay.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        add = btn("＋  Add", "primary", "Save this video to a library series", small=True)
        add.setFixedHeight(29)
        add.clicked.connect(lambda: self.add_requested.emit(dict(self.video)))
        actions.addWidget(add, 1)
        dl = icon_btn("", "Add and download immediately")
        dl.setIcon(icon("download", T_PRIMARY, 14))
        dl.setIconSize(QSize(14, 14))
        dl.clicked.connect(lambda: self.download_requested.emit(dict(self.video)))
        actions.addWidget(dl)
        open_btn = icon_btn("", "Open on YouTube")
        open_btn.setIcon(icon("external", T_SEC, 14))
        open_btn.setIconSize(QSize(14, 14))
        open_btn.clicked.connect(lambda: self.open_requested.emit(dict(self.video)))
        actions.addWidget(open_btn)
        lay.addLayout(actions)

    def update_poster(self, key: str, pix: QPixmap) -> None:
        self.thumb.update_poster(key, pix)

    def mouseDoubleClickEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit(dict(self.video))
        super().mouseDoubleClickEvent(ev)
