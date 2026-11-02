"""Tokens-driven visual primitives shared by every page and dialog."""
from typing import Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QLabel, QProgressBar, QPushButton,
    QVBoxLayout, QWidget,
)

from ..theme import (
    T_AMBER2, T_AMBER_LINE, T_AMBER_SOFT, T_CARD_SOFT, T_EMERALD2,
    T_EMERALD_LINE, T_EMERALD_SOFT, T_LINE, T_MUTED,
    T_ON_PRIMARY, T_PRIMARY, T_PRIMARY_LINE, T_PRIMARY_SOFT, T_ROSE2,
    T_ROSE_LINE, T_ROSE_SOFT, T_SEC,
)


def mk_label(text: str = "", cls: str = "", color_name: str = "",
             wrap: bool = False) -> QLabel:
    """Styled label: cls is one of display/titleXl/titleLg/titleMd/titleSm/body/small."""
    lab = QLabel(text)
    if cls:
        lab.setObjectName(cls)
    if color_name == "muted":
        lab.setStyleSheet(f"color: {T_MUTED};")
    elif color_name == "sec":
        lab.setStyleSheet(f"color: {T_SEC};")
    lab.setWordWrap(wrap)
    return lab


def label_caps(text: str) -> QLabel:
    lab = QLabel(text.upper())
    lab.setObjectName("labelCaps")
    return lab


def eyebrow(text: str) -> QLabel:
    lab = QLabel(text.upper())
    lab.setObjectName("eyebrow")
    return lab


def mono_label(text: str = "") -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("mono")
    return lab


def chip_tag(text: str, tone: str = "default") -> QLabel:
    tones = {
        "default": (T_CARD_SOFT, T_LINE, T_SEC),
        "sky": (T_PRIMARY_SOFT, T_PRIMARY_LINE, T_PRIMARY),
        "emerald": (T_EMERALD_SOFT, T_EMERALD_LINE, T_EMERALD2),
        "amber": (T_AMBER_SOFT, T_AMBER_LINE, T_AMBER2),
        "rose": (T_ROSE_SOFT, T_ROSE_LINE, T_ROSE2),
        "primary": (T_PRIMARY, T_PRIMARY, T_ON_PRIMARY),
    }
    bg, border, fg = tones.get(tone, tones["default"])
    lab = QLabel(text)
    lab.setStyleSheet(
        f"background: {bg}; border: 1px solid {border}; border-radius: 8px;"
        f"color: {fg}; font-size: 10px; font-weight: 700; padding: 2px 8px;"
    )
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lab


def btn(text: str, kind: str = "ghost", tip: str = "", small: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName(kind if kind in ("primary", "ghost", "danger", "success", "chip") else "ghost")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if tip:
        b.setToolTip(tip)
    b.setFixedHeight(32 if small else 38)
    return b


def icon_btn(symbol: str, tip: str = "", danger: bool = False) -> QPushButton:
    b = QPushButton(symbol)
    b.setObjectName("iconBtn")
    b.setFixedSize(30, 30)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if danger:
        b.setProperty("danger", True)
    if tip:
        b.setToolTip(tip)
    return b


def hline() -> QFrame:
    f = QFrame()
    f.setObjectName("hline")
    f.setFixedHeight(1)
    f.setFrameShape(QFrame.Shape.NoFrame)
    return f


def vline() -> QFrame:
    f = QFrame()
    f.setObjectName("vline")
    f.setFixedWidth(1)
    f.setFrameShape(QFrame.Shape.NoFrame)
    return f


def styled_bar(color: str = "primary") -> QProgressBar:
    p = QProgressBar()
    p.setRange(0, 100)
    p.setTextVisible(False)
    p.setFixedHeight(6)
    p.setObjectName({"emerald": "barGreen", "amber": "barAmber", "rose": "barRose"}.get(color, "barDefault"))
    return p


def set_shadow(w: QWidget, blur: int = 40, alpha: int = 160, dy: int = 10) -> None:
    eff = QGraphicsDropShadowEffect(w)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    w.setGraphicsEffect(eff)


def _title_block(title: str, sub: str) -> QVBoxLayout:
    v = QVBoxLayout()
    v.setSpacing(3)
    v.addWidget(mk_label(title, "titleLg"))
    v.addWidget(mk_label(sub, "body", "muted"))
    return v


def heading_block(kicker: str, title: str, sub: str = "") -> Tuple[QWidget, QVBoxLayout]:
    """Eyebrow + display title + supporting line, used at the top of pages."""
    host = QWidget()
    v = QVBoxLayout(host)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(2)
    if kicker:
        v.addWidget(eyebrow(kicker))
    v.addWidget(mk_label(title, "display"))
    if sub:
        v.addWidget(mk_label(sub, "body", "muted"))
    return host, v
