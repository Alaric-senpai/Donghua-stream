"""Semantic design tokens and the global stylesheet for Donghua Stream.

The palette keeps the Stitch dark-slate + sky identity. Everything below is a
token so pages never hard-code a raw color or radius.
"""
from .icons import asset_path

# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------
T_CANVAS = "#020617"          # app background
T_CANVAS_SOFT = "#060d1f"     # console / inset wells
T_RAIL = "#0f172a"            # navigation rail
T_RAIL_DEEP = "#0b1222"       # inputs, inner panels
T_CARD = "#1e293b"            # primary card surface
T_CARD_SOFT = "#172134"       # list rows, quiet cards
T_CARD_HI = "#22304a"         # hovered card surface
T_HOVER = "#334155"           # neutral hover
T_LINE = "rgba(51,65,85,90)"
T_LINE_SOFT = "rgba(51,65,85,55)"
T_LINE_STRONG = "rgba(71,85,105,150)"

# ---------------------------------------------------------------------------
# Type & accents
# ---------------------------------------------------------------------------
T_TEXT = "#f8fafc"
T_SEC = "#94a3b8"
T_MUTED = "#8494ab"           # WCAG AA on every surface (4.74:1 on card)
T_FAINT = "#5c6b80"           # decorative only — never body copy

T_PRIMARY = "#38bdf8"         # sky-400
T_PRIMARY_HOVER = "#7dd3fc"
T_PRIMARY_PRESS = "#0ea5e9"
T_PRIMARY_SOFT = "rgba(56,189,248,28)"
T_PRIMARY_LINE = "rgba(56,189,248,110)"
T_ON_PRIMARY = "#002b40"

T_EMERALD = "#10b981"
T_EMERALD2 = "#4edea3"
T_EMERALD_SOFT = "rgba(16,185,129,26)"
T_EMERALD_LINE = "rgba(16,185,129,105)"

T_AMBER = "#f59e0b"
T_AMBER2 = "#fcd34d"
T_AMBER_SOFT = "rgba(245,158,11,26)"
T_AMBER_LINE = "rgba(245,158,11,105)"

T_ROSE = "#f43f5e"
T_ROSE2 = "#fda4af"
T_ROSE_SOFT = "rgba(244,63,94,26)"
T_ROSE_LINE = "rgba(244,63,94,105)"

T_VIOLET = "#a78bfa"

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
F_DISPLAY = "Montserrat"
F_BODY = "Noto Sans"
F_MONO = "Fira Code"

# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------
R_XS = 6
R_SM = 8
R_MD = 10
R_LG = 12
R_XL = 16
R_HERO = 20


