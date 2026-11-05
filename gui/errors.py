"""Global crash capture that shows a copyable report instead of aborting."""
import platform
import sys
import traceback
from datetime import datetime
from typing import Any, Optional

from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from .dialogs.error_dialog import ErrorDialog


def environment_summary() -> str:
    """Small, paste-friendly header for every crash report."""
    try:
        import yt_dlp
        engine = getattr(yt_dlp.version, "__version__", "unknown")
    except Exception:
        engine = "unknown"
    return (
        f"Time:     {datetime.now().isoformat(timespec='seconds')}\n"
        f"Python:   {sys.version.split()[0]}\n"
        f"PyQt:     {PYQT_VERSION_STR}  ·  Qt {QT_VERSION_STR}\n"
        f"Platform: {platform.platform()}\n"
        f"Engine:   yt-dlp {engine}\n"
    )


def format_exception(exc_type: Any, exc_value: BaseException,
                     tb: Any) -> str:
    body = "".join(traceback.format_exception(exc_type, exc_value, tb))
    return f"{environment_summary()}\n{body}"


class ErrorReporter(QObject):
    """Marshals exceptions from any thread onto the GUI thread."""

    error = pyqtSignal(str, str, str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._showing = False
        self.error.connect(self._present)

    def _present(self, title: str, summary: str, details: str) -> None:
        if self._showing:
            sys.stderr.write(details + "\n")
            return
        self._showing = True
        try:
            ErrorDialog(title, summary, details).exec()
        except Exception:
            sys.stderr.write(details + "\n")
        finally:
            self._showing = False

    def capture(self, title: str, summary: str, details: str) -> None:
        self.error.emit(title, summary, details)


def install_exception_hook(app: QApplication) -> ErrorReporter:
    """Replace sys.excepthook so PyQt6 does not abort on slot exceptions."""
    reporter = ErrorReporter(app)
    app._error_reporter = reporter  # type: ignore[attr-defined]
    previous = sys.excepthook

    def hook(exc_type, exc_value, tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc_value, tb)
            return
        reporter.capture(
            "Unexpected error",
            "The app intercepted this error and kept running. Copy the details "
            "below before reporting it.",
            format_exception(exc_type, exc_value, tb),
        )

    sys.excepthook = hook
    return reporter
