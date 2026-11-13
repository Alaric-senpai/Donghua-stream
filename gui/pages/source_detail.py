"""SourceDetailView — full detail page for an AnimeCube or DonghuaStream series.

Mirrors SeriesDetailView's layout language but reads from sources.py instead of
PostgreSQL.  Episodes can be checked and added to the library via
prompt_source_episodes.
"""
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import db
import sources
from media_ids import extract_video_id
from ..components.primitives import (
    btn, chip_tag, eyebrow, mk_label,
)
from ..components.source_card import SourceSeriesCard
from ..components.stack_list import StackList
from ..components.thumb import PosterThumb
from ..dialogs.source_episodes import prompt_source_episodes
from ..icons import icon
from ..infrastructure.thumbnails import ThumbnailStore
from ..theme import (
    T_AMBER2, T_AMBER_LINE, T_AMBER_SOFT, T_MUTED, T_ON_PRIMARY, T_PRIMARY,
    T_PRIMARY_LINE, T_PRIMARY_SOFT, T_TEXT,
)


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
        except Exception as exc:
            result = exc
        self.result_ready.emit(self._token, result)


class _SrcEpisodeRow(QFrame):
    """Single episode checkbox row used in the SourceDetailView registry."""

    def __init__(self, episode: Dict[str, Any], checked: bool = True,
                 already_registered: bool = False,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ep = episode
        self.setObjectName("episodeRow")
        self.setFixedHeight(56)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        self.check = QCheckBox()
        self.check.setChecked(checked)
        self.check.setFixedSize(28, 26)
        lay.addWidget(self.check, 0, Qt.AlignmentFlag.AlignCenter)

        num = episode.get("episode_number") or 0
        numlab = QLabel(f"#{int(num):03d}" if isinstance(num, int) else "#000")
        numlab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        numlab.setFixedSize(48, 26)
        numlab.setStyleSheet(
            f"color: {T_MUTED}; background: rgba(51,65,85,65);"
            "border-radius: 6px; font-family: 'Fira Code'; font-size: 10px;"
        )
        lay.addWidget(numlab)

        title_text = episode.get("title") or episode.get("url") or ""
        title = QLabel(title_text)
        title.setStyleSheet(f"color: {T_TEXT}; font-weight: 600; font-size: 13px;")
        title.setToolTip(episode.get("url") or "")
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(title, 1)

        # Status indicator
        if already_registered:
            lay.addWidget(chip_tag("IN LIBRARY", "amber"))
        else:
            lay.addWidget(chip_tag("NEW", "sky"))


class SourceDetailView(QWidget):
    """Full series detail for a source (AnimeCube / DonghuaStream) series."""

    toast = pyqtSignal(str, bool)
    series_selected = pyqtSignal(str, dict)   # source_key, series_data
    # series_id, urls — emitted when the add flow opted into immediate download
    download_requested = pyqtSignal(int, list)
    # series_id — emitted after the library changed, so the window refreshes
    library_changed = pyqtSignal(int)

    def __init__(self, thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs
        self._source_key = ""
        self._series_url = ""
        self._details: Dict[str, Any] = {}
        self._registered_ids: set = set()   # video_ids already in library
        self._busy = False
        self._checkboxes: List[tuple[QCheckBox, Dict[str, Any]]] = []
        self._workers: List[ExploreWorker] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # One scroll area for the whole page: the episode list takes the room
        # it needs and the recommendations follow underneath it.
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        content = QVBoxLayout(host)
        content.setContentsMargins(28, 14, 28, 24)
        content.setSpacing(16)

        # ---- hero info card
        self._build_hero_card(content)

        # ---- episode registry section
        self._build_registry_section(content)

        # ---- recommendations rail
        self._build_recommendations_rail(content)

        content.addStretch(1)
        self.page_scroll.setWidget(host)
        root.addWidget(self.page_scroll)

    # ---- hero card ------------------------------------------------------------
    def _build_hero_card(self, root: QVBoxLayout) -> None:
        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        cl = QHBoxLayout(card)
        cl.setContentsMargins(18, 18, 18, 18)
        cl.setSpacing(18)

        self.poster = PosterThumb(self.thumbs, "", radius=12)
        self.poster.setFixedSize(232, 145)
        cl.addWidget(self.poster, 0, Qt.AlignmentFlag.AlignTop)

        mid = QVBoxLayout()
        mid.setSpacing(4)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        self.chip_status = chip_tag("", "sky")
        self.chip_eps = chip_tag("0 EPS", "sky")
        self.chip_quality = chip_tag("", "default")
        chip_row.addWidget(self.chip_status)
        chip_row.addWidget(self.chip_eps)
        chip_row.addWidget(self.chip_quality)
        chip_row.addStretch(1)
        mid.addLayout(chip_row)

        self.title = mk_label("—", "titleXl")
        mid.addWidget(self.title)

        self.sub = mk_label("", "body", "muted")
        mid.addWidget(self.sub)

        self.synopsis = mk_label("", "body")
        self.synopsis.setWordWrap(True)
        self.synopsis.setMaximumHeight(54)
        mid.addWidget(self.synopsis)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.add_full_btn = btn("Add Series", "primary")
        self.add_full_btn.setIcon(icon("plus", T_ON_PRIMARY, 13))
        self.add_full_btn.setIconSize(QSize(13, 13))
        # One button, two ways in: attach to an existing library series or
        # create a brand-new one from scratch.
        self.add_menu = QMenu(self.add_full_btn)
        self._act_existing = self.add_menu.addAction(
            "Add to an existing series…")
        self._act_new = self.add_menu.addAction(
            "Create a new series and add it…")
        self._act_existing.triggered.connect(
            lambda: self._add_series("existing"))
        self._act_new.triggered.connect(lambda: self._add_series("new"))
        self.add_full_btn.setMenu(self.add_menu)
        btn_row.addWidget(self.add_full_btn)

        self.add_sel_btn = btn("Add Selected Episodes…", "ghost")
        self.add_sel_btn.setToolTip(
            "Register only the checked episodes of this series")
        self.add_sel_btn.clicked.connect(self._add_selected)
        btn_row.addWidget(self.add_sel_btn)

        self.open_src_btn = btn("Open Source", "ghost")
        self.open_src_btn.setObjectName("link")
        self.open_src_btn.clicked.connect(self._open_source)
        btn_row.addWidget(self.open_src_btn)

        mid.addLayout(btn_row)
        cl.addLayout(mid, 1)
        root.addWidget(card)

    # ---- episode registry -----------------------------------------------------
    def _build_registry_section(self, root: QVBoxLayout) -> None:
        reg_head = QHBoxLayout()
        reg_head.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(eyebrow("Episode registry"))
        self.reg_count = mk_label("", "small")
        title_col.addWidget(self.reg_count)
        reg_head.addLayout(title_col)
        reg_head.addSpacing(12)

        for text, tip, handler in (
                ("All", "Select every episode", self._check_all),
                ("None", "Clear the selection", self._check_none),
                ("Latest", "Select only the newest episode", self._check_latest),
        ):
            b = btn(text, "chip", tip, small=True)
            b.setFixedHeight(30)
            b.clicked.connect(handler)
            reg_head.addWidget(b)

        reg_head.addStretch(1)

        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Filter episodes…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(32)
        self.search.setFixedWidth(230)
        self.search.textChanged.connect(self._render_rows)
        reg_head.addWidget(self.search)
        root.addLayout(reg_head)

        # The list grows to fit every episode; the page itself scrolls.
        self.rows_host = StackList(spacing=6)
        self.rows_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        root.addWidget(self.rows_host)

    # ---- recommendations rail -------------------------------------------------
    def _build_recommendations_rail(self, root: QVBoxLayout) -> None:
        rail = QFrame()
        rail.setObjectName("card")
        rail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(8)

        self.rec_eyebrow = eyebrow("RECOMMENDED")
        rl.addWidget(self.rec_eyebrow)

        self.rec_scroll = QScrollArea()
        self.rec_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.rec_scroll.setWidgetResizable(True)
        self.rec_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.rec_scroll.setFixedHeight(214)
        self.rec_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        rec_host = QWidget()
        rec_host.setObjectName("scrollHost")
        self.rec_layout = QHBoxLayout(rec_host)
        self.rec_layout.setContentsMargins(0, 0, 0, 0)
        self.rec_layout.setSpacing(12)
        self.rec_layout.addStretch(1)
        self.rec_scroll.setWidget(rec_host)
        rl.addWidget(self.rec_scroll)

        root.addWidget(rail)

    # ---- public loading API ---------------------------------------------------
    def load(self, source_key: str, series_url: str) -> None:
        """Fetch series details and catalog in parallel, then populate UI."""
        self._source_key = str(source_key or "")
        self._series_url = str(series_url or "")
        self._details = {}
        self._catalog = []
        self._registered_ids = set()

        source = sources.SOURCES.get(self._source_key)
        if not source:
            self.toast.emit(f"Unknown source: {self._source_key}", False)
            return

        self._busy = True
        self.title.setText("Loading…")
        self.sub.setText(self._series_url)
        self.synopsis.setText("")
        self.reg_count.setText("")

        worker = ExploreWorker(1, lambda: source.details(self._series_url),
                               self)
        self._workers = [worker]
        worker.result_ready.connect(self._on_worker_done)
        worker.start()

    def _on_worker_done(self, token: int, result: Any) -> None:
        self._busy = False
        if isinstance(result, Exception):
            self.title.setText("Could not load this series")
            self.sub.setText(self._series_url)
            self.synopsis.setText(str(result))
            self.toast.emit(f"Could not load series: {result}", False)
            return

        self._details = dict(result or {})
        self._populate()

    def _populate(self) -> None:
        d = self._details
        if not d:
            return

        # Poster / thumbnail (remote URL, cached on disk)
        url = str(d.get("thumbnail") or "").strip()
        key = f"srcdetail:{d.get('id') or url}"
        if url:
            pix = self.thumbs.get_url(key, url)
            if pix and not pix.isNull():
                self.poster.set_poster(pix)
            else:
                def _on_pix(loaded_key, loaded_pix):
                    if loaded_key == key:
                        try:
                            self.thumbs.loaded.disconnect(_on_pix)
                        except TypeError:
                            pass
                        self.poster.set_poster(loaded_pix)
                self.thumbs.loaded.connect(_on_pix)

        # Chips
        ep_count = int(d.get("episode_count") or 0)
        self.chip_eps.setText(f"{ep_count} EPS")

        status_text = str(d.get("status") or "SOURCE").upper()
        self.chip_status.setText(status_text)
        self._set_status_tone("sky")

        quality = str(d.get("quality") or "").strip()
        if quality:
            self.chip_quality.setText(quality)
            self.chip_quality.setVisible(True)
        else:
            self.chip_quality.setVisible(False)

        # Title / sub / synopsis
        self.title.setText(d.get("title") or "—")

        source_url = str(d.get("url") or "").strip()
        year = str(d.get("year") or "").strip()
        genres = ", ".join(d.get("genres") or []) or ""
        bits = [source_url, year, genres]
        self.sub.setText("  ·  ".join(b for b in bits if b))

        self.synopsis.setText(d.get("description") or "")

        # Episode registry
        episodes = sorted(
            list(d.get("episodes") or []),
            key=lambda ep: (ep.get("episode_number") or 0, ep.get("id") or ""),
        )

        # Check which episodes are already registered
        video_ids = []
        ep_video_map: Dict[str, Dict[str, Any]] = {}
        for ep in episodes:
            vid = extract_video_id(str(ep.get("url") or ""))
            if vid:
                ep["video_id"] = vid
                video_ids.append(vid)
                ep_video_map[vid] = ep

        registered_eps = db.get_episodes_by_ids(video_ids) if video_ids else []
        self._registered_ids = {str(ep.get("video_id") or "") for ep in registered_eps}

        self._episodes = episodes
        self._ep_video_map = ep_video_map
        self._render_rows()

        # Count label
        self.reg_count.setText(f"{len(episodes)} episodes")

        # Recommendations: pick 6 items from catalog excluding current series
        self._load_recommendations()

        # Open source button
        if source_url:
            self.open_src_btn.setVisible(True)
        else:
            self.open_src_btn.setVisible(False)

    def _set_status_tone(self, tone: str) -> None:
        tones = {
            "emerald": (T_PRIMARY_SOFT, T_PRIMARY_LINE, T_PRIMARY),
            "amber": (T_AMBER_SOFT, T_AMBER_LINE, T_AMBER2),
            "sky": (T_PRIMARY_SOFT, T_PRIMARY_LINE, T_PRIMARY),
        }
        bg, line, fg = tones.get(tone, tones["sky"])
        self.chip_status.setStyleSheet(
            f"background: {bg}; border: 1px solid {line}; border-radius: 8px;"
            f"color: {fg}; font-size: 10px; font-weight: 700; padding: 2px 8px;"
        )

    def _render_rows(self) -> None:
        text = (self.search.text() or "").strip().lower()
        rows = []
        for ep in self._episodes:
            if text and text not in (ep.get("title") or "").lower() \
                    and text not in (ep.get("url") or "").lower():
                continue

            vid = str(ep.get("video_id") or extract_video_id(
                str(ep.get("url") or "")))
            already_reg = vid in self._registered_ids
            row = _SrcEpisodeRow(ep, checked=True, already_registered=already_reg)
            rows.append(row)

        self.rows_host.set_items(rows)
        self._checkboxes = [
            (row.check, row.ep)
            for row in rows
            if hasattr(row, 'check')
        ]

    def _load_recommendations(self) -> None:
        # Clear existing tiles (keep the trailing stretch)
        while self.rec_layout.count() > 1:
            item = self.rec_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        d = self._details
        candidates = list(d.get("recommendations") or [])
        label = f"RECOMMENDED  ·  {self._source_key.upper()}"
        self.rec_eyebrow.setText(label)

        if not candidates:
            note = QLabel("No recommendations available for this series yet.")
            note.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
            self.rec_layout.insertWidget(0, note)
            return

        current_source = self._source_key
        for item in candidates[:6]:
            card = SourceSeriesCard(item, self.thumbs)
            card.selected.connect(
                lambda data, k=current_source:
                    self.series_selected.emit(k, dict(data or {})))
            self.rec_layout.insertWidget(
                self.rec_layout.count() - 1, card)

    # ---- checkbox helpers -----------------------------------------------------
    def _check_all(self) -> None:
        for row in self.rows_host.items:
            if hasattr(row, 'check'):
                row.check.blockSignals(True)
                row.check.setChecked(True)
                row.check.blockSignals(False)

    def _check_none(self) -> None:
        for row in self.rows_host.items:
            if hasattr(row, 'check'):
                row.check.blockSignals(True)
                row.check.setChecked(False)
                row.check.blockSignals(False)

    def _check_latest(self) -> None:
        latest_num = 0
        for row in self.rows_host.items:
            ep = getattr(row, 'ep', {})
            num = int(ep.get("episode_number") or 0)
            if num > latest_num:
                latest_num = num
        for row in self.rows_host.items:
            if hasattr(row, 'check'):
                ep = getattr(row, 'ep', {})
                num = int(ep.get("episode_number") or 0)
                row.check.blockSignals(True)
                row.check.setChecked(num == latest_num)
                row.check.blockSignals(False)

    def _selected_episodes(self) -> List[Dict[str, Any]]:
        result = []
        for row in self.rows_host.items:
            if hasattr(row, 'check') and row.check.isChecked():
                ep = getattr(row, 'ep', {})
                if ep:
                    result.append(dict(ep))
        return result

    # ---- action handlers ------------------------------------------------------
    def _add_series(self, target_mode: str = "existing") -> None:
        """Add every episode of the show to the library.

        ``target_mode`` decides how the dialog starts: on an existing library
        series, or on the "create a new series" entry.
        """
        if not self._details:
            return
        chosen = list(self._details.get("episodes") or [])
        if not chosen:
            self.toast.emit("No episodes found on this source page.", False)
            return
        self._open_dialog(chosen, target_mode=target_mode)

    def _add_selected(self) -> None:
        chosen = self._selected_episodes()
        if not chosen:
            self.toast.emit("No episodes selected.", False)
            return
        self._open_dialog(chosen, target_mode="any")

    def _open_dialog(self, episodes: List[Dict[str, Any]],
                     target_mode: str = "any") -> None:
        details = dict(self._details)
        details["episodes"] = episodes

        payload = prompt_source_episodes(details, self._get_library_series(),
                                         download_now=False,
                                         target_mode=target_mode, parent=self)
        if not payload:
            return

        self._save_payload(payload)

    def _save_payload(self, payload: Dict[str, Any]) -> None:
        sid = payload.get("series_id")
        episodes = list(payload.get("episodes") or [])
        if not episodes:
            self.toast.emit("No episodes were selected.", False)
            return

        try:
            if sid:
                series_id = int(sid)
            else:
                source_label = str(
                    self._details.get("channel") or self._details.get("source") or
                    "Source").strip()
                description = (
                    f"{source_label} series · "
                    f"{self._details.get('url') or ''}"
                ).strip()
                created = db.create_series(
                    payload.get("new_name") or self._details.get("title")
                    or "New Donghua",
                    description=description,
                )
                series_id = int(created["id"])

            stats = db.add_episode_entries(series_id, episodes)
            added = int((stats or {}).get("added", 0) or 0)
            updated = int((stats or {}).get("updated", 0) or 0)
            message = f"Added {added} episode(s)."
            if updated:
                message = f"Added {added} and refreshed {updated} episode(s)."
            if payload.get("download_now"):
                urls = [str(ep.get("url") or "").strip()
                        for ep in episodes if ep.get("url")]
                if urls:
                    self.download_requested.emit(series_id, urls)
                    message = f"Queued {len(urls)} episode(s) for download."
            self.toast.emit(message, True)
            # The library changed: let the window reload Home/Library so the
            # new series (or the updated one) shows up immediately.
            self.library_changed.emit(series_id)

            # Refresh registration indicators
            video_ids = [extract_video_id(str(ep.get("url") or ""))
                         for ep in episodes if ep.get("url")]
            registered = db.get_episodes_by_ids(video_ids)
            self._registered_ids = {str(ep.get("video_id") or "") for ep in registered}
            self._render_rows()

        except Exception as exc:
            self.toast.emit(f"Could not save: {exc}", False)

    def _get_library_series(self) -> List[Dict[str, Any]]:
        try:
            return db.get_all_series()
        except Exception:
            return []

    # ---- lifecycle -----------------------------------------------------------
    def shutdown(self) -> None:
        for worker in list(self._workers):
            try:
                if not worker.isRunning():
                    continue
                worker.requestInterruption()
                if not worker.wait(1500):
                    worker.terminate()
                    worker.wait(500)
            except RuntimeError:
                pass
        self._workers = []

    def _open_source(self) -> None:
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        url = str(self._details.get("url") or "").strip()
        if url:
            QDesktopServices.openUrl(QUrl(url))
