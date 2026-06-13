<div align="center">

# Frankfurter — Currency Intelligence GUI

**A feature-rich desktop application for exploring exchange-rate data powered by the [Frankfurter API](https://frankfurter.dev)**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Data: ECB](https://img.shields.io/badge/Data-European%20Central%20Bank-003399?logo=data:image/svg+xml;base64,)](https://www.ecb.europa.eu/)
[![API: Frankfurter](https://img.shields.io/badge/API-frankfurter.dev-F5A623)](https://frankfurter.dev)
[![No API Key](https://img.shields.io/badge/No%20API%20Key-Required-brightgreen)](https://frankfurter.dev)

*ECB data, no API key required. Coverage back to 1948 across 80+ currencies.*

</div>

---

## Features

### 11-Tab Interface

| Tab | Description |
|-----|-------------|
| **Dashboard** | Live rates for any base currency — sortable table, change indicators, CSV/JSON export |
| **Historical** | Every rate for any single past date |
| **Time Series** | Plot any currency pair across a custom date range; 6 chart types; quick-range buttons; weekly/monthly grouping |
| **Converter** | Real-time conversion with swap button and timestamped history log |
| **Compare** | Overlay up to 6 currencies on one chart over a chosen period |
| **Statistics** | Min/Max/Mean/Std-dev/Change% summary cards + histogram / rolling-average charts |
| **Heatmap** | Annual % change heatmap for any currency pair, year by year |
| **Matrix** | Cross-rate NxN matrix fetched in parallel across all selected currencies |
| **Watchlist** | Monitor multiple currency pairs in one place with live rate snapshots |
| **Ccy Detail** | Full metadata per currency (name, providers, date range, ISO code) |
| **Providers** | Browse the data providers behind the Frankfurter API |

### Chart Types
Line · Area · Bar (directional green/red) · Multi-Currency Overlay · Histogram · Rolling Averages (7-day & 30-day)

### Export
- **CSV and JSON** export on every data tab
- **PNG or SVG** chart export directly from the matplotlib toolbar

### Performance
- **Thread-safe in-memory TTL cache** — live rates cached 5 min, historical data cached 24 h
- **Parallel fetching** via `ThreadPoolExecutor` for the Matrix and Watchlist tabs
- **Lazy tab construction** — only the active tab is built on startup; all others are built on first click

---

## Getting Started

### Requirements

- Python **3.11** or newer
- Dependencies listed in `requirements.txt`

```bash
git clone https://github.com/Yeongwonhan-Jeolmang/Frankfurter.git
cd Frankfurter
pip install -r requirements.txt
python main.py
```

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `customtkinter` | >= 5.2.0 | Modern dark-themed UI framework |
| `matplotlib` | >= 3.7.0 | Charts and data visualisation |
| `pandas` | >= 2.0.0 | Data wrangling for time series |
| `httpx` | >= 0.27.0 | HTTP client with connection pooling |
| `requests` | >= 2.28.0 | Auxiliary HTTP utility |
| `Pillow` | >= 10.0.0 | Image handling |
| `tkcalendar` | >= 1.6.0 | Date picker widgets |

---

## Project Structure

```
Frankfurter/
├── main.py                     <- Entry point
├── requirements.txt
├── pyproject.toml
│
├── api/
│   ├── __init__.py
│   └── client.py               <- FrankfurterClient (all API calls + TTL cache)
│
├── ui/
│   ├── __init__.py
│   ├── app.py                  <- App (main CTk window, lazy tab orchestration)
│   ├── theme.py                <- Colour palette, fonts, matplotlib style
│   ├── widgets.py              <- StatCard, RateTable, StatusBar, ...
│   ├── chart_panel.py          <- ChartPanel (embedded matplotlib canvas)
│   └── tabs.py                 <- All 11 tab implementations
│
├── utils/
│   ├── __init__.py
│   └── workers.py              <- AsyncWorker (daemon-thread background calls)
│
└── exports/
    ├── __init__.py
    └── exporter.py             <- CSV / JSON export helpers
```

---

## API Reference

All data is sourced from **`api.frankfurter.dev` (v2)** — no authentication required.

| Endpoint | Used for |
|----------|----------|
| `GET /v2/currencies` | Populate currency dropdowns |
| `GET /v2/currencies?scope=all` | Include archived currencies (DEM, FRF, BEF...) |
| `GET /v2/rates?base=X` | Dashboard & Historical rates |
| `GET /v2/rates?from=...&to=...&quotes=X` | Time Series, Compare, Heatmap |
| `GET /v2/rates?group=month` | Monthly-grouped data for Heatmap |
| `GET /v2/rate/{base}/{quote}` | Converter & Watchlist single-pair rates |
| `GET /v2/currency/{code}` | Currency Detail metadata |
| `GET /v2/providers` | Provider attribution list |

> Data sourced from the **European Central Bank** and **83+ other central banks**.  
> Historical coverage back to **1948** for many currencies.

---

## License

Distributed under the [GNU General Public License v3.0](LICENSE).