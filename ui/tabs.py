"""
All tab views for the Frankfurter GUI brought to you by Florian van den Bersselaar.
"""

import customtkinter as ctk
from datetime import date, timedelta, datetime
from tkinter import filedialog
import json

from ui.theme import *
from ui.widgets import (
    StatCard,
    SectionHeader,
    HSeparator,
    LabelledCombo,
    RateTable,
    SearchEntry,
    WatchlistPanel,
    SkeletonFrame,
)
from ui.chart_panel import ChartPanel
from utils.workers import AsyncWorker
from exports.exporter import export_to_csv, export_to_json, default_filename

# ── helpers ────────────────────────────────────────────────────────────────────


def _date_entry(parent, label, default):
    ctk.CTkLabel(parent, text=label, font=FONT_LABEL, text_color=TEXT_MUTED).pack(
        anchor="w"
    )
    e = ctk.CTkEntry(
        parent,
        placeholder_text=default,
        fg_color=BG_INPUT,
        border_color=BORDER_COLOR,
        text_color=TEXT_PRIMARY,
        font=FONT_MONO,
        width=160,
        height=32,
    )
    e.insert(0, default)
    e.pack(fill="x", pady=(0, PAD_SM))
    return e


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


def _sidebar(parent, title):
    sb = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=0, width=250)
    sb.pack(side="left", fill="y")
    sb.pack_propagate(False)
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
    qf = ctk.CTkFrame(parent, fg_color="transparent")
    qf.pack(fill="x", padx=PAD_MD)

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
    ]
    for lbl, days, ytd in presets:
        ctk.CTkButton(
            qf,
            text=lbl,
            height=26,
            width=40,
            fg_color=BG_INPUT,
            hover_color=BG_HOVER,
            text_color=TEXT_PRIMARY,
            font=FONT_SMALL,
            command=lambda d=days, y=ytd: _apply(d, y),
        ).pack(side="left", padx=1, pady=2)


# ── base ───────────────────────────────────────────────────────────────────────


