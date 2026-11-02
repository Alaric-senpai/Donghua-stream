#!/usr/bin/env python3
"""gui.py - Donghua Stream: cinematic TV-streaming desktop app (PyQt6).

UI fully based on the "donghua stream" Stitch design system
(canvas #020617, rail #0f172a, card #1e293b, hover #334155, primary #38bdf8):

  * 250px navigation rail  - Home / Library / Downloads / Add Donghua /
                             Settings + DB status footer
  * Home    - hero spotlight with gradient scrims, filter tabs with count
              chips, telemetry strip, poster grid with hover quick-actions
  * Library - compact list rows of the same catalog
  * Series Detail - "N EPS" chip, genre tags, sync-progress card, episode
              registry (All / Downloaded / Queued / Failed tabs) with
              per-row Download, Copy, Edit, Delete, Retry
  * Add Donghua wizard - step pills, storage preset tiles (Videos /
              Downloads / Documents / Custom) with free-space chips, bulk
              paste with `URL  # Episode title` parsing, and both
              "Save to Library" and "Save & Download Immediately"
  * Downloads - Network Pipeline telemetry (rate / transferred / ETA),
              queue with priority reordering, Pause All / Resume All /
              Clear Finished, colorized yt-dlp terminal
  * Settings - Storage & Directories, Quality & Formats, Network limits,
              Browser & Auth, Database & Daemon (Test Connection)

The interactive CLI (script.py) keeps working untouched.
Launch from anywhere with the global `donghua-gui` command.
"""

import os
import re
import sys
import shutil
import threading

from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QThread, QObject, QTimer, pyqtSignal, QUrl, QSize
from PyQt6.QtGui import (
    QDesktopServices, QKeySequence, QPainter, QPixmap, QColor, QFont,
    QShortcut, QIcon, QLinearGradient,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWidgets import (
    QApplication, QAbstractItemView, QButtonGroup, QCheckBox, QComboBox,
    QDialog, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QStackedWidget, QStatusBar, QTextEdit, QToolButton, QVBoxLayout, QWidget,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import pyqtSlot

import db
import downloader
from downloader import VideoDownloader

# ==============================================================================
# Design tokens  (from the Stitch "donghua stream" design system)
# ==============================================================================
T_CANVAS = "#020617"          # canvas-base
T_RAIL = "#0f172a"            # surface-rail / nav
T_CARD = "#1e293b"            # surface-card
T_HOVER = "#334155"           # surface-hover
T_BORDER = "rgba(51,65,85,0.4)"
T_PRIMARY = "#38bdf8"         # sky-400
T_ON_PRIMARY = "#004965"
T_TEXT = "#f8fafc"
T_SEC = "#94a3b8"
T_MUTED = "#64748b"
T_EMERALD = "#10b981"
T_EMERALD2 = "#4edea3"
T_AMBER = "#f59e0b"
T_ROSE = "#f43f5e"
T_FONT = "Inter"

THUMB_DIR = os.path.join(os.path.expanduser("~"), ".cache", "donghua-stream", "thumbs")
os.makedirs(THUMB_DIR, exist_ok=True)

# ==============================================================================
# Small helpers
# ==============================================================================


def human_size(n: Optional[float]) -> str:
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return (f"{n:.1f} {unit}" if unit not in ("B",) else f"{int(n)} {unit}")
        n /= 1024.0
    return f"{n:.1f} TB"


def speed_text(bps: Optional[float]) -> str:
    try:
        return f"{human_size(float(bps or 0))}/s"
    except (TypeError, ValueError):
        return "0 B/s"


def format_eta(seconds: Optional[float]) -> str:
    try:
        s = int(float(seconds or 0))
    except (TypeError, ValueError):
        s = 0
    if s <= 0:
        return "--:--"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def disk_free(path: str) -> Optional[int]:
    try:
        return shutil.disk_usage(os.path.expanduser(path)).free
    except OSError:
        return None


def resolve_path(raw: str, base_dir: Optional[str] = None) -> str:
    p = os.path.expanduser(raw.strip())
    if base_dir and not os.path.isabs(p):
        p = os.path.join(os.path.expanduser(base_dir), p)
    return p


URL_RE = re.compile(r"https?://\S+")


def parse_bulk_urls(text: str) -> List[Dict[str, str]]:
    """Parse pasted text into episode entries.

    Accepts one URL per line, optionally `URL   # Episode title`.
    Lines starting with '#' or '//' are comments.
    Returns [{'url', 'title', 'vid', 'dup'}]; 'dup' == "1" when video id repeats.
    """
    items: List[Dict[str, str]] = []
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        m = re.match(r"^(.*?)(?:\s*#\s*(.+))?$", line)
        url = URL_RE.search(m.group(1))
        if not url:
            continue
        url = url.group(0).strip()
        title = (m.group(2) or "").strip()
        vid = db.extract_video_id(url)
        dup = vid in seen
        seen.add(vid)
        items.append({"url": url, "title": title, "vid": vid, "dup": "1" if dup else ""})
    return items


QUALITY_OPTIONS = [("480p", "480p (Fast)"), ("720p", "720p (HD)"),
                   ("1080p", "1080p (Full HD)"), ("2160p", "4K (2160p)"), ("best", "Best Available")]

CONTAINER_OPTIONS = [("mp4", "MP4  - max compatibility"),
                     ("mkv", "MKV  - best quality muxing"),
                     ("webm", "WebM  - open codecs")]

BROWSER_OPTIONS = [("brave", "Brave"), ("chrome", "Chrome"), ("chromium", "Chromium"),
                   ("firefox", "Firefox"), ("edge", "Edge"), ("opera", "Opera"),
                   ("vivaldi", "Vivaldi"), ("safari", "Safari"), ("none", "No cookies")]


def quality_label(q: Any) -> str:
    for val, lab in QUALITY_OPTIONS:
        if str(val) == str(q):
            return lab
    return f"{q}p"


def pct(part: int, whole: int) -> int:
    return int(round(100.0 * part / whole)) if whole else 0


def load_settings() -> Dict[str, str]:
    try:
        return db.get_all_settings()
    except Exception:
        return dict(db.DEFAULT_SETTINGS)


def set_setting(key: str, value: str) -> bool:
    try:
        return db.set_setting(key, str(value))
    except Exception:
        return False


# ==============================================================================
# Thumbnails (async network fetch with local disk cache)
# ==============================================================================


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


# ==============================================================================
# yt-dlp console output → colorized terminal lines
# ==============================================================================


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


# ==============================================================================
# Download engine bridge
# ==============================================================================


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

    event = pyqtSignal(str, dict)
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
        ydl_log = QuietYdlLogger(self)
        ydl_log.line.connect(self.line)  # type: ignore[arg-type]
        engine = VideoDownloader(
            quality=self.task.quality if self.task.quality else s.get("default_quality", "720p"),
            max_retries=int(s.get("max_retries", "3") or 3),
            browser=(s.get("browser_cookies", "brave") or "").strip().lower(),
            write_subs=True,
            on_event=lambda ev, data: self.event.emit(ev, dict(data or {})),
            cancel_check=self._cancel_flag.is_set,
            ydl_logger=ydl_log,
            container=s.get("default_container", "mp4") or "mp4",
            sub_langs=s.get("sub_langs", "en") or "en",
            rate_limit=(rate_mb if rate_mb > 0 else None),
        )
        try:
            summary = engine.download_urls(self.task.urls, self.task.save_dir,
                                           quality=self.task.quality)
            self.event.emit("summary", {
                "total": summary.total,
                "succeeded": list(summary.succeeded),
                "failed": [dict(f) for f in summary.failed],
                "skipped": list(summary.skipped),
            })
        except Exception as exc:  # keep the GUI alive if the engine explodes
            self.event.emit("summary", {"fatal": str(exc)})


class DownloadManager(QObject):
    """Sequential queue: exactly one Now-Playing task at a time.

    "Pause All" freezes the queue (the running task is allowed to finish);
    it does not abort the active task.
    """

    state_changed = pyqtSignal()
    event = pyqtSignal(str, dict)          # forwarded downloader events
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
        worker.event.connect(self._on_event)
        worker.line.connect(self.log_line)  # type: ignore[arg-type]
        worker.finished.connect(self._on_worker_finished)
        self.active = worker
        worker.start()

    def _on_event(self, ev: str, data: dict) -> None:
        task = self.active_task
        if task and ev == "progress" and data.get("status") == "downloading":
            total = float(data.get("total_bytes") or 0)
            done = float(data.get("downloaded_bytes") or 0)
            task.progress = (done / total) if total > 0 else 0.0
        self.event.emit(ev, data)
        # Re-broadcast a snapshot of the running state for view refreshes.
        self.state_changed.emit()

    def _on_worker_finished(self) -> None:
        task, worker = self.active_task, self.active
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


# ==============================================================================
# Toast (bottom-right notification, per the Stitch status/sync chips)
# ==============================================================================


class Toast(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self._label)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, ok: bool = True, ms: int = 4200):
        self._label.setText(
            f"<span style='color:{T_EMERALD2 if ok else '#ffb4ab'};font-weight:800'>"
            f"{'✔' if ok else '⚠'}</span>&nbsp;{text}"
        )
        self.adjustSize()
        host = self.parent() if self.parent() is not None else self
        self.move(host.width() - self.width() - 24, host.height() - self.height() - 64)
        self.show()
        self.raise_()
        self._timer.start(ms)

    def resize_for(self, host: QWidget):
        self.move(host.width() - self.width() - 24, host.height() - self.height() - 64)


# ==============================================================================
# Global stylesheet (QSS translation of the Stitch Tailwind classes)
# ==============================================================================


def app_stylesheet() -> str:
    return f"""
* {{
    background: transparent;
    color: {T_TEXT};
    font-family: "{T_FONT}", "Segoe UI", sans-serif;
}}
QWidget#root {{ background-color: {T_CANVAS}; }}
QFrame#rail, QWidget#railInner {{ background-color: {T_RAIL}; }}
QFrame#card {{ background-color: {T_CARD}; border-radius: 16px; }}
QFrame#cardSoft {{ background-color: #131b2e; border-radius: 12px; }}
QLabel {{ color: {T_TEXT}; background: transparent; }}
QLabel.colorSec {{ color: {T_SEC}; }}
QLabel.colorMuted {{ color: {T_MUTED}; }}
QLabel.labelCaps {{
    color: {T_MUTED}; font-size: 11px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase; background: transparent;
}}
QLabel.codePill {{ color: {T_PRIMARY}; font-family: "JetBrains Mono", monospace; }}
QLabel.titleXl {{ font-size: 30px; font-weight: 800; }}
QLabel.titleLg {{ font-size: 24px; font-weight: 700; }}
QLabel.titleMd {{ font-size: 17px; font-weight: 700; }}
QLabel.titleSm {{ font-size: 14px; font-weight: 600; }}
QLabel.body {{ font-size: 13px; color: {T_SEC}; }}
QLabel.small {{ font-size: 11px; color: {T_MUTED}; }}

QPushButton {{ border: none; border-radius: 10px; padding: 0px; background: transparent; }}
QPushButton#navBtn {{
    text-align: left; padding: 10px 14px; border-radius: 10px;
    color: {T_SEC}; font-size: 14px; font-weight: 600;
}}
QPushButton#navBtn:hover {{ background: {T_HOVER}; color: {T_TEXT}; }}
QPushButton#navBtn:checked {{ background: {T_PRIMARY}; color: {T_ON_PRIMARY}; }}

QPushButton#primary {{
    background: {T_PRIMARY}; color: {T_ON_PRIMARY};
    border-radius: 10px; font-weight: 800; font-size: 13px;
}}
QPushButton#primary:hover {{ background: #7dd3fc; }}
QPushButton#primary:disabled {{ background: #155e75; color: #67a9c1; }}

QPushButton#ghost {{
    background: {T_CARD}; color: {T_TEXT}; border: 1px solid #33415555;
    border-radius: 10px; font-weight: 600; font-size: 13px;
}}
QPushButton#ghost:hover {{ background: {T_HOVER}; border-color: {T_PRIMARY}; }}

QPushButton#danger {{
    background: transparent; color: {T_ROSE}; border: 1px solid #f43f5e55;
    border-radius: 10px; font-weight: 600; font-size: 13px;
}}
QPushButton#danger:hover {{ background: #f43f5e22; }}

QPushButton#success {{
    background: {T_EMERALD}; color: #00311f; border-radius: 10px;
    font-weight: 800; font-size: 13px;
}}
QPushButton#success:hover {{ background: {T_EMERALD2}; }}

QPushButton#iconBtn {{
    background: {T_CARD}; color: {T_SEC}; border-radius: 8px;
    font-size: 14px; min-width: 30px; max-height: 30px; border: 1px solid transparent;
}}
QPushButton#iconBtn:hover {{ background: {T_HOVER}; color: {T_PRIMARY}; }}
QPushButton#iconBtn:disabled {{ color: #475569; }}

QPushButton#chip {{
    background: {T_CARD}; border: 1px solid #33415555; border-radius: 999px;
    color: {T_SEC}; padding: 5px 12px; font-size: 12px; font-weight: 600;
}}
QPushButton#chipTri {{
    background: #f59e0b22; border: 1px solid #f59e0b66; border-radius: 999px;
    color: #fcd34d; padding: 5px 12px; font-size: 12px; font-weight: 700;
}}
QPushButton#chipEmerge {{
    background: #10b98122; border: 1px solid #10b98166; border-radius: 999px;
    color: {T_EMERALD2}; padding: 5px 12px; font-size: 12px; font-weight: 700;
}}
QPushButton#chipActive {{
    background: {T_PRIMARY}; border-radius: 999px; color: {T_ON_PRIMARY};
    padding: 5px 12px; font-size: 12px; font-weight: 700;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {T_RAIL};
    border: 1px solid {T_BORDER};
    border-radius: 10px;
    padding: 8px 12px;
    color: {T_TEXT};
    font-size: 13px;
    selection-background-color: {T_PRIMARY};
    selection-color: {T_ON_PRIMARY};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {T_PRIMARY};
}}
QLineEdit#search {{
    background: {T_CARD}; border: 1px solid #33415555; border-radius: 999px;
    padding: 9px 18px; color: {T_SEC}; font-size: 13px;
}}
QLineEdit#search:focus {{ border-color: {T_PRIMARY}; background: #223049; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{
    background: {T_CARD}; border: 1px solid {T_PRIMARY};
    selection-background-color: {T_HOVER}; outline: none;
}}

QListWidget {{
    background: transparent; border: none; outline: none;
}}
QListWidget::item {{ color: {T_SEC}; border-radius: 8px; padding: 6px 10px; }}
QListWidget::item:selected {{ background: {T_HOVER}; color: {T_TEXT}; }}
QListWidget::item:hover {{ background: #223049; }}

QScrollArea {{ border: none; background: transparent; }}
QWidget#scrollHost {{ background: transparent; }}

QProgressBar {{
    background: #0e1a30; border: none; border-radius: 4px;
    text-align: center; color: transparent; max-height: 8px; min-height: 8px;
}}
QProgressBar::chunk {{ border-radius: 4px; background-color: {T_PRIMARY}; }}
QProgressBar#barGreen::chunk {{ background-color: {T_EMERALD}; }}
QProgressBar#barAmber::chunk {{ background-color: {T_AMBER}; }}
QProgressBar#barRose::chunk {{ background-color: {T_ROSE}; }}

QTextEdit {{
    background: {T_RAIL}; border: 1px solid {T_BORDER}; border-radius: 12px;
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 12px; color: #cbd5e1; padding: 10px;
    selection-background-color: {T_PRIMARY}; selection-color: {T_ON_PRIMARY};
}}
QTextEdit:focus {{ border-color: {T_PRIMARY}; }}

QFrame#hline {{ background: #33415566; max-height: 1px; border: none; }}
QFrame#vline {{ background: #33415566; max-width: 1px; border: none; }}
QFrame#heroChrome {{ background: transparent; }}
QLabel#terminalDemo {{ color: {T_SEC}; }}

QStatusBar {{ background: {T_RAIL}; color: {T_MUTED}; border-top: 1px solid #28354d; }}
QStatusBar::item {{ border: none; }}

QToolTip {{
    background: {T_CARD}; color: {T_TEXT}; border: 1px solid {T_PRIMARY};
    padding: 4px 8px; border-radius: 6px;
}}
QMenu {{ background: {T_CARD}; border: 1px solid {T_PRIMARY}; padding: 6px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 6px; color: {T_SEC}; }}
QMenu::item:selected {{ background: {T_HOVER}; color: {T_TEXT}; }}
QCheckBox {{ color: {T_SEC}; font-size: 13px; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid #475569; background: {T_RAIL};
}}
QCheckBox::indicator:checked {{ background: {T_PRIMARY}; border-color: {T_PRIMARY}; }}
"""


def mk_label(text: str = "", cls: str = "", color_name: str = "",
             wrap: bool = False) -> QLabel:
    """Styled label: cls is one of titleXl/titleLg/titleMd/titleSm/body/small."""
    lab = QLabel(text)
    if cls:
        lab.setObjectName(cls)
    if color_name == "muted":
        lab.setStyleSheet(f"color: {T_MUTED};")
    elif color_name == "sec":
        lab.setStyleSheet(f"color: {T_SEC};")
    lab.setWordWrap(wrap)
    return lab


def label_caps(text: str) -> QLabel:
    lab = QLabel(text.upper())
    lab.setStyleSheet(
        f"color: {T_MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1.2px;"
    )
    return lab


def chip_tag(text: str, tone: str = "default") -> QLabel:
    tones = {
        "default": (T_CARD, "#33415588", T_SEC),
        "sky": ("#38bdf833", "#38bdf877", T_PRIMARY),
        "emerald": ("#10b98122", "#10b98166", T_EMERALD2),
        "amber": ("#f59e0b22", "#f59e0b66", "#fcd34d"),
        "rose": ("#f43f5e22", "#f43f5e66", "#fda4af"),
        "primary": (T_PRIMARY, T_PRIMARY, T_ON_PRIMARY),
    }
    bg, border, fg = tones.get(tone, tones["default"])
    lab = QLabel(text)
    lab.setStyleSheet(
        f"background: {bg}; border: 1px solid {border}; border-radius: 999px;"
        f"color: {fg}; font-size: 11px; font-weight: 700; padding: 2px 10px;"
    )
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lab


def btn(text: str, kind: str = "ghost", tip: str = "", small: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName(kind if kind in ("primary", "ghost", "danger", "success", "chip") else "ghost")
    if tip:
        b.setToolTip(tip)
    if small:
        b.setFixedHeight(28)
    else:
        b.setMinimumHeight(38)
    return b


def icon_btn(symbol: str, tip: str = "") -> QPushButton:
    b = QPushButton(symbol, )
    b.setObjectName("iconBtn")
    b.setFixedSize(30, 30)
    if tip:
        b.setToolTip(tip)
    return b


def hline() -> QFrame:
    f = QFrame()
    f.setObjectName("hline")
    f.setFixedHeight(1)
    f.setFrameShape(QFrame.Shape.NoFrame)
    return f


def vline() -> QFrame:
    f = QFrame()
    f.setObjectName("vline")
    f.setFixedWidth(1)
    f.setFrameShape(QFrame.Shape.NoFrame)
    return f


def styled_bar(color: str = "primary") -> QProgressBar:
    p = QProgressBar()
    p.setRange(0, 100)
    p.setTextVisible(False)
    p.setObjectName({"emerald": "barGreen", "amber": "barAmber", "rose": "barRose"}.get(color, "barDefault"))
    return p


def set_shadow(w: QWidget, blur: int = 40, alpha: int = 160, dy: int = 10) -> None:
    eff = QGraphicsDropShadowEffect(w)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    w.setGraphicsEffect(eff)


# ==============================================================================
# Navigation rail (Sidebar)
# ==============================================================================

NAV_ITEMS = [
    ("home", "⌂", "Home", "Hero spotlight, spotlight rows and the poster catalog."),
    ("library", "▤", "Library", "Compact list of every donghua in the database."),
    ("downloads", "⇩", "Downloads", "Network pipeline telemetry and queue control."),
    ("add", "✚", "Add Donghua", "Register a series and its episode URLs."),
    ("settings", "⚙", "Settings", "Storage, quality, network and database preferences."),
]


class Sidebar(QWidget):
    """250px navigation rail: surface #0f172a, nav buttons, DB status footer."""

    navigate = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("rail")
        self.setFixedWidth(250)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 24, 16, 16)
        outer.setSpacing(8)

        # ---- logo block
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel("▶")
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"background: {T_PRIMARY}; color: {T_ON_PRIMARY}; border-radius: 12px;"
            "font-size: 18px; font-weight: 900;"
        )
        brand.addWidget(logo)
        btxt = QVBoxLayout()
        btxt.setSpacing(0)
        btxt.addWidget(QLabel("Donghua Stream"))
        sub = QLabel("Desktop Hub")
        sub.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
        self._ver_sub = sub
        btxt.addWidget(self._ver_sub)
        bcol = QWidget()
        bcol.setLayout(btxt)
        brand.addWidget(bcol)
        brand.addStretch(1)
        outer.addLayout(brand)
        outer.addSpacing(18)

        caps = QLabel("NAVIGATION")
        caps.setStyleSheet(f"color: {T_MUTED}; font-size: 10px; font-weight: 800; letter-spacing: 1.5px;")
        outer.addWidget(caps)
        outer.addSpacing(2)

        self._buttons: Dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for i, (key, glyph, name, tip) in enumerate(NAV_ITEMS):
            b = QPushButton(f"{glyph}   {name}")
            b.setObjectName("navBtn")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setMinimumHeight(40)
            b.setChecked(i == 0)
            self._group.addButton(b, i)
            b.clicked.connect(lambda _=False, k=key: self.navigate.emit(k))
            self._buttons[key] = b
            outer.addWidget(b)

        outer.addStretch(1)

        # ---- DB footer (Stitch: "DB: Connected | v16.3 | donghua_db @ localhost")
        outer.addWidget(hline())
        footer = QWidget()
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(2, 8, 2, 0)
        fl.setSpacing(3)
        self.db_status = QLabel("DB: Connected")
        self.db_status.setStyleSheet(f"color: {T_EMERALD2}; font-size: 11px; font-weight: 700;")
        fl.addWidget(self.db_status)
        self.db_host = QLabel(self._db_host_text())
        self.db_host.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
        fl.addWidget(self.db_host)
        self._engine_lbl = QLabel("")
        self._engine_lbl.setStyleSheet(f"color: {T_MUTED}; font-size: 10px;")
        fl.addWidget(self._engine_lbl)
        outer.addWidget(footer)

    @staticmethod
    def _db_host_text() -> str:
        cfg = getattr(db, "DB_CONFIG", {})
        return f"donghua_db @ {cfg.get('host', 'localhost')}"

    def set_db_ok(self, ok: bool) -> None:
        self.db_status.setText("DB: Connected" if ok else "DB: Offline")
        self.db_status.setStyleSheet(
            f"color: {T_EMERALD2 if ok else T_ROSE}; font-size: 11px; font-weight: 700;"
        )

    def set_engine_version(self, version: str) -> None:
        self._ver_sub.setText(f"Desktop Hub  ·  yt-dlp {version}")
        self._engine_lbl.setText(f"Engine: yt-dlp {version}")

    def set_active(self, key: str) -> None:
        btn_ = self._buttons.get(key)
        if btn_:
            btn_.setChecked(True)

    def default_key(self) -> str:
        return "home"


