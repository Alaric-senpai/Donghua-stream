"""Cinematic hero spotlight with poster backdrop and gradient scrims."""
import os
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import T_BORDER, T_CARD, T_SEC
from .primitives import btn, chip_tag


class HeroSpotlight(QFrame):
    download_all = pyqtSignal(int)
    verify_disk = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("heroChrome")
        self._series: Dict[str, Any] = {}
        self._pix: Optional[QPixmap] = None
        self._vid = ""
        self.setFixedHeight(300)
        self.setMinimumHeight(300)

        self._inner = QLabel(self)
        self._inner.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        box = QWidget(self)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(36, 28, 36, 26)
        bl.setSpacing(10)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.chip_eps = chip_tag("0 EPS", "sky")
        self.chip_dir = chip_tag("", "default")
        self.chip_status = chip_tag("", "emerald")
        chips.addWidget(self.chip_eps)
        chips.addWidget(self.chip_dir)
        chips.addWidget(self.chip_status)
        chips.addStretch(1)
        bl.addLayout(chips)

        self.title = QLabel("No donghua yet")
        self.title.setStyleSheet("font-size: 30px; font-weight: 800; color: #f8fafc;")
        bl.addWidget(self.title)

        self.desc = QLabel("Register your first series from the Add Donghua wizard to see it spotlighted here.")
        self.desc.setStyleSheet(f"color: {T_SEC}; font-size: 13px;")
        self.desc.setMaximumWidth(560)
        self.desc.setWordWrap(True)
        bl.addWidget(self.desc)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.cta = btn("▶  Download Next Pending", "primary", "Queue every pending episode of this series")
        self.cta.clicked.connect(lambda: self.download_all.emit(self.series_id))
        self.verify = btn("⚡  Verify / Scan Disk", "ghost", "Re-sync this series against its downloaded.txt archive")
        self.verify.clicked.connect(lambda: self.verify_disk.emit(self.series_id))
        row.addWidget(self.cta)
        row.addWidget(self.verify)
        row.addStretch(1)
        bl.addLayout(row)

        box.setGeometry(0, 0, 900, 300)

    series_id: int = 0

    def set_series(self, series: Optional[Dict[str, Any]], poster: str,
                   thumbs: ThumbnailStore) -> None:
        self._series = series or {}
        self.series_id = int(self._series.get("id", 0) or 0)
        self._vid = poster or ""
        self._pix = thumbs.get(self._vid) if self._vid else None
        tot = int(self._series.get("total_episodes", 0) or 0)
        done = int(self._series.get("downloaded_episodes", 0) or 0)
        pend = int(self._series.get("pending_episodes", 0) or 0)
        path = self._series.get("save_dir") or ""
        self._inner.setHidden(not self._series)
        if self._series:
            self.title.setText(self._series.get("name") or "")
            self.desc.setText(self._series.get("description")
                              or "No description recorded for this series yet.")
            self.chip_eps.setText(f"{tot} EPS")
            self.chip_dir.setText(path.replace(os.path.expanduser("~"), "~"))
            if tot and done >= tot:
                self.chip_status.setText("COMPLETE")
            elif done:
                self.chip_status.setText(f"{done} of {tot} DOWNLOADED")
            else:
                self.chip_status.setText("NOT STARTED")
            self.cta.setEnabled(pend > 0)
            self.cta.setText(f"▶  Download Next Pending ({pend})")
        self.resizeEvent(None)  # type: ignore[arg-type]
        self.update()

    def _reposition(self) -> None:
        w = self.width()
        self._inner.setGeometry(56, 96, min(620, w - 120), 200)

    def resizeEvent(self, ev) -> None:
        if ev is not None:
            super().resizeEvent(ev)
        self._reposition()
        for c in self.findChildren(QWidget):
            pass
        box = self.findChildren(QWidget)
        if box:
            box[0].setGeometry(0, 0, self.width(), self.height())

    def paintEvent(self, ev) -> None:
        from PyQt6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T_CARD))
        p.drawRoundedRect(QRectF(0, 0, w, h), 24, 24)
        if self._pix and not self._pix.isNull():
            img = self._pix.toImage()
            cw, ch = img.width(), img.height()
            scale = max(w / cw, h / ch, 1e-6)
            small = img.scaled(int(cw * scale), int(ch * scale),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            p.save()
            p.setClipRect(QRectF(12, 12, w - 24, h - 24))
            p.setOpacity(0.30)
            p.drawImage((w - small.width()) // 2, 12 + (h - 24 - small.height()) // 3, small)
            p.restore()
        # cinematic scrims
        left = QLinearGradient(0, 0, w * 0.75, 0)
        left.setColorAt(0, QColor(2, 6, 23, 245))
        left.setColorAt(1, QColor(2, 6, 23, 0))
        p.fillRect(QRectF(0, 0, w * 0.75, h), left)
        bottom = QLinearGradient(0, h - 140, 0, h)
        bottom.setColorAt(0, QColor(2, 6, 23, 0))
        bottom.setColorAt(1, QColor(2, 6, 23, 235))
        p.fillRect(QRectF(0, h - 140, w, 140), bottom)
        p.setPen(QColor(T_BORDER))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 24, 24)

