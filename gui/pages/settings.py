"""Settings: storage, formats, network, auth, database and API credentials."""
import os
from typing import Dict, List, Optional

from PyQt6.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

import app_config
from ..components.primitives import btn, eyebrow, hline, label_caps, mk_label
from ..components.storage_card import StorageCard
from ..dialogs.credentials import REGIONS, CredentialsDialog
from ..icons import icon
from ..theme import F_MONO, T_AMBER2, T_EMERALD2, T_MUTED, T_SEC
from ..utils import (
    BROWSER_OPTIONS, CONTAINER_OPTIONS, QUALITY_OPTIONS, disk_free,
    human_size, load_settings, resolve_path, set_setting,
)

API_CONSOLE_URL = "https://console.cloud.google.com/apis/credentials"


def _display_path(path: str) -> str:
    return (path or "").replace(os.path.expanduser("~"), "~")


class SectionCard(QFrame):
    """A settings card with a heading, divider and a vertical body."""

    def __init__(self, title: str, sub: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(9)
        lay.addWidget(mk_label(title, "titleMd"))
        if sub:
            sub_lbl = mk_label(sub, "small", "muted", wrap=True)
            lay.addWidget(sub_lbl)
        lay.addWidget(hline())
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 2, 0, 0)
        self.body.setSpacing(9)
        lay.addLayout(self.body)
        lay.addStretch(1)

    def add_row(self, label: str, widget: QWidget) -> None:
        """Label on the left, control on the right."""
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(label_caps(label))
        row.addStretch(1)
        row.addWidget(widget)
        wrap = QWidget()
        wrap.setLayout(row)
        self.body.addWidget(wrap)


