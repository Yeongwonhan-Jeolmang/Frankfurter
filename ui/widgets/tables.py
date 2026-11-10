"""
Model/view tables: the sortable rate table (Dashboard, Historical) and the
watchlist panel.

The Tk version had to hand-roll a label pool to stay fast. Qt's model/view
classes only paint the visible rows, so a full refresh is a single model
reset regardless of how many currencies there are.
"""

from __future__ import annotations

from PyQt6.QtCore import QAbstractTableModel, QEvent, QModelIndex, Qt
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from ui.theme import *
from ui.widgets.common import fmt_rate, make_label

_ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
_ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter


class _InteractiveTable(QTableView):
    """
    QTableView with: an empty-state message, hover tracking (so a model can
    highlight e.g. the ✕ under the mouse), and a hand cursor over the
    "clickable" columns listed in ``CLICK_COLS``.
    """

    CLICK_COLS: set[int] = set()

    def __init__(self, empty_text: str):
        super().__init__()
        self.setMouseTracking(True)
        self.viewport().installEventFilter(self)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(28)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._empty = make_label(empty_text, FONT_BODY, TEXT_DIM, align=_ALIGN_CENTER)
        self._empty.setParent(self.viewport())
        self._empty.hide()

    def set_empty_visible(self, show: bool, text: str | None = None) -> None:
        if text is not None:
            self._empty.setText(text)
        self._empty.setVisible(show)
        self._place_empty()

    def _place_empty(self) -> None:
        vp = self.viewport().rect()
        self._empty.setGeometry(0, PAD_LG, vp.width(), 40)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_empty()

    def eventFilter(self, obj, ev):
        if obj is self.viewport():
            if ev.type() == QEvent.Type.MouseMove:
                idx = self.indexAt(ev.position().toPoint())
                self._set_hover(idx.row() if idx.isValid() else -1, idx.column() if idx.isValid() else -1)
            elif ev.type() == QEvent.Type.Leave:
                self._set_hover(-1, -1)
        return super().eventFilter(obj, ev)

    def _set_hover(self, row: int, col: int) -> None:
        if col in self.CLICK_COLS:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().unsetCursor()
        m = self.model()
        if hasattr(m, "set_hover"):
            m.set_hover(row, col)


# ══════════════════════════════════════════════════════════════════════════════
# Rate table
# ══════════════════════════════════════════════════════════════════════════════


