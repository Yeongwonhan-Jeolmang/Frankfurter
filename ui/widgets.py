"""
Reusable custom widgets brought to you by Florian van den Bersselaar
"""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk
from ui.theme import *


class StatCard(ctk.CTkFrame):
    def __init__(self, master, label: str, value: str = "—", color=None, **kw):
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

    def set_value(self, value: str, color=None) -> None:
        self._val.configure(text=value, text_color=color or self._color)

    def set_label(self, label: str) -> None:
        self._lbl.configure(text=label.upper())


class SectionHeader(ctk.CTkFrame):
    def __init__(self, master, text: str, **kw):
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
    def __init__(
        self, master, label: str, values, width: int = 160, command=None, **kw
    ):
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

    def get(self) -> str:
        return self.combo.get()

    def set(self, v: str) -> None:
        self.combo.set(v)

    def configure_values(self, values) -> None:
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

    def set_status(self, msg: str, state: str = "ok") -> None:
        c = {"ok": ACCENT_GREEN, "loading": ACCENT_GOLD, "error": ACCENT_RED}
        self._dot.configure(text_color=c.get(state, ACCENT_GOLD))
        self._msg.configure(text=msg)


class RateTable(ctk.CTkScrollableFrame):
    """
    Scrollable table of exchange rates.

    Performance: rows are created once and their labels are reconfigured
    in-place rather than destroyed and recreated on every filter change.
    Rows beyond the visible set are hidden with grid_remove() instead of
    being destroyed.
    """

    HEADERS = ("Currency", "Code", "Rate", "Inverse", "Change")
    _MAX_ROWS = 220  # upper bound — pre-allocate this many label rows

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG_DARK, **kw)
        self._prev: dict[str, float] = {}
        self._filter: str = ""
        self._raw_rates: dict[str, float] = {}
        self._raw_names: dict[str, str] = {}
        self._raw_base: str = "EUR"
        # Pre-allocated label widgets: list of (row_frame, [label, ...])
        self._pool: list[tuple[ctk.CTkFrame, list[ctk.CTkLabel]]] = []
        self._build_header()
        self._preallocate_pool()

    def _build_header(self) -> None:
        for c, h in enumerate(self.HEADERS):
            ctk.CTkLabel(
                self, text=h, font=FONT_SUBHEAD, text_color=ACCENT_GOLD, anchor="w"
            ).grid(row=0, column=c, sticky="ew", padx=(PAD_SM, PAD_MD), pady=4)
        ctk.CTkFrame(self, height=1, fg_color=BORDER_COLOR).grid(
            row=1, column=0, columnspan=5, sticky="ew", pady=2
        )
        for c in range(5):
            self.grid_columnconfigure(c, weight=1)

    def _preallocate_pool(self) -> None:
        """Create _MAX_ROWS hidden label rows up front so _render never destroys widgets."""
        for i in range(self._MAX_ROWS):
            bg = BG_CARD if i % 2 == 0 else BG_DARK
            labels: list[ctk.CTkLabel] = []
            for c in range(5):
                lbl = ctk.CTkLabel(
                    self,
                    text="",
                    font=FONT_MONO if c >= 2 else FONT_BODY,
                    text_color=TEXT_PRIMARY,
                    anchor="w",
                    fg_color=bg,
                    corner_radius=0,
                )
                lbl.grid(
                    row=i + 2,
                    column=c,
                    sticky="ew",
                    padx=(PAD_SM, PAD_MD),
                    pady=2,
                )
                lbl.grid_remove()  # hidden until needed
                labels.append(lbl)
            self._pool.append((ctk.CTkFrame(self, fg_color="transparent"), labels))

    def populate(
        self,
        rates: dict[str, float],
        currency_names: dict[str, str],
        base: str,
        filter_text: str = "",
    ) -> None:
        self._raw_rates = rates
        self._raw_names = currency_names
        self._raw_base = base
        self._filter = filter_text.upper()
        self._render()

    def set_filter(self, text: str) -> None:
        self._filter = text.upper()
        self._render()

    def _render(self) -> None:
        items = sorted(self._raw_rates.items())
        if self._filter:
            items = [
                (c, r)
                for c, r in items
                if self._filter in c
                or self._filter in self._raw_names.get(c, "").upper()
            ]

        # Hide all pool rows first
        for _, labels in self._pool:
            for lbl in labels:
                lbl.grid_remove()

        for i, (code, rate) in enumerate(items):
            if i >= self._MAX_ROWS:
                break
            _, labels = self._pool[i]
            bg = BG_CARD if i % 2 == 0 else BG_DARK

            name = self._raw_names.get(code, code)
            inv = round(1 / rate, 6) if rate else 0
            prev = self._prev.get(code)
            if prev is None:
                ct: str = "—"
                cc = TEXT_MUTED
            elif rate > prev:
                ct = f"▲ {(rate - prev) / prev * 100:.4f}%"
                cc = ACCENT_GREEN
            elif rate < prev:
                ct = f"▼ {(prev - rate) / prev * 100:.4f}%"
                cc = ACCENT_RED
            else:
                ct = "→ 0.0000%"
                cc = TEXT_MUTED

            vals = [name, code, f"{rate:.6f}", f"{inv:.6f}", ct]
            colors = [TEXT_PRIMARY, ACCENT_GOLD, TEXT_PRIMARY, TEXT_MUTED, cc]

            for c, (lbl, v, col) in enumerate(zip(labels, vals, colors)):
                lbl.configure(
                    text=v,
                    text_color=col,
                    fg_color=bg,
                    font=FONT_MONO if c >= 2 else FONT_BODY,
                )
                lbl.grid()  # make visible

        self._prev = dict(self._raw_rates)


