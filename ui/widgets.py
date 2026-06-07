"""
Reusable custom widgets brought to you by Florian van den Bersselaar
"""

import tkinter as tk
import customtkinter as ctk
from ui.theme import *


class StatCard(ctk.CTkFrame):
    def __init__(self, master, label, value="—", color=None, **kw):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=CORNER_RADIUS,
            border_width=1,
            border_color=BORDER_COLOR,
            **kw,
        )
        self._color = color or ACCENT_GOLD
        self._lbl = ctk.CTkLabel(
            self, text=label.upper(), font=FONT_LABEL, text_color=TEXT_MUTED
        )
        self._lbl.pack(anchor="w", padx=PAD_MD, pady=(PAD_MD, 2))
        self._val = ctk.CTkLabel(
            self, text=value, font=FONT_MONO_LG, text_color=self._color
        )
        self._val.pack(anchor="w", padx=PAD_MD, pady=(0, PAD_MD))

    def set_value(self, value, color=None):
        self._val.configure(text=value, text_color=color or self._color)

    def set_label(self, label):
        self._lbl.configure(text=label.upper())


class SectionHeader(ctk.CTkFrame):
    def __init__(self, master, text, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        ctk.CTkFrame(
            self, width=4, height=20, fg_color=ACCENT_GOLD, corner_radius=2
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(self, text=text, font=FONT_HEADING, text_color=TEXT_PRIMARY).pack(
            side="left"
        )


class HSeparator(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, height=1, fg_color=BORDER_COLOR, **kw)


class LabelledCombo(ctk.CTkFrame):
    def __init__(self, master, label, values, width=160, command=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        if label:
            ctk.CTkLabel(self, text=label, font=FONT_LABEL, text_color=TEXT_MUTED).pack(
                anchor="w"
            )
        self.combo = ctk.CTkComboBox(
            self,
            values=values,
            width=width,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            button_color=ACCENT_GOLD,
            dropdown_fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            font=FONT_BODY,
            command=command,
        )
        self.combo.pack(fill="x")

    def get(self):
        return self.combo.get()

    def set(self, v):
        self.combo.set(v)

    def configure_values(self, values):
        self.combo.configure(values=values)


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, height=28, fg_color=BG_CARD, corner_radius=0, **kw)
        self._dot = ctk.CTkLabel(
            self,
            text="●",
            font=("Helvetica Neue", 10),
            text_color=ACCENT_GREEN,
            width=20,
        )
        self._dot.pack(side="left", padx=(PAD_MD, 4))
        self._msg = ctk.CTkLabel(
            self, text="Ready", font=FONT_SMALL, text_color=TEXT_MUTED
        )
        self._msg.pack(side="left")
        ctk.CTkLabel(
            self,
            text="api.frankfurter.dev  •  ECB Data",
            font=FONT_SMALL,
            text_color=TEXT_DIM,
        ).pack(side="right", padx=PAD_MD)

    def set_status(self, msg, state="ok"):
        c = {"ok": ACCENT_GREEN, "loading": ACCENT_GOLD, "error": ACCENT_RED}
        self._dot.configure(text_color=c.get(state, ACCENT_GOLD))
        self._msg.configure(text=msg)


class RateTable(ctk.CTkScrollableFrame):
    HEADERS = ("Currency", "Code", "Rate", "Inverse", "Change")

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG_DARK, **kw)
        self._rows: list = []
        self._prev: dict = {}
        self._filter = ""
        self._raw_rates: dict = {}
        self._raw_names: dict = {}
        self._raw_base = "EUR"
        self._build_header()

    def _build_header(self):
        for c, h in enumerate(self.HEADERS):
            ctk.CTkLabel(
                self, text=h, font=FONT_SUBHEAD, text_color=ACCENT_GOLD, anchor="w"
            ).grid(row=0, column=c, sticky="ew", padx=(PAD_SM, PAD_MD), pady=4)
        ctk.CTkFrame(self, height=1, fg_color=BORDER_COLOR).grid(
            row=1, column=0, columnspan=5, sticky="ew", pady=2
        )
        for c in range(5):
            self.grid_columnconfigure(c, weight=1)

    def populate(self, rates, currency_names, base, filter_text=""):
        self._raw_rates = rates
        self._raw_names = currency_names
        self._raw_base = base
        self._filter = filter_text.upper()
        self._render()

    def set_filter(self, text):
        self._filter = text.upper()
        self._render()

    def _render(self):
        for row in self._rows:
            for w in row:
                w.destroy()
        self._rows.clear()

        items = sorted(self._raw_rates.items())
        if self._filter:
            items = [
                (c, r)
                for c, r in items
                if self._filter in c
                or self._filter in self._raw_names.get(c, "").upper()
            ]

        for i, (code, rate) in enumerate(items):
            bg = BG_CARD if i % 2 == 0 else BG_DARK
            name = self._raw_names.get(code, code)
            inv = round(1 / rate, 6) if rate else 0
            prev = self._prev.get(code)
            if prev is None:
                ct, cc = "—", TEXT_MUTED
            elif rate > prev:
                ct, cc = f"▲ {(rate-prev)/prev*100:.4f}%", ACCENT_GREEN
            elif rate < prev:
                ct, cc = f"▼ {(prev-rate)/prev*100:.4f}%", ACCENT_RED
            else:
                ct, cc = "→ 0.0000%", TEXT_MUTED

            vals = [name, code, f"{rate:.6f}", f"{inv:.6f}", ct]
            colors = [TEXT_PRIMARY, ACCENT_GOLD, TEXT_PRIMARY, TEXT_MUTED, cc]
            row_w = []
            for c, (v, col) in enumerate(zip(vals, colors)):
                lbl = ctk.CTkLabel(
                    self,
                    text=v,
                    font=FONT_MONO if c >= 2 else FONT_BODY,
                    text_color=col,
                    anchor="w",
                    fg_color=bg,
                    corner_radius=0,
                )
                lbl.grid(
                    row=i + 2, column=c, sticky="ew", padx=(PAD_SM, PAD_MD), pady=2
                )
                row_w.append(lbl)
            self._rows.append(row_w)
        self._prev = dict(self._raw_rates)


class SearchEntry(ctk.CTkFrame):
    """Search/filter text field with clear button."""

    def __init__(self, master, placeholder="Search…", on_change=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._cb = on_change
        self._var = tk.StringVar()
        self._var.trace_add("write", self._changed)
        self._entry = ctk.CTkEntry(
            self,
            textvariable=self._var,
            placeholder_text=placeholder,
            fg_color=BG_INPUT,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_BODY,
            height=32,
        )
        self._entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            self,
            text="✕",
            width=32,
            height=32,
            fg_color=BG_INPUT,
            hover_color=BG_HOVER,
            text_color=TEXT_MUTED,
            font=FONT_SMALL,
            command=self.clear,
        ).pack(side="left", padx=(2, 0))

    def _changed(self, *_):
        if self._cb:
            self._cb(self._var.get())

    def clear(self):
        self._var.set("")

    def get(self):
        return self._var.get()


class WatchlistPanel(ctk.CTkScrollableFrame):
    """Compact live watchlist rows."""

    def __init__(self, master, on_select=None, **kw):
        super().__init__(master, fg_color=BG_DARK, **kw)
        self._on_select = on_select
        self._pairs: list[tuple] = []
        self._rows: list = []

    def set_pairs(self, pairs: list[tuple]):
        self._pairs = pairs

    def refresh(self, snapshots: list[dict]):
        for w in self._rows:
            w.destroy()
        self._rows.clear()
        for i, snap in enumerate(snapshots):
            bg = BG_CARD if i % 2 == 0 else BG_DARK
            base = snap.get("base", "?")
            quote = snap.get("quote", "?")
            rate = snap.get("rate")
            label = f"{base}/{quote}"
            rate_s = f"{rate:.5f}" if rate else "N/A"

            row = ctk.CTkFrame(self, fg_color=bg, corner_radius=4)
            row.pack(fill="x", pady=1)

            ctk.CTkLabel(
                row,
                text=label,
                font=FONT_SUBHEAD,
                text_color=ACCENT_GOLD,
                width=80,
                anchor="w",
            ).pack(side="left", padx=PAD_SM, pady=6)
            ctk.CTkLabel(
                row, text=rate_s, font=FONT_MONO, text_color=TEXT_PRIMARY
            ).pack(side="left", padx=PAD_SM)
            date_s = snap.get("date", "")
            ctk.CTkLabel(row, text=date_s, font=FONT_SMALL, text_color=TEXT_DIM).pack(
                side="right", padx=PAD_MD
            )
            self._rows.append(row)


class LoadingOverlay(ctk.CTkFrame):
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, master, **kw):
        super().__init__(
            master, fg_color=BG_CARD + "CC", corner_radius=CORNER_RADIUS, **kw
        )
        self._lbl = ctk.CTkLabel(
            self, text="⠋  Fetching…", font=("Courier New", 13), text_color=ACCENT_GOLD
        )
        self._lbl.pack(expand=True)
        self._idx = 0
        self._running = False

    def start(self):
        self._running = True
        self._tick()

    def stop(self):
        self._running = False

    def _tick(self):
        if not self._running:
            return
        self._idx = (self._idx + 1) % len(self.FRAMES)
        self._lbl.configure(text=f"{self.FRAMES[self._idx]}  Fetching data…")
        self.after(80, self._tick)
