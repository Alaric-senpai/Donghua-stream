"""Modal used by Explore to add a whole source series to the library.

YouTube results are single videos, but AnimeCube and DonghuaStream results are
series pages.  This dialog keeps the same "pick or create a library series"
flow as :mod:`add_video` and adds a checklist of the episodes discovered on the
source page.
"""
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QVBoxLayout, QWidget,
)

from ..components.primitives import btn, eyebrow, hline, label_caps, mk_label
from ..theme import F_MONO, T_MUTED, T_ROSE2, T_SEC, app_stylesheet


def _suggest_name(details: Dict[str, Any]) -> str:
    title = str(details.get("title") or "").strip()
    return title or "New Donghua"


def _episode_text(episode: Dict[str, Any]) -> str:
    number = episode.get("episode_number")
    prefix = f"EP {int(number):03d}" if isinstance(number, int) else "EP"
    title = str(episode.get("title") or "").strip()
    if title and title.lower() not in ("", prefix.lower()):
        return f"{prefix}  ·  {title}"
    return prefix


class SourceEpisodesDialog(QDialog):
    """Choose episodes and the library series that should own them."""

    def __init__(self, details: Dict[str, Any],
                 series_list: List[Dict[str, Any]],
                 download_now: bool = False,
                 target_mode: str = "any",
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.details = dict(details or {})
        # "any"     — existing series first, plus a "create new" entry
        # "existing"— only existing library series may be targeted
        # "new"     — start on the "create a new series" entry
        self.target_mode = str(target_mode or "any")
        self._series = list(series_list or [])
        self.episodes = sorted(
            list(self.details.get("episodes") or []),
            key=lambda ep: (ep.get("episode_number") or 0,
                            str(ep.get("title") or "")))
        self._checks: List[tuple[QCheckBox, Dict[str, Any]]] = []

        source_label = str(
            self.details.get("channel") or self.details.get("source") or
            "Source").strip()
        self.setWindowTitle(f"Add series · {source_label} · Donghua Stream")
        self.setMinimumWidth(640)
        self.setStyleSheet(app_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(11)

        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(eyebrow("Save a source series"))
        head.addWidget(mk_label("Add Series to Library", "display"))
        self._head_note = mk_label(
            "Choose which episodes to register, then pick the series that "
            "should own them.", "body", "muted")
        head.addWidget(self._head_note)
        root.addLayout(head)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 13, 16, 13)
        cl.setSpacing(5)

        title = QLabel(str(self.details.get("title") or "Untitled series"))
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
        cl.addWidget(title)

        bits = [source_label]
        year = self.details.get("year")
        if year:
            bits.append(str(year))
        bits.append(f"{len(self.episodes)} episodes")
        meta = QLabel("  ·  ".join(bits))
        meta.setStyleSheet(
            f"color: {T_MUTED}; font-family: '{F_MONO}'; font-size: 10px;")
        cl.addWidget(meta)

        description = str(self.details.get("description") or "").strip()
        if description:
            if len(description) > 260:
                description = description[:257].rstrip() + "…"
            desc = QLabel(description)
            desc.setWordWrap(True)
            desc.setMaximumHeight(52)
            desc.setStyleSheet(f"color: {T_SEC}; font-size: 11px;")
            cl.addWidget(desc)

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
        self._new_index = -1
        if self.target_mode != "existing":
            self._new_index = self.target.count()
            self.target.addItem("＋  Create a new series…", None)
        if self.target_mode == "existing" and self._new_index == 0:
            # No library series yet: fall back to creating one.
            self.target_mode = "new"
        self.target.currentIndexChanged.connect(self._on_target_changed)
        self.target.setVisible(self.target_mode != "new")
        cl.addWidget(self.target)

        self.new_name = QLineEdit(_suggest_name(self.details))
        self.new_name.setPlaceholderText("New series name")
        self.new_hint = QLabel("")
        self.new_hint.setStyleSheet(
            f"color: {T_MUTED}; font-family: '{F_MONO}'; font-size: 9px;")
        cl.addWidget(self.new_name)
        cl.addWidget(self.new_hint)

        self.download_chk = QCheckBox(
            "Queue the selected episodes immediately after saving")
        self.download_chk.setChecked(bool(download_now))
        self.download_chk.toggled.connect(self._sync_button_text)
        cl.addWidget(self.download_chk)
        root.addWidget(card)

        # ---- episode checklist -------------------------------------------
        pick_head = QHBoxLayout()
        pick_head.setSpacing(8)
        pick_head.addWidget(label_caps("Episodes"))
        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(
            f"color: {T_MUTED}; font-family: '{F_MONO}'; font-size: 9px;")
        pick_head.addWidget(self.count_lbl)
        pick_head.addStretch(1)
        for text, tip, handler in (
                ("All", "Select every episode", lambda: self._set_all(True)),
                ("None", "Clear the episode selection",
                 lambda: self._set_all(False)),
                ("Latest", "Select only the newest episode",
                 self._latest_only)):
            action = btn(text, "ghost", tip, small=True)
            action.setFixedHeight(26)
            action.clicked.connect(handler)
            pick_head.addWidget(action)
        root.addLayout(pick_head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setMinimumHeight(190)
        self.scroll.setMaximumHeight(250)
        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(4, 2, 8, 2)
        holder_layout.setSpacing(2)
        if self.episodes:
            for episode in self.episodes:
                check = QCheckBox(_episode_text(episode))
                check.setChecked(True)
                check.toggled.connect(self._sync_selection)
                holder_layout.addWidget(check)
                self._checks.append((check, episode))
            holder_layout.addStretch(1)
        else:
            empty = QLabel(
                "This source page did not list any episodes yet.")
            empty.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
            holder_layout.addWidget(empty)
        self.scroll.setWidget(holder)
        root.addWidget(self.scroll)

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

        if self.target_mode == "new":
            if self._new_index >= 0:
                self.target.setCurrentIndex(self._new_index)
            self.new_name.setFocus()
        elif self.target_mode == "existing" and self.target.count() > 0:
            self.target.setCurrentIndex(0)
        self._on_target_changed()
        self._sync_selection()

    # ---- selection ---------------------------------------------------------
    def _set_all(self, checked: bool) -> None:
        for check, _episode in self._checks:
            check.blockSignals(True)
            check.setChecked(checked)
            check.blockSignals(False)
        self._sync_selection()

    def _latest_only(self) -> None:
        latest = max(
            (episode.get("episode_number") or 0
             for _check, episode in self._checks), default=0)
        for check, episode in self._checks:
            check.blockSignals(True)
            check.setChecked((episode.get("episode_number") or 0) == latest)
            check.blockSignals(False)
        self._sync_selection()

    def selected_episodes(self) -> List[Dict[str, Any]]:
        return [dict(episode) for check, episode in self._checks
                if check.isChecked()]

    def _sync_selection(self) -> None:
        chosen = len(self.selected_episodes())
        self.count_lbl.setText(f"{chosen} of {len(self._checks)} selected")
        self.save_btn.setEnabled(chosen > 0)
        self._sync_button_text()

    # ---- target series -----------------------------------------------------
    def _target_id(self) -> Optional[int]:
        if self.target_mode == "new":
            return None
        data = self.target.currentData()
        return int(data) if data is not None else None

    def _on_target_changed(self) -> None:
        creating = self._target_id() is None
        self.new_name.setVisible(creating or self.target_mode == "new")
        self.new_hint.setVisible(creating or self.target_mode == "new")
        if creating:
            raw = self.new_name.text().strip() or "New Donghua"
            path = f"~/Videos/{raw.replace(' ', '')}"
            self.new_hint.setText(f"Save folder will be created under {path}")
        self.error.hide()
        self._sync_button_text()

    def _target_label(self) -> str:
        if self.target_mode == "new":
            return "Create a new series"
        return "Add to an existing series"

    def _sync_button_text(self) -> None:
        action = ("Add & Download" if self.download_chk.isChecked()
                  else "Add to Library")
        self.save_btn.setText(action)

    def _save(self) -> None:
        sid = self._target_id()
        name = self.new_name.text().strip()
        if sid is None and not name:
            self.error.setText(
                "Give the new series a name, or pick an existing one.")
            self.error.show()
            self.new_name.setFocus()
            return
        if not self.selected_episodes():
            self.error.setText("Select at least one episode to add.")
            self.error.show()
            return
        self.accept()

    # ---- result ------------------------------------------------------------
    def payload(self) -> Dict[str, Any]:
        sid = self._target_id()
        return {
            "series_id": sid,
            "new_name": self.new_name.text().strip() if sid is None else "",
            "download_now": self.download_chk.isChecked(),
            "episodes": self.selected_episodes(),
            "source": str(self.details.get("source") or ""),
            "source_url": str(self.details.get("url") or ""),
            "title": str(self.details.get("title") or ""),
        }


def prompt_source_episodes(
        details: Dict[str, Any],
        series_list: List[Dict[str, Any]],
        download_now: bool = False,
        target_mode: str = "any",
        parent: Optional[QWidget] = None) -> Optional[Dict[str, Any]]:
    """Ask where the episodes should land.

    ``target_mode`` is "any", "existing" or "new" and decides where the
    target selector starts.
    """
    dialog = SourceEpisodesDialog(
        details, series_list, download_now=download_now,
        target_mode=target_mode, parent=parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.payload()
    return None