def app_stylesheet() -> str:
    """Build the global QSS. Uses rgba(r,g,b,0-255) — never #RRGGBBAA."""
    chevron_down = asset_path("chevron-down.svg")
    chevron_up = asset_path("chevron-up.svg")
    check = asset_path("check.svg")
    return f"""
/* ------------------------------------------------------------------ base */
QWidget {{
    color: {T_TEXT};
    font-family: "{F_BODY}";
    font-size: 13px;
}}
QMainWindow, QDialog {{ background-color: {T_CANVAS}; }}
QWidget#root {{ background-color: {T_CANVAS}; }}
QLabel {{ background: transparent; }}
QStackedWidget, QScrollArea, QWidget#scrollHost,
QWidget#qt_scrollarea_viewport {{ background: transparent; }}

QLabel#eyebrow {{
    color: {T_PRIMARY};
    font-family: "{F_MONO}";
    font-size: 10px;
    font-weight: 600;
}}
QLabel#display {{
    color: {T_TEXT};
    font-family: "{F_DISPLAY}";
    font-size: 27px;
    font-weight: 800;
}}
QLabel#titleXl {{
    color: {T_TEXT}; font-family: "{F_DISPLAY}";
    font-size: 24px; font-weight: 700;
}}
QLabel#titleLg {{
    color: {T_TEXT}; font-family: "{F_DISPLAY}";
    font-size: 20px; font-weight: 700;
}}
QLabel#titleMd {{
    color: {T_TEXT}; font-family: "{F_DISPLAY}";
    font-size: 15px; font-weight: 600;
}}
QLabel#titleSm {{ color: {T_TEXT}; font-size: 13px; font-weight: 700; }}
QLabel#body {{ color: {T_SEC}; font-size: 13px; }}
QLabel#small {{ color: {T_MUTED}; font-size: 11px; }}
QLabel#mono {{
    color: {T_SEC}; font-family: "{F_MONO}"; font-size: 11px;
}}
QLabel#labelCaps {{
    color: {T_MUTED}; font-family: "{F_MONO}";
    font-size: 10px; font-weight: 600;
}}
QLabel#codePill {{
    color: {T_PRIMARY}; font-family: "{F_MONO}"; font-size: 11px;
}}
QLabel#heroTitle {{
    color: {T_TEXT}; font-family: "{F_DISPLAY}";
    font-size: 31px; font-weight: 800;
}}
QLabel#heroBody {{ color: {T_SEC}; font-size: 13px; }}
QLabel#heroMeta {{
    color: {T_MUTED}; font-family: "{F_MONO}"; font-size: 11px;
}}
QLabel#statValue {{
    color: {T_TEXT}; font-family: "{F_MONO}";
    font-size: 18px; font-weight: 700;
}}
QLabel#statCap {{
    color: {T_MUTED}; font-family: "{F_MONO}";
    font-size: 9px; font-weight: 600;
}}
QLabel#crumb {{ color: {T_SEC}; font-size: 13px; font-weight: 600; }}

/* ----------------------------------------------------------------- cards */
QFrame#card {{
    background-color: {T_CARD};
    border: 1px solid {T_LINE};
    border-radius: {R_XL}px;
}}
QFrame#cardSoft {{
    background-color: {T_CARD_SOFT};
    border: 1px solid {T_LINE_SOFT};
    border-radius: {R_LG}px;
}}
QFrame#panel {{
    background-color: {T_RAIL_DEEP};
    border: 1px solid {T_LINE};
    border-radius: {R_LG}px;
}}
QFrame#subtleBar {{
    background-color: {T_RAIL_DEEP};
    border: 1px solid {T_LINE_SOFT};
    border-radius: {R_LG}px;
}}
QFrame#seriesCard {{
    background-color: {T_CARD_SOFT};
    border: 1px solid {T_LINE_SOFT};
    border-radius: {R_LG}px;
}}
QFrame#seriesCard:hover {{
    background-color: {T_CARD_HI};
    border-color: {T_PRIMARY_LINE};
}}
QFrame#listRow {{
    background-color: {T_CARD_SOFT};
    border: 1px solid {T_LINE_SOFT};
    border-radius: {R_LG}px;
}}
QFrame#listRow:hover {{
    background-color: #1b2942;
    border-color: {T_PRIMARY_LINE};
}}
QFrame#episodeRow {{
    background-color: {T_CARD_SOFT};
    border: 1px solid {T_LINE_SOFT};
    border-radius: {R_MD}px;
}}
QFrame#episodeRow:hover {{
    background-color: #1b2942;
    border-color: {T_LINE_STRONG};
}}
QFrame#queueRow {{
    background-color: {T_CARD_SOFT};
    border: 1px solid {T_LINE_SOFT};
    border-radius: {R_MD}px;
}}
QFrame#queueRow[active="true"] {{
    background-color: {T_PRIMARY_SOFT};
    border: 1px solid {T_PRIMARY_LINE};
}}
QFrame#storageCard {{
    background-color: {T_RAIL_DEEP};
    border: 1px solid {T_LINE};
    border-radius: {R_LG}px;
}}
QFrame#storageCard:hover {{
    background-color: #101c31;
    border-color: {T_PRIMARY_LINE};
}}
QFrame#storageCard[checked="true"] {{
    background-color: {T_PRIMARY_SOFT};
    border: 1px solid {T_PRIMARY};
}}
QFrame#statusStrip {{
    background-color: {T_RAIL};
    border-top: 1px solid {T_LINE};
}}
QFrame#heroChrome {{ background: transparent; border: none; }}
QFrame#hline {{ background: {T_LINE}; max-height: 1px; border: none; }}
QFrame#vline {{ background: {T_LINE}; max-width: 1px; border: none; }}

/* --------------------------------------------------------------- buttons */
QPushButton {{
    background-color: {T_CARD};
    color: {T_TEXT};
    border: 1px solid {T_LINE};
    border-radius: {R_MD}px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {T_HOVER}; border-color: {T_LINE_STRONG}; }}
QPushButton:pressed {{ background-color: #263449; }}
QPushButton:disabled {{ color: {T_FAINT}; border-color: {T_LINE_SOFT}; }}

QPushButton#primary {{
    background-color: {T_PRIMARY};
    color: {T_ON_PRIMARY};
    border: 1px solid {T_PRIMARY};
    border-radius: {R_MD}px;
    font-weight: 800;
}}
QPushButton#primary:hover {{ background-color: {T_PRIMARY_HOVER}; border-color: {T_PRIMARY_HOVER}; }}
QPushButton#primary:pressed {{ background-color: {T_PRIMARY_PRESS}; border-color: {T_PRIMARY_PRESS}; }}
QPushButton#primary:disabled {{
    background-color: #12384c; color: #6f9fb4; border-color: #12384c;
}}

QPushButton#ghost {{
    background-color: {T_CARD};
    color: {T_TEXT};
    border: 1px solid {T_LINE};
}}
QPushButton#ghost:hover {{ background-color: {T_HOVER}; border-color: {T_LINE_STRONG}; }}
QPushButton#danger {{
    background-color: transparent;
    color: {T_ROSE2};
    border: 1px solid {T_ROSE_LINE};
}}
QPushButton#danger:hover {{ background-color: {T_ROSE_SOFT}; border-color: {T_ROSE}; }}
QPushButton#success {{
    background-color: {T_EMERALD};
    color: #00311f;
    border: 1px solid {T_EMERALD};
    font-weight: 800;
}}
QPushButton#success:hover {{ background-color: {T_EMERALD2}; border-color: {T_EMERALD2}; }}

QPushButton#iconBtn {{
    background-color: rgba(30,41,59,190);
    color: {T_SEC};
    border: 1px solid {T_LINE_SOFT};
    border-radius: {R_SM}px;
    font-size: 12px;
    padding: 0px;
}}
QPushButton#iconBtn:hover {{
    background-color: {T_PRIMARY_SOFT};
    color: {T_PRIMARY};
    border-color: {T_PRIMARY_LINE};
}}
QPushButton#iconBtn:disabled {{ color: #475569; background-color: transparent; }}
QPushButton#iconBtn[danger="true"]:hover {{
    background-color: {T_ROSE_SOFT}; color: {T_ROSE2}; border-color: {T_ROSE_LINE};
}}

QPushButton#chip {{
    background-color: {T_CARD_SOFT};
    border: 1px solid {T_LINE};
    border-radius: {R_SM}px;
    color: {T_SEC};
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton#chip:hover {{ border-color: {T_LINE_STRONG}; color: {T_TEXT}; }}
QPushButton#chip:checked {{
    background-color: {T_PRIMARY_SOFT};
    border-color: {T_PRIMARY_LINE};
    color: #bae6fd;
    font-weight: 700;
}}
QPushButton#chip:disabled {{ color: {T_FAINT}; }}
QPushButton#chipTri {{
    background-color: {T_AMBER_SOFT};
    border: 1px solid {T_AMBER_LINE};
    border-radius: {R_SM}px;
    color: {T_AMBER2};
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}}
QPushButton#chipEmerge {{
    background-color: {T_EMERALD_SOFT};
    border: 1px solid {T_EMERALD_LINE};
    border-radius: {R_SM}px;
    color: {T_EMERALD2};
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}}
QPushButton#chipActive {{
    background-color: {T_PRIMARY};
    border: 1px solid {T_PRIMARY};
    border-radius: {R_SM}px;
    color: {T_ON_PRIMARY};
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 800;
}}

/* ------------------------------------------------------------------- nav */
QPushButton#navBtn {{
    text-align: left;
    padding: 9px 12px;
    border-radius: 9px;
    color: {T_SEC};
    background: transparent;
    border: 1px solid transparent;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#navBtn:hover {{
    background-color: rgba(51,65,85,95);
    color: {T_TEXT};
    border-color: transparent;
}}
QPushButton#navBtn:checked {{
    background-color: {T_PRIMARY_SOFT};
    color: {T_PRIMARY};
    border: 1px solid {T_PRIMARY_LINE};
    font-weight: 700;
}}
QPushButton#navAction {{
    text-align: left;
    padding: 10px 12px;
    border-radius: 9px;
    background-color: {T_PRIMARY_SOFT};
    border: 1px solid {T_PRIMARY_LINE};
    color: {T_PRIMARY};
    font-size: 13px;
    font-weight: 700;
}}
QPushButton#navAction:hover {{
    background-color: rgba(56,189,248,45);
    border-color: {T_PRIMARY};
}}

/* ---------------------------------------------------------------- inputs */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {T_RAIL_DEEP};
    border: 1px solid {T_LINE};
    border-radius: {R_MD}px;
    padding: 8px 12px;
    color: {T_TEXT};
    font-size: 13px;
    selection-background-color: {T_PRIMARY};
    selection-color: {T_ON_PRIMARY};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {T_LINE_STRONG}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {T_PRIMARY};
    background-color: #0d1729;
}}
QLineEdit:disabled {{ color: {T_FAINT}; }}
QLineEdit#search {{
    background-color: {T_CARD_SOFT};
    border: 1px solid {T_LINE};
    border-radius: {R_MD}px;
    padding: 8px 12px;
    color: {T_TEXT};
    font-size: 12px;
}}
QLineEdit#search:focus {{
    border-color: {T_PRIMARY};
    background-color: #1b2942;
}}

QComboBox {{
    background-color: {T_RAIL_DEEP};
    border: 1px solid {T_LINE};
    border-radius: {R_MD}px;
    padding: 7px 30px 7px 12px;
    color: {T_TEXT};
    font-size: 12px;
}}
QComboBox:hover {{ border-color: {T_LINE_STRONG}; }}
QComboBox:focus {{ border-color: {T_PRIMARY}; }}
QComboBox#chip {{
    background-color: {T_CARD_SOFT};
    border: 1px solid {T_LINE};
    border-radius: {R_SM}px;
    padding: 0px 26px 0px 10px;
    color: {T_SEC};
    font-size: 11px;
    font-weight: 600;
}}
QComboBox#chip:hover {{ border-color: {T_LINE_STRONG}; color: {T_TEXT}; }}
QComboBox#chip:focus {{ border-color: {T_PRIMARY}; color: {T_TEXT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: url({chevron_down});
    width: 12px; height: 12px;
}}
QComboBox QAbstractItemView {{
    background-color: {T_CARD};
    border: 1px solid {T_LINE_STRONG};
    border-radius: {R_SM}px;
    padding: 4px;
    selection-background-color: {T_PRIMARY_SOFT};
    selection-color: {T_TEXT};
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    color: {T_SEC};
    padding: 6px 10px;
    min-height: 22px;
    border-radius: {R_XS}px;
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {T_PRIMARY_SOFT};
    color: {T_TEXT};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid {T_LINE};
    border-top-right-radius: {R_MD}px;
    background: transparent;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    border-left: 1px solid {T_LINE};
    border-bottom-right-radius: {R_MD}px;
    background: transparent;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {T_HOVER};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({chevron_up}); width: 10px; height: 10px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({chevron_down}); width: 10px; height: 10px;
}}

QTextEdit {{
    background-color: {T_RAIL_DEEP};
    border: 1px solid {T_LINE};
    border-radius: {R_MD}px;
    color: {T_TEXT};
    font-size: 13px;
    padding: 10px;
    selection-background-color: {T_PRIMARY};
    selection-color: {T_ON_PRIMARY};
}}
QTextEdit:focus {{ border-color: {T_PRIMARY}; }}
QTextEdit#codeInput {{
    font-family: "{F_MONO}";
    font-size: 11px;
    color: #cbd5e1;
    padding: 12px;
}}
QTextEdit#console {{
    background-color: {T_CANVAS_SOFT};
    border: 1px solid {T_LINE_SOFT};
    border-radius: {R_SM}px;
    font-family: "{F_MONO}";
    font-size: 11px;
    color: #cbd5e1;
    padding: 12px;
}}

QCheckBox {{ color: {T_SEC}; font-size: 12px; spacing: 8px; }}
QCheckBox:hover {{ color: {T_TEXT}; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border-radius: 5px;
    border: 1px solid #475569;
    background-color: {T_RAIL_DEEP};
}}
QCheckBox::indicator:hover {{ border-color: {T_PRIMARY}; }}
QCheckBox::indicator:checked {{
    background-color: {T_PRIMARY};
    border-color: {T_PRIMARY};
    image: url({check});
}}

/* ------------------------------------------------------------- selectors */
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ color: {T_SEC}; border-radius: {R_SM}px; padding: 6px 10px; }}
QListWidget::item:selected {{ background: {T_HOVER}; color: {T_TEXT}; }}

/* -------------------------------------------------------------- progress */
QProgressBar {{
    background-color: #0d1729;
    border: none;
    border-radius: 3px;
    text-align: center;
    color: transparent;
    min-height: 6px;
    max-height: 6px;
}}
QProgressBar::chunk {{ border-radius: 3px; background-color: {T_PRIMARY}; }}
QProgressBar#barGreen::chunk {{ background-color: {T_EMERALD}; }}
QProgressBar#barAmber::chunk {{ background-color: {T_AMBER}; }}
QProgressBar#barRose::chunk {{ background-color: {T_ROSE}; }}

/* ------------------------------------------------------------- scrollbars */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #334155;
    min-height: 32px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{ background: #475569; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #334155;
    min-width: 32px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{ background: #475569; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

/* ----------------------------------------------------------------- menus */
QToolTip {{
    background-color: {T_RAIL_DEEP};
    color: {T_TEXT};
    border: 1px solid {T_LINE_STRONG};
    border-radius: {R_SM}px;
    padding: 5px 8px;
    font-size: 11px;
}}
QMenu {{
    background-color: {T_CARD};
    border: 1px solid {T_LINE_STRONG};
    border-radius: {R_SM}px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 20px;
    border-radius: {R_XS}px;
    color: {T_SEC};
}}
QMenu::item:selected {{ background-color: {T_HOVER}; color: {T_TEXT}; }}
QMenu::separator {{ height: 1px; background: {T_LINE}; margin: 5px 8px; }}

QMessageBox {{ background-color: {T_RAIL}; }}
QMessageBox QLabel {{ color: {T_TEXT}; }}
QMessageBox QPushButton {{ min-width: 84px; }}

/* ----------------------------------------------------------------- toast */
QFrame#toast {{
    background-color: {T_RAIL};
    border: 1px solid {T_PRIMARY_LINE};
    border-radius: {R_LG}px;
}}
QFrame#toast[tone="error"] {{ border-color: {T_ROSE_LINE}; }}
QFrame#toast QLabel {{ color: {T_TEXT}; font-size: 12px; }}

/* ------------------------------------------------------------ status bar */
QStatusBar {{
    background-color: {T_RAIL};
    color: {T_MUTED};
    border-top: 1px solid {T_LINE};
}}
QStatusBar::item {{ border: none; }}
"""
