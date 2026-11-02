"""Top bar: breadcrumb, global search, quality selector, status chips."""
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget,
)

from ..utils import QUALITY_OPTIONS, speed_text
from .primitives import icon_btn


class HeaderBar(QWidget):
    """Back arrow + breadcrumb | global search | status chips."""

    back_clicked = pyqtSignal()
    search_submitted = pyqtSignal(str)
    quality_changed = pyqtSignal(str)
    add_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(64)
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 10, 24, 4)
        root.setSpacing(12)

        self.back_btn = icon_btn("‹", "Back")
        self.back_btn.clicked.connect(self.back_clicked.emit)
        root.addWidget(self.back_btn)

        self.crumb = QLabel("Library")
        self.crumb.setStyleSheet("font-size: 14px; font-weight: 700; color: #cbd5e1;")
        root.addWidget(self.crumb)
        root.addStretch(1)

        # ---- global search (URL paste → QuickUrlDialog; text → library filter)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Paste any video URL or search your library…")
        self.search.setFixedWidth(340)
        self.search.returnPressed.connect(lambda: self.search_submitted.emit(self.search.text().strip()))
        root.addWidget(self.search)

        # ---- quality chip (QComboBox styled as a pill)
        self.quality = QComboBox()
        self.quality.setObjectName("chip")
        for val, lab in QUALITY_OPTIONS:
            self.quality.addItem(lab, val)
        self.quality.setFixedHeight(28)
        self.quality.style().unpolish(self.quality)
        self.quality.style().polish(self.quality)
        self.quality.currentIndexChanged.connect(
            lambda i: self.quality_changed.emit(self.quality.currentData()))
        root.addWidget(self.quality)

        # ---- active download chip
        self.active_chip = QPushButton("Idle")
        self.active_chip.setObjectName("chip")
        self.active_chip.setFixedHeight(28)
        root.addWidget(self.active_chip)

        # ---- network chip
        self.net_chip = QPushButton("Fast / Online")
        self.net_chip.setObjectName("chipTri")
        self.net_chip.setFixedHeight(28)
        root.addWidget(self.net_chip)

        # add donghua quick button
        self.add_btn = icon_btn("＋", "Quick-add a URL")
        self.add_btn.clicked.connect(self.add_clicked.emit)
        root.addWidget(self.add_btn)

    def set_breadcrumb(self, text: str) -> None:
        self.crumb.setText(text)

    def set_active_text(self, text: str, busy: bool) -> None:
        self.active_chip.setText(text)
        self.active_chip.setObjectName("chipActive" if busy else "chip")
        self.net_chip.setText(("Downloading" if busy else "Fast / Online"))
        self.net_chip.setObjectName("chipEmerge" if busy else "chipTri")
        for w in (self.active_chip, self.net_chip):
            w.style().unpolish(w)
            w.style().polish(w)

    def set_speed(self, bps: float) -> None:
        if self.active_chip.objectName() == "chipActive" and bps:
            self.active_chip.setText(f"1 Active ({speed_text(bps)})")

    def set_quality_silent(self, value: str) -> None:
        idx = self.quality.findData(value)
        if idx >= 0:
            self.quality.blockSignals(True)
            self.quality.setCurrentIndex(idx)
            self.quality.blockSignals(False)

