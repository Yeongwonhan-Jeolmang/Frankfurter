"""5. Compare — overlay up to 8 currencies on one chart."""

from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtWidgets import QCheckBox

from ui.chart_panel import ChartPanel
from ui.tabs.base import BaseTab, code_of, quick_range_chips, saved_or, validate_range
from ui.theme import *
from ui.widgets import (
    CodeCombo,
    CurrencyChecklist,
    DateEntry,
    Field,
    SearchEntry,
    Sidebar,
    SkeletonOverlay,
    hbox,
    make_button,
    make_label,
    set_color,
)


class CompareTab(BaseTab):
    MAX_SERIES = 8
    DEFAULTS = ["USD", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR"]

    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._last: dict = {}
        self._build()

    def _build(self):
        s = self._settings
        year_ago = (date.today() - timedelta(days=365)).isoformat()
        sb = Sidebar("Multi-Currency Compare")
        self._base_e = CodeCombo(self._codes, saved_or(s, "cmp_base", "EUR"))
        self._start_e = DateEntry(saved_or(s, "cmp_start", year_ago))
        self._end_e = DateEntry(saved_or(s, "cmp_end", date.today().isoformat()))
        sb.add(Field("Base", self._base_e))
        sb.add(Field("Start", self._start_e))
        sb.add(Field("End", self._end_e))

        # Rates of e.g. JPY (~160) and GBP (~0.85) can't share an absolute
        # axis meaningfully, so normalising to % change is on by default.
        self._pct = QCheckBox("Normalise (% change from start)")
        self._pct.setChecked(bool(saved_or(s, "cmp_pct", True)))
        self._pct.toggled.connect(self._on_pct_toggle)
        sb.add(self._pct, after=PAD_SM)

        self._sel_lbl = make_label("", FONT_LABEL, TEXT_MUTED)
        sb.add(
            hbox(
                self._sel_lbl,
                None,
                make_button("Clear", self._clear_checks, "muted", width=52),
            )
        )
        sb.add(SearchEntry("Filter currencies…", on_change=self._filter_checks))
        self._checks = CurrencyChecklist(
            self._codes,
            self._names,
            saved_or(s, "cmp_quotes", None) or self.DEFAULTS,
            height=200,
        )
        self._checks.changed.connect(self._update_sel_count)
        sb.add(self._checks)
        self._update_sel_count()
        sb.add(make_button("📊  Compare", self._fetch), before=PAD_MD, after=PAD_SM)

        sb.separator()
        sb.caption("Quick Ranges")
        sb.add(quick_range_chips(self._start_e, self._end_e, self._fetch))

        sb.separator()
        sb.add(
            make_button(
                "⬇  CSV",
                lambda: self._export_csv_data(self._last, "compare"),
                "secondary",
            )
        )
        sb.add(
            make_button(
                "⬇  JSON",
                lambda: self._export_json_data(self._last, "compare"),
                "secondary",
            )
        )

        main = self._split(sb, margins=PAD_MD)
        self._chart = ChartPanel(show_types=False)
        self._chart.set_pct_mode(self._pct.isChecked())
        main.addWidget(self._chart, 1)
        self._skeleton = SkeletonOverlay(self._chart)

    def _update_sel_count(self):
        n = len(self._checks.selected())
        self._sel_lbl.setText(f"Selected {n} / {self.MAX_SERIES}")
        set_color(self._sel_lbl, ACCENT_RED if n > self.MAX_SERIES else TEXT_MUTED)

    def _clear_checks(self):
        self._checks.clear_checks()

    def _filter_checks(self, text):
        self._checks.apply_filter(text)

    def _on_pct_toggle(self, on: bool):
        self._chart.set_pct_mode(on)
        if self._settings:
            self._settings.set("cmp_pct", on)

    def _fetch(self):
        base = code_of(self._base_e, "EUR")
        start, end, problem = validate_range(self._start_e, self._end_e)
        if problem:
            self._status(problem, "error")
            return
        if not self._check_codes(base):
            return
        selected = [c for c in self._checks.selected() if c != base]
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
