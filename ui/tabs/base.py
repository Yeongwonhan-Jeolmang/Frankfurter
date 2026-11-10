"""
BaseTab and the helpers every tab shares: async requests with stale-reply
protection, validation, and CSV / JSON export.
"""

from __future__ import annotations

from datetime import date, timedelta

from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from exports.exporter import default_filename, export_to_csv, export_to_json
from ui.theme import *
from ui.widgets import ChipGrid, MIN_DATE
from utils.workers import AsyncWorker

__all__ = [
    "BaseTab",
    "MIN_DATE",
    "code_of",
    "parse_date",
    "validate_range",
    "quick_range_chips",
    "saved_or",
    "scrollable",
]


def code_of(widget, fallback: str) -> str:
    """Read a currency code from an entry/combo ("EUR – Euro" → "EUR")."""
    return widget.get().split(" –")[0].strip().upper() or fallback


def parse_date(text):
    """Return a date for a YYYY-MM-DD string, or None if invalid."""
    try:
        return date.fromisoformat(text.strip())
    except (ValueError, AttributeError):
        return None


def validate_range(start_w, end_w):
    """
    Validate a start/end pair of DateEntry widgets. Returns
    (start_iso, end_iso, None) on success or (None, None, error_message).
    Offending fields are highlighted red.
    """
    s, e = parse_date(start_w.get()), parse_date(end_w.get())
    start_w.flag_error(s is None)
    end_w.flag_error(e is None)
    if s is None or e is None:
        return None, None, "Dates must be in YYYY-MM-DD format"
    today = date.today()
    if s > today:
        start_w.flag_error(True)
        return None, None, "Start date is in the future"
    if s < MIN_DATE:
        start_w.flag_error(True)
        return None, None, f"No data before {MIN_DATE.isoformat()}"
    if s > e:
        start_w.flag_error(True)
        end_w.flag_error(True)
        return None, None, "Start date must be before end date"
    return s.isoformat(), min(e, today).isoformat(), None


def quick_range_chips(start_entry, end_entry, fetch_fn, presets=None) -> ChipGrid:
    """Quick-range chips (1M 3M 6M YTD 1Y …) that fill start / end and fetch."""

    def _apply(days, ytd=False):
        end = date.today()
        start = date(end.year, 1, 1) if ytd else (end - timedelta(days=days))
        start_entry.set(start.isoformat())
        end_entry.set(end.isoformat())
        fetch_fn()

    presets = presets or [
        ("1M", 30, False),
        ("3M", 90, False),
        ("6M", 180, False),
        ("YTD", 0, True),
        ("1Y", 365, False),
        ("2Y", 730, False),
        ("5Y", 1826, False),
        ("10Y", 3652, False),
    ]
    return ChipGrid([(lbl, lambda d=days, y=ytd: _apply(d, y)) for lbl, days, ytd in presets])


def scrollable(content: QWidget, min_w: int = 560, min_h: int = 520) -> QScrollArea:
    """
    Wrap a tab's main column so it scrolls on small windows instead of
    squashing its widgets (Qt shrinks children to fit; Tk simply clipped).
    Above the minimum size it just stretches to fill the space.
    """
    content.setMinimumSize(min_w, min_h)
    sa = QScrollArea()
    sa.setWidget(content)
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    return sa


def saved_or(settings, key, default):
    return settings.get(key, default) if settings else default


class BaseTab(QWidget):
    """
    Every tab gets the shared client, the currency-name map, a status
    callback and the Settings store. Most tabs are a fixed-width sidebar on
    the left and a main area on the right: use :meth:`_split` to get both.
    """

    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(parent)
        self._client = client
        self._names = currency_names
        self._status = status_cb
        self._codes = sorted(currency_names.keys())
        self._settings = settings
        # Monotonic request counters per channel: a response is only applied
        # if no newer request on the same channel was started meanwhile, so a
        # slow old reply can never overwrite fresher data on screen.
        self._req_seq: dict[str, int] = {}

    # ── layout ────────────────────────────────────────────────────────────
    def _split(self, sidebar: QWidget, margins: int = PAD_LG) -> QVBoxLayout:
        """Sidebar on the left, returns the main column's layout."""
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(sidebar)
        main = QWidget()
        lay = QVBoxLayout(main)
        lay.setContentsMargins(margins, margins, margins, margins)
        lay.setSpacing(PAD_SM)
        row.addWidget(scrollable(main), 1)
        return lay

    # ── async ─────────────────────────────────────────────────────────────
    def _run(self, fn, cb, skeleton=None, channel: str = "main") -> None:
        self._status("Fetching…", "loading")
        seq = self._req_seq.get(channel, 0) + 1
        self._req_seq[channel] = seq
        if skeleton is not None:
            skeleton.start()

        def wrapped(result, err):
            if sip.isdeleted(self):
                return  # tab (or window) was closed meanwhile
            if self._req_seq.get(channel) != seq:
                return  # superseded by a newer request
            if skeleton is not None and not sip.isdeleted(skeleton):
                skeleton.stop()
            cb(result, err)

        AsyncWorker(fn, wrapped).start()

    def _check_codes(self, *codes) -> bool:
        """Validate the *shape* of currency codes. Archived codes (DEM, FRF…)
        are not in the active list but are still valid, so the API has the
        final say."""
        for c in codes:
            if not c or len(c) != 3 or not c.isalpha():
                self._status(f"Invalid currency code: {c or '(empty)'}", "error")
                return False
        return True

    # ── export ────────────────────────────────────────────────────────────
    def _ask_save_path(self, prefix: str, ext: str) -> str | None:
        label = ext.upper()
        p, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {label}",
            default_filename(prefix, ext),
            f"{label} (*.{ext})",
        )
        if not p:
            return None
        if not p.lower().endswith(f".{ext}"):
            p += f".{ext}"
        return p

    def _write_export(self, writer, payload, prefix: str, ext: str) -> None:
        p = self._ask_save_path(prefix, ext)
        if not p:
            return
        try:
            writer(payload, p)
            self._status(f"Exported → {p}", "ok")
        except OSError as e:
            self._status(f"Export failed: {e}", "error")

    def _export_csv_data(self, data, prefix="rates"):
        if not data:
            self._status("Nothing to export yet — fetch some data first", "error")
            return
        self._write_export(export_to_csv, data, prefix, "csv")

    def _export_json_data(self, data, prefix="rates"):
        if not data:
            self._status("Nothing to export yet — fetch some data first", "error")
            return
        self._write_export(export_to_json, data, prefix, "json")

    # Enter / F5 from the main window
    def _fetch(self):  # pragma: no cover - overridden
        pass
