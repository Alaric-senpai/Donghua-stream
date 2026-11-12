"""ExploreHost: one Explore screen per source, switched by a tab bar.

YouTube keeps its original search page untouched.  AnimeCube and
DonghuaStream each get their own catalog screen with a trending grid by
default, so every source is browsable on its own page.
"""
from typing import Dict, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from ..components.primitives import btn, eyebrow
from ..infrastructure.thumbnails import ThumbnailStore
from .explore import ExploreView
from .source_explore import SourceExploreView

SOURCE_KEYS = ("youtube", "animecube", "donghuastream")


class ExploreHost(QWidget):
    """Tabbed container holding one screen per source."""

    tab_changed = pyqtSignal(str)   # source key

    def __init__(self, thumbs: ThumbnailStore,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- tab bar
        bar = QFrame()
        bar.setObjectName("card")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 10, 18, 10)
        bl.setSpacing(8)
        bl.addWidget(eyebrow("Explore"))
        bl.addSpacing(6)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.tab_buttons: Dict[str, QPushButton] = {}

        self.youtube_view = ExploreView(thumbs)
        self.source_views: Dict[str, SourceExploreView] = {}
        for key in SOURCE_KEYS:
            if key == "youtube":
                continue
            self.source_views[key] = SourceExploreView(key, thumbs)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.youtube_view)
        self._order = ["youtube"] + list(self.source_views.keys())
        for key in self._order[1:]:
            self.stack.addWidget(self.source_views[key])

        for key in self._order:
            label = {
                "youtube": "YouTube",
                "animecube": "AnimeCube",
                "donghuastream": "DonghuaStream",
            }.get(key, key.title())
            b = btn(label, "chip", small=True)
            b.setCheckable(True)
            b.setFixedHeight(30)
            b.setChecked(key == "youtube")
            self._group.addButton(b)
            b.clicked.connect(lambda _=False, k=key: self.select(k))
            self.tab_buttons[key] = b
            bl.addWidget(b)

        bl.addStretch(1)
        self.hint = btn("Open site", "ghost", "Open the source website", small=True)
        self.hint.setFixedHeight(30)
        self.hint.clicked.connect(self._open_site)
        bl.addWidget(self.hint)
        root.addWidget(bar)

        body = QFrame()
        body.setObjectName("root")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(0, 0, 0, 0)
        blay.addWidget(self.stack)
        root.addWidget(body, 1)

        self._current = "youtube"

    # ---- tabs --------------------------------------------------------------
    @property
    def current_key(self) -> str:
        return self._current

    def select(self, key: str) -> None:
        if key not in self._order:
            return
        self._current = key
        button = self.tab_buttons.get(key)
        if button is not None and not button.isChecked():
            button.setChecked(True)
        index = self._order.index(key)
        self.stack.setCurrentIndex(index)
        if key == "youtube":
            self.youtube_view.ensure_loaded()
        else:
            view = self.source_views.get(key)
            if view is not None:
                view.ensure_loaded()
        self.tab_changed.emit(key)

    def ensure_loaded(self) -> None:
        self.select(self._current)

    def _open_site(self) -> None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        if self._current == "youtube":
            QDesktopServices.openUrl(QUrl("https://www.youtube.com"))
            return
        view = self.source_views.get(self._current)
        if view is not None:
            QDesktopServices.openUrl(QUrl(view.source_url))

    def shutdown(self) -> None:
        for view in self.source_views.values():
            try:
                view.shutdown()
            except Exception:
                pass
