"""Download Center: live telemetry, queue control and a colorized console."""
from typing import Any, Dict, Optional

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QScrollArea, QTextEdit,
    QVBoxLayout, QWidget,
)

from ..components.empty_state import EmptyState
from ..components.primitives import (
    btn, chip_tag, eyebrow, icon_btn, label_caps, mk_label, styled_bar,
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

        # ---- copyable error banner (hidden until something fails)
        self.error_banner = QFrame()
        self.error_banner.setObjectName("errorBanner")
        eb = QHBoxLayout(self.error_banner)
        eb.setContentsMargins(12, 8, 12, 8)
        eb.setSpacing(8)
        warn = QLabel("!")
        warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        warn.setFixedSize(24, 24)
        warn.setStyleSheet(
            f"color: {T_ROSE2}; border: 1px solid {T_ROSE2};"
            "border-radius: 12px; font-size: 14px; font-weight: 900;"
            "background: rgba(244,63,94,25);")
        eb.addWidget(warn, 0, Qt.AlignmentFlag.AlignTop)
        err_col = QVBoxLayout()
        err_col.setSpacing(1)
        self.error_title = mk_label("Download error", "titleSm")
        self.error_msg = mk_label("", "small", wrap=True)
        self.error_msg.setSizePolicy(
            self.error_msg.sizePolicy().horizontalPolicy(),
            self.error_msg.sizePolicy().verticalPolicy())
        err_col.addWidget(self.error_title)
        err_col.addWidget(self.error_msg)
        eb.addLayout(err_col, 1)
        self.copy_err_btn = btn(
            "Copy Error", "danger", "Copy the full error report", small=True)
        self.copy_err_btn.setFixedHeight(28)
        self.copy_err_btn.setIcon(icon("copy", T_ROSE2, 13))
        self.copy_err_btn.setIconSize(QSize(13, 13))
        self.copy_err_btn.clicked.connect(self._copy_error)
        eb.addWidget(self.copy_err_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        dismiss = icon_btn("", "Dismiss this error")
        dismiss.setFixedSize(28, 28)
        dismiss.setIcon(icon("close", T_SEC, 13))
        dismiss.setIconSize(QSize(13, 13))
        dismiss.clicked.connect(self.error_banner.hide)
        eb.addWidget(dismiss, 0, Qt.AlignmentFlag.AlignVCenter)
        self.error_banner.hide()
        root.addWidget(self.error_banner)
        self._last_error_title = ""
        self._last_error_details = ""

        # ---- console
        term_card = QFrame()
        term_card.setObjectName("card")
        tl2 = QVBoxLayout(term_card)
        tl2.setContentsMargins(12, 10, 12, 12)
        tl2.setSpacing(8)
        term_head = QHBoxLayout()
        term_head.addWidget(label_caps("yt-dlp console"))
        term_head.addStretch(1)
        self.copy_log_btn = btn(
            "Copy Console", "ghost", "Copy every line currently in the console",
            small=True)
        self.copy_log_btn.setFixedHeight(24)
        self.copy_log_btn.setIcon(icon("copy", T_SEC, 12))
        self.copy_log_btn.setIconSize(QSize(12, 12))
        self.copy_log_btn.clicked.connect(self._copy_console)
        term_head.addWidget(self.copy_log_btn)
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

    # ---- copyable error reporting -----------------------------------------
    def _show_error(self, title: str, summary: str, details: str) -> None:
        self._last_error_title = title
        self._last_error_details = details.strip()
        self.error_title.setText(title)
        self.error_msg.setText(summary)
        self.error_banner.show()

    def _flash_button(self, button: QWidget, original: str) -> None:
        try:
            button.setText("Copied")
        except RuntimeError:
            return
        QTimer.singleShot(1600, lambda b=button, o=original: self._restore_button(b, o))

    @staticmethod
    def _restore_button(button: QWidget, original: str) -> None:
        try:
            button.setText(original)
        except RuntimeError:
            pass

    def _copy_error(self) -> None:
        if not self._last_error_details:
            return
        text = f"{self._last_error_title}\n\n{self._last_error_details}"
        QApplication.clipboard().setText(text)
        self._flash_button(self.copy_err_btn, "Copy Error")

    def _copy_console(self) -> None:
        text = self.terminal.toPlainText().strip() or "No console output yet."
        QApplication.clipboard().setText(text)
        self._flash_button(self.copy_log_btn, "Copy Console")

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
        task_name = m.active_task.series_name if m.active_task else "Download"
        if ev == "start":
            self.error_banner.hide()
        elif ev == "progress" and data.get("status") == "downloading":
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
                + task_name)
        elif ev == "skip":
            self.tile_eta.set("00:00", "already in archive — skipped")
        elif ev == "retry_error":
            self.step_chip.setText("Retrying…")
            attempt = data.get("attempt", "?")
            max_retries = data.get("max_retries", "?")
            url = str(data.get("url") or "")
            error = str(data.get("error") or "Unknown error")
            self._show_error(
                "Download attempt failed",
                f"{task_name} · attempt {attempt}/{max_retries}. Retrying…",
                f"Series: {task_name}\nURL: {url}\n"
                f"Attempt: {attempt}/{max_retries}\n\n{error}")
        elif ev == "failure":
            self.step_chip.setText("Failed")
            url = str(data.get("url") or "")
            error = str(data.get("error") or "Unknown error")
            self._show_error(
                "Episode failed",
                f"{task_name} · this video could not be downloaded.",
                f"Series: {task_name}\nURL: {url}\n\n{error}")
        elif ev == "success":
            self.step_chip.setText("Completed ✔")
        elif ev == "summary":
            if "fatal" in data:
                fatal = str(data["fatal"])
                self.tile_rate.set("ERR", fatal[:40])
                self.terminal.append(terminal_html(f"[error] {fatal}"))
                self._show_error(
                    "Download engine error",
                    f"{task_name} · the download engine stopped unexpectedly.",
                    f"Series: {task_name}\n\n{fatal}")
            else:
                ok = len(data.get("succeeded", []))
                failed = data.get("failed", [])
                bad = len(failed)
                self.tile_rate.set(f"{ok} ok", f"{bad} failed · {ok + bad} processed")
                self._peak_speed = 0.0
                if bad:
                    details = "\n\n".join(
                        f"{f.get('url', '')}\n{f.get('error', '')}"
                        for f in failed if isinstance(f, dict))
                    self._show_error(
                        f"{bad} episode(s) failed",
                        f"{task_name} · {ok} saved. Copy the error details below.",
                        details)

    def on_log_line(self, line: str) -> None:
        self.terminal.append(terminal_html(line))
