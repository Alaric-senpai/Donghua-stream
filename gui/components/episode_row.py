"""Episode registry row: number, identity, status and per-row actions."""
from typing import Any, Dict, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from ..icons import icon
from ..theme import T_AMBER2, T_MUTED, T_PRIMARY, T_ROSE2, T_SEC, T_TEXT
from .primitives import chip_tag, icon_btn


class EpisodeRow(QFrame):
    download = pyqtSignal(dict)
    copy_url = pyqtSignal(str)
    edit_ep = pyqtSignal(dict)
    del_ep = pyqtSignal(dict)
    retry = pyqtSignal(dict)

    def __init__(self, ep: Dict[str, Any], index: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ep = ep
        self.setObjectName("episodeRow")
        self.setFixedHeight(56)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        num = ep.get("episode_number") or index + 1
        numlab = QLabel(f"#{int(num):03d}" if isinstance(num, int) else f"#{num}")
        numlab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        numlab.setFixedSize(48, 26)
        numlab.setStyleSheet(
            f"color: {T_MUTED}; background: rgba(51,65,85,65);"
            "border-radius: 6px; font-family: 'Fira Code'; font-size: 10px;"
        )
        lay.addWidget(numlab)

        title = QLabel(ep.get("title") or ep.get("url") or "")
        title.setStyleSheet(f"color: {T_TEXT}; font-weight: 600; font-size: 13px;")
        title.setToolTip(ep.get("url") or "")
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(title, 1)

        status = ep.get("status") or "pending"
        tone = {"downloaded": "emerald", "failed": "rose", "queued": "sky",
                "pending": "default"}.get(status, "default")
        label = {"downloaded": "✔ READY", "failed": "✖ FAILED",
                 "queued": "QUEUED", "pending": "PENDING"}.get(status, status.upper())
        lay.addWidget(chip_tag(label, tone))

        dl = icon_btn("", "Download this episode now")
        dl.setFixedSize(28, 28)
        dl.setIcon(icon("download", T_PRIMARY, 15))
        dl.setIconSize(QSize(15, 15))
        dl.clicked.connect(lambda: self.download.emit(self.ep))
        cp = icon_btn("", "Copy URL")
        cp.setFixedSize(28, 28)
        cp.setIcon(icon("copy", T_SEC, 15))
        cp.setIconSize(QSize(15, 15))
        cp.clicked.connect(lambda: self.copy_url.emit(self.ep.get("url", "")))
        ed = icon_btn("", "Edit title / episode number")
        ed.setFixedSize(28, 28)
        ed.setIcon(icon("edit", T_SEC, 15))
        ed.setIconSize(QSize(15, 15))
        ed.clicked.connect(lambda: self.edit_ep.emit(self.ep))
        de = icon_btn("", "Delete from registry", danger=True)
        de.setFixedSize(28, 28)
        de.setIcon(icon("trash", T_ROSE2, 15))
        de.setIconSize(QSize(15, 15))
        de.clicked.connect(lambda: self.del_ep.emit(self.ep))
        for b in (dl, cp, ed, de):
            lay.addWidget(b)
        if status == "failed":
            ret = icon_btn("", "Retry failed download")
            ret.setFixedSize(28, 28)
            ret.setIcon(icon("rotate", T_AMBER2, 15))
            ret.setIconSize(QSize(15, 15))
            ret.clicked.connect(lambda: self.retry.emit(self.ep))
            lay.addWidget(ret)
