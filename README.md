<div align="center">

# Frankfurter — Currency Intelligence GUI

**A feature-rich desktop application for exploring exchange-rate data powered by the [Frankfurter API](https://frankfurter.dev)**

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Data: ECB](https://img.shields.io/badge/Data-European%20Central%20Bank-003399)](https://www.ecb.europa.eu/)
[![API: Frankfurter](https://img.shields.io/badge/API-frankfurter.dev-F5A623)](https://frankfurter.dev)
[![No API Key](https://img.shields.io/badge/No%20API%20Key-Required-brightgreen)](https://frankfurter.dev)

*ECB data, no API key required. Coverage back to 1948 across 80+ currencies.*

</div>

---

## Features

### 11-Tab Interface

| Tab | Description |
|-----|-------------|
| **Dashboard** | Live rates for any base currency — sortable table with ★ pin column, change indicators, CSV/JSON export |
| **Historical** | Every rate for any single past date with year quick-jump buttons |
| **Time Series** | Plot any pair across a custom range; 8 chart types; % change toggle; quick-range presets; weekly/monthly grouping; CSV/JSON export |
| **Converter** | Real-time conversion with reverse mode (Quote → Base), swap button, copy to clipboard, and timestamped history log |
| **Compare** | Overlay up to 8 currencies on one chart; 1M / 3M / 6M / YTD / 1Y presets |
| **Statistics** | Min/Max/Mean/Std-dev/Change% summary cards + chart; 1M / 3M / 6M / YTD / 1Y presets |
| **Heatmap** | Annual % change bar chart for any currency pair; CSV/JSON export |
| **Matrix** | Cross-rate N×N matrix fetched in parallel; CSV/JSON export |
| **Watchlist** | Monitor multiple pairs with live snapshots; ★ pin to sort favourites first; pairs persist between sessions |
| **Ccy Detail** | Full metadata per currency (name, providers, date range) + 5-year rate chart |
| **Providers** | Browse the data providers behind the Frankfurter API |

### Chart Types
Line · Area · Bar (directional green/red) · Multi-Currency Overlay · Histogram · Rolling Averages (7-day & 30-day) · Candlestick (Monthly OHLC) · Scatter

### New in This Release

| Feature | Where |
|---------|-------|
| **★ Favourites / pinned pairs** | Click ★ in the Dashboard rate table or Watchlist; pinned pairs float to the top and persist across sessions |
| **Reverse rate calculator** | Converter tab — "Quote → Base" radio flips direction; amount is divided by the rate rather than multiplied |
| **Persistent settings** | Base currency, date range, selected pairs, and favourites are saved to `~/.frankfurter_settings.json` and restored on next launch |
| **Keyboard shortcuts** | `Ctrl+1` – `Ctrl+9` switch tabs; `Enter` fires the active tab's fetch |
| **Copy to clipboard** | "📋 Copy Result" button in the Converter copies the formatted result string |
| **Loading skeletons** | Animated pulsing bars + braille spinner overlay all content areas while API requests are in flight |
| **Export chart data** | Heatmap and Matrix tabs have "⬇ CSV" and "⬇ JSON" buttons in their sidebars |
| **% Change toggle** | Time Series sidebar checkbox switches the chart to percent-change-from-first-value mode |
| **Date range presets** | Compare and Statistics tabs have 1M / 3M / 6M / YTD / 1Y quick buttons that set dates and auto-fetch |

### New in 1.1

| Feature / fix | Where |
|---------------|-------|
| **📅 Date pickers** | Every date field now has a calendar button (uses `tkcalendar`, which was already a dependency but unused) |
| **Currency drop-downs** | Base / quote fields in Historical, Time Series, Compare, Statistics and Heatmap are combo boxes (typing still works, e.g. archived codes like `DEM`) |
| **Input validation** | Bad dates, reversed ranges, future dates and same-currency pairs are caught before any request; offending fields turn red |
| **Chart hover read-out** | Move the mouse over Line / Area / Bar / Rolling Avg / Compare charts to see the date and value(s) under the cursor |
| **Latest-value label** | Line charts tag the final point with its value |
| **Sortable rate tables** | Click *Currency*, *Code*, *Rate* or *Change* headers to sort; double-click a row to copy the rate |
| **Compare normalisation** | "% change from start" toggle (on by default) so JPY, GBP and INR can share one axis; CSV/JSON export; selection counter and *Clear* button |
| **Statistics** | Four extra cards: annualised volatility, high–low range %, best day and worst day |
| **Heatmap** | Close-to-close annual change (Dec → Dec; current year = YTD) and summary cards (best / worst / average / up-years) |
| **Watchlist** | Click a pair to chart it, ✕ to remove a single pair, Enter adds the typed pair, failed pairs are flagged |
| **Converter** | Result updates live while you type the amount or flip direction (no extra request); accepts `1,000.50`; swap and currency changes re-convert |
| **Historical** | ◀ Prev day / Next day ▶ buttons (weekends skipped); 12-year quick-jump grid |
| **Providers** | Filter box, sorted list and a "currencies covered" card |
| **Session restore** | Window size/position, last open tab, and most tab inputs are remembered |
| **Shortcuts** | `F5` refresh, `Ctrl+0` for tab 10, `Ctrl+Tab` / `Ctrl+Shift+Tab` to cycle tabs |

**Performance:** the Dashboard / Historical tables now use lightweight Tk labels allocated on demand instead of 1 320 pre-built CTkLabels (≈ 2 s faster to build each); Compare fetches all currencies in **one** request instead of one per currency; candlesticks and date parsing are vectorised; the HTTP cache is LRU-bounded; transient network errors and HTTP 429/5xx are retried with back-off; results are delivered to the UI through a thread-safe queue instead of calling Tk from worker threads.

**Bug fixes:** ★ clicks could toggle a pin several times (bindings stacked up on every re-render); the Change column was wiped whenever you filtered or pinned; the Matrix colour bar was duplicated on every rebuild, shrinking the chart; switching chart type on the Heatmap/Matrix tabs erased the chart; quick-range and year buttons overflowed the sidebar and were unclickable; a cleared watchlist came back after restart; Compare's filter scrambled the list order; a slow old response could overwrite a newer one; `Refresh` served cached data; Currency Detail charted EUR against itself; Enter did nothing on the Converter tab; a tab that failed to build stayed blank silently; settings writes were not atomic.

### New in the PyQt6 port

The whole GUI now runs on **PyQt6** instead of customtkinter. Every tab, shortcut and feature from 1.1 is still there; the look (dark theme, gold accents) is carried over through a Qt style sheet.

| Change | Details |
|--------|---------|
| **Qt model/view tables** | Rate, watchlist, provider and matrix tables are real Qt tables; only visible rows are painted, so refreshes are instant no matter how many currencies |
| **Built-in calendar** | Date pickers use Qt's `QCalendarWidget` — `tkcalendar` is no longer needed |
| **Cleaner threading** | Worker results reach the GUI through a queued Qt signal instead of a 15 ms polling loop |
| **Resizable splits** | Matrix (chart ↔ table) and Watchlist (list ↔ chart) have a draggable divider |
| **Small windows** | Sidebars and main areas scroll instead of clipping; stat-card values shrink to fit narrow cards (full value in the tooltip) |
| **Checklists** | Compare / Matrix currency lists are one `QListWidget`; clicking anywhere on a row toggles it |
| **Heatmap years** | Year fields are spin boxes limited to 1948 – this year (scroll or ↑/↓) |
| **Modular code** | `ui/tabs/` has one module per tab; `ui/widgets/` is split by purpose |
| **Fewer dependencies** | `customtkinter`, `tkcalendar` and `Pillow` are gone; a Tk-enabled Python is no longer required |

> The saved window position now uses Qt's own format (`window_geometry_qt`), so the window opens at the default size once after upgrading. All other saved settings carry over unchanged.

### Export
- **CSV and JSON** on every data tab (Dashboard, Historical, Time Series, Heatmap, Matrix)
- **PNG, SVG or PDF** chart export via the 💾 Save button on any chart panel

### Performance
- **Thread-safe in-memory TTL + LRU cache** — live rates cached 5 min, historical data cached 24 h
- **Parallel fetching** via `ThreadPoolExecutor` for the Matrix and Watchlist tabs
- **Lazy tab construction** — only the active tab is built on startup; all others are built on first click

---

## Getting Started

### Standard (any OS)

```bash
git clone https://github.com/Yeongwonhan-Jeolmang/Frankfurter.git
cd Frankfurter
pip install -r requirements.txt
python main.py
```

### NixOS

PyQt6 wheels from pip expect system libraries that NixOS doesn't expose at the usual paths, so the simplest route is to let Nix provide the Python packages:

```bash
nix-shell -p 'python3.withPackages (ps: [ ps.pyqt6 ps.matplotlib ps.pandas ps.httpx ])' --run 'bash run.sh'
```

`run.sh`:
1. Starts the app straight away if PyQt6 & co. are already importable (the command above)
2. Otherwise locates `libstdc++.so.6` via `gcc`, creates a `.venv/` on first run and pip-installs `requirements.txt`
3. Launches `main.py`

### Requirements

- Python **3.12** or newer
- Dependencies listed in `requirements.txt`

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `PyQt6` | >= 6.5 | GUI toolkit (widgets, tables, calendar, dialogs) |
| `matplotlib` | >= 3.7.0 | Charts and data visualisation (Qt backend) |
| `pandas` | >= 2.0.0 | Data wrangling for time series |
| `httpx` | >= 0.27.0 | HTTP client with connection pooling |

---

## Project Structure

```
Frankfurter/
├── main.py                     <- Entry point
├── run.sh                      <- NixOS launcher (optional) (venv + libstdc++ fix)
├── requirements.txt
├── pyproject.toml
│
├── api/
│   ├── __init__.py
│   └── client.py               <- FrankfurterClient (all API calls + TTL cache)
│
├── ui/
│   ├── __init__.py
│   ├── app.py                  <- App (QMainWindow, keyboard shortcuts, lazy tab orchestration)
│   ├── theme.py                <- Colour palette, fonts, dark QPalette, Qt style sheet, matplotlib style
│   ├── chart_panel.py          <- ChartPanel (8 chart types, % change mode, hover read-out, export)
│   ├── assets/                 <- Small SVG icons used by the style sheet (chevron, check mark, arrows)
│   ├── widgets/
│   │   ├── common.py           <- StatCard, SectionHeader, StatusBar, Sidebar, CodeCombo, SegmentedButton, ...
│   │   ├── dates.py            <- DateEntry + calendar pop-up
│   │   ├── tables.py           <- RateTable (★ pins, sorting) and WatchlistPanel (Qt model/view)
│   │   ├── checklist.py        <- CurrencyChecklist (Compare / Matrix)
│   │   └── loading.py          <- SkeletonOverlay, SpinnerLabel
│   └── tabs/
│       ├── base.py             <- BaseTab (async requests, validation, export) + shared helpers
│       ├── dashboard.py  historical.py  timeseries.py  converter.py  compare.py  stats.py
│       └── heatmap.py  matrix.py  watchlist.py  detail.py  providers.py
│
├── utils/
│   ├── __init__.py
│   ├── settings.py             <- Settings (persistent JSON — favourites, currencies, date ranges)
│   └── workers.py              <- AsyncWorker (thread pool + queued Qt signal back to the GUI thread)
│
└── exports/
    ├── __init__.py
    └── exporter.py             <- CSV / JSON export helpers
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` … `Ctrl+9`, `Ctrl+0` | Switch to tab 1 – 10 |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | Next / previous tab |
| `Enter` or `F5` | Trigger fetch on the currently active tab (Watchlist: add the typed pair) |

---

## API Reference

All data is sourced from **`api.frankfurter.dev` (v2)** — no authentication required.

| Endpoint | Used for |
|----------|----------|
| `GET /v2/currencies` | Populate currency dropdowns |
| `GET /v2/currencies?scope=all` | Include archived currencies (DEM, FRF, BEF…) |
| `GET /v2/rates?base=X` | Dashboard & Historical rates |
| `GET /v2/rates?from=…&to=…&quotes=X` | Time Series, Compare, Heatmap |
| `GET /v2/rates?group=month` | Monthly-grouped data for Heatmap |
| `GET /v2/rate/{base}/{quote}` | Converter & Watchlist single-pair rates |
| `GET /v2/currency/{code}` | Currency Detail metadata |
| `GET /v2/providers` | Provider attribution list |

> Data sourced from the **European Central Bank** and **83+ other central banks**.  
> Historical coverage back to **1948** for many currencies.

---

## Architecture Notes

- **Settings** is a single shared instance created in `App.__init__` and passed as a `settings=` kwarg to every tab. `BaseTab` stores it as `self._settings` — no global state.
- **SkeletonOverlay** is a child widget of the table / chart it covers; an event filter keeps it sized to its target, so it never disturbs the layout.
- **Threading:** work runs on a shared `ThreadPoolExecutor`; `AsyncWorker` emits a Qt signal from the worker thread, which Qt queues onto the GUI thread. `BaseTab._run` drops replies from superseded requests and from tabs that have been destroyed.
- **Styling** lives in `ui/theme.py`: widgets opt into variants via dynamic properties (e.g. `QPushButton[variant="accent"]`, `QLineEdit[error="true"]`) rather than per-widget colours.
- **Reverse conversion** is client-side: always fetch the forward rate and invert it, avoiding an extra API call.
- **Favourites** are stored as `[[base, quote], …]` in `~/.frankfurter_settings.json` and used by both `RateTable` and `WatchlistPanel` to sort starred pairs to the top.

---

## License

Distributed under the [GNU General Public License v3.0](LICENSE).
