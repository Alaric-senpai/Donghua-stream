"""YouTube-style video tile used by the Explore feed.

The tile deliberately has no surrounding card chrome: artwork, a two-line
title, channel avatar and metadata sit directly on the page background, the
way YouTube's home grid does.  Library actions appear as translucent overlay
buttons only while the tile is hovered.
"""
from typing import Any, Dict, Optional

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QCursor, QFont, QLinearGradient, QPainter, QPainterPath,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from ..icons import icon
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import (
    F_BODY, T_AMBER2, T_LINE_STRONG, T_MUTED, T_PRIMARY, T_SEC, T_TEXT,
)
from .primitives import icon_btn


def _title_font() -> QFont:
    font = QFont(F_BODY)
    font.setPixelSize(14)
    font.setWeight(QFont.Weight.DemiBold)
    return font


def _meta_font(size: int = 12) -> QFont:
    font = QFont(F_BODY)
    font.setPixelSize(size)
    return font


class TwoLineLabel(QLabel):
    """Title label that wraps to two lines and elides the overflow."""

    def __init__(self, text: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._full = str(text or "").strip()
        self.setFont(_title_font())
        self.setStyleSheet(f"color: {T_TEXT};")
        self.setWordWrap(False)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.fontMetrics().lineSpacing() * 2 + 2)
        self.setToolTip(self._full)
        self._rewrap()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._rewrap()

    def _rewrap(self) -> None:
        width = max(10, self.width())
        metrics = self.fontMetrics()
        words = self._full.split()
        line1 = ""
        index = 0
        while index < len(words):
            trial = f"{line1} {words[index]}".strip()
            if line1 and metrics.horizontalAdvance(trial) > width:
                break
            line1 = trial
            index += 1
        line1 = metrics.elidedText(line1, Qt.TextElideMode.ElideRight, width)
        rest = " ".join(words[index:])
        line2 = metrics.elidedText(rest, Qt.TextElideMode.ElideRight, width) if rest else ""
        self.setText(line1 + (f"\n{line2}" if line2 else ""))


class ElidedLabel(QLabel):
    """One-line label that elides cleanly as the tile width changes."""

    def __init__(self, text: str, *, color: str = T_SEC, size: int = 12,
                 weight: QFont.Weight = QFont.Weight.Normal,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._full = str(text or "").strip()
        font = _meta_font(size)
        font.setWeight(weight)
        self.setFont(font)
        self.setStyleSheet(f"color: {color};")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.fontMetrics().height())
        self.setToolTip(self._full)
        self._elide()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._elide()

    def _elide(self) -> None:
        self.setText(self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideRight, max(10, self.width())))


class ChannelAvatar(QWidget):
    """Small circular channel avatar with a generated fallback."""

    def __init__(self, thumbs: ThumbnailStore, channel_id: str, url: str,
                 name: str, size: int = 36,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._size = size
        self._thumbs = thumbs
        self._letter = (str(name or "Source").strip() or "S")[:1].upper()
        self._key = f"chan:{channel_id or name or 'source'}"
        self._pix: Optional[QPixmap] = None
        if url:
            self._pix = thumbs.get_url(self._key, url)
        self.setToolTip(str(name or "Source"))

    def set_source(self, channel_id: str, url: str, name: str) -> None:
        """Point the avatar at a channel, fetching artwork when available."""
        name = str(name or "Source")
        key = f"chan:{channel_id or name or 'source'}"
        self._letter = (name.strip() or "S")[:1].upper()
        self.setToolTip(name)
        if key == self._key and (not url or self._pix is not None):
            return
        self._key = key
        self._pix = None
        if url:
            self._pix = self._thumbs.get_url(key, url)
        self.update()

    def update_avatar(self, key: str, pix: QPixmap) -> bool:
        if key != self._key or pix.isNull():
            return False
        self._pix = pix
        self.update()
        return True

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addEllipse(rect)
        p.setClipPath(path)
        if self._pix and not self._pix.isNull():
            img = self._pix.toImage()
            if img.width() and img.height():
                scale = max(rect.width() / img.width(),
                            rect.height() / img.height())
                scaled = img.scaled(
                    int(img.width() * scale), int(img.height() * scale),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                p.drawImage(
                    int((rect.width() - scaled.width()) / 2),
                    int((rect.height() - scaled.height()) / 2), scaled)
        else:
            grad = QLinearGradient(0, 0, self._size, self._size)
            grad.setColorAt(0.0, QColor("#1d4ed8"))
            grad.setColorAt(1.0, QColor("#0e7490"))
            p.fillRect(self.rect(), grad)
            p.setPen(QColor(T_TEXT))
            font = QFont(F_BODY)
            font.setPixelSize(max(12, int(self._size * 0.38)))
            font.setWeight(QFont.Weight.Bold)
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._letter)
        p.setClipping(False)
        p.setPen(QColor(T_LINE_STRONG))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)
        p.end()


