"""4. Converter — real-time conversion with reverse mode and history."""

from __future__ import annotations

import math
from datetime import date, datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QLineEdit,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ui.tabs.base import MIN_DATE, BaseTab, code_of, parse_date, saved_or, scrollable
from ui.theme import *
from ui.widgets import (
    CodeCombo,
    DateEntry,
    Field,
    HSeparator,
    SectionHeader,
    hbox,
    make_button,
    make_label,
    set_error,
)


class ConverterTab(BaseTab):
    def __init__(self, client, currency_names, status_cb, settings=None, parent=None):
        super().__init__(client, currency_names, status_cb, settings, parent)
        self._last_result_text: str = "—"
        # (base, quote, requested_date, rate, rate_date) of the last fetch —
        # lets the amount / direction update instantly without a network call
        self._last_rate: tuple | None = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        root.addWidget(scrollable(body, min_w=760, min_h=600))
        outer = QVBoxLayout(body)
        outer.setContentsMargins(60, 30, 60, 20)
        outer.setSpacing(PAD_SM)
        outer.addWidget(make_label(
            "Currency Converter", FONT_DISPLAY, ACCENT_GOLD, align=Qt.AlignmentFlag.AlignCenter
        ))
        outer.addSpacing(PAD_LG)

        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(PAD_LG, PAD_LG, PAD_LG, PAD_LG)
        cl.setSpacing(PAD_MD)
        outer.addWidget(card)

        # Row 1: amount, from, ⇄, to, convert
        s = self._settings
        row1 = QGridLayout()
        row1.setHorizontalSpacing(PAD_MD)
        self._amt = QLineEdit("1000")
        self._amt.setObjectName("BigAmount")
        self._amt.setPlaceholderText("1000.00")
        self._amt.setMinimumWidth(160)
        self._amt.textEdited.connect(lambda _t: self._live_update())
        self._from = CodeCombo(self._codes, saved_or(s, "conv_from", "EUR"),
                               command=lambda _t: self._reconvert())
        self._to = CodeCombo(self._codes, saved_or(s, "conv_to", "USD"),
                             command=lambda _t: self._reconvert())
        for cb in (self._from, self._to):
            cb.setMinimumWidth(130)
        swap = make_button("⇄", self._swap, "glyph", width=44, tooltip="Swap currencies")
        convert = make_button("Convert", self._convert, width=110)
        row1.addWidget(Field("Amount", self._amt), 0, 0)
        row1.addWidget(Field("From", self._from), 0, 1)
        row1.addWidget(Field("", swap), 0, 2, Qt.AlignmentFlag.AlignBottom)
        row1.addWidget(Field("To", self._to), 0, 3)
        row1.addWidget(Field("", convert), 0, 4, Qt.AlignmentFlag.AlignBottom)
        row1.setColumnStretch(0, 3)
        row1.setColumnStretch(1, 2)
        row1.setColumnStretch(3, 2)
        # Align the swap / convert buttons with the inputs, not the field captions
        swap.setFixedHeight(36)
        convert.setFixedHeight(36)
        row1.setContentsMargins(0, 0, 0, 0)
        cl.addLayout(row1)

        # Direction toggle (reverse mode)
        self._dir_group = QButtonGroup(self)
        self._fwd = QRadioButton("Base → Quote")
        self._rev = QRadioButton("Quote → Base  (reverse)")
        self._fwd.setChecked(True)
        for rb in (self._fwd, self._rev):
            self._dir_group.addButton(rb)
        self._fwd.toggled.connect(lambda _on: self._live_update())
        cl.addWidget(hbox(make_label("Direction:", FONT_SMALL, TEXT_MUTED), self._fwd, self._rev, None,
                          spacing=PAD_MD))

        # Optional historical date
        self._date_e = DateEntry()
        self._date_e.setFixedWidth(170)
        self._date_e.picked.connect(lambda _d: self._reconvert())
        latest = make_button("Latest", lambda: (self._date_e.set(""), self._reconvert()), "muted", width=64)
        cl.addWidget(hbox(make_label("Date (leave blank for latest):", FONT_SMALL, TEXT_MUTED),
                          self._date_e, latest, None, spacing=PAD_MD))

        cl.addWidget(HSeparator())

        self._res = make_label("—", (FONT_DISPLAY[0], 28, "bold"), ACCENT_GOLD,
                               align=Qt.AlignmentFlag.AlignCenter)
        self._res.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._detail = make_label("", FONT_MONO, TEXT_MUTED, align=Qt.AlignmentFlag.AlignCenter)
        self._detail.setWordWrap(True)
        cl.addWidget(self._res)
        cl.addWidget(self._detail)
        self._copy_btn = make_button("📋  Copy Result", self._copy_to_clipboard, "outline", width=150)
        cl.addWidget(self._copy_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        outer.addSpacing(PAD_MD)
        outer.addWidget(SectionHeader("Conversion History"))
        self._hist = QPlainTextEdit()
        self._hist.setReadOnly(True)
        self._hist.setMinimumHeight(120)
        outer.addWidget(self._hist, 1)
        outer.addWidget(make_button("🗑  Clear History", self._hist.clear, "secondary"),
                        0, Qt.AlignmentFlag.AlignRight)

    # Enter key / F5 dispatch from the main window
    def _fetch(self):
        self._convert()

    def _swap(self):
        f, t = self._from.get(), self._to.get()
        self._from.set(t)
        self._to.set(f)
        self._reconvert()

    def _reconvert(self):
        """Re-run the conversion if one has already been shown."""
        if self._last_rate is not None:
            self._convert()

    @staticmethod
    def _parse_amount(text):
        """Accept '1,000.50', '1 000', '1_000' and the like."""
        cleaned = text.replace(",", "").replace("_", "").replace(" ", "").strip()
        amount = float(cleaned)
        if not math.isfinite(amount):
            raise ValueError("non-finite")
        return amount

    def _live_update(self):
        """Recompute from the cached rate as the user types — no network."""
        if self._last_rate is None:
            return
        base, quote, req_date, rate, rate_date = self._last_rate
        if (
            code_of(self._from, "EUR") != base
            or code_of(self._to, "USD") != quote
            or (self._date_e.get().strip() or None) != req_date
        ):
            return
        try:
            amount = self._parse_amount(self._amt.text())
        except (ValueError, TypeError):
            set_error(self._amt, True)
            return
        set_error(self._amt, False)
        self._show_result(amount, base, quote, rate, rate_date, log=False)

    def _copy_to_clipboard(self):
        text = self._last_result_text
        if text and text != "—":
            QGuiApplication.clipboard().setText(text)
            self._copy_btn.setText("✓  Copied!")
            QTimer.singleShot(1500, lambda: self._copy_btn.setText("📋  Copy Result"))
            self._status("Result copied to clipboard", "ok")

    def _convert(self):
        try:
            amount = self._parse_amount(self._amt.text())
        except (ValueError, TypeError):
            set_error(self._amt, True)
            self._status("Invalid amount", "error")
            return
        set_error(self._amt, False)

        base = code_of(self._from, "EUR")
        quote = code_of(self._to, "USD")
        on_date = self._date_e.get().strip() or None
        if on_date is not None:
            d = parse_date(on_date)
            bad = d is None or d > date.today() or d < MIN_DATE
            self._date_e.flag_error(bad)
            if bad:
                self._status("Date must be YYYY-MM-DD, between 1948 and today", "error")
                return
        else:
            self._date_e.flag_error(False)
        if not self._check_codes(base, quote):
            return
        if self._settings:
            self._settings.update(conv_from=base, conv_to=quote)

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
            rate = float(rate)
            rate_date = data.get("date") or on_date or "latest"
            self._last_rate = (base, quote, on_date, rate, rate_date)
            # The amount may have changed while the request was in flight
            try:
                amt = self._parse_amount(self._amt.text())
            except (ValueError, TypeError):
                amt = amount
            self._show_result(amt, base, quote, rate, rate_date, log=True)

        self._run(work, done)

    def _show_result(self, amount, base, quote, rate, rate_date, log=True):
        if self._rev.isChecked():
            # amount is in *quote* currency; convert back to base
            converted = amount / rate
            log_from, log_to = quote, base
        else:
            converted = amount * rate
            log_from, log_to = base, quote
        result_text = f"{amount:,.2f} {log_from}  =  {converted:,.4f} {log_to}"
        self._last_result_text = result_text
        self._res.setText(result_text)
        self._detail.setText(
            f"1 {base} = {rate:.6f} {quote}  •  1 {quote} = {1 / rate:.6f} {base}  •  Date: {rate_date}"
        )
        if not log:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self._hist.appendPlainText(
            f"[{ts}]  {amount:,.2f} {log_from} → {converted:,.4f} {log_to}  @ {rate:.6f}  ({rate_date})"
        )
        self._status(f"Converted  {amount:,.2f} {log_from} → {log_to}", "ok")
