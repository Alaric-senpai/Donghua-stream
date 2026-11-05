"""Navigation rail: brand, page links, primary add action and DB footer."""
from typing import Dict, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
    QWidget,
)

import db
from ..icons import icon
from ..theme import (
    T_EMERALD2, T_MUTED, T_ON_PRIMARY, T_PRIMARY, T_ROSE2, T_SEC,
)
from .primitives import hline

NAV_PAGES = [
    ("home", "home", "Home", "Hero spotlight, spotlight rows and the poster catalog."),
    ("explore", "compass", "Explore", "Discover donghua on YouTube with Data API v3."),
    ("library", "library", "Library", "Every donghua in the database."),
    ("downloads", "download", "Downloads", "Network pipeline telemetry and queue control."),
    ("settings", "settings", "Settings", "Storage, quality, network and database preferences."),
]


class Sidebar(QWidget):
    """250px rail: deep slate surface, tinted active nav, live DB status."""

    navigate = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("rail")
        self.setFixedWidth(250)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 22, 16, 14)
        outer.setSpacing(6)

        # ---- brand
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setFixedSize(38, 38)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"background: {T_PRIMARY}; border-radius: 11px;")
        logo.setPixmap(icon("play", T_ON_PRIMARY, 16).pixmap(16, 16))
        brand.addWidget(logo)
        btxt = QVBoxLayout()
        btxt.setSpacing(0)
        name = QLabel("Donghua Stream")
        name.setStyleSheet(
            "font-family: 'Montserrat'; font-size: 14px; font-weight: 700;"
        )
        btxt.addWidget(name)
        sub = QLabel("DESKTOP HUB")
        sub.setStyleSheet(
            f"color: {T_MUTED}; font-family: 'Fira Code'; font-size: 9px;"
        )
        self._ver_sub = sub
        btxt.addWidget(sub)
        bcol = QWidget()
        bcol.setLayout(btxt)
        brand.addWidget(bcol)
        brand.addStretch(1)
        outer.addLayout(brand)
        outer.addSpacing(18)

        caps = QLabel("BROWSE")
        caps.setStyleSheet(
            f"color: {T_MUTED}; font-family: 'Fira Code'; font-size: 9px; font-weight: 600;"
        )
        outer.addWidget(caps)
        outer.addSpacing(2)

        self._buttons: Dict[str, QPushButton] = {}
        self._icon_names: Dict[str, str] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for i, (key, icon_name, label, tip) in enumerate(NAV_PAGES):
            b = QPushButton(f"   {label}")
            b.setObjectName("navBtn")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setMinimumHeight(38)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIconSize(QSize(18, 18))
            b.setIcon(icon(icon_name, T_PRIMARY if i == 0 else T_SEC, 18))
            b.setChecked(i == 0)
            self._group.addButton(b, i)
            b.clicked.connect(lambda _=False, k=key: self.navigate.emit(k))
            self._buttons[key] = b
            self._icon_names[key] = icon_name
            outer.addWidget(b)

        outer.addSpacing(6)
        add = QPushButton("   Add Donghua")
        add.setObjectName("navAction")
        add.setMinimumHeight(40)
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.setIconSize(QSize(18, 18))
        add.setIcon(icon("plus", T_PRIMARY, 18))
        add.setToolTip("Register a series and its episode URLs")
        add.clicked.connect(lambda: self.navigate.emit("add"))
        self._buttons["add"] = add
        outer.addWidget(add)
        outer.addStretch(1)

        # ---- DB footer
        outer.addWidget(hline())
        panel = QFrame()
        panel.setObjectName("panel")
        fl = QVBoxLayout(panel)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(3)
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {T_EMERALD2}; font-size: 8px;")
        status_row.addWidget(self._dot)
        self.db_status = QLabel("Connected")
        self.db_status.setStyleSheet(
            f"color: {T_EMERALD2}; font-size: 11px; font-weight: 700;")
        status_row.addWidget(self.db_status)
        status_row.addStretch(1)
        fl.addLayout(status_row)
        self.db_host = QLabel(self._db_host_text())
        self.db_host.setStyleSheet(
            f"color: {T_MUTED}; font-family: 'Fira Code'; font-size: 9px;")
        fl.addWidget(self.db_host)
        self._engine_lbl = QLabel("")
        self._engine_lbl.setStyleSheet(
            f"color: {T_MUTED}; font-family: 'Fira Code'; font-size: 9px;")
        fl.addWidget(self._engine_lbl)
        outer.addWidget(panel)

    @staticmethod
    def _db_host_text() -> str:
        cfg = db.get_db_config()
        return f"{cfg.get('dbname', 'donghua_db')} @ {cfg.get('host', 'localhost')}"

    def refresh_db_host(self) -> None:
        self.db_host.setText(self._db_host_text())

    def set_db_ok(self, ok: bool) -> None:
        tone = T_EMERALD2 if ok else T_ROSE2
        self._dot.setStyleSheet(f"color: {tone}; font-size: 8px;")
        self.db_status.setText("Connected" if ok else "Offline")
        self.db_status.setStyleSheet(
            f"color: {tone}; font-size: 11px; font-weight: 700;")

    def set_engine_version(self, version: str) -> None:
        self._ver_sub.setText("DESKTOP HUB")
        self._engine_lbl.setText(f"engine  yt-dlp {version}")

    def set_active(self, key: str) -> None:
        for k, b in self._buttons.items():
            if k == "add":
                continue
            active = k == key
            b.setChecked(active)
            b.setIcon(icon(self._icon_names[k], T_PRIMARY if active else T_SEC, 18))

    def default_key(self) -> str:
        return "home"
