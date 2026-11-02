"""Async YouTube thumbnail fetcher with an on-disk cache."""
import os
import re
from typing import Optional

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import (
    QNetworkAccessManager, QNetworkReply, QNetworkRequest,
)


THUMB_DIR = os.path.join(os.path.expanduser("~"), ".cache", "donghua-stream", "thumbs")


class ThumbnailStore(QObject):
    """Fetch hqdefault posters for video ids asynchronously with a disk cache."""

    loaded = pyqtSignal(str, QPixmap)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._nam.finished.connect(self._on_finished)
        self._inflight: set = set()

    def thumb_path(self, vid: str) -> str:
        return os.path.join(THUMB_DIR, f"{vid}.jpg")

    def get(self, vid: str) -> Optional[QPixmap]:
        if not vid:
            return None
        path = self.thumb_path(vid)
        if os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                return pix
        if vid in self._inflight:
            return None
        self._inflight.add(vid)
        req = QNetworkRequest(QUrl(f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"))
        req.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute,
                         QNetworkRequest.CacheLoadControl.PreferCache)
        self._nam.get(req)
        return None

    def _on_finished(self, reply: QNetworkReply) -> None:
        vid = re.search(r"/vi/([A-Za-z0-9_-]{6,})/", reply.request().url().toString())
        if not vid:
            return
        vid = vid.group(1)
        self._inflight.discard(vid)
        data = bytes(reply.readAll())
        reply.deleteLater()
        if not data:
            return
        pix = QPixmap()
        if pix.loadFromData(data) and not pix.isNull():
            pix.save(self.thumb_path(vid), "JPG")
        if not pix.isNull():
            self.loaded.emit(vid, pix)

