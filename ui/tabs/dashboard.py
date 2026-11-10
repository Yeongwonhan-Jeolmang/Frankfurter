"""1. Dashboard — live rates for any base currency."""

from __future__ import annotations

from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QRadioButton, QWidget

from ui.tabs.base import BaseTab, code_of, saved_or
from ui.theme import *
from ui.widgets import (
    CodeCombo,
    RateTable,
    SearchEntry,
    SectionHeader,
    Sidebar,
    SkeletonOverlay,
    StatCard,
    make_button,
    make_label,
    set_color,
)


class DashboardTab(BaseTab):
    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._last: dict = {}
        self._build()
        self._fetch()

    def _build(self):
        sb = Sidebar("FRANKFURTER")
        sb.add(make_label("Exchange Rate Terminal", FONT_SMALL, TEXT_MUTED))
        sb.separator()

        sb.add(SectionHeader("Base Currency"), after=PAD_SM)
        self._base = CodeCombo(
            self._codes, saved_or(self._settings, "dashboard_base", "EUR"),
            command=lambda _t: self._fetch(),
        )
        sb.add(self._base, after=PAD_MD)

        sb.add(SectionHeader("Filter"), after=PAD_SM)
        self._search = SearchEntry("Search currencies…", on_change=self._table_filter)
        sb.add(self._search)

        sb.separator()
        sb.add(make_button("⟳  Refresh", lambda: self._fetch(force=True)))
        sb.separator()
        sb.add(make_button("⬇  CSV", lambda: self._export_csv_data(self._last, "latest"), "secondary"))
        sb.add(make_button("⬇  JSON", lambda: self._export_json_data(self._last, "latest"), "secondary"))

        sb.separator()
        sb.caption("Currency Scope")
        self._scope_group = QButtonGroup(self)
        self._scope_buttons: dict[str, QRadioButton] = {}
        for v, l in (("active", "Active only"), ("all", "All incl. archived names")):
            rb = QRadioButton(l)
            rb.setChecked(v == "active")
            self._scope_group.addButton(rb)
            self._scope_buttons[v] = rb
            rb.toggled.connect(lambda on: on and self._fetch())
            sb.add(rb)

        sb.separator()
        sb.caption("★  Pinned Pairs", ACCENT_GOLD)
        self._pinned_lbl = make_label(
            "Click ★ in the table to pin a pair", FONT_SMALL, TEXT_DIM, wrap=True
        )
        sb.add(self._pinned_lbl)

        main = self._split(sb)

        cards = QWidget()
        cl = QHBoxLayout(cards)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(PAD_MD)
        self._c_rate = StatCard("EUR/USD")
        self._c_count = StatCard("Currencies", color=ACCENT_BLUE)
        self._c_date = StatCard("Last Updated", color=TEXT_PRIMARY)
        self._c_scope = StatCard("Scope", color=ACCENT_PURPLE)
        for c in (self._c_rate, self._c_count, self._c_date, self._c_scope):
            cl.addWidget(c)
        main.addWidget(cards)
        main.addSpacing(PAD_MD)

        main.addWidget(SectionHeader(
            "Exchange Rates  (click ★ to pin • header to sort • double-click to copy)"
        ))
        self._table = RateTable(
            settings=self._settings,
            on_copy=lambda t: self._status(f"Copied  “{t}”", "ok"),
            on_pin=self._update_pinned_label,
        )
        main.addWidget(self._table, 1)
        self._skeleton = SkeletonOverlay(self._table)

    def _scope(self) -> str:
        return "all" if self._scope_buttons["all"].isChecked() else "active"

    def _table_filter(self, text):
        self._table.set_filter(text)

    def _update_pinned_label(self):
        if not self._settings:
            return
        base = code_of(self._base, "EUR")
        pairs = [f"{b}/{q}" for b, q in self._settings.get_favourites() if b == base]
        if pairs:
            self._pinned_lbl.setText("\n".join(pairs))
            set_color(self._pinned_lbl, ACCENT_GOLD)
        else:
            self._pinned_lbl.setText("Click ★ in the table to pin a pair")
            set_color(self._pinned_lbl, TEXT_DIM)

    def _fetch(self, force=False):
        base = code_of(self._base, "EUR")
        if not self._check_codes(base):
            return
        scope = self._scope()
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
            self._table.populate(rates, names, base, self._search.get())
            self._update_pinned_label()
            self._status(f"Rates for {base}  •  {on_date}  •  {len(rates)} pairs", "ok")

        self._run(work, done, skeleton=self._skeleton)
