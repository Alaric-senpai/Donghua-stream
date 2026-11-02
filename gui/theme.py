"""Design tokens and the global QSS, straight from the Stitch system."""


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

