"""Tintable SVG icons for the shell, nav and inline affordances."""
from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

ASSET_DIR = Path(__file__).resolve().parent / "assets" / "icons"


def asset_path(name: str) -> str:
    """Absolute path to a packaged SVG (used by QSS url() rules)."""
    return (ASSET_DIR / name).as_posix()


@lru_cache(maxsize=96)
def icon(name: str, color: str = "#94a3b8", size: int = 18) -> QIcon:
    """Render a line SVG in `color` at a crisp 2x device pixel ratio."""
    path = ASSET_DIR / f"{name}.svg"
    if not path.exists():
        return QIcon()
    try:
        svg = path.read_text(encoding="utf-8").replace("currentColor", color)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        pix = QPixmap(size * 2, size * 2)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        pix.setDevicePixelRatio(2.0)
        return QIcon(pix)
    except Exception:
        return QIcon()
