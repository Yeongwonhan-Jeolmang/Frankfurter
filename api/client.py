"""
Frankfurter API Client  —  api.frankfurter.dev  v2
Thread-safe, with integrated TTL caching and full v2 endpoint coverage. (Hana Eun-Seo and Simon Roberge)

v2 API returns flat lists of {date, base, quote, rate} objects.
All methods that previously returned v1-style dicts now normalise the
response into the same shape the UI expects:
  - get_latest_rates / get_rates_on_date  → {"date":..., "base":..., "rates": {quote: rate, ...}}
  - get_time_series                       → {"rates": {"YYYY-MM-DD": {quote: rate, ...}, ...}}
  - get_currencies                        → {iso_code: name, ...}
"""

import httpx
import threading
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Optional

BASE_URL = "https://api.frankfurter.dev/v2"
TIMEOUT = 15


class FrankfurterAPIError(Exception):
    pass


# ── tiny in-process cache ─────────────────────────────────────────────────────


class _Cache:
    def __init__(self):
        self._store: dict = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            e = self._store.get(key)
            if e and time.monotonic() < e[1]:
                return e[0]
            return None

    def set(self, key, value, ttl: int):
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    def clear(self):
        with self._lock:
            self._store.clear()


_cache = _Cache()


# ── helpers ───────────────────────────────────────────────────────────────────


def _flat_to_rates_dict(flat: list) -> dict:
    """
    Convert v2 flat list → {"date":..., "base":..., "rates": {quote: rate}}
    Works for both single-date and multi-date responses.
    For multi-date the "date" and "base" fields reflect the first entry.
    """
    if not flat:
        return {"date": "—", "base": "—", "rates": {}}
    # single-date: all entries share the same date
    first = flat[0]
    rates = {entry["quote"]: entry["rate"] for entry in flat}
    return {
        "date": first.get("date", "—"),
        "base": first.get("base", "—"),
        "rates": rates,
    }


def _flat_to_series_dict(flat: list) -> dict:
    """
    Convert v2 flat list → {"rates": {"YYYY-MM-DD": {quote: rate, ...}, ...}}
    Multiple quotes on the same date are merged into one day-dict.
    """
    by_date: dict = {}
    for entry in flat:
        d = entry.get("date", "")
        quote = entry.get("quote", "")
        rate = entry.get("rate")
        if d and quote and rate is not None:
            by_date.setdefault(d, {})[quote] = rate
    return {"rates": by_date}


# ── client ────────────────────────────────────────────────────────────────────