# ==============================================================================
# Header bar (translucent top chrome per the Stitch screens)
# ==============================================================================


class HeaderBar(QWidget):
    """Back arrow + breadcrumb | global search | status chips."""

    back_clicked = pyqtSignal()
    search_submitted = pyqtSignal(str)
    quality_changed = pyqtSignal(str)
    add_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(64)
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 10, 24, 4)
        root.setSpacing(12)

        self.back_btn = icon_btn("‹", "Back")
        self.back_btn.clicked.connect(self.back_clicked.emit)
        root.addWidget(self.back_btn)

        self.crumb = QLabel("Library")
        self.crumb.setStyleSheet("font-size: 14px; font-weight: 700; color: #cbd5e1;")
        root.addWidget(self.crumb)
        root.addStretch(1)

        # ---- global search (URL paste → QuickUrlDialog; text → library filter)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Paste any video URL or search your library…")
        self.search.setFixedWidth(340)
        self.search.returnPressed.connect(lambda: self.search_submitted.emit(self.search.text().strip()))
        root.addWidget(self.search)

        # ---- quality chip (QComboBox styled as a pill)
        self.quality = QComboBox()
        self.quality.setObjectName("chip")
        for val, lab in QUALITY_OPTIONS:
            self.quality.addItem(lab, val)
        self.quality.setFixedHeight(28)
        self.quality.style().unpolish(self.quality)
        self.quality.style().polish(self.quality)
        self.quality.currentIndexChanged.connect(
            lambda i: self.quality_changed.emit(self.quality.currentData()))
        root.addWidget(self.quality)

        # ---- active download chip
        self.active_chip = QPushButton("Idle")
        self.active_chip.setObjectName("chip")
        self.active_chip.setFixedHeight(28)
        root.addWidget(self.active_chip)

        # ---- network chip
        self.net_chip = QPushButton("Fast / Online")
        self.net_chip.setObjectName("chipTri")
        self.net_chip.setFixedHeight(28)
        root.addWidget(self.net_chip)

        # add donghua quick button
        self.add_btn = icon_btn("＋", "Quick-add a URL")
        self.add_btn.clicked.connect(self.add_clicked.emit)
        root.addWidget(self.add_btn)

    def set_breadcrumb(self, text: str) -> None:
        self.crumb.setText(text)

    def set_active_text(self, text: str, busy: bool) -> None:
        self.active_chip.setText(text)
        self.active_chip.setObjectName("chipActive" if busy else "chip")
        self.net_chip.setText(("Downloading" if busy else "Fast / Online"))
        self.net_chip.setObjectName("chipEmerge" if busy else "chipTri")
        for w in (self.active_chip, self.net_chip):
            w.style().unpolish(w)
            w.style().polish(w)

    def set_speed(self, bps: float) -> None:
        if self.active_chip.objectName() == "chipActive" and bps:
            self.active_chip.setText(f"1 Active ({speed_text(bps)})")

    def set_quality_silent(self, value: str) -> None:
        idx = self.quality.findData(value)
        if idx >= 0:
            self.quality.blockSignals(True)
            self.quality.setCurrentIndex(idx)
            self.quality.blockSignals(False)


