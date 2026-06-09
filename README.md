# Frankfurter — Currency Intelligence GUI

A feature-rich desktop application for exploring exchange-rate data powered by
the **[Frankfurter API](https://frankfurter.dev)** (European Central Bank data,
no API key required).

---

## Features

| Tab | What it does |
|-----|-------------|
| Dashboard | Live rates for any base currency with full sortable table, change indicators, and export |
| Historical | Look up every rate for any single past date |
| Time Series | Plot any currency pair across a custom date range; 6 chart types; quick-range buttons; weekly/monthly grouping |
| Converter | Real-time conversion with swap button and timestamped history log |
| Compare | Overlay up to 6 currencies on one chart over a chosen period |
| Statistics | Min/Max/Mean/Std-dev/Change% summary cards + histogram / rolling-average charts |

### Chart types (Time Series & Statistics)
- Line · Area · Bar (green/red by direction) · Multi-Currency overlay · Histogram · Rolling Averages (7-day & 30-day)

### Export
- CSV and JSON export on every data tab
- Save any chart as PNG or SVG directly from the matplotlib toolbar

---

## Requirements

```
Python ≥ 3.11
customtkinter
matplotlib
pandas
requests
Pillow
tkcalendar
```

Install:
```bash
pip install -r requirements.txt
```

---

## Project Structure

```
├── main.py                   ← Entry point
├── requirements.txt
│
├── api/
│   ├── __init__.py
│   ├── client.py             ← FrankfurterClient (all API calls)
│   └── cache.py              ← TTLCache (in-memory, thread-safe)
│
├── ui/
│   ├── __init__.py
│   ├── app.py                ← App (main CTk window, tab orchestration)
│   ├── theme.py              ← Colour palette, fonts, matplotlib style
│   ├── widgets.py            ← StatCard, RateTable, StatusBar, etc.
│   ├── chart_panel.py        ← ChartPanel (embedded matplotlib)
│   └── tabs.py               ← DashboardTab, HistoricalTab, TimeSeriesTab,
│                                ConverterTab, CompareTab, StatsTab
│
├── utils/
│   ├── __init__.py
│   └── workers.py            ← AsyncWorker (daemon-thread background calls)
│
└── exports/
    ├── __init__.py
    └── exporter.py           ← CSV / JSON export helpers
```

---

## Run

```bash
cd frankfurter_app
python main.py
```

---

## API

All data comes from **api.frankfurter.dev** (v2):

| Endpoint | Used for |
|----------|---------|
| `GET /v2/currencies` | Populate currency dropdowns |
| `GET /v2/rates?base=X` | Dashboard & Historical |
| `GET /v2/rates?from=…&to=…&quotes=X` | Time Series & Compare |
| `GET /v2/rate/X/Y` | Converter |
| `GET /v2/providers` | (future: provider attribution) |

Data sourced from the European Central Bank and 83 other central banks.
Historical coverage back to 1948 for many currencies.