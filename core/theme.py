"""QSS generator for a vivid, configurable VoltHTTP palette (no Qt dependency)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeColors:
    yellow: str
    fuchsia: str
    background: str


PRESETS = {
    "Vivid": ThemeColors("#fff13f", "#ff43bf", "#26162e"),
    "Electric": ThemeColors("#fcff36", "#ff00c8", "#170e2c"),
    "Classic": ThemeColors("#ffe45b", "#8629e6", "#5a2c7a"),
}


def normalize_hex(value: str) -> str:
    value = value.strip()
    if len(value) != 7 or value[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in value[1:]):
        raise ValueError("Color must be a 6-digit hex value, e.g. #ff43bf")
    return value.lower()


def blend(first: str, second: str, ratio: float) -> str:
    """Linear RGB mixing for palette surfaces and edge sheen."""
    r = min(1.0, max(0.0, ratio))
    a = [int(first[i:i+2], 16) for i in (1, 3, 5)]
    b = [int(second[i:i+2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x*(1-r)+y*r):02x}" for x, y in zip(a, b))


def style_for(theme: ThemeColors) -> str:
    y, p, base = (normalize_hex(theme.yellow), normalize_hex(theme.fuchsia), normalize_hex(theme.background))
    surface = blend(base, "#ffffff", 0.090)
    lifted = blend(base, "#ffffff", 0.135)
    input_bg = blend(base, "#000000", 0.28)
    sidebar = blend(base, "#000000", 0.10)
    border = blend(base, p, 0.27)
    bright_border = blend(base, p, 0.50)
    muted = blend(base, "#ffffff", 0.64)
    faint = blend(base, "#ffffff", 0.75)
    pink_soft = blend(p, "#ffffff", 0.45)
    pink_deep = blend(p, "#000000", 0.38)
    yellow_light = blend(y, "#ffffff", 0.64)
    # Background colors remain user-customizable; adapt base text on light selections.
    lum = sum(int(base[i:i+2], 16)*w for i, w in zip((1,3,5), (0.2126, 0.7152, 0.0722)))
    ink = "#211226" if lum > 148 else "#fff6ff"
    field_ink = "#fff6ff" if lum <= 148 else "#211226"
    return f'''
* {{ font-family: 'Inter', 'Segoe UI', Arial, sans-serif; font-size: 12px; }}
QMainWindow, QWidget#root {{ background: {base}; color: {ink}; }}
QWidget {{ color: {ink}; }}
QFrame#topbar {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {lifted}, stop:0.28 {surface}, stop:0.72 {base}, stop:1 {blend(base,p,0.18)}); border-bottom: 2px solid {bright_border}; }}
QLabel#brand {{ color: {y}; font-size: 24px; font-weight: 900; letter-spacing: 1px; }}
QLabel#brandNote {{ color: {pink_soft}; font-size: 10px; letter-spacing: 1px; }}
QLabel#sectionTitle {{ font-size: 11px; font-weight: 900; color: {pink_soft}; letter-spacing: 1.2px; }}
QLabel#hint {{ color: {muted}; font-size: 11px; }}
QFrame#sidebar {{ background: {sidebar}; border-right: 1px solid {border}; }}
QFrame#panel {{ background: {surface}; border: 1px solid {border}; border-radius: 12px; }}
QFrame#responsePanel {{ background: {blend(base,'#ffffff',0.055)}; border: 1px solid {border}; border-radius: 12px; }}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget, QListWidget {{
  background: {input_bg}; border: 1px solid {bright_border}; border-radius: 7px; color: {field_ink};
  selection-background-color: {pink_deep}; selection-color: white; padding: 7px;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QTableWidget:focus {{ border: 2px solid {y}; }}
QPlainTextEdit, QTextEdit {{ font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: {surface}; color: {ink}; selection-background-color: {pink_deep}; border: 1px solid {bright_border}; }}
QPushButton {{ background: {lifted}; border: 1px solid {bright_border}; color: {ink}; padding: 8px 13px; border-radius: 8px; font-weight: 700; }}
QPushButton:hover {{ background: {blend(base,p,0.36)}; border-color: {p}; }}
QPushButton:pressed {{ background: {blend(base,p,0.51)}; }}
QPushButton:disabled {{ color: {muted}; background: {surface}; border-color: {border}; }}
QPushButton#sendButton {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {yellow_light},stop:0.34 {y},stop:1 {blend(y,'#bf7514',0.31)}); border: 1px solid {yellow_light}; color: #2b142c; font-weight: 900; font-size: 14px; padding: 11px 25px; }}
QPushButton#sendButton:hover {{ background: {yellow_light}; }}
QPushButton#pinkButton {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {pink_soft},stop:0.35 {p},stop:1 {pink_deep}); border: 1px solid {pink_soft}; color: #25101c; font-weight: 800; }}
QPushButton#pinkButton:hover {{ background: {pink_soft}; }}
QTabWidget::pane {{ border: 1px solid {border}; border-radius: 8px; background: {surface}; top: -1px; }}
QTabBar::tab {{ background: {lifted}; color: {faint}; padding: 11px 15px; margin-right: 2px; border: 1px solid {border}; border-bottom: 0; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: 700; }}
QTabBar::tab:selected {{ color: {y}; background: {blend(base,p,0.28)}; border-top: 3px solid {p}; }}
QTabBar::tab:hover {{ color: {yellow_light}; }}
QHeaderView::section {{ background: {lifted}; color: {ink}; border: 0; padding: 7px; border-bottom: 1px solid {bright_border}; font-weight: 700; }}
QTableWidget {{ gridline-color: {border}; padding: 0; alternate-background-color: {surface}; }}
QTableWidget::item {{ padding: 4px; }}
QCheckBox {{ color: {ink}; spacing: 8px; }}
QCheckBox::indicator {{ width: 17px; height: 17px; border: 1px solid {p}; border-radius: 4px; background: {input_bg}; }}
QCheckBox::indicator:checked {{ background: {y}; border: 2px solid {p}; }}
QListWidget {{ background: transparent; border: none; }}
QListWidget::item {{ padding: 10px 8px; border-radius: 6px; margin: 1px; }}
QListWidget::item:selected {{ background: {blend(base,p,0.3)}; border-left: 3px solid {y}; }}
QListWidget::item:hover {{ background: {blend(base,p,0.16)}; }}
QSplitter::handle {{ background: transparent; width: 7px; }}
QScrollBar:vertical {{ background: {base}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {bright_border}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QStatusBar {{ background: {base}; color: {faint}; border-top: 1px solid {border}; }}
QToolTip {{ background: {lifted}; color: {ink}; border: 1px solid {p}; padding: 5px; }}
'''


STYLE = style_for(PRESETS["Classic"])
