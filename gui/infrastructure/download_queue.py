"""Sequential yt-dlp queue bridged into Qt signals (one active task)."""
import threading
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from downloader import VideoDownloader

from ..utils import load_settings


class QuietYdlLogger(QObject):
    """Routes yt-dlp console output into the Downloads terminal view."""

    line = pyqtSignal(str)
    tag = "[download]"

    def debug(self, msg: Any):
        text = str(msg).rstrip()
        if text:
            self.line.emit(f"{self.tag} {text}")

    warning = debug
    info = debug

    def error(self, msg: Any):
        text = str(msg).rstrip()
        if text:
            self.line.emit(f"[error] {text}")


class DownloadTask:
    """One queued unit: a batch of URLs for one series."""

    def __init__(self, series_id: int, series_name: str, save_dir: str,
                 urls: List[str], quality: Optional[str] = None,
                 label: str = ""):
        self.series_id = series_id
        self.series_name = series_name
        self.save_dir = save_dir
        self.urls = urls
        self.quality = quality
        self.label = label or f"{series_name}"
        self.progress = 0.0
        self.status = "queued"

    def __repr__(self):
        return f"<Task {self.series_name} {len(self.urls)} url(s) {self.status}>"


class DownloadWorker(QThread):
    """Executes one DownloadTask through the shared VideoDownloader engine."""

    # NOTE: never name a signal ``event`` on a QObject: it shadows
    # QObject.event() and Qt aborts with "native Qt signal is not callable".
    download_event = pyqtSignal(str, dict)
    line = pyqtSignal(str)

    def __init__(self, task: DownloadTask, settings: Dict[str, str], parent=None):
        super().__init__(parent)
        self.task = task
        self.settings = settings
        self._cancel_flag = threading.Event()

    def cancel(self):
        self._cancel_flag.set()

    def run(self):
        s = self.settings
        try:
            rate_mb = float(s.get("rate_limit_mb", "0") or 0)
        except (TypeError, ValueError):
            rate_mb = 0.0
        ydl_log = QuietYdlLogger()
        ydl_log.line.connect(self.line)  # type: ignore[arg-type]
        engine = VideoDownloader(
            quality=self.task.quality if self.task.quality else s.get("default_quality", "720p"),
            max_retries=int(s.get("max_retries", "3") or 3),
            browser=(s.get("browser_cookies", "brave") or "").strip().lower(),
            write_subs=True,
            on_event=lambda ev, data: self.download_event.emit(ev, dict(data or {})),
            cancel_check=self._cancel_flag.is_set,
            ydl_logger=ydl_log,
            container=s.get("default_container", "mp4") or "mp4",
            sub_langs=s.get("sub_langs", "en") or "en",
            rate_limit=(rate_mb if rate_mb > 0 else None),
        )
        try:
            summary = engine.download_urls(self.task.urls, self.task.save_dir,
                                           quality=self.task.quality)
            self.download_event.emit("summary", {
                "total": summary.total,
                "succeeded": list(summary.succeeded),
                "failed": [dict(f) for f in summary.failed],
                "skipped": list(summary.skipped),
            })
        except Exception as exc:  # keep the GUI alive if the engine explodes
            self.download_event.emit("summary", {"fatal": str(exc)})


class DownloadManager(QObject):
    """Sequential queue: exactly one Now-Playing task at a time.

    "Pause All" freezes the queue (the running task is allowed to finish);
    it does not abort the active task.
    """

    state_changed = pyqtSignal()
    download_event = pyqtSignal(str, dict)  # forwarded downloader events
    log_line = pyqtSignal(str)
    task_done = pyqtSignal(object, bool)   # (task, ok)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.queue: List[DownloadTask] = []
        self.active: Optional[DownloadWorker] = None
        self.active_task: Optional[DownloadTask] = None
        self.paused = False
        self.finished_log: List[Dict[str, Any]] = []
        self.settings: Dict[str, str] = load_settings()

    # ---- public API -------------------------------------------------------
    def enqueue(self, task: DownloadTask) -> None:
        self.settings = load_settings()
        self.queue.append(task)
        self.state_changed.emit()
        self._maybe_start_next()

    def remove(self, task: DownloadTask) -> None:
        if task in self.queue:
            self.queue.remove(task)
            self.state_changed.emit()

    def move(self, task: DownloadTask, up: bool) -> None:
        if task not in self.queue:
            return
        i = self.queue.index(task)
        j = i - 1 if up else i + 1
        if 0 <= j < len(self.queue):
            self.queue[i], self.queue[j] = self.queue[j], self.queue[i]
            self.state_changed.emit()

    def clear_finished(self) -> None:
        self.finished_log.clear()
        self.state_changed.emit()

    def pause_all(self) -> None:
        self.paused = True
        self.state_changed.emit()

    def resume_all(self) -> None:
        self.paused = False
        self.state_changed.emit()
        self._maybe_start_next()

    def cancel_current(self) -> None:
        if self.active:
            self.log_line.emit("[status] Cancel request sent to yt-dlp…")
            self.active.cancel()

    def shutdown(self, wait_ms: int = 3000) -> None:
        """Stop the active worker before Qt tears down its parent objects."""
        self.paused = True
        worker = self.active
        if worker is None:
            return
        worker.cancel()
        if worker.wait(wait_ms):
            return
        # Last-resort guard for a wedged network call. The process is exiting,
        # so a partially written file is preferable to an abort in QThread.
        worker.terminate()
        worker.wait(800)

    def busy(self) -> bool:
        return self.active is not None

    # ---- internals ----------------------------------------------------------
    def _maybe_start_next(self) -> None:
        if self.active or self.paused or not self.queue:
            if self.paused and self.queue:
                self.log_line.emit("[status] Queue paused - new tasks will wait.")
            return
        task = self.queue.pop(0)
        self.active_task = task
        task.status = "downloading"
        self.log_line.emit(
            f"[status] Now playing: {task.series_name} - {len(task.urls)} video(s)"
            + (f" ({task.label})" if task.label else "")
        )
        self.state_changed.emit()
        worker = DownloadWorker(task, self.settings, self)
        worker.download_event.connect(self._on_event)
        worker.line.connect(self.log_line)  # type: ignore[arg-type]
        worker.finished.connect(self._on_worker_finished)
        self.active = worker
        worker.start()

    def _on_event(self, ev: str, data: dict) -> None:
        task = self.active_task
        if task and ev == "progress" and data.get("status") in (
                "downloading", "stream_finished"):
            total = float(data.get("total_bytes") or 0)
            done = float(data.get("downloaded_bytes") or 0)
            progress = (done / total) if total > 0 else 0.0
            # A finished stream is not a finished episode: another stream
            # and the ffmpeg merge may still be pending.
            if data.get("status") == "stream_finished":
                progress = min(progress, 0.99)
            task.progress = progress
        elif task and ev == "progress" and data.get("status") == "finished":
            task.progress = 1.0
        self.download_event.emit(ev, data)
        # Re-broadcast a snapshot of the running state for view refreshes.
        self.state_changed.emit()

    def _on_worker_finished(self) -> None:
        task = self.active_task
        self.active, self.active_task = None, None
        if task is not None:
            task.status = "finished"
            task.progress = 1.0
            self.finished_log.append({
                "series": task.series_name, "dir": task.save_dir,
                "urls": list(task.urls), "label": task.label, "time": "just now",
            })
        self.state_changed.emit()
        self.task_done.emit(task, task is not None)
        self._maybe_start_next()

    def current_snapshot(self) -> Dict[str, Any]:
        t = self.active_task
        if not t:
            return {}
        return {"task": t, "progress": t.progress, "label": t.label}

