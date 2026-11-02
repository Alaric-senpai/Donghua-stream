"""Single-URL quick-add dialog opened from the header search."""
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget,
)

from ..components.primitives import btn, label_caps, mk_label
from ..theme import app_stylesheet
from ..utils import QUALITY_OPTIONS, URL_RE, quality_label


class QuickUrlDialog(QDialog):
    def __init__(self, series_list: List[Dict[str, Any]], settings: Dict[str, str],
                 url: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Quick Add URL")
        self.setStyleSheet(app_stylesheet())
        self.setMinimumSize(540, 460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(10)
        lay.addWidget(mk_label("Add a single episode", "titleMd"))
        lay.addWidget(mk_label("Pick the series it belongs to (or start a new one from the wizard).",
                               "body", "muted"))

        lay.addWidget(label_caps("Video URL"))
        self.url = QLineEdit(url)
        self.url.setPlaceholderText("https://youtu.be/…")
        lay.addWidget(self.url)

        lay.addWidget(label_caps("Episode title (optional)"))
        self.title = QLineEdit()
        self.title.setPlaceholderText("e.g. Episode 15 — The Blade")
        lay.addWidget(self.title)

        lay.addWidget(label_caps("Series"))
        self.series_box = QComboBox()
        self.series_box.addItem("➕  New series (opens the wizard)…", "__new__")
        for s in series_list:
            self.series_box.addItem(s.get("name", ""), s["id"])
        lay.addWidget(self.series_box)

        qrow = QHBoxLayout()
        qrow.addWidget(label_caps("Quality"))
        self.quality = QComboBox()
        self.quality.setObjectName("chip")
        for val, lab in QUALITY_OPTIONS:
            self.quality.addItem(lab, val)
        self.quality.setCurrentText(quality_label(settings.get("default_quality", "720p")))
        self.quality.setFixedHeight(30)
        qrow.addWidget(self.quality)
        qrow.addStretch(1)
        holder = QWidget()
        holder.setLayout(qrow)
        lay.addWidget(holder)

        self.dl_now = QCheckBox("Download this episode immediately")
        self.dl_now.setChecked(True)
        lay.addWidget(self.dl_now)

        btns = QHBoxLayout()
        btns.addStretch(1)
        c = btn("Cancel", "ghost")
        c.clicked.connect(self.reject)
        s = btn("Save", "primary")
        s.clicked.connect(self.accept)
        btns.addWidget(c)
        btns.addWidget(s)
        lay.addLayout(btns)

    def collect(self):
        if self.exec() != 1 or not URL_RE.search(self.url.text()):
            return None
        return {
            "url": URL_RE.search(self.url.text()).group(0),
            "title": self.title.text().strip(),
            "series": self.series_box.currentData(),
            "series_label": self.series_box.currentText(),
            "quality": self.quality.currentData(),
            "download_now": self.dl_now.isChecked(),
        }