class VideoThumb(QWidget):
    """Rounded 16:9 artwork with duration and membership pills."""

    def __init__(self, thumbs: ThumbnailStore, video: Dict[str, Any],
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs
        self.video = video
        self.key = (
            f"card:{video.get('source') or 'youtube'}:{video.get('id', '')}")
        self._pix: Optional[QPixmap] = thumbs.get_url(
            self.key, str(video.get("thumbnail") or ""))
        self._hovered = False
        self.setMinimumHeight(120)

    def update_poster(self, key: str, pix: QPixmap) -> bool:
        if key != self.key or pix.isNull():
            return False
        self._pix = pix
        self.update()
        return True

    def set_hovered(self, hovered: bool) -> None:
        if self._hovered != hovered:
            self._hovered = hovered
            self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
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
                p.drawImage(
                    int((rect.width() - scaled.width()) / 2),
                    int((rect.height() - scaled.height()) / 2), scaled)
        else:
            grad = QLinearGradient(0, 0, rect.width(), rect.height())
            grad.setColorAt(0.0, QColor("#16233b"))
            grad.setColorAt(1.0, QColor("#0b1222"))
            p.fillRect(rect, grad)
            p.setPen(QColor("#475569"))
            font = p.font()
            font.setPixelSize(30)
            p.setFont(font)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "▶")

        if self._hovered:
            p.fillRect(rect, QColor(255, 255, 255, 14))

        scrim = QLinearGradient(0, rect.height() - 62, 0, rect.height())
        scrim.setColorAt(0.0, QColor(2, 6, 23, 0))
        scrim.setColorAt(1.0, QColor(2, 6, 23, 205))
        p.fillRect(QRectF(0, rect.height() - 62, rect.width(), 62), scrim)

        self._draw_badge(p, rect)
        duration = str(self.video.get("duration_text") or "")
        if duration and duration != "—":
            p.setFont(QFont(F_BODY, 8, QFont.Weight.DemiBold))
            metrics = p.fontMetrics()
            tw = metrics.horizontalAdvance(duration) + 12
            pill = QRectF(rect.width() - tw - 9, rect.height() - 25, tw, 17)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(2, 6, 23, 225))
            p.drawRoundedRect(pill, 4, 4)
            p.setPen(QColor(T_TEXT))
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, duration)

        p.setClipping(False)
        p.setPen(QColor(T_PRIMARY if self._hovered else T_LINE_STRONG))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        p.end()

    def _draw_badge(self, p: QPainter, rect: QRectF) -> None:
        label = ""
        if self.video.get("members_only"):
            label = "MEMBERS"
        elif self.video.get("members_first"):
            label = "MEMBERS FIRST"
        if not label:
            return
        p.setFont(QFont(F_BODY, 7, QFont.Weight.Bold))
        metrics = p.fontMetrics()
        tw = metrics.horizontalAdvance(label) + 14
        pill = QRectF(9, 9, tw, 18)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(120, 53, 15, 225))
        p.drawRoundedRect(pill, 4, 4)
        p.setPen(QColor(T_AMBER2))
        p.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)


