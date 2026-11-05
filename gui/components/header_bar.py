"""Top bar: back, breadcrumb, global search, quality and live status chips."""
from typing import Optional

from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget,
)

from ..icons import icon
from ..theme import T_MUTED, T_ON_PRIMARY, T_SEC
from ..utils import QUALITY_OPTIONS, speed_text
from .primitives import btn, icon_btn


class HeaderBar(QWidget):
    """A calm command bar: navigation context on the left, actions on the right."""

    back_clicked = pyqtSignal()
    search_submitted = pyqtSignal(str)
    quality_changed = pyqtSignal(str)
    add_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(66)
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 12, 24, 8)
        root.setSpacing(12)

        self.back_btn = icon_btn("", "Back")
        self.back_btn.setFixedSize(32, 32)
        self.back_btn.setIcon(icon("chevron-left", T_SEC, 16))
        self.back_btn.setIconSize(QSize(16, 16))
        self.back_btn.clicked.connect(self.back_clicked.emit)
        self.back_btn.hide()
        root.addWidget(self.back_btn)

        self.crumb = QLabel("Home")
        self.crumb.setObjectName("crumb")
        root.addWidget(self.crumb)
        root.addStretch(1)

        # ---- global search: paste a URL to quick-add, type to filter the library
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search library or paste a video URL…")
        self.search.setMinimumWidth(260)
        self.search.setMaximumWidth(380)
        self.search.setFixedHeight(34)
        self.search.addAction(icon("search", T_MUTED, 16),
                              QLineEdit.ActionPosition.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(
            lambda: self.search_submitted.emit(self.search.text().strip()))
        root.addWidget(self.search, 1)

        self.quality = QComboBox()
        self.quality.setObjectName("chip")
        self.quality.setToolTip("Default download quality")
        for val, lab in QUALITY_OPTIONS:
            self.quality.addItem(lab, val)
        self.quality.setFixedHeight(30)
        self.quality.setFixedWidth(146)
        self.quality.currentIndexChanged.connect(
            lambda _i: self.quality_changed.emit(str(self.quality.currentData())))
        root.addWidget(self.quality)

        self.active_chip = QPushButton("Idle")
        self.active_chip.setObjectName("chip")
        self.active_chip.setFixedHeight(30)
        self.active_chip.setToolTip("Live download queue state")
        root.addWidget(self.active_chip)

        self.net_chip = QPushButton("Online")
        self.net_chip.setObjectName("chipEmerge")
        self.net_chip.setFixedHeight(30)
        self.net_chip.setToolTip("Network / downloader status")
        root.addWidget(self.net_chip)

        self.add_btn = btn("Add", "primary", "Open the registration wizard", small=True)
        self.add_btn.setFixedHeight(32)
        self.add_btn.setIcon(icon("plus", T_ON_PRIMARY, 13))
        self.add_btn.setIconSize(QSize(13, 13))
        self.add_btn.clicked.connect(self.add_clicked.emit)
        root.addWidget(self.add_btn)

    # ---- API used by MainWindow -------------------------------------------
    def set_breadcrumb(self, text: str) -> None:
        self.crumb.setText(text)

    def set_back_visible(self, visible: bool) -> None:
        self.back_btn.setVisible(visible)

    def set_active_text(self, text: str, busy: bool) -> None:
        self.active_chip.setText(text)
        self.active_chip.setObjectName("chipActive" if busy else "chip")
        self.net_chip.setText("Downloading" if busy else "Online")
        self.net_chip.setObjectName("chipEmerge" if busy else "chipTri")
        for w in (self.active_chip, self.net_chip):
            w.style().unpolish(w)
            w.style().polish(w)

    def set_speed(self, bps: float) -> None:
        if self.active_chip.objectName() == "chipActive" and bps:
            self.active_chip.setText(f"1 Active · {speed_text(bps)}")

    def set_quality_silent(self, value: str) -> None:
        idx = self.quality.findData(value)
        if idx >= 0:
            self.quality.blockSignals(True)
            self.quality.setCurrentIndex(idx)
            self.quality.blockSignals(False)
