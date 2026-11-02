"""250px navigation rail with the database status footer."""
from typing import Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

import db
from ..theme import (
    T_EMERALD2, T_MUTED, T_ON_PRIMARY, T_PRIMARY, T_ROSE,
)
from .primitives import hline


NAV_ITEMS = [
    ("home", "⌂", "Home", "Hero spotlight, spotlight rows and the poster catalog."),
    ("library", "▤", "Library", "Compact list of every donghua in the database."),
    ("downloads", "⇩", "Downloads", "Network pipeline telemetry and queue control."),
    ("add", "✚", "Add Donghua", "Register a series and its episode URLs."),
    ("settings", "⚙", "Settings", "Storage, quality, network and database preferences."),
]


class Sidebar(QWidget):
    """250px navigation rail: surface #0f172a, nav buttons, DB status footer."""

    navigate = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("rail")
        self.setFixedWidth(250)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 24, 16, 16)
        outer.setSpacing(8)

        # ---- logo block
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel("▶")
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"background: {T_PRIMARY}; color: {T_ON_PRIMARY}; border-radius: 12px;"
            "font-size: 18px; font-weight: 900;"
        )
        brand.addWidget(logo)
        btxt = QVBoxLayout()
        btxt.setSpacing(0)
        btxt.addWidget(QLabel("Donghua Stream"))
        sub = QLabel("Desktop Hub")
        sub.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
        self._ver_sub = sub
        btxt.addWidget(self._ver_sub)
        bcol = QWidget()
        bcol.setLayout(btxt)
        brand.addWidget(bcol)
        brand.addStretch(1)
        outer.addLayout(brand)
        outer.addSpacing(18)

        caps = QLabel("NAVIGATION")
        caps.setStyleSheet(f"color: {T_MUTED}; font-size: 10px; font-weight: 800; letter-spacing: 1.5px;")
        outer.addWidget(caps)
        outer.addSpacing(2)

        self._buttons: Dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for i, (key, glyph, name, tip) in enumerate(NAV_ITEMS):
            b = QPushButton(f"{glyph}   {name}")
            b.setObjectName("navBtn")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setMinimumHeight(40)
            b.setChecked(i == 0)
            self._group.addButton(b, i)
            b.clicked.connect(lambda _=False, k=key: self.navigate.emit(k))
            self._buttons[key] = b
            outer.addWidget(b)

        outer.addStretch(1)

        # ---- DB footer (Stitch: "DB: Connected | v16.3 | donghua_db @ localhost")
        outer.addWidget(hline())
        footer = QWidget()
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(2, 8, 2, 0)
        fl.setSpacing(3)
        self.db_status = QLabel("DB: Connected")
        self.db_status.setStyleSheet(f"color: {T_EMERALD2}; font-size: 11px; font-weight: 700;")
        fl.addWidget(self.db_status)
        self.db_host = QLabel(self._db_host_text())
        self.db_host.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
        fl.addWidget(self.db_host)
        self._engine_lbl = QLabel("")
        self._engine_lbl.setStyleSheet(f"color: {T_MUTED}; font-size: 10px;")
        fl.addWidget(self._engine_lbl)
        outer.addWidget(footer)

    @staticmethod
    def _db_host_text() -> str:
        cfg = getattr(db, "DB_CONFIG", {})
        return f"donghua_db @ {cfg.get('host', 'localhost')}"

    def set_db_ok(self, ok: bool) -> None:
        self.db_status.setText("DB: Connected" if ok else "DB: Offline")
        self.db_status.setStyleSheet(
            f"color: {T_EMERALD2 if ok else T_ROSE}; font-size: 11px; font-weight: 700;"
        )

    def set_engine_version(self, version: str) -> None:
        self._ver_sub.setText(f"Desktop Hub  ·  yt-dlp {version}")
        self._engine_lbl.setText(f"Engine: yt-dlp {version}")

    def set_active(self, key: str) -> None:
        btn_ = self._buttons.get(key)
        if btn_:
            btn_.setChecked(True)

    def default_key(self) -> str:
        return "home"

