"""
All tab views for the Frankfurter GUI brought to you by Florian van den Bersselaar.
"""

import json
import math
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox

import customtkinter as ctk

from exports.exporter import default_filename, export_to_csv, export_to_json
from ui.chart_panel import ChartPanel
from ui.theme import *
from ui.widgets import (
    DateEntry,
    HSeparator,
    LabelledCombo,
    RateTable,
    SearchEntry,
    SectionHeader,
    SkeletonFrame,
    StatCard,
    WatchlistPanel,
)
from utils.workers import AsyncWorker

# Earliest date with data in the Frankfurter API
MIN_DATE = date(1948, 1, 1)

# ── helpers ────────────────────────────────────────────────────────────────────


def _date_entry(parent, label, default):
    """Labelled YYYY-MM-DD field with a 📅 calendar picker."""
    ctk.CTkLabel(parent, text=label, font=FONT_LABEL, text_color=TEXT_MUTED).pack(
        anchor="w"
    )
    e = DateEntry(parent, default=default, width=160)
    e.pack(fill="x", pady=(0, PAD_SM))
    return e


def _code_entry(parent, label, default, codes):
    """Labelled currency field: a combo box that lists every known code but
    still accepts typing (so archived codes like DEM can be entered)."""
    ctk.CTkLabel(parent, text=label, font=FONT_LABEL, text_color=TEXT_MUTED).pack(
        anchor="w"
    )
    cb = ctk.CTkComboBox(
        parent,
        values=list(codes),
        fg_color=BG_INPUT,
        border_color=BORDER_COLOR,
        button_color=ACCENT_GOLD,
        button_hover_color="#B8960C",
        dropdown_fg_color=BG_CARD,
        dropdown_hover_color=BG_HOVER,
        text_color=TEXT_PRIMARY,
        font=FONT_MONO,
        width=160,
        height=32,
    )
    cb.set(default)
    cb.pack(fill="x", pady=(0, PAD_SM))
    return cb


def _code(widget, fallback):
    """Read a currency code from an entry/combo ("EUR – Euro" → "EUR")."""
    return widget.get().split(" –")[0].strip().upper() or fallback


def _parse_date(text):
    """Return a date for a YYYY-MM-DD string, or None if invalid."""
    try:
        return date.fromisoformat(text.strip())
    except (ValueError, AttributeError):
        return None


def _validate_range(start_w, end_w):
    """
    Validate a start/end pair of DateEntry widgets. Returns
    (start_iso, end_iso, None) on success or (None, None, error_message).
    Offending fields are highlighted red.
    """
    s, e = _parse_date(start_w.get()), _parse_date(end_w.get())
    for w, d in ((start_w, s), (end_w, e)):
        if hasattr(w, "flag_error"):
            w.flag_error(d is None)
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


def _btn(parent, text, cmd, accent=True, **kw):
    return ctk.CTkButton(
        parent,
        text=text,
        fg_color=ACCENT_GOLD if accent else BG_INPUT,
        hover_color="#B8960C" if accent else BG_HOVER,
        text_color=BG_DARK if accent else TEXT_PRIMARY,
        font=("Georgia", 11, "bold"),
        height=36,
        corner_radius=CORNER_RADIUS,
        command=cmd,
        **kw,
    )


def _chip_grid(parent, items, cols=4, width=48):
    """
    Lay small 'chip' buttons out in a wrapping grid. *items* is a list of
    (label, command). Packing them side-by-side (the old approach) pushed
    everything past the 4th button outside the fixed-width sidebar.
    """
    f = ctk.CTkFrame(parent, fg_color="transparent")
    for c in range(cols):
        f.grid_columnconfigure(c, weight=1, uniform="chip")
    for i, (lbl, cmd) in enumerate(items):
        ctk.CTkButton(
            f,
            text=lbl,
            height=26,
            width=width,
            fg_color=BG_INPUT,
            hover_color=BG_HOVER,
            text_color=TEXT_PRIMARY,
            font=FONT_SMALL,
            command=cmd,
        ).grid(row=i // cols, column=i % cols, padx=1, pady=1, sticky="ew")
    return f


def _sidebar(parent, title):
    # Scrollable so every control stays reachable on small windows (the
    # Time Series sidebar used to cut its export buttons off at 800 px).
    sb = ctk.CTkScrollableFrame(
        parent,
        fg_color=BG_CARD,
        corner_radius=0,
        width=236,
        scrollbar_button_color=BG_CARD,
        scrollbar_button_hover_color=BG_HOVER,
    )
    sb.pack(side="left", fill="y")
    ctk.CTkLabel(sb, text=title, font=FONT_HEADING, text_color=ACCENT_GOLD).pack(
        pady=(PAD_LG, PAD_SM), padx=PAD_MD, anchor="w"
    )
    return sb


def _quick_range_row(parent, start_entry, end_entry, fetch_fn):
    """Add quick-range buttons (1M 3M 6M YTD 1Y) to *parent*, wiring them to
    start_entry / end_entry and calling fetch_fn after each click."""
    ctk.CTkLabel(
        parent, text="Quick Ranges", font=FONT_LABEL, text_color=TEXT_MUTED
    ).pack(padx=PAD_MD, anchor="w")

    def _apply(days, ytd=False):
        end = date.today()
        start = date(end.year, 1, 1) if ytd else (end - timedelta(days=days))
        start_entry.delete(0, "end")
        start_entry.insert(0, start.isoformat())
        end_entry.delete(0, "end")
        end_entry.insert(0, end.isoformat())
        fetch_fn()

    presets = [
        ("1M", 30, False),
        ("3M", 90, False),
        ("6M", 180, False),
        ("YTD", 0, True),
        ("1Y", 365, False),
        ("2Y", 730, False),
        ("5Y", 1826, False),
        ("10Y", 3652, False),
    ]
    _chip_grid(
        parent,
        [(lbl, lambda d=days, y=ytd: _apply(d, y)) for lbl, days, ytd in presets],
        cols=4,
    ).pack(fill="x", padx=PAD_MD, pady=(2, 0))


# ── base ───────────────────────────────────────────────────────────────────────


class BaseTab(ctk.CTkFrame):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, fg_color=BG_DARK, **kw)
        self._client = client
        self._names = currency_names
        self._status = status_cb
        self._codes = sorted(currency_names.keys())
        self._settings = settings
        # Monotonic request counters per channel: a response is only applied
        # if no newer request on the same channel was started meanwhile, so a
        # slow old reply can never overwrite fresher data on screen.
        self._req_seq: dict[str, int] = {}

    def _run(self, fn, cb, skeleton=None, channel="main"):
        self._status("Fetching…", "loading")
        seq = self._req_seq.get(channel, 0) + 1
        self._req_seq[channel] = seq
        if skeleton:
            try:
                skeleton.show()
            except Exception:
                pass

        def wrapped(result, err):
            if self._req_seq.get(channel) != seq:
                return  # superseded by a newer request
            if skeleton:
                try:
                    skeleton.hide()
                except Exception:
                    pass
            try:
                if not self.winfo_exists():
                    return
            except Exception:
                return
            cb(result, err)

        AsyncWorker(fn, wrapped, root=self.winfo_toplevel()).start()

    def _check_codes(self, *codes) -> bool:
        """Validate currency codes against the loaded list (if any)."""
        # Only the shape is checked here: archived codes (DEM, FRF…) are not
        # in the active list but are still valid, so the API has the final say.
        for c in codes:
            if not c or len(c) != 3 or not c.isalpha():
                self._status(f"Invalid currency code: {c or '(empty)'}", "error")
                return False
        return True

    def _export_csv_data(self, data, prefix="rates"):
        if not data:
            self._status("Nothing to export yet — fetch some data first", "error")
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=default_filename(prefix, "csv"),
        )
        if p:
            try:
                export_to_csv(data, p)
                self._status(f"Exported → {p}", "ok")
            except OSError as e:
                self._status(f"Export failed: {e}", "error")

    def _export_json_data(self, data, prefix="rates"):
        if not data:
            self._status("Nothing to export yet — fetch some data first", "error")
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=default_filename(prefix, "json"),
        )
        if p:
            try:
                export_to_json(data, p)
                self._status(f"Exported → {p}", "ok")
            except OSError as e:
                self._status(f"Export failed: {e}", "error")


# ══════════════════════════════════════════════════════════════════════════════
# 1. Dashboard
# ══════════════════════════════════════════════════════════════════════════════


