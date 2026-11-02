"""Preset storage-location tile with a live free-space chip."""
import os
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..theme import T_BORDER, T_MUTED, T_PRIMARY, T_RAIL, T_SEC
from ..utils import disk_free, human_size
from .primitives import chip_tag


class StorageCard(QPushButton):
    chosen = pyqtSignal(str)   # resolved base dir

    def __init__(self, glyph: str, name: str, default_dir: str,
                 recommended: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(96)
        self.setStyleSheet(f"""
            QPushButton {{ background: {T_RAIL}; border: 1px solid {T_BORDER};
                           border-radius: 16px; text-align: left; }}
            QPushButton:checked {{ border: 2px solid {T_PRIMARY}; background: #122036; }}
            QPushButton:hover {{ background: #17233c; }}
        """)
        self._dir = default_dir
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 14, 10)
        lay.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(8)
        self._glyph = QLabel(glyph)
        self._glyph.setStyleSheet(f"font-size: 20px; color: {T_PRIMARY};")
        top.addWidget(self._glyph)
        self._name = QLabel(name)
        self._name.setStyleSheet("font-weight: 800; font-size: 14px;")
        top.addWidget(self._name)
        top.addStretch(1)
        if recommended:
            top.addWidget(chip_tag("Recommended", "sky"))
        self._free = QLabel("checking…")
        self._free.setStyleSheet(f"color: {T_SEC}; font-size: 11px;")
        top.addWidget(self._free)
        lay.addLayout(top)
        self._path = QLabel(default_dir.replace(os.path.expanduser("~"), "~"))
        self._path.setStyleSheet(f"color: {T_MUTED}; font-size: 11px; font-family: monospace;")
        lay.addWidget(self._path)
        self.toggled.connect(self._on_toggle)

    def refresh_free(self) -> None:
        free = disk_free(self._dir)
        self._free.setText(f"{human_size(free)} free" if free is not None else "unavailable")

    def set_dir(self, path: str) -> None:
        self._dir = path
        self._path.setText(path.replace(os.path.expanduser("~"), "~"))
        self.refresh_free()

    def dir(self) -> str:
        return self._dir

    def _on_toggle(self, checked: bool) -> None:
        if checked:
            self.chosen.emit(self._dir)

