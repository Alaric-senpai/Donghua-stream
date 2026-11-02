"""Bulk-paste quick import drawer (`URL   # Episode title`)."""
import re
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

from ..components.primitives import btn, chip_tag, label_caps, mk_label
from ..theme import app_stylesheet
from ..utils import parse_bulk_urls


class AddUrlsDialog(QDialog):
    """Bulk-paste drawer: `URL   # Episode title`, start index, auto-download."""

    def __init__(self, series: Dict[str, Any], next_ep: int,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Episodes — {series.get('name', '')}")
        self.setMinimumSize(660, 560)
        self.setStyleSheet(app_stylesheet())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(12)

        lay.addWidget(mk_label("Quick Import Drawer", "titleMd"))
        lay.addWidget(mk_label("Paste one or many video URLs. Optional format: URL   # Episode title",
                               "body", "muted"))

        self.urls = QTextEdit()
        self.urls.setPlaceholderText(
            "https://youtu.be/XXXXXXXXX  # Episode 12 - The Divine Trail\nhttps://www.youtube.com/watch?v=YYYYYYYYY")
        self.urls.setMinimumHeight(180)
        self.urls.textChanged.connect(self._update_badge)
        lay.addWidget(self.urls)

        badge_row = QHBoxLayout()
        self.badge = chip_tag("0 valid URLs  ·  0 duplicates", "default")
        badge_row.addWidget(self.badge)
        badge_row.addStretch(1)
        lay.addLayout(badge_row)

        opts = QGridLayout()
        opts.setHorizontalSpacing(18)
        opts.setVerticalSpacing(8)
        opts.addWidget(label_caps("Start index / episode number"), 0, 0)
        self.start_at = QSpinBox()
        self.start_at.setRange(1, 99999)
        self.start_at.setValue(max(1, next_ep))
        self.start_at.setFixedWidth(120)
        opts.addWidget(self.start_at, 1, 0)
        opts.addWidget(label_caps("Numbering"), 0, 1)
        num_box = QComboBox()
        num_box.addItems(["Sequential (n, n+1, …)", "From URL titles", "No numbering"])
        num_box.setFixedWidth(210)
        opts.addWidget(num_box, 1, 1)
        opts.setColumnStretch(2, 1)
        lay.addLayout(opts)

        self.auto_dl = QCheckBox("Start downloading these episodes immediately after saving")
        self.auto_dl.setChecked(True)
        lay.addWidget(self.auto_dl)

        lay.addStretch(1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = btn("Cancel", "ghost")
        cancel.clicked.connect(self.reject)
        save = btn("💾  Save to Library Only", "ghost", "Register URLs without downloading")
        save.clicked.connect(lambda: self.done(1))
        dl = btn("⤓  Save & Download Immediately", "primary", "Register and queue every URL")
        dl.clicked.connect(lambda: self.done(2))
        btns.addWidget(cancel)
        btns.addWidget(save)
        btns.addWidget(dl)
        lay.addLayout(btns)

        self._mode = None
        self._numbering = num_box

    def _update_badge(self) -> None:
        items = parse_bulk_urls(self.urls.toPlainText())
        dups = sum(1 for i in items if i["dup"])
        self.badge.setText(f"{len(items)} valid URLs  ·  {dups} duplicated  ·  {len(items) - dups} new")
        self.badge.setStyleSheet(
            f"background: {'#10b98122' if items else '#f43f5e22'};"
            f"border: 1px solid {'#10b98166' if items else '#f43f5e66'};"
            "border-radius: 999px; color: #4edea3; font-size: 11px; font-weight: 700;"
            "padding: 2px 10px;")

    def result_entries(self):
        return self._mode

    # run helper -----------------------------------------------------------
    def collect(self):
        """Returns (mode, entries, next_index, auto) or None when cancelled."""
        code = self.exec()
        if code == 0:
            return None
        mode = "download" if code == 2 or self.auto_dl.isChecked() else "save"
        if code == 1:
            mode = "save"
        entries = parse_bulk_urls(self.urls.toPlainText())
        if self._numbering.currentIndex() == 0:
            n = self.start_at.value()
            for e in entries:
                e["num"] = n
                n += 1
        elif self._numbering.currentIndex() == 1:
            for e in entries:
                m = re.search(r"[Ee]p(?:isode)?\s*-?\s*(\d+)", e["title"])
                e["num"] = int(m.group(1)) if m else None
        else:
            for e in entries:
                e["num"] = None
        return mode, entries, self.start_at.value(), self.auto_dl.isChecked()