class DashboardTab(BaseTab):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._last: dict = {}
        self._build()

    def _build(self):
        sb = _sidebar(self, "FRANKFURTER")
        ctk.CTkLabel(
            sb, text="Exchange Rate Terminal", font=FONT_SMALL, text_color=TEXT_MUTED
        ).pack(padx=PAD_MD, anchor="w")
        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)

        SectionHeader(sb, "Base Currency").pack(
            padx=PAD_MD, pady=(0, PAD_SM), anchor="w"
        )
        self._base = LabelledCombo(
            sb, "", self._codes, width=210, command=lambda _: self._fetch()
        )
        saved_base = (
            self._settings.get("dashboard_base", "EUR") if self._settings else "EUR"
        )
        self._base.set(saved_base)
        self._base.pack(padx=PAD_MD, pady=(0, PAD_MD), fill="x")

        SectionHeader(sb, "Filter").pack(padx=PAD_MD, pady=(0, PAD_SM), anchor="w")
        self._search = SearchEntry(sb, "Search currencies…", on_change=self._on_filter)
        self._search.pack(padx=PAD_MD, fill="x")

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _btn(sb, "⟳  Refresh", lambda: self._fetch(force=True)).pack(
            padx=PAD_MD, pady=2, fill="x"
        )
        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _btn(sb, "⬇  CSV", self._do_csv, accent=False).pack(
            padx=PAD_MD, pady=2, fill="x"
        )
        _btn(sb, "⬇  JSON", self._do_json, accent=False).pack(
            padx=PAD_MD, pady=2, fill="x"
        )

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        ctk.CTkLabel(
            sb, text="Currency Scope", font=FONT_LABEL, text_color=TEXT_MUTED
        ).pack(padx=PAD_MD, anchor="w")
        self._scope = ctk.StringVar(value="active")
        for v, l in [
            ("active", "Active only"),
            ("all", "All incl. archived names"),
        ]:
            ctk.CTkRadioButton(
                sb,
                text=l,
                variable=self._scope,
                value=v,
                font=FONT_SMALL,
                text_color=TEXT_PRIMARY,
                fg_color=ACCENT_GOLD,
                hover_color="#B8960C",
                command=self._fetch,
            ).pack(anchor="w", padx=PAD_MD, pady=1)

        # Pinned pairs panel in sidebar
        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        ctk.CTkLabel(
            sb, text="★  Pinned Pairs", font=FONT_LABEL, text_color=ACCENT_GOLD
        ).pack(padx=PAD_MD, anchor="w")
        self._pinned_lbl = ctk.CTkLabel(
            sb,
            text="Click ★ in the table to pin a pair",
            font=FONT_SMALL,
            text_color=TEXT_DIM,
            wraplength=200,
            justify="left",
        )
        self._pinned_lbl.pack(padx=PAD_MD, anchor="w", pady=(2, 0))

        # main
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=PAD_LG, pady=PAD_LG)

        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.pack(fill="x", pady=(0, PAD_LG))
        self._c_rate = StatCard(cards, "EUR/USD")
        self._c_count = StatCard(cards, "Currencies", color=ACCENT_BLUE)
        self._c_date = StatCard(cards, "Last Updated", color=TEXT_PRIMARY)
        self._c_scope = StatCard(cards, "Scope", color=ACCENT_PURPLE)
        for c in [self._c_rate, self._c_count, self._c_date, self._c_scope]:
            c.pack(side="left", expand=True, fill="both", padx=PAD_SM)

        SectionHeader(
            main,
            "Exchange Rates  (click ★ to pin • header to sort • double-click to copy)",
        ).pack(anchor="w", pady=(0, PAD_SM))

        # Wrap table in a relative-positioned container so SkeletonFrame can place() over it
        table_wrap = ctk.CTkFrame(main, fg_color="transparent")
        table_wrap.pack(fill="both", expand=True)
        self._table = RateTable(
            table_wrap,
            settings=self._settings,
            on_copy=lambda t: self._status(f"Copied  “{t}”", "ok"),
            on_pin=self._update_pinned_label,
        )
        self._table.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(table_wrap)

        self._fetch()

    def _update_pinned_label(self):
        if not self._settings:
            return
        favs = self._settings.get_favourites()
        base = self._base.get().split(" –")[0].strip()
        pairs = [f"{b}/{q}" for b, q in favs if b == base]
        if pairs:
            self._pinned_lbl.configure(text="\n".join(pairs), text_color=ACCENT_GOLD)
        else:
            self._pinned_lbl.configure(
                text="Click ★ in the table to pin a pair", text_color=TEXT_DIM
            )

    def _on_filter(self, text):
        self._table.set_filter(text)

    def _fetch(self, force=False):
        base = _code(self._base, "EUR")
        if not self._check_codes(base):
            return
        scope = self._scope.get()
        if self._settings:
            self._settings.set("dashboard_base", base)

        def work():
            if force:
                self._client.invalidate_latest()
            rates = self._client.get_latest_rates(base)
            names = self._client.get_currencies(scope)
            return rates, names

        def done(result, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            rates_data, names = result
            self._last = rates_data
            self._names = names
            self._codes = sorted(names.keys())
            rates = rates_data.get("rates", {})
            on_date = rates_data.get("date", "—")
            # Headline pair: vs USD, or vs EUR when the base *is* USD
            ref = "EUR" if base == "USD" else "USD"
            self._c_rate.set_label(f"{base}/{ref}")
            ref_rate = rates.get(ref)
            self._c_rate.set_value(f"{ref_rate:.4f}" if ref_rate is not None else "—")
            self._c_count.set_value(str(len(rates)))
            self._c_date.set_value(on_date)
            self._c_scope.set_value(scope.capitalize())
            self._table.populate(rates, names, base)
            self._update_pinned_label()
            self._status(f"Rates for {base}  •  {on_date}  •  {len(rates)} pairs", "ok")

        self._run(work, done, skeleton=self._skeleton)

    def _do_csv(self):
        self._export_csv_data(self._last, "latest")

    def _do_json(self):
        self._export_json_data(self._last, "latest")


# ══════════════════════════════════════════════════════════════════════════════
# 2. Historical
# ══════════════════════════════════════════════════════════════════════════════


class HistoricalTab(BaseTab):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._last: dict = {}
        self._build()

    def _build(self):
        sb = _sidebar(self, "Historical Lookup")
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="x", padx=PAD_MD)
        s = self._settings
        self._base_e = _code_entry(
            inner,
            "Base Currency",
            s.get("hist_base", "EUR") if s else "EUR",
            self._codes,
        )
        self._date_e = _date_entry(
            inner,
            "Date (YYYY-MM-DD)",
            s.get("hist_date", "2010-01-04") if s else "2010-01-04",
        )

        # Step one business day back / forward and re-fetch
        step = ctk.CTkFrame(inner, fg_color="transparent")
        step.pack(fill="x", pady=(0, PAD_SM))
        step.grid_columnconfigure((0, 1), weight=1)
        for col, (txt, delta) in enumerate((("◀  Prev day", -1), ("Next day  ▶", 1))):
            ctk.CTkButton(
                step,
                text=txt,
                height=26,
                fg_color=BG_INPUT,
                hover_color=BG_HOVER,
                text_color=TEXT_PRIMARY,
                font=FONT_SMALL,
                command=lambda d=delta: self._step_day(d),
            ).grid(row=0, column=col, sticky="ew", padx=(2, 0) if col else (0, 2))

        _btn(inner, "🔍  Fetch", self._fetch).pack(fill="x", pady=PAD_SM)
        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)

        ctk.CTkLabel(
            sb, text="Quick Jump", font=FONT_LABEL, text_color=TEXT_MUTED
        ).pack(padx=PAD_MD, anchor="w")
        current_year = date.today().year
        _chip_grid(
            sb,
            [
                (str(yr), lambda y=yr: self._jump_year(y))
                for yr in range(current_year, current_year - 12, -1)
            ],
            cols=4,
        ).pack(fill="x", padx=PAD_MD, pady=(2, 0))

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _btn(
            sb,
            "⬇  CSV",
            lambda: self._export_csv_data(self._last, "historical"),
            accent=False,
        ).pack(padx=PAD_MD, pady=2, fill="x")
        _btn(
            sb,
            "⬇  JSON",
            lambda: self._export_json_data(self._last, "historical"),
            accent=False,
        ).pack(padx=PAD_MD, pady=2, fill="x")

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=PAD_LG, pady=PAD_LG)

        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.pack(fill="x", pady=(0, PAD_LG))
        self._c_base = StatCard(cards, "Base")
        self._c_date2 = StatCard(cards, "Date", color=ACCENT_BLUE)
        self._c_cnt = StatCard(cards, "Currencies", color=TEXT_PRIMARY)
        for c in [self._c_base, self._c_date2, self._c_cnt]:
            c.pack(side="left", expand=True, fill="both", padx=PAD_SM)

        SectionHeader(main, "Rates on Selected Date").pack(anchor="w", pady=(0, PAD_SM))

        table_wrap = ctk.CTkFrame(main, fg_color="transparent")
        table_wrap.pack(fill="both", expand=True)
        self._table = RateTable(
            table_wrap,
            settings=self._settings,
            on_copy=lambda t: self._status(f"Copied  “{t}”", "ok"),
        )
        self._table.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(table_wrap)

    def _jump_year(self, yr):
        # The first business day of the current year may not exist yet
        target = min(date(yr, 1, 2), date.today())
        self._date_e.set(target.isoformat())
        self._fetch()

    def _step_day(self, delta):
        d = _parse_date(self._date_e.get()) or date.today()
        d += timedelta(days=delta)
        # Skip weekends — central banks don't publish on them
        while d.weekday() >= 5:
            d += timedelta(days=delta)
        if d > date.today() or d < MIN_DATE:
            self._status("No data beyond that date", "error")
            return
        self._date_e.set(d.isoformat())
        self._fetch()

    def _fetch(self):
        base = _code(self._base_e, "EUR")
        d = _parse_date(self._date_e.get())
        self._date_e.flag_error(d is None or d > date.today() or d < MIN_DATE)
        if d is None:
            self._status("Date must be in YYYY-MM-DD format", "error")
            return
        if d > date.today() or d < MIN_DATE:
            self._status(f"Date must be between {MIN_DATE} and today", "error")
            return
        if not self._check_codes(base):
            return
        on_date = d.isoformat()
        if self._settings:
            self._settings.update(hist_base=base, hist_date=on_date)

        def work():
            return self._client.get_rates_on_date(on_date, base)

        def done(data, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            self._last = data
            rates = data.get("rates", {})
            actual_base = data.get("base", base)
            actual_date = data.get("date", on_date)
            self._c_base.set_value(actual_base)
            self._c_date2.set_value(actual_date)
            self._c_cnt.set_value(str(len(rates)))
            self._table.populate(rates, self._names, actual_base)
            self._status(
                f"Historical  •  {actual_base}  •  {actual_date}  •  {len(rates)} pairs",
                "ok",
            )

        self._run(work, done, skeleton=self._skeleton)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Time Series
# ══════════════════════════════════════════════════════════════════════════════


class TimeSeriesTab(BaseTab):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._last: dict = {}
        self._build()

    def _build(self):
        sb = _sidebar(self, "Time Series Chart")
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="x", padx=PAD_MD)

        # Restore persisted values
        s = self._settings
        saved_base = s.get("ts_base", "EUR") if s else "EUR"
        saved_quote = s.get("ts_quote", "USD") if s else "USD"
        saved_start = (
            s.get("ts_start", (date.today() - timedelta(days=365)).isoformat())
            if s
            else (date.today() - timedelta(days=365)).isoformat()
        )
        saved_end = (
            s.get("ts_end", date.today().isoformat()) if s else date.today().isoformat()
        )

        pair = ctk.CTkFrame(inner, fg_color="transparent")
        pair.pack(fill="x")
        left = ctk.CTkFrame(pair, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        self._base_e = _code_entry(left, "Base", saved_base, self._codes)
        self._quote_e = _code_entry(left, "Quote", saved_quote, self._codes)
        ctk.CTkButton(
            pair,
            text="⇅",
            width=28,
            height=72,
            fg_color=BG_INPUT,
            hover_color=BG_HOVER,
            text_color=ACCENT_GOLD,
            font=("Georgia", 16),
            command=self._swap,
        ).pack(side="left", padx=(4, 0), pady=(14, PAD_SM))
        self._start_e = _date_entry(inner, "Start", saved_start)
        self._end_e = _date_entry(inner, "End", saved_end)

        ctk.CTkLabel(
            inner, text="Group By", font=FONT_LABEL, text_color=TEXT_MUTED
        ).pack(anchor="w")
        self._group = ctk.StringVar(value="None")
        ctk.CTkSegmentedButton(
            inner,
            values=["None", "Weekly", "Monthly"],
            variable=self._group,
            font=FONT_SMALL,
            fg_color=BG_INPUT,
            selected_color=ACCENT_GOLD,
            selected_hover_color="#B8960C",
            unselected_color=BG_INPUT,
            unselected_hover_color=BG_HOVER,
            text_color=TEXT_PRIMARY,
        ).pack(fill="x", pady=(0, PAD_SM))

        # % change toggle
        HSeparator(inner).pack(fill="x", pady=PAD_SM)
        self._pct_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            inner,
            text="% Change from Start",
            variable=self._pct_var,
            font=FONT_SMALL,
            text_color=TEXT_PRIMARY,
            fg_color=ACCENT_GOLD,
            hover_color=ACCENT_GOLD,
            checkmark_color=BG_DARK,
            command=self._on_pct_toggle,
        ).pack(anchor="w", pady=(0, PAD_SM))

        _btn(inner, "📈  Fetch & Plot", self._fetch).pack(fill="x", pady=PAD_MD)

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        ctk.CTkLabel(
            sb, text="Quick Ranges", font=FONT_LABEL, text_color=TEXT_MUTED
        ).pack(padx=PAD_MD, anchor="w")
        _chip_grid(
            sb,
            [
                (lbl, lambda d=days: self._quick(d))
                for lbl, days in [
                    ("1M", 30),
                    ("3M", 90),
                    ("6M", 180),
                    ("1Y", 365),
                    ("3Y", 1095),
                    ("5Y", 1826),
                    ("10Y", 3652),
                    ("20Y", 7305),
                ]
            ],
            cols=4,
        ).pack(fill="x", padx=PAD_MD, pady=(2, 0))

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _btn(
            sb,
            "⬇  CSV",
            lambda: self._export_csv_data(self._last, "timeseries"),
            accent=False,
        ).pack(padx=PAD_MD, pady=2, fill="x")
        _btn(
            sb,
            "⬇  JSON",
            lambda: self._export_json_data(self._last, "timeseries"),
            accent=False,
        ).pack(padx=PAD_MD, pady=2, fill="x")

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True)

        self._chart = ChartPanel(main)
        self._chart.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        self._skeleton = SkeletonFrame(main)

    def _on_pct_toggle(self):
        self._chart.set_pct_mode(self._pct_var.get())

    def _swap(self):
        b, q = self._base_e.get(), self._quote_e.get()
        self._base_e.set(q)
        self._quote_e.set(b)
        if self._last:
            self._fetch()

    def _quick(self, days):
        end = date.today()
        start = end - timedelta(days=days)
        self._start_e.delete(0, "end")
        self._start_e.insert(0, start.isoformat())
        self._end_e.delete(0, "end")
        self._end_e.insert(0, end.isoformat())
        self._fetch()

    def _fetch(self):
        base = _code(self._base_e, "EUR")
        quote = _code(self._quote_e, "USD")
        start, end, problem = _validate_range(self._start_e, self._end_e)
        if problem:
            self._status(problem, "error")
            return
        if not self._check_codes(base, quote):
            return
        if base == quote:
            self._status("Base and quote must be different currencies", "error")
            return
        group = {"Weekly": "week", "Monthly": "month"}.get(self._group.get())

        if self._settings:
            self._settings.update(
                ts_base=base, ts_quote=quote, ts_start=start, ts_end=end
            )

        def work():
            return self._client.get_time_series(start, end, base, [quote], group)

        def done(data, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            self._last = data
            self._chart.set_pct_mode(self._pct_var.get())
            self._chart.plot_series(data, base, quote)
            n = len(data.get("rates", {}))
            self._status(
                f"{base}/{quote}  •  {n} data points  •  {start} → {end}", "ok"
            )

        self._run(work, done, skeleton=self._skeleton)


# ══════════════════════════════════════════════════════════════════════════════
# 4. Converter
# ══════════════════════════════════════════════════════════════════════════════


class ConverterTab(BaseTab):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._last_result_text: str = "—"
        # (base, quote, requested_date, rate, rate_date) of the last fetch —
        # lets the amount / direction update instantly without a network call
        self._last_rate: tuple | None = None
        self._build()

    def _build(self):
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(expand=True, fill="both", padx=60, pady=30)

        ctk.CTkLabel(
            outer, text="Currency Converter", font=FONT_DISPLAY, text_color=ACCENT_GOLD
        ).pack(pady=(0, PAD_LG))

        card = ctk.CTkFrame(
            outer,
            fg_color=BG_CARD,
            corner_radius=CORNER_RADIUS,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        card.pack(fill="x")

        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=PAD_LG, pady=PAD_LG)

        ctk.CTkLabel(
            row1,
            text="Amount",
            font=FONT_LABEL,
            text_color=TEXT_MUTED,
            width=60,
            anchor="w",
        ).pack(side="left")
        self._amt = ctk.CTkEntry(
            row1,
            placeholder_text="1000.00",
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_MONO_LG,
            height=44,
            width=180,
        )
        self._amt.insert(0, "1000")
        self._amt.pack(side="left", padx=PAD_MD)
        self._amt.bind("<KeyRelease>", lambda e: self._live_update())

        # Restore saved currencies
        s = self._settings
        saved_from = s.get("conv_from", "EUR") if s else "EUR"
        saved_to = s.get("conv_to", "USD") if s else "USD"

        self._from = LabelledCombo(
            row1, "From", self._codes, width=200, command=lambda _: self._reconvert()
        )
        self._from.set(saved_from)
        self._from.pack(side="left", padx=PAD_MD)
        ctk.CTkButton(
            row1,
            text="⇄",
            width=40,
            height=44,
            fg_color=BG_INPUT,
            hover_color=BG_HOVER,
            text_color=ACCENT_GOLD,
            font=("Georgia", 18),
            command=self._swap,
        ).pack(side="left", padx=PAD_SM)
        self._to = LabelledCombo(
            row1, "To", self._codes, width=200, command=lambda _: self._reconvert()
        )
        self._to.set(saved_to)
        self._to.pack(side="left", padx=PAD_MD)
        _btn(row1, "Convert", self._convert).pack(side="left", padx=PAD_MD)

        # Direction toggle (reverse mode)
        row_dir = ctk.CTkFrame(card, fg_color="transparent")
        row_dir.pack(fill="x", padx=PAD_LG, pady=(0, PAD_SM))
        ctk.CTkLabel(
            row_dir, text="Direction:", font=FONT_SMALL, text_color=TEXT_MUTED
        ).pack(side="left")
        self._dir_var = ctk.StringVar(value="fwd")
        ctk.CTkRadioButton(
            row_dir,
            text="Base → Quote",
            variable=self._dir_var,
            value="fwd",
            font=FONT_SMALL,
            text_color=TEXT_PRIMARY,
            fg_color=ACCENT_GOLD,
            command=self._live_update,
        ).pack(side="left", padx=(PAD_MD, PAD_SM))
        ctk.CTkRadioButton(
            row_dir,
            text="Quote → Base  (reverse)",
            variable=self._dir_var,
            value="rev",
            font=FONT_SMALL,
            text_color=TEXT_PRIMARY,
            fg_color=ACCENT_GOLD,
            command=self._live_update,
        ).pack(side="left", padx=PAD_SM)

        # optional historical date
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=PAD_LG, pady=(0, PAD_MD))
        ctk.CTkLabel(
            row2,
            text="Date (leave blank for latest):",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
        ).pack(side="left")
        self._date_e = DateEntry(row2, width=140)
        self._date_e.pack(side="left", padx=PAD_MD)
        ctk.CTkButton(
            row2,
            text="Latest",
            width=60,
            height=28,
            fg_color=BG_INPUT,
            hover_color=BG_HOVER,
            text_color=TEXT_MUTED,
            font=FONT_SMALL,
            command=lambda: (self._date_e.set(""), self._reconvert()),
        ).pack(side="left")

        HSeparator(card).pack(fill="x", padx=PAD_LG)

        res_f = ctk.CTkFrame(card, fg_color="transparent")
        res_f.pack(fill="x", padx=PAD_LG, pady=PAD_LG)
        self._res = ctk.CTkLabel(
            res_f, text="—", font=("Georgia", 32, "bold"), text_color=ACCENT_GOLD
        )
        self._res.pack()
        self._detail = ctk.CTkLabel(
            res_f, text="", font=FONT_MONO, text_color=TEXT_MUTED
        )
        self._detail.pack(pady=(4, 0))

        # Copy to clipboard button
        copy_row = ctk.CTkFrame(res_f, fg_color="transparent")
        copy_row.pack(pady=(PAD_SM, 0))
        self._copy_btn = ctk.CTkButton(
            copy_row,
            text="📋  Copy Result",
            width=140,
            height=28,
            fg_color=BG_INPUT,
            hover_color=BG_HOVER,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_PRIMARY,
            font=FONT_SMALL,
            command=self._copy_to_clipboard,
        )
        self._copy_btn.pack()

        HSeparator(outer).pack(fill="x", pady=PAD_MD)
        SectionHeader(outer, "Conversion History").pack(anchor="w", pady=(0, PAD_SM))
        self._hist = ctk.CTkTextbox(
            outer,
            fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            font=FONT_MONO,
            height=180,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=CORNER_RADIUS,
        )
        self._hist.pack(fill="both", expand=True)
        self._hist.configure(state="disabled")
        _btn(outer, "🗑  Clear History", self._clear_hist, accent=False).pack(
            anchor="e", pady=PAD_SM
        )

    # Enter key / F5 dispatch from App
    def _fetch(self):
        self._convert()

    def _swap(self):
        f, t = self._from.get(), self._to.get()
        self._from.set(t)
        self._to.set(f)
        self._reconvert()

    def _reconvert(self):
        """Re-run the conversion if one has already been shown."""
        if self._last_rate is not None:
            self._convert()

    @staticmethod
    def _parse_amount(text):
        """Accept '1,000.50', '1 000', '1_000' and the like."""
        cleaned = text.replace(",", "").replace("_", "").replace(" ", "").strip()
        amount = float(cleaned)
        if not math.isfinite(amount):
            raise ValueError("non-finite")
        return amount

    def _live_update(self):
        """Recompute from the cached rate as the user types — no network."""
        if self._last_rate is None:
            return
        base, quote, req_date, rate, rate_date = self._last_rate
        if (
            _code(self._from, "EUR") != base
            or _code(self._to, "USD") != quote
            or (self._date_e.get().strip() or None) != req_date
        ):
            return
        try:
            amount = self._parse_amount(self._amt.get())
        except (ValueError, TypeError):
            self._amt.configure(border_color=ACCENT_RED)
            return
        self._amt.configure(border_color=BORDER_COLOR)
        self._show_result(amount, base, quote, rate, rate_date, log=False)

    def _clear_hist(self):
        self._hist.configure(state="normal")
        self._hist.delete("1.0", "end")
        self._hist.configure(state="disabled")

    def _copy_to_clipboard(self):
        text = self._last_result_text
        if text and text != "—":
            try:
                root = self.winfo_toplevel()
                root.clipboard_clear()
                root.clipboard_append(text)
                self._copy_btn.configure(text="✓  Copied!")
                self.after(
                    1500, lambda: self._copy_btn.configure(text="📋  Copy Result")
                )
                self._status("Result copied to clipboard", "ok")
            except Exception as e:
                self._status(f"Copy failed: {e}", "error")

    def _convert(self):
        try:
            amount = self._parse_amount(self._amt.get())
        except (ValueError, TypeError):
            self._amt.configure(border_color=ACCENT_RED)
            self._status("Invalid amount", "error")
            return
        self._amt.configure(border_color=BORDER_COLOR)

        base = _code(self._from, "EUR")
        quote = _code(self._to, "USD")
        on_date = self._date_e.get().strip() or None
        if on_date is not None:
            d = _parse_date(on_date)
            bad = d is None or d > date.today() or d < MIN_DATE
            self._date_e.flag_error(bad)
            if bad:
                self._status("Date must be YYYY-MM-DD, between 1948 and today", "error")
                return
        else:
            self._date_e.flag_error(False)
        if not self._check_codes(base, quote):
            return

        # Persist selections
        if self._settings:
            self._settings.update(conv_from=base, conv_to=quote)

        def work():
            # Always fetch the base→quote rate; reverse logic is applied client-side
            return self._client.get_single_rate(base, quote, on_date)

        def done(data, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            rate = data.get("rate", 0)
            if not rate:
                self._status("Received zero or missing rate", "error")
                return
            rate = float(rate)
            rate_date = data.get("date") or on_date or "latest"
            self._last_rate = (base, quote, on_date, rate, rate_date)
            # The amount may have changed while the request was in flight
            try:
                amt = self._parse_amount(self._amt.get())
            except (ValueError, TypeError):
                amt = amount
            self._show_result(amt, base, quote, rate, rate_date, log=True)

        self._run(work, done)

    def _show_result(self, amount, base, quote, rate, rate_date, log=True):
        reverse = self._dir_var.get() == "rev"
        if reverse:
            # amount is in *quote* currency; convert back to base
            converted = amount / rate
            log_from, log_to = quote, base
        else:
            converted = amount * rate
            log_from, log_to = base, quote
        result_text = f"{amount:,.2f} {log_from}  =  {converted:,.4f} {log_to}"

        self._last_result_text = result_text
        self._res.configure(text=result_text)
        self._detail.configure(
            text=f"1 {base} = {rate:.6f} {quote}  •  1 {quote} = {1 / rate:.6f} {base}  •  Date: {rate_date}"
        )
        if not log:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}]  {amount:,.2f} {log_from} → {converted:,.4f} {log_to}  @ {rate:.6f}  ({rate_date})\n"
        self._hist.configure(state="normal")
        self._hist.insert("end", line)
        self._hist.see("end")
        self._hist.configure(state="disabled")
        self._status(f"Converted  {amount:,.2f} {log_from} → {log_to}", "ok")


