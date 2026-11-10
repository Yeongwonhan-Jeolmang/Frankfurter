"""7. Heatmap — annual close-to-close % change for a pair."""

from __future__ import annotations

import csv
from datetime import date

from PyQt6.QtWidgets import QAbstractSpinBox, QHBoxLayout, QSpinBox, QWidget

from exports.exporter import export_to_json
from ui.chart_panel import ChartPanel
from ui.tabs.base import MIN_DATE, BaseTab, code_of, saved_or
from ui.theme import *
from ui.widgets import (
    CodeCombo,
    Field,
    Sidebar,
    SkeletonOverlay,
    StatCard,
    hbox,
    make_button,
)


def _year_box(value: int) -> QSpinBox:
    sp = QSpinBox()
    sp.setRange(MIN_DATE.year, date.today().year)
    sp.setValue(value)
    sp.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    sp.setAccelerated(True)
    return sp


class HeatmapTab(BaseTab):
    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._last_data: dict[int, float] = {}
        self._last_base = "EUR"
        self._last_quote = "USD"
        self._build()

    def _build(self):
        s = self._settings
        sb = Sidebar("Annual Heatmap")
        self._base_e = CodeCombo(self._codes, saved_or(s, "heat_base", "EUR"))
        self._quote_e = CodeCombo(self._codes, saved_or(s, "heat_quote", "USD"))
        sb.add(Field("Base", self._base_e))
        sb.add(Field("Quote", self._quote_e))
        self._start_yr = _year_box(2000)
        self._end_yr = _year_box(date.today().year)
        sb.add(hbox(Field("Start Year", self._start_yr), Field("End Year", self._end_yr), spacing=4))
        sb.add(make_button("🔥  Generate Heatmap", self._fetch), before=PAD_SM, after=PAD_SM)
        sb.note("Shows the close-to-close % change for each year (current year = YTD). "
                "Scroll or use ↑/↓ in the year boxes.")

        sb.separator()
        sb.add(make_button("⬇  CSV", self._do_csv, "secondary"))
        sb.add(make_button("⬇  JSON", self._do_json, "secondary"))

        main = self._split(sb, margins=PAD_MD)
        self._chart = ChartPanel(show_types=False)
        main.addWidget(self._chart, 1)
        self._skeleton = SkeletonOverlay(self._chart)

        cards = QWidget()
        cl = QHBoxLayout(cards)
        cl.setContentsMargins(0, PAD_SM, 0, 0)
        cl.setSpacing(PAD_MD)
        self._c_best = StatCard("Best Year", color=ACCENT_GREEN)
        self._c_worst = StatCard("Worst Year", color=ACCENT_RED)
        self._c_avg = StatCard("Average / Year", color=ACCENT_GOLD)
        self._c_up = StatCard("Up Years", color=ACCENT_BLUE)
        for c in (self._c_best, self._c_worst, self._c_avg, self._c_up):
            cl.addWidget(c)
        main.addWidget(cards)

    def _do_csv(self):
        if not self._last_data:
            self._status("Nothing to export yet — generate a heatmap first", "error")
            return

        def write(data, path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["year", "base", "quote", "pct_change"])
                w.writeheader()
                for yr, chg in sorted(data.items()):
                    w.writerow({"year": yr, "base": self._last_base,
                                "quote": self._last_quote, "pct_change": round(chg, 6)})

        self._write_export(write, self._last_data, "heatmap", "csv")

    def _do_json(self):
        if not self._last_data:
            self._status("Nothing to export yet — generate a heatmap first", "error")
            return
        payload = {
            "base": self._last_base,
            "quote": self._last_quote,
            "annual_changes": {str(yr): chg for yr, chg in sorted(self._last_data.items())},
        }
        self._write_export(export_to_json, payload, "heatmap", "json")

    def _fetch(self):
        base = code_of(self._base_e, "EUR")
        quote = code_of(self._quote_e, "USD")
        sy, ey = self._start_yr.value(), self._end_yr.value()
        if sy > ey:
            sy, ey = ey, sy
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
                self._c_avg.set_value(f"{avg:+.2f}%", ACCENT_GREEN if avg >= 0 else ACCENT_RED)
                self._c_up.set_value(f"{ups} / {len(data)}")
            else:
                for c in (self._c_best, self._c_worst, self._c_avg, self._c_up):
                    c.set_value("—")
            self._status(f"Annual heatmap  {base}/{quote}  {sy}–{ey}", "ok")

        self._run(work, done, skeleton=self._skeleton)
