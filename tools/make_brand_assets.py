"""Build the app icon and banner from the artwork the app already cached.

The desktop hub borrows its identity from the donghua posters it has seen:
this script mosaics a handful of cached images into a rounded app icon and a
wide banner, both in the app's dark-navy palette.

Usage:
    ./venv/bin/python tools/make_brand_assets.py
    ./venv/bin/python tools/make_brand_assets.py --icon-size 256 --count 40
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtGui import (
    QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
    QPixmap,
)

NAVY = QColor("#020617")
NAVY_SOFT = QColor("#0b1222")
CYAN = QColor("#3ea6ff")
WHITE = QColor("#f8fafc")


def _candidates(cache_dir: Path, count: int) -> List[Path]:
    """Pick poster-like images out of the thumbnail cache, deterministically."""
    pools = [cache_dir / "remote", cache_dir / "thumbs"]
    found: List[Path] = []
    for pool in pools:
        if not pool.is_dir():
            continue
        for path in sorted(pool.glob("*.jpg")):
            try:
                image = QImage(str(path))
            except Exception:
                continue
            if image.isNull() or image.height() < 120:
                continue
            ratio = image.height() / max(1, image.width())
            if 1.15 <= ratio <= 2.1:      # portrait posters read best
                found.append(path)
    if not found:
        return []
    rng = random.Random(7)
    rng.shuffle(found)
    return found[:max(4, count)]


def _cover(pix: QPixmap, size: int) -> QPixmap:
    """Scale a pixmap so it covers a square of `size`, centred."""
    scaled = pix.scaled(size, size,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation)
    x = (scaled.width() - size) // 2
    y = (scaled.height() - size) // 2
    return scaled.copy(x, y, size, size)


def _play_triangle(painter: QPainter, centre: QPointF, height: float,
                   color: QColor, alpha: int = 235) -> None:
    """Draw the app's play glyph."""
    w = height * 0.88
    path = QPainterPath()
    path.moveTo(centre.x() - w * 0.42, centre.y() - height / 2)
    path.lineTo(centre.x() + w * 0.58, centre.y())
    path.lineTo(centre.x() - w * 0.42, centre.y() + height / 2)
    path.closeSubpath()
    glow = QColor(color)
    glow.setAlpha(70)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(glow))
    painter.drawPath(path)
    fill = QColor(color)
    fill.setAlpha(alpha)
    painter.setBrush(QBrush(fill))
    painter.drawPath(path)


def _rounded_mask(size: int, radius: int) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    return path


def build_icon(images: List[Path], size: int) -> QPixmap:
    canvas = QPixmap(size, size)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    radius = int(size * 0.22)
    painter.setClipPath(_rounded_mask(size, radius))

    cells = 2
    cell = size // cells
    for index in range(cells * cells):
        if not images:
            break
        image = images[index % len(images)]
        pix = QPixmap(str(image))
        if pix.isNull():
            continue
        x = (index % cells) * cell
        y = (index // cells) * cell
        painter.drawPixmap(x, y, _cover(pix, cell + 2))

    if not images:
        painter.fillRect(QRectF(0, 0, size, size), QBrush(NAVY))

    # Darken the artwork so the glyph stays readable.
    shade = QLinearGradient(0, 0, 0, size)
    shade.setColorAt(0.0, QColor(2, 6, 23, 120))
    shade.setColorAt(1.0, QColor(2, 6, 23, 195))
    painter.fillRect(QRectF(0, 0, size, size), QBrush(shade))

    _play_triangle(painter, QPointF(size * 0.5, size * 0.5),
                   size * 0.30, WHITE)

    painter.setClipping(False)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    pen = QPen(QColor(CYAN.red(), CYAN.green(), CYAN.blue(), 90))
    pen.setWidth(max(2, size // 160))
    painter.setPen(pen)
    painter.drawPath(_rounded_mask(size, radius))
    painter.end()
    return canvas


def build_banner(images: List[Path], width: int, height: int) -> QPixmap:
    canvas = QPixmap(width, height)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    painter.setClipRect(QRectF(0, 0, width, height))
    count = max(3, min(6, len(images) or 3))
    strip = width // count
    for index in range(count):
        if not images:
            break
        pix = QPixmap(str(images[index % len(images)]))
        if pix.isNull():
            continue
        scaled = pix.scaled(strip + 2, height,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
        x = (scaled.width() - strip) // 2
        y = (scaled.height() - height) // 2
        painter.drawPixmap(index * strip, 0, scaled.copy(x, y, strip, height))

    if not images:
        painter.fillRect(QRectF(0, 0, width, height), QBrush(NAVY))

    fade = QLinearGradient(0, 0, width, 0)
    fade.setColorAt(0.0, QColor(2, 6, 23, 245))
    fade.setColorAt(0.45, QColor(2, 6, 23, 170))
    fade.setColorAt(1.0, QColor(2, 6, 23, 120))
    painter.fillRect(QRectF(0, 0, width, height), QBrush(fade))

    vertical = QLinearGradient(0, 0, 0, height)
    vertical.setColorAt(0.0, QColor(11, 18, 34, 120))
    vertical.setColorAt(1.0, QColor(2, 6, 23, 170))
    painter.fillRect(QRectF(0, 0, width, height), QBrush(vertical))

    _play_triangle(painter, QPointF(width * 0.16, height * 0.5),
                   height * 0.42, WHITE, alpha=210)
    painter.end()
    return canvas


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        default=os.path.join(os.path.expanduser("~"), ".cache",
                             "donghua-stream"))
    parser.add_argument("--out-dir", default="gui/assets/icons")
    parser.add_argument("--icon-size", type=int, default=512)
    parser.add_argument("--banner-size", default="1600x600")
    parser.add_argument("--count", type=int, default=48)
    args = parser.parse_args(argv)

    try:
        width, height = (int(part) for part in args.banner_size.lower().split("x"))
    except ValueError:
        print(f"invalid --banner-size: {args.banner_size}", file=sys.stderr)
        return 2

    # QPixmap needs a running Qt application.
    app = QGuiApplication.instance() or QGuiApplication([])

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    images = _candidates(Path(args.cache_dir), args.count)
    if not images:
        print("no cached artwork found — drawing the abstract fallback mark")

    icon = build_icon(images, args.icon_size)
    icon_path = out_dir / "app-icon.png"
    icon.save(str(icon_path), "PNG")

    banner = build_banner(images, width, height)
    banner_path = out_dir / "app-banner.png"
    banner.save(str(banner_path), "PNG")

    print(f"icon   : {icon_path} ({icon.width()}x{icon.height()}, "
          f"{len(images)} source images)")
    print(f"banner : {banner_path} ({banner.width()}x{banner.height()}, "
          f"{len(images)} source images)")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