class BaseTab(ctk.CTkFrame):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, fg_color=BG_DARK, **kw)
        self._client = client
        self._names = currency_names
        self._status = status_cb
        self._codes = sorted(currency_names.keys())
        self._settings = settings

    def _run(self, fn, cb, skeleton=None):
        self._status("Fetching…", "loading")
        if skeleton:
            try:
                skeleton.show()
            except Exception:
                pass

        def wrapped(result, err):
            if skeleton:
                try:
                    skeleton.hide()
                except Exception:
                    pass
            cb(result, err)

        AsyncWorker(fn, wrapped, root=self.winfo_toplevel()).start()

    def _export_csv_data(self, data):
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=default_filename("rates", "csv"),
        )
        if p:
            export_to_csv(data, p)
            self._status(f"Exported → {p}", "ok")

    def _export_json_data(self, data):
        p = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=default_filename("rates", "json"),
        )
        if p:
            export_to_json(data, p)
            self._status(f"Exported → {p}", "ok")


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
        self._base = LabelledCombo(sb, "", self._codes, width=210)
        saved_base = (
            self._settings.get("dashboard_base", "EUR") if self._settings else "EUR"
        )
        self._base.set(saved_base)
        self._base.pack(padx=PAD_MD, pady=(0, PAD_MD), fill="x")

        SectionHeader(sb, "Filter").pack(padx=PAD_MD, pady=(0, PAD_SM), anchor="w")
        self._search = SearchEntry(sb, "Search currencies…", on_change=self._on_filter)
        self._search.pack(padx=PAD_MD, fill="x")

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _btn(sb, "⟳  Refresh", self._fetch).pack(padx=PAD_MD, pady=2, fill="x")
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
            ("active", "Active only (165)"),
            ("all", "All incl. archived (201)"),
        ]:
            ctk.CTkRadioButton(
                sb,
                text=l,
                variable=self._scope,
                value=v,
                font=FONT_SMALL,
                text_color=TEXT_PRIMARY,
                fg_color=ACCENT_GOLD,
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

        SectionHeader(main, "Exchange Rates  (click ★ to pin)").pack(
            anchor="w", pady=(0, PAD_SM)
        )

        # Wrap table in a relative-positioned container so SkeletonFrame can place() over it
        table_wrap = ctk.CTkFrame(main, fg_color="transparent")
        table_wrap.pack(fill="both", expand=True)
        self._table = RateTable(table_wrap, settings=self._settings)
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

    def _fetch(self):
        base = self._base.get().split(" –")[0].strip()
        scope = self._scope.get()
        if self._settings:
            self._settings.set("dashboard_base", base)

        def work():
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
            self._c_rate.set_label(f"{base}/USD")
            usd_rate = rates.get("USD")
            self._c_rate.set_value(f"{usd_rate:.4f}" if usd_rate is not None else "—")
            self._c_count.set_value(str(len(rates)))
            self._c_date.set_value(on_date)
            self._c_scope.set_value(scope.capitalize())
            self._table.populate(rates, names, base)
            self._update_pinned_label()
            self._status(f"Rates for {base}  •  {on_date}  •  {len(rates)} pairs", "ok")

        self._run(work, done, skeleton=self._skeleton)

    def _do_csv(self):
        if self._last:
            self._export_csv_data(self._last)

    def _do_json(self):
        if self._last:
            self._export_json_data(self._last)


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
        self._base_e = _date_entry(inner, "Base Currency", "EUR")
        self._date_e = _date_entry(inner, "Date (YYYY-MM-DD)", "2010-01-04")
        _btn(inner, "🔍  Fetch", self._fetch).pack(fill="x", pady=PAD_SM)
        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)

        ctk.CTkLabel(
            sb, text="Quick Jump", font=FONT_LABEL, text_color=TEXT_MUTED
        ).pack(padx=PAD_MD, anchor="w")
        years_f = ctk.CTkFrame(sb, fg_color="transparent")
        years_f.pack(fill="x", padx=PAD_MD)
        current_year = date.today().year
        for yr in range(current_year, current_year - 10, -1):
            ctk.CTkButton(
                years_f,
                text=str(yr),
                height=26,
                width=60,
                fg_color=BG_INPUT,
                hover_color=BG_HOVER,
                text_color=TEXT_PRIMARY,
                font=FONT_SMALL,
                command=lambda y=yr: self._jump_year(y),
            ).pack(side="left", padx=1, pady=1)

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _btn(
            sb, "⬇  CSV", lambda: self._export_csv_data(self._last), accent=False
        ).pack(padx=PAD_MD, pady=2, fill="x")
        _btn(
            sb, "⬇  JSON", lambda: self._export_json_data(self._last), accent=False
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
        self._table = RateTable(table_wrap, settings=self._settings)
        self._table.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(table_wrap)

    def _jump_year(self, yr):
        self._date_e.delete(0, "end")
        self._date_e.insert(0, f"{yr}-01-02")
        self._fetch()

    def _fetch(self):
        base = self._base_e.get().strip().upper() or "EUR"
        on_date = self._date_e.get().strip()

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

        self._base_e = _date_entry(inner, "Base", saved_base)
        self._quote_e = _date_entry(inner, "Quote", saved_quote)
        self._start_e = _date_entry(inner, "Start", saved_start)
        self._end_e = _date_entry(inner, "End", saved_end)

        ctk.CTkLabel(
            inner, text="Group By", font=FONT_LABEL, text_color=TEXT_MUTED
        ).pack(anchor="w")
        self._group = ctk.StringVar(value="none")
        for v, l in [("none", "None"), ("week", "Weekly"), ("month", "Monthly")]:
            ctk.CTkRadioButton(
                inner,
                text=l,
                variable=self._group,
                value=v,
                font=FONT_BODY,
                text_color=TEXT_PRIMARY,
                fg_color=ACCENT_GOLD,
            ).pack(anchor="w", pady=1)

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
        qf = ctk.CTkFrame(sb, fg_color="transparent")
        qf.pack(fill="x", padx=PAD_MD)
        for lbl, days in [
            ("1M", 30),
            ("3M", 90),
            ("6M", 180),
            ("1Y", 365),
            ("3Y", 1095),
            ("5Y", 1825),
            ("10Y", 3650),
            ("20Y", 7300),
        ]:
            ctk.CTkButton(
                qf,
                text=lbl,
                height=26,
                width=48,
                fg_color=BG_INPUT,
                hover_color=BG_HOVER,
                text_color=TEXT_PRIMARY,
                font=FONT_SMALL,
                command=lambda d=days: self._quick(d),
            ).pack(side="left", padx=1, pady=2)

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _btn(
            sb, "⬇  CSV", lambda: self._export_csv_data(self._last), accent=False
        ).pack(padx=PAD_MD, pady=2, fill="x")
        _btn(
            sb, "⬇  JSON", lambda: self._export_json_data(self._last), accent=False
        ).pack(padx=PAD_MD, pady=2, fill="x")

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True)

        self._chart = ChartPanel(main)
        self._chart.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        self._skeleton = SkeletonFrame(main)

    def _on_pct_toggle(self):
        self._chart.set_pct_mode(self._pct_var.get())

    def _quick(self, days):
        end = date.today()
        start = end - timedelta(days=days)
        self._start_e.delete(0, "end")
        self._start_e.insert(0, start.isoformat())
        self._end_e.delete(0, "end")
        self._end_e.insert(0, end.isoformat())
        self._fetch()

    def _fetch(self):
        base = self._base_e.get().strip().upper() or "EUR"
        quote = self._quote_e.get().strip().upper() or "USD"
        start = self._start_e.get().strip()
        end = self._end_e.get().strip()
        group = self._group.get()
        group = None if group == "none" else group

        if self._settings:
            self._settings.set("ts_base", base)
            self._settings.set("ts_quote", quote)
            self._settings.set("ts_start", start)
            self._settings.set("ts_end", end)

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

        # Restore saved currencies
        s = self._settings
        saved_from = s.get("conv_from", "EUR") if s else "EUR"
        saved_to = s.get("conv_to", "USD") if s else "USD"

        self._from = LabelledCombo(row1, "From", self._codes, width=200)
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
        self._to = LabelledCombo(row1, "To", self._codes, width=200)
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
        ).pack(side="left", padx=(PAD_MD, PAD_SM))
        ctk.CTkRadioButton(
            row_dir,
            text="Quote → Base  (reverse)",
            variable=self._dir_var,
            value="rev",
            font=FONT_SMALL,
            text_color=TEXT_PRIMARY,
            fg_color=ACCENT_GOLD,
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
        self._date_e = ctk.CTkEntry(
            row2,
            placeholder_text="YYYY-MM-DD",
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_MONO,
            width=140,
            height=28,
        )
        self._date_e.pack(side="left", padx=PAD_MD)

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

    def _swap(self):
        f, t = self._from.get(), self._to.get()
        self._from.set(t)
        self._to.set(f)

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
        import math

        try:
            amount = float(self._amt.get())
            if not math.isfinite(amount):
                raise ValueError("non-finite")
        except (ValueError, TypeError):
            self._status("Invalid amount", "error")
            return

        base = self._from.get().split(" –")[0].strip()
        quote = self._to.get().split(" –")[0].strip()
        on_date = self._date_e.get().strip() or None
        reverse = self._dir_var.get() == "rev"

        # Persist selections
        if self._settings:
            self._settings.set("conv_from", base)
            self._settings.set("conv_to", quote)

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

            if reverse:
                # amount is in *quote* currency; convert back to base
                effective_rate = 1.0 / rate
                converted = amount * effective_rate
                result_text = f"{amount:,.2f} {quote}  =  {converted:,.4f} {base}"
                log_from, log_to = quote, base
            else:
                converted = amount * rate
                result_text = f"{amount:,.2f} {base}  =  {converted:,.4f} {quote}"
                log_from, log_to = base, quote

            self._last_result_text = result_text
            self._res.configure(text=result_text)
            self._detail.configure(
                text=f"Rate: {rate:.6f}  •  Inverse: {1/rate:.6f}  •  Date: {data.get('date','—')}"
            )
            ts = datetime.now().strftime("%H:%M:%S")
            log = f"[{ts}]  {amount:,.2f} {log_from} → {converted:,.4f} {log_to}  @ {rate:.6f}  ({data.get('date','latest')})\n"
            self._hist.configure(state="normal")
            self._hist.insert("end", log)
            self._hist.see("end")
            self._hist.configure(state="disabled")
            self._status(f"Converted  {amount} {log_from} → {log_to}", "ok")

        self._run(work, done)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Multi-currency Compare
# ══════════════════════════════════════════════════════════════════════════════


class CompareTab(BaseTab):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
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

        self._base_e = _date_entry(inner, "Base", saved_base)
        self._start_e = _date_entry(inner, "Start", saved_start)
        self._end_e = _date_entry(inner, "End", saved_end)

        ctk.CTkLabel(
            inner,
            text="Select Currencies (up to 8)",
            font=FONT_LABEL,
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(PAD_SM, 2))

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
        defaults = {"USD", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR"}
        for code in self._codes:
            var = ctk.BooleanVar(value=code in defaults)
            self._check_vars[code] = var
            cb = ctk.CTkCheckBox(
                self._scroll,
                text=f"{code}  {self._names.get(code,code)}",
                variable=var,
                font=FONT_SMALL,
                text_color=TEXT_PRIMARY,
                fg_color=ACCENT_GOLD,
                hover_color=ACCENT_GOLD,
                checkmark_color=BG_DARK,
            )
            cb.pack(anchor="w", pady=1)
            self._check_widgets[code] = cb

        _btn(inner, "📊  Compare", self._fetch).pack(fill="x", pady=PAD_MD)

        HSeparator(sb).pack(fill="x", padx=PAD_MD, pady=PAD_MD)
        _quick_range_row(sb, self._start_e, self._end_e, self._fetch)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True)
        self._chart = ChartPanel(main)
        self._chart.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        self._skeleton = SkeletonFrame(main)

    def _filter_checks(self, text):
        text = text.upper()
        for code, widget in self._check_widgets.items():
            match = (
                not text or text in code or text in self._names.get(code, "").upper()
            )
            if match:
                widget.pack(anchor="w", pady=1)
            else:
                widget.pack_forget()

    def _fetch(self):
        base = self._base_e.get().strip().upper() or "EUR"
        start = self._start_e.get().strip()
        end = self._end_e.get().strip()
        quotes = [c for c, v in self._check_vars.items() if v.get()][:8]
        if not quotes:
            self._status("Select at least one currency", "error")
            return

        if self._settings:
            self._settings.set("cmp_base", base)
            self._settings.set("cmp_start", start)
            self._settings.set("cmp_end", end)

        def work():
            return {
                q: self._client.get_time_series(start, end, base, [q]) for q in quotes
            }

        def done(data, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            self._chart.plot_multi(data, base)
            self._status(f"Comparing {len(quotes)} currencies vs {base}", "ok")

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

        self._base_e = _date_entry(inner, "Base", saved_base)
        self._quote_e = _date_entry(inner, "Quote", saved_quote)
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
        ]
        self._cards: dict[str, StatCard] = {}
        for i, (key, lbl, col) in enumerate(specs):
            c = StatCard(grid, lbl, color=col)
            c.grid(row=i // 5, column=i % 5, sticky="nsew", padx=PAD_SM, pady=PAD_SM)
            self._cards[key] = c
        for col in range(5):
            grid.grid_columnconfigure(col, weight=1)

        HSeparator(main).pack(fill="x", pady=PAD_MD)
        SectionHeader(main, "Rate Chart").pack(anchor="w", pady=(0, PAD_SM))

        chart_wrap = ctk.CTkFrame(main, fg_color="transparent")
        chart_wrap.pack(fill="both", expand=True)
        self._chart = ChartPanel(chart_wrap)
        self._chart.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(chart_wrap)

    def _fetch(self):
        base = self._base_e.get().strip().upper() or "EUR"
        quote = self._quote_e.get().strip().upper() or "USD"
        start = self._start_e.get().strip()
        end = self._end_e.get().strip()

        if self._settings:
            self._settings.set("stats_base", base)
            self._settings.set("stats_quote", quote)
            self._settings.set("stats_start", start)
            self._settings.set("stats_end", end)

        def work():
            stats = self._client.get_volatility_stats(base, quote, start, end)
            series = self._client.get_time_series(start, end, base, [quote])
            return stats, series

        def done(result, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            stats, series = result
            chg = stats.get("change_pct", 0)
            dd = stats.get("max_drawdown", 0)
            fmts = {
                "min": f"{stats.get('min',0):.6f}",
                "max": f"{stats.get('max',0):.6f}",
                "mean": f"{stats.get('mean',0):.6f}",
                "stdev": f"{stats.get('stdev',0):.6f}",
                "count": str(stats.get("count", 0)),
                "change_pct": f"{chg:+.4f}%",
                "avg_daily_pct_change": f"{stats.get('avg_daily_pct_change',0):+.4f}%",
                "max_drawdown": f"{dd:.4f}%",
                "first": f"{stats.get('first',0):.6f}",
                "last": f"{stats.get('last',0):.6f}",
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
        self._base_e = _date_entry(inner, "Base", "EUR")
        self._quote_e = _date_entry(inner, "Quote", "USD")
        self._start_yr = _date_entry(inner, "Start Year", "2000")
        self._end_yr = _date_entry(inner, "End Year", str(date.today().year))
        _btn(inner, "🔥  Generate Heatmap", self._fetch).pack(fill="x", pady=PAD_MD)

        ctk.CTkLabel(
            sb,
            text="Shows annual % change for\neach year in the range.",
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
        self._chart = ChartPanel(chart_wrap)
        self._chart.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(chart_wrap)

        self._summary_frame = ctk.CTkScrollableFrame(main, height=100, fg_color=BG_CARD)
        self._summary_frame.pack(fill="x", padx=PAD_MD, pady=(0, PAD_MD))
        self._summary_labels: list = []

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
        base = self._base_e.get().strip().upper() or "EUR"
        quote = self._quote_e.get().strip().upper() or "USD"
        try:
            sy = int(self._start_yr.get().strip())
            ey = int(self._end_yr.get().strip())
        except Exception:
            sy, ey = 2000, date.today().year

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
            for w in self._summary_labels:
                w.destroy()
            self._summary_labels.clear()
            ctk.CTkLabel(
                self._summary_frame,
                text="Year",
                font=FONT_SUBHEAD,
                text_color=ACCENT_GOLD,
                width=60,
            ).grid(row=0, column=0, padx=4)
            ctk.CTkLabel(
                self._summary_frame,
                text="% Change",
                font=FONT_SUBHEAD,
                text_color=ACCENT_GOLD,
                width=100,
            ).grid(row=0, column=1, padx=4)
            for i, (yr, chg) in enumerate(sorted(data.items())):
                col = ACCENT_GREEN if chg >= 0 else ACCENT_RED
                yl = ctk.CTkLabel(
                    self._summary_frame,
                    text=str(yr),
                    font=FONT_MONO,
                    text_color=TEXT_MUTED,
                    width=60,
                )
                yl.grid(row=i + 1, column=0, padx=4, pady=1)
                cl = ctk.CTkLabel(
                    self._summary_frame,
                    text=f"{chg:+.2f}%",
                    font=FONT_MONO,
                    text_color=col,
                    width=100,
                )
                cl.grid(row=i + 1, column=1, padx=4, pady=1)
                self._summary_labels += [yl, cl]
            self._status(f"Annual heatmap  {base}/{quote}  {sy}–{ey}", "ok")

        self._run(work, done, skeleton=self._skeleton)


# ══════════════════════════════════════════════════════════════════════════════
# 8. Cross-Rate Matrix
# ══════════════════════════════════════════════════════════════════════════════


class MatrixTab(BaseTab):
    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._last_matrix: dict = {}
        self._last_codes: list[str] = []
        self._build()

    def _build(self):
        sb = _sidebar(self, "Cross-Rate Matrix")
        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="x", padx=PAD_MD)
        ctk.CTkLabel(
            inner,
            text="Select Currencies (3–10)",
            font=FONT_LABEL,
            text_color=TEXT_MUTED,
        ).pack(anchor="w")

        self._scroll = ctk.CTkScrollableFrame(
            inner, height=260, fg_color=BG_INPUT, corner_radius=CORNER_RADIUS
        )
        self._scroll.pack(fill="x")
        self._check_vars: dict[str, ctk.BooleanVar] = {}
        defaults = {"EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY"}
        for code in self._codes:
            var = ctk.BooleanVar(value=code in defaults)
            self._check_vars[code] = var
            ctk.CTkCheckBox(
                self._scroll,
                text=f"{code}",
                variable=var,
                font=FONT_SMALL,
                text_color=TEXT_PRIMARY,
                fg_color=ACCENT_GOLD,
                hover_color=ACCENT_GOLD,
                checkmark_color=BG_DARK,
            ).pack(anchor="w", pady=1)

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
        self._chart = ChartPanel(chart_wrap)
        self._chart.pack(fill="both", expand=True)
        self._skeleton = SkeletonFrame(chart_wrap)

        self._table_frame = ctk.CTkScrollableFrame(main, height=200, fg_color=BG_CARD)
        self._table_frame.pack(fill="x", padx=PAD_MD, pady=(0, PAD_MD))

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
        codes = [c for c, v in self._check_vars.items() if v.get()][:10]
        if len(codes) < 2:
            self._status("Select at least 2 currencies", "error")
            return

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
            self._status(f"Cross-rate matrix for {len(codes)} currencies", "ok")

        self._run(work, done, skeleton=self._skeleton)


# ══════════════════════════════════════════════════════════════════════════════
# 9. Watchlist
# ══════════════════════════════════════════════════════════════════════════════


class WatchlistTab(BaseTab):
    SAVE_FILE = "watchlist.json"

    def __init__(self, master, client, currency_names, status_cb, settings=None, **kw):
        super().__init__(master, client, currency_names, status_cb, settings, **kw)
        self._pairs: list[tuple] = []
        self._load_saved()
        self._build()

    def _load_saved(self):
        # Prefer settings-based persistence; fall back to watchlist.json for compatibility
        if self._settings:
            saved = self._settings.get("watchlist_pairs")
            if saved:
                self._pairs = [tuple(p) for p in saved]
                return
        try:
            with open(self.SAVE_FILE) as f:
                self._pairs = [tuple(p) for p in json.load(f)]
        except Exception:
            self._pairs = [
                ("EUR", "USD"),
                ("GBP", "USD"),
                ("USD", "JPY"),
                ("EUR", "GBP"),
            ]

    def _save_pairs(self):
        if self._settings:
            self._settings.set("watchlist_pairs", [list(p) for p in self._pairs])
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
        _btn(row, "+", self._add_pair, accent=True).pack(side="left", padx=PAD_SM)

        HSeparator(inner).pack(fill="x", pady=PAD_SM)
        _btn(inner, "⟳  Refresh All", self._refresh).pack(fill="x", pady=2)
        _btn(inner, "🗑  Clear All", self._clear, accent=False).pack(fill="x", pady=2)

        ctk.CTkLabel(
            sb,
            text="Pairs persist between sessions.\nClick ★ to pin to the top.\nPinned pairs appear first.",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
            wraplength=200,
            justify="left",
        ).pack(padx=PAD_MD, pady=PAD_MD)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=PAD_LG, pady=PAD_LG)

        SectionHeader(main, "Watched Pairs  (★ to pin)").pack(
            anchor="w", pady=(0, PAD_SM)
        )
        self._wl = WatchlistPanel(main, settings=self._settings)
        self._wl.pack(fill="both", expand=False)

        HSeparator(main).pack(fill="x", pady=PAD_MD)
        SectionHeader(main, "1-Year Chart").pack(anchor="w", pady=(0, PAD_SM))
        self._chart = ChartPanel(main)
        self._chart.pack(fill="both", expand=True)

        self._refresh()

    def _add_pair(self):
        b = self._add_base.get().strip().upper()
        q = self._add_quote.get().strip().upper()
        if b and q and (b, q) not in self._pairs:
            self._pairs.append((b, q))
            self._save_pairs()
            self._refresh()

    def _clear(self):
        self._pairs.clear()
        self._save_pairs()
        self._wl.refresh([])

    def _refresh(self):
        if not self._pairs:
            return

        def work():
            return self._client.get_watchlist_snapshot(self._pairs)

        def done(snaps, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
            self._wl.refresh(snaps)
            if self._pairs:
                base, quote = self._pairs[0]
                self._plot_pair(base, quote)
            self._status(f"Watchlist refreshed  •  {len(snaps)} pairs", "ok")

        self._run(work, done)

    def _plot_pair(self, base, quote):
        start = (date.today() - timedelta(days=365)).isoformat()

        def work():
            return self._client.get_time_series(start, None, base, [quote])

        def done(data, err):
            if not err:
                self._chart.plot_series(data, base, quote)

        AsyncWorker(work, done, root=self.winfo_toplevel()).start()


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
        self._combo.set("EUR")
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
        )
        self._raw.pack(fill="both", expand=True)

        HSeparator(main).pack(fill="x", pady=PAD_MD)
        SectionHeader(main, "5-Year Rate Chart vs EUR").pack(
            anchor="w", pady=(0, PAD_SM)
        )
        self._chart = ChartPanel(main)
        self._chart.pack(fill="both", expand=True)

    def _on_select(self, _=None):
        pass

    def _fetch(self):
        code = self._combo.get().split(" –")[0].strip().upper()

        def work():
            detail = self._client.get_currency_detail(code)
            series = self._client.get_time_series(
                (date.today() - timedelta(days=5 * 365)).isoformat(),
                None,
                "EUR",
                [code],
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
            self._c_name.set_value(name, ACCENT_BLUE)
            self._c_prov.set_value(str(n_prov))
            self._c_since.set_value(start_dt if isinstance(start_dt, str) else "—")
            self._raw.configure(state="normal")
            self._raw.delete("1.0", "end")
            self._raw.insert("1.0", json.dumps(detail, indent=2))
            self._raw.configure(state="disabled")
            self._chart.plot_series(series, "EUR", code)
            self._status(f"Currency detail  •  {code}  •  {name}", "ok")

        self._run(work, done)


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

        SectionHeader(main, "Provider List").pack(anchor="w", pady=(0, PAD_SM))
        self._list = ctk.CTkScrollableFrame(main, fg_color=BG_DARK)
        self._list.pack(fill="both", expand=True)
        self._rows: list = []
        self._fetch()

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
            providers = data if isinstance(data, list) else data.get("providers", [])
            self._c_cnt.set_value(str(len(providers)))
            hdr = ctk.CTkFrame(self._list, fg_color=BG_CARD, corner_radius=4)
            hdr.pack(fill="x", pady=1)
            for col, w, lbl in [
                (0, 80, "Key"),
                (1, 200, "Name"),
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
                    n_ccy = len(prov.get("currencies", []))
                else:
                    key = name = str(prov)
                    country = "—"
                    n_ccy: int | str = "—"
                bg = BG_CARD if i % 2 == 0 else BG_DARK
                row = ctk.CTkFrame(self._list, fg_color=bg, corner_radius=2)
                row.pack(fill="x", pady=1)
                for col, w, txt, col_color in [
                    (0, 80, key, ACCENT_GOLD),
                    (1, 200, name, TEXT_PRIMARY),
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
            self._status(f"Loaded {len(providers)} providers", "ok")

        self._run(work, done)
