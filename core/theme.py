"""Material-inspired QSS palette for FLukeQuery (Qt-independent design tokens)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeColors:
    yellow: str
    fuchsia: str
    background: str


PRESETS = {
    "Vivid": ThemeColors("#fff13f", "#ff43bf", "#80314f"),
    "Electric": ThemeColors("#fcff36", "#ff00c8", "#170e2c"),
    "Classic": ThemeColors("#ffe45b", "#8629e6", "#5a2c7a"),
}


def normalize_hex(value: str) -> str:
    value = value.strip()
    if len(value) != 7 or value[0] != "#" or any(ch not in "0123456789abcdefABCDEF" for ch in value[1:]):
        raise ValueError("Color must be a 6-digit hex value, e.g. #ff43bf")
    return value.lower()


def blend(first: str, second: str, ratio: float) -> str:
    """Mix two sRGB hex colors; existing public helper retained for imports/tests."""
    r = min(1.0, max(0.0, ratio))
    a = [int(first[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(second[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * (1 - r) + y * r):02x}" for x, y in zip(a, b))


def rgba(color: str, opacity: float) -> str:
    """Qt QSS rgba color, with an integer 0–255 alpha channel."""
    c = normalize_hex(color)
    alpha = round(min(1.0, max(0.0, float(opacity))) * 255)
    return f"rgba({int(c[1:3], 16)}, {int(c[3:5], 16)}, {int(c[5:7], 16)}, {alpha})"


def relative_luminance(color: str) -> float:
    """sRGB relative luminance, useful for automatic text contrast."""
    rgb = [int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    rgb = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * weight for v, weight in zip(rgb, (0.2126, 0.7152, 0.0722)))


def contrast_ink(background: str) -> str:
    black, white = "#1b1024", "#fffaff"
    lum = relative_luminance(normalize_hex(background))
    return black if (lum + 0.05) / (relative_luminance(black) + 0.05) >= (relative_luminance(white) + 0.05) / (lum + 0.05) else white


@dataclass(frozen=True)
class MaterialTokens:
    background: str
    surface: str
    surface_alt: str
    raised: str
    field: str
    border: str
    border_focus: str
    text: str
    muted: str
    accent: str
    accent_ink: str
    secondary: str
    secondary_ink: str
    hover: str
    selected: str
    sheen: str


def tokens_for(theme: ThemeColors) -> MaterialTokens:
    yellow, pink, base = (normalize_hex(theme.yellow), normalize_hex(theme.fuchsia),
                          normalize_hex(theme.background))
    dark = relative_luminance(base) < 0.23
    text = "#fffaff" if dark else "#23152a"
    return MaterialTokens(
        background=base,
        surface=blend(base, "#ffffff" if dark else "#000000", 0.13 if dark else 0.05),
        surface_alt=blend(base, "#ffffff" if dark else "#000000", 0.085 if dark else 0.03),
        raised=blend(base, "#ffffff" if dark else "#000000", 0.19 if dark else 0.11),
        field=blend(base, "#000000" if dark else "#ffffff", 0.25 if dark else 0.76),
        border=blend(base, "#ffffff" if dark else "#000000", 0.24 if dark else 0.20),
        border_focus=yellow,
        text=text,
        muted=blend(text, base, 0.34 if dark else 0.39),
        accent=yellow,
        accent_ink=contrast_ink(yellow),
        secondary=pink,
        secondary_ink=contrast_ink(pink),
        hover=blend(base, pink, 0.32 if dark else 0.18),
        selected=blend(base, pink, 0.24 if dark else 0.13),
        sheen=blend(base, "#ffffff", 0.23 if dark else 0.12),
    )


def style_for(theme: ThemeColors, glass: int = 55) -> str:
    """Return a material-style palette with adjustable *surface* translucency.

    glass=0 is opaque; 85 has the most transparent surfaces.
    This changes child surfaces only, not the window's desktop opacity.
    """
    glass = max(0, min(85, int(glass)))
    panel_alpha = 1 - glass * 0.0065
    sidebar_alpha = 1 - glass * 0.0071
    field_alpha = 1 - glass * 0.0038
    bar_alpha = 1 - glass * 0.0049
    tab_alpha = 1 - glass * 0.0065
    t = tokens_for(theme)
    y, p = t.accent, t.secondary
    pink_bright = blend(p, "#ffffff", 0.36)
    raised_light = blend(t.raised, "#ffffff", 0.07)
    background_start = blend(t.background, t.secondary, 0.17)
    background_middle = blend(t.background, "#ffffff", 0.045)
    background_end = blend(t.background, t.accent, 0.11)
    return f"""