class SettingsView(QWidget):
    test_connection = pyqtSignal()
    resync_requested = pyqtSignal()
    settings_changed = pyqtSignal(str)     # key that changed, "*" for all
    toast = pyqtSignal(str, bool)

    def __init__(self, settings: Optional[Dict[str, str]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.s: Dict[str, str] = dict(settings or load_settings())
        self._widgets: Dict[str, QWidget] = {}
        self._loading = True
        self._storage_guard = False
        self.tiles: List[StorageCard] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 14, 28, 18)
        outer.setSpacing(12)

        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(eyebrow("Preferences"))
        head.addWidget(mk_label("Settings & Storage", "display"))
        head.addWidget(mk_label(
            "Choose where episodes live, how they are fetched and which engine the app talks to.",
            "body", "muted"))
        outer.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        host.setObjectName("scrollHost")
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 2, 6, 14)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # ---- 1. storage (full width)
        storage = SectionCard(
            "Storage & Directories",
            "Where new episodes are saved. A per-donghua sub-folder keeps every series self-contained.")
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.t_videos = StorageCard(
            "⌂", "Videos", os.path.expanduser("~/Videos"), recommended=True)
        self.t_downloads = StorageCard(
            "⤓", "Downloads", os.path.expanduser("~/Downloads"))
        self.t_docs = StorageCard(
            "▤", "Documents", os.path.expanduser("~/Documents"))
        self.t_custom = StorageCard("✎", "Custom…", os.path.expanduser("~/Videos"))
        self.tiles = [self.t_videos, self.t_downloads, self.t_docs, self.t_custom]
        for t in self.tiles:
            tiles.addWidget(t, 1)
            t.toggled.connect(self._on_tile)
        tile_holder = QWidget()
        tile_holder.setLayout(tiles)
        storage.body.addWidget(tile_holder)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        self.custom_path = QLineEdit()
        self.custom_path.setPlaceholderText("Type or browse any folder for a custom location…")
        self.custom_path.textChanged.connect(self._on_custom_typed)
        self.custom_path.editingFinished.connect(self._on_custom_commit)
        browse = btn("Browse…", "ghost", "Pick a custom save location", small=True)
        browse.clicked.connect(self._pick_custom)
        custom_row.addWidget(self.custom_path, 1)
        custom_row.addWidget(browse)
        custom_holder = QWidget()
        custom_holder.setLayout(custom_row)
        storage.body.addWidget(custom_holder)

        self.subfolder_chk = QCheckBox(
            "Use a per-donghua sub-folder inside the save location")
        self.subfolder_chk.setChecked(self.s.get("per_series_subfolder", "1") == "1")
        self.subfolder_chk.toggled.connect(self._on_subfolder)
        storage.body.addWidget(self.subfolder_chk)
        grid.addWidget(storage, 0, 0, 1, 2)

        # ---- 2. quality & formats (left)
        quality = SectionCard(
            "Quality & Formats",
            "Applied to every new download unless a series overrides it.")
        self._mk_field(quality, "Default quality", "default_quality",
                       ("combo", QUALITY_OPTIONS))
        self._mk_field(quality, "Container format", "default_container",
                       ("combo", CONTAINER_OPTIONS))
        grid.addWidget(quality, 1, 0)

        # ---- 3. network & downloader (right)
        network = SectionCard(
            "Network & Downloader",
            "Retry budget, bandwidth ceiling and subtitle language track.")
        self._mk_field(network, "Max retries per video", "max_retries", ("spin", 1, 20))
        self._mk_field(network, "Subtitle languages", "sub_langs", ("text", "en, zh-Hans"))
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.0, 500.0)
        self.rate_spin.setDecimals(1)
        self.rate_spin.setSingleStep(0.5)
        self.rate_spin.setSuffix(" MB/s")
        self.rate_spin.setFixedWidth(140)
        try:
            self.rate_spin.setValue(float(self.s.get("rate_limit_mb", "0") or 0))
        except (TypeError, ValueError):
            self.rate_spin.setValue(0.0)
        self.rate_spin.valueChanged.connect(
            lambda v: self._save("rate_limit_mb", f"{v:g}"))
        self._widgets["rate_limit_mb"] = self.rate_spin
        network.add_row("Rate limit (0 = unlimited)", self.rate_spin)
        grid.addWidget(network, 1, 1)

        # ---- 4. browser & auth (left)
        browser = SectionCard(
            "Browser & Auth",
            "Which local browser profile yt-dlp should reuse for cookies.")
        self._mk_field(
            browser, "Cookies source", "browser_cookies",
            ("combo", [b for b in BROWSER_OPTIONS if b[0] != "safari"]))
        grid.addWidget(browser, 2, 0)

        # ---- 5. database & daemon (right)
        catalog = SectionCard(
            "Database & Daemon",
            "PostgreSQL credentials now live in the shared config file, not in code.")
        self.db_info = QLabel("")
        self.db_info.setWordWrap(True)
        self.db_info.setStyleSheet(
            f"color: {T_SEC}; font-family: '{F_MONO}'; font-size: 10px;"
            "background: rgba(11,18,34,180); border: 1px solid rgba(51,65,85,70);"
            "border-radius: 8px; padding: 10px 12px;")
        catalog.body.addWidget(self.db_info)
        self.config_lbl = QLabel("")
        self.config_lbl.setWordWrap(True)
        self.config_lbl.setStyleSheet(
            f"color: {T_MUTED}; font-family: '{F_MONO}'; font-size: 9px;")
        self.config_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        catalog.body.addWidget(self.config_lbl)
        dbrow = QHBoxLayout()
        dbrow.setSpacing(8)
        test_btn = btn("⚡  Test Connection", "ghost", "Ping the database now", small=True)
        test_btn.clicked.connect(self.test_connection.emit)
        resync_btn = btn("⟳  Force Re-Sync", "ghost",
                         "Re-sync every series against its downloaded.txt", small=True)
        resync_btn.clicked.connect(self.resync_requested.emit)
        edit_db = btn("Edit Credentials", "ghost",
                      "Edit PostgreSQL credentials in the shared config", small=True)
        edit_db.clicked.connect(self._edit_credentials)
        open_cfg = btn("Config Folder", "ghost",
                       "Reveal the folder that stores config.json", small=True)
        open_cfg.clicked.connect(self._open_config_folder)
        dbrow.addWidget(test_btn)
        dbrow.addWidget(resync_btn)
        dbrow.addWidget(edit_db)
        dbrow.addWidget(open_cfg)
        dbrow.addStretch(1)
        dbholder = QWidget()
        dbholder.setLayout(dbrow)
        catalog.body.addWidget(dbholder)
        grid.addWidget(catalog, 2, 1)

        # ---- 6. YouTube Data API (full width)
        api = SectionCard(
            "YouTube Data API v3",
            "Powers Explore. The key is stored in config.json and shared with the CLI.")
        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("AIza… (leave blank to disable Explore)")
        self.api_key.setClearButtonEnabled(True)
        key_row.addWidget(self.api_key, 1)
        self.show_key = QCheckBox("Show")
        self.show_key.toggled.connect(
            lambda on: self.api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if on
                else QLineEdit.EchoMode.Password))
        key_row.addWidget(self.show_key)
        key_holder = QWidget()
        key_holder.setLayout(key_row)
        api.body.addWidget(key_holder)

        api_row = QHBoxLayout()
        api_row.setSpacing(9)
        api_row.addWidget(label_caps("Region"))
        self.api_region = QComboBox()
        for code, name in REGIONS:
            self.api_region.addItem(f"{code}  ·  {name}", code)
        self.api_region.setFixedWidth(210)
        api_row.addWidget(self.api_region)
        self.api_state = QLabel("")
        self.api_state.setStyleSheet(f"color: {T_MUTED}; font-size: 11px;")
        api_row.addWidget(self.api_state)
        api_row.addStretch(1)
        get_key = btn("Get a key", "ghost", "Open Google Cloud credentials",
                      small=True)
        get_key.setIcon(icon("external", T_SEC, 13))
        get_key.setIconSize(QSize(13, 13))
        get_key.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(API_CONSOLE_URL)))
        save_api = btn("Save API Key", "primary",
                       "Write the YouTube key to the shared config", small=True)
        save_api.clicked.connect(self._save_youtube)
        api_row.addWidget(get_key)
        api_row.addWidget(save_api)
        api_holder = QWidget()
        api_holder.setLayout(api_row)
        api.body.addWidget(api_holder)
        grid.addWidget(api, 3, 0, 1, 2)

        grid.setRowStretch(4, 1)
        scroll.setWidget(host)
        outer.addWidget(scroll, 1)

        # ---- reset footer
        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.disk_lbl = mk_label("", "small")
        footer.addWidget(self.disk_lbl)
        footer.addStretch(1)
        self.reset_btn = btn(
            "Reset to Defaults", "danger",
            "Restore every setting to the shipped default")
        self.reset_btn.clicked.connect(self._reset)
        footer.addWidget(self.reset_btn)
        outer.addLayout(footer)

        for t in self.tiles:
            t.refresh_free()
        self.refresh_connection_info()
        self._sync_controls()
        self._loading = False
        self._update_disk_hint()

    # ---- field builders ---------------------------------------------------
    def _mk_field(self, sec: SectionCard, label: str, key: str,
                  spec: tuple) -> None:
        kind = spec[0]
        if kind == "combo":
            widget = QComboBox()
            widget.setObjectName("chip")
            widget.setFixedHeight(30)
            widget.setMinimumWidth(168)
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
            widget.setFixedWidth(110)
            try:
                widget.setValue(int(self.s.get(key, "3") or 3))
            except (TypeError, ValueError):
                widget.setValue(3)
            widget.valueChanged.connect(lambda v, k=key: self._save(k, str(v)))
            self._widgets[key] = widget
        elif kind == "text":
            widget = QLineEdit(self.s.get(key, ""))
            widget.setPlaceholderText(spec[1] if len(spec) > 1 else "")
            widget.setFixedWidth(200)
            widget.editingFinished.connect(
                lambda w=widget, k=key: self._save(k, w.text().strip() or "en"))
            self._widgets[key] = widget
        else:
            return
        sec.add_row(label, widget)

    # ---- config / credentials --------------------------------------------
    def refresh_connection_info(self) -> None:
        """Refresh labels and API fields from the authoritative config."""
        try:
            cfg = app_config.load_config()
        except Exception:
            return
        db_cfg = cfg.get("database", {})
        yt_cfg = cfg.get("youtube", {})
        try:
            import yt_dlp
            engine_ver = yt_dlp.version.__version__
        except Exception:
            engine_ver = "unknown"
        if hasattr(self, "db_info"):
            self.db_info.setText(
                f"DB     {db_cfg.get('dbname') or '-'} @ "
                f"{db_cfg.get('host') or '-'}:{db_cfg.get('port') or '-'}\n"
                f"USER   {db_cfg.get('user') or '-'}\n"
                f"ENGINE yt-dlp {engine_ver}")
        if hasattr(self, "config_lbl"):
            self.config_lbl.setText(
                f"CONFIG {app_config.display_path()}")
        if hasattr(self, "api_key"):
            if not self.api_key.hasFocus():
                self.api_key.setText(str(yt_cfg.get("api_key") or ""))
            idx = self.api_region.findData(str(yt_cfg.get("region_code") or "US"))
            if idx >= 0 and not self.api_region.hasFocus():
                self.api_region.setCurrentIndex(idx)
            configured = bool(str(yt_cfg.get("api_key") or "").strip())
            self.api_state.setText(
                "✔ configured" if configured else "Missing · Explore disabled")
            self.api_state.setStyleSheet(
                f"color: {T_EMERALD2 if configured else T_AMBER2};"
                "font-size: 11px; font-weight: 600;")

    def _edit_credentials(self) -> None:
        dlg = CredentialsDialog(focus="database", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.refresh_connection_info()
        self.settings_changed.emit("*")
        self.toast.emit("Connection credentials saved to config.json.", True)

    def _open_config_folder(self) -> None:
        app_config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(app_config.CONFIG_DIR)))

    def _save_youtube(self) -> None:
        app_config.set_youtube({
            "api_key": self.api_key.text().strip(),
            "region_code": str(self.api_region.currentData() or "US"),
        })
        self.refresh_connection_info()
        self.settings_changed.emit("*")
        if self.api_key.text().strip():
            self.toast.emit("YouTube API key saved.", True)
        else:
            self.toast.emit("YouTube API key cleared — Explore is disabled.", True)

    # ---- storage selection ------------------------------------------------
    def _select_tile(self, chosen: StorageCard) -> None:
        self._storage_guard = True
        try:
            for t in self.tiles:
                t.setChecked(t is chosen)
        finally:
            self._storage_guard = False
        chosen.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_tile(self, checked: bool) -> None:
        if not checked or self._loading or self._storage_guard:
            return
        src = self.sender()
        if src not in self.tiles:
            return
        self._select_tile(src)
        if src is self.t_custom:
            text = self.custom_path.text().strip()
            if not text:
                text = _display_path(self.s.get("global_save_dir", "~/Videos"))
                self.custom_path.setText(text)
            src.set_dir(resolve_path(text))
        self._save("global_save_dir", src.dir())
        self._update_disk_hint()

    def _on_custom_typed(self, text: str) -> None:
        if not text.strip():
            return
        self.t_custom.set_dir(resolve_path(text))

    def _on_custom_commit(self) -> None:
        text = self.custom_path.text().strip()
        if not text:
            return
        self.t_custom.set_dir(resolve_path(text))
        if not self.t_custom.isChecked():
            self._select_tile(self.t_custom)
            self._save("global_save_dir", self.t_custom.dir())
        self._update_disk_hint()

    def _pick_custom(self) -> None:
        start = os.path.expanduser(self.custom_path.text().strip() or "~")
        path = QFileDialog.getExistingDirectory(self, "Global save location", start)
        if path:
            self.custom_path.setText(path)
            self.t_custom.set_dir(path)
            self._select_tile(self.t_custom)
            self._save("global_save_dir", path)
            self._update_disk_hint()

    def _on_subfolder(self, checked: bool) -> None:
        if self._loading:
            return
        self._save("per_series_subfolder", "1" if checked else "0")

    # ---- persistence ------------------------------------------------------
    def _save(self, key: str, value: str) -> None:
        if self._loading:
            return
        self.s[key] = value
        if set_setting(key, value):
            self.settings_changed.emit(key)
            pretty = value.replace(os.path.expanduser("~"), "~")
            self.toast.emit(f"Saved {key.replace('_', ' ')} · {pretty}", True)
        else:
            self.toast.emit(f"Could not save {key.replace('_', ' ')}", False)
        if key == "global_save_dir":
            self._update_disk_hint()

    def set_default_quality(self, value: str) -> None:
        """Keep the settings combo in sync when the header changes quality."""
        combo = self._widgets.get("default_quality")
        self.s["default_quality"] = value
        if isinstance(combo, QComboBox):
            idx = combo.findData(value)
            if idx >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(idx)
                combo.blockSignals(False)

    def _sync_controls(self) -> None:
        """Push self.s values into every widget (used by reset)."""
        for key, widget in self._widgets.items():
            value = self.s.get(key, "")
            if isinstance(widget, QComboBox):
                idx = widget.findData(value)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QSpinBox):
                try:
                    widget.setValue(int(value or 0))
                except (TypeError, ValueError):
                    widget.setValue(3)
            elif isinstance(widget, QDoubleSpinBox):
                try:
                    widget.setValue(float(value or 0))
                except (TypeError, ValueError):
                    widget.setValue(0.0)
            elif isinstance(widget, QLineEdit):
                widget.setText(value)
        if hasattr(self, "subfolder_chk"):
            self.subfolder_chk.setChecked(
                self.s.get("per_series_subfolder", "1") == "1")
        self._sync_storage()
        self.refresh_connection_info()
        if hasattr(self, "custom_path"):
            self._update_disk_hint()

    def _sync_storage(self) -> None:
        current = os.path.expanduser(self.s.get("global_save_dir", "~/Videos"))
        match: Optional[StorageCard] = None
        for t in self.tiles[:-1]:
            if os.path.normpath(t.dir()) == os.path.normpath(current):
                match = t
                break
        self._loading = True
        try:
            if match is None:
                match = self.t_custom
                self.t_custom.set_dir(current)
            self.custom_path.setText(_display_path(current))
            self._select_tile(match)
            for t in self.tiles:
                t.refresh_free()
        finally:
            self._loading = False

    def _update_disk_hint(self) -> None:
        if not hasattr(self, "disk_lbl"):
            return
        path = self.s.get("global_save_dir", "~/Videos")
        free = disk_free(path)
        if free is None:
            self.disk_lbl.setText("")
            return
        self.disk_lbl.setText(
            f"Save location · {_display_path(path)}  ·  {human_size(free)} free")

    def _reset(self) -> None:
        try:
            self.s = app_config.reset_settings()
        except Exception as exc:
            self.toast.emit(f"Could not reset settings: {exc}", False)
            return
        self._loading = True
        try:
            self._sync_controls()
        finally:
            self._loading = False
        self.settings_changed.emit("*")
        self.toast.emit("Settings restored to defaults.", True)
