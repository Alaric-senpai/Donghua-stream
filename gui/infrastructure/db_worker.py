"""Run blocking Postgres calls off the UI thread."""
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class DbWorker(QThread):
    done = pyqtSignal(object, object)     # token, result_or_exception

    def __init__(self, fn: Callable[[], Any], token: int, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.fn = fn
        self.token = token

    def run(self) -> None:
        try:
            self.done.emit(self.token, self.fn())
        except Exception as exc:  # noqa: BLE001
            self.done.emit(self.token, exc)

