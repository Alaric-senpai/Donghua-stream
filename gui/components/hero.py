"""Cinematic spotlight hero with artwork, scrims and direct actions."""
import os
from typing import Any, Dict, Optional

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QLinearGradient, QPainter, QPainterPath, QPixmap, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from ..icons import icon
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import (
    T_AMBER2, T_AMBER_LINE, T_AMBER_SOFT, T_CARD, T_EMERALD2,
    T_EMERALD_LINE, T_EMERALD_SOFT, T_LINE_STRONG, T_ON_PRIMARY,
    T_PRIMARY, T_PRIMARY_LINE, T_PRIMARY_SOFT, T_SEC,
)
from .primitives import btn, chip_tag


class HeroSpotlight(QFrame):
    download_all = pyqtSignal(int)
    verify_disk = pyqtSignal(int)
    open_requested = pyqtSignal(int)
    add_requested = pyqtSignal()

    HEIGHT = 272

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("heroChrome")
        self._series: Dict[str, Any] = {}
        self._pix: Optional[QPixmap] = None
        self._vid = ""
        self.series_id = 0
        self.setFixedHeight(self.HEIGHT)

        body = QVBoxLayout(self)
        body.setContentsMargins(32, 22, 32, 22)
        body.setSpacing(8)

        chips = QHBoxLayout()
        chips.setSpacing(7)
        self.chip_kicker = chip_tag("SPOTLIGHT", "primary")
        self.chip_eps = chip_tag("0 EPS", "sky")
        self.chip_status = chip_tag("", "emerald")
        chips.addWidget(self.chip_kicker)
        chips.addWidget(self.chip_eps)
        chips.addWidget(self.chip_status)
        chips.addStretch(1)
        body.addLayout(chips)

        self.title = QLabel("Your library is empty")
        self.title.setObjectName("heroTitle")
        body.addWidget(self.title)

        self.desc = QLabel(
            "Register your first donghua from the Add Donghua wizard to see it spotlighted here.")
        self.desc.setObjectName("heroBody")
        self.desc.setWordWrap(True)
        self.desc.setMaximumWidth(620)
        self.desc.setMaximumHeight(38)
        body.addWidget(self.desc)

        self.meta = QLabel("")
        self.meta.setObjectName("heroMeta")
        self.meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        body.addWidget(self.meta)
        body.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.cta = btn("Download Next Pending", "primary",
                       "Queue every pending episode of this series")
        self.cta.setIcon(icon("play", T_ON_PRIMARY, 13))
        self.cta.setIconSize(QSize(13, 13))
        self.cta.clicked.connect(lambda: self.download_all.emit(self.series_id))
        self.verify = btn("Verify Disk", "ghost",
                          "Re-sync this series against its downloaded.txt archive")
        self.verify.setIcon(icon("rotate", T_SEC, 13))
        self.verify.setIconSize(QSize(13, 13))
        self.verify.clicked.connect(lambda: self.verify_disk.emit(self.series_id))
        self.view = btn("View Series", "ghost", "Open the full series page")
        self.view.setIcon(icon("chevron-right", T_SEC, 13))
        self.view.setIconSize(QSize(13, 13))
        self.view.clicked.connect(lambda: self.open_requested.emit(self.series_id))
        self.add_btn = btn("＋  Add your first Donghua", "primary",
                           "Open the registration wizard")
        self.add_btn.clicked.connect(self.add_requested.emit)
        actions.addWidget(self.cta)
        actions.addWidget(self.verify)
        actions.addWidget(self.view)
        actions.addWidget(self.add_btn)
        actions.addStretch(1)
        body.addLayout(actions)

        self._show_empty()

    # ---- state ------------------------------------------------------------
    def _show_empty(self) -> None:
        self.chip_eps.hide()
        self.chip_status.hide()
        self.meta.hide()
        self.verify.hide()
        self.view.hide()
        self.cta.hide()
        self.add_btn.show()

    def _set_status_tone(self, tone: str) -> None:
        tones = {
            "emerald": (T_EMERALD_SOFT, T_EMERALD_LINE, T_EMERALD2),
            "amber": (T_AMBER_SOFT, T_AMBER_LINE, T_AMBER2),
            "sky": (T_PRIMARY_SOFT, T_PRIMARY_LINE, T_PRIMARY),
        }
        bg, line, fg = tones.get(tone, tones["sky"])
        self.chip_status.setStyleSheet(
            f"background: {bg}; border: 1px solid {line}; border-radius: 8px;"
            f"color: {fg}; font-size: 10px; font-weight: 700; padding: 2px 8px;"
        )

    def set_series(self, series: Optional[Dict[str, Any]], poster: str,
                   thumbs: ThumbnailStore) -> None:
        self._series = series or {}
        self.series_id = int(self._series.get("id", 0) or 0)
        self._vid = poster or ""
        self._pix = thumbs.get(self._vid) if self._vid else None
        if not self._series:
            self.title.setText("Your library is empty")
            self.desc.setText(
                "Register your first donghua from the Add Donghua wizard to see it spotlighted here.")
            self._show_empty()
            self.update()
            return

        tot = int(self._series.get("total_episodes", 0) or 0)
        done = int(self._series.get("downloaded_episodes", 0) or 0)
        pend = int(self._series.get("pending_episodes", 0) or 0)
        path = (self._series.get("save_dir") or "").replace(os.path.expanduser("~"), "~")
        self.title.setText(self._series.get("name") or "Untitled")
        desc = (self._series.get("description") or "").strip()
        self.desc.setText(desc or "No synopsis recorded yet — open the series to manage its episodes.")
        self.chip_eps.setText(f"{tot} EPISODES")
        self.meta.setText(f"{done} READY  ·  {pend} PENDING  ·  {path}")
        self.meta.setToolTip(path)
        if tot and done >= tot:
            self.chip_status.setText("COMPLETE")
            self._set_status_tone("emerald")
        elif done:
            self.chip_status.setText(f"{done} OF {tot} DOWNLOADED")
            self._set_status_tone("sky")
        else:
            self.chip_status.setText("NOT STARTED")
            self._set_status_tone("amber")

        self.cta.setEnabled(pend > 0)
        self.cta.setText(f"Download Next Pending ({pend})")
        self.chip_eps.show()
        self.chip_status.show()
        self.meta.show()
        self.verify.show()
        self.view.show()
        self.cta.show()
        self.add_btn.hide()
        self.update()

    # ---- paint ------------------------------------------------------------
    def _rounded_path(self) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 20, 20)
        return path

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        path = self._rounded_path()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T_CARD))
        p.drawPath(path)

        if self._pix and not self._pix.isNull():
            p.save()
            p.setClipPath(path)
            scaled = self._pix.scaled(
                w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            p.setOpacity(0.42)
            p.drawPixmap(int((w - scaled.width()) / 2),
                         int((h - scaled.height()) / 2), scaled)
            p.restore()

        # ambient sky glow in the top-right corner
        p.save()
        p.setClipPath(path)
        glow = QRadialGradient(w * 0.86, 0, max(w * 0.55, 1))
        glow.setColorAt(0.0, QColor(56, 189, 248, 58))
        glow.setColorAt(1.0, QColor(56, 189, 248, 0))
        p.fillRect(QRectF(0, 0, w, h), glow)

        left = QLinearGradient(0, 0, w * 0.78, 0)
        left.setColorAt(0.0, QColor(2, 6, 23, 248))
        left.setColorAt(0.62, QColor(2, 6, 23, 190))
        left.setColorAt(1.0, QColor(2, 6, 23, 0))
        p.fillRect(QRectF(0, 0, w, h), left)
        bottom = QLinearGradient(0, h - 110, 0, h)
        bottom.setColorAt(0.0, QColor(2, 6, 23, 0))
        bottom.setColorAt(1.0, QColor(2, 6, 23, 220))
        p.fillRect(QRectF(0, h - 110, w, 110), bottom)
        p.restore()

        p.setPen(QColor(T_LINE_STRONG))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()