class FrankfurterClient:
    """All Frankfurter v2 endpoints in one place."""

    def __init__(self):
        # httpx.Client is thread-safe for concurrent reads; one shared client
        # with connection pooling is faster than per-thread sessions.
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
            http2=False,  # frankfurter.dev doesn't support h2; skip negotiation
        )

    # ── Currencies ────────────────────────────────────────────────────────────

    def get_currencies(self, scope: str = "active") -> dict[str, str]:
        """
        scope="active"  → active currencies
        scope="all"     → all currencies incl. archived (e.g. DEM, FRF, BEF)
        Returns {iso_code: name}.
        v2 returns a list of objects: [{iso_code, name, ...}, ...]
        """
        key = f"currencies:{scope}"
        cached: dict[str, str] | None = _cache.get(key)
        if cached is not None:
            return cached
        params = {} if scope == "active" else {"scope": "all"}
        data = self._get("/currencies", params)
        result: dict[str, str]
        # v2: list of currency objects
        if isinstance(data, list):
            result = {
                str(item["iso_code"]): str(item.get("name", item["iso_code"]))
                for item in data
                if "iso_code" in item
            }
        elif isinstance(data, dict):
            # fallback: handle {code: name} or {code: {name: ...}}
            first = next(iter(data.values()), None)
            if isinstance(first, dict):
                result = {str(k): str(v.get("name", k)) for k, v in data.items()}
            else:
                result = {str(k): str(v) for k, v in data.items()}
        else:
            result = {}
        _cache.set(key, result, 86400)
        return result

    def get_currency_detail(self, code: str) -> dict:
        """Full metadata for a single currency (name, providers, date range…)."""
        key = f"ccy:{code}"
        cached = _cache.get(key)
        if cached:
            return cached
        data = self._get(f"/currency/{code.upper()}")
        # v2 returns a plain object — normalise field names for the UI
        if isinstance(data, dict):
            # Ensure "name" key exists
            if "name" not in data and "iso_code" in data:
                data["name"] = data.get("iso_code", code)
            # Ensure "start" key from start_date
            if "start" not in data and "start_date" in data:
                data["start"] = data["start_date"]
        _cache.set(key, data, 86400)
        return data

    # ── Latest rates ──────────────────────────────────────────────────────────

    def get_latest_rates(self, base="EUR", quotes: Optional[list] = None) -> dict:
        """
        Returns {"date": ..., "base": ..., "rates": {quote: rate, ...}}
        """
        params = {"base": base}
        if quotes:
            params["quotes"] = ",".join(quotes)
        key = f"latest:{base}:{','.join(sorted(quotes or []))}"
        cached = _cache.get(key)
        if cached:
            return cached
        raw = self._get("/rates", params)
        data = _flat_to_rates_dict(raw) if isinstance(raw, list) else raw
        _cache.set(key, data, 300)
        return data

    # ── Historical single date ────────────────────────────────────────────────

    def get_rates_on_date(
        self, on_date: str, base="EUR", quotes: Optional[list] = None
    ) -> dict:
        """
        Returns {"date": ..., "base": ..., "rates": {quote: rate, ...}}
        """
        params = {"base": base, "date": on_date}
        if quotes:
            params["quotes"] = ",".join(quotes)
        key = f"hist:{on_date}:{base}:{','.join(sorted(quotes or []))}"
        cached = _cache.get(key)
        if cached:
            return cached
        raw = self._get("/rates", params)
        data = _flat_to_rates_dict(raw) if isinstance(raw, list) else raw
        _cache.set(key, data, 86400)
        return data

    # ── Time series ───────────────────────────────────────────────────────────

    def get_time_series(
        self,
        start: str,
        end: Optional[str] = None,
        base="EUR",
        quotes: Optional[list] = None,
        group: Optional[str] = None,
    ) -> dict:
        """
        Returns {"rates": {"YYYY-MM-DD": {quote: rate, ...}, ...}}
        """
        params = {"base": base, "from": start}
        if end:
            params["to"] = end
        if quotes:
            params["quotes"] = ",".join(quotes)
        if group:
            params["group"] = group
        key = f"ts:{start}:{end}:{base}:{','.join(sorted(quotes or []))}:{group}"
        cached = _cache.get(key)
        if cached:
            return cached
        raw = self._get("/rates", params)
        data = _flat_to_series_dict(raw) if isinstance(raw, list) else raw
        ttl = 86400 if end and end < date.today().isoformat() else 300
        _cache.set(key, data, ttl)
        return data

    # ── Single pair ───────────────────────────────────────────────────────────

    def get_single_rate(
        self, base: str, quote: str, on_date: Optional[str] = None
    ) -> dict:
        """
        Returns {"date": ..., "base": ..., "quote": ..., "rate": float}
        v2 /rate/{base}/{quote} already returns this shape — no normalisation needed.
        """
        params = {}
        if on_date:
            params["date"] = on_date
        key = f"rate:{base}:{quote}:{on_date}"
        cached = _cache.get(key)
        if cached:
            return cached
        data = self._get(f"/rate/{base.upper()}/{quote.upper()}", params)
        ttl = 86400 if on_date else 300
        _cache.set(key, data, ttl)
        return data

    # ── Providers ─────────────────────────────────────────────────────────────

    def get_providers(self) -> list[dict]:
        cached: list[dict] | None = _cache.get("providers")
        if cached is not None:
            return cached
        data = self._get("/providers")
        providers: list[dict] = (
            data if isinstance(data, list) else data.get("providers", [])
        )
        _cache.set("providers", providers, 86400)
        return providers

    # ── Cross-rate matrix ─────────────────────────────────────────────────────

    def get_cross_rate_matrix(
        self, codes: list[str]
    ) -> dict[str, dict[str, float | None]]:
        """
        Return a NxN matrix of rates.  Fetches all base currencies in parallel.
        Missing rates are represented as None.
        """
        matrix: dict[str, dict[str, float | None]] = {}

        def fetch_row(base):
            try:
                data = self.get_latest_rates(base, [q for q in codes if q != base])
                row: dict[str, float | None] = {
                    k: float(v) for k, v in data.get("rates", {}).items()
                }
                row[base] = 1.0
                return base, row
            except FrankfurterAPIError:
                fallback: dict[str, float | None] = {q: None for q in codes}
                return base, fallback

        with ThreadPoolExecutor(max_workers=min(len(codes), 8)) as pool:
            futures = {pool.submit(fetch_row, base): base for base in codes}
            for future in as_completed(futures):
                base, row = future.result()
                matrix[base] = row

        return matrix

    # ── Statistics ────────────────────────────────────────────────────────────

    def get_volatility_stats(
        self, base: str, quote: str, start: str, end: Optional[str] = None
    ) -> dict:
        data = self.get_time_series(start, end, base, [quote])
        values = [v[quote] for v in data.get("rates", {}).values() if quote in v]
        if not values:
            return {}
        pct_changes = [
            (values[i] - values[i - 1]) / values[i - 1] * 100
            for i in range(1, len(values))
            if values[i - 1] != 0
        ]
        return {
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "count": len(values),
            "change_pct": (
                ((values[-1] - values[0]) / values[0]) * 100 if values[0] else 0
            ),
            "avg_daily_pct_change": statistics.mean(pct_changes) if pct_changes else 0,
            "max_drawdown": self._max_drawdown(values),
            "first": values[0],
            "last": values[-1],
        }

    @staticmethod
    def _max_drawdown(values: list[float]) -> float:
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            if peak == 0:
                continue
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return max_dd

    # ── Year heatmap data ─────────────────────────────────────────────────────

    def get_annual_changes(
        self, base: str, quote: str, start_year: int, end_year: int
    ) -> dict[int, float]:
        """
        Return {year: annual_pct_change} for each full year in range.
        Uses monthly grouping to keep response small.
        """
        start = f"{start_year}-01-01"
        end = f"{end_year}-12-31"
        data = self.get_time_series(start, end, base, [quote], group="month")
        rates_map = data.get("rates", {})
        by_year: dict[int, list[float]] = {}
        for d, day_data in rates_map.items():
            if quote not in day_data:
                continue
            year = int(d[:4])
            by_year.setdefault(year, []).append(day_data[quote])
        result = {}
        for year, vals in sorted(by_year.items()):
            if len(vals) >= 2:
                result[year] = (vals[-1] - vals[0]) / vals[0] * 100
        return result

    # ── Watchlist helpers ─────────────────────────────────────────────────────

    def get_watchlist_snapshot(self, pairs: list[tuple[str, str]]) -> list[dict]:
        """
        Fetch the latest rate for each (base, quote) pair in parallel.
        Returns list of {base, quote, rate, date}.
        """

        def fetch_pair(base, quote):
            try:
                d = self.get_single_rate(base, quote)
                return {
                    "base": base,
                    "quote": quote,
                    "rate": d.get("rate"),
                    "date": d.get("date"),
                }
            except FrankfurterAPIError as e:
                return {"base": base, "quote": quote, "rate": None, "error": str(e)}

        results: list[dict] = [{}] * len(pairs)
        with ThreadPoolExecutor(max_workers=min(len(pairs), 8)) as pool:
            futures = {
                pool.submit(fetch_pair, b, q): i for i, (b, q) in enumerate(pairs)
            }
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()

        return results

    # ── internal ──────────────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        try:
            r = self._http.get(path, params=params)
            if not r.is_success:
                try:
                    msg = r.json().get("message", r.text)
                except Exception:
                    msg = r.text
                raise FrankfurterAPIError(f"HTTP {r.status_code}: {msg}")
            return r.json()
        except httpx.ConnectError as e:
            raise FrankfurterAPIError(f"Connection error: {e}") from e
        except httpx.TimeoutException:
            raise FrankfurterAPIError("Request timed out.") from None
