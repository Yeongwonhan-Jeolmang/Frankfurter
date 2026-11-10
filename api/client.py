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

import math
import statistics
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import httpx

BASE_URL = "https://api.frankfurter.dev/v2"
TIMEOUT = 15
# Transient failures (connection drops, timeouts, 429/5xx) are retried this many
# extra times with a short exponential back-off before surfacing to the UI.
MAX_RETRIES = 2
RETRY_BACKOFF = 0.4
_RETRY_STATUS = {429, 500, 502, 503, 504}
# Upper bound on cached responses so long sessions don't grow memory forever.
CACHE_MAX_ENTRIES = 256
# Trading days per year, used to annualise daily volatility.
TRADING_DAYS = 252


class FrankfurterAPIError(Exception):
    pass


# ── tiny in-process cache ─────────────────────────────────────────────────────


class _Cache:
    """Thread-safe TTL cache with LRU eviction once *max_entries* is reached."""

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES):
        self._store: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._max = max_entries

    def get(self, key):
        with self._lock:
            e = self._store.get(key)
            if e is None:
                return None
            if time.monotonic() < e[1]:
                self._store.move_to_end(key)
                return e[0]
            # Evict expired entry immediately rather than letting it accumulate
            del self._store[key]
            return None

    def set(self, key, value, ttl: int):
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)
            self._store.move_to_end(key)
            while len(self._store) > self._max:
                self._store.popitem(last=False)

    def clear(self):
        with self._lock:
            self._store.clear()

    def invalidate(self, prefix: str) -> None:
        """Drop every entry whose key starts with *prefix*."""
        with self._lock:
            for k in [k for k in self._store if str(k).startswith(prefix)]:
                del self._store[k]


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
    # ISO dates sort lexicographically; guarantee chronological order so every
    # consumer (charts, stats, exports) can rely on it.
    return {"rates": dict(sorted(by_date.items()))}


def _sorted_values(rates_map: dict, quote: str) -> list[float]:
    """Chronologically ordered values of *quote* from a series rates map."""
    return [
        float(day[quote])
        for _, day in sorted(rates_map.items())
        if day.get(quote) is not None
    ]


# ── client ────────────────────────────────────────────────────────────────────


