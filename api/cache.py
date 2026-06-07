"""
Simple in-memory LRU-style cache with TTL for API responses. (Hana Eun-SEo)
"""

import time
import threading
from typing import Optional


class TTLCache:
    """Thread-safe dictionary cache with per-entry TTL."""

    def __init__(self, default_ttl: int = 300):
        self._store: dict = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if time.monotonic() > expiry:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value, ttl: Optional[int] = None):
        with self._lock:
            ttl = ttl if ttl is not None else self.default_ttl
            self._store[key] = (value, time.monotonic() + ttl)

    def clear(self):
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)


# Module-level shared cache (5-minute TTL for live rates, 24 h for history)
live_cache = TTLCache(default_ttl=300)
history_cache = TTLCache(default_ttl=86400)
