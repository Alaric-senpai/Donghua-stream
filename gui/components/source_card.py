"""Cards for artwork pulled from a remote URL (source catalog entries).

The library's :class:`SeriesCard` paints artwork cached under a local video
id.  Explore cards and recommendation tiles on the source pages have only a
remote thumbnail URL, so this variant fetches it through the shared
``ThumbnailStore`` cache and repaints when the artwork lands.
"""
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import F_BODY, T_MUTED, T_TEXT
from .thumb import PosterThumb


class SourceSeriesCard(QFrame):
    """Poster tile with a compact metadata block, sized like SeriesCard."""

    selected = pyqtSignal(object)   # dict: the catalog entry the tile stands for

    WIDTH = 208
    HEIGHT = 196

    def __init__(self, item: Dict[str, Any],
                 thumbs: ThumbnailStore,
                 parent: Optional[QFrame] = None):
        super().__init__(parent)
        self._item = dict(item or {})
        self._thumbs = thumbs
        card_key = str(self._item.get("id") or self._item.get("slug") or "")
        # Distinct namespace from library cache keys.
        self._key = f"srccard:{card_key}:{self._item.get('thumbnail') or ''}"

        self.setObjectName("sourceCard")
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        title = str(self._item.get("title") or "Untitled")
        self.setToolTip(f"{title}\nClick to open the series details")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.poster = PosterThumb(thumbs, "", radius=12)
        self.poster.setFixedSize(self.WIDTH, 124)
        lay.addWidget(self.poster)

        meta = QFrame(self)
        meta_lay = QVBoxLayout(meta)
        meta_lay.setContentsMargins(2, 6, 2, 0)
        meta_lay.setSpacing(1)

        font = QFont(F_BODY)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        title_label = QLabel()
        metrics = QFontMetrics(font)
        title_label.setFont(font)
        title_label.setText(metrics.elidedText(
            title, Qt.TextElideMode.ElideRight, self.WIDTH - 4))
        title_label.setStyleSheet(
            f"color: {T_TEXT}; font-weight: 600; font-size: 13px;")
        title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        meta_lay.addWidget(title_label)

        bits = []
        count = self._item.get("episode_count")
        if isinstance(count, int) and count > 0:
            bits.append(f"{count} EPS")
        meta_text = str(self._item.get("views_text") or "").strip()
        if meta_text:
            bits.append(meta_text)
        status = str(self._item.get("status") or "").strip()
        source_label = str(
            self._item.get("channel") or self._item.get("source") or "")
        if status:
            bits.append(status)
        elif source_label:
            bits.append(source_label)
        if bits:
            meta_label = QLabel("  ·  ".join(bits))
            meta_label.setStyleSheet(f"color: {T_MUTED}; font-size: 10px;")
            meta_label.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            meta_lay.addWidget(meta_label)
        lay.addWidget(meta, 1)

        url = str(self._item.get("thumbnail") or "").strip()
        if url:
            pix = thumbs.get_url(self._key, url)
            if pix and not pix.isNull():
                self.poster.set_poster(pix)
            else:
                thumbs.loaded.connect(self._on_loaded)

    @property
    def item(self) -> Dict[str, Any]:
        return dict(self._item)

    def _on_loaded(self, key: str, pix) -> None:
        if key == self._key and pix is not None and not pix.isNull():
            try:
                self._thumbs.loaded.disconnect(self._on_loaded)
            except TypeError:
                pass
            self.poster.set_poster(pix)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(dict(self._item))
        super().mousePressEvent(event)
