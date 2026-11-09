"""
Reusable custom widgets brought to you by Florian van den Bersselaar
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from ui.theme import *


class StatCard(ctk.CTkFrame):
    def __init__(self, master, label: str, value: str = "—", color=None, **kw):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=CORNER_RADIUS,
            border_width=1,
            border_color=BORDER_COLOR,
            **kw,
        )
        self._color = color or ACCENT_GOLD
        self._lbl = ctk.CTkLabel(
            self, text=label.upper(), font=FONT_LABEL, text_color=TEXT_MUTED
        )
        self._lbl.pack(anchor="w", padx=PAD_MD, pady=(PAD_MD, 2))
        self._val = ctk.CTkLabel(
            self, text=value, font=FONT_MONO_LG, text_color=self._color
        )
        self._val.pack(anchor="w", padx=PAD_MD, pady=(0, PAD_MD))

    def set_value(self, value: str, color=None) -> None:
        self._val.configure(text=value, text_color=color or self._color)

    def set_label(self, label: str) -> None:
        self._lbl.configure(text=label.upper())


class SectionHeader(ctk.CTkFrame):
    def __init__(self, master, text: str, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        ctk.CTkFrame(
            self, width=4, height=20, fg_color=ACCENT_GOLD, corner_radius=2
        ).pack(side="left", padx=(0, 8))
        self._lbl = ctk.CTkLabel(
            self, text=text, font=FONT_HEADING, text_color=TEXT_PRIMARY
        )
        self._lbl.pack(side="left")

    def set_text(self, text: str) -> None:
        self._lbl.configure(text=text)


class HSeparator(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, height=1, fg_color=BORDER_COLOR, **kw)


class LabelledCombo(ctk.CTkFrame):
    def __init__(
        self, master, label: str, values, width: int = 160, command=None, **kw
    ):
        super().__init__(master, fg_color="transparent", **kw)
        if label:
            ctk.CTkLabel(self, text=label, font=FONT_LABEL, text_color=TEXT_MUTED).pack(
                anchor="w"
            )
        self.combo = ctk.CTkComboBox(
            self,
            values=values,
            width=width,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            button_color=ACCENT_GOLD,
            dropdown_fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            font=FONT_BODY,
            command=command,
        )
        self.combo.pack(fill="x")

    def get(self) -> str:
        return self.combo.get()

    def set(self, v: str) -> None:
        self.combo.set(v)

    def configure_values(self, values) -> None:
        self.combo.configure(values=values)


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, height=28, fg_color=BG_CARD, corner_radius=0, **kw)
        self._dot = ctk.CTkLabel(
            self,
            text="●",
            font=("Helvetica Neue", 10),
            text_color=ACCENT_GREEN,
            width=20,
        )
        self._dot.pack(side="left", padx=(PAD_MD, 4))
        self._msg = ctk.CTkLabel(
            self, text="Ready", font=FONT_SMALL, text_color=TEXT_MUTED
        )
        self._msg.pack(side="left")
        ctk.CTkLabel(
            self,
            text="api.frankfurter.dev  •  ECB Data",
            font=FONT_SMALL,
            text_color=TEXT_DIM,
        ).pack(side="right", padx=PAD_MD)
        self._time = ctk.CTkLabel(self, text="", font=FONT_SMALL, text_color=TEXT_DIM)
        self._time.pack(side="right", padx=PAD_SM)

    def set_status(self, msg: str, state: str = "ok") -> None:
        from datetime import datetime as _dt

        c = {"ok": ACCENT_GREEN, "loading": ACCENT_GOLD, "error": ACCENT_RED}
        self._dot.configure(text_color=c.get(state, ACCENT_GOLD))
        self._msg.configure(
            text=msg, text_color=ACCENT_RED if state == "error" else TEXT_MUTED
        )
        if state != "loading":
            self._time.configure(text=f"Last update {_dt.now():%H:%M:%S}  •")


class RateTable(ctk.CTkScrollableFrame):
    """
    Scrollable, sortable table of exchange rates with a clickable ★ pin column.

    Performance:
      * Cells are lightweight ``tk.Label`` widgets (a CTkLabel is a canvas +
        label pair and is ~10x more expensive to create). This alone removes
        the multi-second freeze the old 1 320 pre-allocated CTkLabels caused
        on startup.
      * Rows are allocated lazily — only as many as the data needs — and are
        reconfigured in place on every filter / sort / refresh.
      * Event bindings are attached once per row; each handler looks up the
        row's *current* currency code, so re-rendering never stacks duplicate
        callbacks (the old per-render ``bind`` on CTkLabel kept *adding*
        handlers, so a ★ click could toggle the pin several times).

    Pinned (starred) pairs always float to the top. Click a column header to
    sort by it (click again to reverse); double-click a row to copy its rate.
    """

    HEADERS = ("★", "Currency", "Code", "Rate", "Inverse", "Change")
    # header label -> sort key understood by _sorted_items()
    SORTABLE = {"Currency": "name", "Code": "code", "Rate": "rate", "Change": "change"}
    _STAR_FONT = ("Helvetica Neue", 12)

    def __init__(self, master, settings=None, on_copy=None, on_pin=None, **kw):
        super().__init__(master, fg_color=BG_DARK, **kw)
        self._settings = settings
        self._on_copy = on_copy
        self._on_pin = on_pin
        self._prev: dict[str, float] = {}
        self._prev_base: str | None = None
        self._changes: dict[str, float | None] = {}
        self._filter: str = ""
        self._raw_rates: dict[str, float] = {}
        self._raw_names: dict[str, str] = {}
        self._raw_base: str = "EUR"
        self._sort_key: str = "code"
        self._sort_desc: bool = False
        self._pool: list[list[tk.Label]] = []
        self._row_codes: list[str | None] = []
        self._header_lbls: dict[str, ctk.CTkLabel] = {}
        self._empty_lbl: ctk.CTkLabel | None = None
        self._build_header()

    def _build_header(self) -> None:
        for c, h in enumerate(self.HEADERS):
            lbl = ctk.CTkLabel(
                self,
                text=h,
                font=FONT_SUBHEAD,
                text_color=ACCENT_GOLD,
                anchor="center" if c == 0 else "w",
                cursor="hand2" if h in self.SORTABLE else "arrow",
            )
            lbl.grid(row=0, column=c, sticky="ew", padx=(PAD_SM, PAD_MD), pady=4)
            if h in self.SORTABLE:
                lbl.bind("<Button-1>", lambda e, k=self.SORTABLE[h]: self.sort_by(k))
            self._header_lbls[h] = lbl
        ctk.CTkFrame(self, height=1, fg_color=BORDER_COLOR).grid(
            row=1, column=0, columnspan=len(self.HEADERS), sticky="ew", pady=2
        )
        # Star column is narrow; rest expand
        self.grid_columnconfigure(0, weight=0, minsize=32)
        for c in range(1, len(self.HEADERS)):
            self.grid_columnconfigure(c, weight=1)
        self._update_header_arrows()

    def _ensure_pool(self, n: int) -> None:
        while len(self._pool) < n:
            i = len(self._pool)
            labels: list[tk.Label] = []
            for c in range(len(self.HEADERS)):
                is_star = c == 0
                lbl = tk.Label(
                    self,
                    text="",
                    font=(
                        self._STAR_FONT
                        if is_star
                        else (FONT_MONO if c >= 3 else FONT_BODY)
                    ),
                    fg=TEXT_PRIMARY,
                    bg=BG_DARK,
                    anchor="center" if is_star else "w",
                    cursor="hand2" if is_star else "",
                    bd=0,
                    padx=4,
                    pady=3,
                    highlightthickness=0,
                )
                lbl.grid(row=i + 2, column=c, sticky="ew", padx=(0, 0), pady=0)
                lbl.grid_remove()
                if is_star:
                    lbl.bind("<Button-1>", lambda e, r=i: self._on_star(r))
                else:
                    lbl.bind("<Double-Button-1>", lambda e, r=i: self._on_copy_row(r))
                labels.append(lbl)
            self._pool.append(labels)
            self._row_codes.append(None)

    # ── public API ────────────────────────────────────────────────────────────

    def populate(
        self,
        rates: dict[str, float],
        currency_names: dict[str, str],
        base: str,
        filter_text: str = "",
    ) -> None:
        # Change % is only meaningful against the previous snapshot of the
        # *same* base currency; it's computed here (not in _render) so that
        # filtering / sorting / pinning never wipes the indicators.
        if self._prev_base == base and self._prev:
            self._changes = {
                c: (
                    ((r - self._prev[c]) / self._prev[c] * 100)
                    if self._prev.get(c)
                    else None
                )
                for c, r in rates.items()
            }
        else:
            self._changes = {c: None for c in rates}
        self._prev = dict(rates)
        self._prev_base = base

        self._raw_rates = rates
        self._raw_names = currency_names
        self._raw_base = base
        if filter_text:
            self._filter = filter_text.upper()
        self._render()

    def set_filter(self, text: str) -> None:
        self._filter = text.upper()
        self._render()

    def sort_by(self, key: str) -> None:
        if key == self._sort_key:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_key = key
            self._sort_desc = key in ("rate", "change")
        self._update_header_arrows()
        self._render()

    # ── rendering ─────────────────────────────────────────────────────────────

    def _update_header_arrows(self) -> None:
        for h, lbl in self._header_lbls.items():
            key = self.SORTABLE.get(h)
            if key and key == self._sort_key:
                lbl.configure(text=f"{h} {'▼' if self._sort_desc else '▲'}")
            else:
                lbl.configure(text=h)

    def _sorted_items(self, items: list[tuple[str, float]]) -> list[tuple[str, float]]:
        k = self._sort_key
        if k == "name":
            keyf = lambda it: self._raw_names.get(it[0], it[0]).upper()
        elif k == "rate":
            keyf = lambda it: it[1]
        elif k == "change":
            # Unknown changes always sink to the bottom regardless of direction
            def keyf(it):
                ch = self._changes.get(it[0])
                return (ch is not None, ch if ch is not None else 0.0)

        else:
            keyf = lambda it: it[0]
        return sorted(items, key=keyf, reverse=self._sort_desc)

    def _render(self) -> None:
        pinned_quotes: set[str] = set()
        if self._settings:
            pinned_quotes = {
                q for b, q in self._settings.get_favourites() if b == self._raw_base
            }

        items = list(self._raw_rates.items())
        if self._filter:
            items = [
                (c, r)
                for c, r in items
                if self._filter in c
                or self._filter in self._raw_names.get(c, "").upper()
            ]
        items = self._sorted_items(items)

        # Pinned pairs float to the top (sorted() is stable, so order is kept)
        items.sort(key=lambda it: it[0] not in pinned_quotes)

        self._ensure_pool(len(items))
        self._show_empty(not items and bool(self._raw_rates))

        for i, labels in enumerate(self._pool):
            if i >= len(items):
                if self._row_codes[i] is not None:
                    for lbl in labels:
                        lbl.grid_remove()
                    self._row_codes[i] = None
                continue

            code, rate = items[i]
            bg = BG_CARD if i % 2 == 0 else BG_DARK
            is_pinned = code in pinned_quotes

            name = self._raw_names.get(code, code)
            inv = 1 / rate if rate else 0.0
            pct = self._changes.get(code)
            if pct is None:
                ct, cc = "—", TEXT_MUTED
            elif pct > 0:
                ct, cc = f"▲ {pct:.4f}%", ACCENT_GREEN
            elif pct < 0:
                ct, cc = f"▼ {abs(pct):.4f}%", ACCENT_RED
            else:
                ct, cc = "→ 0.0000%", TEXT_MUTED

            row_vals = (
                "★" if is_pinned else "☆",
                name,
                code,
                _fmt_rate(rate),
                _fmt_rate(inv),
                ct,
            )
            row_colors = (
                ACCENT_GOLD if is_pinned else TEXT_DIM,
                TEXT_PRIMARY,
                ACCENT_GOLD,
                TEXT_PRIMARY,
                TEXT_MUTED,
                cc,
            )
            for lbl, v, col in zip(labels, row_vals, row_colors):
                lbl.configure(text=v, fg=col, bg=bg)
                if self._row_codes[i] is None:
                    lbl.grid()
            self._row_codes[i] = code

    def _show_empty(self, show: bool) -> None:
        if show:
            if self._empty_lbl is None:
                self._empty_lbl = ctk.CTkLabel(
                    self,
                    text="No currencies match the filter",
                    font=FONT_BODY,
                    text_color=TEXT_DIM,
                )
            self._empty_lbl.grid(
                row=2, column=0, columnspan=len(self.HEADERS), pady=PAD_LG
            )
        elif self._empty_lbl is not None:
            self._empty_lbl.grid_remove()

    # ── interactions ──────────────────────────────────────────────────────────

    def _on_star(self, row: int) -> None:
        code = self._row_codes[row] if row < len(self._row_codes) else None
        if code:
            self._toggle_pin(self._raw_base, code)

    def _on_copy_row(self, row: int) -> None:
        code = self._row_codes[row] if row < len(self._row_codes) else None
        if not code:
            return
        rate = self._raw_rates.get(code)
        text = f"1 {self._raw_base} = {_fmt_rate(rate)} {code}"
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            return
        if self._on_copy:
            self._on_copy(text)

    def _toggle_pin(self, base: str, quote: str) -> None:
        if self._settings:
            self._settings.toggle_favourite(base, quote)
            self._render()
            if self._on_pin:
                self._on_pin()


def _fmt_rate(v) -> str:
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


class SearchEntry(ctk.CTkFrame):
    """
    Search/filter text field with clear button.
    Debounces keystrokes by 120 ms so rapid typing doesn't hammer the
    on_change callback on every single character.
    """

    _DEBOUNCE_MS = 120

    def __init__(self, master, placeholder: str = "Search…", on_change=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._cb = on_change
        self._var = tk.StringVar()
        self._var.trace_add("write", self._on_write)
        self._after_id: str | None = None
        self._entry = ctk.CTkEntry(
            self,
            textvariable=self._var,
            placeholder_text=placeholder,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_BODY,
            height=32,
        )
        self._entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            self,
            text="✕",
            width=32,
            height=32,
            fg_color=BG_INPUT,
            hover_color=BG_HOVER,
            text_color=TEXT_MUTED,
            font=FONT_SMALL,
            command=self.clear,
        ).pack(side="left", padx=(2, 0))

    def _on_write(self, *_) -> None:
        if self._after_id is not None:
            try:
                self._entry.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self._entry.after(self._DEBOUNCE_MS, self._fire)

    def _fire(self) -> None:
        self._after_id = None
        if self._cb:
            self._cb(self._var.get())

    def clear(self) -> None:
        self._var.set("")

    def get(self) -> str:
        return self._var.get()


class WatchlistPanel(ctk.CTkScrollableFrame):
    """
    Compact live watchlist rows — starred pairs sorted to the top.

    Click a pair to select it (fires ``on_select(base, quote)``), ★ to pin it,
    ✕ to remove it (fires ``on_remove(base, quote)``). Bindings are attached
    once per pooled row and resolve the row's current pair at click time.
    """

    def __init__(self, master, settings=None, on_select=None, on_remove=None, **kw):
        super().__init__(master, fg_color=BG_DARK, **kw)
        self._settings = settings
        self._on_select = on_select
        self._on_remove = on_remove
        self._pairs: list[tuple[str, str]] = []
        self._pool: list[tuple[ctk.CTkFrame, list]] = []
        self._row_pairs: list[tuple[str, str] | None] = []
        self._last_snaps: list[dict] = []
        self._selected: tuple[str, str] | None = None
        self._empty_lbl = ctk.CTkLabel(
            self,
            text="Your watchlist is empty — add a pair on the left.",
            font=FONT_BODY,
            text_color=TEXT_DIM,
        )

    def set_pairs(self, pairs: list[tuple[str, str]]) -> None:
        self._pairs = pairs

    def set_selected(self, base: str, quote: str) -> None:
        self._selected = (base, quote)
        self.refresh(self._last_snaps)

    def _ensure_pool(self, n: int) -> None:
        while len(self._pool) < n:
            i = len(self._pool)
            row = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=4, cursor="hand2")

            star_lbl = ctk.CTkLabel(
                row,
                text="☆",
                font=("Helvetica Neue", 13),
                text_color=TEXT_DIM,
                width=24,
                cursor="hand2",
            )
            star_lbl.pack(side="left", padx=(PAD_SM, 2), pady=6)

            pair_lbl = ctk.CTkLabel(
                row,
                text="",
                font=FONT_SUBHEAD,
                text_color=ACCENT_GOLD,
                width=80,
                anchor="w",
            )
            pair_lbl.pack(side="left", padx=PAD_SM, pady=6)

            rate_lbl = ctk.CTkLabel(
                row, text="", font=FONT_MONO, text_color=TEXT_PRIMARY
            )
            rate_lbl.pack(side="left", padx=PAD_SM)

            del_lbl = ctk.CTkLabel(
                row,
                text="✕",
                font=FONT_SMALL,
                text_color=TEXT_DIM,
                width=24,
                cursor="hand2",
            )
            del_lbl.pack(side="right", padx=(0, PAD_SM))

            date_lbl = ctk.CTkLabel(row, text="", font=FONT_SMALL, text_color=TEXT_DIM)
            date_lbl.pack(side="right", padx=PAD_MD)

            # Bind exactly once; handlers resolve the pair for row *i* lazily.
            star_lbl.bind("<Button-1>", lambda e, r=i: self._row_action(r, "star"))
            del_lbl.bind("<Button-1>", lambda e, r=i: self._row_action(r, "remove"))
            del_lbl.bind(
                "<Enter>", lambda e, w=del_lbl: w.configure(text_color=ACCENT_RED)
            )
            del_lbl.bind(
                "<Leave>", lambda e, w=del_lbl: w.configure(text_color=TEXT_DIM)
            )
            for w in (row, pair_lbl, rate_lbl, date_lbl):
                w.bind("<Button-1>", lambda e, r=i: self._row_action(r, "select"))

            self._pool.append((row, [star_lbl, pair_lbl, rate_lbl, date_lbl, del_lbl]))
            self._row_pairs.append(None)

    def refresh(self, snapshots: list[dict]) -> None:
        self._last_snaps = snapshots

        # Sort starred pairs to top
        if self._settings:
            favs = {(str(b), str(q)) for b, q in self._settings.get_favourites()}

            def sort_key(snap):
                b = str(snap.get("base", "?"))
                q = str(snap.get("quote", "?"))
                return (0 if (b, q) in favs else 1, b, q)

            snapshots = sorted(snapshots, key=sort_key)

        if snapshots:
            self._empty_lbl.pack_forget()
        else:
            self._empty_lbl.pack(pady=PAD_LG)

        self._ensure_pool(len(snapshots))
        for i, snap in enumerate(snapshots):
            base = str(snap.get("base", "?"))
            quote = str(snap.get("quote", "?"))
            rate = snap.get("rate")
            rate_s = _fmt_rate(rate) if rate else "N/A"
            err = snap.get("error")
            date_s = "error" if err else str(snap.get("date") or "")
            is_sel = self._selected == (base, quote)
            bg = BG_SELECTED if is_sel else (BG_CARD if i % 2 == 0 else BG_DARK)
            is_fav = bool(self._settings and self._settings.is_favourite(base, quote))

            row, widgets = self._pool[i]
            star_lbl, pair_lbl, rate_lbl, date_lbl, _del = widgets
            row.configure(
                fg_color=bg,
                border_width=1 if is_sel else 0,
                border_color=ACCENT_GOLD,
            )
            star_lbl.configure(
                text="★" if is_fav else "☆",
                text_color=ACCENT_GOLD if is_fav else TEXT_DIM,
            )
            pair_lbl.configure(text=f"{base}/{quote}")
            rate_lbl.configure(
                text=rate_s, text_color=TEXT_PRIMARY if rate else ACCENT_RED
            )
            date_lbl.configure(text=date_s, text_color=ACCENT_RED if err else TEXT_DIM)
            self._row_pairs[i] = (base, quote)

            row.pack(fill="x", pady=1)

        for i in range(len(snapshots), len(self._pool)):
            self._pool[i][0].pack_forget()
            self._row_pairs[i] = None

    def _row_action(self, row: int, action: str) -> None:
        pair = self._row_pairs[row] if row < len(self._row_pairs) else None
        if pair is None:
            return
        base, quote = pair
        if action == "star":
            self._toggle_fav(base, quote)
        elif action == "remove":
            if self._on_remove:
                self._on_remove(base, quote)
        elif action == "select":
            self._selected = pair
            self.refresh(self._last_snaps)
            if self._on_select:
                self._on_select(base, quote)

    def _toggle_fav(self, base: str, quote: str) -> None:
        if self._settings:
            self._settings.toggle_favourite(base, quote)
            # Re-render with stored snapshot to reflect new order
            self.refresh(self._last_snaps)


class LoadingOverlay(ctk.CTkFrame):
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG_CARD, corner_radius=CORNER_RADIUS, **kw)
        self._lbl = ctk.CTkLabel(
            self, text="⠋  Fetching…", font=("Courier New", 13), text_color=ACCENT_GOLD
        )
        self._lbl.pack(expand=True)
        self._idx = 0
        self._running = False

    def start(self) -> None:
        self._running = True
        self._tick()

    def stop(self) -> None:
        self._running = False

    def _tick(self) -> None:
        if not self._running:
            return
        self._idx = (self._idx + 1) % len(self.FRAMES)
        self._lbl.configure(text=f"{self.FRAMES[self._idx]}  Fetching data…")
        self.after(80, self._tick)


class SkeletonFrame(ctk.CTkFrame):
    """
    Animated loading skeleton — place() over a content frame while data is
    in flight.  Call show() before the request and hide() in the done callback.
    """

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, master, rows: int = 7, **kw):
        super().__init__(master, fg_color=BG_DARK, corner_radius=0, **kw)
        self._after_id: str | None = None
        self._fidx = 0
        self._bars: list[ctk.CTkFrame] = []
        self._phase = False

        self._spinner = ctk.CTkLabel(
            self,
            text="⠋  Loading…",
            font=("Courier New", 12),
            text_color=ACCENT_GOLD,
        )
        self._spinner.pack(pady=(PAD_LG + 4, PAD_MD))

        widths = [0.85, 0.65, 0.78, 0.55, 0.82, 0.60, 0.72]
        for j in range(rows):
            outer = ctk.CTkFrame(self, fg_color="transparent")
            outer.pack(fill="x", padx=PAD_LG * 3, pady=4)
            bar = ctk.CTkFrame(outer, fg_color=BG_INPUT, height=16, corner_radius=4)
            bar.pack(fill="x")
            self._bars.append(bar)

    # ── public ────────────────────────────────────────────────────────────────

    def show(self) -> None:
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        if self._after_id is None:  # don't stack a second animation loop
            self._animate()

    def hide(self) -> None:
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.place_forget()

    # ── animation ─────────────────────────────────────────────────────────────

    def _animate(self) -> None:
        self._fidx = (self._fidx + 1) % len(self.FRAMES)
        self._spinner.configure(text=f"{self.FRAMES[self._fidx]}  Loading data…")
        self._phase = not self._phase
        shade = BG_HOVER if self._phase else BG_INPUT
        for bar in self._bars:
            bar.configure(fg_color=shade)
        self._after_id = self.after(140, self._animate)


# ── Date picker (tkcalendar) ──────────────────────────────────────────────────

try:  # tkcalendar is optional at runtime — the button simply isn't offered
    from tkcalendar import Calendar as _TkCalendar
except Exception:  # pragma: no cover - depends on the environment
    _TkCalendar = None


def date_picker_available() -> bool:
    return _TkCalendar is not None


def open_date_picker(entry, on_pick=None) -> None:
    """
    Pop up a dark-themed calendar beneath *entry* (a CTkEntry holding a
    YYYY-MM-DD string). Picking a day writes it back into the entry and calls
    ``on_pick(iso_date)``. Escape or closing the window cancels.
    """
    if _TkCalendar is None:
        return
    from datetime import date as _date

    try:
        current = _date.fromisoformat(entry.get().strip())
    except ValueError:
        current = _date.today()

    top = ctk.CTkToplevel(entry)
    top.title("Pick a date")
    top.configure(fg_color=BG_CARD)
    top.resizable(False, False)
    top.transient(entry.winfo_toplevel())
    x = entry.winfo_rootx()
    y = entry.winfo_rooty() + entry.winfo_height() + 4
    top.geometry(f"+{x}+{y}")

    cal = _TkCalendar(
        top,
        selectmode="day",
        year=current.year,
        month=current.month,
        day=current.day,
        date_pattern="yyyy-mm-dd",
        maxdate=_date.today(),
        mindate=_date(1948, 1, 1),
        showweeknumbers=False,
        firstweekday="monday",
        font=FONT_LABEL,
        background=BG_CARD,
        foreground=TEXT_PRIMARY,
        bordercolor=BORDER_COLOR,
        headersbackground=BG_INPUT,
        headersforeground=ACCENT_GOLD,
        normalbackground=BG_DARK,
        normalforeground=TEXT_PRIMARY,
        weekendbackground=BG_DARK,
        weekendforeground=TEXT_MUTED,
        othermonthbackground=BG_CARD,
        othermonthforeground=TEXT_DIM,
        othermonthwebackground=BG_CARD,
        othermonthweforeground=TEXT_DIM,
        selectbackground=ACCENT_GOLD,
        selectforeground=BG_DARK,
        disabledbackground=BG_CARD,
        disabledforeground=TEXT_DIM,
        disableddaybackground=BG_CARD,
        disableddayforeground=TEXT_DIM,
    )
    cal.pack(padx=PAD_SM, pady=PAD_SM)

    def _pick(_event=None):
        iso = cal.get_date()
        entry.delete(0, "end")
        entry.insert(0, iso)
        top.destroy()
        if on_pick:
            on_pick(iso)

    btns = ctk.CTkFrame(top, fg_color="transparent")
    btns.pack(fill="x", padx=PAD_SM, pady=(0, PAD_SM))
    ctk.CTkButton(
        btns,
        text="Today",
        width=70,
        height=26,
        fg_color=BG_INPUT,
        hover_color=BG_HOVER,
        text_color=TEXT_PRIMARY,
        font=FONT_SMALL,
        command=lambda: (cal.selection_set(_date.today()), _pick()),
    ).pack(side="left")
    ctk.CTkButton(
        btns,
        text="Cancel",
        width=70,
        height=26,
        fg_color=BG_INPUT,
        hover_color=BG_HOVER,
        text_color=TEXT_MUTED,
        font=FONT_SMALL,
        command=top.destroy,
    ).pack(side="right")

    cal.bind("<<CalendarSelected>>", _pick)
    top.bind("<Escape>", lambda e: top.destroy())
    top.after(50, top.focus_force)


class DateEntry(ctk.CTkFrame):
    """
    A YYYY-MM-DD entry with a 📅 calendar button. Exposes the subset of the
    CTkEntry API the tabs use (get / delete / insert) so it is a drop-in
    replacement, and validates its contents on demand.
    """

    def __init__(self, master, default: str = "", width: int = 160, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="YYYY-MM-DD",
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_MONO,
            width=width,
            height=32,
        )
        if default:
            self.entry.insert(0, default)
        self.entry.pack(side="left", fill="x", expand=True)
        if date_picker_available():
            ctk.CTkButton(
                self,
                text="📅",
                width=32,
                height=32,
                fg_color=BG_INPUT,
                hover_color=BG_HOVER,
                border_color=BORDER_COLOR,
                border_width=1,
                text_color=ACCENT_GOLD,
                font=FONT_BODY,
                command=lambda: open_date_picker(self.entry),
            ).pack(side="left", padx=(2, 0))

    # CTkEntry-compatible surface
    def get(self) -> str:
        return self.entry.get()

    def delete(self, first, last=None) -> None:
        self.entry.delete(first, last)

    def insert(self, index, text: str) -> None:
        self.entry.insert(index, text)

    def set(self, text: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, text)

    def flag_error(self, bad: bool = True) -> None:
        """Highlight the field red (e.g. after failed validation)."""
        self.entry.configure(border_color=ACCENT_RED if bad else BORDER_COLOR)
