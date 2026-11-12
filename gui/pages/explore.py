"""Explore: explicit YouTube search with cached, quota-aware results.

Nothing loads automatically.  The page starts on a search prompt; only an
explicit search calls the YouTube Data API, and responses are cached on disk.
"""
import traceback
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QSize, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

import app_config
import youtube_api
from ..components.primitives import btn, chip_tag, eyebrow, mk_label
from ..components.video_card import VideoCard
from ..components.video_grid import VideoGrid
from ..icons import icon
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import (
    F_MONO, T_AMBER2, T_AMBER_LINE, T_AMBER_SOFT, T_EMERALD2,
    T_EMERALD_LINE, T_EMERALD_SOFT, T_MUTED, T_PRIMARY,
    T_ROSE_LINE, T_ROSE_SOFT, T_ROSE2, T_SEC, T_TEXT,
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

class ExploreWorker(QThread):
    """Run one blocking network call without freezing the UI."""

    result_ready = pyqtSignal(int, object)   # token, result-or-exception

    def __init__(self, token: int, fn, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._token = token
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # handed to the GUI thread for reporting
            result = exc
        self.result_ready.emit(self._token, result)


class StatePanel(QWidget):
    """Centered onboarding / empty / error panel with two optional actions."""

    primary = pyqtSignal()
    secondary = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(240)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 24, 16, 24)
        lay.setSpacing(7)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.glyph = QLabel("◌")
        self.glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.glyph.setFixedSize(52, 52)
        lay.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignHCenter)

        self.title = QLabel("")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {T_TEXT};")
        lay.addWidget(self.title)

        self.body = QLabel("")
        self.body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.setWordWrap(True)
        self.body.setFixedWidth(640)
        self.body.setStyleSheet(f"font-size: 12px; color: {T_SEC};")
        lay.addWidget(self.body, 0, Qt.AlignmentFlag.AlignHCenter)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        self.primary_btn = btn("", "primary", small=True)
        self.primary_btn.setFixedHeight(32)
        self.primary_btn.clicked.connect(self.primary.emit)
        self.secondary_btn = btn("", "ghost", small=True)
        self.secondary_btn.setFixedHeight(32)
        self.secondary_btn.clicked.connect(self.secondary.emit)
        row.addWidget(self.primary_btn)
        row.addWidget(self.secondary_btn)
        row.addStretch(1)
        lay.addLayout(row)

    def show_state(self, glyph: str, title: str, body: str,
                   primary: str = "", secondary: str = "",
                   tone: str = "sky") -> None:
        tones = {
            "sky": (T_PRIMARY, "rgba(56,189,248,25)", "rgba(56,189,248,85)"),
            "emerald": (T_EMERALD2, T_EMERALD_SOFT, T_EMERALD_LINE),
            "amber": (T_AMBER2, T_AMBER_SOFT, T_AMBER_LINE),
            "rose": (T_ROSE2, T_ROSE_SOFT, T_ROSE_LINE),
        }
        fg, bg, border = tones.get(tone, tones["sky"])
        self.glyph.setText(glyph)
        self.glyph.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border};"
            "border-radius: 26px; font-size: 21px; font-weight: 700;")
        self.title.setText(title)
        self.body.setText(body)
        self.body.setMinimumHeight(self.body.heightForWidth(640))
        self.primary_btn.setText(primary)
        self.primary_btn.setVisible(bool(primary))
        self.secondary_btn.setText(secondary)
        self.secondary_btn.setVisible(bool(secondary))