class SearchEntry(ctk.CTkFrame):
    """
    Search/filter text field with clear button.
    Debounces keystrokes by 120 ms so rapid typing doesn't hammer the
    on_change callback on every single character.
    """

    _DEBOUNCE_MS = 120

    def __init__(self, master, placeholder: str = "Search…", on_change=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._cb = on_change
        self._var = tk.StringVar()
        self._var.trace_add("write", self._on_write)
        self._after_id: str | None = None
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

    def _on_write(self, *_) -> None:
        # Cancel any pending debounce timer
        if self._after_id is not None:
            try:
                self._entry.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self._entry.after(self._DEBOUNCE_MS, self._fire)

    def _fire(self) -> None:
        self._after_id = None
        if self._cb:
            self._cb(self._var.get())

    def clear(self) -> None:
        self._var.set("")

    def get(self) -> str:
        return self._var.get()


class WatchlistPanel(ctk.CTkScrollableFrame):
    """Compact live watchlist rows — reuses widgets to avoid destroy/recreate churn."""

    _COLS = 3  # pair label, rate, date

    def __init__(self, master, on_select=None, **kw):
        super().__init__(master, fg_color=BG_DARK, **kw)
        self._on_select = on_select
        self._pairs: list[tuple[str, str]] = []
        # Pool of (frame, [label, label, label]) reused in place
        self._pool: list[tuple[ctk.CTkFrame, list[ctk.CTkLabel]]] = []

    def set_pairs(self, pairs: list[tuple[str, str]]) -> None:
        self._pairs = pairs

    def _ensure_pool(self, n: int) -> None:
        """Grow the pool to at least n rows."""
        while len(self._pool) < n:
            i = len(self._pool)
            bg = BG_CARD if i % 2 == 0 else BG_DARK
            row = ctk.CTkFrame(self, fg_color=bg, corner_radius=4)
            labels = [
                ctk.CTkLabel(
                    row,
                    text="",
                    font=FONT_SUBHEAD,
                    text_color=ACCENT_GOLD,
                    width=80,
                    anchor="w",
                ),
                ctk.CTkLabel(row, text="", font=FONT_MONO, text_color=TEXT_PRIMARY),
                ctk.CTkLabel(row, text="", font=FONT_SMALL, text_color=TEXT_DIM),
            ]
            labels[0].pack(side="left", padx=PAD_SM, pady=6)
            labels[1].pack(side="left", padx=PAD_SM)
            labels[2].pack(side="right", padx=PAD_MD)
            self._pool.append((row, labels))

    def refresh(self, snapshots: list[dict]) -> None:
        self._ensure_pool(len(snapshots))
        for i, snap in enumerate(snapshots):
            base = str(snap.get("base", "?"))
            quote = str(snap.get("quote", "?"))
            rate = snap.get("rate")
            rate_s = f"{rate:.5f}" if rate else "N/A"
            date_s = str(snap.get("date", ""))
            bg = BG_CARD if i % 2 == 0 else BG_DARK

            row, labels = self._pool[i]
            row.configure(fg_color=bg)
            labels[0].configure(text=f"{base}/{quote}")
            labels[1].configure(text=rate_s)
            labels[2].configure(text=date_s)
            row.pack(fill="x", pady=1)

        # Hide unused rows
        for i in range(len(snapshots), len(self._pool)):
            self._pool[i][0].pack_forget()


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

    def start(self) -> None:
        self._running = True
        self._tick()

    def stop(self) -> None:
        self._running = False

    def _tick(self) -> None:
        if not self._running:
            return
        self._idx = (self._idx + 1) % len(self.FRAMES)
        self._lbl.configure(text=f"{self.FRAMES[self._idx]}  Fetching data…")
        self.after(80, self._tick)
