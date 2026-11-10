"""Central design tokens brought to you by Florian van den Bersselaar

The colour / spacing tokens are unchanged from the customtkinter version.
On top of them this module builds the Qt look: fonts (``qfont``), a dark
``QPalette`` and the application-wide Qt Style Sheet (``build_stylesheet``).
"""

from __future__ import annotations

from pathlib import Path

BG_DARK = "#0D1117"
BG_CARD = "#161B22"
BG_INPUT = "#1C2128"
BG_HOVER = "#21262D"
BG_SELECTED = "#2D333B"

ACCENT_GOLD = "#D4AF37"
ACCENT_GOLD_HOVER = "#B8960C"
ACCENT_GREEN = "#3FB950"
ACCENT_RED = "#F85149"
ACCENT_BLUE = "#58A6FF"
ACCENT_PURPLE = "#BC8CFF"
ACCENT_ORANGE = "#FF9F1C"
ACCENT_CYAN = "#2EC4B6"

TEXT_PRIMARY = "#E6EDF3"
TEXT_MUTED = "#7D8590"
TEXT_DIM = "#484F58"

BORDER_COLOR = "#30363D"

# Font specs stay as (family, point size[, "bold"]) tuples so they read the
# same as before; ``qfont()`` turns them into QFont objects. Each family is
# a comma-separated fallback list because Georgia / Helvetica Neue / Courier
# New are not installed everywhere (most Linux desktops, for one).
_SERIF = "Georgia, 'DejaVu Serif', 'Liberation Serif', serif"
_SANS = "'Helvetica Neue', 'Segoe UI', 'Inter', 'DejaVu Sans', Arial, sans-serif"
_MONO = "'Courier New', 'DejaVu Sans Mono', 'Liberation Mono', monospace"

FONT_DISPLAY = (_SERIF, 22, "bold")
FONT_HEADING = (_SERIF, 14, "bold")
FONT_SUBHEAD = (_SERIF, 11, "bold")
FONT_BODY = (_SANS, 11)
FONT_MONO = (_MONO, 11)
FONT_MONO_LG = (_MONO, 18, "bold")
FONT_SMALL = (_SANS, 9)
FONT_LABEL = (_SANS, 10)

CORNER_RADIUS = 8
PAD_SM = 6
PAD_MD = 12
PAD_LG = 20

SIDEBAR_WIDTH = 252

PALETTE = [
    ACCENT_GOLD,
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_RED,
    ACCENT_PURPLE,
    ACCENT_ORANGE,
    ACCENT_CYAN,
    "#E71D36",
    "#F72585",
    "#4CC9F0",
    "#7BF1A8",
    "#FFD166",
]

MPL_STYLE = {
    "figure.facecolor": BG_CARD,
    "axes.facecolor": BG_DARK,
    "axes.edgecolor": BORDER_COLOR,
    "axes.labelcolor": TEXT_MUTED,
    "xtick.color": TEXT_MUTED,
    "ytick.color": TEXT_MUTED,
    "text.color": TEXT_PRIMARY,
    "grid.color": BORDER_COLOR,
    "grid.linestyle": "--",
    "grid.alpha": 0.4,
    "lines.linewidth": 2,
    "legend.facecolor": BG_CARD,
    "legend.edgecolor": BORDER_COLOR,
    "legend.labelcolor": TEXT_PRIMARY,
}

ASSETS = Path(__file__).resolve().parent / "assets"


# ── Qt helpers ────────────────────────────────────────────────────────────────


def _families(spec: str) -> list[str]:
    return [f.strip().strip("'\"") for f in spec.split(",") if f.strip()]


def qfont(spec):
    """Turn a ``(families, size[, "bold"])`` tuple into a QFont."""
    from PyQt6.QtGui import QFont

    family, size, *rest = spec
    f = QFont()
    f.setFamilies(_families(family))
    f.setPointSizeF(float(size))
    if "bold" in rest:
        f.setBold(True)
    if "monospace" in family:
        f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def css_font(spec) -> str:
    """The same tuple as a QSS ``font`` shorthand fragment."""
    family, size, *rest = spec
    weight = "bold " if "bold" in rest else ""
    return f"{weight}{size}pt {family}"


