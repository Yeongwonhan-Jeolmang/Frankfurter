"""
Main application window — orchestrates all tabs and the status bar.
"""

import customtkinter as ctk

from ui.theme import *
from ui.widgets import StatusBar
from ui.tabs import (
    DashboardTab,
    HistoricalTab,
    TimeSeriesTab,
    ConverterTab,
    CompareTab,
    StatsTab,
    HeatmapTab,
    MatrixTab,
    WatchlistTab,
    CurrencyDetailTab,
    ProvidersTab,
)
from api.client import FrankfurterClient
from utils.workers import AsyncWorker

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class App(ctk.CTk):
    """Root window."""

    TITLE = "Frankfurter — Currency Intelligence"
    W, H = 1280, 800

    TABS = [
        ("🏠  Dashboard", DashboardTab),
        ("📅  Historical", HistoricalTab),
        ("📈  Time Series", TimeSeriesTab),
        ("💱  Converter", ConverterTab),
        ("⚖  Compare", CompareTab),
        ("📐  Statistics", StatsTab),
        ("🔥  Heatmap", HeatmapTab),
        ("🔢  Matrix", MatrixTab),
        ("👁  Watchlist", WatchlistTab),
        ("ℹ  Ccy Detail", CurrencyDetailTab),
        ("🏦  Providers", ProvidersTab),
    ]

    def __init__(self):
        super().__init__()
        self.title(self.TITLE)
        self.geometry(f"{self.W}x{self.H}")
        self.minsize(900, 620)
        self.configure(fg_color=BG_DARK)

        self._client = FrankfurterClient()
        self._currency_names: dict[str, str] = {}

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_skeleton()
        self._load_currencies()

    def _on_close(self):
        self.destroy()
        import sys

        sys.exit(0)

    # ------------------------------------------------------------------
    # Layout skeleton (shown immediately, tabs populated after currency load)
    # ------------------------------------------------------------------

    def _build_skeleton(self):
        # ── Title bar ──────────────────────────────────────────────────
        titlebar = ctk.CTkFrame(self, fg_color=BG_CARD, height=56, corner_radius=0)
        titlebar.pack(fill="x", side="top")

        ctk.CTkLabel(
            titlebar,
            text="  ⬡  FRANKFURTER",
            font=("Georgia", 18, "bold"),
            text_color=ACCENT_GOLD,
        ).pack(side="left", padx=PAD_LG, pady=PAD_MD)

        ctk.CTkLabel(
            titlebar,
            text="Exchange Rates & Currency Analytics",
            font=FONT_BODY,
            text_color=TEXT_MUTED,
        ).pack(side="left", pady=PAD_MD)

        # ECB source badge
        ctk.CTkLabel(
            titlebar,
            text="Source: European Central Bank  •  api.frankfurter.dev",
            font=FONT_SMALL,
            text_color=TEXT_DIM,
        ).pack(side="right", padx=PAD_LG)

        # ── Status bar ─────────────────────────────────────────────────
        self._statusbar = StatusBar(self)
        self._statusbar.pack(fill="x", side="bottom")

        # ── Tab view ───────────────────────────────────────────────────
        self._tabview = ctk.CTkTabview(
            self,
            fg_color=BG_DARK,
            segmented_button_fg_color=BG_CARD,
            segmented_button_selected_color=ACCENT_GOLD,
            segmented_button_selected_hover_color="#B8960C",
            segmented_button_unselected_color=BG_CARD,
            segmented_button_unselected_hover_color=BG_HOVER,
            text_color=TEXT_PRIMARY,
            text_color_disabled=TEXT_DIM,
            border_width=0,
            corner_radius=0,
        )
        self._tabview.pack(fill="both", expand=True)

        # Pre-create tab frames (content added after currency load)
        self._tab_frames: dict[str, ctk.CTkFrame] = {}
        for label, _ in self.TABS:
            tab = self._tabview.add(label)
            tab.configure(fg_color=BG_DARK)
            self._tab_frames[label] = tab

        # Loading label shown until currencies arrive
        self._loading_lbl = ctk.CTkLabel(
            self._tab_frames[self.TABS[0][0]],
            text="⠙  Loading currencies from api.frankfurter.dev…",
            font=FONT_HEADING,
            text_color=ACCENT_GOLD,
        )
        self._loading_lbl.pack(expand=True)

    # ------------------------------------------------------------------
    # Currency bootstrap
    # ------------------------------------------------------------------

    def _load_currencies(self):
        self._statusbar.set_status("Loading currency list…", "loading")

        def work():
            return self._client.get_currencies()

        def done(data, err):
            if err:
                self._statusbar.set_status(f"Failed to load currencies: {err}", "error")
                self._currency_names = {
                    "EUR": "Euro",
                    "USD": "US Dollar",
                    "GBP": "British Pound",
                    "JPY": "Japanese Yen",
                }
            else:
                self._currency_names = data

            self._loading_lbl.destroy()
            self._build_tabs()

        AsyncWorker(work, done, root=self).start()

    def _build_tabs(self):
        # Store tab classes for lazy construction
        self._tab_classes: dict[str, type] = {label: cls for label, cls in self.TABS}
        self._built_tabs: set[str] = set()

        # Build only the first tab (Dashboard) immediately so the app feels ready
        self._build_tab(self.TABS[0][0])

        # All remaining tabs are built lazily on first click
        self._tabview.configure(command=self._on_tab_change)

        self._statusbar.set_status(
            f"Ready  •  {len(self._currency_names)} currencies loaded", "ok"
        )

    def _build_tab(self, label: str):
        if label in self._built_tabs:
            return
        self._built_tabs.add(label)
        TabClass = self._tab_classes[label]
        parent = self._tab_frames[label]
        tab_widget = TabClass(
            parent,
            client=self._client,
            currency_names=self._currency_names,
            status_cb=self._statusbar.set_status,
        )
        tab_widget.pack(fill="both", expand=True)

    def _on_tab_change(self):
        label = self._tabview.get()
        self._build_tab(label)
