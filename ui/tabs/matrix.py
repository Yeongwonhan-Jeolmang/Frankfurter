"""8. Matrix — N×N cross-rate matrix, chart + table."""

from __future__ import annotations

import csv

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
)

from exports.exporter import export_to_json
from ui.chart_panel import ChartPanel
from ui.tabs.base import BaseTab
from ui.theme import *
from ui.widgets import (
    CurrencyChecklist,
    SearchEntry,
    Sidebar,
    SkeletonOverlay,
    make_button,
    set_color,
)


class MatrixTab(BaseTab):
    MAX_CODES = 10
    DEFAULTS = ["EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY"]

    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._last_matrix: dict = {}
        self._last_codes: list[str] = []
        self._build()

    def _build(self):
        sb = Sidebar("Cross-Rate Matrix")
        self._sel_lbl = sb.caption("")
        sb.add(
            SearchEntry(
                "Filter currencies…", on_change=lambda t: self._checks.apply_filter(t)
            )
        )
        saved = self._settings.get("matrix_codes") if self._settings else None
        self._checks = CurrencyChecklist(
            self._codes, self._names, saved or self.DEFAULTS, height=240
        )
        self._checks.changed.connect(self._update_sel_count)
        sb.add(self._checks)
        self._update_sel_count()
        sb.add(
            make_button("🔢  Build Matrix", self._fetch), before=PAD_MD, after=PAD_SM
        )
        sb.note("Each cell shows the rate:\nRow currency → Column currency")
        sb.separator()
        sb.add(make_button("⬇  CSV", self._do_csv, "secondary"))
        sb.add(make_button("⬇  JSON", self._do_json, "secondary"))

        main = self._split(sb, margins=PAD_MD)
        # Chart above, table below; the user can drag the divider
        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(PAD_MD)
        self._chart = ChartPanel(show_types=False)
        split.addWidget(self._chart)
        self._table = QTableWidget()
        self._table.setObjectName("Framed")
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.ContiguousSelection
        )
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setMinimumHeight(120)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self._table.verticalHeader().setDefaultSectionSize(26)
        vh = self._table.verticalHeader()
        vh.setStyleSheet(
            f"QHeaderView::section {{ color: {ACCENT_GOLD}; background: {BG_CARD};"
            f" border: none; border-right: 1px solid {BORDER_COLOR}; padding: 0 8px; }}"
        )
        split.addWidget(self._table)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([520, 220])
        main.addWidget(split, 1)
        self._skeleton = SkeletonOverlay(self._chart)

    def _update_sel_count(self):
        n = len(self._checks.selected())
        self._sel_lbl.setText(f"Selected {n}  (2–{self.MAX_CODES})")
        set_color(
            self._sel_lbl, ACCENT_RED if n > self.MAX_CODES or n < 2 else TEXT_MUTED
        )

    def _fill_table(self, matrix, codes):
        t = self._table
        t.clear()
        t.setRowCount(len(codes))
        t.setColumnCount(len(codes))
        t.setHorizontalHeaderLabels(codes)
        t.setVerticalHeaderLabels(codes)
        mono = qfont(FONT_MONO)
        for i, b in enumerate(codes):
            for j, q in enumerate(codes):
                val = matrix.get(b, {}).get(q)
                it = QTableWidgetItem(f"{val:.4f}" if val is not None else "—")
                it.setFont(mono)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it.setForeground(
                    QColor(
                        ACCENT_GOLD
                        if b == q
                        else TEXT_PRIMARY if val is not None else TEXT_DIM
                    )
                )
                it.setToolTip(
                    f"1 {b} = {val} {q}" if val is not None else f"{b}/{q}: no data"
                )
                t.setItem(i, j, it)

    def _do_csv(self):
        if not self._last_matrix or not self._last_codes:
            self._status("Nothing to export yet — build a matrix first", "error")
            return

        def write(_payload, path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["base", "quote", "rate"])
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

        self._write_export(write, None, "matrix", "csv")

    def _do_json(self):
        if not self._last_matrix:
            self._status("Nothing to export yet — build a matrix first", "error")
            return
        self._write_export(
            export_to_json,
            {"codes": self._last_codes, "matrix": self._last_matrix},
            "matrix",
            "json",
        )

    def _fetch(self):
        selected = self._checks.selected()
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
            self._fill_table(matrix, codes)
            msg = f"Cross-rate matrix for {len(codes)} currencies"
            if len(selected) > self.MAX_CODES:
                msg += f"  •  only the first {self.MAX_CODES} selected are used"
            self._status(msg, "ok")

        self._run(work, done, skeleton=self._skeleton)
