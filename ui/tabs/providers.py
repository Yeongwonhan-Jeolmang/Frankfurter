"""11. Providers — the data providers behind the Frankfurter API."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ui.tabs.base import BaseTab
from ui.theme import *
from ui.widgets import SearchEntry, SectionHeader, Sidebar, StatCard, hbox, make_button


class ProvidersTab(BaseTab):
    COLUMNS = (
        ("Key", ACCENT_GOLD),
        ("Name", TEXT_PRIMARY),
        ("Country", TEXT_MUTED),
        ("Currencies", ACCENT_BLUE),
    )

    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._row_text: list[str] = []
        self._build()
        self._fetch()

    def _build(self):
        sb = Sidebar("Data Providers")
        sb.add(
            make_button("⟳  Load Providers", self._fetch), before=PAD_SM, after=PAD_SM
        )
        sb.note("Frankfurter sources data from 84 central banks worldwide.")

        main = self._split(sb)
        cards = QWidget()
        cl = QHBoxLayout(cards)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(PAD_MD)
        self._c_cnt = StatCard("Total Providers")
        self._c_ccy = StatCard("Currencies Covered", color=ACCENT_BLUE)
        cl.addWidget(self._c_cnt)
        cl.addWidget(self._c_ccy)
        main.addWidget(cards)
        main.addSpacing(PAD_MD)

        self._search = SearchEntry(
            "Filter by key, name or country…", on_change=self._apply_filter
        )
        self._search.setFixedWidth(300)
        main.addWidget(hbox(SectionHeader("Provider List"), None, self._search))

        t = QTableWidget(0, len(self.COLUMNS))
        t.setHorizontalHeaderLabels([c for c, _ in self.COLUMNS])
        t.verticalHeader().hide()
        t.verticalHeader().setDefaultSectionSize(28)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setAlternatingRowColors(True)
        t.setShowGrid(False)
        t.setWordWrap(False)
        hh = t.horizontalHeader()
        hh.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table = t
        main.addWidget(t, 1)

    def _apply_filter(self, text):
        text = text.upper()
        for r, blob in enumerate(self._row_text):
            self._table.setRowHidden(r, bool(text) and text not in blob)

    def _fetch(self):
        def work():
            return self._client.get_providers()

        def done(data, err):
            if err:
                self._status(f"Error: {err}", "error")
                return
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

            t = self._table
            t.setRowCount(len(providers))
            self._row_text = []
            body, mono = qfont(FONT_BODY), qfont(FONT_MONO)
            for r, prov in enumerate(providers):
                if isinstance(prov, dict):
                    key = str(prov.get("key", prov.get("code", "—")) or "—")
                    name = str(prov.get("name", "—") or "—")
                    country = str(prov.get("country", "—") or "—")
                    ccys = prov.get("currencies") or []  # the API may send null
                    n_ccy = str(len(ccys))
                    tip = ", ".join(c for c in ccys if isinstance(c, str))
                else:
                    key = name = str(prov)
                    country, n_ccy, tip = "—", "—", ""
                for c, (txt, (_h, color)) in enumerate(
                    zip((key, name, country, n_ccy), self.COLUMNS)
                ):
                    it = QTableWidgetItem(txt)
                    it.setForeground(QColor(color))
                    it.setFont(mono if c in (0, 3) else body)
                    if c == 3 and tip:
                        it.setToolTip(tip)
                    t.setItem(r, c, it)
                self._row_text.append(f"{key} {name} {country}".upper())
            self._apply_filter(self._search.get())
            self._status(f"Loaded {len(providers)} providers", "ok")

        self._run(work, done)