class RateModel(QAbstractTableModel):
    HEADERS = ("★", "Currency", "Code", "Rate", "Inverse", "Change")
    # column index -> sort key
    SORT_KEYS = {1: "name", 2: "code", 3: "rate", 5: "change"}

    def __init__(self, settings=None):
        super().__init__()
        self._settings = settings
        self._prev: dict[str, float] = {}
        self._prev_base: str | None = None
        self._changes: dict[str, float | None] = {}
        self._filter = ""
        self._rates: dict[str, float] = {}
        self._names: dict[str, str] = {}
        self.base = "EUR"
        self.sort_key = "code"
        self.sort_desc = False
        self._rows: list[str] = []
        self._pinned: set[str] = set()
        self._fonts = {
            "star": qfont((FONT_BODY[0], 12)),
            "body": qfont(FONT_BODY),
            "mono": qfont(FONT_MONO),
            "code": qfont((FONT_MONO[0], 11, "bold")),
        }

    # ── data in ───────────────────────────────────────────────────────────
    def populate(self, rates, names, base, filter_text: str = "") -> None:
        # Change % is only meaningful against the previous snapshot of the
        # *same* base currency; computing it here (not when rendering) means
        # filtering / sorting / pinning never wipes the indicators.
        if self._prev_base == base and self._prev:
            self._changes = {
                c: ((r - self._prev[c]) / self._prev[c] * 100) if self._prev.get(c) else None
                for c, r in rates.items()
            }
        else:
            self._changes = {c: None for c in rates}
        self._prev = dict(rates)
        self._prev_base = base
        self._rates = dict(rates)
        self._names = names
        self.base = base
        if filter_text:
            self._filter = filter_text.upper()
        self.rebuild()

    def set_filter(self, text: str) -> None:
        self._filter = text.upper()
        self.rebuild()

    def sort_by(self, key: str) -> None:
        if key == self.sort_key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_key = key
            self.sort_desc = key in ("rate", "change")
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(self.HEADERS) - 1)
        self.rebuild()

    def rebuild(self) -> None:
        self.beginResetModel()
        self._pinned = set()
        if self._settings:
            self._pinned = {q for b, q in self._settings.get_favourites() if b == self.base}
        codes = list(self._rates)
        if self._filter:
            f = self._filter
            codes = [c for c in codes if f in c or f in self._names.get(c, "").upper()]
        k = self.sort_key
        if k == "name":
            keyf = lambda c: self._names.get(c, c).upper()
        elif k == "rate":
            keyf = lambda c: self._rates[c]
        elif k == "change":
            # Unknown changes always sink to the bottom regardless of direction
            def keyf(c):
                ch = self._changes.get(c)
                return (ch is not None, ch if ch is not None else 0.0)
        else:
            keyf = lambda c: c
        codes.sort(key=keyf, reverse=self.sort_desc)
        codes.sort(key=lambda c: c not in self._pinned)  # stable: pins on top
        self._rows = codes
        self.endResetModel()

    # ── accessors ─────────────────────────────────────────────────────────
    def code_at(self, row: int) -> str | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def rate_of(self, code: str):
        return self._rates.get(code)

    def has_data(self) -> bool:
        return bool(self._rates)

    # ── Qt model API ──────────────────────────────────────────────────────
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            h = self.HEADERS[section]
            if self.SORT_KEYS.get(section) == self.sort_key:
                return f"{h} {'▼' if self.sort_desc else '▲'}"
            return h
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return _ALIGN_CENTER if section == 0 else _ALIGN_LEFT
        if role == Qt.ItemDataRole.ToolTipRole and section in self.SORT_KEYS:
            return "Click to sort"
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        code = self._rows[index.row()]
        col = index.column()
        pinned = code in self._pinned
        R = Qt.ItemDataRole
        if role == R.DisplayRole:
            if col == 0:
                return "★" if pinned else "☆"
            if col == 1:
                return self._names.get(code, code)
            if col == 2:
                return code
            rate = self._rates[code]
            if col == 3:
                return fmt_rate(rate)
            if col == 4:
                return fmt_rate(1 / rate if rate else 0.0)
            pct = self._changes.get(code)
            if pct is None:
                return "—"
            if pct > 0:
                return f"▲ {pct:.4f}%"
            if pct < 0:
                return f"▼ {abs(pct):.4f}%"
            return "→ 0.0000%"
        if role == R.ForegroundRole:
            if col == 0:
                return QColor(ACCENT_GOLD if pinned else TEXT_DIM)
            if col == 2:
                return QColor(ACCENT_GOLD)
            if col == 4:
                return QColor(TEXT_MUTED)
            if col == 5:
                pct = self._changes.get(code)
                if pct is None or pct == 0:
                    return QColor(TEXT_MUTED)
                return QColor(ACCENT_GREEN if pct > 0 else ACCENT_RED)
            return QColor(TEXT_PRIMARY)
        if role == R.FontRole:
            if col == 0:
                return self._fonts["star"]
            if col == 2:
                return self._fonts["code"]
            return self._fonts["mono"] if col >= 3 else self._fonts["body"]
        if role == R.TextAlignmentRole:
            return _ALIGN_CENTER if col == 0 else _ALIGN_LEFT
        if role == R.ToolTipRole and col == 0:
            return f"{'Unpin' if pinned else 'Pin'} {self.base}/{code}"
        return None


