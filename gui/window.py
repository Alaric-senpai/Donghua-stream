"""MainWindow: assembles rail, header, pages, queue and dialogs."""
import os
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QStackedWidget,
    QVBoxLayout, QWidget,
)

import db
from .components.header_bar import HeaderBar
from .components.sidebar import Sidebar
from .components.toast import Toast
from .dialogs.quick_url import QuickUrlDialog
from .dialogs.wizard import AddWizard
from .infrastructure.db_worker import DbWorker
from .infrastructure.download_queue import DownloadManager, DownloadTask
from .infrastructure.size_scanner import SizeScanner
from .infrastructure.thumbnails import ThumbnailStore
from .pages.detail import SeriesDetailView
from .pages.downloads import DownloadsView
from .pages.home import HomeView
from .pages.library import LibraryView
from .pages.settings import SettingsView
from .theme import T_MUTED, T_RAIL
from .utils import (
    URL_RE, disk_free, human_size, load_settings, pct, quality_label,
    set_setting,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Donghua Stream — Desktop Hub")
        self.resize(1440, 920)
        self.setMinimumSize(1080, 680)
        self.settings: Dict[str, str] = load_settings()
        self.manager = DownloadManager(self)
        self.thumbs = ThumbnailStore(self)
        self.thumbs.loaded.connect(self._on_thumb_loaded)
        self._token = 0
        self._workers: List[DbWorker] = []
        self._sizes: Dict[int, int] = {}
        self._scanner: Optional[SizeScanner] = None
        self._detail_sid = 0
        self._detail_vid = ""

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        # ---- sidebar + right column
        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self.navigateTo)
        shell.addWidget(self.sidebar)

        col = QWidget()
        colv = QVBoxLayout(col)
        colv.setContentsMargins(0, 0, 0, 0)
        colv.setSpacing(0)
        shell.addWidget(col, 1)

        self.header = HeaderBar()
        self.header.back_clicked.connect(lambda: self.navigateTo("home"))
        self.header.search_submitted.connect(self._on_search)
        self.header.add_clicked.connect(self.open_wizard)
        self.header.quality_changed.connect(self._on_header_quality)
        colv.addWidget(self.header)

        self.stack = QStackedWidget()
        colv.addWidget(self.stack, 1)

        self.home_view = HomeView(self.thumbs)
        self.library_view = LibraryView(self.thumbs)
        self.detail_view = SeriesDetailView(self.thumbs)
        self.downloads_view = DownloadsView(self.manager)
        self.settings_view = SettingsView(self.settings)
        for w in (self.home_view, self.library_view, self.detail_view,
                  self.downloads_view, self.settings_view):
            self.stack.addWidget(w)
        self._page_by_key = {"home": 0, "library": 1, "detail": 2,
                             "downloads": 3, "settings": 4}

        # view wiring
        self.home_view.series_opened.connect(self.open_series)
        self.home_view.series_download_all.connect(self._download_all_for)
        self.home_view.series_folder.connect(self._open_folder_series)
        self.home_view.series_delete.connect(self._delete_series)
        self.home_view.add_requested.connect(self.open_wizard)
        self.home_view.sync_requested.connect(self._force_resync)
        self.library_view.series_opened.connect(self.open_series)
        self.library_view.series_download_all.connect(self._download_all_for)
        self.library_view.series_folder.connect(self._open_folder_series)
        self.library_view.series_delete.connect(self._delete_series)
        self.library_view.add_requested.connect(self.open_wizard)
        self.library_view.sync_requested.connect(self._force_resync)
        self.detail_view.back_requested.connect(lambda: self.navigateTo("library"))
        self.detail_view.download_urls_requested.connect(self._download_episodes_for)
        self.detail_view.open_folder.connect(self._open_folder)
        self.detail_view.sync_series.connect(self._sync_series)
        self.detail_view.episode_changed.connect(lambda sid: (self.refresh_full(sid)))
        self.detail_view.toast.connect(lambda msg, ok: self.statusToast.show_message(msg, ok))
        self.settings_view.test_connection.connect(self._test_connection)
        self.settings_view.resync_requested.connect(self._force_resync)
        self.settings_view.settings_changed.connect(self._on_settings_changed)
        self.settings_view.toast.connect(lambda msg, ok: self.statusToast.show_message(msg, ok))

        # ---- status strip (bottom per Stitch footer spec)
        strip = QFrame()
        strip.setObjectName("card")
        strip.setStyleSheet(f"QFrame#card {{ border-radius: 0px; background: {T_RAIL};"
                            "border-top: 1px solid #28354d; }")
        strip.setFixedHeight(34)
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(18, 4, 18, 4)
        sl.setSpacing(14)
        self.status_free = QLabel("Storage: — free")
        self.status_catalog = QLabel("0 series · 0/0 downloaded")
        self.status_engine = QLabel("Engine: yt-dlp")
        self.status_state = QLabel("Status: Idle")
        for lab in (self.status_free, self.status_catalog, self.status_engine, self.status_state):
            lab.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
            sl.addWidget(lab)
        sl.addStretch(1)
        vers = QLabel("donghua-gui · PyQt6")
        vers.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
        sl.addWidget(vers)
        colv.addWidget(strip)

        # ---- toast overlay
        self.statusToast = Toast(central)
        self.statusToast.hide()

        # ---- manager wiring
        self.manager.state_changed.connect(self._on_queue_state)
        self.manager.event.connect(self._on_dl_event)
        self.manager.log_line.connect(self.downloads_view.on_log_line)
        self.manager.task_done.connect(self._on_task_done)

        # ---- shortcuts
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.header.search.setFocus())
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self.navigateTo("home"))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self.navigateTo("library"))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self.navigateTo("downloads"))
        QShortcut(QKeySequence("Ctrl+,"), self, lambda: self.navigateTo("settings"))
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)

        self.refresh_engine_versions()
        self.navigateTo("home")
        # bootstrap DB (create if missing, schema, archive re-sync), then first load
        self.run_db(lambda: db.init_db(), lambda res: self.refresh_full())

    # ---- helpers ------------------------------------------------------------
    def run_db(self, fn: Callable[[], Any], callback: Callable[[Any], None]) -> None:
        self._token += 1
        token = self._token
        worker = DbWorker(fn, token, self)

        def _on_done(t: int, res: Any, w: DbWorker = worker) -> None:
            if w in self._workers:
                self._workers.remove(w)
            if t == token:
                try:
                    callback(res)
                except Exception as exc:  # keep the GUI alive on handler errors
                    self.statusToast.show_message(f"UI refresh failed: {exc}", False)

        worker.done.connect(_on_done)
        worker.finished.connect(worker.deleteLater)
        self._workers.append(worker)
        worker.start()

    def statusToastMove(self) -> None:
        self.statusToast.resize_for(self.centralWidget())

    def refresh_engine_versions(self) -> None:
        try:
            import yt_dlp
            ver = yt_dlp.version.__version__
        except Exception:
            ver = "unknown"
        self.sidebar.set_engine_version(ver)
        self.status_engine.setText(f"Engine: yt-dlp {ver}")

    # ---- navigation -----------------------------------------------------------
    def navigateTo(self, key: str) -> None:
        if key == "add":
            self.open_wizard()
            return
        if key == "detail":
            key = "detail"
        self.stack.setCurrentIndex(self._page_by_key.get(key, 0))
        self.sidebar.set_active({"home": "home", "library": "library",
                                 "downloads": "downloads", "settings": "settings"}.get(key, "home"))
        self.header.set_breadcrumb({
            "home": "Home", "library": "Library", "downloads": "Download Center",
            "settings": "Settings & Storage", "detail": "Library / Series",
        }.get(key, "Home"))
        if key == "downloads":
            self.downloads_view.on_state_changed()

    def open_series(self, sid: int) -> None:
        self._detail_sid = sid

        def _loaded(res) -> None:
            if isinstance(res, Exception) or not res:
                self.statusToast.show_message("Series could not be loaded.", False)
                return
            series, poster_map = res
            if not series:
                return
            self._detail_vid = poster_map.get(sid, "")
            self.detail_view.load(series, self._detail_vid)
            self.stack.setCurrentIndex(self._page_by_key["detail"])
            self.sidebar.set_active("library")
            self.header.set_breadcrumb(f"Library / {series.get('name', '')}")
        self.run_db(lambda: (db.get_series(sid), db.get_series_poster_ids()), _loaded)

    # ---- data refresh ---------------------------------------------------------
    def refresh_full(self, focus_sid: Optional[int] = None) -> None:
        def _loaded(res) -> None:
            if isinstance(res, Exception):
                self.sidebar.set_db_ok(False)
                self.statusToast.show_message(f"Database error: {res}", False)
                return
            series, posters = res
            self.sidebar.set_db_ok(True)
            self.home_view.load(series, posters)
            self.library_view.load(series, posters)
            if self._detail_sid and focus_sid in (None, self._detail_sid):
                self.open_series(self._detail_sid)
            done = sum(int(s.get("downloaded_episodes", 0) or 0) for s in series)
            total = sum(int(s.get("total_episodes", 0) or 0) for s in series)
            self.status_catalog.setText(
                f"{len(series)} series · {done}/{total} downloaded ({pct(done, total)}%)")
            free = disk_free(self.settings.get("global_save_dir", "~/Videos"))
            self.status_free.setText(f"Storage: {human_size(free)} free")
            self.start_size_scan(series)
            if self.stack.currentIndex() == self._page_by_key["downloads"]:
                self.downloads_view.on_state_changed()
        self.run_db(lambda: (db.get_all_series(), db.get_series_poster_ids()), _loaded)

    def start_size_scan(self, series: List[Dict[str, Any]]) -> None:
        if self._scanner and self._scanner.isRunning():
            return
        jobs = [(s["id"], s.get("save_dir", "")) for s in series if s.get("save_dir")]
        if not jobs:
            return
        self._scanner = SizeScanner(jobs, self)
        sizes: Dict[int, int] = {}

        def _on_scan(sid: int, total: int):
            sizes[sid] = total
            self._sizes.update({sid: total})
            self.home_view.update_sizes({sid: total})
            self.library_view.update_sizes({sid: total})
            if sid == self._detail_sid:
                self.detail_view.update_disk_line(total)

        self._scanner.scanned.connect(_on_scan)
        self._scanner.finished.connect(self._scanner.deleteLater)
        self._scanner.start()

    # ---- thumbnails ------------------------------------------------------------
    def _on_thumb_loaded(self, vid: str, pix: QPixmap) -> None:
        self.home_view.update_poster(vid, pix)
        self.library_view.update_poster(vid, pix)
        if self._detail_vid == vid:
            self.detail_view.poster.setPixmap(
                pix.scaled(self.detail_view.poster.size(),
                           Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation))

    # ---- search / quick add -----------------------------------------------------
    def _on_search(self, text: str) -> None:
        if not text:
            return
        if URL_RE.search(text):
            dlg = QuickUrlDialog(self.home_view._all, self.settings, text, self)
            got = dlg.collect()
            if not got:
                return
            url, title = got["url"], got["title"]
            if got["series"] == "__new__":
                self.open_wizard(prefill=url)
                return
            sid = int(got["series"])
            self._quick_add_to(sid, url, title, got["quality"], got["download_now"])
        else:
            self.navigateTo("home")
            self.home_view.set_filter("all")
            self.home_view.quick.setText(text)
        self.header.search.clear()

    def _quick_add_to(self, sid: int, url: str, title: str,
                      quality: Optional[str], download_now: bool) -> None:
        def _saved(_res) -> None:
            self.statusToast.show_message("Episode saved to the library.", True)
            if download_now:
                s = next((x for x in self.home_view._all if x["id"] == sid), None)
                if s:
                    self._download_episodes_for(sid, [url], quality)
            else:
                self.refresh_full(sid)
        self.run_db(lambda: db.add_episode(sid, url, title=title or ""), _saved)

    # ---- wizard -----------------------------------------------------------------
    def open_wizard(self, prefill: str = "") -> None:
        dlg = AddWizard(self.settings, self)
        if prefill:
            dlg.urls.setPlainText(prefill)
            dlg.next_btn.setFocus()
        dlg.series_created.connect(self._on_series_created)
        dlg.exec()
        self.refresh_full()

    def _on_series_created(self, sid: int, urls: list, download_now: bool, quality: str) -> None:
        self.statusToast.show_message(
            f"Series created with {len(urls)} episode(s)." if urls else "Series created.", True)
        if download_now and urls:

            def _created(res) -> None:
                if isinstance(res, Exception) or not res:
                    return
                series = res
                task = DownloadTask(sid, series.get("name", ""),
                                    series.get("save_dir", ""), list(urls),
                                    quality=quality, label=str(series.get("key") or ""))
                self.manager.enqueue(task)
                self.navigateTo("downloads")
            self.run_db(lambda: db.get_series(sid), _created)
        else:
            self.open_series(sid)

    # ---- downloads plumbing -------------------------------------------------------
    def _download_all_for(self, sid: int) -> None:
        def _loaded(res) -> None:
            if isinstance(res, Exception) or not res:
                self.statusToast.show_message("Could not queue this series.", False)
                return
            series, eps = res
            urls = [e["url"] for e in eps if e.get("status") != "downloaded"]
            if not urls:
                self.statusToast.show_message("Everything from this series is already downloaded ✔", True)
                return
            self._enqueue(series, urls)
        self.run_db(lambda: (db.get_series(sid), db.get_episodes(sid)), _loaded)

    def _download_episodes_for(self, sid: int, urls: List[str], quality: Optional[str]) -> None:
        def _loaded(res) -> None:
            if isinstance(res, Exception) or not res:
                return
            series = res
            self._enqueue(series, urls, quality)
        self.run_db(lambda: db.get_series(sid), _loaded)

    def _enqueue(self, series: Dict[str, Any], urls: List[str],
                 quality: Optional[str] = None) -> None:
        task = DownloadTask(int(series["id"]), series.get("name", ""),
                            series.get("save_dir", ""), urls,
                            quality=quality, label=str(series.get("key") or ""))
        self.manager.enqueue(task)
        # mark as queued in the registry
        def _mark(_res):
            self.refresh_full()
        self.run_db(lambda: [db.mark_episode_status(int(series["id"]),
                                                    db.extract_video_id(u), "queued")
                             for u in urls], _mark)
        self.navigateTo("downloads")
        self.statusToast.show_message(f"Queued {len(urls)} video(s) from {series.get('name', '')}.", True)

    def _on_dl_event(self, ev: str, data: Dict[str, Any]) -> None:
        self.downloads_view.on_event(ev, data)
        if ev == "progress" and data.get("status") == "downloading":
            self.header.set_speed(float(data.get("speed") or 0))
            self.status_state.setText(
                f"Status: {human_size(data.get('downloaded_bytes') or 0)} / "
                f"{human_size(data.get('total_bytes') or 0)}")
        elif ev == "attempt":
            self.header.set_active_text("1 Active", True)
            self.status_state.setText("Status: Downloading")
        elif ev == "success":
            self.status_state.setText("Status: Saved")
        elif ev == "finish":
            self.status_state.setText("Status: Idle")

    def _on_queue_state(self) -> None:
        self.downloads_view.on_state_changed()
        m = self.manager
        if m.active_task:
            self.header.set_active_text("1 Active", True)
        elif m.paused:
            self.header.set_active_text("Queue Paused", False)
        elif m.queue:
            self.header.set_active_text(f"{len(m.queue)} Queued", False)
        else:
            self.header.set_active_text("Idle", False)

    def _on_task_done(self, task: Optional[DownloadTask], ok: bool) -> None:
        if task is None:
            return

        def _mark(_res) -> None:
            self.statusToast.show_message(
                f"{task.series_name}: run complete.", True)
            self.refresh_full()

        def _sync() -> None:
            try:
                db.sync_series_with_archive(int(task.series_id))
                eps = db.get_episodes(int(task.series_id))
                arch = db.get_archive_downloaded_ids(task.save_dir)
                for e in eps:
                    if e["video_id"] in arch:
                        db.mark_episode_status(int(task.series_id), e["video_id"], "downloaded")
            except Exception:
                pass
        self.run_db(_sync, _mark)

    # ---- series actions ---------------------------------------------------------
    def _open_folder(self, path: str) -> None:
        if not path:
            return
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            self.statusToast.show_message("Folder does not exist yet.", False)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _open_folder_series(self, sid: int) -> None:
        s = next((x for x in self.home_view._all if x["id"] == sid), None)
        if s:
            self._open_folder(s.get("save_dir", ""))

    def _delete_series(self, sid: int) -> None:
        s = next((x for x in self.home_view._all if x["id"] == sid), None)
        name = s["name"] if s else f"id {sid}"
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Delete series",
                f"Delete '{name}' and its episode registry?\nFiles on disk are NOT removed.") == \
                QMessageBox.StandardButton.Yes:
            try:
                db.delete_series(sid)
                self.statusToast.show_message(f"Deleted {name}.", True)
            except Exception as exc:
                self.statusToast.show_message(f"Delete failed: {exc}", False)
            self.refresh_full()

    def _sync_series(self, sid: int) -> None:
        def _done(res) -> None:
            if isinstance(res, Exception):
                self.statusToast.show_message(f"Sync failed: {res}", False)
            else:
                self.statusToast.show_message("Archive re-sync finished.", True)
            self.refresh_full()
        self.run_db(lambda: db.sync_series_with_archive(sid), _done)

    def _force_resync(self) -> None:
        def _res() -> Any:
            data = db.sync_existing_records()
            for s in db.get_all_series():
                db.sync_series_with_archive(s["id"])
            return data

        def _done(res) -> None:
            if isinstance(res, Exception):
                self.statusToast.show_message(f"Re-sync failed: {res}", False)
            else:
                self.statusToast.show_message("Library re-synced.", True)
            self.refresh_full()
        self.run_db(_res, _done)

    def _test_connection(self) -> None:
        def _ping() -> bool:
            conn = db.get_connection()
            conn.close()
            return True

        def _done(res) -> None:
            self.sidebar.set_db_ok(res is True or not isinstance(res, Exception))
            self.statusToast.show_message(
                "Database connection OK ✔" if res is True else f"Connection failed: {res}",
                res is True)
            self.refresh_full()
        self.run_db(_ping, _done)

    def _on_settings_changed(self, key: str) -> None:
        self.settings = load_settings()
        if key in ("default_quality", "*"):
            self.header.set_quality_silent(self.settings.get("default_quality", "720p"))
        if key in ("global_save_dir", "*"):
            free = disk_free(self.settings.get("global_save_dir", "~/Videos"))
            self.status_free.setText(f"Storage: {human_size(free)} free")

    def _on_header_quality(self, value: str) -> None:
        self.settings["default_quality"] = value
        set_setting("default_quality", value)
        self.settings_view.s["default_quality"] = value
        self.statusToast.show_message(f"Default quality set to {quality_label(value)}.", True)

    # ---- misc ------------------------------------------------------------
    def closeEvent(self, ev) -> None:
        # Ask the engine to stop and let threads finish so Qt does not
        # destroy live QThreads on shutdown.
        try:
            self.manager.cancel_current()
        except Exception:
            pass
        for w in list(self._workers):
            try:
                w.wait(400)
            except Exception:
                pass
        if self._scanner is not None:
            try:
                self._scanner.wait(300)
            except Exception:
                pass
        if self.manager.active:
            try:
                self.manager.active.wait(700)
            except Exception:
                pass
        super().closeEvent(ev)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self.statusToastMove()

