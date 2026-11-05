"""Friendly empty state with an optional call to action."""
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .primitives import btn


class EmptyState(QWidget):
    action_requested = pyqtSignal()

    def __init__(self, glyph: str, title: str, body: str = "",
                 action: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 24, 16, 24)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cap = QLabel(glyph)
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setStyleSheet(
            "background: rgba(56,189,248,25); color: #38bdf8;"
            "border: 1px solid rgba(56,189,248,80); border-radius: 24px;"
            "font-size: 20px; font-weight: 700;"
        )
        cap.setFixedSize(48, 48)
        lay.addWidget(cap, 0, Qt.AlignmentFlag.AlignHCenter)

        heading = QLabel(title)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        lay.addWidget(heading)

        if body:
            sub = QLabel(body)
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setWordWrap(True)
            sub.setMaximumWidth(420)
            sub.setStyleSheet("font-size: 12px; color: #94a3b8;")
            lay.addWidget(sub, 0, Qt.AlignmentFlag.AlignHCenter)

        if action:
            button = btn(action, "primary", small=True)
            button.clicked.connect(self.action_requested.emit)
            lay.addSpacing(6)
            lay.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
