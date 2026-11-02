"""Home: hero spotlight, telemetry strip, filters, poster catalog."""
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QHBoxLayout, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from ..components.hero import HeroSpotlight
from ..components.poster_grid import PosterGrid
from ..components.primitives import btn, mk_label
from ..components.series_cards import CompactSeriesRow, SeriesCard
from ..components.telemetry import TelemetryStrip
from ..infrastructure.thumbnails import ThumbnailStore
from ..utils import pct


class HomeView(QWidget):
    series_opened = pyqtSignal(int)
    series_download_all = pyqtSignal(int)
    series_folder = pyqtSignal(int)
    series_delete = pyqtSignal(int)
    add_requested = pyqtSignal()
    sync_requested = pyqtSignal()

    FILTERS = [("all", "All"), ("progress", "In Progress"),
               ("complete", "Complete"), ("new", "Not Started")]

    def __init__(self, thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs
        self._posters: Dict[int, str] = {}
        self._all: List[Dict[str, Any]] = []
        self._sizes: Dict[int, int] = {}
        self._filter = "all"
        self._query = ""
        self._sort = "title"
        self._list_mode = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 12, 28, 16)
        root.setSpacing(12)

        # ---- page heading + view switcher
        head = QHBoxLayout()
        tl = QVBoxLayout()
        tl.addWidget(mk_label("Donghua Library", "titleLg"))
        tl.addWidget(mk_label("Your entire donghua catalog, spotlighted like a TV streaming app.",
                              "body", "muted"))
        head.addLayout(tl)
        head.addStretch(1)
        self.grid_toggle = btn("▦  Grid", "chip", "Poster grid view")
        self.list_toggle = btn("☰  List", "chip", "Compact list view")
        self.grid_toggle.setCheckable(True)
        self.list_toggle.setCheckable(True)
        self.grid_toggle.setChecked(True)
        self.grid_toggle.clicked.connect(lambda: self.set_mode(False))
        self.list_toggle.clicked.connect(lambda: self.set_mode(True))
        head.addWidget(self.grid_toggle)
        head.addWidget(self.list_toggle)
        addb = btn("＋  Add Donghua", "primary", "Open the registration wizard")
        addb.clicked.connect(self.add_requested.emit)
        head.addWidget(addb)
        root.addLayout(head)

        self.hero = HeroSpotlight()
        self.hero.download_all.connect(self.series_download_all)
        self.hero.verify_disk.connect(self._verify)
        root.addWidget(self.hero)

        self.telemetry = TelemetryStrip()
        self.telemetry.sync_requested.connect(self.sync_requested.emit)
        root.addWidget(self.telemetry)

        # ---- filter tab chips + quick filter + sort
        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self.tab_buttons: Dict[str, QPushButton] = {}
        for key, name in self.FILTERS:
            b = QPushButton(name)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(key == "all")
            self._tab_group.addButton(b)
            b.clicked.connect(lambda _=False, k=key: self.set_filter(k))
            self.tab_buttons[key] = b
            tabs.addWidget(b)
        self._count_labels: Dict[str, str] = {}

        tabs.addSpacing(8)
        self.quick = QLineEdit()
        self.quick.setPlaceholderText("Quick filter…")
        self.quick.setFixedWidth(200)
        self.quick.textChanged.connect(self._on_quick)
        tabs.addWidget(self.quick, 1)
        self.sort_box = QComboBox()
        self.sort_box.setObjectName("chip")
        self.sort_box.addItems(["Title A→Z", "Most Episodes", "Most Downloaded", "Largest Disk"])
        self.sort_box.setFixedHeight(30)
        self.sort_box.currentIndexChanged.connect(self._on_sort)
        tabs.addWidget(self.sort_box)
        holder = QWidget()
        holder.setLayout(tabs)
        root.addWidget(holder)

        # ---- scrollable content
        self.stack_area = QScrollArea()
        self.stack_area.setWidgetResizable(True)
        self.stack_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        self._host_lay = QVBoxLayout(host)
        self._host_lay.setContentsMargins(0, 4, 4, 0)
        self._host_lay.setSpacing(14)
        self.grid_host = PosterGrid()
        self.list_host = PosterGrid()
        self.list_host.hide()
        self._host_lay.addWidget(self.grid_host)
        self._host_lay.addWidget(self.list_host)
        self._host_lay.addStretch(1)
        self.empty = mk_label("No series match this filter.", "body", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._host_lay.addWidget(self.empty)
        self.stack_area.setWidget(host)
        root.addWidget(self.stack_area, 1)

    # ---- mode / filter plumbing -------------------------------------------
    def set_mode(self, list_mode: bool) -> None:
        self._list_mode = list_mode
        self.grid_toggle.setChecked(not list_mode)
        self.list_toggle.setChecked(list_mode)
        self.grid_host.setVisible(not list_mode)
        self.list_host.setVisible(list_mode)
        self._rebuild()

    def set_filter(self, key: str) -> None:
        self._filter = key
        self._rebuild()

    def _on_quick(self, text: str) -> None:
        self._query = text.strip().lower()
        self._rebuild()

    def _on_sort(self, idx: int) -> None:
        self._sort = ["title", "episodes", "downloaded", "disk"][max(0, idx)]
        self._rebuild()

    def _verify(self, sid: int) -> None:
        self.sync_requested.emit()

    # ---- data ---------------------------------------------------------------
    def update_poster(self, vid: str, pix: QPixmap) -> None:
        for w in (*self.grid_host._items, *self.list_host._items):
            pw = getattr(w, "poster", None) or w
            if getattr(pw, "vid", "") == vid:
                pw.set_poster(pix)

    def update_sizes(self, sizes: Dict[int, int]) -> None:
        self._sizes.update(sizes)
        for w in (*self.grid_host._items, *self.list_host._items):
            data = getattr(w, "series", None)
            if data and data["id"] in sizes:
                w.set_disk_size(sizes[data["id"]])

    def load(self, series_list: List[Dict[str, Any]], posters: Dict[int, str]) -> None:
        self._all = series_list
        self._posters = posters
        counts = {"all": len(series_list), "progress": 0, "complete": 0, "new": 0}
        for s in series_list:
            tot = int(s.get("total_episodes", 0) or 0)
            done = int(s.get("downloaded_episodes", 0) or 0)
            if tot and done >= tot:
                counts["complete"] += 1
            elif done:
                counts["progress"] += 1
            else:
                counts["new"] += 1
        for key, b in self.tab_buttons.items():
            b.setText(f"{self.FILTERS[[k for k, _ in self.FILTERS].index(key)][1]} ({counts.get(key, 0)})")
        hero_src = (series_list or [{}])[0]
        self.hero.set_series(hero_src, posters.get(hero_src.get("id", 0), ""), self.thumbs)
        total_eps = sum(int(s.get("total_episodes", 0) or 0) for s in series_list)
        total_done = sum(int(s.get("downloaded_episodes", 0) or 0) for s in series_list)
        self.telemetry.set_counts(len(series_list), len(series_list))
        self.telemetry.disk_chip.setText(
            f"{total_done} of {total_eps} episodes on disk ({pct(total_done, total_eps)}%)")
        self._rebuild()

    def _filtered(self) -> List[Dict[str, Any]]:
        out = []
        for s in self._all:
            tot = int(s.get("total_episodes", 0) or 0)
            done = int(s.get("downloaded_episodes", 0) or 0)
            if self._filter == "complete" and not (tot and done >= tot):
                continue
            if self._filter == "progress" and not (0 < done < tot):
                continue
            if self._filter == "new" and done:
                continue
            if self._query and self._query not in s.get("name", "").lower():
                continue
            out.append(s)
        keymap = {
            "title": lambda s: s.get("name", "").lower(),
            "episodes": lambda s: -int(s.get("total_episodes", 0) or 0),
            "downloaded": lambda s: -int(s.get("downloaded_episodes", 0) or 0),
            "disk": lambda s: -self._sizes.get(s["id"], 0),
        }
        out.sort(key=keymap.get(self._sort, keymap["title"]))
        return out

    def _rebuild(self) -> None:
        data = self._filtered()
        if self._list_mode:
            self.grid_host.set_items([])
            rows = []
            for s in data:
                r = CompactSeriesRow(s, self._posters, self.thumbs)
                r.clicked.connect(self.series_opened)
                r.download_next.connect(self.series_download_all)
                r.open_folder.connect(self.series_folder)
                r.delete_requested.connect(self.series_delete)
                rows.append(r)
            self.list_host.set_items(rows)
            items = rows
        else:
            self.list_host.set_items([])
            cards = []
            for s in data:
                c = SeriesCard(s, self._posters, self.thumbs)
                c.clicked.connect(self.series_opened)
                c.poster.download_next.connect(self.series_download_all)
                c.poster.open_folder.connect(self.series_folder)
                c.poster.delete_requested.connect(self.series_delete)
                cards.append(c)
            self.grid_host.set_items(cards)
            items = cards
        for w in items:
            sid = w.series["id"]
            if sid in self._sizes:
                w.set_disk_size(self._sizes[sid])
        self.empty.setVisible(not items)
        self.telemetry.set_counts(len(data), len(self._all))

    def set_sizes_pending(self) -> None:
        pass

