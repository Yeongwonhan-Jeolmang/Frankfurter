"""
Persistent settings — saves to ~/.frankfurter_settings.json.
Covers: base currency, date ranges per tab, watchlist pairs, favourites.
"""

from __future__ import annotations

import json
from pathlib import Path


class Settings:
    FILE = Path.home() / ".frankfurter_settings.json"

    def __init__(self):
        self._data: dict = {}
        self.load()

    # ── persistence ──────────────────────────────────────────────────────────

    def load(self) -> None:
        try:
            with open(self.FILE) as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def save(self) -> None:
        try:
            with open(self.FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    # ── generic get/set ──────────────────────────────────────────────────────

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self.save()

    # ── favourites ───────────────────────────────────────────────────────────

    def get_favourites(self) -> list[tuple[str, str]]:
        """Return list of (base, quote) tuples that are starred."""
        return [tuple(p) for p in self._data.get("favourites", [])]

    def is_favourite(self, base: str, quote: str) -> bool:
        return [base, quote] in self._data.get("favourites", [])

    def toggle_favourite(self, base: str, quote: str) -> bool:
        """Toggle and return True if now a favourite."""
        favs: list = self._data.setdefault("favourites", [])
        pair = [base, quote]
        if pair in favs:
            favs.remove(pair)
            self.save()
            return False
        favs.append(pair)
        self.save()
        return True

    def add_favourite(self, base: str, quote: str) -> None:
        favs: list = self._data.setdefault("favourites", [])
        if [base, quote] not in favs:
            favs.append([base, quote])
            self.save()

    def remove_favourite(self, base: str, quote: str) -> None:
        favs: list = self._data.get("favourites", [])
        try:
            favs.remove([base, quote])
            self.save()
        except ValueError:
            pass
