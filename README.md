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

### Export
- **CSV and JSON** on every data tab (Dashboard, Historical, Time Series, Heatmap, Matrix)
- **PNG or SVG** chart export from the matplotlib toolbar on any chart panel

### Performance
- **Thread-safe in-memory TTL cache** — live rates cached 5 min, historical data cached 24 h
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

The app requires a Tk-capable Python build and GCC's `libstdc++` for the numpy/matplotlib wheels. Use the provided launcher:

```bash
nix-shell -p python3Full gcc --run 'bash run.sh'
```

`run.sh` automatically:
1. Locates `libstdc++.so.6` via `gcc -print-file-name` and injects it into `LD_LIBRARY_PATH`
2. Creates a `.venv/` on first run and pip-installs all dependencies
3. Launches `main.py` using the venv Python

### Requirements

- Python **3.12** or newer
- Dependencies listed in `requirements.txt`

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `customtkinter` | >= 5.2.0 | Modern dark-themed UI framework |
| `matplotlib` | >= 3.7.0 | Charts and data visualisation |
| `pandas` | >= 2.0.0 | Data wrangling for time series |
| `httpx` | >= 0.27.0 | HTTP client with connection pooling |
| `Pillow` | >= 10.0.0 | Image handling |
| `tkcalendar` | >= 1.6.0 | Date picker widgets |

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
│   ├── app.py                  <- App (root CTk window, keyboard shortcuts, lazy tab orchestration)
│   ├── theme.py                <- Colour palette, fonts, matplotlib style
│   ├── widgets.py              <- StatCard, RateTable (★ pins), WatchlistPanel, SkeletonFrame, ...
│   ├── chart_panel.py          <- ChartPanel (8 chart types, % change mode, PNG export)
│   └── tabs.py                 <- All 11 tab implementations
│
├── utils/
│   ├── __init__.py
│   ├── settings.py             <- Settings (persistent JSON — favourites, currencies, date ranges)
│   └── workers.py              <- AsyncWorker (daemon-thread background calls)
│
└── exports/
    ├── __init__.py
    └── exporter.py             <- CSV / JSON export helpers
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` … `Ctrl+9` | Switch to tab 1 – 9 |
| `Enter` | Trigger fetch on the currently active tab |

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
- **SkeletonFrame** uses `place(relx=0, rely=0, relwidth=1, relheight=1)` over a wrapper frame so it covers the content area exactly without disturbing the layout.
- **Reverse conversion** is client-side: always fetch the forward rate and invert it, avoiding an extra API call.
- **Favourites** are stored as `[[base, quote], …]` in `~/.frankfurter_settings.json` and used by both `RateTable` and `WatchlistPanel` to sort starred pairs to the top.

---

## License

Distributed under the [GNU General Public License v3.0](LICENSE).