* {{ font-family: 'Segoe UI Variable', 'Segoe UI', Arial, sans-serif; font-size: 13px; }}
QMainWindow {{ background: {t.background}; color: {t.text}; }}
QWidget#root {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 {background_start},stop:0.38 {background_middle},
        stop:0.70 {t.background},stop:1 {background_end});
    color: {t.text};
}}
QWidget {{ color: {t.text}; }}
QFrame#topbar {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {rgba(t.sheen, bar_alpha)},stop:0.12 {rgba(t.raised, bar_alpha)},
        stop:0.86 {rgba(t.surface_alt, bar_alpha)},stop:1 {rgba(t.surface_alt, bar_alpha)});
    border: none; border-bottom: 1px solid {t.border};
}}
QLabel#brand {{ color: {y}; font-size: 25px; font-weight: 800; }}
QLabel#brandNote {{ color: {pink_bright}; font-size: 10px; font-weight: 600; }}
QLabel#sectionTitle {{ color: {pink_bright}; font-size: 11px; font-weight: 800; }}
QLabel#hint {{ color: {t.muted}; font-size: 11px; }}
QFrame#sidebar {{
    background: {rgba(t.surface_alt, sidebar_alpha)}; border: none;
    border-right: 1px solid {rgba(t.border, 0.65)};
}}
QFrame#panel, QFrame#responsePanel {{
    background: {rgba(t.surface, panel_alpha)}; border: 1px solid {rgba(t.border, 0.65)}; border-radius: 19px;
}}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
QTableWidget {{
    background: {rgba(t.field, field_alpha)}; color: {t.text}; border: 1px solid {rgba(t.border, 0.80)};
    border-radius: 11px; padding: 8px 11px;
    selection-background-color: {t.secondary}; selection-color: {t.secondary_ink};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QTableWidget:focus {{
    border: 2px solid {t.border_focus};
}}
QLineEdit:disabled, QComboBox:disabled, QPlainTextEdit:disabled {{
    background: {t.surface_alt}; color: {t.muted};
}}
QPlainTextEdit, QTextEdit {{
    font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px;
}}
QComboBox {{ padding-right: 30px; }}
QComboBox#methodSelector {{
    background: {rgba(t.raised, field_alpha)}; border: 1px solid {p};
    color: {y}; font-weight: 800; border-radius: 13px;
}}
QComboBox::drop-down {{ border: none; width: 27px; }}
QComboBox QAbstractItemView {{
    background: {t.raised}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 10px;
    padding: 5px; outline: none;
    selection-background-color: {t.selected}; selection-color: {y};
}}
QComboBox QAbstractItemView::item {{
    padding: 7px 11px; border-radius: 7px; min-height: 29px;
}}
QPushButton {{
    color: {t.text}; background: {rgba(t.raised, bar_alpha)};
    border: 1px solid {t.border}; border-radius: 12px;
    padding: 8px 16px; font-weight: 650;
}}
QPushButton:hover {{ background: {rgba(t.hover, 0.91)}; border: 1px solid {p}; }}
QPushButton:pressed {{ background: {rgba(t.selected, 0.92)}; border: 1px solid {y}; }}
QPushButton:focus {{ border: 2px solid {y}; }}
QPushButton:disabled {{
    color: {t.muted}; background: {t.surface_alt}; border: 1px solid {t.border};
}}
QPushButton#sendButton {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {blend(y, "#ffffff", 0.36)}, stop:0.22 {y}, stop:1 {blend(y, "#000000", 0.13)});
    color: {t.accent_ink}; border: 1px solid {blend(y, "#ffffff", 0.30)};
    font-weight: 800; font-size: 14px; border-radius: 14px; padding: 9px 24px;
}}
QPushButton#sendButton:hover {{ background: {blend(y, "#ffffff", 0.20)}; }}
QPushButton#sendButton:disabled {{ background: {t.raised}; color: {t.muted}; border: 1px solid {t.border}; }}
QPushButton#pinkButton {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {pink_bright},stop:0.20 {p},stop:1 {blend(p, "#000000", 0.16)});
    border: 1px solid {pink_bright}; color: {t.secondary_ink};
    font-weight: 800; border-radius: 12px;
}}
QPushButton#pinkButton:hover {{ background: {pink_bright}; }}
QTabWidget::pane {{ background: transparent; border: none; top: 0px; }}
QTabBar {{ background: transparent; border: none; }}
QTabBar::tab {{
    background: transparent; color: {t.muted};
    padding: 10px 18px; margin: 2px 5px 7px 0;
    border: 1px solid transparent; border-radius: 12px; font-weight: 650;
}}
QTabBar::tab:selected {{
    background: {rgba(t.selected, tab_alpha)}; color: {y};
    border: 1px solid {rgba(blend(t.border, p, 0.5), 0.6)};
    font-weight: 800;
}}
QTabBar::tab:hover:!selected {{ background: {rgba(t.hover, tab_alpha)}; color: {t.text}; }}
QHeaderView::section {{
    background: {rgba(t.raised, field_alpha)}; color: {t.text}; border: none;
    border-bottom: 1px solid {t.border}; padding: 9px 12px; font-weight: 700;
}}
QTableWidget {{ gridline-color: {rgba(t.border, 0.5)}; alternate-background-color: {rgba(t.surface_alt, field_alpha)}; padding: 0; }}
QTableWidget::item {{ padding: 5px; }}
QTableWidget::item:selected {{ background: {t.selected}; color: {t.text}; }}
QCheckBox {{ spacing: 10px; color: {t.text}; background: transparent; }}
QCheckBox::indicator {{ width: 19px; height: 19px; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 10px 12px; border-radius: 9px; margin: 2px; }}
QListWidget::item:selected {{
    background: {rgba(t.selected, 0.82)}; color: {y}; border-left: 3px solid {y};
}}
QListWidget::item:hover:!selected {{ background: {rgba(t.hover, 0.70)}; }}
QSplitter::handle {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px 1px; }}
QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {p}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; }}
QScrollBar::handle:horizontal {{ background: {t.border}; border-radius: 5px; min-width: 28px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QStatusBar {{ background: {rgba(t.surface_alt, bar_alpha)}; color: {t.muted}; border-top: 1px solid {rgba(t.border, 0.55)}; }}
QSlider::groove:horizontal {{ height: 6px; background: {rgba(t.field, field_alpha)}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {p}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {y}; width: 17px; margin: -7px 0; border-radius: 8px;
    border: 2px solid {t.surface};
}}
QToolTip {{
    background: {raised_light}; color: {t.text}; border: 1px solid {p};
    border-radius: 9px; padding: 7px 10px;
}}
"""


STYLE = style_for(PRESETS["Vivid"])