class RateTable(_InteractiveTable):
    """
    Sortable table of exchange rates with a clickable ★ pin column.
    Pinned (starred) pairs always float to the top. Click a column header to
    sort by it (click again to reverse); double-click a row to copy its rate.
    """

    CLICK_COLS = {0}

    def __init__(self, settings=None, on_copy=None, on_pin=None):
        super().__init__("No currencies match the filter")
        self._settings = settings
        self._on_copy = on_copy
        self._on_pin = on_pin
        self._model = RateModel(settings)
        self.setModel(self._model)
        hh = self.horizontalHeader()
        hh.setSectionsClickable(True)
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 40)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.sectionClicked.connect(self._on_header)
        hh.setMinimumSectionSize(40)
        self.clicked.connect(self._on_click)
        self.doubleClicked.connect(self._on_double)
        self._model.modelReset.connect(self._update_empty)

    @property
    def model_(self) -> RateModel:
        return self._model

    # public API (unchanged from the Tk version)
    def populate(self, rates, currency_names, base, filter_text: str = "") -> None:
        self._model.populate(rates, currency_names, base, filter_text)

    def set_filter(self, text: str) -> None:
        self._model.set_filter(text)

    def sort_by(self, key: str) -> None:
        self._model.sort_by(key)

    def _update_empty(self) -> None:
        self.set_empty_visible(self._model.rowCount() == 0 and self._model.has_data())

    def _on_header(self, section: int) -> None:
        key = RateModel.SORT_KEYS.get(section)
        if key:
            self._model.sort_by(key)

    def _on_click(self, idx) -> None:
        if idx.column() != 0 or not self._settings:
            return
        code = self._model.code_at(idx.row())
        if code:
            self._settings.toggle_favourite(self._model.base, code)
            self._model.rebuild()
            if self._on_pin:
                self._on_pin()

    def _on_double(self, idx) -> None:
        if idx.column() == 0:
            return
        code = self._model.code_at(idx.row())
        if not code:
            return
        text = f"1 {self._model.base} = {fmt_rate(self._model.rate_of(code))} {code}"
        QGuiApplication.clipboard().setText(text)
        if self._on_copy:
            self._on_copy(text)


# ══════════════════════════════════════════════════════════════════════════════
# Watchlist
# ══════════════════════════════════════════════════════════════════════════════


