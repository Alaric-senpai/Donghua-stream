"""Small, interruptible motion helpers (Apple-style fade-through)."""
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QWidget


def fade_in(widget: QWidget, ms: int = 180) -> None:
    """Fade a widget in without blocking; safe to call repeatedly."""
    old = getattr(widget, "_fade_anim", None)
    if old is not None:
        try:
            old.stop()
        except RuntimeError:
            pass
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _done() -> None:
        try:
            widget.setGraphicsEffect(None)
        except RuntimeError:
            pass
        if getattr(widget, "_fade_anim", None) is anim:
            widget._fade_anim = None  # type: ignore[attr-defined]

    anim.finished.connect(_done)
    widget._fade_anim = anim  # type: ignore[attr-defined]
    anim.start()