# ══════════════════════════════════════════════════════════════════════════════
# 5. Multi-currency Compare
# ══════════════════════════════════════════════════════════════════════════════


class CompareTab(BaseTab):
    MAX_SERIES = 8

    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._last: dict = {}
        self._build()

    def _build(self):
        sb = _sidebar(self, "Multi-Currency Compare")
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="x", padx=PAD_MD)

        s = self._settings
        saved_base = s.get("cmp_base", "EUR") if s else "EUR"
        saved_start = (
            s.get("cmp_start", (date.today() - timedelta(days=365)).isoformat())
            if s
            else (date.today() - timedelta(days=365)).isoformat()
        )
        saved_end = (
            s.get("cmp_end", date.today().isoformat())
            if s
            else date.today().isoformat()
        )

        self._base_e = _code_entry(inner, "Base", saved_base, self._codes)
        self._start_e = _date_entry(inner, "Start", saved_start)
        self._end_e = _date_entry(inner, "End", saved_end)

        # Rates of e.g. JPY (~160) and GBP (~0.85) can't share an absolute
        # axis meaningfully, so normalising to % change is on by default.
        self._pct_var = ctk.BooleanVar(value=s.get("cmp_pct", True) if s else True)
        ctk.CTkCheckBox(
            inner,
            text="Normalise (% change from start)",
            variable=self._pct_var,
            font=FONT_SMALL,
            text_color=TEXT_PRIMARY,
            fg_color=ACCENT_GOLD,
            hover_color=ACCENT_GOLD,
            checkmark_color=BG_DARK,
            command=self._on_pct_toggle,
        ).pack(anchor="w", pady=(0, PAD_SM))

        hdr = ctk.CTkFrame(inner, fg_color="transparent")
        hdr.pack(fill="x", pady=(PAD_SM, 2))
        self._sel_lbl = ctk.CTkLabel(
            hdr,
            text=f"Select Currencies (up to {self.MAX_SERIES})",
            font=FONT_LABEL,
            text_color=TEXT_MUTED,
        )
        self._sel_lbl.pack(side="left")
        ctk.CTkButton(
            hdr,
            text="Clear",
            width=44,
            height=20,
            fg_color=BG_INPUT,
            hover_color=BG_HOVER,
            text_color=TEXT_MUTED,
            font=FONT_SMALL,
            command=self._clear_checks,
        ).pack(side="right")

        self._search_c = SearchEntry(
            inner, "Filter currencies…", on_change=self._filter_checks
        )
        self._search_c.pack(fill="x", pady=(0, PAD_SM))

        self._scroll = ctk.CTkScrollableFrame(
            inner, height=200, fg_color=BG_INPUT, corner_radius=CORNER_RADIUS
        )
        self._scroll.pack(fill="x")
        self._check_vars: dict[str, ctk.BooleanVar] = {}
        self._check_widgets: dict[str, ctk.CTkCheckBox] = {}
        saved_sel = s.get("cmp_quotes") if s else None
        defaults = set(
            saved_sel or ["USD", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR"]
        )
        for code in self._codes:
            var = ctk.BooleanVar(value=code in defaults)
            self._check_vars[code] = var
            cb = ctk.CTkCheckBox(
                self._scroll,
                text=f"{code}  {self._names.get(code, code)}",
                variable=var,
                font=FONT_SMALL,
                text_color=TEXT_PRIMARY,
                fg_color=ACCENT_GOLD,
                hover_color=ACCENT_GOLD,
                checkmark_color=BG_DARK,
                command=self._update_sel_count,
            )
            cb.pack(anchor="w", pady=1)
            self._check_widgets[code] = cb
        self._update_sel_count()

        _btn(inner, "📊  Compare", self._fetch).pack(fill="x", pady=PAD_MD)

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _quick_range_row(sb, self._start_e, self._end_e, self._fetch)

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _btn(
            sb,
            "⬇  CSV",
            lambda: self._export_csv_data(self._last, "compare"),
            accent=False,
        ).pack(padx=PAD_MD, pady=2, fill="x")
        _btn(
            sb,
            "⬇  JSON",
            lambda: self._export_json_data(self._last, "compare"),
            accent=False,
        ).pack(padx=PAD_MD, pady=2, fill="x")

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True)
        self._chart = ChartPanel(main, show_types=False)
        self._chart.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        self._chart.set_pct_mode(self._pct_var.get())
        self._skeleton = SkeletonFrame(main)

    def _selected(self):
        return [c for c, v in self._check_vars.items() if v.get()]

    def _update_sel_count(self):
        n = len(self._selected())
        over = n > self.MAX_SERIES
        self._sel_lbl.configure(
            text=f"Selected {n} / {self.MAX_SERIES}",
            text_color=ACCENT_RED if over else TEXT_MUTED,
        )

    def _clear_checks(self):
        for v in self._check_vars.values():
            v.set(False)
        self._update_sel_count()

    def _on_pct_toggle(self):
        self._chart.set_pct_mode(self._pct_var.get())
        if self._settings:
            self._settings.set("cmp_pct", self._pct_var.get())

    def _filter_checks(self, text):
        text = text.upper()
        # Forget everything, then re-pack matches in the original order —
        # re-packing only the matches appended them at the end and scrambled
        # the alphabetical list after a few searches.
        for widget in self._check_widgets.values():
            widget.pack_forget()
        for code, widget in self._check_widgets.items():
            if not text or text in code or text in self._names.get(code, "").upper():
                widget.pack(anchor="w", pady=1)

    def _fetch(self):
        base = _code(self._base_e, "EUR")
        start, end, problem = _validate_range(self._start_e, self._end_e)
        if problem:
            self._status(problem, "error")
            return
        if not self._check_codes(base):
            return
        selected = [c for c in self._selected() if c != base]
        if not selected:
            self._status("Select at least one currency (other than the base)", "error")
            return
        quotes = selected[: self.MAX_SERIES]

        if self._settings:
            self._settings.update(
                cmp_base=base, cmp_start=start, cmp_end=end, cmp_quotes=quotes
            )

        def work():
            # One request for all quotes instead of one request per quote
            return self._client.get_time_series(start, end, base, quotes)

        def done(data, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            self._last = data
            rates = data.get("rates", {})
            datasets = {
                q: {"rates": {d: {q: day[q]} for d, day in rates.items() if q in day}}
                for q in quotes
            }
            self._chart.plot_multi(datasets, base)
            msg = f"Comparing {len(quotes)} currencies vs {base}"
            if len(selected) > self.MAX_SERIES:
                msg += f"  •  only the first {self.MAX_SERIES} selected are shown"
            self._status(msg, "ok")

        self._run(work, done, skeleton=self._skeleton)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Statistics
# ══════════════════════════════════════════════════════════════════════════════


class StatsTab(BaseTab):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._build()

    def _build(self):
        sb = _sidebar(self, "Statistics")
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="x", padx=PAD_MD)

        s = self._settings
        saved_base = s.get("stats_base", "EUR") if s else "EUR"
        saved_quote = s.get("stats_quote", "USD") if s else "USD"
        saved_start = (
            s.get("stats_start", (date.today() - timedelta(days=365)).isoformat())
            if s
            else (date.today() - timedelta(days=365)).isoformat()
        )
        saved_end = (
            s.get("stats_end", date.today().isoformat())
            if s
            else date.today().isoformat()
        )

        self._base_e = _code_entry(inner, "Base", saved_base, self._codes)
        self._quote_e = _code_entry(inner, "Quote", saved_quote, self._codes)
        self._start_e = _date_entry(inner, "Start", saved_start)
        self._end_e = _date_entry(inner, "End", saved_end)
        _btn(inner, "📐  Analyse", self._fetch).pack(fill="x", pady=PAD_MD)

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _quick_range_row(sb, self._start_e, self._end_e, self._fetch)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=PAD_LG, pady=PAD_LG)
        SectionHeader(main, "Statistical Summary").pack(anchor="w", pady=(0, PAD_MD))

        grid = ctk.CTkFrame(main, fg_color="transparent")
        grid.pack(fill="x")
        specs = [
            ("min", "Minimum", ACCENT_RED),
            ("max", "Maximum", ACCENT_GREEN),
            ("mean", "Mean", ACCENT_GOLD),
            ("stdev", "Std Deviation", ACCENT_BLUE),
            ("count", "Data Points", TEXT_PRIMARY),
            ("change_pct", "Period Change %", ACCENT_GOLD),
            ("avg_daily_pct_change", "Avg Daily %", ACCENT_PURPLE),
            ("max_drawdown", "Max Drawdown %", ACCENT_RED),
            ("first", "First Rate", TEXT_MUTED),
            ("last", "Last Rate", TEXT_MUTED),
            ("volatility_ann", "Volatility (ann.)", ACCENT_ORANGE),
            ("range_pct", "High–Low Range %", ACCENT_CYAN),
            ("best_day", "Best Day %", ACCENT_GREEN),
            ("worst_day", "Worst Day %", ACCENT_RED),
        ]
        cols = 7
        self._cards: dict[str, StatCard] = {}
        for i, (key, lbl, col) in enumerate(specs):
            c = StatCard(grid, lbl, color=col)
            c.grid(
                row=i // cols, column=i % cols, sticky="nsew", padx=PAD_SM, pady=PAD_SM
            )
            self._cards[key] = c
        for col in range(cols):
            grid.grid_columnconfigure(col, weight=1, uniform="stat")

        HSeparator(main).pack(fill="x", pady=PAD_MD)
        SectionHeader(main, "Rate Chart").pack(anchor="w", pady=(0, PAD_SM))

        chart_wrap = ctk.CTkFrame(main, fg_color="transparent")
        chart_wrap.pack(fill="both", expand=True)
        self._chart = ChartPanel(chart_wrap)
        self._chart.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(chart_wrap)

    def _fetch(self):
        base = _code(self._base_e, "EUR")
        quote = _code(self._quote_e, "USD")
        start, end, problem = _validate_range(self._start_e, self._end_e)
        if problem:
            self._status(problem, "error")
            return
        if not self._check_codes(base, quote):
            return
        if base == quote:
            self._status("Base and quote must be different currencies", "error")
            return

        if self._settings:
            self._settings.update(
                stats_base=base, stats_quote=quote, stats_start=start, stats_end=end
            )

        def work():
            stats = self._client.get_volatility_stats(base, quote, start, end)
            series = self._client.get_time_series(start, end, base, [quote])
            return stats, series

        def done(result, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            stats, series = result
            if not stats:
                for card in self._cards.values():
                    card.set_value("—")
                self._chart.plot_series(series, base, quote)
                self._status(f"No data for {base}/{quote} in that range", "error")
                return
            chg = stats.get("change_pct", 0)
            dd = stats.get("max_drawdown", 0)
            fmts = {
                "min": f"{stats.get('min', 0):.6f}",
                "max": f"{stats.get('max', 0):.6f}",
                "mean": f"{stats.get('mean', 0):.6f}",
                "stdev": f"{stats.get('stdev', 0):.6f}",
                "count": str(stats.get("count", 0)),
                "change_pct": f"{chg:+.4f}%",
                "avg_daily_pct_change": f"{stats.get('avg_daily_pct_change', 0):+.4f}%",
                "max_drawdown": f"{dd:.4f}%",
                "first": f"{stats.get('first', 0):.6f}",
                "last": f"{stats.get('last', 0):.6f}",
                "volatility_ann": f"{stats.get('volatility_ann', 0):.2f}%",
                "range_pct": f"{stats.get('range_pct', 0):.2f}%",
                "best_day": f"{stats.get('best_day', 0):+.3f}%",
                "worst_day": f"{stats.get('worst_day', 0):+.3f}%",
            }
            for key, val in fmts.items():
                color = None
                if key == "change_pct":
                    color = ACCENT_GREEN if chg >= 0 else ACCENT_RED
                elif key == "max_drawdown":
                    color = ACCENT_RED if dd > 5 else ACCENT_GREEN
                self._cards[key].set_value(val, color)
            self._chart.plot_series(series, base, quote)
            self._status(f"Statistics  {base}/{quote}  ({start} → {end})", "ok")

        self._run(work, done, skeleton=self._skeleton)


# ══════════════════════════════════════════════════════════════════════════════
# 7. Year Heatmap
# ══════════════════════════════════════════════════════════════════════════════


class HeatmapTab(BaseTab):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._last_data: dict[int, float] = {}
        self._last_base = "EUR"
        self._last_quote = "USD"
        self._build()

    def _build(self):
        sb = _sidebar(self, "Annual Heatmap")
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="x", padx=PAD_MD)
        s = self._settings
        self._base_e = _code_entry(
            inner, "Base", s.get("heat_base", "EUR") if s else "EUR", self._codes
        )
        self._quote_e = _code_entry(
            inner, "Quote", s.get("heat_quote", "USD") if s else "USD", self._codes
        )
        yrs = ctk.CTkFrame(inner, fg_color="transparent")
        yrs.pack(fill="x")
        yrs.grid_columnconfigure((0, 1), weight=1)
        self._start_yr = self._year_entry(yrs, "Start Year", "2000", 0)
        self._end_yr = self._year_entry(yrs, "End Year", str(date.today().year), 1)
        _btn(inner, "🔥  Generate Heatmap", self._fetch).pack(fill="x", pady=PAD_MD)

        ctk.CTkLabel(
            sb,
            text="Shows the close-to-close % change\nfor each year (current year = YTD).",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
            wraplength=200,
            justify="left",
        ).pack(padx=PAD_MD)

        # Export buttons
        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _btn(sb, "⬇  CSV", self._do_csv, accent=False).pack(
            padx=PAD_MD, pady=2, fill="x"
        )
        _btn(sb, "⬇  JSON", self._do_json, accent=False).pack(
            padx=PAD_MD, pady=2, fill="x"
        )

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True)

        # Cards are packed first (at the bottom) so the expanding chart can
        # never squeeze them out of view on smaller windows.
        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.pack(side="bottom", fill="x", padx=PAD_MD - PAD_SM, pady=(0, PAD_MD))

        chart_wrap = ctk.CTkFrame(main, fg_color="transparent")
        chart_wrap.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        self._chart = ChartPanel(chart_wrap, show_types=False)
        self._chart.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(chart_wrap)
        self._c_best = StatCard(cards, "Best Year", color=ACCENT_GREEN)
        self._c_worst = StatCard(cards, "Worst Year", color=ACCENT_RED)
        self._c_avg = StatCard(cards, "Average / Year", color=ACCENT_GOLD)
        self._c_up = StatCard(cards, "Up Years", color=ACCENT_BLUE)
        for c in (self._c_best, self._c_worst, self._c_avg, self._c_up):
            c.pack(side="left", expand=True, fill="both", padx=PAD_SM)

    @staticmethod
    def _year_entry(parent, label, default, col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, sticky="ew", padx=(0, 2) if col == 0 else (2, 0))
        ctk.CTkLabel(f, text=label, font=FONT_LABEL, text_color=TEXT_MUTED).pack(
            anchor="w"
        )
        e = ctk.CTkEntry(
            f,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_MONO,
            height=32,
            width=60,
        )
        e.insert(0, default)
        e.pack(fill="x", pady=(0, PAD_SM))
        return e

    def _do_csv(self):
        if not self._last_data:
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=default_filename("heatmap", "csv"),
        )
        if p:
            import csv as _csv

            with open(p, "w", newline="", encoding="utf-8") as f:
                w = _csv.DictWriter(
                    f, fieldnames=["year", "base", "quote", "pct_change"]
                )
                w.writeheader()
                for yr, chg in sorted(self._last_data.items()):
                    w.writerow(
                        {
                            "year": yr,
                            "base": self._last_base,
                            "quote": self._last_quote,
                            "pct_change": round(chg, 6),
                        }
                    )
            self._status(f"Exported → {p}", "ok")

    def _do_json(self):
        if not self._last_data:
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=default_filename("heatmap", "json"),
        )
        if p:
            payload = {
                "base": self._last_base,
                "quote": self._last_quote,
                "annual_changes": {
                    str(yr): chg for yr, chg in sorted(self._last_data.items())
                },
            }
            export_to_json(payload, p)
            self._status(f"Exported → {p}", "ok")

    def _fetch(self):
        base = _code(self._base_e, "EUR")
        quote = _code(self._quote_e, "USD")
        this_year = date.today().year
        try:
            sy = int(self._start_yr.get().strip())
            ey = int(self._end_yr.get().strip())
        except ValueError:
            self._status("Years must be whole numbers, e.g. 2000", "error")
            return
        if sy > ey:
            sy, ey = ey, sy
        sy = max(sy, MIN_DATE.year)
        ey = min(ey, this_year)
        if sy > this_year:
            self._status("Start year is in the future", "error")
            return
        if not self._check_codes(base, quote):
            return
        if base == quote:
            self._status("Base and quote must be different currencies", "error")
            return
        if self._settings:
            self._settings.update(heat_base=base, heat_quote=quote)

        def work():
            return self._client.get_annual_changes(base, quote, sy, ey)

        def done(data, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            self._last_data = data
            self._last_base = base
            self._last_quote = quote
            self._chart.plot_heatmap(data, base, quote)
            if data:
                best = max(data.items(), key=lambda kv: kv[1])
                worst = min(data.items(), key=lambda kv: kv[1])
                avg = sum(data.values()) / len(data)
                ups = sum(1 for v in data.values() if v >= 0)
                self._c_best.set_value(f"{best[0]}  {best[1]:+.2f}%")
                self._c_worst.set_value(f"{worst[0]}  {worst[1]:+.2f}%")
                self._c_avg.set_value(
                    f"{avg:+.2f}%", ACCENT_GREEN if avg >= 0 else ACCENT_RED
                )
                self._c_up.set_value(f"{ups} / {len(data)}")
            else:
                for c in (self._c_best, self._c_worst, self._c_avg, self._c_up):
                    c.set_value("—")
            self._status(f"Annual heatmap  {base}/{quote}  {sy}–{ey}", "ok")

        self._run(work, done, skeleton=self._skeleton)


# ══════════════════════════════════════════════════════════════════════════════
# 8. Cross-Rate Matrix
# ══════════════════════════════════════════════════════════════════════════════


class MatrixTab(BaseTab):
    MAX_CODES = 10

    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._last_matrix: dict = {}
        self._last_codes: list[str] = []
        self._build()

    def _build(self):
        sb = _sidebar(self, "Cross-Rate Matrix")
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="x", padx=PAD_MD)
        self._sel_lbl = ctk.CTkLabel(
            inner,
            text=f"Select Currencies (2–{self.MAX_CODES})",
            font=FONT_LABEL,
            text_color=TEXT_MUTED,
        )
        self._sel_lbl.pack(anchor="w")
        SearchEntry(inner, "Filter currencies…", on_change=self._filter_checks).pack(
            fill="x", pady=(0, PAD_SM)
        )

        self._scroll = ctk.CTkScrollableFrame(
            inner, height=240, fg_color=BG_INPUT, corner_radius=CORNER_RADIUS
        )
        self._scroll.pack(fill="x")
        self._check_vars: dict[str, ctk.BooleanVar] = {}
        self._check_widgets: dict[str, ctk.CTkCheckBox] = {}
        s = self._settings
        defaults = set(
            (s.get("matrix_codes") if s else None)
            or ["EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY"]
        )
        for code in self._codes:
            var = ctk.BooleanVar(value=code in defaults)
            self._check_vars[code] = var
            cb = ctk.CTkCheckBox(
                self._scroll,
                text=f"{code}  {self._names.get(code, code)}",
                variable=var,
                font=FONT_SMALL,
                text_color=TEXT_PRIMARY,
                fg_color=ACCENT_GOLD,
                hover_color=ACCENT_GOLD,
                checkmark_color=BG_DARK,
                command=self._update_sel_count,
            )
            cb.pack(anchor="w", pady=1)
            self._check_widgets[code] = cb
        self._update_sel_count()

        _btn(inner, "🔢  Build Matrix", self._fetch).pack(fill="x", pady=PAD_MD)
        ctk.CTkLabel(
            sb,
            text="Each cell shows the rate:\nRow currency → Column currency",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
            wraplength=200,
            justify="left",
        ).pack(padx=PAD_MD)

        # Export buttons
        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _btn(sb, "⬇  CSV", self._do_csv, accent=False).pack(
            padx=PAD_MD, pady=2, fill="x"
        )
        _btn(sb, "⬇  JSON", self._do_json, accent=False).pack(
            padx=PAD_MD, pady=2, fill="x"
        )

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True)

        chart_wrap = ctk.CTkFrame(main, fg_color="transparent")
        chart_wrap.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        self._chart = ChartPanel(chart_wrap, show_types=False)
        self._chart.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(chart_wrap)

        self._table_frame = ctk.CTkScrollableFrame(
            main, height=200, fg_color=BG_CARD, orientation="vertical"
        )
        self._table_frame.pack(fill="x", padx=PAD_MD, pady=(0, PAD_MD))

    def _selected(self):
        return [c for c, v in self._check_vars.items() if v.get()]

    def _update_sel_count(self):
        n = len(self._selected())
        self._sel_lbl.configure(
            text=f"Selected {n}  (2–{self.MAX_CODES})",
            text_color=ACCENT_RED if n > self.MAX_CODES or n < 2 else TEXT_MUTED,
        )

    def _filter_checks(self, text):
        text = text.upper()
        for widget in self._check_widgets.values():
            widget.pack_forget()
        for code, widget in self._check_widgets.items():
            if not text or text in code or text in self._names.get(code, "").upper():
                widget.pack(anchor="w", pady=1)

    def _do_csv(self):
        if not self._last_matrix or not self._last_codes:
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=default_filename("matrix", "csv"),
        )
        if p:
            import csv as _csv

            with open(p, "w", newline="", encoding="utf-8") as f:
                w = _csv.DictWriter(f, fieldnames=["base", "quote", "rate"])
                w.writeheader()
                for b in self._last_codes:
                    for q in self._last_codes:
                        val = self._last_matrix.get(b, {}).get(q)
                        w.writerow(
                            {
                                "base": b,
                                "quote": q,
                                "rate": val if val is not None else "",
                            }
                        )
            self._status(f"Exported → {p}", "ok")

    def _do_json(self):
        if not self._last_matrix:
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=default_filename("matrix", "json"),
        )
        if p:
            export_to_json({"codes": self._last_codes, "matrix": self._last_matrix}, p)
            self._status(f"Exported → {p}", "ok")

    def _fetch(self):
        selected = self._selected()
        codes = selected[: self.MAX_CODES]
        if len(codes) < 2:
            self._status("Select at least 2 currencies", "error")
            return
        if self._settings:
            self._settings.set("matrix_codes", codes)

        def work():
            return self._client.get_cross_rate_matrix(codes)

        def done(matrix, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            self._last_matrix = matrix
            self._last_codes = codes
            self._chart.plot_matrix_heatmap(matrix, codes)
            for w in self._table_frame.winfo_children():
                w.destroy()
            # header row
            ctk.CTkLabel(
                self._table_frame,
                text="",
                width=50,
                font=FONT_SMALL,
                text_color=TEXT_DIM,
            ).grid(row=0, column=0, padx=2)
            for j, q in enumerate(codes):
                ctk.CTkLabel(
                    self._table_frame,
                    text=q,
                    width=70,
                    font=FONT_SUBHEAD,
                    text_color=ACCENT_GOLD,
                ).grid(row=0, column=j + 1, padx=2)
            for i, base in enumerate(codes):
                ctk.CTkLabel(
                    self._table_frame,
                    text=base,
                    width=50,
                    font=FONT_SUBHEAD,
                    text_color=ACCENT_GOLD,
                ).grid(row=i + 1, column=0, padx=2)
                for j, q in enumerate(codes):
                    val = matrix.get(base, {}).get(q)
                    txt = f"{val:.4f}" if val is not None else "—"
                    col = ACCENT_GOLD if base == q else TEXT_PRIMARY
                    ctk.CTkLabel(
                        self._table_frame,
                        text=txt,
                        width=70,
                        font=FONT_MONO,
                        text_color=col,
                    ).grid(row=i + 1, column=j + 1, padx=2, pady=1)
            msg = f"Cross-rate matrix for {len(codes)} currencies"
            if len(selected) > self.MAX_CODES:
                msg += f"  •  only the first {self.MAX_CODES} selected are used"
            self._status(msg, "ok")

        self._run(work, done, skeleton=self._skeleton)


# ══════════════════════════════════════════════════════════════════════════════
# 9. Watchlist
# ══════════════════════════════════════════════════════════════════════════════


class WatchlistTab(BaseTab):
    # Legacy location (current working directory) — read once for migration
    SAVE_FILE = "watchlist.json"
    DEFAULT_PAIRS = [("EUR", "USD"), ("GBP", "USD"), ("USD", "JPY"), ("EUR", "GBP")]

    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._pairs: list[tuple] = []
        self._selected: tuple[str, str] | None = None
        self._load_saved()
        self._build()

    def _load_saved(self):
        # Prefer settings-based persistence; fall back to watchlist.json for compatibility
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
        # No settings store available — keep the legacy file behaviour
        try:
            with open(self.SAVE_FILE, "w") as f:
                json.dump(self._pairs, f)
        except Exception:
            pass

    def _build(self):
        sb = _sidebar(self, "Watchlist")
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="x", padx=PAD_MD)
        ctk.CTkLabel(
            inner, text="Add Pair", font=FONT_LABEL, text_color=TEXT_MUTED
        ).pack(anchor="w")
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        self._add_base = ctk.CTkEntry(
            row,
            placeholder_text="EUR",
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_MONO,
            width=65,
            height=32,
        )
        self._add_base.pack(side="left")
        ctk.CTkLabel(row, text="/", font=FONT_HEADING, text_color=TEXT_MUTED).pack(
            side="left", padx=4
        )
        self._add_quote = ctk.CTkEntry(
            row,
            placeholder_text="USD",
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_MONO,
            width=65,
            height=32,
        )
        self._add_quote.pack(side="left")
        _btn(row, "+", self._add_pair, accent=True, width=36).pack(
            side="left", padx=PAD_SM
        )

        HSeparator(inner).pack(fill="x", pady=PAD_SM)
        _btn(inner, "⟳  Refresh All", lambda: self._refresh(force=True)).pack(
            fill="x", pady=2
        )
        _btn(inner, "🗑  Clear All", self._clear, accent=False).pack(fill="x", pady=2)

        ctk.CTkLabel(
            sb,
            text="Pairs persist between sessions.\nClick a pair to chart it.\n★ pins it to the top, ✕ removes it.",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
            wraplength=200,
            justify="left",
        ).pack(padx=PAD_MD, pady=PAD_MD, anchor="w")

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=PAD_LG, pady=PAD_LG)

        SectionHeader(main, "Watched Pairs  (click to chart • ★ to pin)").pack(
            anchor="w", pady=(0, PAD_SM)
        )
        self._wl = WatchlistPanel(
            main,
            settings=self._settings,
            on_select=self._plot_pair,
            on_remove=self._remove_pair,
        )
        self._wl.pack(fill="both", expand=False)

        HSeparator(main).pack(fill="x", pady=PAD_MD)
        self._chart_hdr = SectionHeader(main, "1-Year Chart")
        self._chart_hdr.pack(anchor="w", pady=(0, PAD_SM))
        chart_wrap = ctk.CTkFrame(main, fg_color="transparent")
        chart_wrap.pack(fill="both", expand=True)
        self._chart = ChartPanel(chart_wrap)
        self._chart.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(chart_wrap)

        self._refresh()

    # Enter / F5 from App: add the typed pair if any, else refresh
    def _fetch(self):
        if self._add_base.get().strip() or self._add_quote.get().strip():
            self._add_pair()
        else:
            self._refresh(force=True)

    def _add_pair(self):
        b = self._add_base.get().strip().upper()
        q = self._add_quote.get().strip().upper()
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
        self._add_base.delete(0, "end")
        self._add_quote.delete(0, "end")
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
        self._wl.refresh(
            [
                s
                for s in self._wl._last_snaps
                if (s.get("base"), s.get("quote")) != (base, quote)
            ]
        )
        self._status(f"Removed {base}/{quote}", "ok")
        if self._selected is None and self._pairs:
            self._plot_pair(*self._pairs[0])

    def _clear(self):
        if not self._pairs:
            return
        if not messagebox.askyesno(
            "Clear watchlist",
            f"Remove all {len(self._pairs)} pairs from the watchlist?",
            parent=self.winfo_toplevel(),
        ):
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
            self._wl._selected = self._selected
            self._wl.refresh(snaps)
            failed = sum(1 for s in snaps if s.get("error"))
            if failed:
                msg = (
                    f"Watchlist refreshed  •  {len(snaps) - failed} ok, {failed} failed"
                )
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
            self._status(
                msg or f"{base}/{quote}  •  1-year chart",
                "ok" if ok else "error",
            )

        self._run(work, done, skeleton=self._skeleton, channel="chart")


