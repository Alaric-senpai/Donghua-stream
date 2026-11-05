"""Async YouTube thumbnail fetcher with an on-disk cache."""
import hashlib
import os
import re
from typing import Dict, Optional

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import (
    QNetworkAccessManager, QNetworkReply, QNetworkRequest,
)


THUMB_DIR = os.path.join(os.path.expanduser("~"), ".cache", "donghua-stream", "thumbs")
REMOTE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "donghua-stream", "remote")


class ThumbnailStore(QObject):
    """Fetch YouTube posters asynchronously with a disk cache.

    Library cards request by video id (``get``); Explore cards request the
    exact thumbnail URL returned by the Data API (``get_url``) so they can use
    true 16:9 artwork.  Both paths emit ``loaded`` with the cache key they were
    asked for, so each page can update the right widgets.
    """

    loaded = pyqtSignal(str, QPixmap)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._nam.finished.connect(self._on_finished)
        self._inflight: set = set()
        self._reply_keys: Dict[int, str] = {}
        self._reply_paths: Dict[int, str] = {}

    def thumb_path(self, vid: str) -> str:
        return os.path.join(THUMB_DIR, f"{vid}.jpg")

    def remote_path(self, cache_key: str) -> str:
        digest = hashlib.sha1(str(cache_key).encode("utf-8")).hexdigest()
        return os.path.join(REMOTE_DIR, f"{digest}.jpg")

    def get(self, vid: str) -> Optional[QPixmap]:
        if not vid:
            return None
        return self._load(vid, self.thumb_path(vid),
                          f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg")

    def get_url(self, cache_key: str, url: str) -> Optional[QPixmap]:
        """Load an arbitrary thumbnail URL, cached under ``cache_key``."""
        if not cache_key or not url:
            return None
        return self._load(cache_key, self.remote_path(cache_key), url)

    def _load(self, key: str, path: str, url: str) -> Optional[QPixmap]:
        if os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                return pix
        if key in self._inflight:
            return None
        self._inflight.add(key)
        req = QNetworkRequest(QUrl(url))
        req.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute,
                         QNetworkRequest.CacheLoadControl.PreferCache)
        reply = self._nam.get(req)
        self._reply_keys[id(reply)] = key
        self._reply_paths[id(reply)] = path
        return None

    def _on_finished(self, reply: QNetworkReply) -> None:
        key = self._reply_keys.pop(id(reply), "")
        path = self._reply_paths.pop(id(reply), "")
        if not key:
            # Fall back to the old URL convention for requests made elsewhere.
            match = re.search(r"/vi/([A-Za-z0-9_-]{6,})/",
                              reply.request().url().toString())
            if not match:
                reply.deleteLater()
                return
            key = match.group(1)
            path = self.thumb_path(key)
        self._inflight.discard(key)
        data = bytes(reply.readAll())
        reply.deleteLater()
        if not data:
            return
        pix = QPixmap()
        if pix.loadFromData(data) and not pix.isNull():
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                pix.save(path, "JPG")
            except OSError:
                pass
        if not pix.isNull():
            self.loaded.emit(key, pix)

