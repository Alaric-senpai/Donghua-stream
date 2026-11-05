"""Full-width vertical list host with deterministic height (no layout drift)."""
from typing import List, Optional

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QWidget


class StackList(QWidget):
    """Stacks fixed-height rows edge-to-edge, with a small gutter between them."""

    def __init__(self, parent: Optional[QWidget] = None, spacing: int = 8):
        super().__init__(parent)
        self._items: List[QWidget] = []
        self._spacing = spacing
        self._width = 0

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

    def relayout(self) -> None:
        width = self.width()
        if width <= 1:
            parent = self.parentWidget()
            width = parent.width() - 8 if parent is not None else 800
        width = max(120, width)
        self._width = width
        y = 0
        for w in self._items:
            h = w.height() or w.sizeHint().height()
            w.setGeometry(0, y, width, h)
            y += h + self._spacing
        total = max(0, y - self._spacing) if self._items else 1
        if self.height() != total:
            self.setFixedHeight(total)
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        height = 0
        width = 0
        for w in self._items:
            height += (w.height() or w.sizeHint().height()) + self._spacing
            width = max(width, w.sizeHint().width())
        return QSize(width, max(1, height - self._spacing) if self._items else 1)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        if ev is not None and self.width() != self._width:
            self.relayout()
