"""Application bootstrap: the single public entry point for the desktop app."""
import sys
from typing import List, Optional

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from .theme import app_stylesheet
from .window import MainWindow


def main(argv: Optional[List[str]] = None) -> int:
    """Launch Donghua Stream. Used by `donghua-gui` and `donghua --gui`."""
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Donghua Stream")
    app.setOrganizationName("donghua")
    app.setStyleSheet(app_stylesheet())
    app.setWindowIcon(QIcon.fromTheme("applications-multimedia"))
    window = MainWindow()
    window.show()
    return app.exec()
