"""Explore: YouTube Data API v3 discovery built on the shared config.

Discovery is intentionally quota-friendly: one cheap ``videos.list`` trending
call and one curated ``search.list`` call.  Searches are cached on disk, and
the page keeps partial results when only one rail fails.
"""
import traceback
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QSize, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QScrollArea, QVBoxLayout, QWidget,
)

import app_config
import youtube_api
from ..components.poster_grid import PosterGrid
from ..components.primitives import btn, chip_tag, eyebrow, mk_label
from ..components.video_card import VideoCard
from ..icons import icon
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import (
    F_MONO, T_AMBER2, T_AMBER_LINE, T_AMBER_SOFT, T_MUTED, T_PRIMARY,
    T_ROSE2, T_SEC, T_TEXT,
)

QUICK_SEARCHES = [
    "donghua", "cultivation donghua", "xianxia", "3D donghua",
    "Battle Through the Heavens", "Throne of Seal",
]
CONSOLE_URL = "https://console.cloud.google.com/apis/credentials"


class ExploreWorker(QThread):
    """Run one blocking API call without freezing the UI."""

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
        self.setMinimumHeight(230)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 26, 16, 26)
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
        self.body.setMaximumWidth(500)
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
            "amber": (T_AMBER2, T_AMBER_SOFT, T_AMBER_LINE),
            "rose": (T_ROSE2, "rgba(244,63,94,24)", "rgba(244,63,94,100)"),
        }
        fg, bg, border = tones.get(tone, tones["sky"])
        self.glyph.setText(glyph)
        self.glyph.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border};"
            "border-radius: 26px; font-size: 21px; font-weight: 700;")
        self.title.setText(title)
        self.body.setText(body)
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
        self._loaded = False
        self._rails: List[Dict[str, Any]] = []
        self._cards: List[VideoCard] = []
        self._last_query = ""
        self._last_error = ""
        self._mode = "discover"

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
        content.setContentsMargins(28, 14, 28, 18)
        content.setSpacing(12)

        # ---- heading
        head = QHBoxLayout()
        head.setSpacing(10)
        tl = QVBoxLayout()
        tl.setSpacing(2)
        tl.addWidget(eyebrow("Beyond your library"))
        tl.addWidget(mk_label("Explore", "display"))
        tl.addWidget(mk_label(
            "Discover donghua on YouTube, then save any find straight into a series.",
            "body", "muted"))
        head.addLayout(tl)
        head.addStretch(1)
        self.api_chip = chip_tag("API KEY NEEDED", "amber")
        self.api_chip.setFixedHeight(26)
        head.addWidget(self.api_chip, 0, Qt.AlignmentFlag.AlignTop)
        self.refresh_btn = btn("⟳  Refresh", "ghost",
                               "Fetch fresh results (uses YouTube API quota)",
                               small=True)
        self.refresh_btn.setIcon(icon("rotate", T_SEC, 13))
        self.refresh_btn.setIconSize(QSize(13, 13))
        self.refresh_btn.clicked.connect(lambda: self.refresh(force=True))
        head.addWidget(self.refresh_btn, 0, Qt.AlignmentFlag.AlignTop)
        content.addLayout(head)

        # ---- search
        search_card = QFrame()
        search_card.setObjectName("card")
        sc = QVBoxLayout(search_card)
        sc.setContentsMargins(16, 13, 16, 12)
        sc.setSpacing(9)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("search")
        self.search_input.setPlaceholderText(
            "Search YouTube for a donghua, studio, trailer or episode…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(36)
        self.search_input.returnPressed.connect(self._submit_search)
        row.addWidget(self.search_input, 1)
        search_btn = btn("Search YouTube", "primary",
                         "Run a YouTube Data API search (100 quota units)")
        search_btn.setFixedHeight(36)
        search_btn.setIcon(icon("search", "#002b40", 14))
        search_btn.setIconSize(QSize(14, 14))
        search_btn.clicked.connect(self._submit_search)
        row.addWidget(search_btn)
        back_btn = btn("Discovery", "ghost", "Back to curated rails", small=True)
        back_btn.setFixedHeight(36)
        back_btn.clicked.connect(self._back_to_discovery)
        row.addWidget(back_btn)
        sc.addLayout(row)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(mk_label("TRY", "labelCaps"))
        for text in QUICK_SEARCHES:
            chip = btn(text, "chip", f"Search YouTube for “{text}”", small=True)
            chip.setFixedHeight(26)
            chip.clicked.connect(
                lambda _=False, q=text: self.search_for(q))
            chips.addWidget(chip)
        chips.addStretch(1)
        sc.addLayout(chips)

        self.status_line = QLabel("")
        self.status_line.setStyleSheet(
            f"color: {T_MUTED}; font-family: '{F_MONO}'; font-size: 9px;")
        sc.addWidget(self.status_line)
        content.addWidget(search_card)

        # ---- state panels (loading / onboarding / errors)
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
        load_title = QLabel("Tuning into YouTube")
        load_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        load_title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {T_TEXT};")
        lp.addWidget(load_title)
        load_sub = QLabel(
            "Fetching trending animation and donghua discoveries from the "
            "YouTube Data API. Cached rails return instantly.")
        load_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        load_sub.setWordWrap(True)
        load_sub.setMaximumWidth(480)
        load_sub.setStyleSheet(f"font-size: 12px; color: {T_SEC};")
        lp.addWidget(load_sub, 0, Qt.AlignmentFlag.AlignHCenter)
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedSize(220, 4)
        self.loading_bar.setTextVisible(False)
        lp.addWidget(self.loading_bar, 0, Qt.AlignmentFlag.AlignHCenter)
        content.addWidget(self.loading_panel)

        self.state_panel = StatePanel()
        self.state_panel.primary.connect(self.connect_requested.emit)
        content.addWidget(self.state_panel)

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

        # ---- rails
        self.rails_host = QWidget()
        self.rails_layout = QVBoxLayout(self.rails_host)
        self.rails_layout.setContentsMargins(0, 0, 0, 0)
        self.rails_layout.setSpacing(16)
        content.addWidget(self.rails_host)
        content.addStretch(1)

        self.page_scroll.setWidget(host)
        root.addWidget(self.page_scroll)

        self._show_loading(False)
        self._show_not_configured()

    # ---- public API -------------------------------------------------------
    def ensure_loaded(self) -> None:
        """Called when navigation lands on Explore."""
        if not app_config.youtube_ready():
            self._loaded = False
            self._show_not_configured()
            return
        self._update_api_chip()
        if not self._loaded and not self._busy:
            self.refresh()

    def reload_credentials(self) -> None:
        """Settings saved a new key/region; make the next visit refetch."""
        self._loaded = False
        self._update_api_chip()
        if self.isVisible():
            self.ensure_loaded()

    def refresh(self, force: bool = False) -> None:
        if self._busy:
            return
        if not app_config.youtube_ready():
            self._show_not_configured()
            return
        self._mode = "discover"
        self._last_query = ""
        self._run(
            lambda client: youtube_api.discover(client, refresh=force),
            self._on_discovery)

    def search_for(self, query: str) -> None:
        text = str(query or "").strip()
        if not text:
            return
        self.search_input.setText(text)
        self._submit_search()

    def shutdown(self, wait_ms: int = 2000) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(wait_ms)

    # ---- search / load ----------------------------------------------------
    def _submit_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self._back_to_discovery()
            return
        if self._busy:
            return
        if not app_config.youtube_ready():
            self._show_not_configured()
            return
        self._mode = "search"
        self._last_query = query
        limit = int(app_config.explore_config().get("result_limit") or 18)
        self._run(
            lambda client: client.search(query, max_results=limit),
            lambda items: self._on_search(query, items))

    def _back_to_discovery(self) -> None:
        if self._busy:
            return
        self.search_input.clear()
        if self._mode != "discover":
            self._mode = "discover"
            self._last_query = ""
            self.refresh()

    def _run(self, fn, on_success) -> None:
        self._token += 1
        token = self._token
        client = youtube_api.YouTubeClient()
        self._set_busy(True)
        self._show_loading(True)
        self._update_status("Contacting the YouTube Data API…")

        worker = ExploreWorker(token, lambda: fn(client), self)
        self._worker = worker

        def _done(t: int, result: Any) -> None:
            if self._worker is worker:
                self._worker = None
            worker.deleteLater()
            if t != self._token:
                return
            self._set_busy(False)
            if isinstance(result, Exception):
                self._show_error(result)
                return
            on_success(result)

        worker.result_ready.connect(_done)
        worker.start()

    def _on_discovery(self, data: Dict[str, Any]) -> None:
        rails = list(data.get("rails") or [])
        errors = list(data.get("errors") or [])
        self._loaded = True
        self._mode = "discover"
        self._render_rails(rails)
        if errors:
            self._show_notice(
                "Some rails could not load. Trending remains available.",
                "\n\n".join(errors))
        else:
            self._hide_notice()
        total = sum(len(r.get("items") or []) for r in rails)
        self._update_status(
            f"YOUTUBE DATA API v3  ·  {len(rails)} rail(s)  ·  {total} videos  ·  "
            f"cached {app_config.explore_config().get('cache_minutes', 20)} min")
        self._update_api_chip()

    def _on_search(self, query: str, items: List[Dict[str, Any]]) -> None:
        self._loaded = True
        self._mode = "search"
        rail = {
            "key": "search",
            "title": f"Results for “{query}”",
            "caption": f"{len(items)} videos · ordered by relevance",
            "items": list(items),
        }
        self._render_rails([rail] if items else [])
        if items:
            self._hide_notice()
            self._update_status(
                f"SEARCH  ·  {len(items)} results  ·  cached "
                f"{app_config.explore_config().get('cache_minutes', 20)} min")
        else:
            self._show_state(
                "◎", "No videos found",
                f"YouTube returned no video results for “{query}”. Try a "
                "broader title, a studio name, or the Discovery rails.",
                "Back to discovery", "Open YouTube")
        self._update_api_chip()

    # ---- render -----------------------------------------------------------
    def _render_rails(self, rails: List[Dict[str, Any]]) -> None:
        self._clear_rails()
        self._rails = list(rails)
        self._show_loading(False)
        self.state_panel.hide()
        if not rails:
            self._show_state(
                "◎", "Nothing to show yet",
                "The API returned no videos. Try refreshing or a different search.",
                "Refresh", "Open YouTube")
            self.rails_host.hide()
            return
        self.rails_host.show()
        for rail in rails:
            section = QWidget()
            sl = QVBoxLayout(section)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(8)
            head = QHBoxLayout()
            head.setSpacing(8)
            title_col = QVBoxLayout()
            title_col.setSpacing(1)
            title_col.addWidget(mk_label(rail.get("title", "YouTube"), "titleLg"))
            caption = str(rail.get("caption") or "")
            if caption:
                title_col.addWidget(mk_label(caption, "small", "muted"))
            head.addLayout(title_col)
            head.addStretch(1)
            count = len(rail.get("items") or [])
            head.addWidget(chip_tag(f"{count} VIDEOS", "sky"))
            sl.addLayout(head)

            grid = PosterGrid()
            cards = []
            for video in rail.get("items") or []:
                card = VideoCard(video, self.thumbs)
                card.add_requested.connect(self.add_requested)
                card.download_requested.connect(self.download_requested)
                card.open_requested.connect(self.open_requested)
                cards.append(card)
            self._cards.extend(cards)
            grid.set_items(cards)
            sl.addWidget(grid)
            self.rails_layout.addWidget(section)

    def _clear_rails(self) -> None:
        self._cards = []
        while self.rails_layout.count():
            item = self.rails_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _on_thumb_loaded(self, key: str, pix) -> None:
        for card in self._cards:
            card.update_poster(key, pix)

    # ---- states -----------------------------------------------------------
    def _show_loading(self, busy: bool) -> None:
        self.loading_panel.setVisible(busy)
        if busy:
            self.rails_host.hide()
            self.state_panel.hide()
            self._hide_notice()

    def _show_not_configured(self) -> None:
        self._clear_rails()
        self._rails = []
        self._show_loading(False)
        self.rails_host.hide()
        self.notice.hide()
        self.state_panel.show()
        self.state_panel.show_state(
            "⌘", "Connect YouTube",
            "Explore uses the YouTube Data API v3. Add a Google Cloud API key "
            "to the shared config file once; the GUI and CLI will both use it.",
            "Connect YouTube", "Get an API key", "amber")
        self._replace_state_actions(self.connect_requested.emit,
                                    self._open_console)
        self._update_status("YOUTUBE API KEY MISSING  ·  " + app_config.display_path())
        self._set_busy(False)
        self._update_api_chip()

    def _show_error(self, exc: Exception) -> None:
        self._show_loading(False)
        self._clear_rails()
        self.rails_host.hide()
        self.state_panel.show()
        if isinstance(exc, youtube_api.YouTubeNotConfigured):
            self._show_not_configured()
            return
        if isinstance(exc, youtube_api.YouTubeError):
            summary = str(exc)
            self._last_error = exc.report()
        else:
            summary = "Explore could not load YouTube results."
            self._last_error = traceback.format_exc()
        self.state_panel.show_state(
            "⚠", "YouTube is not responding", summary,
            "Retry", "Copy details", "rose")
        self._replace_state_actions(
            lambda: self.refresh(force=True), self._copy_details)
        self._update_status("EXPLORE ERROR  ·  " + summary)
        self._update_api_chip()
        self._show_notice(summary, self._last_error, tone="rose")

    def _show_state(self, glyph: str, title: str, body: str,
                    primary: str = "", secondary: str = "") -> None:
        self._clear_rails()
        self._show_loading(False)
        self.rails_host.hide()
        self.state_panel.show()
        self.state_panel.show_state(glyph, title, body, primary, secondary)
        if primary.lower().startswith("back"):
            self._replace_state_actions(self._back_to_discovery,
                                        self._open_youtube_home)
        elif primary.lower().startswith("refresh"):
            self._replace_state_actions(
                lambda: self.refresh(force=True), self._open_youtube_home)
        else:
            self._replace_state_actions(self._open_youtube_home,
                                        self._copy_details)

    def _replace_state_actions(self, primary, secondary) -> None:
        for signal, slot in ((self.state_panel.primary, primary),
                             (self.state_panel.secondary, secondary)):
            try:
                signal.disconnect()
            except (TypeError, RuntimeError):
                pass
            signal.connect(slot)

    def _update_api_chip(self) -> None:
        if app_config.youtube_ready():
            self.api_chip.setText("YOUTUBE DATA API v3")
            self.api_chip.setStyleSheet(
                "background: rgba(56,189,248,28);"
                "border: 1px solid rgba(56,189,248,110); border-radius: 8px;"
                f"color: {T_PRIMARY}; font-size: 10px; font-weight: 700;"
                "padding: 2px 8px;")
        else:
            self.api_chip.setText("API KEY NEEDED")
            self.api_chip.setStyleSheet(
                f"background: {T_AMBER_SOFT}; border: 1px solid {T_AMBER_LINE};"
                f"border-radius: 8px; color: {T_AMBER2}; font-size: 10px;"
                "font-weight: 700; padding: 2px 8px;")

    def _show_notice(self, message: str, details: str,
                     tone: str = "amber") -> None:
        self.notice_lbl.setText(message)
        color = T_ROSE2 if tone == "rose" else T_AMBER2
        self.notice_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._last_error = details
        self.notice.show()

    def _hide_notice(self) -> None:
        self.notice.hide()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.refresh_btn.setEnabled(not busy)
        self.search_input.setEnabled(not busy)

    def _update_status(self, text: str) -> None:
        self.status_line.setText(text)

    def _copy_details(self) -> None:
        QApplication.clipboard().setText(self._last_error or "No details available.")
        self._show_notice("Error details copied to the clipboard.",
                          self._last_error or "No details available.")

    def _open_console(self) -> None:
        QDesktopServices.openUrl(QUrl(CONSOLE_URL))

    def _open_youtube_home(self) -> None:
        QDesktopServices.openUrl(QUrl("https://www.youtube.com"))