class FrankfurterClient:
    """All Frankfurter v2 endpoints in one place."""

    def __init__(self):
        # httpx.Client is thread-safe for concurrent reads; one shared client
        # with connection pooling is faster than per-thread sessions.
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "Frankfurter-GUI/1.1 (+https://github.com/Yeongwonhan-Jeolmang/Frankfurter)",
            },
            timeout=TIMEOUT,
            http2=False,  # frankfurter.dev doesn't support h2; skip negotiation
        )

    def close(self) -> None:
        """Release pooled connections (call on application exit)."""
        try:
            self._http.close()
        except Exception:
            pass

    @staticmethod
    def clear_cache() -> None:
        """Drop every cached response."""
        _cache.clear()

    @staticmethod
    def invalidate_latest() -> None:
        """Forget cached *latest* rates so a manual refresh really hits the
        network (historical data is immutable and stays cached)."""
        _cache.invalidate("latest:")
        _cache.invalidate("rate:")  # single-pair latest keys end in ':None'

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
        code = code.upper()
        key = f"ccy:{code}"
        cached = _cache.get(key)
        if cached is not None:
            return cached
        data = self._get(f"/currency/{code}")
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

    def get_latest_rates(self, base="EUR", quotes: list | None = None) -> dict:
        """
        Returns {"date": ..., "base": ..., "rates": {quote: rate, ...}}
        """
        base = base.upper()
        quotes = [q.upper() for q in quotes] if quotes else None
        params = {"base": base}
        if quotes:
            params["quotes"] = ",".join(quotes)
        key = f"latest:{base}:{','.join(sorted(quotes or []))}"
        cached = _cache.get(key)
        if cached is not None:
            return cached
        raw = self._get("/rates", params)
        data = _flat_to_rates_dict(raw) if isinstance(raw, list) else raw
        _cache.set(key, data, 300)
        return data

    # ── Historical single date ────────────────────────────────────────────────

    def get_rates_on_date(
        self, on_date: str, base="EUR", quotes: list | None = None
    ) -> dict:
        """
        Returns {"date": ..., "base": ..., "rates": {quote: rate, ...}}
        """
        base = base.upper()
        quotes = [q.upper() for q in quotes] if quotes else None
        params = {"base": base, "date": on_date}
        if quotes:
            params["quotes"] = ",".join(quotes)
        key = f"hist:{on_date}:{base}:{','.join(sorted(quotes or []))}"
        cached = _cache.get(key)
        if cached is not None:
            return cached
        raw = self._get("/rates", params)
        data = _flat_to_rates_dict(raw) if isinstance(raw, list) else raw
        _cache.set(key, data, 86400)
        return data

    # ── Time series ───────────────────────────────────────────────────────────

    def get_time_series(
        self,
        start: str,
        end: str | None = None,
        base="EUR",
        quotes: list | None = None,
        group: str | None = None,
    ) -> dict:
        """
        Returns {"rates": {"YYYY-MM-DD": {quote: rate, ...}, ...}}
        """
        base = base.upper()
        quotes = [q.upper() for q in quotes] if quotes else None
        params = {"base": base, "from": start}
        if end:
            params["to"] = end
        if quotes:
            params["quotes"] = ",".join(quotes)
        if group:
            params["group"] = group
        key = f"ts:{start}:{end}:{base}:{','.join(sorted(quotes or []))}:{group}"
        cached = _cache.get(key)
        if cached is not None:
            return cached
        raw = self._get("/rates", params)
        data = _flat_to_series_dict(raw) if isinstance(raw, list) else raw
        ttl = 86400 if end and end < date.today().isoformat() else 300
        _cache.set(key, data, ttl)
        return data

    # ── Single pair ───────────────────────────────────────────────────────────

    def get_single_rate(
        self, base: str, quote: str, on_date: str | None = None
    ) -> dict:
        """
        Returns {"date": ..., "base": ..., "quote": ..., "rate": float}
        v2 /rate/{base}/{quote} already returns this shape — no normalisation needed.
        """
        base, quote = base.upper(), quote.upper()
        params = {}
        if on_date:
            params["date"] = on_date
        key = f"rate:{base}:{quote}:{on_date}"
        cached = _cache.get(key)
        if cached is not None:
            return cached
        if base == quote:
            # Identity pair — no need to hit the network (and the API rejects it)
            return {
                "date": on_date or date.today().isoformat(),
                "base": base,
                "quote": quote,
                "rate": 1.0,
            }
        data = self._get(f"/rate/{base}/{quote}", params)
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
            except (FrankfurterAPIError, ValueError, TypeError):
                row = {q: None for q in codes}
            row[base] = 1.0
            return base, row

        if not codes:
            return matrix

        with ThreadPoolExecutor(max_workers=min(len(codes), 8)) as pool:
            futures = {pool.submit(fetch_row, base): base for base in codes}
            for future in as_completed(futures):
                base, row = future.result()
                matrix[base] = row

        return matrix

    # ── Statistics ────────────────────────────────────────────────────────────

    def get_volatility_stats(
        self, base: str, quote: str, start: str, end: str | None = None
    ) -> dict:
        data = self.get_time_series(start, end, base, [quote])
        values = _sorted_values(data.get("rates", {}), quote)
        if not values:
            return {}
        pct_changes = [
            (values[i] - values[i - 1]) / values[i - 1] * 100
            for i in range(1, len(values))
            if values[i - 1] != 0
        ]
        daily_sd = statistics.stdev(pct_changes) if len(pct_changes) > 1 else 0.0
        lo, hi = min(values), max(values)
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
            # Annualised volatility of daily % moves (sqrt-of-time scaling)
            "volatility_ann": daily_sd * math.sqrt(TRADING_DAYS),
            "range_pct": ((hi - lo) / lo * 100) if lo else 0,
            "best_day": max(pct_changes) if pct_changes else 0,
            "worst_day": min(pct_changes) if pct_changes else 0,
        }

    @staticmethod
    def _max_drawdown(values: list[float]) -> float:
        peak = values[0]
        max_dd = 0.0
        for v in values:
            peak = max(peak, v)
            if peak == 0:
                continue
            dd = (peak - v) / peak * 100
            max_dd = max(max_dd, dd)
        return max_dd

    # ── Year heatmap data ─────────────────────────────────────────────────────

    def get_annual_changes(
        self, base: str, quote: str, start_year: int, end_year: int
    ) -> dict[int, float]:
        """
        Return {year: annual_pct_change} for each year in range.

        A year's change is measured close-to-close: from the last observation
        of the previous year to the last observation of that year (the
        current year is therefore year-to-date). The first year falls back to
        first-to-last within the year when no prior data exists.
        Uses monthly grouping to keep the response small.
        """
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        today = date.today()
        end_year = min(end_year, today.year)
        # Include December of the previous year as the opening reference
        # (no reference month before the API's first date, 1948-01-01)
        start = (
            f"{start_year - 1}-12-01" if start_year > 1948 else f"{start_year}-01-01"
        )
        end = min(f"{end_year}-12-31", today.isoformat())
        data = self.get_time_series(start, end, base, [quote], group="month")
        rates_map = data.get("rates", {})
        by_year: dict[int, list[float]] = {}
        for d, day_data in sorted(rates_map.items()):
            v = day_data.get(quote)
            if v is None:
                continue
            by_year.setdefault(int(d[:4]), []).append(float(v))
        result: dict[int, float] = {}
        for year in range(start_year, end_year + 1):
            vals = by_year.get(year)
            if not vals:
                continue
            prev = by_year.get(year - 1)
            opening = prev[-1] if prev else vals[0]
            if opening and (prev or len(vals) >= 2):
                result[year] = (vals[-1] - opening) / opening * 100
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
                return {
                    "base": base,
                    "quote": quote,
                    "rate": None,
                    "date": None,
                    "error": str(e),
                }

        if not pairs:
            return []
        results: list[dict] = [{} for _ in pairs]
        with ThreadPoolExecutor(max_workers=min(len(pairs), 8)) as pool:
            futures = {
                pool.submit(fetch_pair, b, q): i for i, (b, q) in enumerate(pairs)
            }
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()

        return results

    # ── internal ──────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict | None = None):
        """GET *path* and return decoded JSON, retrying transient failures."""
        last_err: FrankfurterAPIError | None = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt:
                time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
            try:
                r = self._http.get(path, params=params)
            except httpx.TimeoutException:
                last_err = FrankfurterAPIError("Request timed out.")
                continue
            except (httpx.ConnectError, httpx.NetworkError) as e:
                last_err = FrankfurterAPIError(f"Connection error: {e}")
                continue
            except httpx.HTTPError as e:
                raise FrankfurterAPIError(f"HTTP error: {e}") from e

            if r.status_code in _RETRY_STATUS:
                last_err = FrankfurterAPIError(
                    f"HTTP {r.status_code}: {self._error_message(r)}"
                )
                continue
            if not r.is_success:
                raise FrankfurterAPIError(
                    f"HTTP {r.status_code}: {self._error_message(r)}"
                )
            try:
                return r.json()
            except ValueError as e:
                raise FrankfurterAPIError("Malformed JSON in API response.") from e
        assert last_err is not None
        raise last_err

    @staticmethod
    def _error_message(r: httpx.Response) -> str:
        try:
            body = r.json()
            if isinstance(body, dict):
                return str(body.get("message", r.text))
        except Exception:
            pass
        return r.text[:200]