class ExploreView(QWidget):
    connect_requested = pyqtSignal()
    add_requested = pyqtSignal(dict)
    download_requested = pyqtSignal(dict)
    open_requested = pyqtSignal(dict)

    def __init__(self, thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs
        self.thumbs.loaded.connect(self._on_thumb_loaded)
        self._token = 0
        self._worker: Optional[ExploreWorker] = None
        self._busy = False
        self._mode = "idle"
        self._last_query = ""
        self._last_error = ""
        self._cards: List[VideoCard] = []
        self._search_items: List[Dict[str, Any]] = []

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

        # ---- page heading
        head = QHBoxLayout()
        head.setSpacing(10)
        tl = QVBoxLayout()
        tl.setSpacing(2)
        self.eyebrow_label = eyebrow("YOUTUBE · DONGHUA")
        tl.addWidget(self.eyebrow_label)
        tl.addWidget(mk_label("Explore", "display"))
        self.subtitle_label = mk_label(
            "Search YouTube for a donghua, studio, trailer or episode, then "
            "add it to your library.", "body", "muted")
        tl.addWidget(self.subtitle_label)
        head.addLayout(tl)
        head.addStretch(1)
        self.api_chip = chip_tag("SEARCH READY", "emerald")
        self.api_chip.setFixedHeight(26)
        head.addWidget(self.api_chip, 0, Qt.AlignmentFlag.AlignTop)
        content.addLayout(head)

        # ---- search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search YouTube for a donghua, studio, trailer or episode…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(40)
        self.search_input.setStyleSheet(SEARCH_STYLE)
        self.search_input.returnPressed.connect(self._submit_search)
        search_row.addWidget(self.search_input, 1)

        self.search_btn = QPushButton("Search")
        self.search_btn.setFixedHeight(40)
        self.search_btn.setStyleSheet(SEARCH_BUTTON_STYLE)
        self.search_btn.setIcon(icon("search", T_TEXT, 14))
        self.search_btn.setIconSize(QSize(14, 14))
        self.search_btn.clicked.connect(self._submit_search)
        search_row.addWidget(self.search_btn)

        self.clear_btn = btn("Clear", "ghost",
                             "Clear the search and return to the start", small=True)
        self.clear_btn.setFixedHeight(40)
        self.clear_btn.clicked.connect(self._clear_search)
        self.clear_btn.hide()
        search_row.addWidget(self.clear_btn)
        content.addLayout(search_row)

        hint_row = QHBoxLayout()
        hint_row.setSpacing(8)
        self.search_hint = QLabel("")
        self.search_hint.setWordWrap(True)
        hint_row.addWidget(self.search_hint, 1)
        self.key_btn = btn("Add API key", "chip",
                           "Add a YouTube Data API key for search", small=True)
        self.key_btn.setFixedHeight(24)
        self.key_btn.clicked.connect(self.connect_requested.emit)
        self.key_btn.hide()
        hint_row.addWidget(self.key_btn)
        content.addLayout(hint_row)

        # ---- section heading
        section_head = QHBoxLayout()
        section_head.setSpacing(8)
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self.section_title = mk_label("Search YouTube", "titleLg")
        title_col.addWidget(self.section_title)
        self.section_caption = mk_label("", "small", "muted")
        title_col.addWidget(self.section_caption)
        section_head.addLayout(title_col)
        section_head.addStretch(1)
        content.addLayout(section_head)

        # ---- partial-error notice
        self.notice = QFrame()
        self.notice.setObjectName("subtleBar")
        nl = QHBoxLayout(self.notice)
        nl.setContentsMargins(12, 7, 12, 7)
        nl.setSpacing(8)
        self.notice_lbl = QLabel("")
        self.notice_lbl.setStyleSheet(f"color: {T_AMBER2}; font-size: 11px;")
        self.notice_lbl.setWordWrap(True)
        nl.addWidget(self.notice_lbl, 1)
        notice_btn = btn("Details", "ghost", "Show the copyable error report",
                         small=True)
        notice_btn.setFixedHeight(26)
        notice_btn.clicked.connect(self._copy_details)
        nl.addWidget(notice_btn)
        content.addWidget(self.notice)
        self.notice.hide()

        # ---- loading
        self.loading_panel = QFrame()
        self.loading_panel.setObjectName("card")
        lp = QVBoxLayout(self.loading_panel)
        lp.setContentsMargins(20, 34, 20, 34)
        lp.setSpacing(10)
        lp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        load_glyph = QLabel("◌")
        load_glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        load_glyph.setFixedSize(52, 52)
        load_glyph.setStyleSheet(
            f"background: rgba(56,189,248,25); color: {T_PRIMARY};"
            "border: 1px solid rgba(56,189,248,85); border-radius: 26px;"
            "font-size: 23px; font-weight: 700;")
        lp.addWidget(load_glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        self.loading_title = QLabel("Searching YouTube")
        self.loading_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {T_TEXT};")
        lp.addWidget(self.loading_title)
        self.loading_sub = QLabel("")
        self.loading_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_sub.setWordWrap(True)
        self.loading_sub.setMaximumWidth(480)
        self.loading_sub.setStyleSheet(f"font-size: 12px; color: {T_SEC};")
        lp.addWidget(self.loading_sub, 0, Qt.AlignmentFlag.AlignHCenter)
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedSize(220, 4)
        self.loading_bar.setTextVisible(False)
        lp.addWidget(self.loading_bar, 0, Qt.AlignmentFlag.AlignHCenter)
        content.addWidget(self.loading_panel)
        self.loading_panel.hide()

        # ---- empty / error state
        self.state_panel = StatePanel()
        self.state_panel.primary.connect(self.connect_requested.emit)
        content.addWidget(self.state_panel)

        # ---- video grid
        self.grid = VideoGrid()
        content.addWidget(self.grid)

        # ---- status line
        self.status_line = QLabel("")
        self.status_line.setStyleSheet(
            f"color: {T_MUTED}; font-family: '{F_MONO}'; font-size: 9px;")
        content.addWidget(self.status_line)
        content.addStretch(1)

        self.page_scroll.setWidget(host)
        root.addWidget(self.page_scroll)

        self._update_search_state()
        self._show_idle_state()

    # ---- public API -------------------------------------------------------
    def ensure_loaded(self) -> None:
        """Called when navigation lands on Explore; never touches the API."""
        self._update_search_state()
        if self._mode == "idle":
            self._show_idle_state()

    def reload_credentials(self) -> None:
        """Settings saved a new key; refresh the prompt without searching."""
        self._update_search_state()
        if self._mode == "idle":
            self._show_idle_state()

    def refresh(self) -> None:
        """Refresh the search-readiness prompt without any network access."""
        self._update_search_state()
        if self._mode == "idle":
            self._show_idle_state()

    def search_for(self, query: str) -> None:
        text = str(query or "").strip()
        if not text:
            return
        self.search_input.setText(text)
        self._submit_search()

    def shutdown(self, wait_ms: int = 2000) -> None:
        worker = self._worker
        if worker is None or not worker.isRunning():
            return
        worker.requestInterruption()
        if worker.wait(wait_ms):
            return
        # The process is exiting and Qt cannot destroy a running QThread.
        worker.terminate()
        worker.wait(500)

    # ---- search -----------------------------------------------------------
    def _submit_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self._clear_search()
            return
        if self._busy:
            return
        if not app_config.youtube_ready():
            self._update_search_state()
            self._last_query = query
            self._show_error(
                youtube_api.YouTubeNotConfigured(
                    "No YouTube Data API key is saved."))
            return
        self._mode = "search"
        self._last_query = query
        self._enter_search_mode(query, searching=True)
        limit = int(app_config.explore_config().get("result_limit") or 18)
        self._run(
            lambda: youtube_api.YouTubeClient().search(
                query, max_results=limit),
            lambda items: self._on_search(query, items),
            loading=True,
            failure=self._show_error,
        )

    def _clear_search(self) -> None:
        if self._busy:
            return
        self._mode = "idle"
        self._last_query = ""
        self._search_items = []
        self._cards = []
        self.search_input.clear()
        self.grid.set_cards([])
        self._show_idle_state()

    def _enter_search_mode(self, query: str, *, searching: bool) -> None:
        self.clear_btn.show()
        self.eyebrow_label.setText("YOUTUBE · SEARCH")
        self.subtitle_label.setText(
            "Explicit YouTube search — results are cached locally to save "
            "quota.")
        self.section_caption.setText(
            "Contacting the YouTube Data API…" if searching else "")
        self.section_title.setText(
            f"Searching for “{query}”" if searching else f"Results for “{query}”")
        self._set_api_mode("search")
        if searching:
            self.loading_title.setText("Searching YouTube")
            self.loading_sub.setText(
                "One explicit search uses 100 quota units. Results are "
                "cached so repeating the same search does not spend quota "
                "again.")
            self._show_loading(True)
        else:
            self._show_loading(False)
            self.state_panel.hide()
            self.grid.show()

    def _on_search(self, query: str, items: List[Dict[str, Any]]) -> None:
        self._mode = "search"
        self._search_items = list(items or [])
        self._show_loading(False)
        self._enter_search_mode(query, searching=False)
        self._cards = self._make_cards(self._search_items)
        self.grid.set_cards(self._cards)
        self.grid.show()
        self.section_title.setText(f"Results for “{query}”")
        self.section_caption.setText(
            f"{len(self._search_items)} videos · ordered by relevance")
        self._set_status(
            f"SEARCH · {len(self._search_items)} RESULTS · 100 API UNITS USED")
        if not self._search_items:
            self.grid.hide()
            self._show_state(
                "◎", "No videos found",
                f"YouTube returned no video results for “{query}”. Try a "
                "broader title or a studio name.",
                "Clear search", "Open YouTube")
            self._replace_state_actions(self._clear_search,
                                        self._open_youtube_home)
        else:
            self._hide_notice()

    def _make_cards(self, items: List[Dict[str, Any]]) -> List[VideoCard]:
        cards = []
        for video in items:
            card = VideoCard(video, self.thumbs)
            card.add_requested.connect(self.add_requested)
            card.download_requested.connect(self.download_requested)
            card.open_requested.connect(self.open_requested)
            cards.append(card)
        return cards

    def _on_thumb_loaded(self, key: str, pix) -> None:
        for card in self._cards:
            card.update_asset(key, pix)

    # ---- display state ----------------------------------------------------
    def _show_idle_state(self) -> None:
        self._mode = "idle"
        self._set_busy(False)
        self.clear_btn.hide()
        self.grid.hide()
        self.loading_panel.hide()
        self.notice.hide()
        self._update_search_state()
        self._set_api_mode("idle")
        self.state_panel.show()
        self.eyebrow_label.setText("YOUTUBE · DONGHUA")
        self.subtitle_label.setText(
            "Search YouTube for a donghua, studio, trailer or episode, then "
            "add it to your library.")
        self.section_title.setText("Search YouTube")
        self.section_caption.setText(
            "Nothing loads automatically — search when you are ready.")
        ready = app_config.youtube_ready()
        if ready:
            self._set_status("YOUTUBE SEARCH · READY")
            self._show_state(
                "⌕", "Find something to watch",
                "Search YouTube by title, studio, trailer or episode. "
                "Results can be added straight to your library.",
                "Open YouTube")
            self._replace_state_actions(self._open_youtube_home,
                                        self._open_youtube_home)
        else:
            self._set_status("YOUTUBE SEARCH · API KEY REQUIRED")
            self._show_state(
                "⌘", "Connect YouTube search",
                "Add a YouTube Data API key in Settings to search YouTube. "
                "The key is stored locally and only used for your searches.",
                "Add API key", "Open YouTube", tone="amber")
            self._replace_state_actions(self.connect_requested.emit,
                                        self._open_youtube_home)

    def _set_api_mode(self, mode: str) -> None:
        if mode == "search":
            self._chip("100 API UNITS", T_AMBER2, T_AMBER_SOFT, T_AMBER_LINE)
        elif app_config.youtube_ready():
            self._chip("SEARCH READY", T_EMERALD2, T_EMERALD_SOFT,
                       T_EMERALD_LINE)
        else:
            self._chip("API KEY REQUIRED", T_AMBER2, T_AMBER_SOFT,
                       T_AMBER_LINE)

    def _chip(self, text: str, fg: str, bg: str, border: str) -> None:
        self.api_chip.setText(text)
        self.api_chip.setStyleSheet(
            f"background: {bg}; border: 1px solid {border};"
            f"border-radius: 8px; color: {fg}; font-size: 10px;"
            "font-weight: 700; padding: 2px 8px;")

    def _update_search_state(self) -> None:
        ready = app_config.youtube_ready()
        self.key_btn.setVisible(not ready)
        if ready:
            self.search_btn.setToolTip(
                "Search YouTube (100 API units, cached)")
            self.search_hint.setText(
                "Search uses 100 YouTube API units and is cached for "
                f"{app_config.explore_config().get('cache_minutes', 20)} min.")
            self.search_hint.setStyleSheet(
                f"color: {T_MUTED}; font-size: 10px;")
        else:
            self.search_btn.setToolTip(
                "Add a YouTube Data API key in Settings to search")
            self.search_hint.setText(
                "YouTube search needs a Data API key. Add one in Settings "
                "to enable it.")
            self.search_hint.setStyleSheet(
                f"color: {T_AMBER2}; font-size: 10px;")
        if self._mode == "idle":
            self._set_api_mode("idle")

    # ---- worker plumbing --------------------------------------------------
    def _run(self, fn, on_success, *, loading: bool,
             failure) -> None:
        self._token += 1
        token = self._token
        self._set_busy(True)
        if loading:
            self._show_loading(True)
        self._set_status("CONTACTING YOUTUBE…")

        worker = ExploreWorker(token, fn, self)
        self._worker = worker

        def _done(t: int, result: Any) -> None:
            if self._worker is worker:
                self._worker = None
            worker.deleteLater()
            if t != self._token:
                return
            self._set_busy(False)
            if isinstance(result, Exception):
                failure(result)
                return
            on_success(result)

        worker.result_ready.connect(_done)
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.search_input.setEnabled(not busy)
        self.search_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)

    # ---- states -----------------------------------------------------------
    def _show_loading(self, show: bool) -> None:
        self.loading_panel.setVisible(show)
        if show:
            self.grid.hide()
            self.state_panel.hide()
            self.notice.hide()

    def _show_error(self, exc: Exception) -> None:
        self._show_loading(False)
        self.grid.hide()
        self.state_panel.show()
        if isinstance(exc, youtube_api.YouTubeNotConfigured):
            self._mode = "idle"
            self.clear_btn.hide()
            self._update_search_state()
            self._set_api_mode("idle")
            self.section_title.setText("YouTube search")
            self.section_caption.setText(
                "Add an API key to search all of YouTube.")
            self._set_status("SEARCH NEEDS A YOUTUBE API KEY")
            self._show_state(
                "⌘", "Connect YouTube search",
                "Add a YouTube Data API key in Settings to search YouTube. "
                "The key is stored locally and only used for your searches.",
                "Add API key", "Open YouTube", tone="amber")
            self._replace_state_actions(self.connect_requested.emit,
                                        self._open_youtube_home)
            return
        self._mode = "search"
        self.clear_btn.show()
        if isinstance(exc, youtube_api.YouTubeError):
            summary = str(exc)
            self._last_error = exc.report()
        else:
            summary = "Explore could not load YouTube results."
            self._last_error = traceback.format_exc()
        self.section_title.setText("Search failed")
        self.section_caption.setText(
            f"“{self._last_query}” · retry or clear the search")
        self._set_status("SEARCH ERROR · " + summary)
        self._show_state(
            "⚠", "YouTube is not responding",
            summary, "Retry search", "Clear search", tone="rose")
        self._replace_state_actions(
            lambda: self.search_for(self._last_query), self._clear_search)
        self._show_notice(summary, self._last_error, tone="rose")

    def _show_state(self, glyph: str, title: str, body: str,
                    primary: str = "", secondary: str = "",
                    tone: str = "sky") -> None:
        self.state_panel.show()
        self.state_panel.show_state(glyph, title, body, primary, secondary, tone)

    def _replace_state_actions(self, primary, secondary) -> None:
        for signal, slot in ((self.state_panel.primary, primary),
                             (self.state_panel.secondary, secondary)):
            try:
                signal.disconnect()
            except (TypeError, RuntimeError):
                pass
            signal.connect(slot)

    def _show_notice(self, message: str, details: str,
                     tone: str = "amber") -> None:
        self.notice_lbl.setText(message)
        color = T_ROSE2 if tone == "rose" else T_AMBER2
        self.notice_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._last_error = details
        self.notice.show()

    def _hide_notice(self) -> None:
        self.notice.hide()

    def _set_status(self, text: str) -> None:
        self.status_line.setText(text)

    def _copy_details(self) -> None:
        QApplication.clipboard().setText(
            self._last_error or "No details available.")
        self._show_notice("Error details copied to the clipboard.",
                          self._last_error or "No details available.")

    def _open_youtube_home(self) -> None:
        QDesktopServices.openUrl(QUrl("https://www.youtube.com"))

