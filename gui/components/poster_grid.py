"""Responsive poster grid that keeps every tile visible and aligned."""
from typing import List, Optional

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QWidget


class PosterGrid(QWidget):
    """Wrapping grid of fixed-size artwork tiles (12px gutters)."""

    GAP_X = 12
    GAP_Y = 12

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items: List[QWidget] = []
        self._layout_width = 0

    @property
    def items(self) -> List[QWidget]:
        return list(self._items)

    def set_items(self, items: List[QWidget]) -> None:
        for w in self._items:
            w.setParent(None)
            w.deleteLater()
        self._items = list(items)
        for w in self._items:
            w.setParent(self)
            w.show()
        self.relayout()

    def _content_width(self) -> int:
        width = self.width()
        if width <= 1:
            parent = self.parentWidget()
            if parent is not None:
                width = parent.width() - 4
        return max(160, width if width > 1 else 900)

    def relayout(self) -> None:
        if not self._items:
            self._layout_width = self._content_width()
            self.setFixedHeight(1)
            return

        width = self._content_width()
        self._layout_width = width
        first = self._items[0]
        tile_w = max(first.sizeHint().width(), first.minimumWidth(), 1)
        cols = max(1, (width + self.GAP_X) // (tile_w + self.GAP_X))

        x = y = 0
        row_h = 0
        for i, w in enumerate(self._items):
            # Honour setFixedSize(): some tiles (Explore video cards) are
            # wider than their layout sizeHint, and must not be squeezed.
            iw = max(w.sizeHint().width(), w.minimumWidth(), 1)
            ih = max(w.sizeHint().height(), w.minimumHeight(), 1)
            w.setGeometry(x, y, iw, ih)
            row_h = max(row_h, ih)
            col = i % cols
            if col == cols - 1 or i == len(self._items) - 1:
                x = 0
                y += row_h + self.GAP_Y
                row_h = 0
            else:
                x += iw + self.GAP_X

        total = max(1, y - self.GAP_Y) if self._items else 1
        if self.height() != total:
            self.setFixedHeight(total)
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        if not self._items:
            return QSize(208, 1)
        first = self._items[0]
        width = max(first.sizeHint().width(), 1)
        height = self.height() or 1
        return QSize(width, height)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        if ev is not None and self.width() != self._layout_width:
            self.relayout()
