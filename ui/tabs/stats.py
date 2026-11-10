"""6. Statistics — summary cards and a chart for one pair."""

from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtWidgets import QGridLayout, QWidget

from ui.chart_panel import ChartPanel
from ui.tabs.base import BaseTab, code_of, quick_range_chips, saved_or, validate_range
from ui.theme import *
from ui.widgets import (
    CodeCombo,
    DateEntry,
    Field,
    SectionHeader,
    Sidebar,
    SkeletonOverlay,
    StatCard,
    make_button,
)

_SPECS = [
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


class StatsTab(BaseTab):
    COLS = 7

    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._build()

    def _build(self):
        s = self._settings
        year_ago = (date.today() - timedelta(days=365)).isoformat()
        sb = Sidebar("Statistics")
        self._base_e = CodeCombo(self._codes, saved_or(s, "stats_base", "EUR"))
        self._quote_e = CodeCombo(self._codes, saved_or(s, "stats_quote", "USD"))
        self._start_e = DateEntry(saved_or(s, "stats_start", year_ago))
        self._end_e = DateEntry(saved_or(s, "stats_end", date.today().isoformat()))
        sb.add(Field("Base", self._base_e))
        sb.add(Field("Quote", self._quote_e))
        sb.add(Field("Start", self._start_e))
        sb.add(Field("End", self._end_e))
        sb.add(make_button("📐  Analyse", self._fetch), before=PAD_SM, after=PAD_SM)
        sb.separator()
        sb.caption("Quick Ranges")
        sb.add(quick_range_chips(self._start_e, self._end_e, self._fetch))

        main = self._split(sb)
        main.addWidget(SectionHeader("Statistical Summary"))
        main.addSpacing(PAD_SM)
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(PAD_SM)
        self._cards: dict[str, StatCard] = {}
        for i, (key, lbl, col) in enumerate(_SPECS):
            c = StatCard(lbl, color=col)
            grid.addWidget(c, i // self.COLS, i % self.COLS)
            self._cards[key] = c
        for col in range(self.COLS):
            grid.setColumnStretch(col, 1)
        main.addWidget(grid_w)
        main.addSpacing(PAD_MD)
        main.addWidget(SectionHeader("Rate Chart"))
        self._chart = ChartPanel()
        main.addWidget(self._chart, 1)
        self._skeleton = SkeletonOverlay(self._chart)

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