def apply_dark_palette(app) -> None:
    """Fusion style + dark palette. The palette matters beyond QSS: matplotlib's
    Qt toolbar picks light or dark icons from it, and native dialogs (file
    pickers, message boxes) use it for anything QSS doesn't reach."""
    from PyQt6.QtGui import QColor, QPalette

    app.setStyle("Fusion")
    p = QPalette()
    R = QPalette.ColorRole
    p.setColor(R.Window, QColor(BG_DARK))
    p.setColor(R.WindowText, QColor(TEXT_PRIMARY))
    p.setColor(R.Base, QColor(BG_INPUT))
    p.setColor(R.AlternateBase, QColor(BG_CARD))
    p.setColor(R.ToolTipBase, QColor(BG_CARD))
    p.setColor(R.ToolTipText, QColor(TEXT_PRIMARY))
    p.setColor(R.PlaceholderText, QColor(TEXT_DIM))
    p.setColor(R.Text, QColor(TEXT_PRIMARY))
    p.setColor(R.Button, QColor(BG_INPUT))
    p.setColor(R.ButtonText, QColor(TEXT_PRIMARY))
    p.setColor(R.BrightText, QColor(ACCENT_RED))
    p.setColor(R.Highlight, QColor(ACCENT_GOLD))
    p.setColor(R.HighlightedText, QColor(BG_DARK))
    p.setColor(R.Link, QColor(ACCENT_BLUE))
    p.setColor(R.Mid, QColor(BORDER_COLOR))
    p.setColor(R.Dark, QColor(BG_DARK))
    p.setColor(R.Light, QColor(BG_SELECTED))
    for role in (R.Text, R.WindowText, R.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(TEXT_DIM))
    app.setPalette(p)


