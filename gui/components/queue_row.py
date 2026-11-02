"""Priority-queue row with move-up / move-down / remove controls."""
import os
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ..infrastructure.download_queue import DownloadTask
from ..theme import T_MUTED
from .primitives import chip_tag, icon_btn


class QueueRow(QFrame):
    move_up = pyqtSignal(object)
    move_down = pyqtSignal(object)
    remove = pyqtSignal(object)
    paused = pyqtSignal()
    resumed = pyqtSignal()

    def __init__(self, task: DownloadTask, index: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.task = task
        self.setObjectName("card")
        self.setFixedHeight(52)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(10)
        pos = QLabel(f"{index + 1:>2}")
        pos.setStyleSheet(f"color: {T_MUTED}; font-family: monospace; font-size: 14px; font-weight: 800;")
        pos.setFixedWidth(28)
        lay.addWidget(pos)
        name = QLabel(task.series_name)
        name.setStyleSheet("font-weight: 800; font-size: 13px;")
        lay.addWidget(name, 1)
        lay.addWidget(chip_tag(task.label if task.label else "series", "default"))
        lay.addWidget(chip_tag(f"{len(task.urls)} videos", "default"))
        dir_lab = QLabel(task.save_dir.replace(os.path.expanduser("~"), "~"))
        dir_lab.setStyleSheet(f"color: {T_MUTED}; font-size: 10px; font-family: monospace;")
        lay.addWidget(dir_lab, 1)
        up = icon_btn("↑", "Move up (higher priority)")
        down = icon_btn("↓", "Move down")
        rm = icon_btn("␥", "Remove from queue")
        up.clicked.connect(lambda: self.move_up.emit(task))
        down.clicked.connect(lambda: self.move_down.emit(task))
        rm.clicked.connect(lambda: self.remove.emit(task))
        for b in (up, down, rm):
            lay.addWidget(b)