class CardActions(QWidget):
    """Small translucent action row shown over the artwork on hover."""

    def __init__(self, card: "VideoCard", parent: QWidget):
        super().__init__(parent)
        self._card = card
        self.setFixedSize(104, 30)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.add_btn = icon_btn("", "Add to a library series")
        self.add_btn.setIcon(icon("plus", T_TEXT, 14))
        self.add_btn.setIconSize(QSize(14, 14))
        self.add_btn.setFixedSize(30, 30)
        self.add_btn.clicked.connect(
            lambda: self._card.add_requested.emit(dict(self._card.video)))
        row.addWidget(self.add_btn)

        self.download_btn = icon_btn("", "Add and download now")
        self.download_btn.setIcon(icon("download", T_TEXT, 14))
        self.download_btn.setIconSize(QSize(14, 14))
        self.download_btn.setFixedSize(30, 30)
        self.download_btn.clicked.connect(
            lambda: self._card.download_requested.emit(dict(self._card.video)))
        row.addWidget(self.download_btn)

        self.open_btn = icon_btn("", "Open the source page")
        self.open_btn.setIcon(icon("external", T_TEXT, 14))
        self.open_btn.setIconSize(QSize(14, 14))
        self.open_btn.setFixedSize(30, 30)
        self.open_btn.clicked.connect(
            lambda: self._card.open_requested.emit(dict(self._card.video)))
        row.addWidget(self.open_btn)

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(max(8, parent.width() - self.width() - 9), 8)


class VideoCard(QWidget):
    """Borderless YouTube-style tile used by the Explore feed."""

    add_requested = pyqtSignal(dict)
    download_requested = pyqtSignal(dict)
    open_requested = pyqtSignal(dict)

    MIN_WIDTH = 240

    def __init__(self, video: Dict[str, Any], thumbs: ThumbnailStore,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.video = dict(video or {})
        self.setObjectName("ytVideoCard")
        self.setStyleSheet("QWidget#ytVideoCard { background: transparent; }")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(
            f"{self.video.get('title', '')}\n"
            f"{self.video.get('channel', '')}\n"
            "Double-click to open the source page")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.thumb = VideoThumb(thumbs, self.video)
        outer.addWidget(self.thumb)

        info = QHBoxLayout()
        info.setContentsMargins(0, 10, 0, 0)
        info.setSpacing(10)
        self.avatar = ChannelAvatar(
            thumbs,
            str(self.video.get("channel_id") or ""),
            str(self.video.get("channel_avatar") or ""),
            str(self.video.get("channel") or "Source"),
            36,
        )
        info.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        self.title_label = TwoLineLabel(str(self.video.get("title") or ""))
        text.addWidget(self.title_label)
        self.channel_label = ElidedLabel(
            str(self.video.get("channel") or "Source"), color=T_SEC, size=12)
        text.addWidget(self.channel_label)
        views = str(self.video.get("views_text") or "").strip()
        age = str(self.video.get("age_text") or "").strip()
        meta = "  ·  ".join(bit for bit in (views, age) if bit)
        self.meta_label = ElidedLabel(meta or "Source", color=T_MUTED, size=11)
        text.addWidget(self.meta_label)
        info.addLayout(text, 1)
        outer.addLayout(info)

        self.actions = CardActions(self, self.thumb)
        self.actions.reposition()
        self.actions.hide()

        self.set_card_width(300)

    def set_card_width(self, width: int) -> None:
        width = max(self.MIN_WIDTH, int(width))
        self.setFixedWidth(width)
        thumb_h = max(120, round(width * 9 / 16))
        self.thumb.setFixedHeight(thumb_h)
        text_h = (self.title_label.height() + self.channel_label.height()
                  + self.meta_label.height() + 4)
        info_h = max(self.avatar.height(), text_h)
        self.setFixedHeight(thumb_h + 10 + info_h + 2)
        self.actions.reposition()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self.actions.reposition()

    def update_asset(self, key: str, pix: QPixmap) -> None:
        self.thumb.update_poster(key, pix)
        self.avatar.update_avatar(key, pix)

    def _set_hovered(self, hovered: bool) -> None:
        self.thumb.set_hovered(hovered)
        self.actions.setVisible(hovered)
        if hovered:
            self.actions.raise_()

    def enterEvent(self, ev) -> None:
        self._set_hovered(True)
        super().enterEvent(ev)

    def leaveEvent(self, ev) -> None:
        # Moving onto one of the overlay buttons can produce a parent leave
        # event; keep the controls visible while the pointer is inside.
        local = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(local):
            self._set_hovered(False)
        super().leaveEvent(ev)

    def mouseDoubleClickEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit(dict(self.video))
        super().mouseDoubleClickEvent(ev)
