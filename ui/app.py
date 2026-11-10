"""
Main application window — orchestrates all tabs and the status bar.
"""

from __future__ import annotations

import traceback

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

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
from ui.widgets import SpinnerLabel, StatusBar, make_label
from utils import workers
from utils.settings import Settings
from utils.workers import AsyncWorker


class App(QMainWindow):
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

    # Settings key for Qt's own geometry blob (the Tk "WxH+X+Y" string under
    # "window_geometry" is left alone so switching back still works)
    GEOMETRY_KEY = "window_geometry_qt"

    def __init__(
        self, client: FrankfurterClient | None = None, settings: Settings | None = None
    ):
        super().__init__()
        self.setWindowTitle(self.TITLE)
        self._settings = settings or Settings()
        self._client = client or FrankfurterClient()
        self._currency_names: dict[str, str] = {}
        self._load_failed = False
        self._ready = False
        self._pages: list[QWidget] = []
        self._built: dict[int, QWidget] = {}

        self.setMinimumSize(900, 620)
        self._restore_geometry()
        self._build_skeleton()
        self._bind_shortcuts()
        self._load_currencies()

    # ------------------------------------------------------------------
    # Window state
    # ------------------------------------------------------------------

    def _restore_geometry(self) -> None:
        blob = self._settings.get(self.GEOMETRY_KEY)
        ok = False
        if isinstance(blob, str) and blob:
            try:
                ok = self.restoreGeometry(QByteArray.fromBase64(blob.encode("ascii")))
            except Exception:
                ok = False
        if not ok:
            self.resize(self.W, self.H)

    def closeEvent(self, event):
        try:
            geo = bytes(self.saveGeometry().toBase64()).decode("ascii")
            self._settings.update(
                **{
                    self.GEOMETRY_KEY: geo,
                    "last_tab": self.TABS[self._tabs.currentIndex()][0],
                }
            )
        except Exception:
            pass
        try:
            self._client.close()
        finally:
            workers.shutdown()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        def sc(seq, fn):
            s = QShortcut(QKeySequence(seq), self)
            s.setContext(Qt.ShortcutContext.WindowShortcut)
            s.activated.connect(fn)
            return s

        # Ctrl+1 … Ctrl+9 switch to tab N; Ctrl+0 → tab 10
        for i in range(1, 10):
            sc(f"Ctrl+{i}", lambda idx=i - 1: self._switch_tab(idx))
        sc("Ctrl+0", lambda: self._switch_tab(9))
        # Ctrl+Tab / Ctrl+Shift+Tab cycle through tabs
        sc("Ctrl+Tab", lambda: self._cycle_tab(1))
        sc("Ctrl+Shift+Tab", lambda: self._cycle_tab(-1))
        sc("Ctrl+Backtab", lambda: self._cycle_tab(-1))
        # Enter / F5 trigger a fetch on the active tab
        for key in ("Return", "Enter", "F5"):
            sc(key, self._on_enter)

    def _cycle_tab(self, step: int) -> None:
        self._switch_tab((self._tabs.currentIndex() + step) % len(self.TABS))

    def _switch_tab(self, idx: int) -> None:
        if 0 <= idx < len(self.TABS):
            self._tabs.setCurrentIndex(idx)  # builds it via currentChanged

    def _on_enter(self) -> None:
        """Delegate Enter / F5 to the active tab's ``_fetch``."""
        if isinstance(QApplication.focusWidget(), QPlainTextEdit):
            return  # don't hijack Enter inside multi-line text boxes
        tab = self._built.get(self._tabs.currentIndex())
        if tab is not None and hasattr(tab, "_fetch"):
            try:
                tab._fetch()
            except Exception as e:
                traceback.print_exc()
                self._statusbar.set_status(f"Error: {e}", "error")

    # ------------------------------------------------------------------
    # Layout skeleton
    # ------------------------------------------------------------------

    def _build_skeleton(self) -> None:
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        title = QFrame()
        title.setObjectName("TitleBar")
        title.setFixedHeight(56)
        tl = QHBoxLayout(title)
        tl.setContentsMargins(PAD_LG, 0, PAD_LG, 0)
        tl.setSpacing(PAD_MD)
        tl.addWidget(
            make_label("⬡  FRANKFURTER", (FONT_HEADING[0], 18, "bold"), ACCENT_GOLD)
        )
        tl.addWidget(
            make_label("Exchange Rates & Currency Analytics", FONT_BODY, TEXT_MUTED)
        )
        tl.addStretch(1)
        tl.addWidget(
            make_label(
                "Source: European Central Bank  •  api.frankfurter.dev",
                FONT_SMALL,
                TEXT_DIM,
            )
        )
        lay.addWidget(title)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setUsesScrollButtons(True)
        self._tabs.tabBar().setExpanding(False)
        self._tabs.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)
        for i, (label, _cls) in enumerate(self.TABS):
            page = QWidget()
            pl = QVBoxLayout(page)
            pl.setContentsMargins(0, 0, 0, 0)
            self._pages.append(page)
            self._tabs.addTab(page, label)
            hint = f"Ctrl+{i + 1}" if i < 9 else ("Ctrl+0" if i == 9 else "")
            if hint:
                self._tabs.setTabToolTip(i, hint)
        lay.addWidget(self._tabs, 1)

        self._statusbar = StatusBar()
        lay.addWidget(self._statusbar)
        self.setCentralWidget(central)

        # Re-open the tab that was active when the app was last closed
        labels = [l for l, _ in self.TABS]
        last = self._settings.get("last_tab")
        if last in labels:
            self._tabs.setCurrentIndex(labels.index(last))

        self._loading_lbl = SpinnerLabel("Loading currencies from api.frankfurter.dev…")
        self._pages[self._tabs.currentIndex()].layout().addWidget(self._loading_lbl)
        self._tabs.currentChanged.connect(self._on_tab_change)

    # ------------------------------------------------------------------
    # Currency bootstrap
    # ------------------------------------------------------------------

    def _load_currencies(self) -> None:
        self._statusbar.set_status("Loading currency list…", "loading")

        def done(data, err):
            self._load_failed = bool(err or not data)
            if self._load_failed:
                self._statusbar.set_status(
                    f"Failed to load currencies (offline?): {err or 'empty list'}"
                    "  •  using a built-in fallback list",
                    "error",
                )
                self._currency_names = dict(self.FALLBACK_CURRENCIES)
            else:
                self._currency_names = data
            self._loading_lbl.deleteLater()
            self._loading_lbl = None
            self._ready = True
            self._build_tab(self._tabs.currentIndex())
            if not self._load_failed:
                self._statusbar.set_status(
                    f"Ready  •  {len(self._currency_names)} currencies loaded  •  "
                    "Ctrl+1…9 switch tabs, Enter/F5 fetch",
                    "ok",
                )

        AsyncWorker(self._client.get_currencies, done).start()

    def _on_tab_change(self, idx: int) -> None:
        if self._ready:
            self._build_tab(idx)
        elif self._loading_lbl is not None:
            # Keep the spinner on whichever tab is showing
            self._pages[idx].layout().addWidget(self._loading_lbl)

    def _build_tab(self, idx: int) -> None:
        """Tabs are built lazily, the first time they're shown."""
        if idx in self._built or not (0 <= idx < len(self.TABS)):
            return
        label, cls = self.TABS[idx]
        page = self._pages[idx]
        pl = page.layout()
        while pl.count():  # e.g. an error label from a failed attempt
            w = pl.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        try:
            tab = cls(
                client=self._client,
                currency_names=self._currency_names,
                status_cb=self._statusbar.set_status,
                settings=self._settings,
            )
        except Exception as e:
            # Never leave a silently blank tab: show the error and allow a retry
            traceback.print_exc()
            err = make_label(
                f"⚠  This tab failed to load:\n{e}",
                FONT_BODY,
                ACCENT_RED,
                align=Qt.AlignmentFlag.AlignCenter,
            )
            pl.addWidget(err)
            self._statusbar.set_status(f"Tab failed to load: {e}", "error")
            return
        pl.addWidget(tab)
        self._built[idx] = tab

    # Handy for tests / scripting
    def tab_widget(self, idx: int) -> QWidget | None:
        return self._built.get(idx)

    @property
    def tabs(self) -> QTabWidget:
        return self._tabs

    @property
    def statusbar(self) -> StatusBar:
        return self._statusbar
