"""SourceExploreView — browse AnimeCube / DonghuaStream series catalogs.

Shows a trending grid by default and a search flow.  Clicking any series
card emits ``series_selected(source_key, series_dict)`` so the parent window
can navigate to SourceDetailView.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout,
    QWidget,
)

import sources
from ..components.primitives import btn, chip_tag, eyebrow, mk_label
from ..components.poster_grid import PosterGrid
from ..components.source_card import SourceSeriesCard
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import (
    T_AMBER2, T_AMBER_LINE, T_AMBER_SOFT, T_EMERALD2,
    T_EMERALD_LINE, T_EMERALD_SOFT, T_MUTED,
    T_ROSE_LINE, T_ROSE_SOFT, T_ROSE2,
)

SEARCH_STYLE = """
QLineEdit {
    background: #0f0f0f;
    border: 1px solid #303030;
    border-radius: 20px;
    padding: 8px 16px;
    color: #f1f1f1;
    font-size: 13px;
    selection-background-color: #3ea6ff;
    selection-color: #0f0f0f;
}
QLineEdit:focus { border-color: #3ea6ff; }
"""

SEARCH_BUTTON_STYLE = """
QPushButton {
    background: #272727;
    color: #f1f1f1;
    border: 1px solid #303030;
    border-radius: 20px;
    padding: 0 18px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton:hover { background: #3f3f3f; }
QPushButton:pressed { background: #4a4a4a; }
QPushButton:disabled { color: #717171; background: #1f1f1f; }
"""

class _ExploreWorker(QThread):
    """Run one blocking network call without freezing the UI."""
    result_ready = pyqtSignal(int, object)   # token, result-or-exception

    def __init__(self, token: int, fn, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._token = token
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            result = exc
        self.result_ready.emit(self._token, result)


class SourceExploreView(QWidget):
    """Browse and search AnimeCube / DonghuaStream catalogs.

    Default state: trending grid (top-rated series from the source).
    Search state: results grid matching the user's query.

    Emits ``series_selected(source_key, series_dict)`` when a card is clicked.
    """

    # source_key, series_dict
    series_selected = pyqtSignal(str, dict)
    connect_requested = pyqtSignal()   # no-op for non-YouTube sources

    def __init__(self, source_key: str,
                 thumbs: ThumbnailStore,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._source_key = source_key
        self._thumbs = thumbs
        self._source = sources.SOURCES.get(source_key)
        self._label = (
            self._source.label if self._source else source_key.title())
        self._mode = "idle"   # idle | trending | search
        self._last_query = ""
        self._busy = False
        self._cards: List[SourceSeriesCard] = []
        self._token = 0
        self._worker: Optional[_ExploreWorker] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        content = QVBoxLayout(host)
        content.setContentsMargins(28, 14, 28, 22)
        content.setSpacing(14)

        # ---- header
        self.eyebrow_label = eyebrow("")
        self.title_label = mk_label("", "titleLg")
        self.subtitle_label = mk_label("", "body", "muted")
        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(self.eyebrow_label)
        head.addWidget(self.title_label)
        head.addWidget(self.subtitle_label)
        content.addLayout(head)

        # ---- search row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.source_chip = chip_tag(f"{self._label.upper()}", "sky")
        self.source_chip.setFixedHeight(28)
        search_row.addWidget(self.source_chip)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            f"Search {self._label} for a donghua series…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(40)
        self.search_input.setStyleSheet(SEARCH_STYLE)
        self.search_input.returnPressed.connect(self._submit_search)
        search_row.addWidget(self.search_input, 1)

        self.search_btn = btn("Search", "primary")
        self.search_btn.setFixedHeight(40)
        self.search_btn.setStyleSheet(SEARCH_STYLE)
        self.search_btn.clicked.connect(self._submit_search)
        search_row.addWidget(self.search_btn)
        content.addLayout(search_row)

        # ---- section header
        self.section_title = mk_label("", "titleMd")
        self.section_caption = mk_label("", "small")
        self.section_caption.setStyleSheet(f"color: {T_MUTED};")
        sec = QHBoxLayout()
        sec.setSpacing(8)
        sec.addWidget(self.section_title)
        sec.addWidget(self.section_caption)
        sec.addStretch(1)
        self.api_chip = QLabel()
        self.api_chip.setStyleSheet(
            f"background: {T_AMBER_SOFT}; border: 1px solid {T_AMBER_LINE};"
            f"border-radius: 8px; color: {T_AMBER2}; font-size: 10px;"
            "font-weight: 700; padding: 2px 8px;")
        sec.addWidget(self.api_chip)
        content.addLayout(sec)

        # ---- content grid
        self.grid = PosterGrid()
        content.addWidget(self.grid)

        # ---- loading / error panels
        self.loading_panel = QFrame()
        self.loading_panel.setObjectName("card")
        lp_lay = QVBoxLayout(self.loading_panel)
        lp_lay.setContentsMargins(24, 20, 24, 20)
        lp_lay.setSpacing(8)
        lp_lay.addWidget(mk_label("Loading…", "titleMd"))
        self.loading_sub = mk_label("", "body", "muted")
        lp_lay.addWidget(self.loading_sub)
        self.loading_panel.hide()

        self.state_panel = QFrame()
        self.state_panel.setObjectName("card")
        sp_lay = QVBoxLayout(self.state_panel)
        sp_lay.setContentsMargins(24, 20, 24, 20)
        sp_lay.setSpacing(4)
        self.state_icon = mk_label("", "display")
        self.state_title = mk_label("", "titleMd")
        self.state_desc = mk_label("", "body", "muted")
        self.state_desc.setWordWrap(True)
        self.state_action1 = btn("Action", "ghost")
        self.state_action2 = btn("Action", "ghost")
        sp_lay.addWidget(self.state_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        sp_lay.addWidget(self.state_title, 0, Qt.AlignmentFlag.AlignHCenter)
        sp_lay.addWidget(self.state_desc, 0, Qt.AlignmentFlag.AlignHCenter)
        hrow = QHBoxLayout()
        hrow.addWidget(self.state_action1)
        hrow.addWidget(self.state_action2)
        sp_lay.addLayout(hrow)
        self.state_panel.hide()

        content.addWidget(self.loading_panel)
        content.addWidget(self.state_panel)
        content.addStretch(1)

        self.page_scroll.setWidget(host)
        root.addWidget(self.page_scroll)

        # Deferred: the host calls ensure_loaded() when this tab is shown,
        # so the catalog is not fetched until the user opens this source.
        self._loaded = False
        self.eyebrow_label.setText(f"{self._label.upper()} · CATALOG")
        self.title_label.setText(f"Explore {self._label}")
        self.subtitle_label.setText(
            f"Browse the public {self._label} catalog. "
            "No account or API key is required.")
        self.section_title.setText("Trending Series")
        self.section_caption.setText(
            "Catalog loads when this tab is opened…")
        self._chip("PUBLIC", T_EMERALD2, T_EMERALD_SOFT, T_EMERALD_LINE)

    # ---- navigation --------------------------------------------------------
    @property
    def source_url(self) -> str:
        return self._source.home_url if self._source else ""

    # ---- load trending -----------------------------------------------------
    def _to_card(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a raw catalog entry into a display card.

        AnimeCube's catalog carries raw fields (``coverImage``, ``slug``);
        its own ``_card`` builder turns those into a card dict.  DonghuaStream
        already returns finished cards.
        """
        if item.get("url") and "thumbnail" in item:
            return dict(item)
        builder = getattr(self._source, "_card", None)
        if builder is not None:
            try:
                return dict(builder(item))
            except Exception:
                return dict(item)
        return dict(item)

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self._show_trending()

    def _show_trending(self) -> None:
        if not self._source:
            return
        self._loaded = True
        self._set_busy(True)
        self.loading_panel.show()
        self.grid.hide()
        self.state_panel.hide()
        self._set_status(f"{self._label.upper()} · TRENDING")
        self.eyebrow_label.setText(f"{self._label.upper()} · CATALOG")
        self.title_label.setText(f"Explore {self._label}")
        self.subtitle_label.setText(
            f"Browse the public {self._label} catalog. "
            "No account or API key is required.")
        self.section_title.setText("Trending Series")
        self.section_caption.setText("Top-rated donghua from the community")
        self._chip("PUBLIC", T_EMERALD2, T_EMERALD_SOFT, T_EMERALD_LINE)

        def load() -> List[Dict[str, Any]]:
            try:
                catalog = self._source._catalog()
            except Exception:
                catalog = []
            # Sort by rating desc
            scored = sorted(
                catalog,
                key=lambda x: float(x.get("rating") or 0),
                reverse=True,
            )
            return [self._to_card(item) for item in scored]

        self._token += 1
        worker = _ExploreWorker(self._token, load)
        self._worker = worker

        def _done(t: int, result: Any) -> None:
            if self._worker is not worker:
                return
            self._worker = None
            worker.deleteLater()
            self._set_busy(False)
            if isinstance(result, Exception):
                self._show_error(result)
                return
            self._on_trending(result)

        worker.result_ready.connect(_done)
        worker.start()

    def _on_trending(self, items: List[Dict[str, Any]]) -> None:
        self._mode = "trending"
        self._cards = []
        for it in items:
            card = SourceSeriesCard(it, self._thumbs)
            card.selected.connect(self._on_card_selected)
            self._cards.append(card)
        self.loading_panel.hide()
        self.grid.set_items(self._cards)
        self.grid.show()
        self.section_title.setText("Trending Series")
        self.section_caption.setText(
            f"{len(items)} series  ·  sorted by rating")
        self._set_status(
            f"{self._label.upper()} · {len(items)} TRENDING SERIES")

    # ---- search -----------------------------------------------------------
    def _submit_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self._clear_search()
            return
        if self._busy:
            return
        self._last_query = query
        self._mode = "search"
        self.loading_panel.show()
        self.grid.hide()
        self.state_panel.hide()
        self._set_status(f"SEARCHING {self._label.upper()}…")
        self.section_title.setText(f"Searching for \"{query}\"")
        self.section_caption.setText("Contacting the catalog…")
        self._chip("SEARCHING", T_AMBER2, T_AMBER_SOFT, T_AMBER_LINE)

        def do_search() -> List[Dict[str, Any]]:
            return self._source.search(query, max_results=20)

        self._token += 1
        worker = _ExploreWorker(self._token, do_search)
        self._worker = worker

        def _done(t: int, result: Any) -> None:
            if self._worker is not worker:
                return
            self._worker = None
            worker.deleteLater()
            self._set_busy(False)
            if isinstance(result, Exception):
                self._show_error(result)
                return
            self._on_search(query, result)

        worker.result_ready.connect(_done)
        worker.start()

    def _on_search(self, query: str, items: List[Dict[str, Any]]) -> None:
        self._mode = "search"
        self._cards = []
        for it in items:
            card = SourceSeriesCard(it, self._thumbs)
            card.selected.connect(self._on_card_selected)
            self._cards.append(card)
        self.loading_panel.hide()
        if not items:
            self.state_icon.setText("◎")
            self.state_title.setText("No results found")
            self.state_desc.setText(
                f"{self._label} returned no series for \"{query}\". "
                "Try a shorter or different title.")
            self.state_action1.hide()
            self.state_action2.setText("Show trending")
            self.state_action2.show()
            self.state_action2.clicked.connect(self._show_trending)
            self.state_panel.show()
        else:
            self.state_panel.hide()
            self.grid.set_items(self._cards)
            self.grid.show()
        self.section_title.setText(f"Results for \"{query}\"")
        self.section_caption.setText(
            f"{len(items)} series  ·  {self._label}")
        self._chip("PUBLIC", T_EMERALD2, T_EMERALD_SOFT, T_EMERALD_LINE)
        self._set_status(
            f"{self._label.upper()} · {len(items)} RESULTS FOR \"{query}\"")

    def _clear_search(self) -> None:
        self.search_input.clear()
        self._mode = "idle"
        self._last_query = ""
        self._show_trending()

    # ---- card interaction --------------------------------------------------
    def _on_card_selected(self, series_dict: Dict[str, Any]) -> None:
        self.series_selected.emit(self._source_key, series_dict)

    # ---- states ----------------------------------------------------------
    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.search_input.setEnabled(not busy)
        self.search_btn.setEnabled(not busy)

    def _chip(self, text: str, fg: str, bg: str, border: str) -> None:
        self.api_chip.setText(text)
        self.api_chip.setStyleSheet(
            f"background: {bg}; border: 1px solid {border};"
            f"border-radius: 8px; color: {fg}; font-size: 10px;"
            "font-weight: 700; padding: 2px 8px;")

    def _set_status(self, text: str) -> None:
        self.section_caption.setText(text)

    def _show_error(self, exc: Exception) -> None:
        self.loading_panel.hide()
        summary = str(exc) if exc else "Unknown error"
        self.state_icon.setText("⚠")
        self.state_title.setText(f"{self._label} is not responding")
        self.state_desc.setText(summary)
        self.state_action1.setText("Try again")
        self.state_action1.show()
        self.state_action1.clicked.connect(self._show_trending)
        self.state_action2.setText("Clear")
        self.state_action2.show()
        self.state_action2.clicked.connect(self._clear_search)
        self.state_panel.show()
        self._chip("ERROR", T_ROSE2, T_ROSE_SOFT, T_ROSE_LINE)

    def shutdown(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(1500)