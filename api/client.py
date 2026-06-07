"""
Frankfurter API Client  —  api.frankfurter.dev  v2
Thread-safe, with integrated TTL caching and full v2 endpoint coverage. (Hana Eun-Seo and Simon Roberge)
"""

import requests
import threading
import statistics
import time
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


# ── client ────────────────────────────────────────────────────────────────────


class FrankfurterClient:
    """All Frankfurter v2 endpoints in one place."""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers["Accept"] = "application/json"
        self._lock = threading.Lock()

    # ── Currencies ────────────────────────────────────────────────────────────

    def get_currencies(self, scope: str = "active") -> dict[str, str]:
        """
        scope="active"  → 165 current currencies
        scope="all"     → 201 currencies incl. archived (e.g. DEM, FRF, BEF)
        Returns {code: name}.
        """
        key = f"currencies:{scope}"
        cached = _cache.get(key)
        if cached:
            return cached
        params = {} if scope == "active" else {"scope": "all"}
        data = self._get("/currencies", params)
        # v2 returns {code: {name:..., ...}} or plain {code: name}
        if data and isinstance(next(iter(data.values())), dict):
            result = {k: v.get("name", k) for k, v in data.items()}
        else:
            result = data
        _cache.set(key, result, 86400)
        return result

    def get_currency_detail(self, code: str) -> dict:
        """Full metadata for a single currency (name, providers, date range…)."""
        key = f"ccy:{code}"
        cached = _cache.get(key)
        if cached:
            return cached
        data = self._get(f"/currency/{code.upper()}")
        _cache.set(key, data, 86400)
        return data

    # ── Latest rates ──────────────────────────────────────────────────────────

    def get_latest_rates(self, base="EUR", quotes: Optional[list] = None) -> dict:
        params = {"base": base}
        if quotes:
            params["quotes"] = ",".join(quotes)
        key = f"latest:{base}:{','.join(sorted(quotes or []))}"
        cached = _cache.get(key)
        if cached:
            return cached
        data = self._get("/rates", params)
        _cache.set(key, data, 300)
        return data

    # ── Historical single date ────────────────────────────────────────────────

    def get_rates_on_date(
        self, on_date: str, base="EUR", quotes: Optional[list] = None
    ) -> dict:
        params = {"base": base, "date": on_date}
        if quotes:
            params["quotes"] = ",".join(quotes)
        key = f"hist:{on_date}:{base}:{quotes}"
        cached = _cache.get(key)
        if cached:
            return cached
        data = self._get("/rates", params)
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
        params = {"base": base, "from": start}
        if end:
            params["to"] = end
        if quotes:
            params["quotes"] = ",".join(quotes)
        if group:
            params["group"] = group
        key = f"ts:{start}:{end}:{base}:{quotes}:{group}"
        cached = _cache.get(key)
        if cached:
            return cached
        data = self._get("/rates", params)
        ttl = 86400 if end and end < date.today().isoformat() else 300
        _cache.set(key, data, ttl)
        return data

    # ── Single pair ───────────────────────────────────────────────────────────

    def get_single_rate(
        self, base: str, quote: str, on_date: Optional[str] = None
    ) -> dict:
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

    def get_providers(self) -> list:
        cached = _cache.get("providers")
        if cached:
            return cached
        data = self._get("/providers")
        _cache.set("providers", data, 86400)
        return data

    # ── Cross-rate matrix ─────────────────────────────────────────────────────

    def get_cross_rate_matrix(self, codes: list[str]) -> dict[str, dict[str, float]]:
        """
        Return a NxN matrix of rates.  Uses a single call per base by fetching
        one base at a time with all quotes, minimising round-trips.
        """
        matrix: dict[str, dict[str, float]] = {}
        for base in codes:
            try:
                data = self.get_latest_rates(base, [q for q in codes if q != base])
                matrix[base] = data.get("rates", {})
                matrix[base][base] = 1.0
            except FrankfurterAPIError:
                matrix[base] = {q: None for q in codes}
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
        Fetch the latest rate for each (base, quote) pair.
        Returns list of {base, quote, rate, date}.
        """
        results = []
        for base, quote in pairs:
            try:
                d = self.get_single_rate(base, quote)
                results.append(
                    {
                        "base": base,
                        "quote": quote,
                        "rate": d.get("rate"),
                        "date": d.get("date"),
                    }
                )
            except FrankfurterAPIError as e:
                results.append(
                    {"base": base, "quote": quote, "rate": None, "error": str(e)}
                )
        return results

    # ── internal ──────────────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        with self._lock:
            try:
                r = self._session.get(BASE_URL + path, params=params, timeout=TIMEOUT)
                if not r.ok:
                    try:
                        msg = r.json().get("message", r.text)
                    except:
                        msg = r.text
                    raise FrankfurterAPIError(f"HTTP {r.status_code}: {msg}")
                return r.json()
            except requests.exceptions.ConnectionError as e:
                raise FrankfurterAPIError(f"Connection error: {e}") from e
            except requests.exceptions.Timeout:
                raise FrankfurterAPIError("Request timed out.") from None
