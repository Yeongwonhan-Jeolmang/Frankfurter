"""
Main application window — orchestrates all tabs and the status bar.
"""

import sys

import customtkinter as ctk

from api.client import FrankfurterClient
from ui.tabs import (
    CompareTab,
    ConverterTab,
    CurrencyDetailTab,
    DashboardTab,
    HeatmapTab,
    HistoricalTab,
    MatrixTab,
    ProvidersTab,
    StatsTab,
    TimeSeriesTab,
    WatchlistTab,
)
from ui.theme import *
from ui.widgets import StatusBar
from utils.settings import Settings
from utils.workers import AsyncWorker

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class App(ctk.CTk):
    """Root window."""

    TITLE = "Frankfurter — Currency Intelligence"
    W, H = 1280, 800

    # Used when the currency list can't be fetched (e.g. offline at startup)
    FALLBACK_CURRENCIES = {
        "AUD": "Australian Dollar",
        "CAD": "Canadian Dollar",
        "CHF": "Swiss Franc",
        "CNY": "Chinese Renminbi Yuan",
        "EUR": "Euro",
        "GBP": "British Pound",
        "HKD": "Hong Kong Dollar",
        "INR": "Indian Rupee",
        "JPY": "Japanese Yen",
        "MXN": "Mexican Peso",
        "NOK": "Norwegian Krone",
        "NZD": "New Zealand Dollar",
        "SEK": "Swedish Krona",
        "SGD": "Singapore Dollar",
        "USD": "US Dollar",
    }

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
        self._settings = Settings()
        # Restore the last window size/position (validated, falls back to default)
        geo = self._settings.get("window_geometry")
        self.geometry(
            geo if isinstance(geo, str) and "x" in geo else f"{self.W}x{self.H}"
        )
        self.minsize(900, 620)
        self.configure(fg_color=BG_DARK)

        self._client = FrankfurterClient()
        self._currency_names: dict[str, str] = {}
        # Map label → built tab widget (for keyboard-shortcut Enter dispatch)
        self._built_tab_widgets: dict[str, object] = {}

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_skeleton()
        self._load_currencies()
        self._bind_shortcuts()

    def _on_close(self):
        try:
            # Persist window geometry and the active tab for next launch
            if self.state() == "normal":
                self._settings.update(
                    window_geometry=self.geometry(), last_tab=self._tabview.get()
                )
            else:
                self._settings.set("last_tab", self._tabview.get())
        except Exception:
            pass
        self._client.close()
        self.destroy()
        sys.exit(0)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _bind_shortcuts(self):
        # Ctrl+1 … Ctrl+9  — switch to tab by 1-based index (Ctrl+0 → tab 10)
        for i in range(1, 10):
            self.bind_all(
                f"<Control-Key-{i}>",
                lambda e, idx=i - 1: self._switch_tab(idx),
            )
        self.bind_all("<Control-Key-0>", lambda e: self._switch_tab(9))
        # Ctrl+Tab / Ctrl+Shift+Tab — cycle through tabs
        self.bind_all("<Control-Tab>", lambda e: self._cycle_tab(1))
        self.bind_all("<Control-Shift-Tab>", lambda e: self._cycle_tab(-1))
        self.bind_all("<Control-ISO_Left_Tab>", lambda e: self._cycle_tab(-1))
        # Enter / F5 — trigger fetch on the active tab
        self.bind_all("<Return>", self._on_enter)
        self.bind_all("<KP_Enter>", self._on_enter)
        self.bind_all("<F5>", self._on_enter)

    def _cycle_tab(self, step: int) -> str:
        labels = [l for l, _ in self.TABS]
        try:
            idx = labels.index(self._tabview.get())
        except ValueError:
            idx = 0
        self._switch_tab((idx + step) % len(labels))
        return "break"  # stop Tk's default focus traversal

    def _switch_tab(self, idx: int) -> None:
        if idx < len(self.TABS):
            label = self.TABS[idx][0]
            try:
                self._tabview.set(label)
                # Tabs are only constructible once the currency list is in;
                # before that, _build_tabs builds whichever tab is selected.
                if hasattr(self, "_tab_classes"):
                    self._build_tab(label)
            except Exception:
                pass

    def _on_enter(self, event=None) -> None:
        """Delegate Enter to the active tab's _fetch method if it exists."""
        # Don't hijack Enter inside multi-line text boxes
        if event is not None and event.widget.winfo_class() == "Text":
            return
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

        # Re-open the tab that was active when the app was last closed
        last = self._settings.get("last_tab")
        if last in self._tab_frames:
            self._tabview.set(last)

        self._loading_lbl = ctk.CTkLabel(
            self._tab_frames[self._tabview.get()],
            text="⠋  Loading currencies from api.frankfurter.dev…",
            font=FONT_HEADING,
            text_color=ACCENT_GOLD,
        )
        self._loading_lbl.pack(expand=True)
        self._spin_idx = 0
        self._spin_loading()

    def _spin_loading(self) -> None:
        """Animate the braille spinner while the currency list loads."""
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        try:
            if not self._loading_lbl.winfo_exists():
                return
        except Exception:
            return
        self._spin_idx = (self._spin_idx + 1) % len(frames)
        self._loading_lbl.configure(
            text=f"{frames[self._spin_idx]}  Loading currencies from api.frankfurter.dev…"
        )
        self.after(90, self._spin_loading)

    # ------------------------------------------------------------------
    # Currency bootstrap
    # ------------------------------------------------------------------

    def _load_currencies(self):
        self._statusbar.set_status("Loading currency list…", "loading")

        def work():
            return self._client.get_currencies()

        def done(data, err):
            self._load_failed = bool(err or not data)
            if self._load_failed:
                self._statusbar.set_status(
                    f"Failed to load currencies (offline?): {err or 'empty list'}  •  using a built-in fallback list",
                    "error",
                )
                self._currency_names = dict(self.FALLBACK_CURRENCIES)
            else:
                self._currency_names = data

            self._loading_lbl.destroy()
            self._build_tabs()

        AsyncWorker(work, done, root=self).start()

    def _build_tabs(self):
        self._tab_classes: dict[str, type] = {label: cls for label, cls in self.TABS}
        self._built_tabs: set[str] = set()

        # Build whichever tab is showing (the user may have switched with a
        # shortcut while the list was loading, or we restored the last tab)
        self._build_tab(self._tabview.get())
        self._tabview.configure(command=self._on_tab_change)

        if not getattr(self, "_load_failed", False):
            self._statusbar.set_status(
                f"Ready  •  {len(self._currency_names)} currencies loaded  •  "
                "Ctrl+1…9 switch tabs, Enter/F5 fetch",
                "ok",
            )

    def _build_tab(self, label: str):
        if label in self._built_tabs:
            return
        self._built_tabs.add(label)
        TabClass = self._tab_classes[label]
        parent = self._tab_frames[label]
        for w in parent.winfo_children():  # e.g. an error label from a failed try
            w.destroy()
        try:
            tab_widget = TabClass(
                parent,
                client=self._client,
                currency_names=self._currency_names,
                status_cb=self._statusbar.set_status,
                settings=self._settings,
            )
        except Exception as e:
            # Never leave a silently blank tab: show the error and allow a retry
            import traceback

            traceback.print_exc()
            self._built_tabs.discard(label)
            for w in parent.winfo_children():
                w.destroy()
            ctk.CTkLabel(
                parent,
                text=f"⚠  This tab failed to load:\n{e}",
                font=FONT_BODY,
                text_color=ACCENT_RED,
            ).pack(expand=True)
            self._statusbar.set_status(f"Tab failed to load: {e}", "error")
            return
        tab_widget.pack(fill="both", expand=True)
        self._built_tab_widgets[label] = tab_widget

    def _on_tab_change(self):
        label = self._tabview.get()
        self._build_tab(label)
