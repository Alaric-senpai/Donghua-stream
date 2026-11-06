"""Responsive borderless grid for YouTube-style video tiles."""
from typing import List, Optional

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QWidget

from .video_card import VideoCard


class VideoGrid(QWidget):
    """Wrapping grid that stretches every tile to fill the available width."""

    GAP_X = 16
    GAP_Y = 22
    MIN_CARD_WIDTH = 250

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._cards: List[VideoCard] = []
        self._layout_width = 0

    @property
    def cards(self) -> List[VideoCard]:
        return list(self._cards)

    def set_cards(self, cards: List[VideoCard]) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = list(cards)
        for card in self._cards:
            card.setParent(self)
            card.show()
        self.relayout()

    def clear(self) -> None:
        self.set_cards([])

    def _content_width(self) -> int:
        width = self.width()
        if width <= 1:
            parent = self.parentWidget()
            if parent is not None:
                width = parent.width() - 4
        return max(260, width if width > 1 else 1100)

    def relayout(self) -> None:
        width = self._content_width()
        self._layout_width = width
        if not self._cards:
            self.setFixedHeight(1)
            return

        gap = self.GAP_X
        columns = max(1, (width + gap) // (self.MIN_CARD_WIDTH + gap))
        card_width = max(
            self.MIN_CARD_WIDTH,
            (width - gap * (columns - 1)) // columns,
        )

        x = y = 0
        row_height = 0
        for index, card in enumerate(self._cards):
            card.set_card_width(card_width)
            height = card.height()
            card.setGeometry(x, y, card_width, height)
            row_height = max(row_height, height)
            if index % columns == columns - 1 or index == len(self._cards) - 1:
                x = 0
                y += row_height + self.GAP_Y
                row_height = 0
            else:
                x += card_width + gap

        total = max(1, y - self.GAP_Y)
        if self.height() != total:
            self.setFixedHeight(total)
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        return QSize(self._content_width(), self.height() or 1)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        if ev is not None and self.width() != self._layout_width:
            self.relayout()
