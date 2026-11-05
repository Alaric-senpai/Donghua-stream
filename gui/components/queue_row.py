"""Priority-queue row with move-up / move-down / remove controls."""
import os
from typing import Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from ..icons import icon
from ..infrastructure.download_queue import DownloadTask
from ..theme import T_MUTED, T_PRIMARY, T_ROSE2, T_SEC, T_TEXT
from .primitives import chip_tag, icon_btn


class QueueRow(QFrame):
    move_up = pyqtSignal(object)
    move_down = pyqtSignal(object)
    remove = pyqtSignal(object)
    paused = pyqtSignal()
    resumed = pyqtSignal()

    def __init__(self, task: DownloadTask, index: int,
                 active: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.task = task
        self.setObjectName("queueRow")
        self.setProperty("active", active)
        self.setFixedHeight(60)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(10)

        pos = QLabel(f"{index + 1:02d}")
        pos.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pos.setFixedSize(30, 30)
        pos.setStyleSheet(
            f"color: {T_PRIMARY if active else T_MUTED};"
            "background: rgba(51,65,85,65); border-radius: 7px;"
            "font-family: 'Fira Code'; font-size: 11px; font-weight: 700;"
        )
        lay.addWidget(pos)

        info = QWidget()
        il = QHBoxLayout(info)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(8)
        name = QLabel(task.series_name)
        name.setStyleSheet(f"color: {T_TEXT}; font-weight: 700; font-size: 13px;")
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        il.addWidget(name)
        il.addWidget(chip_tag(task.label if task.label else "series", "default"))
        il.addWidget(chip_tag(f"{len(task.urls)} videos", "default"))
        lay.addWidget(info, 1)

        dir_lab = QLabel(task.save_dir.replace(os.path.expanduser("~"), "~"))
        dir_lab.setStyleSheet(
            f"color: {T_SEC}; font-family: 'Fira Code'; font-size: 9px;")
        dir_lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        dir_lab.setMaximumWidth(260)
        lay.addWidget(dir_lab, 1)

        if active:
            lay.addWidget(chip_tag("● RUNNING", "sky"))

        up = icon_btn("", "Move up (higher priority)")
        down = icon_btn("", "Move down")
        rm = icon_btn("", "Remove from queue", danger=True)
        up.setIcon(icon("arrow-up", T_SEC, 14))
        down.setIcon(icon("arrow-down", T_SEC, 14))
        rm.setIcon(icon("trash", T_ROSE2, 14))
        for b in (up, down, rm):
            b.setFixedSize(28, 28)
            b.setIconSize(QSize(14, 14))
        up.clicked.connect(lambda: self.move_up.emit(task))
        down.clicked.connect(lambda: self.move_down.emit(task))
        rm.clicked.connect(lambda: self.remove.emit(task))
        for b in (up, down, rm):
            lay.addWidget(b)
