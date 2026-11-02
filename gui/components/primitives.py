"""Tokens-driven visual primitives used by every page and dialog."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QLabel, QProgressBar, QPushButton,
    QVBoxLayout, QWidget,
)

from ..theme import (
    T_AMBER, T_CARD, T_EMERALD, T_EMERALD2, T_MUTED, T_ON_PRIMARY,
    T_PRIMARY, T_ROSE, T_SEC,
)


def mk_label(text: str = "", cls: str = "", color_name: str = "",
             wrap: bool = False) -> QLabel:
    """Styled label: cls is one of titleXl/titleLg/titleMd/titleSm/body/small."""
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
    lab.setStyleSheet(
        f"color: {T_MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px;"
    )
    return lab


def chip_tag(text: str, tone: str = "default") -> QLabel:
    tones = {
        "default": (T_CARD, "#33415588", T_SEC),
        "sky": ("#38bdf833", "#38bdf877", T_PRIMARY),
        "emerald": ("#10b98122", "#10b98166", T_EMERALD2),
        "amber": ("#f59e0b22", "#f59e0b66", "#fcd34d"),
        "rose": ("#f43f5e22", "#f43f5e66", "#fda4af"),
        "primary": (T_PRIMARY, T_PRIMARY, T_ON_PRIMARY),
    }
    bg, border, fg = tones.get(tone, tones["default"])
    lab = QLabel(text)
    lab.setStyleSheet(
        f"background: {bg}; border: 1px solid {border}; border-radius: 999px;"
        f"color: {fg}; font-size: 11px; font-weight: 700; padding: 2px 10px;"
    )
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lab


def btn(text: str, kind: str = "ghost", tip: str = "", small: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName(kind if kind in ("primary", "ghost", "danger", "success", "chip") else "ghost")
    if tip:
        b.setToolTip(tip)
    if small:
        b.setFixedHeight(28)
    else:
        b.setMinimumHeight(38)
    return b


def icon_btn(symbol: str, tip: str = "") -> QPushButton:
    b = QPushButton(symbol, )
    b.setObjectName("iconBtn")
    b.setFixedSize(30, 30)
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
    v.addWidget(mk_label(title, "titleLg"))
    v.addWidget(mk_label(sub, "body", "muted"))
    return v

