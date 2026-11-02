"""Daemon-sync strip that sits above the catalog grid."""
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ..theme import T_MUTED, T_SEC
from .primitives import btn, chip_tag


class TelemetryStrip(QFrame):
    sync_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(52)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 8, 18, 8)
        lay.setSpacing(10)
        self.sync_chip = chip_tag("● Daemon Sync: Active", "emerald")
        lay.addWidget(self.sync_chip)
        self.display_chip = QLabel("Displaying 0 of 0 donghua")
        self.display_chip.setStyleSheet(f"color: {T_SEC}; font-size: 12px;")
        lay.addWidget(self.display_chip)
        self.disk_chip = QLabel("")
        self.disk_chip.setStyleSheet(f"color: {T_MUTED}; font-size: 12px;")
        lay.addWidget(self.disk_chip)
        lay.addStretch(1)
        sync_btn = btn("⟳  Sync All Incomplete", "chip", "Run archive re-sync for every series")
        sync_btn.clicked.connect(self.sync_requested.emit)
        lay.addWidget(sync_btn)

    def set_counts(self, shown: int, total: int, online: bool = True) -> None:
        self.display_chip.setText(f"Displaying {shown} of {total} donghua")
        self.sync_chip.setText(("● Daemon Sync: Active" if online else "◌ Daemon Sync: Offline"))

