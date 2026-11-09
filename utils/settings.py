"""
Persistent settings — saves to ~/.frankfurter_settings.json.
Covers: base currency, date ranges per tab, watchlist pairs, favourites.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path


class Settings:
    FILE = Path.home() / ".frankfurter_settings.json"

    def __init__(self):
        self._data: dict = {}
        self._lock = threading.Lock()
        self.load()

    # ── persistence ──────────────────────────────────────────────────────────

    def load(self) -> None:
        try:
            with open(self.FILE, encoding="utf-8") as f:
                data = json.load(f)
            # A hand-edited or corrupted file must never crash the app
            self._data = data if isinstance(data, dict) else {}
        except Exception:
            self._data = {}

    def save(self) -> None:
        """Atomically write settings (temp file + rename) so a crash or a
        full disk mid-write can never leave a truncated JSON file behind."""
        with self._lock:
            try:
                self.FILE.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp = tempfile.mkstemp(
                    dir=self.FILE.parent, prefix=".frankfurter_", suffix=".tmp"
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(self._data, f, indent=2)
                    os.replace(tmp, self.FILE)
                except Exception:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                    raise
            except Exception:
                pass

    # ── generic get/set ──────────────────────────────────────────────────────

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        if self._data.get(key) == value:
            return  # unchanged — skip the disk write
        self._data[key] = value
        self.save()

    def update(self, **values) -> None:
        """Set several keys with a single disk write."""
        changed = False
        for key, value in values.items():
            if self._data.get(key) != value:
                self._data[key] = value
                changed = True
        if changed:
            self.save()

    # ── favourites ───────────────────────────────────────────────────────────

    def get_favourites(self) -> list[tuple[str, str]]:
        """Return list of (base, quote) tuples that are starred."""
        return [
            (str(p[0]), str(p[1]))
            for p in self._data.get("favourites", [])
            if isinstance(p, (list, tuple)) and len(p) == 2
        ]

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
