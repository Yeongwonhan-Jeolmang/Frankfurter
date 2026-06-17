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
    Scrollable table of exchange rates with a clickable ★ pin column.

    Performance: rows are created once and their labels are reconfigured
    in-place rather than destroyed and recreated on every filter change.
    Rows beyond the visible set are hidden with grid_remove().
    Pinned (starred) pairs always float to the top.
    """

    HEADERS = ("★", "Currency", "Code", "Rate", "Inverse", "Change")
    _MAX_ROWS = 220

    def __init__(self, master, settings=None, **kw):
        super().__init__(master, fg_color=BG_DARK, **kw)
        self._settings = settings
        self._prev: dict[str, float] = {}
        self._filter: str = ""
        self._raw_rates: dict[str, float] = {}
        self._raw_names: dict[str, str] = {}
        self._raw_base: str = "EUR"
        self._pool: list[list[ctk.CTkLabel]] = []
        self._build_header()
        self._preallocate_pool()

    def _build_header(self) -> None:
        for c, h in enumerate(self.HEADERS):
            ctk.CTkLabel(
                self, text=h, font=FONT_SUBHEAD, text_color=ACCENT_GOLD, anchor="w"
            ).grid(row=0, column=c, sticky="ew", padx=(PAD_SM, PAD_MD), pady=4)
        ctk.CTkFrame(self, height=1, fg_color=BORDER_COLOR).grid(
            row=1, column=0, columnspan=len(self.HEADERS), sticky="ew", pady=2
        )
        # Star column is narrow; rest expand
        self.grid_columnconfigure(0, weight=0, minsize=32)
        for c in range(1, len(self.HEADERS)):
            self.grid_columnconfigure(c, weight=1)

    def _preallocate_pool(self) -> None:
        for i in range(self._MAX_ROWS):
            bg = BG_CARD if i % 2 == 0 else BG_DARK
            labels: list[ctk.CTkLabel] = []
            for c in range(len(self.HEADERS)):
                is_star = c == 0
                lbl = ctk.CTkLabel(
                    self,
                    text="",
                    font=(
                        ("Helvetica Neue", 12)
                        if is_star
                        else (FONT_MONO if c >= 3 else FONT_BODY)
                    ),
                    text_color=TEXT_DIM if is_star else TEXT_PRIMARY,
                    anchor="center" if is_star else "w",
                    fg_color=bg,
                    corner_radius=0,
                    cursor="hand2" if is_star else "arrow",
                    width=30 if is_star else 0,
                )
                lbl.grid(
                    row=i + 2,
                    column=c,
                    sticky="ew",
                    padx=(PAD_SM, PAD_MD),
                    pady=2,
                )
                lbl.grid_remove()
                labels.append(lbl)
            self._pool.append(labels)

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
        pinned_quotes: set[str] = set()
        if self._settings:
            pinned_quotes = {
                q for b, q in self._settings.get_favourites() if b == self._raw_base
            }

        items = sorted(self._raw_rates.items())
        if self._filter:
            items = [
                (c, r)
                for c, r in items
                if self._filter in c
                or self._filter in self._raw_names.get(c, "").upper()
            ]

        # Pinned pairs float to the top
        pinned = [(c, r) for c, r in items if c in pinned_quotes]
        unpinned = [(c, r) for c, r in items if c not in pinned_quotes]
        items = pinned + unpinned

        # Hide all pool rows first
        for labels in self._pool:
            for lbl in labels:
                lbl.grid_remove()

        for i, (code, rate) in enumerate(items):
            if i >= self._MAX_ROWS:
                break
            labels = self._pool[i]
            bg = BG_CARD if i % 2 == 0 else BG_DARK
            is_pinned = code in pinned_quotes

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

            row_vals = [
                "★" if is_pinned else "☆",
                name,
                code,
                f"{rate:.6f}",
                f"{inv:.6f}",
                ct,
            ]
            row_colors = [
                ACCENT_GOLD if is_pinned else TEXT_DIM,
                TEXT_PRIMARY,
                ACCENT_GOLD,
                TEXT_PRIMARY,
                TEXT_MUTED,
                cc,
            ]
            row_fonts = [
                ("Helvetica Neue", 12),
                FONT_BODY,
                FONT_BODY,
                FONT_MONO,
                FONT_MONO,
                FONT_MONO,
            ]

            for c, (lbl, v, col, fnt) in enumerate(
                zip(labels, row_vals, row_colors, row_fonts)
            ):
                lbl.configure(text=v, text_color=col, fg_color=bg, font=fnt)
                lbl.grid()

            # Rebind star toggle with current code snapshot
            star_lbl = labels[0]
            _b, _q = self._raw_base, code
            star_lbl.bind(
                "<Button-1>",
                lambda e, b=_b, q=_q: self._toggle_pin(b, q),
            )

        self._prev = dict(self._raw_rates)

    def _toggle_pin(self, base: str, quote: str) -> None:
        if self._settings:
            self._settings.toggle_favourite(base, quote)
            self._render()


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
    """Compact live watchlist rows — starred pairs sorted to the top."""

    def __init__(self, master, settings=None, on_select=None, **kw):
        super().__init__(master, fg_color=BG_DARK, **kw)
        self._settings = settings
        self._on_select = on_select
        self._pairs: list[tuple[str, str]] = []
        self._pool: list[tuple[ctk.CTkFrame, list]] = []
        self._last_snaps: list[dict] = []

    def set_pairs(self, pairs: list[tuple[str, str]]) -> None:
        self._pairs = pairs

    def _ensure_pool(self, n: int) -> None:
        while len(self._pool) < n:
            i = len(self._pool)
            bg = BG_CARD if i % 2 == 0 else BG_DARK
            row = ctk.CTkFrame(self, fg_color=bg, corner_radius=4)

            star_lbl = ctk.CTkLabel(
                row,
                text="☆",
                font=("Helvetica Neue", 13),
                text_color=TEXT_DIM,
                width=24,
                cursor="hand2",
            )
            star_lbl.pack(side="left", padx=(PAD_SM, 2), pady=6)

            pair_lbl = ctk.CTkLabel(
                row,
                text="",
                font=FONT_SUBHEAD,
                text_color=ACCENT_GOLD,
                width=80,
                anchor="w",
            )
            pair_lbl.pack(side="left", padx=PAD_SM, pady=6)

            rate_lbl = ctk.CTkLabel(
                row, text="", font=FONT_MONO, text_color=TEXT_PRIMARY
            )
            rate_lbl.pack(side="left", padx=PAD_SM)

            date_lbl = ctk.CTkLabel(row, text="", font=FONT_SMALL, text_color=TEXT_DIM)
            date_lbl.pack(side="right", padx=PAD_MD)

            self._pool.append((row, [star_lbl, pair_lbl, rate_lbl, date_lbl]))

    def refresh(self, snapshots: list[dict]) -> None:
        self._last_snaps = snapshots

        # Sort starred pairs to top
        if self._settings:
            favs = {(str(b), str(q)) for b, q in self._settings.get_favourites()}

            def sort_key(snap):
                b = str(snap.get("base", "?"))
                q = str(snap.get("quote", "?"))
                return (0 if (b, q) in favs else 1, b, q)

            snapshots = sorted(snapshots, key=sort_key)

        self._ensure_pool(len(snapshots))
        for i, snap in enumerate(snapshots):
            base = str(snap.get("base", "?"))
            quote = str(snap.get("quote", "?"))
            rate = snap.get("rate")
            rate_s = f"{rate:.5f}" if rate else "N/A"
            date_s = str(snap.get("date", ""))
            bg = BG_CARD if i % 2 == 0 else BG_DARK
            is_fav = bool(self._settings and self._settings.is_favourite(base, quote))

            row, widgets = self._pool[i]
            star_lbl, pair_lbl, rate_lbl, date_lbl = widgets
            row.configure(fg_color=bg)
            star_lbl.configure(
                text="★" if is_fav else "☆",
                text_color=ACCENT_GOLD if is_fav else TEXT_DIM,
            )
            pair_lbl.configure(text=f"{base}/{quote}")
            rate_lbl.configure(text=rate_s)
            date_lbl.configure(text=date_s)

            star_lbl.bind(
                "<Button-1>",
                lambda e, b=base, q=quote: self._toggle_fav(b, q),
            )

            row.pack(fill="x", pady=1)

        for i in range(len(snapshots), len(self._pool)):
            self._pool[i][0].pack_forget()

    def _toggle_fav(self, base: str, quote: str) -> None:
        if self._settings:
            self._settings.toggle_favourite(base, quote)
            # Re-render with stored snapshot to reflect new order
            self.refresh(self._last_snaps)


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


class SkeletonFrame(ctk.CTkFrame):
    """
    Animated loading skeleton — place() over a content frame while data is
    in flight.  Call show() before the request and hide() in the done callback.
    """

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, master, rows: int = 7, **kw):
        super().__init__(master, fg_color=BG_DARK, corner_radius=0, **kw)
        self._after_id: str | None = None
        self._fidx = 0
        self._bars: list[ctk.CTkFrame] = []
        self._phase = False

        self._spinner = ctk.CTkLabel(
            self,
            text="⠋  Loading…",
            font=("Courier New", 12),
            text_color=ACCENT_GOLD,
        )
        self._spinner.pack(pady=(PAD_LG + 4, PAD_MD))

        widths = [0.85, 0.65, 0.78, 0.55, 0.82, 0.60, 0.72]
        for j in range(rows):
            outer = ctk.CTkFrame(self, fg_color="transparent")
            outer.pack(fill="x", padx=PAD_LG * 3, pady=4)
            bar = ctk.CTkFrame(outer, fg_color=BG_INPUT, height=16, corner_radius=4)
            bar.pack(fill="x")
            self._bars.append(bar)

    # ── public ────────────────────────────────────────────────────────────────

    def show(self) -> None:
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self._animate()

    def hide(self) -> None:
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.place_forget()

    # ── animation ─────────────────────────────────────────────────────────────

    def _animate(self) -> None:
        self._fidx = (self._fidx + 1) % len(self.FRAMES)
        self._spinner.configure(text=f"{self.FRAMES[self._fidx]}  Loading data…")
        self._phase = not self._phase
        shade = BG_HOVER if self._phase else BG_INPUT
        for bar in self._bars:
            bar.configure(fg_color=shade)
        self._after_id = self.after(140, self._animate)
