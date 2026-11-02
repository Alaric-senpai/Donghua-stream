"""Application bootstrap: the single public entry point for the desktop app."""
import sys
from typing import List, Optional

from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication

from .icons import icon
from .theme import F_BODY, T_PRIMARY, app_stylesheet
from .window import MainWindow


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
    window = MainWindow()
    window.show()
    return app.exec()