# ==============================================================================
# Disk usage scanner (async "x GB used" rows)
# ==============================================================================


class SizeScanner(QThread):
    scanned = pyqtSignal(int, int)   # series_id, bytes

    def __init__(self, jobs: List[Tuple[int, str]], parent=None):
        super().__init__(parent)
        self.jobs = jobs

    def run(self):
        for series_id, path in self.jobs:
            total = 0
            try:
                for root, _dirs, files in os.walk(os.path.expanduser(path)):
                    for f in files:
                        try:
                            total += os.path.getsize(os.path.join(root, f))
                        except OSError:
                            pass
            except OSError:
                total = 0
            self.scanned.emit(series_id, total)


# ==============================================================================
# Poster grid (wraps fixed-size cards like the Tailwind flex catalog)
# ==============================================================================


class PosterGrid(QWidget):
    """Wrapping grid of fixed-size child widgets (cards or rows)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items: List[QWidget] = []
        self._spacing = (14, 14)

    def set_items(self, items: List[QWidget]) -> None:
        for w in self._items:
            w.setParent(None)
            w.deleteLater()
        self._items = list(items)
        self.relayout()

    def relayout(self) -> None:
        cw = self.width() or (self.parent().width() if self.parent() else 900)
        ideal = self._items[0].sizeHint().width() if self._items else 200
        cols = max(1, int((cw - 4) // (ideal + self._spacing[0])))
        x = y = 0
        last_h = 0
        for i, w in enumerate(self._items):
            hint = w.sizeHint()
            if hint.width() <= 0:
                hint = w.size()
            w.setParent(self)
            w.setGeometry(x, y, max(hint.width(), 0), max(hint.height(), 0))
            last_h = hint.height()
            col = i % cols
            if col == cols - 1 or i == len(self._items) - 1:
                x = 0
                y += last_h + self._spacing[1]
            else:
                x += hint.width() + self._spacing[0]
        total_h = y if not self._items else max(1, y - (last_h + self._spacing[1]) // 2)
        self.setMinimumSize(1, y + (last_h if self._items else 0))
        self.setMaximumHeight((y + last_h if self._items else 0) or 16777215)
        self.updateGeometry()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self.relayout()


# ==============================================================================
# Poster tile (16:10, rimmed scrim, hover quick actions)
# ==============================================================================


class PosterWidget(QFrame):
    clicked = pyqtSignal(int)
    download_next = pyqtSignal(int)
    open_folder = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, series: Dict[str, Any], posters: Dict[int, str],
                 thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.series = series
        self.vid = posters.get(series["id"], "")
        self._pix: Optional[QPixmap] = None
        self.setFixedSize(216, 214)   # 16:10 poster @216 -> 216x135 + meta
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if self.vid:
            self._pix = thumbs.get(self.vid)
        dl = max(0, int(series.get("pending_episodes", 0) or 0))
        tot = int(series.get("total_episodes", 0) or 0)
        done = int(series.get("downloaded_episodes", 0) or 0)
        self._progress = pct(done, tot)

        # ---- action overlay (hover)
        self._hover_box = QWidget(self)
        hb = QHBoxLayout(self._hover_box)
        hb.setContentsMargins(10, 8, 10, 8)
        hb.setSpacing(6)
        self._hover_box.hide()
        pbtn = btn("▶  Download Next", "primary" if dl else "ghost", "Queue every pending episode")
        pbtn.setMinimumHeight(26)
        pbtn.setEnabled(dl > 0)
        pbtn.clicked.connect(lambda: self.download_next.emit(self.series["id"]))
        fbtn = icon_btn("⇗", "Open series folder")
        fbtn.clicked.connect(lambda: self.open_folder.emit(self.series["id"]))
        dbtn = icon_btn("␥", "Delete series")
        dbtn.clicked.connect(lambda: self.delete_requested.emit(self.series["id"]))
        hb.addWidget(pbtn, 1)
        hb.addWidget(fbtn)
        hb.addWidget(dbtn)

        # ---- meta labels under the poster
        self._title = QLabel(self.series["name"])
        self._title.setStyleSheet(f"color: {T_TEXT}; font-weight: 800; font-size: 12px;")
        self._sub = QLabel(f"{tot} EPS  ·  {done} ready")
        self._sub.setStyleSheet(f"color: {T_SEC}; font-size: 10px;")
        self._badge = None
        if tot and done == tot:
            self._badge = ("COMPLETE", T_EMERALD)
        elif dl and done == 0:
            self._badge = ("NEW", T_AMBER)
        elif dl:
            self._badge = (f"{dl} PENDING", T_PRIMARY)
        self._position_meta()

    def set_poster(self, pix: QPixmap) -> None:
        self._pix = pix
        self.update()

    def poster_id(self) -> str:
        return self.vid

    def _poster_h(self) -> int:
        return int(self.width() * 0.625)

    def _position_meta(self) -> None:
        w = self.width()
        ph = self._poster_h()
        self._hover_box.setGeometry(6, max(0, ph - 6), w - 12, 38)
        self._title.setGeometry(12, ph + 8, w - 24, 18)
        self._sub.setGeometry(12, ph + 26, w - 24, 14)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._position_meta()

    def enterEvent(self, ev) -> None:
        super().enterEvent(ev)
        self._hover_box.show()
        self._hover_box.raise_()

    def leaveEvent(self, ev) -> None:
        super().leaveEvent(ev)
        self._hover_box.hide()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.series["id"])
        super().mousePressEvent(ev)

    def paintEvent(self, ev) -> None:
        from PyQt6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ph = self._poster_h()
        w = self.width()

        # card body
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T_CARD))
        p.drawRoundedRect(0, 0, w, self.height(), 16, 16)

        # poster (cover-fit)
        if self._pix and not self._pix.isNull():
            img = self._pix.toImage()
            cw, ch = img.width(), img.height()
            scale = max(w / cw, ph / ch, 1e-6)
            tw, th = int(cw * scale), int(ch * scale)
            small = img.scaled(tw, th, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            dx = int((w - small.width()) / 2)
            dy = int((ph - small.height()) / 2)
            p.save()
            p.setClipRect(0, 0, w, ph)
            p.drawImage(dx, dy, small)
            p.restore()
        else:
            grad = QLinearGradient(0, 0, w, ph)
            grad.setColorAt(0, QColor("#122036"))
            grad.setColorAt(1, QColor(T_RAIL))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(0, 0, w, ph))
            p.setPen(QColor(T_MUTED))
            f = p.font()
            f.setPixelSize(30)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, ph), Qt.AlignmentFlag.AlignCenter, "▶")

        # gradient scrim on poster bottom
        scrim = QLinearGradient(0, float(ph - 70), 0, float(ph))
        scrim.setColorAt(0, QColor(2, 6, 23, 0))
        scrim.setColorAt(1, QColor(2, 6, 23, 200))
        p.fillRect(QRectF(0, ph - 70, w, 70), scrim)

        # dual-tone progress bar pinned to poster bottom
        if self._progress > 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#0e1a30"))
            p.drawRoundedRect(QRectF(10, ph - 10, w - 20, 5, ), 3, 3)
            p.setBrush(QColor(T_EMERALD if self._progress >= 100 else T_PRIMARY))
            p.drawRoundedRect(QRectF(10, ph - 10, max(6.0, (w - 20) * self._progress / 100.0), 5), 3, 3)

        # badge chip top-left
        if self._badge:
            label_, col = self._badge
            p.setFont(QFont(T_FONT, 8, QFont.Weight.Bold))
            fx = p.fontMetrics().horizontalAdvance(label_) + 16
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(col))
            p.drawRoundedRect(QRectF(10, 10, fx, 18), 9, 9)
            p.setPen(QColor("#04121f"))
            p.drawText(QRectF(10, 10, fx, 18), Qt.AlignmentFlag.AlignCenter, label_)

        p.setPen(QColor(T_PRIMARY if self._progress >= 100 else T_BORDER))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, self.height() - 1), 16, 16)


# ==============================================================================
# Series card = PosterWidget + disk-usage row (Stitch grid card)
# ==============================================================================


class SeriesCard(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, series: Dict[str, Any], posters: Dict[int, str],
                 thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.series = series
        self.poster = None
        self.setObjectName("card")
        self.setFixedSize(216, 274)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 10)
        lay.setSpacing(4)
        self.poster = PosterWidget(series, posters, thumbs)
        self.poster.setFixedSize(216, 214)
        lay.addWidget(self.poster, 0, Qt.AlignmentFlag.AlignHCenter)

        row = QHBoxLayout()
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(6)
        tot = int(series.get("total_episodes", 0) or 0)
        dl = int(series.get("downloaded_episodes", 0) or 0)
        left = QLabel(f"{max(0, tot - dl)} left")
        left.setStyleSheet(f"color: {T_MUTED}; font-size: 10px;")
        row.addWidget(left)
        row.addStretch(1)
        self.disk_lbl = QLabel("scanning…")
        self.disk_lbl.setStyleSheet(f"color: {T_MUTED}; font-size: 10px;")
        self.disk_lbl.setToolTip("Disk usage of the series folder")
        row.addWidget(self.disk_lbl)
        wrap = QWidget()
        wrap.setLayout(row)
        lay.addWidget(wrap)
        self.poster.clicked.connect(self.clicked.emit)

    def set_disk_size(self, size: int) -> None:
        self.disk_lbl.setText(human_size(size))


# ==============================================================================
# Compact list row (Library view)
# ==============================================================================


class CompactSeriesRow(QFrame):
    clicked = pyqtSignal(int)
    download_next = pyqtSignal(int)
    open_folder = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, series: Dict[str, Any], posters: Dict[int, str],
                 thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.series = series
        self.setObjectName("card")
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"QFrame#card:hover {{ background: {T_HOVER}; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)

        pw = PosterWidget(series, posters, thumbs)
        pw.setFixedSize(82, 60)
        pw._badge = None
        pw._hover_box.hide()
        lay.addWidget(pw)
        pw.clicked.connect(self.clicked.emit)
        pw.download_next.connect(self.download_next.emit)
        pw.open_folder.connect(self.open_folder.emit)
        pw.delete_requested.connect(self.delete_requested.emit)

        info = QVBoxLayout()
        info.setSpacing(1)
        name = QLabel(series["name"])
        name.setStyleSheet("font-weight: 800; font-size: 14px;")
        info.addWidget(name)
        created = str(series.get("created_at") or "")[:10]
        meta = QLabel(f"Added {created}" if created else "Donghua")
        meta.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
        info.addWidget(meta)
        col = QWidget()
        col.setLayout(info)
        lay.addWidget(col, 1)

        done = int(series.get("downloaded_episodes", 0) or 0)
        pend = int(series.get("pending_episodes", 0) or 0)
        tot = int(series.get("total_episodes", 0) or 0)
        tone = "emerald" if tot and done == tot else ("sky" if pend and done else "default")
        lay.addWidget(chip_tag(f"{done}/{tot} ready", tone))
        if pend:
            lay.addWidget(chip_tag(f"{pend} pending", "amber"))
        self.disk_lbl = QLabel("…")
        self.disk_lbl.setStyleSheet(f"color: {T_MUTED}; font-size: 11px; min-width: 64px;")
        self.disk_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.disk_lbl)

    def set_disk_size(self, size: int) -> None:
        self.disk_lbl.setText(human_size(size))


# ==============================================================================
# Hero spotlight (Stitch: 320px hero, gradient scrims, CTA buttons)
# ==============================================================================


class HeroSpotlight(QFrame):
    download_all = pyqtSignal(int)
    verify_disk = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("heroChrome")
        self._series: Dict[str, Any] = {}
        self._pix: Optional[QPixmap] = None
        self._vid = ""
        self.setFixedHeight(300)
        self.setMinimumHeight(300)

        self._inner = QLabel(self)
        self._inner.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        box = QWidget(self)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(36, 28, 36, 26)
        bl.setSpacing(10)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.chip_eps = chip_tag("0 EPS", "sky")
        self.chip_dir = chip_tag("", "default")
        self.chip_status = chip_tag("", "emerald")
        chips.addWidget(self.chip_eps)
        chips.addWidget(self.chip_dir)
        chips.addWidget(self.chip_status)
        chips.addStretch(1)
        bl.addLayout(chips)

        self.title = QLabel("No donghua yet")
        self.title.setStyleSheet("font-size: 30px; font-weight: 800; color: #f8fafc;")
        bl.addWidget(self.title)

        self.desc = QLabel("Register your first series from the Add Donghua wizard to see it spotlighted here.")
        self.desc.setStyleSheet(f"color: {T_SEC}; font-size: 13px;")
        self.desc.setMaximumWidth(560)
        self.desc.setWordWrap(True)
        bl.addWidget(self.desc)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.cta = btn("▶  Download Next Pending", "primary", "Queue every pending episode of this series")
        self.cta.clicked.connect(lambda: self.download_all.emit(self.series_id))
        self.verify = btn("⚡  Verify / Scan Disk", "ghost", "Re-sync this series against its downloaded.txt archive")
        self.verify.clicked.connect(lambda: self.verify_disk.emit(self.series_id))
        row.addWidget(self.cta)
        row.addWidget(self.verify)
        row.addStretch(1)
        bl.addLayout(row)

        box.setGeometry(0, 0, 900, 300)

    series_id: int = 0

    def set_series(self, series: Optional[Dict[str, Any]], poster: str,
                   thumbs: ThumbnailStore) -> None:
        self._series = series or {}
        self.series_id = int(self._series.get("id", 0) or 0)
        self._vid = poster or ""
        self._pix = thumbs.get(self._vid) if self._vid else None
        tot = int(self._series.get("total_episodes", 0) or 0)
        done = int(self._series.get("downloaded_episodes", 0) or 0)
        pend = int(self._series.get("pending_episodes", 0) or 0)
        path = self._series.get("save_dir") or ""
        self._inner.setHidden(not self._series)
        if self._series:
            self.title.setText(self._series.get("name") or "")
            self.desc.setText(self._series.get("description")
                              or "No description recorded for this series yet.")
            self.chip_eps.setText(f"{tot} EPS")
            self.chip_dir.setText(path.replace(os.path.expanduser("~"), "~"))
            if tot and done >= tot:
                self.chip_status.setText("COMPLETE")
            elif done:
                self.chip_status.setText(f"{done} of {tot} DOWNLOADED")
            else:
                self.chip_status.setText("NOT STARTED")
            self.cta.setEnabled(pend > 0)
            self.cta.setText(f"▶  Download Next Pending ({pend})")
        self.resizeEvent(None)  # type: ignore[arg-type]
        self.update()

    def _reposition(self) -> None:
        w = self.width()
        self._inner.setGeometry(56, 96, min(620, w - 120), 200)

    def resizeEvent(self, ev) -> None:
        if ev is not None:
            super().resizeEvent(ev)
        self._reposition()
        for c in self.findChildren(QWidget):
            pass
        box = self.findChildren(QWidget)
        if box:
            box[0].setGeometry(0, 0, self.width(), self.height())

    def paintEvent(self, ev) -> None:
        from PyQt6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T_CARD))
        p.drawRoundedRect(QRectF(0, 0, w, h), 24, 24)
        if self._pix and not self._pix.isNull():
            img = self._pix.toImage()
            cw, ch = img.width(), img.height()
            scale = max(w / cw, h / ch, 1e-6)
            small = img.scaled(int(cw * scale), int(ch * scale),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            p.save()
            p.setClipRect(QRectF(12, 12, w - 24, h - 24))
            p.setOpacity(0.30)
            p.drawImage((w - small.width()) // 2, 12 + (h - 24 - small.height()) // 3, small)
            p.restore()
        # cinematic scrims
        left = QLinearGradient(0, 0, w * 0.75, 0)
        left.setColorAt(0, QColor(2, 6, 23, 245))
        left.setColorAt(1, QColor(2, 6, 23, 0))
        p.fillRect(QRectF(0, 0, w * 0.75, h), left)
        bottom = QLinearGradient(0, h - 140, 0, h)
        bottom.setColorAt(0, QColor(2, 6, 23, 0))
        bottom.setColorAt(1, QColor(2, 6, 23, 235))
        p.fillRect(QRectF(0, h - 140, w, 140), bottom)
        p.setPen(QColor(T_BORDER))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 24, 24)


# ==============================================================================
# Telemetry strip (Stitch: daemon sync status row)
# ==============================================================================


class TelemetryStrip(QFrame):
    sync_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(52)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 8, 18, 8)
        lay.setSpacing(10)
        self.sync_chip = chip_tag("● Daemon Sync: Active", "emerald")
        lay.addWidget(self.sync_chip)
        self.display_chip = QLabel("Displaying 0 of 0 donghua")
        self.display_chip.setStyleSheet(f"color: {T_SEC}; font-size: 12px;")
        lay.addWidget(self.display_chip)
        self.disk_chip = QLabel("")
        self.disk_chip.setStyleSheet(f"color: {T_MUTED}; font-size: 12px;")
        lay.addWidget(self.disk_chip)
        lay.addStretch(1)
        sync_btn = btn("⟳  Sync All Incomplete", "chip", "Run archive re-sync for every series")
        sync_btn.clicked.connect(self.sync_requested.emit)
        lay.addWidget(sync_btn)

    def set_counts(self, shown: int, total: int, online: bool = True) -> None:
        self.display_chip.setText(f"Displaying {shown} of {total} donghua")
        self.sync_chip.setText(("● Daemon Sync: Active" if online else "◌ Daemon Sync: Offline"))


# ==============================================================================
# Home view (hero + filter tabs + telemetry + poster grid / list)
# ==============================================================================


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

    def set_sizes_pending(self) -> None:
        pass


# ==============================================================================
# Library view (compact rows)
# ==============================================================================


class LibraryView(QWidget):
    series_opened = pyqtSignal(int)
    series_download_all = pyqtSignal(int)
    series_folder = pyqtSignal(int)
    series_delete = pyqtSignal(int)
    add_requested = pyqtSignal()
    sync_requested = pyqtSignal()

    def __init__(self, thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs
        self._posters: Dict[int, str] = {}
        self._sizes: Dict[int, int] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 12, 28, 16)
        root.setSpacing(12)
        head = QHBoxLayout()
        head.addLayout(_title_block("Series Registry", "Every series, its folder and episode health at a glance."))
        head.addStretch(1)
        addb = btn("＋  Add Donghua", "primary")
        addb.clicked.connect(self.add_requested.emit)
        head.addWidget(addb)
        root.addLayout(head)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        self.host_lay = QVBoxLayout(host)
        self.host_lay.setContentsMargins(0, 4, 4, 0)
        self.host_lay.setSpacing(8)
        self.host = PosterGrid()
        self.host_lay.addWidget(self.host)
        self.host_lay.addStretch(1)
        self.empty = mk_label("No series registered yet — use Add Donghua.", "body", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.host_lay.addWidget(self.empty)
        self.area.setWidget(host)
        root.addWidget(self.area, 1)

    def load(self, series_list: List[Dict[str, Any]], posters: Dict[int, str]) -> None:
        self._posters = posters
        rows = [CompactSeriesRow(s, posters, self.thumbs) for s in series_list]
        for r in rows:
            r.clicked.connect(self.series_opened)
            r.download_next.connect(self.series_download_all)
            r.open_folder.connect(self.series_folder)
            r.delete_requested.connect(self.series_delete)
        self.host.set_items(rows)
        self.empty.setVisible(not rows)
        self.update_sizes(self._sizes)

    def update_sizes(self, sizes: Dict[int, int]) -> None:
        self._sizes.update(sizes)
        for w in self.host._items:
            data = getattr(w, "series", None)
            if data and data["id"] in self._sizes:
                w.set_disk_size(self._sizes[data["id"]])

    def update_poster(self, vid: str, pix: QPixmap) -> None:
        for w in self.host._items:
            pw = getattr(w, "poster", None)
            if pw and getattr(pw, "vid", "") == vid:
                pw.set_poster(pix)


def _title_block(title: str, sub: str) -> QVBoxLayout:
    v = QVBoxLayout()
    v.addWidget(mk_label(title, "titleLg"))
    v.addWidget(mk_label(sub, "body", "muted"))
    return v


# ==============================================================================
# Add URLs dialog (per-series quick-import drawer)
# ==============================================================================


class AddUrlsDialog(QDialog):
    """Bulk-paste drawer: `URL   # Episode title`, start index, auto-download."""

    def __init__(self, series: Dict[str, Any], next_ep: int,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Episodes — {series.get('name', '')}")
        self.setMinimumSize(660, 560)
        self.setStyleSheet(app_stylesheet())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(12)

        lay.addWidget(mk_label("Quick Import Drawer", "titleMd"))
        lay.addWidget(mk_label("Paste one or many video URLs. Optional format: URL   # Episode title",
                               "body", "muted"))

        self.urls = QTextEdit()
        self.urls.setPlaceholderText(
            "https://youtu.be/XXXXXXXXX  # Episode 12 - The Divine Trail\nhttps://www.youtube.com/watch?v=YYYYYYYYY")
        self.urls.setMinimumHeight(180)
        self.urls.textChanged.connect(self._update_badge)
        lay.addWidget(self.urls)

        badge_row = QHBoxLayout()
        self.badge = chip_tag("0 valid URLs  ·  0 duplicates", "default")
        badge_row.addWidget(self.badge)
        badge_row.addStretch(1)
        lay.addLayout(badge_row)

        opts = QGridLayout()
        opts.setHorizontalSpacing(18)
        opts.setVerticalSpacing(8)
        opts.addWidget(label_caps("Start index / episode number"), 0, 0)
        self.start_at = QSpinBox()
        self.start_at.setRange(1, 99999)
        self.start_at.setValue(max(1, next_ep))
        self.start_at.setFixedWidth(120)
        opts.addWidget(self.start_at, 1, 0)
        opts.addWidget(label_caps("Numbering"), 0, 1)
        num_box = QComboBox()
        num_box.addItems(["Sequential (n, n+1, …)", "From URL titles", "No numbering"])
        num_box.setFixedWidth(210)
        opts.addWidget(num_box, 1, 1)
        opts.setColumnStretch(2, 1)
        lay.addLayout(opts)

        self.auto_dl = QCheckBox("Start downloading these episodes immediately after saving")
        self.auto_dl.setChecked(True)
        lay.addWidget(self.auto_dl)

        lay.addStretch(1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = btn("Cancel", "ghost")
        cancel.clicked.connect(self.reject)
        save = btn("💾  Save to Library Only", "ghost", "Register URLs without downloading")
        save.clicked.connect(lambda: self.done(1))
        dl = btn("⤓  Save & Download Immediately", "primary", "Register and queue every URL")
        dl.clicked.connect(lambda: self.done(2))
        btns.addWidget(cancel)
        btns.addWidget(save)
        btns.addWidget(dl)
        lay.addLayout(btns)

        self._mode = None
        self._numbering = num_box

    def _update_badge(self) -> None:
        items = parse_bulk_urls(self.urls.toPlainText())
        dups = sum(1 for i in items if i["dup"])
        self.badge.setText(f"{len(items)} valid URLs  ·  {dups} duplicated  ·  {len(items) - dups} new")
        self.badge.setStyleSheet(
            f"background: {'#10b98122' if items else '#f43f5e22'};"
            f"border: 1px solid {'#10b98166' if items else '#f43f5e66'};"
            "border-radius: 999px; color: #4edea3; font-size: 11px; font-weight: 700;"
            "padding: 2px 10px;")

    def result_entries(self):
        return self._mode

    # run helper -----------------------------------------------------------
    def collect(self):
        """Returns (mode, entries, next_index, auto) or None when cancelled."""
        code = self.exec()
        if code == 0:
            return None
        mode = "download" if code == 2 or self.auto_dl.isChecked() else "save"
        if code == 1:
            mode = "save"
        entries = parse_bulk_urls(self.urls.toPlainText())
        if self._numbering.currentIndex() == 0:
            n = self.start_at.value()
            for e in entries:
                e["num"] = n
                n += 1
        elif self._numbering.currentIndex() == 1:
            for e in entries:
                m = re.search(r"[Ee]p(?:isode)?\s*-?\s*(\d+)", e["title"])
                e["num"] = int(m.group(1)) if m else None
        else:
            for e in entries:
                e["num"] = None
        return mode, entries, self.start_at.value(), self.auto_dl.isChecked()


# ==============================================================================
# Episode row (registry line with per-row CRUD)
# ==============================================================================


class EpisodeRow(QFrame):
    download = pyqtSignal(dict)
    copy_url = pyqtSignal(str)
    edit_ep = pyqtSignal(dict)
    del_ep = pyqtSignal(dict)
    retry = pyqtSignal(dict)

    def __init__(self, ep: Dict[str, Any], index: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ep = ep
        self.setObjectName("card")
        self.setFixedHeight(54)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(10)

        num = ep.get("episode_number") or index + 1
        numlab = QLabel(f"#{num:>3}")
        numlab.setStyleSheet(f"color: {T_MUTED}; font-family: monospace; font-size: 12px;")
        numlab.setFixedWidth(48)
        lay.addWidget(numlab)

        title = QLabel(ep.get("title") or ep.get("url") or "")
        title.setStyleSheet("font-weight: 700; font-size: 13px;")
        title.setToolTip(ep.get("url") or "")
        lay.addWidget(title, 1)

        status = ep.get("status") or "pending"
        tone = {"downloaded": "emerald", "failed": "rose", "queued": "sky", "pending": "default"}.get(status, "default")
        lay.addWidget(chip_tag({"downloaded": "✔ READY", "failed": "✖ FAILED",
                                "queued": "QUEUED", "pending": "PENDING"}.get(status, status.upper()), tone))

        dl = icon_btn("⤓", "Download this episode now")
        dl.clicked.connect(lambda: self.download.emit(self.ep))
        cp = icon_btn("⧉", "Copy URL")
        cp.clicked.connect(lambda: self.copy_url.emit(self.ep.get("url", "")))
        ed = icon_btn("✎", "Edit title / episode number")
        ed.clicked.connect(lambda: self.edit_ep.emit(self.ep))
        de = icon_btn("␥", "Delete from registry")
        de.clicked.connect(lambda: self.del_ep.emit(self.ep))
        for b in (dl, cp, ed, de):
            lay.addWidget(b)
        if status == "failed":
            ret = icon_btn("⟳", "Retry failed download")
            ret.clicked.connect(lambda: self.retry.emit(self.ep))
            lay.addWidget(ret)


# ==============================================================================
# Series detail (Stitch screen 2 — Episode Manager)
# ==============================================================================


class SeriesDetailView(QWidget):
    back_requested = pyqtSignal()
    download_urls_requested = pyqtSignal(int, list, str)   # series_id, urls, quality
    open_folder = pyqtSignal(str)
    sync_series = pyqtSignal(int)
    episode_changed = pyqtSignal(int)                      # series_id → refresh
    toast = pyqtSignal(str, bool)

    TABS = [("pending", "Queued"), ("downloaded", "Downloaded"), ("failed", "Failed")]

    def __init__(self, thumbs: ThumbnailStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.thumbs = thumbs
        self.series: Dict[str, Any] = {}
        self._episodes: List[Dict[str, Any]] = []
        self._tab = "all"
        self._query = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 8, 28, 16)
        root.setSpacing(12)

        # ---- top info card
        info = QFrame()
        info.setObjectName("card")
        il = QHBoxLayout(info)
        il.setContentsMargins(20, 18, 20, 18)
        il.setSpacing(20)

        self.poster = QLabel()
        self.poster.setFixedSize(240, 150)
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setStyleSheet("border-radius: 12px; background: #122036;")
        il.addWidget(self.poster)

        mid = QVBoxLayout()
        mid.setSpacing(6)
        top = QHBoxLayout()
        self.chip_eps = chip_tag("0 EPS", "sky")
        self.chip_status = chip_tag("", "emerald")
        top.addWidget(self.chip_eps)
        top.addWidget(self.chip_status)
        top.addStretch(1)
        self.edit_btn = icon_btn("✎", "Edit series name / description / folder")
        self.edit_btn.clicked.connect(self._edit_series)
        top.addWidget(self.edit_btn)
        mid.addLayout(top)
        self.title = mk_label("—", "titleLg")
        mid.addWidget(self.title)
        self.sub = mk_label("", "body", "muted")
        mid.addWidget(self.sub)
        tags = QHBoxLayout()
        tags.setSpacing(6)
        for tname in ("Donghua", "Ongoing"):
            tags.addWidget(chip_tag(tname))
        self.tags_row = tags
        mid.addLayout(tags)

        path_row = QHBoxLayout()
        self.path_lab = mk_label("", "codePill")
        self.path_lab.setStyleSheet(f"color: {T_PRIMARY}; font-family: monospace; font-size: 12px;")
        path_row.addWidget(self.path_lab, 1)
        openb = btn("⇗  Open in File Manager", "ghost", "")
        openb.setMinimumHeight(30)
        openb.clicked.connect(lambda: self.open_folder.emit(self.series.get("save_dir", "")))
        path_row.addWidget(openb)
        mid.addLayout(path_row)
        il.addLayout(mid, 1)

        # ---- sync progress column
        syncbox = QVBoxLayout()
        syncbox.setSpacing(6)
        self.disk_line = mk_label("0 GB used  ·  0 of 0 cached", "titleSm")
        syncbox.addWidget(self.disk_line)
        self.sync_bar = styled_bar("primary")
        syncbox.addWidget(self.sync_bar)
        progress_row = QHBoxLayout()
        progress_row.addWidget(label_caps("Sync Progress"))
        progress_row.addStretch(1)
        self.sync_pct = mk_label("0% Complete", "titleMd")
        progress_row.addWidget(self.sync_pct)
        syncbox.addLayout(progress_row)
        counts_row = QHBoxLayout()
        counts_row.setSpacing(8)
        self.chip_local = chip_tag("LOCAL FILES  ·  0", "emerald")
        self.chip_queue = chip_tag("QUEUE  ·  0", "amber")
        counts_row.addWidget(self.chip_local)
        counts_row.addWidget(self.chip_queue)
        counts_row.addStretch(1)
        syncbox.addLayout(counts_row)

        qlab = label_caps("Quality")
        syncbox.addWidget(qlab)
        self.quality = QComboBox()
        self.quality.setObjectName("chip")
        for val, lab in QUALITY_OPTIONS:
            self.quality.addItem(lab, val)
        self.quality.setFixedHeight(30)
        syncbox.addWidget(self.quality)

        dl_all = btn("▶  Download All Pending", "primary")
        dl_all.clicked.connect(self._download_all)
        syncbox.addWidget(dl_all)
        verify = btn("⚡  Verify / Scan Disk", "ghost")
        verify.clicked.connect(lambda: self.sync_series.emit(self.series_id))
        syncbox.addWidget(verify)
        addurls = btn("＋  Add Episode URLs", "ghost")
        addurls.clicked.connect(self._quick_import)
        syncbox.addWidget(addurls)
        il.addLayout(syncbox)
        root.addWidget(info)

        # ---- registry tabs
        reg_head = QHBoxLayout()
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self.tab_buttons: Dict[str, QPushButton] = {}
        for key, name in [("all", "All")] + self.TABS:
            b = QPushButton(name)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(key == "all")
            self._tab_group.addButton(b)
            b.clicked.connect(lambda _=False, k=key: self.set_tab(k))
            self.tab_buttons[key] = b
            reg_head.addWidget(b)
        reg_head.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter episodes…")
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(self._render_rows)
        reg_head.addWidget(self.search)
        root.addLayout(reg_head)

        self.rows_host = PosterGrid()
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        hl = QVBoxLayout(host)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.rows_host)
        hl.addStretch(1)
        self.empty = mk_label("No episodes in this bucket.", "body", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(self.empty)
        self.area.setWidget(host)
        root.addWidget(self.area, 1)

    # ---- data ---------------------------------------------------------------
    @property
    def series_id(self) -> int:
        return int(self.series.get("id", 0) or 0)

    def load(self, series: Dict[str, Any], poster_vid: str) -> None:
        self.series = series
        vid = poster_vid or ""
        pix = self.thumbs.get(vid) if vid else None
        if pix and not pix.isNull():
            self.poster.setPixmap(
                pix.scaled(self.poster.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation))
        tot = int(series.get("total_episodes", 0) or 0)
        done = int(series.get("downloaded_episodes", 0) or 0)
        pend = int(series.get("pending_episodes", 0) or 0)
        self.chip_eps.setText(f"{tot} EPS")
        self.chip_status.setText("COMPLETE" if tot and done >= tot else
                                 ("AUTO-TRACKING: Active" if pend else "NOT STARTED"))
        self.title.setText(series.get("name") or "")
        self.sub.setText(f"Key: {series.get('key', '')}  ·  Added {str(series.get('created_at') or '')[:10]}")
        self.path_lab.setText((series.get("save_dir") or "").replace(os.path.expanduser("~"), "~"))
        try:
            self._episodes = db.get_episodes(self.series_id) or []
        except Exception as exc:
            self._episodes = []
            self.toast.emit(f"Could not load episodes: {exc}", False)
        n_failed = sum(1 for e in self._episodes if e.get("status") == "failed")
        self.tab_buttons["failed"].setText(f"Failed ({n_failed})")
        self.render_stats()

    def render_stats(self) -> None:
        tot = len(self._episodes)
        done = sum(1 for e in self._episodes if e.get("status") == "downloaded")
        failed = sum(1 for e in self._episodes if e.get("status") == "failed")
        pend = tot - done - failed
        self.disk_line.setText("scanning disk…" if tot else "No episodes yet")
        self.sync_bar.setValue(pct(done, tot))
        self.sync_pct.setText(f"{pct(done, tot)}% Complete")
        self.chip_local.setText(f"LOCAL FILES  ·  {done}")
        self.chip_queue.setText(f"QUEUE  ·  {max(0, pend)}" + (f"  ·  {failed} FAILED" if failed else ""))
        self._render_rows()

    def update_disk_line(self, size: int) -> None:
        done = sum(1 for e in self._episodes if e.get("status") == "downloaded")
        self.disk_line.setText(f"{human_size(size)} used  ·  {done} of {len(self._episodes)} cached")

    def set_tab(self, key: str) -> None:
        self._tab = key
        self._render_rows()

    def _render_rows(self) -> None:
        text = (self.search.text() or "").strip().lower()
        rows = []
        for i, e in enumerate(self._episodes):
            st = e.get("status") or "pending"
            if self._tab != "all" and self._tab != st:
                continue
            if text and text not in (e.get("title") or "").lower() and text not in (e.get("url") or "").lower():
                continue
            rows.append(EpisodeRow(e, i))
            last = rows[-1]
            last.download.connect(self._download_one)
            last.copy_url.connect(self._copy)
            last.edit_ep.connect(self._edit_episode)
            last.del_ep.connect(self._delete_episode)
            last.retry.connect(self._download_one)
        self.rows_host.set_items(rows)
        self.empty.setVisible(not rows)

    # ---- row handlers -------------------------------------------------------
    def _copy(self, url: str) -> None:
        QApplication.clipboard().setText(url)
        self.toast.emit("URL copied to clipboard.", True)

    def _download_one(self, ep: Dict[str, Any]) -> None:
        self.download_urls_requested.emit(self.series_id,
                                          [ep.get("url")], self.quality.currentData())

    def _download_all(self) -> None:
        urls = [e["url"] for e in self._episodes if e.get("status") != "downloaded"]
        if not urls:
            self.toast.emit("Every episode is already downloaded.", True)
            return
        self.download_urls_requested.emit(self.series_id, urls, self.quality.currentData())

    def _quick_import(self) -> None:
        next_num = len(self._episodes) + 1
        dlg = AddUrlsDialog(self.series, next_num, self)
        got = dlg.collect()
        if not got:
            return
        mode, entries, _start, _auto = got
        self._save_entries(entries)
        if mode == "download":
            self.download_urls_requested.emit(
                self.series_id, [e["url"] for e in entries], self.quality.currentData())

    def _save_entries(self, entries: List[Dict[str, Any]]) -> None:
        added = skipped = 0
        for e in entries:
            try:
                res = db.add_episode(self.series_id, e["url"], title=e.get("title", ""),
                                     episode_number=e.get("num"))
                added += 1 if res else 0
            except Exception:
                skipped += 1
        self.toast.emit(f"Imported: {added} added · {skipped} skipped", True)
        self.episode_changed.emit(self.series_id)

    def _edit_episode(self, ep: Dict[str, Any]) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Episode")
        dlg.setStyleSheet(app_stylesheet())
        lay = QVBoxLayout(dlg)
        lay.addWidget(mk_label("Episode details", "titleMd"))
        title_in = QLineEdit(ep.get("title") or "")
        title_in.setPlaceholderText("Title")
        num_in = QSpinBox()
        num_in.setRange(0, 99999)
        num_in.setValue(int(ep.get("episode_number") or 0))
        url_in = QLineEdit(ep.get("url") or "")
        for lab, widget in (("Title", title_in), ("Episode number", num_in), ("URL", url_in)):
            row = QHBoxLayout()
            row.addWidget(label_caps(lab))
            row.addWidget(widget, 1)
            wrap = QWidget()
            wrap.setLayout(row)
            lay.addWidget(wrap)
        bb = QHBoxLayout()
        bb.addStretch(1)
        c = btn("Cancel", "ghost")
        c.clicked.connect(dlg.reject)
        s = btn("Save", "primary")
        s.clicked.connect(dlg.accept)
        bb.addWidget(c)
        bb.addWidget(s)
        lay.addLayout(bb)
        if dlg.exec() == 1:
            try:
                db.update_episode_fields(
                    ep["id"],
                    title=title_in.text(),
                    episode_number=num_in.value() or None,
                    url=url_in.text() if url_in.text() else None,
                )
                self.toast.emit("Episode updated.", True)
                self.episode_changed.emit(self.series_id)
            except Exception as exc:
                self.toast.emit(f"Update failed: {exc}", False)

    def _delete_episode(self, ep: Dict[str, Any]) -> None:
        try:
            db.delete_episode(ep["id"])
            self.toast.emit(f"Removed #{ep.get('episode_number') or '?'} from the registry.", True)
            self.episode_changed.emit(self.series_id)
        except Exception as exc:
            self.toast.emit(f"Delete failed: {exc}", False)

    def _edit_series(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Series")
        dlg.setStyleSheet(app_stylesheet())
        dlg.setMinimumWidth(460)
        lay = QVBoxLayout(dlg)
        lay.addWidget(mk_label("Series details", "titleMd"))
        name_in = QLineEdit(self.series.get("name") or "")
        desc_in = QTextEdit(self.series.get("description") or "")
        desc_in.setMinimumHeight(70)
        dir_row = QHBoxLayout()
        dir_in = QLineEdit((self.series.get("save_dir") or "").replace(os.path.expanduser("~"), "~"))
        browse = btn("Browse…", "ghost")
        browse.setMinimumHeight(30)

        def _pick():
            path = QFileDialog.getExistingDirectory(dlg, "Series folder",
                                                    os.path.expanduser(dir_in.text()))
            if path:
                dir_in.setText(path)
        browse.clicked.connect(_pick)
        dir_row.addWidget(dir_in, 1)
        dir_row.addWidget(browse)
        for lab, wrap in (("Name", name_in), ("Description", desc_in)):
            row = QVBoxLayout()
            row.addWidget(label_caps(lab))
            row.addWidget(wrap)
            holder = QWidget()
            holder.setLayout(row)
            lay.addWidget(holder)
        lay.addWidget(label_caps("Save folder"))
        row = QWidget()
        row.setLayout(dir_row)
        lay.addWidget(row)
        bb = QHBoxLayout()
        bb.addStretch(1)
        c = btn("Cancel", "ghost")
        c.clicked.connect(dlg.reject)
        s = btn("Save", "primary")
        s.clicked.connect(dlg.accept)
        bb.addWidget(c)
        bb.addWidget(s)
        lay.addLayout(bb)
        if dlg.exec() == 1:
            try:
                db.update_series(self.series_id,
                                 name=name_in.text() or None,
                                 description=desc_in.toPlainText(),
                                 save_dir=resolve_path(dir_in.text()) if dir_in.text() else None)
                self.toast.emit("Series updated.", True)
                self.episode_changed.emit(self.series_id)
            except Exception as exc:
                self.toast.emit(f"Update failed: {exc}", False)


# ==============================================================================
# Storage tile (Stitch: Videos / Downloads / Documents / Custom, free-space chip)
# ==============================================================================


class StorageCard(QPushButton):
    chosen = pyqtSignal(str)   # resolved base dir

    def __init__(self, glyph: str, name: str, default_dir: str,
                 recommended: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(96)
        self.setStyleSheet(f"""
            QPushButton {{ background: {T_RAIL}; border: 1px solid {T_BORDER};
                           border-radius: 16px; text-align: left; }}
            QPushButton:checked {{ border: 2px solid {T_PRIMARY}; background: #122036; }}
            QPushButton:hover {{ background: #17233c; }}
        """)
        self._dir = default_dir
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 14, 10)
        lay.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(8)
        self._glyph = QLabel(glyph)
        self._glyph.setStyleSheet(f"font-size: 20px; color: {T_PRIMARY};")
        top.addWidget(self._glyph)
        self._name = QLabel(name)
        self._name.setStyleSheet("font-weight: 800; font-size: 14px;")
        top.addWidget(self._name)
        top.addStretch(1)
        if recommended:
            top.addWidget(chip_tag("Recommended", "sky"))
        self._free = QLabel("checking…")
        self._free.setStyleSheet(f"color: {T_SEC}; font-size: 11px;")
        top.addWidget(self._free)
        lay.addLayout(top)
        self._path = QLabel(default_dir.replace(os.path.expanduser("~"), "~"))
        self._path.setStyleSheet(f"color: {T_MUTED}; font-size: 11px; font-family: monospace;")
        lay.addWidget(self._path)
        self.toggled.connect(self._on_toggle)

    def refresh_free(self) -> None:
        free = disk_free(self._dir)
        self._free.setText(f"{human_size(free)} free" if free is not None else "unavailable")

    def set_dir(self, path: str) -> None:
        self._dir = path
        self._path.setText(path.replace(os.path.expanduser("~"), "~"))
        self.refresh_free()

    def dir(self) -> str:
        return self._dir

    def _on_toggle(self, checked: bool) -> None:
        if checked:
            self.chosen.emit(self._dir)


# ==============================================================================
# Add Donghua wizard (Stitch screen 3 — Registration Wizard)
# ==============================================================================


class AddWizard(QDialog):
    series_created = pyqtSignal(int, list, bool, str)  # series_id, urls, download_now, quality

    def __init__(self, settings: Dict[str, str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Add Donghua — Registration Wizard")
        self.setMinimumSize(760, 640)
        self.setStyleSheet(app_stylesheet())
        self.created_id: Optional[int] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(14)

        head = QVBoxLayout()
        head.addWidget(mk_label("Register a Donghua", "titleLg"))
        head.addWidget(mk_label("Three quick steps: identity, storage, episodes.", "body", "muted"))
        root.addLayout(head)

        # ---- step pills
        pills_row = QHBoxLayout()
        pills_row.setSpacing(10)
        self.pills: List[QLabel] = []
        for i, name in enumerate(("1  Series identity", "2  Storage preferences",
                                  "3  Episodes & finish")):
            pill = chip_tag(name)
            pill.setStyleSheet(
                f"background: {T_CARD}; border: 1px solid #33415566;"
                f"border-radius: 999px; color: {T_SEC};"
                "font-size: 11px; font-weight: 700; padding: 3px 12px;")
            self.pills.append(pill)
            pills_row.addWidget(pill)
        pills_row.addStretch(1)
        root.addLayout(pills_row)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self._build_step1()
        self._build_step2()
        self._build_step3()

        # ---- navigation
        nav = QHBoxLayout()
        self.back_btn = btn("‹  Back", "ghost")
        self.back_btn.clicked.connect(self._go_back)
        self.next_btn = btn("Next  ›", "primary")
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)
        self._update_pills()

    # ---- step 1: identity ------------------------------------------------------
    def _build_step1(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(label_caps("Series title"))
        self.name_in = QLineEdit()
        self.name_in.setPlaceholderText("e.g. Throne of Seal")
        self.name_in.textChanged.connect(self._preview_key)
        lay.addWidget(self.name_in)
        self.key_prev = QLabel("")
        self.key_prev.setStyleSheet(f"color: {T_MUTED}; font-size: 11px; font-family: monospace;")
        lay.addWidget(self.key_prev)
        lay.addWidget(label_caps("Description / synopsis"))
        self.desc_in = QTextEdit()
        self.desc_in.setPlaceholderText("A short synopsis shown on the series detail page…")
        self.desc_in.setMinimumHeight(90)
        lay.addWidget(self.desc_in)
        lay.addStretch(1)
        self.stack.addWidget(page)

    def _preview_key(self, text: str) -> None:
        self.key_prev.setText(f"key → {db.sanitize_slug(text or '')}")

    # ---- step 2: storage ---------------------------------------------------
    def _build_step2(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(10)
        base = self.settings.get("global_save_dir", "~/Videos")
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.tile_videos = StorageCard("⌂", "Videos", os.path.expanduser("~/Videos"), recommended=True)
        self.tile_downloads = StorageCard("⤓", "Downloads", os.path.expanduser("~/Downloads"))
        self.tile_docs = StorageCard("▤", "Documents", os.path.expanduser("~/Documents"))
        self.tiles = [self.tile_videos, self.tile_downloads, self.tile_docs, None]
        tiles.addWidget(self.tile_videos)
        tiles.addWidget(self.tile_downloads)
        tiles.addWidget(self.tile_docs)
        custom_box = QVBoxLayout()
        self.tile_custom = StorageCard("✎", "Custom…", base)
        custom_box.addWidget(self.tile_custom)
        self.custom_path = QLineEdit()
        self.custom_path.setPlaceholderText("Type or browse a folder path…")
        self.custom_path.textChanged.connect(lambda t: self.tile_custom.set_dir(resolve_path(t)))
        brow = QHBoxLayout()
        brow.addWidget(self.custom_path, 1)
        browse = btn("Browse…", "ghost")
        browse.setMinimumHeight(28)

        def _pick():
            path = QFileDialog.getExistingDirectory(self, "Choose save location",
                                                    os.path.expanduser(self.custom_path.text() or base))
            if path:
                self.custom_path.setText(path)
        browse.clicked.connect(_pick)
        brow.addWidget(browse)
        custom_box.addWidget(self.custom_path)
        customw = QWidget()
        customw.setLayout(custom_box)
        tiles.addWidget(customw, 1)
        self.tiles[3] = self.tile_custom
        for t in self.tiles:
            t.toggled.connect(self._on_tile)
            t.refresh_free()
        self.tile_videos.setChecked(True)
        holder = QWidget()
        holder.setLayout(tiles)
        lay.addWidget(holder)

        self.subfolder_check = QCheckBox(
            "Create a per-donghua sub-folder inside the selected location (recommended)")
        self.subfolder_check.setChecked(True)
        lay.addWidget(self.subfolder_check)

        prev_row = QHBoxLayout()
        prev_row.addWidget(label_caps("Resolved folder"))
        self.path_prev = QLabel("")
        self.path_prev.setStyleSheet(f"color: {T_PRIMARY}; font-family: monospace; font-size: 12px;")
        prev_row.addWidget(self.path_prev, 1)
        self.free_prev = chip_tag("")
        prev_row.addWidget(self.free_prev)
        lay.addLayout(prev_row)

        qrow = QHBoxLayout()
        qrow.addWidget(label_caps("Preferred quality"))
        qual = QComboBox()
        qual.setObjectName("chip")
        for val, lab in QUALITY_OPTIONS:
            qual.addItem(lab, val)
        qual.setCurrentText(quality_label(self.settings.get("default_quality", "720p")))
        self.quality_box = qual
        qual.setFixedHeight(30)
        qrow.addWidget(qual)
        qrow.addStretch(1)
        lay.addLayout(qrow)
        lay.addStretch(1)
        self._current_tile_dir = self.tile_videos.dir()
        self.path_prev.setText(self._resolve_save_dir())
        self._update_free()
        self.stack.addWidget(page)

    def _on_tile(self, checked: bool) -> None:
        if not checked or not hasattr(self, "path_prev"):
            return
        src = self.sender()
        if src in self.tiles:
            self._current_tile_dir = src.dir()
        self.path_prev.setText(self._resolve_save_dir())
        self._update_free()

    def _resolve_save_dir(self) -> str:
        base = self._current_tile_dir
        name = self.name_in.text().strip()
        if self.subfolder_check.isChecked() and name:
            return os.path.join(base, db.sanitize_slug(name))
        return base

    def _update_free(self) -> None:
        free = disk_free(self._resolve_save_dir())
        self.free_prev.setText(f"{human_size(free)} free" if free is not None else "path unavailable")

    # ---- step 3: episodes ---------------------------------------------------
    def _build_step3(self) -> None:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(label_caps("Bulk paste episode links"))
        self.urls = QTextEdit()
        self.urls.setPlaceholderText(
            "One URL per line, optional title after '#':\nhttps://youtu.be/AAAAAAAAA  # Episode 1"
        )
        self.urls.setMinimumHeight(190)
        self.urls.textChanged.connect(self._step3_badge)
        lay.addWidget(self.urls)
        row = QHBoxLayout()
        self.badge = chip_tag("0 valid URLs  ·  0 duplicates")
        row.addWidget(self.badge)
        row.addStretch(1)
        self.start_at = QSpinBox()
        self.start_at.setRange(1, 99999)
        self.start_at.setValue(1)
        row.addWidget(label_caps("Start index"))
        row.addWidget(self.start_at)
        lay.addLayout(row)
        self.auto_dl = QCheckBox("Save & Download Immediately (queue all N videos now)")
        self.auto_dl.setChecked(True)
        lay.addWidget(self.auto_dl)
        lay.addStretch(1)
        self.stack.addWidget(page)

    def _step3_badge(self) -> None:
        items = parse_bulk_urls(self.urls.toPlainText())
        dups = sum(1 for i in items if i["dup"])
        self.badge.setText(f"{len(items)} valid URLs  ·  {dups} duplicated")
        self.badge.setStyleSheet(
            f"background: {'#10b98122' if items else '#f43f5e22'};"
            f"border: 1px solid {'#10b98166' if items else '#f43f5e66'};"
            "border-radius: 999px; color: #4edea3; font-size: 11px; font-weight: 700;"
            "padding: 2px 10px;")

    # ---- navigation ---------------------------------------------------------
    def _current_step(self) -> int:
        return self.stack.currentIndex()

    def _go_back(self) -> None:
        if self._current_step() > 0:
            self.stack.setCurrentIndex(self._current_step() - 1)
            self.next_btn.setText("Next  ›")
            self._update_pills()
        else:
            self.reject()

    def _go_next(self) -> None:
        step = self._current_step()
        if step == 0:
            if not self.name_in.text().strip():
                self.name_in.setFocus()
                self.name_in.setStyleSheet(f"border: 1px solid {T_ROSE};")
                return
            self.stack.setCurrentIndex(1)
            self.path_prev.setText(self._resolve_save_dir())
            self._update_free()
        elif step == 1:
            self.stack.setCurrentIndex(2)
            self.next_btn.setText("💾  Save & Finish")
        else:
            self._finish()

    def _update_pills(self) -> None:
        cur = self._current_step()
        for i, pill in enumerate(self.pills):
            if i == cur:
                pill.setStyleSheet(
                    f"background: {T_PRIMARY}; border-radius: 999px; color: {T_ON_PRIMARY};"
                    "font-size: 11px; font-weight: 800; padding: 3px 12px;")
            else:
                pill.setStyleSheet(
                    f"background: {T_CARD}; border: 1px solid #33415566;"
                    f"border-radius: 999px; color: {T_SEC};"
                    "font-size: 11px; font-weight: 700; padding: 3px 12px;")

    # ---- finish ---------------------------------------------------------
    def _finish(self) -> None:
        name = self.name_in.text().strip()
        save_dir = self._resolve_save_dir()
        try:
            os.makedirs(save_dir, exist_ok=True)
        except OSError as exc:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid folder", f"Cannot create folder:\n{exc}")
            return
        entries = parse_bulk_urls(self.urls.toPlainText())
        try:
            series = db.create_series(name, save_dir=save_dir,
                                      description=self.desc_in.toPlainText())
        except Exception as exc:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Database error", str(exc))
            return
        sid = int(series["id"])
        n = self.start_at.value()
        added = 0
        try:
            for e in entries:
                if e["dup"]:
                    continue
                db.add_episode(sid, e["url"], title=e["title"], episode_number=n)
                n += 1
                added += 1
        except Exception:
            pass
        self.created_id = sid
        urls = []
        if self.auto_dl.isChecked():
            urls = [e["url"] for e in entries if not e["dup"]]
            db.set_setting("global_save_dir", self._current_tile_dir)
        quality = self.quality_box.currentData()
        self.series_created.emit(sid, urls, bool(urls), quality)
        self.accept()


# ==============================================================================
# Downloads view (Stitch screen 4 — Telemetry Center)
# ==============================================================================


def terminal_html(line: str) -> str:
    """Colorize yt-dlp terminal tags per the Stitch console mock."""
    tag_colors = {
        "[download]": "#38bdf8",
        "[ffmpeg]": "#f59e0b",
        "[archive]": "#4edea3",
        "[status]": "#94a3b8",
        "[error]": "#f43f5e",
        "[info]": "#64748b",
        "[Extractor]": "#a78bfa",
        "[Merger]": "#f59e0b",
        "[Metadata]": "#fcd34d",
    }
    safe = (line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    for tag, col in tag_colors.items():
        t = tag.replace("[", "\\[").replace("]", "\\]")
        if tag in safe:
            safe = safe.replace(tag, f"<span style='color:{col};font-weight:700'>{tag}</span>", 1)
            break
    return f"<span style='color:#cbd5e1'>{safe}</span>"


class TileBox(QFrame):
    """Monitor-style telemetry tile: caption, big value, sub value."""

    def __init__(self, caption: str, value: str = "—", sub: str = "",
                 tone: str = "sky", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumWidth(132)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(2)
        cap = QLabel(caption.upper())
        cap.setStyleSheet(f"color: {T_MUTED}; font-size: 9px; font-weight: 800; letter-spacing: 1px;")
        v.addWidget(cap)
        self.value = QLabel(value)
        self.value.setStyleSheet(
            f"color: {T_PRIMARY if tone == 'sky' else T_EMERALD2 if tone == 'emerald' else '#fcd34d'};"
            "font-size: 18px; font-weight: 800; font-family: 'JetBrains Mono', monospace;")
        v.addWidget(self.value)
        self.sub = QLabel(sub)
        self.sub.setStyleSheet(f"color: {T_MUTED}; font-size: 10px;")
        v.addWidget(self.sub)

    def set(self, value: str, sub: str = "") -> None:
        self.value.setText(value)
        if sub:
            self.sub.setText(sub)


class QueueRow(QFrame):
    move_up = pyqtSignal(object)
    move_down = pyqtSignal(object)
    remove = pyqtSignal(object)
    paused = pyqtSignal()
    resumed = pyqtSignal()

    def __init__(self, task: DownloadTask, index: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.task = task
        self.setObjectName("card")
        self.setFixedHeight(52)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(10)
        pos = QLabel(f"{index + 1:>2}")
        pos.setStyleSheet(f"color: {T_MUTED}; font-family: monospace; font-size: 14px; font-weight: 800;")
        pos.setFixedWidth(28)
        lay.addWidget(pos)
        name = QLabel(task.series_name)
        name.setStyleSheet("font-weight: 800; font-size: 13px;")
        lay.addWidget(name, 1)
        lay.addWidget(chip_tag(task.label if task.label else "series", "default"))
        lay.addWidget(chip_tag(f"{len(task.urls)} videos", "default"))
        dir_lab = QLabel(task.save_dir.replace(os.path.expanduser("~"), "~"))
        dir_lab.setStyleSheet(f"color: {T_MUTED}; font-size: 10px; font-family: monospace;")
        lay.addWidget(dir_lab, 1)
        up = icon_btn("↑", "Move up (higher priority)")
        down = icon_btn("↓", "Move down")
        rm = icon_btn("␥", "Remove from queue")
        up.clicked.connect(lambda: self.move_up.emit(task))
        down.clicked.connect(lambda: self.move_down.emit(task))
        rm.clicked.connect(lambda: self.remove.emit(task))
        for b in (up, down, rm):
            lay.addWidget(b)


class DownloadsView(QWidget):
    def __init__(self, manager: DownloadManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.manager = manager

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 8, 28, 16)
        root.setSpacing(12)

        # ---- heading + chips
        head = QVBoxLayout()
        head.addWidget(mk_label("Download Center", "titleLg"))
        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.chip_speed = chip_tag("Bandwidth: —", "sky")
        self.chip_stream = chip_tag("Concurrency: 1 stream · sequential", "default")
        self.chip_queue = chip_tag("Queue: 0", "amber")
        self.chip_done = chip_tag("Completed runs: 0", "emerald")
        for c in (self.chip_speed, self.chip_stream, self.chip_queue, self.chip_done):
            chips.addWidget(c)
        chips.addStretch(1)
        head.addLayout(chips)
        root.addLayout(head)

        # ---- now playing telemetry
        npcard = QFrame()
        npcard.setObjectName("card")
        np = QHBoxLayout(npcard)
        np.setContentsMargins(18, 12, 18, 12)
        np.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(4)
        caps = QHBoxLayout()
        caps.addWidget(label_caps("Now Playing"))
        caps.addStretch(1)
        self.step_chip = chip_tag("Idle", "default")
        caps.addWidget(self.step_chip)
        left.addLayout(caps)
        self.np_title = mk_label("No active download", "titleMd")
        left.addWidget(self.np_title)
        self.np_file = mk_label("The pipeline is idle — queue something from the Library.", "small")
        left.addWidget(self.np_file)
        self.np_bar = styled_bar("primary")
        left.addWidget(self.np_bar)
        leftw = QWidget()
        leftw.setLayout(left)
        np.addWidget(leftw, 1)
        self.tile_rate = TileBox("Rate", "—", "current speed")
        self.tile_peak = TileBox("Peak", "—", "peak this run")
        self.tile_xfer = TileBox("Transferred", "—", "of total size")
        self.tile_eta = TileBox("ETA", "--:--", "time remaining")
        for t in (self.tile_rate, self.tile_peak, self.tile_xfer, self.tile_eta):
            np.addWidget(t)
        root.addWidget(npcard)

        # ---- queue controls
        qlab_row = QHBoxLayout()
        qlab_row.addWidget(label_caps("Queue priority (top runs first)"))
        qlab_row.addStretch(1)
        pause = btn("⏸  Pause All", "ghost", "Freeze the queue (the running task finishes)")
        pause.clicked.connect(self.manager.pause_all)
        resume = btn("▶  Resume All", "ghost", "Unfreeze the queue")
        resume.clicked.connect(self.manager.resume_all)
        cancel_cur = btn("✖  Stop Current", "danger", "Cancel the active yt-dlp download")
        cancel_cur.clicked.connect(self.manager.cancel_current)
        clear = btn("✧  Clear Finished", "ghost", "Forget completed runs")
        clear.clicked.connect(self.manager.clear_finished)
        for b in (pause, resume, cancel_cur, clear):
            qlab_row.addWidget(b)
        root.addLayout(qlab_row)

        self.queue_host = PosterGrid()
        qarea = QScrollArea()
        qarea.setWidgetResizable(True)
        qarea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        qarea.setFixedHeight(180)
        qhost = QWidget()
        qhost.setObjectName("scrollHost")
        ql = QVBoxLayout(qhost)
        ql.setContentsMargins(0, 0, 0, 0)
        ql.addWidget(self.queue_host)
        ql.addStretch(1)
        qarea.setWidget(qhost)
        root.addWidget(qarea)

        # ---- terminal
        term_head = QHBoxLayout()
        term_head.addWidget(label_caps("yt-dlp Console"))
        term_head.addStretch(1)
        self.term_chip = chip_tag("tail -f downloads.log", "default")
        term_head.addWidget(self.term_chip)
        root.addLayout(term_head)
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.document().setMaximumBlockCount(1200)
        root.addWidget(self.terminal, 1)
        self._peak_speed = 0.0
        self._last_done = 0
        self._last_total = 0

    def on_state_changed(self) -> None:
        m = self.manager
        rows = []
        if m.active_task:
            rows.append(QueueRow(m.active_task, 0))
            rows[-1].setStyleSheet("QFrame#card { border: 1px solid #38bdf877; }")
            live = QLabel("● RUNNING")
            live.setStyleSheet(f"color: {T_PRIMARY}; font-size: 10px; font-weight: 800;")
            rows[-1].layout().insertWidget(0, live)
        for i, t in enumerate(m.queue):
            rows.append(QueueRow(t, i + (1 if m.active_task else 0)))
        # queue rows expose move/remove
        for r in rows:
            r.move_up.connect(lambda task: self.manager.move(task, True))
            r.move_down.connect(lambda task: self.manager.move(task, False))
            r.remove.connect(self.manager.remove)
        self.queue_host.set_items(rows)
        self.chip_queue.setText(f"Queue: {len(m.queue)}")
        self.chip_done.setText(f"Completed runs: {len(m.finished_log)}")
        task = m.active_task
        if not task:
            self.np_title.setText("No active download")
            self.np_file.setText("The pipeline is idle — queue something from the Library.")
            self.step_chip.setText("Idle" if not m.queue else "Queued — waiting")
            self.np_bar.setValue(0)
        else:
            self.np_title.setText(f"{task.series_name} — {len(task.urls)} video(s)")
            self.np_file.setText(task.save_dir)
            snap = m.current_snapshot()
            self.np_bar.setValue(int((snap.get("progress") or 0) * 100))

    def on_event(self, ev: str, data: Dict[str, Any]) -> None:
        m = self.manager
        if ev == "progress" and data.get("status") == "downloading":
            speed = float(data.get("speed") or 0)
            done = float(data.get("downloaded_bytes") or 0)
            total = float(data.get("total_bytes") or 0)
            self._peak_speed = max(self._peak_speed, speed)
            self.tile_rate.set(speed_text(speed), "current speed")
            self.tile_peak.set(speed_text(self._peak_speed), "peak this run")
            self.tile_xfer.set(human_size(done), f"of {human_size(total)}")
            self.tile_eta.set(format_eta(data.get("eta")), "time remaining")
            self.chip_speed.setText(f"Bandwidth: {speed_text(speed)}")
            self.step_chip.setText("Downloading")
            self.np_bar.setValue(int(100 * done / total) if total else 0)
            if total:
                self._last_done, self._last_total = done, total
        elif ev == "progress" and data.get("status") == "finished":
            self.step_chip.setText("Post-processing")
            self.tile_eta.set("00:00", "saving…")
        elif ev == "attempt":
            self.step_chip.setText(f"Attempt {data.get('attempt')}/{data.get('max_retries')}")
            self.np_title.setText(
                f"{data.get('index', '?')}/{data.get('total', '?')}  ·  "
                + (m.active_task.series_name if m.active_task else "Download"))
        elif ev == "skip":
            self.tile_eta.set("00:00", "already in archive — skipped")
        elif ev == "retry_error":
            self.step_chip.setText("Retrying…")
        elif ev == "success":
            self.step_chip.setText("Completed ✔")
        elif ev == "summary":
            if "fatal" in data:
                self.tile_rate.set("ERR", str(data["fatal"])[:40])
            else:
                ok = len(data.get("succeeded", []))
                bad = len(data.get("failed", []))
                self.tile_rate.set(f"{ok} ok", f"{bad} failed · {ok + bad} processed")
                self._peak_speed = 0.0

    def on_log_line(self, line: str) -> None:
        self.terminal.append(terminal_html(line))


# ==============================================================================
# Settings view (Stitch screen 5 — Storage, formats, network, auth, database)
# ==============================================================================


class SectionCard(QFrame):
    def __init__(self, title: str, sub: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        lay.addWidget(mk_label(title, "titleMd"))
        if sub:
            lay.addWidget(mk_label(sub, "body", "muted"))


class SettingsView(QWidget):
    test_connection = pyqtSignal()
    resync_requested = pyqtSignal()
    settings_changed = pyqtSignal(str)     # key that changed
    toast = pyqtSignal(str, bool)

    def __init__(self, settings: Optional[Dict[str, str]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.s: Dict[str, str] = dict(settings or load_settings())
        self._widgets: Dict[str, QWidget] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 8, 28, 16)
        outer.setSpacing(12)
        outer.addWidget(mk_label("Settings & Storage Preferences", "titleLg"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        root = QVBoxLayout(host)
        root.setContentsMargins(0, 4, 8, 4)
        root.setSpacing(14)

        # ---- 1. Storage & Directories
        sec1 = SectionCard("Storage & Directories",
                           "Where new episodes are saved. A per-donghua sub-folder keeps every series self-contained.")
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.t_videos = StorageCard("⌂", "Videos", os.path.expanduser("~/Videos"), recommended=True)
        self.t_downloads = StorageCard("⤓", "Downloads", os.path.expanduser("~/Downloads"))
        self.t_docs = StorageCard("▤", "Documents", os.path.expanduser("~/Documents"))
        self.t_custom = StorageCard("✎", "Custom…", self.s.get("global_save_dir", "~/Videos"))
        self.tiles = [self.t_videos, self.t_downloads, self.t_docs, self.t_custom]
        for t in self.tiles:
            tiles.addWidget(t)
            t.toggled.connect(self._tile_picked)
        customw = QWidget()
        cw = QVBoxLayout(customw)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(6)
        cw.addWidget(self.t_custom)
        self.custom_path = QLineEdit()
        self.custom_path.setPlaceholderText("Type or browse any folder…")
        self.custom_path.textChanged.connect(lambda p: self.t_custom.set_dir(resolve_path(p)))
        brow = QHBoxLayout()
        brow.addWidget(self.custom_path, 1)
        browse = btn("Browse…", "ghost", "")
        browse.setMinimumHeight(28)

        def _pick():
            path = QFileDialog.getExistingDirectory(self, "Global save location",
                                                    os.path.expanduser(self.custom_path.text() or "~"))
            if path:
                self.custom_path.setText(path)
                self.t_custom.setChecked(True)
        browse.clicked.connect(_pick)
        brow.addWidget(browse)
        cw.addLayout(brow)
        tiles.addWidget(customw, 1)
        self.tiles[3] = self.t_custom
        for t in self.tiles:
            t.refresh_free()
        holder = QWidget()
        holder.setLayout(tiles)
        sec1.layout().addWidget(holder)
        current_dir = self.s.get("global_save_dir", "~/Videos")
        matched = False
        for t in self.tiles[:-1]:
            if t.dir() == current_dir:
                t.setChecked(True)
                matched = True
        if matched:
            self.t_custom.set_dir(current_dir)
            self.custom_path.setText(current_dir)
        else:
            self.t_custom.setChecked(True)
            self.custom_path.setText(current_dir)
        self.subfolder_chk = QCheckBox("Use a per-donghua sub-folder inside the save location")
        self.subfolder_chk.setChecked(self.s.get("per_series_subfolder", "1") == "1")
        self.subfolder_chk.toggled.connect(
            lambda v: self._save("per_series_subfolder", "1" if v else "0"))
        sec1.layout().addWidget(self.subfolder_chk)
        root.addWidget(sec1)

        # ---- 2. Quality & Formats
        sec2 = SectionCard("Quality & Formats", "Applied to every new download unless a series overrides it.")
        self._mk_field(sec2, "Default quality", "default_quality", ("combo", QUALITY_OPTIONS))
        self._mk_field(sec2, "Container format", "default_container", ("combo", CONTAINER_OPTIONS))
        root.addWidget(sec2)

        # ---- 3. Network & Downloader
        sec3 = SectionCard("Network & Downloader", "Retries, bandwidth ceiling, subtitle language track.")
        self._mk_field(sec3, "Max retries per video", "max_retries", ("spin", 1, 20))
        self._mk_field(sec3, "Subtitle languages", "sub_langs", ("text", "en, zh-Hans"))
        rate_box = QHBoxLayout()
        rate_box.addWidget(label_caps("Rate limit (MB/s, 0 = unlimited)"))
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0, 500)
        self.rate_spin.setDecimals(1)
        try:
            self.rate_spin.setValue(float(self.s.get("rate_limit_mb", "0") or 0))
        except (TypeError, ValueError):
            self.rate_spin.setValue(0.0)
        self.rate_spin.setSuffix(" MB/s")
        self.rate_spin.setFixedWidth(150)
        self.rate_spin.valueChanged.connect(lambda v: self._save("rate_limit_mb", str(v)))
        rate_row = QWidget()
        rate_row.setLayout(rate_box)
        self._insert_widgets(sec3, [rate_row, self.rate_spin])
        root.addWidget(sec3)

        # ---- 4. Browser & Auth
        sec4 = SectionCard("Browser & Auth", "Which local browser profile yt-dlp should reuse for cookies.")
        self._mk_field(sec4, "Cookies source", "browser_cookies", ("combo", [b for b in BROWSER_OPTIONS if b[0] != "safari"]))
        root.addWidget(sec4)

        # ---- 5. Database & Daemon
        sec5 = SectionCard("Database & Daemon", "Postgres catalog behind the app, and the download daemon.")
        try:
            import yt_dlp
            engine_ver = yt_dlp.version.__version__
        except Exception:
            engine_ver = "unknown"
        info = QLabel(
            f"DB: donghua_db @ {getattr(db, 'DB_CONFIG', {}).get('host', 'localhost')}  ·  "
            f"user {getattr(db, 'DB_CONFIG', {}).get('user', '-')}  ·  "
            f"engine yt-dlp {engine_ver}")
        info.setStyleSheet(f"color: {T_SEC}; font-size: 12px; font-family: monospace;")
        self._insert_widgets(sec5, [info])
        dbrow = QHBoxLayout()
        test_btn = btn("⚡  Test Connection", "ghost", "Ping the database now")
        test_btn.clicked.connect(self.test_connection.emit)
        resync_btn = btn("⟳  Force Re-Sync", "ghost", "Re-sync every series against its downloaded.txt")
        resync_btn.clicked.connect(self.resync_requested.emit)
        dbrow.addWidget(test_btn)
        dbrow.addWidget(resync_btn)
        dbrow.addStretch(1)
        dbw = QWidget()
        dbw.setLayout(dbrow)
        self._insert_widgets(sec5, [dbw])
        root.addWidget(sec5)

        # ---- reset
        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        reset = btn("Reset to Defaults", "danger", "Restore every setting to the shipped default")
        reset.clicked.connect(self._reset)
        reset_row.addWidget(reset)
        root.addLayout(reset_row)
        root.addStretch(1)

        scroll.setWidget(host)
        outer.addWidget(scroll, 1)
        self._widget_map = self._widgets

    # ---- helpers ----------------------------------------------------------
    def _mk_field(self, sec: SectionCard, label: str, key: str,
                  spec: tuple) -> None:
        kind = spec[0]
        if kind == "combo":
            widget = QComboBox()
            widget.setObjectName("chip")
            widget.setFixedHeight(30)
            for val, lab in spec[1]:
                widget.addItem(lab, val)
            idx = widget.findData(self.s.get(key, ""))
            widget.setCurrentIndex(idx if idx >= 0 else 0)
            widget.currentIndexChanged.connect(
                lambda _i, k=key, w=widget: self._save(k, str(w.currentData())))
            self._widgets[key] = widget
        elif kind == "spin":
            widget = QSpinBox()
            widget.setRange(*spec[1:3])
            widget.setFixedWidth(120)
            try:
                widget.setValue(int(self.s.get(key, "3") or 3))
            except (TypeError, ValueError):
                widget.setValue(3)
            widget.valueChanged.connect(lambda v, k=key: self._save(k, str(v)))
            self._widgets[key] = widget
        elif kind == "text":
            widget = QLineEdit(self.s.get(key, ""))
            widget.setFixedWidth(220)
            widget.editingFinished.connect(
                lambda w=widget, k=key: self._save(k, w.text().strip() or "en"))
            self._widgets[key] = widget
        else:
            return
        row = QHBoxLayout()
        row.addWidget(label_caps(label))
        row.addStretch(1)
        row.addWidget(widget)
        wrap = QWidget()
        wrap.setLayout(row)
        sec.layout().addWidget(wrap)

    def _insert_widgets(self, sec: SectionCard, widgets: List[QWidget]) -> None:
        for w in widgets:
            sec.layout().addWidget(w)

    def _tile_picked(self, checked: bool) -> None:
        if not checked:
            return
        src = self.sender()
        if src in self.tiles:
            self._save("global_save_dir", src.dir())

    def _save(self, key: str, value: str) -> None:
        self.s[key] = value
        if set_setting(key, value):
            self.settings_changed.emit(key)
            self.toast.emit(f"Saved: {key.replace('_', ' ')} = {value}", True)
        else:
            self.toast.emit(f"Could not save {key}", False)

    def _reset(self) -> None:
        for key, value in db.DEFAULT_SETTINGS.items():
            set_setting(key, value)
            self.s[key] = value
        if set_setting("per_series_subfolder", "1"):
            self.s["per_series_subfolder"] = "1"
        self.settings_changed.emit("*")
        self.toast.emit("Settings restored to defaults.", True)


# ==============================================================================
# Generic DB worker (keeps Postgres calls off the UI thread)
# ==============================================================================


class DbWorker(QThread):
    done = pyqtSignal(object, object)     # token, result_or_exception

    def __init__(self, fn: Callable[[], Any], token: int, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.fn = fn
        self.token = token

    def run(self) -> None:
        try:
            self.done.emit(self.token, self.fn())
        except Exception as exc:  # noqa: BLE001
            self.done.emit(self.token, exc)


# ==============================================================================
# Quick add dialog (header search paste → one URL, instantly)
# ==============================================================================


class QuickUrlDialog(QDialog):
    def __init__(self, series_list: List[Dict[str, Any]], settings: Dict[str, str],
                 url: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Quick Add URL")
        self.setStyleSheet(app_stylesheet())
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(10)
        lay.addWidget(mk_label("Add a single episode", "titleMd"))
        lay.addWidget(mk_label("Pick the series it belongs to (or start a new one from the wizard).",
                               "body", "muted"))

        lay.addWidget(label_caps("Video URL"))
        self.url = QLineEdit(url)
        self.url.setPlaceholderText("https://youtu.be/…")
        lay.addWidget(self.url)

        lay.addWidget(label_caps("Episode title (optional)"))
        self.title = QLineEdit()
        self.title.setPlaceholderText("e.g. Episode 15 — The Blade")
        lay.addWidget(self.title)

        lay.addWidget(label_caps("Series"))
        self.series_box = QComboBox()
        self.series_box.addItem("➕  New series (opens the wizard)…", "__new__")
        for s in series_list:
            self.series_box.addItem(s.get("name", ""), s["id"])
        lay.addWidget(self.series_box)

        qrow = QHBoxLayout()
        qrow.addWidget(label_caps("Quality"))
        self.quality = QComboBox()
        self.quality.setObjectName("chip")
        for val, lab in QUALITY_OPTIONS:
            self.quality.addItem(lab, val)
        self.quality.setCurrentText(quality_label(settings.get("default_quality", "720p")))
        self.quality.setFixedHeight(30)
        qrow.addWidget(self.quality)
        qrow.addStretch(1)
        holder = QWidget()
        holder.setLayout(qrow)
        lay.addWidget(holder)

        self.dl_now = QCheckBox("Download this episode immediately")
        self.dl_now.setChecked(True)
        lay.addWidget(self.dl_now)

        btns = QHBoxLayout()
        btns.addStretch(1)
        c = btn("Cancel", "ghost")
        c.clicked.connect(self.reject)
        s = btn("Save", "primary")
        s.clicked.connect(self.accept)
        btns.addWidget(c)
        btns.addWidget(s)
        lay.addLayout(btns)

    def collect(self):
        if self.exec() != 1 or not URL_RE.search(self.url.text()):
            return None
        return {
            "url": URL_RE.search(self.url.text()).group(0),
            "title": self.title.text().strip(),
            "series": self.series_box.currentData(),
            "series_label": self.series_box.currentText(),
            "quality": self.quality.currentData(),
            "download_now": self.dl_now.isChecked(),
        }


# ==============================================================================
# Main window
# ==============================================================================


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
        strip.setStyleSheet(f"QFrame#card {{ border-radius: 0; background: {T_RAIL};"
                            "border-top: 1px solid #28354d; }}")
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


# ==============================================================================
# Entry point
# ==============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Donghua Stream")
    app.setOrganizationName("donghua")
    app.setStyleSheet(app_stylesheet())
    app.setWindowIcon(QIcon.fromTheme("applications-multimedia"))
    app.setStyleSheet(app_stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
