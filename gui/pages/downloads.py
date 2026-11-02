"""Download Center: live telemetry, queue control and a colorized console."""
from typing import Any, Dict, Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from ..components.empty_state import EmptyState
from ..components.primitives import (
    btn, chip_tag, eyebrow, label_caps, mk_label, styled_bar,
)
from ..components.queue_row import QueueRow
from ..components.stack_list import StackList
from ..icons import icon
from ..infrastructure.download_queue import DownloadManager
from ..theme import T_AMBER2, T_EMERALD2, T_MUTED, T_PRIMARY, T_ROSE2, T_SEC
from ..utils import format_eta, human_size, speed_text


def terminal_html(line: str) -> str:
    """Colorize yt-dlp terminal tags for the console card."""
    tag_colors = {
        "[download]": "#38bdf8",
        "[ffmpeg]": "#f59e0b",
        "[archive]": "#4edea3",
        "[status]": "#94a3b8",
        "[error]": "#f43f5e",
        "[info]": "#8494ab",
        "[Extractor]": "#a78bfa",
        "[Merger]": "#f59e0b",
        "[Metadata]": "#fcd34d",
    }
    safe = (line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    for tag, col in tag_colors.items():
        t = tag.replace("[", "\\[").replace("]", "\\]")
        if tag in safe:
            safe = safe.replace(t, f"<span style='color:{col};font-weight:700'>{tag}</span>", 1)
            break
    return f"<span style='color:#cbd5e1'>{safe}</span>"


class TileBox(QFrame):
    """Monitor-style telemetry tile: caption, big value, sub value."""

    def __init__(self, caption: str, value: str = "—", sub: str = "",
                 tone: str = "sky", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setMinimumWidth(118)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(1)
        cap = QLabel(caption.upper())
        cap.setStyleSheet(
            f"color: {T_MUTED}; font-family: 'Fira Code'; font-size: 8px;")
        v.addWidget(cap)
        self.value = QLabel(value)
        color = T_PRIMARY if tone == "sky" else T_EMERALD2 if tone == "emerald" else T_AMBER2
        self.value.setStyleSheet(
            f"color: {color}; font-size: 17px; font-weight: 700; font-family: 'Fira Code';")
        v.addWidget(self.value)
        self.sub = QLabel(sub)
        self.sub.setStyleSheet(f"color: {T_MUTED}; font-size: 9px;")
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
        root.setContentsMargins(28, 14, 28, 18)
        root.setSpacing(12)

        # ---- heading + live chips
        head = QHBoxLayout()
        head.setSpacing(10)
        tl = QVBoxLayout()
        tl.setSpacing(2)
        tl.addWidget(eyebrow("Transfer console"))
        tl.addWidget(mk_label("Download Center", "display"))
        tl.addWidget(mk_label(
            "One sequential pipeline — watch progress, reorder the queue and read the raw log.",
            "body", "muted"))
        head.addLayout(tl)
        head.addStretch(1)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_speed = chip_tag("Bandwidth: —", "sky")
        self.chip_stream = chip_tag("1 stream · sequential", "default")
        self.chip_queue = chip_tag("Queue: 0", "amber")
        self.chip_done = chip_tag("Completed: 0", "emerald")
        for c in (self.chip_speed, self.chip_stream, self.chip_queue, self.chip_done):
            c.setFixedHeight(24)
            chips.addWidget(c)
        head.addLayout(chips)
        root.addLayout(head)

        # ---- now playing telemetry
        npcard = QFrame()
        npcard.setObjectName("card")
        np = QHBoxLayout(npcard)
        np.setContentsMargins(16, 12, 16, 12)
        np.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(4)
        caps = QHBoxLayout()
        caps.addWidget(label_caps("Now playing"))
        caps.addStretch(1)
        self.step_chip = chip_tag("Idle", "default")
        caps.addWidget(self.step_chip)
        left.addLayout(caps)
        self.np_title = mk_label("No active download", "titleMd")
        left.addWidget(self.np_title)
        self.np_file = mk_label(
            "The pipeline is idle — queue something from the Library.", "small")
        self.np_file.setSizePolicy(self.np_file.sizePolicy().horizontalPolicy(),
                                   self.np_file.sizePolicy().verticalPolicy())
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
        qlab_row.setSpacing(7)
        qlab_row.addWidget(label_caps("Queue priority · top runs first"))
        qlab_row.addStretch(1)
        pause = btn("Pause", "ghost", "Freeze the queue (the running task finishes)", small=True)
        pause.setFixedHeight(30)
        pause.setIcon(icon("pause", T_SEC, 13))
        pause.setIconSize(QSize(13, 13))
        pause.clicked.connect(self.manager.pause_all)
        resume = btn("Resume", "ghost", "Unfreeze the queue", small=True)
        resume.setFixedHeight(30)
        resume.setIcon(icon("play", T_SEC, 13))
        resume.setIconSize(QSize(13, 13))
        resume.clicked.connect(self.manager.resume_all)
        cancel_cur = btn("Stop Current", "danger", "Cancel the active yt-dlp download", small=True)
        cancel_cur.setFixedHeight(30)
        cancel_cur.setIcon(icon("close", T_ROSE2, 13))
        cancel_cur.setIconSize(QSize(13, 13))
        cancel_cur.clicked.connect(self.manager.cancel_current)
        clear = btn("Clear Finished", "ghost", "Forget completed runs", small=True)
        clear.setFixedHeight(30)
        clear.setIcon(icon("trash", T_SEC, 13))
        clear.setIconSize(QSize(13, 13))
        clear.clicked.connect(self.manager.clear_finished)
        for b in (pause, resume, cancel_cur, clear):
            qlab_row.addWidget(b)
        root.addLayout(qlab_row)

        self.queue_host = StackList(spacing=6)
        self.queue_empty = EmptyState(
            "⇩", "Queue is clear",
            "Queued downloads appear here when you start one from the Library.")
        self.queue_empty.setMinimumHeight(110)
        qarea = QScrollArea()
        qarea.setWidgetResizable(True)
        qarea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        qarea.setFixedHeight(182)
        qhost = QWidget()
        qhost.setObjectName("scrollHost")
        ql = QVBoxLayout(qhost)
        ql.setContentsMargins(0, 0, 4, 0)
        ql.setSpacing(6)
        ql.addWidget(self.queue_host)
        ql.addWidget(self.queue_empty)
        ql.addStretch(1)
        qarea.setWidget(qhost)
        root.addWidget(qarea)

        # ---- console
        term_card = QFrame()
        term_card.setObjectName("card")
        tl2 = QVBoxLayout(term_card)
        tl2.setContentsMargins(12, 10, 12, 12)
        tl2.setSpacing(8)
        term_head = QHBoxLayout()
        term_head.addWidget(label_caps("yt-dlp console"))
        term_head.addStretch(1)
        self.term_chip = chip_tag("tail -f downloads.log", "default")
        term_head.addWidget(self.term_chip)
        tl2.addLayout(term_head)
        self.terminal = QTextEdit()
        self.terminal.setObjectName("console")
        self.terminal.setReadOnly(True)
        self.terminal.document().setMaximumBlockCount(1200)
        tl2.addWidget(self.terminal, 1)
        root.addWidget(term_card, 1)

        self._peak_speed = 0.0
        self._last_done = 0
        self._last_total = 0

    def on_state_changed(self) -> None:
        m = self.manager
        rows = []
        if m.active_task:
            rows.append(QueueRow(m.active_task, 0, active=True))
        for i, t in enumerate(m.queue):
            rows.append(QueueRow(t, i + (1 if m.active_task else 0)))
        for r in rows:
            r.move_up.connect(lambda task: self.manager.move(task, True))
            r.move_down.connect(lambda task: self.manager.move(task, False))
            r.remove.connect(self.manager.remove)
        self.queue_host.set_items(rows)
        self.queue_empty.setVisible(not rows)
        self.chip_queue.setText(f"Queue: {len(m.queue)}")
        self.chip_done.setText(f"Completed: {len(m.finished_log)}")
        task = m.active_task
        if not task:
            self.np_title.setText("No active download")
            self.np_file.setText("The pipeline is idle — queue something from the Library.")
            self.step_chip.setText("Idle" if not m.queue else "Queued — waiting")
            self.np_bar.setValue(0)
        else:
            self.np_title.setText(f"{task.series_name} — {len(task.urls)} video(s)")
            self.np_file.setText(task.save_dir)
            self.np_file.setToolTip(task.save_dir)
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
