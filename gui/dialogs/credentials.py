"""First-run / missing-credential dialog backed by the shared config file.

The dialog never reads environment variables and never keeps secrets in the
source tree: values are written straight to
``~/.config/donghua-stream/config.json`` with owner-only permissions.
"""
from typing import Optional

from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QSpinBox, QVBoxLayout, QWidget,
)

import app_config
from ..components.primitives import btn, eyebrow, hline, label_caps, mk_label
from ..icons import icon
from ..theme import (
    F_MONO, T_PRIMARY, T_ROSE2, T_SEC, app_stylesheet,
)

CONSOLE_URL = "https://console.cloud.google.com/apis/credentials"
REGIONS = [
    ("US", "United States"), ("GB", "United Kingdom"), ("CA", "Canada"),
    ("AU", "Australia"), ("IN", "India"), ("SG", "Singapore"),
    ("PH", "Philippines"), ("MY", "Malaysia"), ("ID", "Indonesia"),
    ("DE", "Germany"), ("FR", "France"), ("BR", "Brazil"),
    ("JP", "Japan"), ("KR", "South Korea"),
]


class _Field:
    """Small label + widget pair with a consistent look."""

    def __init__(self, label: str, widget: QWidget):
        self.label = label
        self.widget = widget


class CredentialsDialog(QDialog):
    """Edit database and YouTube credentials without leaving the app."""

    def __init__(self, focus: str = "all", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._focus = focus if focus in ("all", "database", "youtube") else "all"
        self.saved = False
        self.setWindowTitle("Credentials · Donghua Stream")
        self.setMinimumWidth(660)
        self.setStyleSheet(app_stylesheet())

        cfg = app_config.load_config()
        self._db = cfg["database"]
        self._yt = cfg["youtube"]

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(12)

        # ---- heading
        head = QHBoxLayout()
        head.setSpacing(13)
        glyph = QLabel("⌘")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setFixedSize(44, 44)
        glyph.setStyleSheet(
            f"background: rgba(56,189,248,24); color: {T_PRIMARY};"
            "border: 1px solid rgba(56,189,248,100); border-radius: 22px;"
            "font-size: 21px; font-weight: 800;")
        head.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(eyebrow("One config for GUI & CLI"))
        titles.addWidget(mk_label(
            "Connect YouTube" if self._focus == "youtube" else "Connect Donghua Stream",
            "display"))
        titles.addWidget(mk_label(
            "Credentials live only in your user config file and are never "
            "committed with the code.", "body", "muted", wrap=True))
        head.addLayout(titles, 1)
        root.addLayout(head)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_lbl = QLabel(app_config.display_path())
        self.path_lbl.setObjectName("mono")
        self.path_lbl.setStyleSheet(
            f"color: {T_SEC}; font-family: '{F_MONO}'; font-size: 11px;")
        self.path_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_lbl.setToolTip(app_config.config_path())
        path_row.addWidget(self.path_lbl, 1)
        open_folder = btn("Open Folder", "ghost",
                          "Reveal the global config folder", small=True)
        open_folder.setIcon(icon("folder", T_SEC, 13))
        open_folder.setIconSize(QSize(13, 13))
        open_folder.clicked.connect(self._open_config_folder)
        path_row.addWidget(open_folder)
        root.addLayout(path_row)
        root.addWidget(hline())

        # ---- database
        self.db_card = self._card(
            "PostgreSQL catalog",
            "The series, episode and archive registry. Required for the app to start.")
        db_grid = QGridLayout()
        db_grid.setHorizontalSpacing(12)
        db_grid.setVerticalSpacing(9)
        db_grid.setColumnStretch(1, 1)
        db_grid.setColumnStretch(3, 1)

        self.host = QLineEdit(str(self._db.get("host") or ""))
        self.host.setPlaceholderText("localhost")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(self._db.get("port") or 5432))
        self.port.setFixedWidth(110)
        self.user = QLineEdit(str(self._db.get("user") or ""))
        self.user.setPlaceholderText("database user")
        self.password = QLineEdit(str(self._db.get("password") or ""))
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("database password")
        self.dbname = QLineEdit(str(self._db.get("dbname") or ""))
        self.dbname.setPlaceholderText("donghua_db")

        db_grid.addWidget(label_caps("Host"), 0, 0)
        db_grid.addWidget(self.host, 0, 1)
        db_grid.addWidget(label_caps("Port"), 0, 2)
        db_grid.addWidget(self.port, 0, 3)
        db_grid.addWidget(label_caps("User"), 1, 0)
        db_grid.addWidget(self.user, 1, 1)
        db_grid.addWidget(label_caps("Password"), 1, 2)
        db_grid.addWidget(self.password, 1, 3)
        db_grid.addWidget(label_caps("Database"), 2, 0)
        db_grid.addWidget(self.dbname, 2, 1, 1, 3)
        self.db_card.body.addLayout(db_grid)
        self.show_db_pass = QCheckBox("Show password")
        self.show_db_pass.toggled.connect(
            lambda on: self.password.setEchoMode(
                QLineEdit.EchoMode.Normal if on
                else QLineEdit.EchoMode.Password))
        self.db_card.body.addWidget(self.show_db_pass)
        if self._focus != "youtube":
            root.addWidget(self.db_card)

        # ---- YouTube
        self.yt_card = self._card(
            "YouTube Data API v3",
            "Powers Explore. Create a key in Google Cloud Console, enable "
            "YouTube Data API v3, then paste it here.")
        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        self.api_key = QLineEdit(str(self._yt.get("api_key") or ""))
        self.api_key.setPlaceholderText("AIza…")
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setClearButtonEnabled(True)
        key_row.addWidget(self.api_key, 1)
        self.show_key = QCheckBox("Show")
        self.show_key.toggled.connect(
            lambda on: self.api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if on
                else QLineEdit.EchoMode.Password))
        key_row.addWidget(self.show_key)
        holder = QWidget()
        holder.setLayout(key_row)
        self.yt_card.body.addWidget(holder)

        region_row = QHBoxLayout()
        region_row.setSpacing(10)
        region_row.addWidget(label_caps("Region"))
        self.region = QComboBox()
        for code, name in REGIONS:
            self.region.addItem(f"{code}  ·  {name}", code)
        idx = self.region.findData(str(self._yt.get("region_code") or "US"))
        self.region.setCurrentIndex(idx if idx >= 0 else 0)
        self.region.setFixedWidth(210)
        region_row.addWidget(self.region)
        region_row.addStretch(1)
        get_key = btn("Get an API key", "ghost",
                      "Open Google Cloud Console credentials", small=True)
        get_key.setIcon(icon("external", T_SEC, 13))
        get_key.setIconSize(QSize(13, 13))
        get_key.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(CONSOLE_URL)))
        region_row.addWidget(get_key)
        region_holder = QWidget()
        region_holder.setLayout(region_row)
        self.yt_card.body.addWidget(region_holder)
        if self._focus != "database":
            root.addWidget(self.yt_card)

        # ---- inline error
        self.error = QLabel("")
        self.error.setStyleSheet(f"color: {T_ROSE2}; font-size: 12px;")
        self.error.setWordWrap(True)
        self.error.hide()
        root.addWidget(self.error)

        root.addStretch(1)

        # ---- actions
        foot = QHBoxLayout()
        foot.setSpacing(8)
        skip = btn("Not now", "ghost",
                   "Continue without saving; missing features stay disabled")
        skip.clicked.connect(self.reject)
        foot.addWidget(skip)
        foot.addStretch(1)
        self.save_btn = btn(
            "Save & Continue" if self._focus != "youtube" else "Connect YouTube",
            "primary", "Write these values to the global config file")
        self.save_btn.setIcon(icon("check", "#002b40", 14))
        self.save_btn.setIconSize(QSize(14, 14))
        self.save_btn.clicked.connect(self._save)
        foot.addWidget(self.save_btn)
        root.addLayout(foot)

        if self._focus == "youtube":
            self.api_key.setFocus()
        else:
            self.host.setFocus()

    # ---- small layout helpers --------------------------------------------
    class _Card(QFrame):
        def __init__(self, title: str, sub: str):
            super().__init__()
            self.setObjectName("card")
            lay = QVBoxLayout(self)
            lay.setContentsMargins(18, 14, 18, 14)
            lay.setSpacing(8)
            lay.addWidget(mk_label(title, "titleMd"))
            if sub:
                lay.addWidget(mk_label(sub, "small", "muted", wrap=True))
            lay.addWidget(hline())
            self.body = QVBoxLayout()
            self.body.setSpacing(8)
            lay.addLayout(self.body)

    def _card(self, title: str, sub: str) -> "_Card":
        return self._Card(title, sub)

    # ---- actions ----------------------------------------------------------
    def _open_config_folder(self) -> None:
        app_config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(app_config.CONFIG_DIR)))

    def _fail(self, message: str, widget: Optional[QWidget] = None) -> None:
        self.error.setText(message)
        self.error.show()
        if widget is not None:
            widget.setFocus()

    def _save(self) -> None:
        self.error.hide()
        if self._focus != "youtube":
            host = self.host.text().strip()
            user = self.user.text().strip()
            dbname = self.dbname.text().strip()
            if not host:
                self._fail("PostgreSQL host is required.", self.host)
                return
            if not user:
                self._fail("PostgreSQL user is required.", self.user)
                return
            if not dbname:
                self._fail("Database name is required.", self.dbname)
                return
            app_config.set_database({
                "host": host,
                "port": int(self.port.value()),
                "user": user,
                "password": self.password.text(),
                "dbname": dbname,
            })
            # Connection helpers read config lazily; refresh display snapshot.
            try:
                import db
                db.reload_db_config()
            except Exception:
                pass

        if self._focus != "database":
            app_config.set_youtube({
                "api_key": self.api_key.text().strip(),
                "region_code": str(self.region.currentData() or "US"),
            })

        self.saved = True
        self.accept()


def prompt_for_credentials(parent: Optional[QWidget] = None,
                           focus: str = "all") -> bool:
    """Show the dialog and return True when the user saved new values."""
    return CredentialsDialog(focus=focus, parent=parent).exec() == QDialog.DialogCode.Accepted