class WatchlistModel(QAbstractTableModel):
    HEADERS = ("★", "Pair", "Rate", "Date", "")

    def __init__(self, settings=None):
        super().__init__()
        self._settings = settings
        self.snaps: list[dict] = []
        self.selected: tuple[str, str] | None = None
        self._hover = (-1, -1)
        self._fonts = {
            "star": qfont((FONT_BODY[0], 13)),
            "pair": qfont(FONT_SUBHEAD),
            "mono": qfont(FONT_MONO),
            "small": qfont(FONT_SMALL),
        }

    def set_snapshots(self, snaps: list[dict]) -> None:
        self.beginResetModel()
        if self._settings:
            favs = {(str(b), str(q)) for b, q in self._settings.get_favourites()}

            def sort_key(s):
                b, q = str(s.get("base", "?")), str(s.get("quote", "?"))
                return (0 if (b, q) in favs else 1, b, q)

            snaps = sorted(snaps, key=sort_key)
        self.snaps = list(snaps)
        self.endResetModel()

    def pair_at(self, row: int) -> tuple[str, str] | None:
        if 0 <= row < len(self.snaps):
            s = self.snaps[row]
            return str(s.get("base", "?")), str(s.get("quote", "?"))
        return None

    def set_hover(self, row: int, col: int) -> None:
        old = self._hover
        self._hover = (row, col)
        for r in {old[0], row}:
            if 0 <= r < len(self.snaps):
                self.dataChanged.emit(self.index(r, 4), self.index(r, 4))

    def refresh_view(self) -> None:
        if self.snaps:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.snaps) - 1, 4))

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.snaps)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return _ALIGN_CENTER if section in (0, 4) else _ALIGN_LEFT
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        s = self.snaps[index.row()]
        base, quote = str(s.get("base", "?")), str(s.get("quote", "?"))
        rate, err = s.get("rate"), s.get("error")
        col = index.column()
        fav = bool(self._settings and self._settings.is_favourite(base, quote))
        sel = self.selected == (base, quote)
        R = Qt.ItemDataRole
        if role == R.DisplayRole:
            return (
                "★" if fav else "☆",
                f"▸ {base}/{quote}" if sel else f"   {base}/{quote}",
                fmt_rate(rate) if rate else "N/A",
                "error" if err else str(s.get("date") or ""),
                "✕",
            )[col]
        if role == R.ForegroundRole:
            if col == 0:
                return QColor(ACCENT_GOLD if fav else TEXT_DIM)
            if col == 1:
                return QColor(ACCENT_GOLD)
            if col == 2:
                return QColor(TEXT_PRIMARY if rate else ACCENT_RED)
            if col == 3:
                return QColor(ACCENT_RED if err else TEXT_DIM)
            hovered = self._hover == (index.row(), 4)
            return QColor(ACCENT_RED if hovered else TEXT_DIM)
        if role == R.BackgroundRole and sel:
            return QColor(212, 175, 55, 46)  # translucent gold
        if role == R.FontRole:
            return (
                self._fonts["star"],
                self._fonts["pair"],
                self._fonts["mono"],
                self._fonts["small"],
                self._fonts["small"],
            )[col]
        if role == R.TextAlignmentRole:
            return _ALIGN_CENTER if col in (0, 4) else _ALIGN_LEFT
        if role == R.ToolTipRole:
            if col == 0:
                return "Unpin" if fav else "Pin to top"
            if col == 4:
                return f"Remove {base}/{quote}"
            if err:
                return str(err)
            return f"Chart {base}/{quote}"
        return None


class WatchlistPanel(_InteractiveTable):
    """
    Compact live watchlist — starred pairs sorted to the top.
    Click a pair to select it (fires ``on_select(base, quote)``), ★ to pin
    it, ✕ to remove it (fires ``on_remove(base, quote)``).
    """

    CLICK_COLS = {0, 1, 2, 3, 4}

    def __init__(self, settings=None, on_select=None, on_remove=None):
        super().__init__("Your watchlist is empty — add a pair on the left.")
        self._settings = settings
        self._on_select = on_select
        self._on_remove = on_remove
        self._model = WatchlistModel(settings)
        self.setModel(self._model)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for c, w in ((0, 40), (4, 40)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.setColumnWidth(c, w)
        hh.setHighlightSections(False)
        self.verticalHeader().setDefaultSectionSize(32)
        self.clicked.connect(self._on_click)
        self.set_empty_visible(True)

    # ── public API ────────────────────────────────────────────────────────
    @property
    def selected(self) -> tuple[str, str] | None:
        return self._model.selected

    @selected.setter
    def selected(self, pair) -> None:
        self._model.selected = tuple(pair) if pair else None
        self._model.refresh_view()

    @property
    def last_snapshots(self) -> list[dict]:
        return list(self._model.snaps)

    def set_selected(self, base: str, quote: str) -> None:
        self.selected = (base, quote)

    def refresh(self, snapshots: list[dict]) -> None:
        self._model.set_snapshots(snapshots)
        self.set_empty_visible(not snapshots)

    def remove(self, base: str, quote: str) -> None:
        self.refresh([s for s in self._model.snaps if (s.get("base"), s.get("quote")) != (base, quote)])

    def _on_click(self, idx) -> None:
        pair = self._model.pair_at(idx.row())
        if pair is None:
            return
        col = idx.column()
        if col == 0:
            if self._settings:
                self._settings.toggle_favourite(*pair)
                self._model.set_snapshots(self._model.snaps)  # re-sort
        elif col == 4:
            if self._on_remove:
                self._on_remove(*pair)
        else:
            self.selected = pair
            if self._on_select:
                self._on_select(*pair)