# ══════════════════════════════════════════════════════════════════════════════
# 10. Currency Detail
# ══════════════════════════════════════════════════════════════════════════════


class CurrencyDetailTab(BaseTab):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._build()

    def _build(self):
        sb = _sidebar(self, "Currency Detail")
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="x", padx=PAD_MD)
        ctk.CTkLabel(
            inner, text="Currency Code", font=FONT_LABEL, text_color=TEXT_MUTED
        ).pack(anchor="w")
        self._combo = LabelledCombo(
            inner, "", self._codes, width=210, command=self._on_select
        )
        s = self._settings
        self._combo.set(s.get("detail_code", "EUR") if s else "EUR")
        self._combo.pack(fill="x")
        _btn(inner, "🔍  View Details", self._fetch).pack(fill="x", pady=PAD_MD)
        ctk.CTkLabel(
            sb,
            text="Shows full metadata for a\nsingle currency from\nthe Frankfurter API.",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
            wraplength=200,
            justify="left",
        ).pack(padx=PAD_MD, pady=PAD_MD)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=PAD_LG, pady=PAD_LG)

        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.pack(fill="x", pady=(0, PAD_LG))
        self._c_code = StatCard(cards, "Code")
        self._c_name = StatCard(cards, "Full Name", color=ACCENT_BLUE)
        self._c_prov = StatCard(cards, "Providers", color=ACCENT_GREEN)
        self._c_since = StatCard(cards, "Data Since", color=ACCENT_PURPLE)
        for c in [self._c_code, self._c_name, self._c_prov, self._c_since]:
            c.pack(side="left", expand=True, fill="both", padx=PAD_SM)

        HSeparator(main).pack(fill="x", pady=PAD_MD)
        SectionHeader(main, "Raw Metadata (JSON)").pack(anchor="w", pady=(0, PAD_SM))
        self._raw = ctk.CTkTextbox(
            main,
            fg_color=BG_CARD,
            text_color=ACCENT_GREEN,
            font=FONT_MONO,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=CORNER_RADIUS,
            height=150,
        )
        self._raw.pack(fill="x")
        self._raw.configure(state="disabled")

        HSeparator(main).pack(fill="x", pady=PAD_MD)
        self._chart_hdr = SectionHeader(main, "5-Year Rate Chart vs EUR")
        self._chart_hdr.pack(anchor="w", pady=(0, PAD_SM))
        chart_wrap = ctk.CTkFrame(main, fg_color="transparent")
        chart_wrap.pack(fill="both", expand=True)
        self._chart = ChartPanel(chart_wrap)
        self._chart.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(chart_wrap)

        self._fetch()

    def _on_select(self, _=None):
        # Picking from the dropdown loads the currency straight away
        self._fetch()

    def _fetch(self):
        code = _code(self._combo, "EUR")
        if not self._check_codes(code):
            return
        # Chart EUR/<code>; for the euro itself (EUR/EUR is a flat line) use EUR/USD
        base, quote = ("EUR", "USD") if code == "EUR" else ("EUR", code)
        if self._settings:
            self._settings.set("detail_code", code)

        def work():
            detail = self._client.get_currency_detail(code)
            series = self._client.get_time_series(
                (date.today() - timedelta(days=5 * 365)).isoformat(),
                None,
                base,
                [quote],
            )
            return detail, series

        def done(result, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            detail, series = result
            name = detail.get("name", code)
            providers = detail.get("providers", [])
            n_prov = len(providers) if isinstance(providers, list) else "—"
            start_dt = detail.get("start", "—")
            self._c_code.set_value(code)
            short = name if len(name) <= 22 else name[:21] + "…"
            self._c_name.set_value(short, ACCENT_BLUE)
            self._c_prov.set_value(str(n_prov))
            self._c_since.set_value(start_dt if isinstance(start_dt, str) else "—")
            self._raw.configure(state="normal")
            self._raw.delete("1.0", "end")
            self._raw.insert("1.0", json.dumps(detail, indent=2))
            self._raw.configure(state="disabled")
            self._chart_hdr.set_text(f"5-Year Rate Chart  —  {base}/{quote}")
            self._chart.plot_series(series, base, quote)
            self._status(f"Currency detail  •  {code}  •  {name}", "ok")

        self._run(work, done, skeleton=self._skeleton)


# ══════════════════════════════════════════════════════════════════════════════
# 11. Providers
# ══════════════════════════════════════════════════════════════════════════════


class ProvidersTab(BaseTab):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._build()

    def _build(self):
        sb = _sidebar(self, "Data Providers")
        _btn(sb, "⟳  Load Providers", self._fetch).pack(
            padx=PAD_MD, pady=PAD_MD, fill="x"
        )
        ctk.CTkLabel(
            sb,
            text="Frankfurter sources data\nfrom 84 central banks\nworldwide.",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
            wraplength=200,
            justify="left",
        ).pack(padx=PAD_MD)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=PAD_LG, pady=PAD_LG)

        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.pack(fill="x", pady=(0, PAD_LG))
        self._c_cnt = StatCard(cards, "Total Providers")
        self._c_cnt.pack(side="left", expand=True, fill="both", padx=PAD_SM)
        self._c_ccy = StatCard(cards, "Currencies Covered", color=ACCENT_BLUE)
        self._c_ccy.pack(side="left", expand=True, fill="both", padx=PAD_SM)

        hdr_row = ctk.CTkFrame(main, fg_color="transparent")
        hdr_row.pack(fill="x", pady=(0, PAD_SM))
        SectionHeader(hdr_row, "Provider List").pack(side="left")
        self._search = SearchEntry(
            hdr_row, "Filter by key, name or country…", on_change=self._apply_filter
        )
        self._search.pack(side="right", fill="x", expand=False)
        self._search._entry.configure(width=260)

        self._list = ctk.CTkScrollableFrame(main, fg_color=BG_DARK)
        self._list.pack(fill="both", expand=True)
        self._rows: list = []
        self._row_text: list[str] = []
        self._fetch()

    def _apply_filter(self, text):
        text = text.upper()
        # rows[0] is the header; keep it, then re-pack matches in order
        for row in self._rows[1:]:
            row.pack_forget()
        for row, blob in zip(self._rows[1:], self._row_text):
            if not text or text in blob:
                row.pack(fill="x", pady=1)

    def _fetch(self):
        def work():
            return self._client.get_providers()

        def done(data, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            for w in self._rows:
                w.destroy()
            self._rows.clear()
            self._row_text.clear()
            providers = data if isinstance(data, list) else data.get("providers", [])
            providers = sorted(
                providers,
                key=lambda p: str(p.get("name", "")) if isinstance(p, dict) else str(p),
            )
            self._c_cnt.set_value(str(len(providers)))
            covered = {
                c
                for p in providers
                if isinstance(p, dict)
                for c in (p.get("currencies") or [])
                if isinstance(c, str)
            }
            self._c_ccy.set_value(str(len(covered)) if covered else "—")
            hdr = ctk.CTkFrame(self._list, fg_color=BG_CARD, corner_radius=4)
            hdr.pack(fill="x", pady=1)
            for col, w, lbl in [
                (0, 80, "Key"),
                (1, 340, "Name"),
                (2, 80, "Country"),
                (3, 100, "Currencies"),
            ]:
                ctk.CTkLabel(
                    hdr,
                    text=lbl,
                    font=FONT_SUBHEAD,
                    text_color=ACCENT_GOLD,
                    width=w,
                    anchor="w",
                ).grid(row=0, column=col, padx=PAD_SM, pady=6)
            self._rows.append(hdr)
            for i, prov in enumerate(providers):
                if isinstance(prov, dict):
                    key = str(prov.get("key", prov.get("code", "—")) or "—")
                    name = str(prov.get("name", "—") or "—")
                    country = str(prov.get("country", "—") or "—")
                    # The API may send null instead of an empty list
                    n_ccy = len(prov.get("currencies") or [])
                else:
                    key = name = str(prov)
                    country = "—"
                    n_ccy: int | str = "—"
                bg = BG_CARD if i % 2 == 0 else BG_DARK
                row = ctk.CTkFrame(self._list, fg_color=bg, corner_radius=2)
                row.pack(fill="x", pady=1)
                for col, w, txt, col_color in [
                    (0, 80, key, ACCENT_GOLD),
                    (1, 340, name, TEXT_PRIMARY),
                    (2, 80, country, TEXT_MUTED),
                    (3, 100, str(n_ccy), ACCENT_BLUE),
                ]:
                    ctk.CTkLabel(
                        row,
                        text=txt,
                        font=FONT_BODY,
                        text_color=col_color,
                        width=w,
                        anchor="w",
                    ).grid(row=0, column=col, padx=PAD_SM, pady=4)
                self._rows.append(row)
                self._row_text.append(f"{key} {name} {country}".upper())
            if self._search.get():
                self._apply_filter(self._search.get())
            self._status(f"Loaded {len(providers)} providers", "ok")

        self._run(work, done)
