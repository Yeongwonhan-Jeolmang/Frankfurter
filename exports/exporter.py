"""
Export helpers: save data to CSV or JSON files. (Worked on by Anna Zieleman)
"""

import csv
import json
from datetime import datetime
from typing import Any


def export_to_csv(data: dict, filepath: str) -> str:
    """
    Flatten a Frankfurter rates-series dict and write to CSV.
    Returns the final filepath.
    """
    rates = data.get("rates", {})
    base = data.get("base", "BASE")

    rows = []
    for date_str, pairs in sorted(rates.items()):
        for currency, rate in pairs.items():
            rows.append(
                {"date": date_str, "base": base, "currency": currency, "rate": rate}
            )

    if not rows and "rate" in data:
        # Single-pair response
        rows.append(
            {
                "date": data.get("date", ""),
                "base": data.get("base", base),
                "currency": data.get("quote", ""),
                "rate": data.get("rate", ""),
            }
        )

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "base", "currency", "rate"])
        writer.writeheader()
        writer.writerows(rows)

    return filepath


def export_to_json(data: Any, filepath: str) -> str:
    """Write *data* as pretty-printed JSON. Returns filepath."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return filepath


def default_filename(prefix: str, ext: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.{ext}"
