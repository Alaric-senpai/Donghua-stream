"""Download Center: live telemetry, queue control, colorized terminal."""
import os
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from ..components.poster_grid import PosterGrid
from ..components.primitives import (
    btn, chip_tag, icon_btn, label_caps, mk_label, styled_bar,
)
from ..components.queue_row import QueueRow
from ..infrastructure.download_queue import DownloadManager, DownloadTask
from ..theme import T_EMERALD2, T_MUTED, T_PRIMARY, T_ROSE, T_SEC
from ..utils import format_eta, human_size, speed_text


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

