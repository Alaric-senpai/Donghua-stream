"""Selectable storage-location tile with live free-space telemetry."""
import os
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from ..theme import (
    T_LINE, T_MUTED, T_ON_PRIMARY, T_PRIMARY, T_RAIL_DEEP, T_SEC,
)
from ..utils import disk_free, human_size
from .primitives import chip_tag


class StorageCard(QFrame):
    """A keyboard-accessible radio-style tile (QFrame, so child layouts work)."""

    chosen = pyqtSignal(str)      # resolved base dir
    toggled = pyqtSignal(bool)

    def __init__(self, glyph: str, name: str, default_dir: str,
                 recommended: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("storageCard")
        self.setProperty("checked", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._dir = default_dir
        self._checked = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(10)
        icon_box = QLabel(glyph)
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setFixedSize(32, 32)
        icon_box.setStyleSheet(
            "background: rgba(56,189,248,25); color: #38bdf8;"
            "border-radius: 9px; font-size: 16px; font-weight: 700;"
        )
        top.addWidget(icon_box)

        col = QVBoxLayout()
        col.setSpacing(2)
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        label = QLabel(name)
        label.setStyleSheet("font-size: 13px; font-weight: 700;")
        name_row.addWidget(label)
        if recommended:
            name_row.addWidget(chip_tag("Recommended", "sky"))
        name_row.addStretch(1)
        col.addLayout(name_row)
        self._free = QLabel("checking…")
        self._free.setStyleSheet(f"color: {T_SEC}; font-size: 10px;")
        col.addWidget(self._free)
        top.addLayout(col, 1)

        self._indicator = QLabel("")
        self._indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._indicator.setFixedSize(20, 20)
        top.addWidget(self._indicator, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)

        self._path = QLabel(self._display_path(default_dir))
        self._path.setStyleSheet(
            f"color: {T_MUTED}; font-size: 9px; font-family: 'Fira Code';")
        self._path.setToolTip(default_dir)
        lay.addWidget(self._path)

        self.toggled.connect(self._on_toggle)
        self._sync_indicator()

    # ---- public API (kept compatible with settings + wizard) --------------
    def refresh_free(self) -> None:
        free = disk_free(self._dir)
        self._free.setText(f"{human_size(free)} free" if free is not None else "unavailable")

    def set_dir(self, path: str) -> None:
        self._dir = path
        self._path.setText(self._display_path(path))
        self._path.setToolTip(path)
        self.refresh_free()

    def dir(self) -> str:
        return self._dir

    def setChecked(self, checked: bool) -> None:
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        self.setProperty("checked", checked)
        self._sync_indicator()
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.toggled.emit(checked)

    def isChecked(self) -> bool:
        return self._checked

    # ---- painting helpers -------------------------------------------------
    @staticmethod
    def _display_path(path: str) -> str:
        return (path or "").replace(os.path.expanduser("~"), "~")

    def _sync_indicator(self) -> None:
        if self._checked:
            self._indicator.setText("✓")
            self._indicator.setStyleSheet(
                f"background: {T_PRIMARY}; color: {T_ON_PRIMARY};"
                "border-radius: 10px; font-size: 11px; font-weight: 900;"
            )
        else:
            self._indicator.setText("")
            self._indicator.setStyleSheet(
                f"background: {T_RAIL_DEEP}; border: 1px solid {T_LINE};"
                "border-radius: 10px;"
            )

    # ---- input ------------------------------------------------------------
    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            # Radio semantics: clicking the selected tile keeps it selected.
            if not self._checked:
                self.setChecked(True)
        super().mousePressEvent(ev)

    def keyPressEvent(self, ev: QKeyEvent) -> None:
        if ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self._checked:
                self.setChecked(True)
            ev.accept()
            return
        super().keyPressEvent(ev)

    def _on_toggle(self, checked: bool) -> None:
        if checked:
            self.chosen.emit(self._dir)