def build_stylesheet() -> str:
    chevron = (ASSETS / "chevron-down.svg").as_posix()
    check = (ASSETS / "check.svg").as_posix()
    left = (ASSETS / "arrow-left.svg").as_posix()
    right = (ASSETS / "arrow-right.svg").as_posix()
    r = CORNER_RADIUS
    return f"""

QMainWindow, QDialog, QMessageBox {{ background: {BG_DARK}; }}
QLabel {{ background: transparent; color: {TEXT_PRIMARY}; }}
QToolTip {{
    background: {BG_CARD}; color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR}; padding: 4px;
}}

/* ── chrome ─────────────────────────────────────────── */
QFrame#TitleBar {{ background: {BG_CARD}; border-bottom: 1px solid {BORDER_COLOR}; }}
QFrame#StatusBar {{ background: {BG_CARD}; border-top: 1px solid {BORDER_COLOR}; }}
QFrame#Card {{
    background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: {r}px;
}}
QFrame#ChartPanel {{ background: {BG_CARD}; border-radius: {r}px; }}
QScrollArea#Sidebar, QWidget#SidebarBody {{ background: {BG_CARD}; border: none; }}
QScrollArea#Sidebar {{ border-right: 1px solid {BORDER_COLOR}; }}
QFrame#Separator {{ background: {BORDER_COLOR}; border: none; }}
QFrame#SectionBar {{ background: {ACCENT_GOLD}; border-radius: 2px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ── tabs ───────────────────────────────────────────── */
QTabWidget::pane {{ border: none; background: {BG_DARK}; }}
QTabWidget::tab-bar {{ alignment: center; }}
QTabBar {{ background: {BG_CARD}; qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: {BG_CARD}; color: {TEXT_PRIMARY};
    padding: 7px 9px; margin: 6px 1px; border: none; border-radius: 6px;
}}
QTabBar::tab:hover {{ background: {BG_HOVER}; }}
QTabBar::tab:selected {{ background: {ACCENT_GOLD}; color: {BG_DARK}; font-weight: bold; }}
QTabBar QToolButton {{ background: {BG_CARD}; border: none; }}
QTabBar QToolButton::left-arrow {{ image: url("{left}"); }}
QTabBar QToolButton::right-arrow {{ image: url("{right}"); }}

/* ── inputs ─────────────────────────────────────────── */
QLineEdit, QComboBox, QSpinBox, QAbstractSpinBox {{
    background: {BG_INPUT}; color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR}; border-radius: 6px;
    padding: 4px 8px; min-height: 22px;
    selection-background-color: {ACCENT_GOLD}; selection-color: {BG_DARK};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {ACCENT_GOLD}; }}
QLineEdit[error="true"], QComboBox[error="true"] {{ border-color: {ACCENT_RED}; }}
QLineEdit[mono="true"], QComboBox[mono="true"], QSpinBox {{ font: {css_font(FONT_MONO)}; }}
QLineEdit#BigAmount {{ font: {css_font(FONT_MONO_LG)}; min-height: 32px; }}
QComboBox {{ padding-right: 28px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 0; border: none;
}}
QAbstractSpinBox QLineEdit, QComboBox QLineEdit {{
    background: transparent; border: none; padding: 0; margin: 0; min-height: 0;
}}
QComboBox::drop-down {{
    subcontrol-origin: border; subcontrol-position: center right;
    width: 24px; border: none; background: {ACCENT_GOLD};
    border-top-right-radius: 6px; border-bottom-right-radius: 6px;
}}
QComboBox::drop-down:hover {{ background: {ACCENT_GOLD_HOVER}; }}
QComboBox::down-arrow {{ image: url("{chevron}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: {BG_CARD}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_COLOR};
    selection-background-color: {BG_HOVER}; selection-color: {ACCENT_GOLD}; outline: 0;
}}

/* ── buttons ────────────────────────────────────────── */
QPushButton {{
    background: {BG_INPUT}; color: {TEXT_PRIMARY};
    border: 1px solid transparent; border-radius: 6px; padding: 5px 10px;
}}
QPushButton:hover {{ background: {BG_HOVER}; }}
QPushButton:pressed {{ background: {BG_SELECTED}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; }}
QPushButton[variant="accent"], QPushButton[variant="secondary"] {{
    font: {css_font((FONT_SUBHEAD[0], 11, "bold"))};
    border-radius: {r}px; min-height: 24px; padding: 6px 12px;
}}
QPushButton[variant="accent"] {{ background: {ACCENT_GOLD}; color: {BG_DARK}; }}
QPushButton[variant="accent"]:hover {{ background: {ACCENT_GOLD_HOVER}; }}
QPushButton[variant="chip"] {{ font: {css_font(FONT_SMALL)}; padding: 3px 2px; }}
QPushButton[variant="outline"] {{ border-color: {BORDER_COLOR}; font: {css_font(FONT_SMALL)}; }}
QPushButton[variant="glyph"] {{ color: {ACCENT_GOLD}; font: {css_font((FONT_SUBHEAD[0], 16))}; padding: 0; }}
QPushButton[variant="muted"] {{ color: {TEXT_MUTED}; font: {css_font(FONT_SMALL)}; }}
QPushButton[segment] {{
    background: {BG_INPUT}; border-radius: 0; padding: 4px 9px;
    font: {css_font(FONT_SMALL)}; border: none;
}}
QPushButton[segment="first"] {{ border-top-left-radius: 6px; border-bottom-left-radius: 6px; }}
QPushButton[segment="last"] {{ border-top-right-radius: 6px; border-bottom-right-radius: 6px; }}
QPushButton[segment="only"] {{ border-radius: 6px; }}
QPushButton[segment]:hover {{ background: {BG_HOVER}; }}
QPushButton[segment]:checked {{ background: {ACCENT_GOLD}; color: {BG_DARK}; }}

/* ── check / radio ──────────────────────────────────── */
QCheckBox, QRadioButton {{ color: {TEXT_PRIMARY}; spacing: 8px; background: transparent; font: {css_font(FONT_SMALL)}; }}
QCheckBox::indicator, QListWidget::indicator {{
    width: 15px; height: 15px; border: 1px solid {TEXT_DIM};
    border-radius: 4px; background: {BG_DARK};
}}
QCheckBox::indicator:hover, QListWidget::indicator:hover {{ border-color: {ACCENT_GOLD}; }}
QCheckBox::indicator:checked, QListWidget::indicator:checked {{
    background: {ACCENT_GOLD}; border-color: {ACCENT_GOLD}; image: url("{check}");
}}
QRadioButton::indicator {{
    width: 12px; height: 12px; border-radius: 8px;
    border: 2px solid {TEXT_DIM}; background: {BG_DARK};
}}
QRadioButton::indicator:hover {{ border-color: {ACCENT_GOLD}; }}
QRadioButton::indicator:checked {{ border: 4px solid {ACCENT_GOLD}; width: 8px; height: 8px; }}

/* ── lists / tables ─────────────────────────────────── */
QListWidget#Checklist {{
    background: {BG_INPUT}; border: none; border-radius: {r}px; padding: 4px;
    font: {css_font(FONT_SMALL)}; outline: 0;
}}
QListWidget#Checklist::item {{ padding: 3px 2px; border-radius: 4px; color: {TEXT_PRIMARY}; }}
QListWidget#Checklist::item:hover {{ background: {BG_HOVER}; }}
QListWidget#Checklist::item:selected {{ background: transparent; color: {TEXT_PRIMARY}; }}

QTableView {{
    background: {BG_DARK}; alternate-background-color: {BG_CARD};
    border: none; gridline-color: transparent; outline: 0;
    selection-background-color: {BG_SELECTED}; selection-color: {TEXT_PRIMARY};
}}
QTableView#Framed {{ background: {BG_CARD}; alternate-background-color: {BG_DARK};
    border: 1px solid {BORDER_COLOR}; border-radius: {r}px; }}

QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {BG_DARK}; color: {ACCENT_GOLD}; border: none;
    border-bottom: 1px solid {BORDER_COLOR}; padding: 6px;
    font: {css_font(FONT_SUBHEAD)};
}}
QTableView#Framed QHeaderView::section {{ background: {BG_CARD}; }}
QHeaderView::section:hover {{ color: {TEXT_PRIMARY}; }}
QHeaderView::down-arrow, QHeaderView::up-arrow {{ image: none; width: 0; }}
QTableCornerButton::section {{ background: {BG_DARK}; border: none; }}

QPlainTextEdit {{
    background: {BG_CARD}; color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR}; border-radius: {r}px; padding: 6px;
    font: {css_font(FONT_MONO)};
    selection-background-color: {ACCENT_GOLD}; selection-color: {BG_DARK};
}}
QPlainTextEdit#Json {{ color: {ACCENT_GREEN}; }}

/* ── scrollbars ─────────────────────────────────────── */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {BG_SELECTED}; border-radius: 3px; }}
QScrollBar::handle:vertical {{ min-height: 30px; }}
QScrollBar::handle:horizontal {{ min-width: 30px; }}
QScrollBar::handle:hover {{ background: {TEXT_DIM}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

/* ── matplotlib toolbar ─────────────────────────────── */
QToolBar {{ background: transparent; border: none; spacing: 2px; }}
QToolBar QToolButton {{ background: transparent; border: none; border-radius: 4px; padding: 3px; }}
QToolBar QToolButton:hover {{ background: {BG_HOVER}; }}
QToolBar QToolButton:checked {{ background: {BG_SELECTED}; }}
QToolBar QLabel {{ color: {TEXT_MUTED}; font: {css_font(FONT_SMALL)}; }}

/* ── calendar popup ─────────────────────────────────── */
QFrame#CalendarPopup {{ background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 6px; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {BG_INPUT}; }}
QCalendarWidget QToolButton {{
    background: transparent; color: {ACCENT_GOLD}; border: none;
    font: {css_font(FONT_SUBHEAD)}; padding: 4px 8px;
}}
QCalendarWidget QToolButton:hover {{ background: {BG_HOVER}; border-radius: 4px; }}
QCalendarWidget QToolButton#qt_calendar_prevmonth {{ qproperty-icon: url("{left}"); }}
QCalendarWidget QToolButton#qt_calendar_nextmonth {{ qproperty-icon: url("{right}"); }}
QCalendarWidget QMenu {{ background: {BG_CARD}; color: {TEXT_PRIMARY}; }}
QCalendarWidget QSpinBox {{ min-height: 18px; padding: 0 4px; }}
QCalendarWidget QAbstractItemView {{
    background: {BG_DARK}; color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_GOLD}; selection-color: {BG_DARK};
    outline: 0; font: {css_font(FONT_LABEL)};
}}
QCalendarWidget QAbstractItemView:disabled {{ color: {TEXT_DIM}; }}

QMenu {{ background: {BG_CARD}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_COLOR}; }}
QMenu::item:selected {{ background: {BG_HOVER}; color: {ACCENT_GOLD}; }}
QMessageBox QLabel {{ color: {TEXT_PRIMARY}; }}
"""
