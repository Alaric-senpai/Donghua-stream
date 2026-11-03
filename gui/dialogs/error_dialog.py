"""Copyable error-report dialog shared by downloads, the wizard and crashes."""
from typing import Optional

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout, QWidget,
)

from ..components.primitives import btn, label_caps, mk_label
from ..icons import icon
from ..theme import T_ON_PRIMARY, T_ROSE2, app_stylesheet


class ErrorDialog(QDialog):
    """A readable error report whose full text can be copied in one click."""

    def __init__(self, title: str, summary: str = "", details: str = "",
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(700, 470)
        self.setStyleSheet(app_stylesheet())
        self._details = (details or summary or title).strip()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(12)
        glyph = QLabel("!")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setFixedSize(38, 38)
        glyph.setStyleSheet(
            "background: rgba(244,63,94,28); color: #fb7185;"
            "border: 1px solid rgba(244,63,94,110); border-radius: 19px;"
            "font-size: 22px; font-weight: 900;")
        head.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(mk_label(title, "titleLg"))
        title_col.addWidget(mk_label(
            "Copy these details to paste them into a bug report or chat.",
            "small", "muted"))
        head.addLayout(title_col, 1)
        root.addLayout(head)

        if summary:
            root.addWidget(mk_label(summary, "body", wrap=True))

        root.addWidget(label_caps("Error details"))
        self.details_view = QTextEdit()
        self.details_view.setObjectName("errorDetails")
        self.details_view.setReadOnly(True)
        self.details_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.details_view.setPlainText(self._details)
        self.details_view.setMinimumHeight(200)
        root.addWidget(self.details_view, 1)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        foot.addStretch(1)
        close_btn = btn("Close", "ghost")
        close_btn.clicked.connect(self.accept)
        self.copy_btn = btn("Copy Details", "primary",
                            "Copy the complete error report to the clipboard")
        self.copy_btn.setIcon(icon("copy", T_ON_PRIMARY, 14))
        self.copy_btn.setIconSize(QSize(14, 14))
        self.copy_btn.clicked.connect(self._copy)
        foot.addWidget(close_btn)
        foot.addWidget(self.copy_btn)
        root.addLayout(foot)

        self.details_view.setFocus()

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._details)
        self.copy_btn.setText("Copied")
        QTimer.singleShot(1600, self._reset_copy)

    def _reset_copy(self) -> None:
        try:
            self.copy_btn.setText("Copy Details")
        except RuntimeError:
            pass


def report_error(parent: Optional[QWidget], title: str, summary: str = "",
                 details: str = "") -> int:
    """Show a modal, copyable error report and return the dialog result."""
    return ErrorDialog(title, summary, details, parent).exec()
