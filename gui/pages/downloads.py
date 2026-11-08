"""Download Center: live telemetry, queue control and a colorized console."""
import re
from typing import Any, Dict, Optional

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QScrollArea, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
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
        "[warning]": "#fbbf24",
        "[error]": "#f43f5e",
        "[info]": "#8494ab",
        "[Extractor]": "#a78bfa",
        "[Merger]": "#f59e0b",
        "[Metadata]": "#fcd34d",
    }
    safe = (line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    for tag, col in tag_colors.items():
        if tag in safe:
            safe = safe.replace(
                tag, f"<span style='color:{col};font-weight:700'>{tag}</span>", 1)
            break
    return f"<span style='color:#cbd5e1'>{safe}</span>"


_PROGRESS_LINE = re.compile(
    r"^\[download\]\s+(?:"
    r"\d+(?:\.\d+)?%"                       # percentage, with or without total
    r"|\d+(?:\.\d+)?\s*[KMGTP]?i?B\s+(?:at\b|\[)"  # unknown total + speed/time
    r")"
)


def is_progress_line(line: str) -> bool:
    """True for yt-dlp's mutable progress row, not destination/log rows."""
    text = line.strip()
    if not text.startswith("[download]"):
        return False
    if text.startswith(("[download] Destination:", "[download] has already")):
        return False
    return bool(_PROGRESS_LINE.match(text))


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
        self._console_expanded = False
        self._progress_active = False
        self._saved_splitter_sizes = [190, 420]

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
        self.npcard = QFrame()
        self.npcard.setObjectName("card")
        np = QHBoxLayout(self.npcard)
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
        root.addWidget(self.npcard)

        # ---- queue controls
        self.qcontrols = QWidget()
        qlab_row = QHBoxLayout(self.qcontrols)
        qlab_row.setContentsMargins(0, 0, 0, 0)
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
        root.addWidget(self.qcontrols)

        self.queue_host = StackList(spacing=6)
        self.queue_empty = EmptyState(
            "⇩", "Queue is clear",
            "Queued downloads appear here when you start one from the Library.")
        self.queue_empty.setMinimumHeight(110)
        self.qarea = QScrollArea()
        self.qarea.setWidgetResizable(True)
        self.qarea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.qarea.setMinimumHeight(110)
        qhost = QWidget()
        qhost.setObjectName("scrollHost")
        ql = QVBoxLayout(qhost)
        ql.setContentsMargins(0, 0, 4, 0)
        ql.setSpacing(6)
        ql.addWidget(self.queue_host)
        ql.addWidget(self.queue_empty)
        ql.addStretch(1)
        self.qarea.setWidget(qhost)

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
        term_card.setMinimumHeight(240)
        tl2 = QVBoxLayout(term_card)
        tl2.setContentsMargins(12, 10, 12, 12)
        tl2.setSpacing(8)
        term_head = QHBoxLayout()
        term_head.addWidget(label_caps("yt-dlp console"))
        term_head.addStretch(1)
        self.expand_btn = btn(
            "Expand", "ghost", "Expand the console to the full page", small=True)
        self.expand_btn.setFixedHeight(24)
        self.expand_btn.setIcon(icon("chevron-up", T_SEC, 12))
        self.expand_btn.setIconSize(QSize(12, 12))
        self.expand_btn.clicked.connect(self._toggle_console_expanded)
        term_head.addWidget(self.expand_btn)
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
        self.terminal.setMinimumHeight(180)
        self.terminal.setPlaceholderText("yt-dlp output will appear here…")
        self.terminal.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.terminal.setToolTip(
            "Select any line and press Ctrl+C, or use Copy Console.")
        self.terminal.document().setMaximumBlockCount(1200)
        tl2.addWidget(self.terminal, 1)

        self.console_splitter = QSplitter(Qt.Orientation.Vertical)
        self.console_splitter.setChildrenCollapsible(False)
        self.console_splitter.setHandleWidth(8)
        self.console_splitter.addWidget(self.qarea)
        self.console_splitter.addWidget(term_card)
        self.console_splitter.setStretchFactor(0, 0)
        self.console_splitter.setStretchFactor(1, 1)
        self.console_splitter.setSizes(self._saved_splitter_sizes)
        root.addWidget(self.console_splitter, 1)

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

    def _toggle_console_expanded(self) -> None:
        self._set_console_expanded(not self._console_expanded)

    def _set_console_expanded(self, expanded: bool) -> None:
        self._console_expanded = expanded
        if expanded:
            sizes = self.console_splitter.sizes()
            if sizes and max(sizes) > 0:
                self._saved_splitter_sizes = sizes
            self.npcard.hide()
            self.qcontrols.hide()
            self.qarea.hide()
            self.expand_btn.setText("Restore")
            self.expand_btn.setToolTip("Restore the queue and telemetry panels")
            self.expand_btn.setIcon(icon("chevron-down", T_SEC, 12))
        else:
            self.npcard.show()
            self.qcontrols.show()
            self.qarea.show()
            self.console_splitter.setSizes(self._saved_splitter_sizes)
            self.expand_btn.setText("Expand")
            self.expand_btn.setToolTip("Expand the console to the full page")
            self.expand_btn.setIcon(icon("chevron-up", T_SEC, 12))

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
            self._progress_active = False
        elif ev == "progress" and data.get("status") in ("downloading",
                                                         "stream_finished"):
            status = str(data.get("status"))
            speed = float(data.get("speed") or 0)
            done = float(data.get("downloaded_bytes") or 0)
            total = float(data.get("total_bytes") or 0)
            if status == "downloading":
                self._peak_speed = max(self._peak_speed, speed)
                self.tile_rate.set(speed_text(speed), "current speed")
                self.tile_eta.set(format_eta(data.get("eta")), "time remaining")
                self.chip_speed.setText(f"Bandwidth: {speed_text(speed)}")
                self.step_chip.setText("Downloading")
            else:
                saved = data.get("formats_done")
                self.tile_rate.set("—", "waiting for next stream")
                self.tile_eta.set("--:--", "more data to fetch")
                self.step_chip.setText(
                    f"Stream {saved} saved" if saved else "Stream saved")
            self.tile_peak.set(speed_text(self._peak_speed), "peak this run")
            self.tile_xfer.set(human_size(done), f"of {human_size(total)}")
            if total:
                pct = int(100 * done / total)
                # A stream may be complete while another stream and the
                # merge are still pending, so never show a full bar yet.
                if status == "stream_finished":
                    pct = min(pct, 99)
                self.np_bar.setValue(pct)
                self._last_done, self._last_total = done, total
            else:
                self.np_bar.setValue(0)
        elif ev == "progress" and data.get("status") == "finished":
            done = float(data.get("downloaded_bytes") or 0)
            total = float(data.get("total_bytes") or 0)
            self.step_chip.setText("Merged ✔")
            self.tile_eta.set("00:00", "download complete")
            self.tile_xfer.set(human_size(done), f"of {human_size(total)}")
            self.np_bar.setValue(100)
        elif ev == "postprocess":
            if data.get("status") == "started":
                name = str(data.get("postprocessor") or "Post-processing")
                self.step_chip.setText(
                    "Merging streams" if "Merger" in name else "Finalizing")
                self.tile_eta.set("--:--", "post-processing")
        elif ev == "attempt":
            self.step_chip.setText(f"Attempt {data.get('attempt')}/{data.get('max_retries')}")
            self.np_title.setText(
                f"{data.get('index', '?')}/{data.get('total', '?')}  ·  "
                + task_name)
        elif ev == "skip":
            self.tile_eta.set("00:00", "already in archive — skipped")
        elif ev == "retry_error":
            # An attempt-level error is not a final failure: yt-dlp has its
            # own client fallbacks and the engine is about to retry.  Keep
            # the red banner reserved for the final summary.
            self.error_banner.hide()
            attempt = data.get("attempt", "?")
            max_retries = data.get("max_retries", "?")
            delay = data.get("delay")
            error = str(data.get("error") or "Unknown error").strip()
            first_line = error.splitlines()[0][:240] if error else "Unknown error"
            wait = f" in {int(delay)}s" if isinstance(delay, (int, float)) else ""
            self.step_chip.setText(f"Retrying {attempt}/{max_retries}")
            self.on_log_line(
                f"[status] Attempt {attempt}/{max_retries} did not complete"
                f"{wait} — retrying: {first_line}")
        elif ev == "failure":
            # All retries for this video are exhausted.  Do not raise the
            # final error banner yet: the queue may still be downloading
            # more episodes, and the summary at the end reports everything.
            url = str(data.get("url") or "")
            error = str(data.get("error") or "Unknown error").strip()
            first_line = error.splitlines()[0][:240] if error else "Unknown error"
            self.step_chip.setText("Episode failed — continuing")
            self.on_log_line(
                f"[error] Gave up on {url} after all retries: {first_line}")
        elif ev == "success":
            self.step_chip.setText("Completed ✔")
        elif ev == "summary":
            if "fatal" in data:
                fatal = str(data["fatal"])
                self.tile_rate.set("ERR", fatal[:40])
                self.on_log_line(f"[error] {fatal}")
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
        """Append log rows, but update yt-dlp progress rows in place."""
        text = str(line).replace("\r\n", "\n").replace("\r", "\n")
        for chunk in text.split("\n"):
            chunk = chunk.rstrip()
            if not chunk:
                continue
            progress = is_progress_line(chunk)
            if progress and self._progress_active:
                self._replace_last_block(terminal_html(chunk))
            else:
                self.terminal.append(terminal_html(chunk))
            self._progress_active = progress
        self.terminal.ensureCursorVisible()

    def _replace_last_block(self, html: str) -> None:
        block = self.terminal.document().lastBlock()
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertHtml(html)
        self.terminal.setTextCursor(cursor)
