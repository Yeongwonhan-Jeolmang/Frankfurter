"""9. Watchlist — monitor several pairs, chart the selected one."""

from __future__ import annotations

import json
from datetime import date, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QMessageBox, QSplitter, QVBoxLayout, QWidget

from ui.chart_panel import ChartPanel
from ui.tabs.base import BaseTab
from ui.theme import *
from ui.widgets import (
    SectionHeader,
    Sidebar,
    SkeletonOverlay,
    WatchlistPanel,
    hbox,
    make_button,
    make_label,
)


class WatchlistTab(BaseTab):
    # Legacy location (current working directory) — read once for migration
    SAVE_FILE = "watchlist.json"
    DEFAULT_PAIRS = [("EUR", "USD"), ("GBP", "USD"), ("USD", "JPY"), ("EUR", "GBP")]

    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._pairs: list[tuple[str, str]] = []
        self._selected: tuple[str, str] | None = None
        self._load_saved()
        self._build()
        self._refresh()

    # ── persistence ───────────────────────────────────────────────────────
    def _load_saved(self):
        if self._settings:
            saved = self._settings.get("watchlist_pairs")
            # `is not None`: an intentionally emptied watchlist ([]) must stay
            # empty after a restart instead of resurrecting the defaults.
            if saved is not None:
                self._pairs = [tuple(p) for p in saved if len(p) == 2]
                return
        try:
            with open(self.SAVE_FILE) as f:
                self._pairs = [tuple(p) for p in json.load(f)]
        except Exception:
            self._pairs = list(self.DEFAULT_PAIRS)

    def _save_pairs(self):
        if self._settings:
            self._settings.set("watchlist_pairs", [list(p) for p in self._pairs])
            return
        try:
            with open(self.SAVE_FILE, "w") as f:
                json.dump(self._pairs, f)
        except Exception:
            pass

    # ── layout ────────────────────────────────────────────────────────────
    def _build(self):
        sb = Sidebar("Watchlist")
        sb.caption("Add Pair")
        self._add_base = QLineEdit()
        self._add_quote = QLineEdit()
        for e, ph in ((self._add_base, "EUR"), (self._add_quote, "USD")):
            e.setPlaceholderText(ph)
            e.setMaxLength(3)
            e.setProperty("mono", True)
            e.setFixedWidth(68)
        sb.add(hbox(self._add_base, make_label("/", FONT_HEADING, TEXT_MUTED), self._add_quote,
                    make_button("+", self._add_pair, width=38, tooltip="Add pair"), None, spacing=4))
        sb.separator()
        sb.add(make_button("⟳  Refresh All", lambda: self._refresh(force=True)))
        sb.add(make_button("🗑  Clear All", self._clear, "secondary"))
        sb.note("Pairs persist between sessions.\nClick a pair to chart it.\n"
                "★ pins it to the top, ✕ removes it.")

        main = self._split(sb)
        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(PAD_MD)

        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(SectionHeader("Watched Pairs  (click to chart • ★ to pin)"))
        self._wl = WatchlistPanel(
            settings=self._settings, on_select=self._plot_pair, on_remove=self._remove_pair
        )
        self._wl.setMinimumHeight(110)
        tl.addWidget(self._wl, 1)
        split.addWidget(top)

        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        self._chart_hdr = SectionHeader("1-Year Chart")
        bl.addWidget(self._chart_hdr)
        self._chart = ChartPanel()
        bl.addWidget(self._chart, 1)
        split.addWidget(bottom)
        split.setSizes([230, 520])
        main.addWidget(split, 1)
        self._skeleton = SkeletonOverlay(self._chart)

    # ── actions ───────────────────────────────────────────────────────────
    def _fetch(self):
        """Enter / F5: add the typed pair if any, else refresh."""
        if self._add_base.text().strip() or self._add_quote.text().strip():
            self._add_pair()
        else:
            self._refresh(force=True)

    def _add_pair(self):
        b = self._add_base.text().strip().upper()
        q = self._add_quote.text().strip().upper()
        if not self._check_codes(b, q):
            return
        if b == q:
            self._status("Base and quote must be different currencies", "error")
            return
        if (b, q) in self._pairs:
            self._status(f"{b}/{q} is already on the watchlist", "error")
            return
        self._pairs.append((b, q))
        self._save_pairs()
        self._add_base.clear()
        self._add_quote.clear()
        self._selected = (b, q)
        self._refresh()

    def _remove_pair(self, base, quote):
        try:
            self._pairs.remove((base, quote))
        except ValueError:
            return
        self._save_pairs()
        if self._selected == (base, quote):
            self._selected = None
        self._wl.remove(base, quote)
        self._status(f"Removed {base}/{quote}", "ok")
        if self._selected is None and self._pairs:
            self._wl.selected = self._pairs[0]
            self._plot_pair(*self._pairs[0])

    def _clear(self):
        if not self._pairs:
            return
        ans = QMessageBox.question(
            self,
            "Clear watchlist",
            f"Remove all {len(self._pairs)} pairs from the watchlist?",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._pairs.clear()
        self._selected = None
        self._save_pairs()
        self._wl.refresh([])
        self._status("Watchlist cleared", "ok")

    def _refresh(self, force=False):
        if not self._pairs:
            self._wl.refresh([])
            return
        pairs = list(self._pairs)  # snapshot for the worker thread

        def work():
            if force:
                self._client.invalidate_latest()
            return self._client.get_watchlist_snapshot(pairs)

        def done(snaps, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            if self._selected not in pairs:
                self._selected = pairs[0]
            self._wl.selected = self._selected
            self._wl.refresh(snaps)
            failed = sum(1 for s in snaps if s.get("error"))
            if failed:
                msg = f"Watchlist refreshed  •  {len(snaps) - failed} ok, {failed} failed"
            else:
                msg = f"Watchlist refreshed  •  {len(snaps)} pairs"
            self._plot_pair(*self._selected, msg=msg, ok=not failed)

        self._run(work, done, channel="snapshot")

    def _plot_pair(self, base, quote, msg=None, ok=True):
        self._selected = (base, quote)
        self._chart_hdr.set_text(f"1-Year Chart  —  {base}/{quote}")
        start = (date.today() - timedelta(days=365)).isoformat()

        def work():
            return self._client.get_time_series(start, None, base, [quote])

        def done(data, err):
            if err:
                self._status(f"Chart error for {base}/{quote}: {err}", "error")
                return
            self._chart.plot_series(data, base, quote)
            self._status(msg or f"{base}/{quote}  •  1-year chart", "ok" if ok else "error")

        self._run(work, done, skeleton=self._skeleton, channel="chart")
