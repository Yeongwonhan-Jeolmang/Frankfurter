"""3. Time Series — plot any pair across a custom range."""

from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtWidgets import QCheckBox, QGridLayout, QSizePolicy, QWidget

from ui.chart_panel import ChartPanel
from ui.tabs.base import BaseTab, code_of, quick_range_chips, saved_or, validate_range
from ui.theme import *
from ui.widgets import (
    CodeCombo,
    DateEntry,
    Field,
    SegmentedButton,
    Sidebar,
    SkeletonOverlay,
    make_button,
)


class TimeSeriesTab(BaseTab):
    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._last: dict = {}
        self._build()

    def _build(self):
        s = self._settings
        year_ago = (date.today() - timedelta(days=365)).isoformat()
        sb = Sidebar("Time Series Chart")

        # Base / quote with a ⇅ swap button beside them
        pair = QWidget()
        g = QGridLayout(pair)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(4)
        g.setVerticalSpacing(0)
        self._base_e = CodeCombo(self._codes, saved_or(s, "ts_base", "EUR"))
        self._quote_e = CodeCombo(self._codes, saved_or(s, "ts_quote", "USD"))
        g.addWidget(Field("Base", self._base_e), 0, 0)
        g.addWidget(Field("Quote", self._quote_e), 1, 0)
        swap = make_button(
            "⇅", self._swap, "glyph", width=30, tooltip="Swap base and quote"
        )
        swap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        g.addWidget(swap, 0, 1, 2, 1)
        g.setColumnStretch(0, 1)
        sb.add(pair)

        self._start_e = DateEntry(saved_or(s, "ts_start", year_ago))
        self._end_e = DateEntry(saved_or(s, "ts_end", date.today().isoformat()))
        sb.add(Field("Start", self._start_e))
        sb.add(Field("End", self._end_e))

        self._group = SegmentedButton(["None", "Weekly", "Monthly"], "None")
        sb.add(Field("Group By", self._group))

        sb.separator()
        self._pct = QCheckBox("% Change from Start")
        self._pct.toggled.connect(self._chart_pct)
        sb.add(self._pct)
        sb.add(
            make_button("📈  Fetch & Plot", self._fetch), before=PAD_MD, after=PAD_SM
        )

        sb.separator()
        sb.caption("Quick Ranges")
        sb.add(
            quick_range_chips(
                self._start_e,
                self._end_e,
                self._fetch,
                [
                    ("1M", 30, False),
                    ("3M", 90, False),
                    ("6M", 180, False),
                    ("1Y", 365, False),
                    ("3Y", 1095, False),
                    ("5Y", 1826, False),
                    ("10Y", 3652, False),
                    ("20Y", 7305, False),
                ],
            )
        )

        sb.separator()
        sb.add(
            make_button(
                "⬇  CSV",
                lambda: self._export_csv_data(self._last, "timeseries"),
                "secondary",
            )
        )
        sb.add(
            make_button(
                "⬇  JSON",
                lambda: self._export_json_data(self._last, "timeseries"),
                "secondary",
            )
        )

        main = self._split(sb, margins=PAD_MD)
        self._chart = ChartPanel()
        main.addWidget(self._chart, 1)
        self._skeleton = SkeletonOverlay(self._chart)

    def _chart_pct(self, on: bool):
        self._chart.set_pct_mode(on)

    def _swap(self):
        b, q = self._base_e.get(), self._quote_e.get()
        self._base_e.set(q)
        self._quote_e.set(b)
        if self._last:
            self._fetch()

    def _fetch(self):
        base = code_of(self._base_e, "EUR")
        quote = code_of(self._quote_e, "USD")
        start, end, problem = validate_range(self._start_e, self._end_e)
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
            self._chart.set_pct_mode(self._pct.isChecked())
            self._chart.plot_series(data, base, quote)
            n = len(data.get("rates", {}))
            self._status(
                f"{base}/{quote}  •  {n} data points  •  {start} → {end}", "ok"
            )

        self._run(work, done, skeleton=self._skeleton)
