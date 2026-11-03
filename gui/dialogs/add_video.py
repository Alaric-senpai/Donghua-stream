"""Modal used by Explore to attach a YouTube video to a library series."""
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QVBoxLayout, QWidget,
)

from ..components.primitives import btn, eyebrow, hline, label_caps, mk_label
from ..theme import F_MONO, T_MUTED, T_ROSE2, app_stylesheet


def _suggest_name(video: Dict[str, Any]) -> str:
    channel = str(video.get("channel") or "").strip()
    title = str(video.get("title") or "").strip()
    if channel and channel.lower() not in ("youtube", "unknown"):
        return channel
    return title or "New Donghua"


class AddVideoDialog(QDialog):
    """Choose (or create) the series that should own this video."""

    def __init__(self, video: Dict[str, Any],
                 series_list: List[Dict[str, Any]],
                 download_now: bool = False,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.video = dict(video or {})
        self._series = list(series_list or [])
        self.setWindowTitle("Add to library · Donghua Stream")
        self.setMinimumWidth(560)
        self.setStyleSheet(app_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(11)

        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(eyebrow("Save a discovery"))
        head.addWidget(mk_label("Add to Library", "display"))
        head.addWidget(mk_label(
            "Attach this video as an episode, or start a new series from it.",
            "body", "muted"))
        root.addLayout(head)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 13, 16, 13)
        cl.setSpacing(5)
        title = QLabel(str(self.video.get("title") or "Untitled video"))
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
        cl.addWidget(title)
        bits = [str(self.video.get("channel") or "YouTube"),
                str(self.video.get("duration_text") or ""),
                str(self.video.get("views_text") or "")]
        meta = QLabel("  ·  ".join(b for b in bits if b))
        meta.setStyleSheet(
            f"color: {T_MUTED}; font-family: '{F_MONO}'; font-size: 10px;")
        cl.addWidget(meta)
        cl.addWidget(hline())

        cl.addWidget(label_caps("Target series"))
        self.target = QComboBox()
        self.target.setMinimumHeight(34)
        for series in self._series:
            done = int(series.get("downloaded_episodes", 0) or 0)
            total = int(series.get("total_episodes", 0) or 0)
            self.target.addItem(
                f"{series.get('name', 'Untitled')}  ·  {done}/{total} episodes",
                int(series.get("id", 0)))
        self.target.addItem("＋  Create a new series…", None)
        self.target.currentIndexChanged.connect(self._on_target_changed)
        cl.addWidget(self.target)

        self.new_name = QLineEdit(_suggest_name(self.video))
        self.new_name.setPlaceholderText("New series name")
        self.new_hint = QLabel("")
        self.new_hint.setStyleSheet(
            f"color: {T_MUTED}; font-family: '{F_MONO}'; font-size: 9px;")
        cl.addWidget(self.new_name)
        cl.addWidget(self.new_hint)

        self.download_chk = QCheckBox(
            "Queue the download immediately after saving")
        self.download_chk.setChecked(bool(download_now))
        self.download_chk.toggled.connect(self._sync_button_text)
        cl.addWidget(self.download_chk)
        root.addWidget(card)

        self.error = QLabel("")
        self.error.setStyleSheet(f"color: {T_ROSE2}; font-size: 12px;")
        self.error.hide()
        root.addWidget(self.error)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        foot.addStretch(1)
        cancel = btn("Cancel", "ghost")
        cancel.clicked.connect(self.reject)
        foot.addWidget(cancel)
        self.save_btn = btn("Add to Library", "primary")
        self.save_btn.clicked.connect(self._save)
        foot.addWidget(self.save_btn)
        root.addLayout(foot)
        self._on_target_changed()

    # ---- state ------------------------------------------------------------
    def _target_id(self) -> Optional[int]:
        data = self.target.currentData()
        return int(data) if data is not None else None

    def _on_target_changed(self) -> None:
        creating = self._target_id() is None
        self.new_name.setVisible(creating)
        self.new_hint.setVisible(creating)
        if creating:
            raw = self.new_name.text().strip() or "New Donghua"
            path = f"~/Videos/{raw.replace(' ', '')}"
            self.new_hint.setText(f"Save folder will be created under {path}")
        self.error.hide()
        self._sync_button_text()

    def _sync_button_text(self) -> None:
        action = "Add & Download" if self.download_chk.isChecked() else "Add to Library"
        self.save_btn.setText(action)

    def _save(self) -> None:
        sid = self._target_id()
        name = self.new_name.text().strip()
        if sid is None and not name:
            self.error.setText("Give the new series a name, or pick an existing one.")
            self.error.show()
            self.new_name.setFocus()
            return
        self.accept()

    # ---- result -----------------------------------------------------------
    def payload(self) -> Dict[str, Any]:
        sid = self._target_id()
        return {
            "series_id": sid,
            "new_name": self.new_name.text().strip() if sid is None else "",
            "download_now": self.download_chk.isChecked(),
            "url": str(self.video.get("url") or ""),
            "title": str(self.video.get("title") or ""),
            "channel": str(self.video.get("channel") or ""),
            "description": str(self.video.get("description") or ""),
        }


def prompt_add_video(video: Dict[str, Any],
                     series_list: List[Dict[str, Any]],
                     download_now: bool = False,
                     parent: Optional[QWidget] = None) -> Optional[Dict[str, Any]]:
    dlg = AddVideoDialog(video, series_list, download_now=download_now,
                         parent=parent)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return dlg.payload()
    return None
