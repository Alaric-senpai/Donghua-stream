"""Episode registry row with per-row registry actions."""
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ..theme import T_MUTED
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
        self.setObjectName("card")
        self.setFixedHeight(54)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(10)

        num = ep.get("episode_number") or index + 1
        numlab = QLabel(f"#{num:>3}")
        numlab.setStyleSheet(f"color: {T_MUTED}; font-family: monospace; font-size: 12px;")
        numlab.setFixedWidth(48)
        lay.addWidget(numlab)

        title = QLabel(ep.get("title") or ep.get("url") or "")
        title.setStyleSheet("font-weight: 700; font-size: 13px;")
        title.setToolTip(ep.get("url") or "")
        lay.addWidget(title, 1)

        status = ep.get("status") or "pending"
        tone = {"downloaded": "emerald", "failed": "rose", "queued": "sky", "pending": "default"}.get(status, "default")
        lay.addWidget(chip_tag({"downloaded": "✔ READY", "failed": "✖ FAILED",
                                "queued": "QUEUED", "pending": "PENDING"}.get(status, status.upper()), tone))

        dl = icon_btn("⤓", "Download this episode now")
        dl.clicked.connect(lambda: self.download.emit(self.ep))
        cp = icon_btn("⧉", "Copy URL")
        cp.clicked.connect(lambda: self.copy_url.emit(self.ep.get("url", "")))
        ed = icon_btn("✎", "Edit title / episode number")
        ed.clicked.connect(lambda: self.edit_ep.emit(self.ep))
        de = icon_btn("␥", "Delete from registry")
        de.clicked.connect(lambda: self.del_ep.emit(self.ep))
        for b in (dl, cp, ed, de):
            lay.addWidget(b)
        if status == "failed":
            ret = icon_btn("⟳", "Retry failed download")
            ret.clicked.connect(lambda: self.retry.emit(self.ep))
            lay.addWidget(ret)

