"""Application bootstrap: the single public entry point for the desktop app."""
import sys
from typing import List, Optional

from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication

import app_config

from .dialogs.credentials import prompt_for_credentials
from .dialogs.error_dialog import report_error
from .errors import install_exception_hook
from .icons import icon
from .theme import F_BODY, T_PRIMARY, app_stylesheet
from .window import MainWindow


def _ensure_startup_config() -> None:
    """Prompt for any credential missing from the global config file.

    The dialog is intentionally shown before MainWindow is constructed so a
    first run never opens a window that is guaranteed to show a database
    error.  Closing it with "Not now" is allowed: the app still opens and the
    missing feature reports a copyable error.
    """
    try:
        issues = app_config.credential_issues()
    except app_config.ConfigError as exc:
        report_error(
            None, "Config file problem",
            "The global config file could not be read. Fix the JSON or remove "
            "it to start from defaults.",
            f"{app_config.display_path()}\n\n{exc}")
        return
    if not issues:
        return
    accepted = prompt_for_credentials(focus="all")
    if accepted:
        try:
            import db
            db.reload_db_config()
        except Exception:
            pass


def main(argv: Optional[List[str]] = None) -> int:
    """Launch Donghua Stream. Used by `donghua-gui` and `donghua --gui`."""
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Donghua Stream")
    app.setOrganizationName("donghua")
    app.setStyle("Fusion")
    app.setFont(QFont(F_BODY, 10))
    app.setStyleSheet(app_stylesheet())
    window_icon = icon("play", T_PRIMARY, 64)
    if window_icon.isNull():
        window_icon = QIcon.fromTheme("applications-multimedia")
    app.setWindowIcon(window_icon)
    install_exception_hook(app)
    _ensure_startup_config()
    window = MainWindow()
    window.show()
    return app.exec()
