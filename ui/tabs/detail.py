"""10. Currency Detail — metadata for one currency plus a 5-year chart."""

from __future__ import annotations

import json
from datetime import date, timedelta

from PyQt6.QtWidgets import QHBoxLayout, QPlainTextEdit, QWidget

from ui.chart_panel import ChartPanel
from ui.tabs.base import BaseTab, code_of, saved_or
from ui.theme import *
from ui.widgets import (
    CodeCombo,
    Field,
    SectionHeader,
    Sidebar,
    SkeletonOverlay,
    StatCard,
    make_button,
)


class CurrencyDetailTab(BaseTab):
    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._build()
        self._fetch()

    def _build(self):
        sb = Sidebar("Currency Detail")
        # Picking from the drop-down loads the currency straight away
        self._combo = CodeCombo(
            self._codes, saved_or(self._settings, "detail_code", "EUR"),
            command=lambda _t: self._fetch(),
        )
        sb.add(Field("Currency Code", self._combo))
        sb.add(make_button("🔍  View Details", self._fetch), before=PAD_SM, after=PAD_SM)
        sb.note("Shows full metadata for a single currency from the Frankfurter API.")

        main = self._split(sb)
        cards = QWidget()
        cl = QHBoxLayout(cards)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(PAD_MD)
        self._c_code = StatCard("Code")
        self._c_name = StatCard("Full Name", color=ACCENT_BLUE)
        self._c_prov = StatCard("Providers", color=ACCENT_GREEN)
        self._c_since = StatCard("Data Since", color=ACCENT_PURPLE)
        for c in (self._c_code, self._c_name, self._c_prov, self._c_since):
            cl.addWidget(c)
        main.addWidget(cards)
        main.addSpacing(PAD_MD)

        main.addWidget(SectionHeader("Raw Metadata (JSON)"))
        self._raw = QPlainTextEdit()
        self._raw.setObjectName("Json")
        self._raw.setReadOnly(True)
        self._raw.setFixedHeight(150)
        main.addWidget(self._raw)
        main.addSpacing(PAD_MD)

        self._chart_hdr = SectionHeader("5-Year Rate Chart vs EUR")
        main.addWidget(self._chart_hdr)
        self._chart = ChartPanel()
        main.addWidget(self._chart, 1)
        self._skeleton = SkeletonOverlay(self._chart)

    def _fetch(self):
        code = code_of(self._combo, "EUR")
        if not self._check_codes(code):
            return
        # Chart EUR/<code>; for the euro itself (EUR/EUR is a flat line) use EUR/USD
        base, quote = ("EUR", "USD") if code == "EUR" else ("EUR", code)
        if self._settings:
            self._settings.set("detail_code", code)

        def work():
            detail = self._client.get_currency_detail(code)
            series = self._client.get_time_series(
                (date.today() - timedelta(days=5 * 365)).isoformat(), None, base, [quote]
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
            self._c_name.set_value(name, ACCENT_BLUE)  # long names clip; full text in tooltip
            self._c_prov.set_value(str(n_prov))
            self._c_since.set_value(start_dt if isinstance(start_dt, str) else "—")
            self._raw.setPlainText(json.dumps(detail, indent=2))
            self._chart_hdr.set_text(f"5-Year Rate Chart  —  {base}/{quote}")
            self._chart.plot_series(series, base, quote)
            self._status(f"Currency detail  •  {code}  •  {name}", "ok")

        self._run(work, done, skeleton=self._skeleton)
