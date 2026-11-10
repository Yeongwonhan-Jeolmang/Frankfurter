"""2. Historical — every rate for a single past date."""

from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtWidgets import QHBoxLayout, QWidget

from ui.tabs.base import MIN_DATE, BaseTab, code_of, parse_date, saved_or
from ui.theme import *
from ui.widgets import (
    ChipGrid,
    CodeCombo,
    DateEntry,
    Field,
    RateTable,
    SectionHeader,
    Sidebar,
    SkeletonOverlay,
    StatCard,
    hbox,
    make_button,
)


class HistoricalTab(BaseTab):
    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._last: dict = {}
        self._build()

    def _build(self):
        s = self._settings
        sb = Sidebar("Historical Lookup")
        self._base_e = CodeCombo(self._codes, saved_or(s, "hist_base", "EUR"))
        sb.add(Field("Base Currency", self._base_e))
        self._date_e = DateEntry(saved_or(s, "hist_date", "2010-01-04"))
        sb.add(Field("Date (YYYY-MM-DD)", self._date_e))

        # Step one business day back / forward and re-fetch
        prev_b = make_button("◀  Prev day", lambda: self._step_day(-1), "chip")
        next_b = make_button("Next day  ▶", lambda: self._step_day(1), "chip")
        sb.add(hbox(prev_b, next_b, spacing=4))
        sb.add(make_button("🔍  Fetch", self._fetch), before=PAD_SM)

        sb.separator()
        sb.caption("Quick Jump")
        this_year = date.today().year
        sb.add(ChipGrid([
            (str(yr), lambda y=yr: self._jump_year(y))
            for yr in range(this_year, this_year - 12, -1)
        ]))

        sb.separator()
        sb.add(make_button("⬇  CSV", lambda: self._export_csv_data(self._last, "historical"), "secondary"))
        sb.add(make_button("⬇  JSON", lambda: self._export_json_data(self._last, "historical"), "secondary"))

        main = self._split(sb)
        cards = QWidget()
        cl = QHBoxLayout(cards)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(PAD_MD)
        self._c_base = StatCard("Base")
        self._c_date2 = StatCard("Date", color=ACCENT_BLUE)
        self._c_cnt = StatCard("Currencies", color=TEXT_PRIMARY)
        for c in (self._c_base, self._c_date2, self._c_cnt):
            cl.addWidget(c)
        main.addWidget(cards)
        main.addSpacing(PAD_MD)
        main.addWidget(SectionHeader("Rates on Selected Date  (double-click to copy)"))
        self._table = RateTable(
            settings=self._settings,
            on_copy=lambda t: self._status(f"Copied  “{t}”", "ok"),
        )
        main.addWidget(self._table, 1)
        self._skeleton = SkeletonOverlay(self._table)

    def _jump_year(self, yr):
        # The first business day of the current year may not exist yet
        target = min(date(yr, 1, 2), date.today())
        self._date_e.set(target.isoformat())
        self._fetch()

    def _step_day(self, delta):
        d = parse_date(self._date_e.get()) or date.today()
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
        base = code_of(self._base_e, "EUR")
        d = parse_date(self._date_e.get())
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
                f"Historical  •  {actual_base}  •  {actual_date}  •  {len(rates)} pairs", "ok"
            )

        self._run(work, done, skeleton=self._skeleton)
