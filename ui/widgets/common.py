"""
Small reusable building blocks: labels, cards, buttons, combo boxes,
segmented buttons, the sidebar container and the status bar.
(Originally brought to you by Florian van den Bersselaar; ported to PyQt6.)
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCompleter,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.theme import *

# ── tiny helpers ──────────────────────────────────────────────────────────────


def repolish(w: QWidget) -> None:
    """Re-apply the style sheet after a dynamic property changed."""
    st = w.style()
    st.unpolish(w)
    st.polish(w)
    w.update()


def set_error(w: QWidget, bad: bool = True) -> None:
    """Red border on an input (``QLineEdit[error="true"]`` in the QSS)."""
    if bool(w.property("error")) != bad:
        w.setProperty("error", bad)
        repolish(w)


def set_color(lbl: QLabel, color: str) -> None:
    lbl.setStyleSheet(f"color: {color};")


def make_label(
    text: str = "",
    font=FONT_BODY,
    color: str = TEXT_PRIMARY,
    wrap: bool = False,
    align: Qt.AlignmentFlag | None = None,
) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(qfont(font))
    set_color(lbl, color)
    if wrap:
        lbl.setWordWrap(True)
    if align is not None:
        lbl.setAlignment(align)
    return lbl


def make_button(
    text: str,
    command: Callable[[], object] | None = None,
    variant: str = "accent",
    width: int | None = None,
    height: int | None = None,
    tooltip: str = "",
) -> QPushButton:
    """
    variant: ``accent`` (gold), ``secondary`` (dark, bold), ``chip`` (small),
    ``outline`` (small with border), ``glyph`` (gold symbol, e.g. ⇄) or
    ``muted`` (small, grey text).
    """
    b = QPushButton(text.replace("&", "&&"))  # "&" is a mnemonic marker in Qt
    b.setProperty("variant", variant)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if width:
        b.setFixedWidth(width)
    if height:
        b.setFixedHeight(height)
    if tooltip:
        b.setToolTip(tooltip)
    if command is not None:
        b.clicked.connect(lambda _checked=False: command())
    return b


def hbox(*widgets, spacing: int = PAD_SM, margins=(0, 0, 0, 0)) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    for x in widgets:
        if x is None:
            lay.addStretch(1)
        elif isinstance(x, int):
            lay.addSpacing(x)
        else:
            lay.addWidget(x)
    return w


def fmt_rate(v) -> str:
    """Format a rate with precision that adapts to its magnitude, so both
    0.000012 (e.g. BTC-like tiny inverses) and 1 480.2 read sensibly."""
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    a = abs(v)
    if a == 0:
        return "0"
    if a >= 1000:
        return f"{v:,.2f}"
    if a >= 1:
        return f"{v:.5f}"
    if a >= 0.01:
        return f"{v:.6f}"
    return f"{v:.3e}" if a < 1e-6 else f"{v:.8f}"


# ── display widgets ───────────────────────────────────────────────────────────


class StatCard(QFrame):
    """A small card: muted upper-case caption over a big coloured value."""

    def __init__(self, label: str, value: str = "—", color: str | None = None):
        super().__init__()
        self.setObjectName("Card")
        self._color = color or ACCENT_GOLD
        lay = QVBoxLayout(self)
        lay.setContentsMargins(PAD_MD, PAD_MD, PAD_MD, PAD_MD)
        lay.setSpacing(2)
        self._lbl = make_label(label.upper(), FONT_LABEL, TEXT_MUTED)
        self._val = make_label(value, FONT_MONO_LG, self._color)
        # Long values are clipped instead of forcing the whole window wider;
        # the full text is always available as a tooltip.
        for w in (self._lbl, self._val):
            w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            w.setMinimumWidth(0)
        lay.addWidget(self._lbl)
        lay.addWidget(self._val)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._base_font = qfont(FONT_MONO_LG)
        self._cap_font = qfont(FONT_LABEL)
        self._val.setFixedHeight(QFontMetrics(self._base_font).height() + 2)

    def set_value(self, value: str, color: str | None = None) -> None:
        self._val.setText(value)
        self._val.setToolTip(value)
        set_color(self._val, color or self._color)
        self._fit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def _fit(self) -> None:
        """Shrink the value (down to 9 pt) and caption (down to 7 pt) fonts until
        they fit the card, so narrow cards — e.g. the 7-across Statistics grid —
        stay readable instead of being clipped."""
        for lbl, base, floor in (
            (self._val, self._base_font, 9),
            (self._lbl, self._cap_font, 7),
        ):
            avail = lbl.width() - 2
            if avail <= 0:
                continue
            f = QFont(base)
            size = f.pointSizeF()
            while (
                size > floor and QFontMetrics(f).horizontalAdvance(lbl.text()) > avail
            ):
                size -= 0.5
                f.setPointSizeF(size)
            if f != lbl.font():
                lbl.setFont(f)

    def set_label(self, label: str) -> None:
        self._lbl.setText(label.upper())
        self._fit()

    def value(self) -> str:
        return self._val.text()


class SectionHeader(QWidget):
    def __init__(self, text: str):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        bar = QFrame()
        bar.setObjectName("SectionBar")
        bar.setFixedSize(4, 20)
        lay.addWidget(bar)
        self._lbl = make_label(text, FONT_HEADING)
        lay.addWidget(self._lbl)
        lay.addStretch(1)

    def set_text(self, text: str) -> None:
        self._lbl.setText(text)

    def text(self) -> str:
        return self._lbl.text()


class HSeparator(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Separator")
        self.setFixedHeight(1)


class StatusBar(QFrame):
    _COLORS = {"ok": ACCENT_GREEN, "loading": ACCENT_GOLD, "error": ACCENT_RED}

    def __init__(self):
        super().__init__()
        self.setObjectName("StatusBar")
        self.setFixedHeight(28)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(PAD_MD, 0, PAD_MD, 0)
        lay.setSpacing(PAD_SM)
        self._dot = make_label("●", (FONT_BODY[0], 10), ACCENT_GREEN)
        self._msg = make_label("Ready", FONT_SMALL, TEXT_MUTED)
        self._msg.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self._time = make_label("", FONT_SMALL, TEXT_DIM)
        lay.addWidget(self._dot)
        lay.addWidget(self._msg, 1)
        lay.addWidget(self._time)
        lay.addWidget(
            make_label("api.frankfurter.dev  •  ECB Data", FONT_SMALL, TEXT_DIM)
        )

    def set_status(self, msg: str, state: str = "ok") -> None:
        set_color(self._dot, self._COLORS.get(state, ACCENT_GOLD))
        self._msg.setText(msg)
        self._msg.setToolTip(msg)
        set_color(self._msg, ACCENT_RED if state == "error" else TEXT_MUTED)
        if state != "loading":
            self._time.setText(f"Last update {datetime.now():%H:%M:%S}  •")

    def message(self) -> str:
        return self._msg.text()


# ── inputs ────────────────────────────────────────────────────────────────────


class Field(QWidget):
    """A small muted caption stacked on top of an input widget."""

    def __init__(self, label: str, widget: QWidget):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, PAD_SM)
        lay.setSpacing(3)
        if label:
            lay.addWidget(make_label(label, FONT_LABEL, TEXT_MUTED))
        lay.addWidget(widget)
        self.widget = widget


class CodeCombo(QComboBox):
    """
    Currency combo box that lists every known code but still accepts typing,
    so archived codes like DEM can be entered. ``command(text)`` fires when
    the user picks an entry from the drop-down list.
    """

    def __init__(self, values: Iterable[str], default: str = "", command=None):
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(16)
        self.setProperty("mono", True)
        self.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.setMinimumContentsLength(5)
        self.addItems(list(values))
        comp = QCompleter(list(values), self)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(comp)
        self.lineEdit().setMaxLength(12)
        if default:
            self.set(default)
        if command is not None:
            self.textActivated.connect(command)

    def get(self) -> str:
        return self.currentText()

    def set(self, v: str) -> None:
        i = self.findText(v)
        if i >= 0:
            self.setCurrentIndex(i)
        else:
            self.setEditText(v)

    def set_values(self, values: Iterable[str]) -> None:
        cur = self.get()
        self.blockSignals(True)
        self.clear()
        self.addItems(list(values))
        self.set(cur)
        self.blockSignals(False)


class SearchEntry(QWidget):
    """
    Search/filter text field with clear button. Debounces keystrokes by
    120 ms so rapid typing doesn't hammer the ``on_change`` callback.
    """

    _DEBOUNCE_MS = 120

    def __init__(self, placeholder: str = "Search…", on_change=None):
        super().__init__()
        self._cb = on_change
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText(placeholder)
        lay.addWidget(self.entry, 1)
        clear = make_button("✕", self.clear, "muted", width=32, tooltip="Clear")
        lay.addWidget(clear)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._DEBOUNCE_MS)
        self._timer.timeout.connect(self._fire)
        self.entry.textChanged.connect(lambda _t: self._timer.start())

    def _fire(self) -> None:
        if self._cb:
            self._cb(self.entry.text())

    def clear(self) -> None:
        self.entry.clear()

    def get(self) -> str:
        return self.entry.text()


class SegmentedButton(QWidget):
    """Row of mutually-exclusive toggle buttons (like CTkSegmentedButton)."""

    changed = pyqtSignal(str)

    def __init__(self, values: list[str], default: str | None = None, command=None):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        n = len(values)
        for i, v in enumerate(values):
            b = QPushButton(v)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            pos = (
                "only"
                if n == 1
                else "first" if i == 0 else "last" if i == n - 1 else "mid"
            )
            b.setProperty("segment", pos)
            self._group.addButton(b)
            lay.addWidget(b)
            self._buttons[v] = b
        self.set(default if default is not None else values[0])
        self._group.buttonClicked.connect(lambda b: self.changed.emit(b.text()))
        if command is not None:
            self.changed.connect(command)

    def get(self) -> str:
        b = self._group.checkedButton()
        return b.text() if b else ""

    def set(self, v: str) -> None:
        b = self._buttons.get(v)
        if b is not None:
            b.setChecked(True)

    def button(self, v: str) -> QPushButton:
        return self._buttons[v]


class ChipGrid(QWidget):
    """
    Small 'chip' buttons in a wrapping grid. *items* is a list of
    (label, command). A grid keeps everything inside the fixed-width sidebar.
    """

    def __init__(self, items, cols: int = 4):
        super().__init__()
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setSpacing(2)
        self.buttons: list[QPushButton] = []
        for i, (lbl, cmd) in enumerate(items):
            b = make_button(lbl, cmd, "chip")
            grid.addWidget(b, i // cols, i % cols)
            self.buttons.append(b)
        for c in range(cols):
            grid.setColumnStretch(c, 1)


# ── layout containers ─────────────────────────────────────────────────────────


class Sidebar(QScrollArea):
    """
    Fixed-width, scrollable left column so every control stays reachable on
    small windows. Widgets are added with :meth:`add` and stack from the top.
    """

    def __init__(self, title: str, width: int = SIDEBAR_WIDTH):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(width)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("SidebarBody")
        self._lay = QVBoxLayout(body)
        self._lay.setContentsMargins(PAD_MD, PAD_LG, PAD_MD, PAD_MD)
        self._lay.setSpacing(3)
        self._lay.addStretch(1)
        self.setWidget(body)
        self.add(make_label(title, FONT_HEADING, ACCENT_GOLD, wrap=True), after=PAD_SM)

    def add(self, w: QWidget, before: int = 0, after: int = 0) -> QWidget:
        idx = self._lay.count() - 1  # keep the trailing stretch last
        if before:
            self._lay.insertSpacing(idx, before)
            idx += 1
        self._lay.insertWidget(idx, w)
        if after:
            self._lay.insertSpacing(idx + 1, after)
        return w

    def separator(self) -> None:
        self.add(HSeparator(), before=PAD_SM, after=PAD_SM)

    def caption(self, text: str, color: str = TEXT_MUTED) -> QLabel:
        return self.add(make_label(text, FONT_LABEL, color))

    def note(self, text: str) -> QLabel:
        return self.add(
            make_label(text, FONT_SMALL, TEXT_MUTED, wrap=True), before=PAD_SM
        )

    def sizeHint(self) -> QSize:
        return QSize(self.width(), 400)
