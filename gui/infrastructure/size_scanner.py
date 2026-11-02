"""Background disk-usage scanner for series folders."""
import os
from typing import List, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal


class SizeScanner(QThread):
    scanned = pyqtSignal(int, int)   # series_id, bytes

    def __init__(self, jobs: List[Tuple[int, str]], parent=None):
        super().__init__(parent)
        self.jobs = jobs

    def run(self):
        for series_id, path in self.jobs:
            total = 0
            try:
                for root, _dirs, files in os.walk(os.path.expanduser(path)):
                    for f in files:
                        try:
                            total += os.path.getsize(os.path.join(root, f))
                        except OSError:
                            pass
            except OSError:
                total = 0
            self.scanned.emit(series_id, total)

