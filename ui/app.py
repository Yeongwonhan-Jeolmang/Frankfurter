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
from utils.settings import Settings

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
        self._settings = Settings()
        # Map label → built tab widget (for keyboard-shortcut Enter dispatch)
        self._built_tab_widgets: dict[str, object] = {}

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_skeleton()
        self._load_currencies()
        self._bind_shortcuts()

    def _on_close(self):
        try:
            self._client._http.close()
        except Exception:
            pass
        self.destroy()
        import sys

        sys.exit(0)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _bind_shortcuts(self):
        # Ctrl+1 … Ctrl+9  — switch to tab by 1-based index
        for i in range(1, 10):
            self.bind_all(
                f"<Control-Key-{i}>",
                lambda e, idx=i - 1: self._switch_tab(idx),
            )
        # Enter — trigger fetch on the active tab
        self.bind_all("<Return>", self._on_enter)

    def _switch_tab(self, idx: int) -> None:
        if idx < len(self.TABS):
            label = self.TABS[idx][0]
            try:
                self._tabview.set(label)
                self._build_tab(label)
            except Exception:
                pass

    def _on_enter(self, event=None) -> None:
        """Delegate Enter to the active tab's _fetch method if it exists."""
        try:
            label = self._tabview.get()
            widget = self._built_tab_widgets.get(label)
            if widget and hasattr(widget, "_fetch"):
                widget._fetch()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Layout skeleton
    # ------------------------------------------------------------------

    def _build_skeleton(self):
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

        ctk.CTkLabel(
            titlebar,
            text="Source: European Central Bank  •  api.frankfurter.dev",
            font=FONT_SMALL,
            text_color=TEXT_DIM,
        ).pack(side="right", padx=PAD_LG)

        self._statusbar = StatusBar(self)
        self._statusbar.pack(fill="x", side="bottom")

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

        self._tab_frames: dict[str, ctk.CTkFrame] = {}
        for label, _ in self.TABS:
            tab = self._tabview.add(label)
            tab.configure(fg_color=BG_DARK)
            self._tab_frames[label] = tab

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
        self._tab_classes: dict[str, type] = {label: cls for label, cls in self.TABS}
        self._built_tabs: set[str] = set()

        self._build_tab(self.TABS[0][0])
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
            settings=self._settings,
        )
        tab_widget.pack(fill="both", expand=True)
        self._built_tab_widgets[label] = tab_widget

    def _on_tab_change(self):
        label = self._tabview.get()
        self._build_tab(label)
