"""Wrapping grid that lays out fixed-size tiles like the Stitch catalog."""
from typing import List, Optional

from PyQt6.QtWidgets import QWidget


class PosterGrid(QWidget):
    """Wrapping grid of fixed-size child widgets (cards or rows)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items: List[QWidget] = []
        self._spacing = (14, 14)

    def set_items(self, items: List[QWidget]) -> None:
        for w in self._items:
            w.setParent(None)
            w.deleteLater()
        self._items = list(items)
        self.relayout()

    def relayout(self) -> None:
        cw = self.width() or (self.parent().width() if self.parent() else 900)
        ideal = self._items[0].sizeHint().width() if self._items else 200
        cols = max(1, int((cw - 4) // (ideal + self._spacing[0])))
        x = y = 0
        last_h = 0
        for i, w in enumerate(self._items):
            hint = w.sizeHint()
            if hint.width() <= 0:
                hint = w.size()
            w.setParent(self)
            w.setGeometry(x, y, max(hint.width(), 0), max(hint.height(), 0))
            last_h = hint.height()
            col = i % cols
            if col == cols - 1 or i == len(self._items) - 1:
                x = 0
                y += last_h + self._spacing[1]
            else:
                x += hint.width() + self._spacing[0]
        total_h = y if not self._items else max(1, y - (last_h + self._spacing[1]) // 2)
        self.setMinimumSize(1, y + (last_h if self._items else 0))
        self.setMaximumHeight((y + last_h if self._items else 0) or 16777215)
        self.updateGeometry()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self.relayout()

