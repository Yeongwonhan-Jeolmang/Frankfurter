"""
ChartPanel — embedded matplotlib with 8 chart types. (Worked on by Anna Zieleman and Simon Roberge)
Ported to PyQt6: the figure lives in a ``FigureCanvasQTAgg`` with matplotlib's
Qt navigation toolbar; all drawing code is unchanged from the Tk version.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("QtAgg")
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from typing import Any
import pandas as pd
import numpy as np
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.theme import *
from ui.widgets.common import SegmentedButton, make_button, make_label


def _style(ax) -> None:
    ax.set_facecolor(BG_DARK)
    ax.figure.set_facecolor(BG_CARD)
    for sp in ax.spines.values():
        sp.set_edgecolor(BORDER_COLOR)
    ax.tick_params(colors=TEXT_MUTED, labelsize=8)
    ax.xaxis.label.set_color(TEXT_MUTED)
    ax.yaxis.label.set_color(TEXT_MUTED)
    ax.title.set_color(TEXT_PRIMARY)
    ax.grid(True, color=BORDER_COLOR, linestyle="--", alpha=0.35)


def _month_end_rule() -> str:
    """pandas >= 2.2 renamed the month-end alias "M" to "ME"."""
    try:
        pd.tseries.frequencies.to_offset("ME")
        return "ME"
    except ValueError:
        return "M"


_MONTH_END = _month_end_rule()


class ChartPanel(QFrame):
    CHART_TYPES = [
        "Line",
        "Area",
        "Bar",
        "Multi-Overlay",
        "Histogram",
        "Rolling Avg",
        "Candlestick (Monthly)",
        "Scatter",
    ]
    # Chart types that have a date x-axis and support the hover read-out
    _HOVERABLE = {"Line", "Area", "Bar", "Multi-Overlay", "Rolling Avg"}

    def __init__(self, show_types: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ChartPanel")
        self._data: dict[str, Any] = {}
        self._base: str = "EUR"
        self._quote: str = "USD"
        self._pct_mode: bool = False
        # "series" | "multi" | "heatmap" | "matrix" — decides what _render draws
        self._mode: str = "series"
        self._special: tuple = ()  # payload for heatmap / matrix modes
        self._show_types = show_types
        self._colorbar = None
        # Cache parsed series so _series() doesn't re-parse on every render
        self._series_cache: dict[str, tuple[list[datetime], list[float]]] = {}
        # Hover read-out state: x positions (matplotlib date numbers) and
        # [(label, y-array, colour)] for every line currently on the axes.
        self._hover_x: np.ndarray | None = None
        self._hover_series: list[tuple[str, tuple[np.ndarray, np.ndarray], str]] = []
        self._hover_artists: tuple = ()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(PAD_MD, PAD_MD, PAD_MD, PAD_SM)
        lay.setSpacing(PAD_SM)
        self._build_toolbar(lay)
        self._build_figure(lay)

    def _build_toolbar(self, lay: QVBoxLayout) -> None:
        bar = QHBoxLayout()
        bar.setSpacing(PAD_MD)
        self._seg = SegmentedButton(self.CHART_TYPES, "Line", command=lambda _v: self._render())
        if self._show_types:
            bar.addWidget(make_label("Chart:", FONT_LABEL, TEXT_MUTED))
            # Scrolls sideways instead of forcing a wide minimum window size
            sc = QScrollArea()
            sc.setWidget(self._seg)
            sc.setWidgetResizable(False)
            sc.setFrameShape(QFrame.Shape.NoFrame)
            sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            sc.setFixedHeight(self._seg.sizeHint().height() + 12)
            sc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            sc.viewport().setAutoFillBackground(False)
            bar.addWidget(sc, 1)
        else:
            self._seg.hide()
            bar.addStretch(1)
        self._save_btn = make_button("💾 Save", self._save, "outline", width=84, height=28)
        bar.addWidget(self._save_btn, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(bar)

    def _build_figure(self, lay: QVBoxLayout) -> None:
        self._fig = Figure(figsize=(8, 4), dpi=96, constrained_layout=True)
        self._fig.set_facecolor(BG_CARD)
        self._ax = self._fig.add_subplot(111)
        _style(self._ax)
        self._mpl_canvas = FigureCanvasQTAgg(self._fig)
        self._mpl_canvas.setStyleSheet(f"background: {BG_CARD};")
        self._mpl_canvas.setMinimumSize(240, 160)
        self._mpl_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self._mpl_canvas, 1)
        # The toolbar picks light icons automatically from the dark palette
        nav = NavigationToolbar2QT(self._mpl_canvas, self, coordinates=True)
        nav.setIconSize(nav.iconSize() * 0.8)
        self._nav = nav
        lay.addWidget(nav)
        self._mpl_canvas.mpl_connect("motion_notify_event", self._on_hover)
        self._mpl_canvas.mpl_connect("axes_leave_event", self._on_leave)
        self._draw_placeholder()

    # ── public ────────────────────────────────────────────────────────────────

    def set_pct_mode(self, enabled: bool) -> None:
        """Switch between absolute rate and % change from first value."""
        if enabled == self._pct_mode:
            return
        self._pct_mode = enabled
        self._series_cache.clear()
        self._render()

    def plot_series(self, data: dict[str, Any], base: str, quote: str) -> None:
        self._mode = "series"
        self._data = data
        self._base = base
        self._quote = quote
        self._series_cache.clear()
        self._render()

    def plot_multi(self, datasets: dict[str, dict[str, Any]], base: str) -> None:
        self._mode = "multi"
        self._data = {"_multi": datasets}
        self._base = base
        self._quote = "multi"
        self._series_cache.clear()
        self._seg.set("Multi-Overlay")
        self._render()

    def plot_heatmap(
        self, annual_changes: dict[int, float], base: str, quote: str
    ) -> None:
        """Year-by-year bar chart coloured green/red."""
        self._mode = "heatmap"
        self._special = (dict(annual_changes), base, quote)
        self._render()

    def plot_matrix_heatmap(self, matrix: dict[str, Any], codes: list[str]) -> None:
        """Cross-rate correlation-style heatmap."""
        self._mode = "matrix"
        self._special = (matrix, list(codes))
        self._render()

    # ── rendering ─────────────────────────────────────────────────────────────

    def _reset_axes(self) -> None:
        # A colorbar lives on its own axes; ax.cla() does not remove it, so
        # without this every matrix rebuild stole more width from the plot.
        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except Exception:
                pass
            self._colorbar = None
        self._ax.cla()
        _style(self._ax)
        self._hover_x = None
        self._hover_series = []
        self._hover_artists = ()

    def _render(self) -> None:
        if self._mode == "heatmap" and self._special:
            self._reset_axes()
            self._draw_annual(*self._special)
            self._mpl_canvas.draw_idle()
            return
        if self._mode == "matrix" and self._special:
            self._reset_axes()
            self._draw_matrix(*self._special)
            self._mpl_canvas.draw_idle()
            return
        if not self._data:
            self._draw_placeholder()
            return
        ctype = self._seg.get()
        self._reset_axes()

        if isinstance(self._data, dict) and "_multi" in self._data:
            self._draw_multi(self._data["_multi"])
        elif ctype == "Line":
            self._draw_line()
        elif ctype == "Area":
            self._draw_area()
        elif ctype == "Bar":
            self._draw_bar()
        elif ctype == "Multi-Overlay":
            self._draw_line(all_q=True)
        elif ctype == "Histogram":
            self._draw_histogram()
        elif ctype == "Rolling Avg":
            self._draw_rolling()
        elif ctype == "Candlestick (Monthly)":
            self._draw_candle()
        elif ctype == "Scatter":
            self._draw_scatter()

        if not self._ax.has_data() and not self._ax.texts:
            self._draw_message("No data for this selection / date range")
        self._mpl_canvas.draw_idle()

    def _series(
        self, quote: str | None = None, data: dict[str, Any] | None = None
    ) -> tuple[list[datetime], list[float]]:
        target = quote or self._quote
        src = self._data if data is None else data
        cache_key = f"{id(src)}:{target}:{'pct' if self._pct_mode else 'abs'}"
        if cache_key in self._series_cache:
            return self._series_cache[cache_key]
        rates = src.get("rates", {})
        if not rates:
            return [], []
        items = sorted(
            (d, day[target]) for d, day in rates.items() if day.get(target) is not None
        )
        if not items:
            return [], []
        date_strs, vals_raw = zip(*items)
        # Vectorised parse — much faster than one pd.Timestamp per point on
        # multi-decade daily series (~5 000+ points).
        dates: list[datetime] = list(pd.to_datetime(list(date_strs)).to_pydatetime())
        vals = [float(v) for v in vals_raw]

        if self._pct_mode and vals and vals[0] != 0:
            first = vals[0]
            vals = [(v - first) / first * 100 for v in vals]

        self._series_cache[cache_key] = (dates, vals)
        return dates, vals

    def _ylabel(self) -> str:
        return "% Change from Start" if self._pct_mode else "Rate"

    def _register_hover(self, dates, label: str, vals, color: str) -> None:
        if not len(dates):
            return
        x = mdates.date2num(np.array(dates))
        if self._hover_x is None or len(x) > len(self._hover_x):
            self._hover_x = x
        self._hover_series.append((label, (x, np.asarray(vals, dtype=float)), color))

    def _draw_line(self, all_q: bool = False) -> None:
        rates = self._data.get("rates", {})
        if not rates:
            return
        dates: list[datetime] = []
        if all_q:
            # Union of quotes across all days, not just the first one
            all_quotes = sorted({q for day in rates.values() for q in day})
            for i, q in enumerate(all_quotes[: len(PALETTE)]):
                dates, vals = self._series(q)
                if dates:
                    self._ax.plot(
                        np.array(dates),
                        np.array(vals),
                        color=PALETTE[i],
                        label=q,
                        linewidth=1.6,
                    )
                    self._register_hover(dates, q, vals, PALETTE[i])
            if self._ax.has_data():
                self._ax.legend(loc="upper left", fontsize=7, ncol=2)
        else:
            dates, vals = self._series()
            if dates:
                self._ax.plot(
                    np.array(dates), np.array(vals), color=ACCENT_GOLD, linewidth=2
                )
                self._ax.scatter(
                    np.array([dates[-1]]),
                    np.array([vals[-1]]),
                    color=ACCENT_GOLD,
                    s=50,
                    zorder=5,
                )
                self._annotate_last(dates[-1], vals[-1])
                self._register_hover(dates, self._quote, vals, ACCENT_GOLD)
        self._fmt_x(dates)
        suffix = " (% Change)" if self._pct_mode else ""
        self._ax.set_title(f"{self._base}/{self._quote}{suffix}", fontsize=11)
        self._ax.set_ylabel(self._ylabel(), fontsize=8)

    def _annotate_last(self, x, y) -> None:
        """Small pill with the latest value next to the final point."""
        txt = f"{y:+.2f}%" if self._pct_mode else f"{y:.4f}"
        self._ax.annotate(
            txt,
            xy=(x, y),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
            color=BG_DARK,
            bbox=dict(boxstyle="round,pad=0.25", fc=ACCENT_GOLD, ec="none"),
            annotation_clip=False,
        )

    def _draw_area(self) -> None:
        dates, vals = self._series()
        if not dates:
            return
        d_arr = np.array(dates)
        v_arr = np.array(vals)
        # Fill down to the visible minimum rather than 0 so the shape is
        # readable for rates far from zero (e.g. EUR/JPY ~160).
        floor = (
            float(v_arr.min()) if not self._pct_mode else min(0.0, float(v_arr.min()))
        )
        self._ax.fill_between(d_arr, v_arr, floor, alpha=0.25, color=ACCENT_GOLD)
        self._ax.plot(d_arr, v_arr, color=ACCENT_GOLD, linewidth=2)
        self._register_hover(dates, self._quote, vals, ACCENT_GOLD)
        self._fmt_x(dates)
        suffix = " (% Change)" if self._pct_mode else " — Area"
        self._ax.set_title(f"{self._base}/{self._quote}{suffix}", fontsize=11)
        self._ax.set_ylabel(self._ylabel(), fontsize=8)

    def _draw_bar(self) -> None:
        dates, vals = self._series()
        if not dates:
            return
        colors = [ACCENT_GOLD] + [
            ACCENT_GREEN if vals[i] >= vals[i - 1] else ACCENT_RED
            for i in range(1, len(vals))
        ]
        self._ax.bar(np.array(dates), np.array(vals), color=colors, width=0.8)
        if not self._pct_mode:
            # Zoom the y-axis onto the data instead of starting at 0
            lo, hi = min(vals), max(vals)
            pad = (hi - lo) * 0.1 or abs(hi) * 0.01 or 1
            self._ax.set_ylim(lo - pad, hi + pad)
        self._register_hover(dates, self._quote, vals, ACCENT_GOLD)
        self._fmt_x(dates)
        suffix = " (% Change)" if self._pct_mode else " — Bar"
        self._ax.set_title(f"{self._base}/{self._quote}{suffix}", fontsize=11)
        self._ax.set_ylabel(self._ylabel(), fontsize=8)

    def _draw_histogram(self) -> None:
        _, vals = self._series()
        if not vals:
            return
        self._ax.hist(
            np.array(vals), bins=35, color=ACCENT_BLUE, edgecolor=BG_DARK, alpha=0.85
        )
        mean = float(np.mean(vals))
        self._ax.axvline(
            mean, color=ACCENT_GOLD, linestyle="--", label=f"Mean: {mean:.4f}"
        )
        self._ax.legend(fontsize=8)
        suffix = " (% Change)" if self._pct_mode else " — Distribution"
        self._ax.set_title(f"{self._base}/{self._quote}{suffix}", fontsize=11)
        self._ax.set_xlabel(self._ylabel(), fontsize=8)
        self._ax.set_ylabel("Frequency", fontsize=8)

    def _draw_rolling(self) -> None:
        dates, vals = self._series()
        if len(vals) < 7:
            if vals:
                self._draw_message("Need at least 7 data points for rolling averages")
            return
        d_arr = np.array(dates)
        v_arr = np.array(vals)
        s = pd.Series(vals, index=dates)
        r7 = s.rolling(7).mean()
        r30 = s.rolling(30).mean()
        self._ax.plot(
            d_arr, v_arr, color=ACCENT_GOLD, alpha=0.3, linewidth=1, label="Daily"
        )
        self._ax.plot(
            d_arr,
            r7.to_numpy(),
            color=ACCENT_BLUE,
            linewidth=1.8,
            label="7-day MA",
        )
        if len(vals) >= 30:
            self._ax.plot(
                d_arr,
                r30.to_numpy(),
                color=ACCENT_GREEN,
                linewidth=1.8,
                label="30-day MA",
            )
            self._register_hover(dates, "30-day MA", r30.to_numpy(), ACCENT_GREEN)
        self._register_hover(dates, "Daily", vals, ACCENT_GOLD)
        self._register_hover(dates, "7-day MA", r7.to_numpy(), ACCENT_BLUE)
        self._ax.legend(fontsize=8)
        self._fmt_x(dates)
        suffix = " (% Change)" if self._pct_mode else " — Rolling Averages"
        self._ax.set_title(f"{self._base}/{self._quote}{suffix}", fontsize=11)
        self._ax.set_ylabel(self._ylabel(), fontsize=8)

    def _draw_candle(self) -> None:
        """Monthly OHLC candlestick — drawn with two vectorised calls
        (vlines + bar) instead of two matplotlib calls per month."""
        dates, vals = self._series()
        if not dates:
            return
        s = pd.Series(vals, index=pd.DatetimeIndex(dates))
        m = s.resample(_MONTH_END).agg(["first", "max", "min", "last"]).dropna()
        if m.empty:
            return
        m.columns = ["open", "high", "low", "close"]
        # resample() keeps a DatetimeIndex; wrap it so the type is explicit
        x = mdates.date2num(pd.DatetimeIndex(m.index).to_pydatetime())
        o, h, l, c = (
            m[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close")
        )
        up = c >= o
        colors = np.where(up, ACCENT_GREEN, ACCENT_RED)
        self._ax.vlines(x, l, h, color=TEXT_MUTED, linewidth=0.8)
        # Doji months (open == close) still get a hairline body
        body = np.where(np.abs(c - o) > 0, c - o, np.maximum((h - l) * 0.01, 1e-9))
        self._ax.bar(x, body, bottom=o, color=colors, width=15, alpha=0.85)
        self._ax.xaxis_date()
        self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        self._fig.autofmt_xdate(rotation=30, ha="right")
        suffix = " (% Change)" if self._pct_mode else ""
        self._ax.set_title(
            f"{self._base}/{self._quote} — Monthly OHLC{suffix}", fontsize=11
        )
        self._ax.set_ylabel(self._ylabel(), fontsize=8)

    def _draw_scatter(self) -> None:
        dates, vals = self._series()
        if not dates:
            return
        x = np.arange(len(vals), dtype=float)
        self._ax.scatter(
            x, np.array(vals), c=np.array(vals), cmap="YlOrBr", s=12, alpha=0.7
        )
        suffix = " (% Change)" if self._pct_mode else " — Rate Scatter"
        self._ax.set_title(f"{self._base}/{self._quote}{suffix}", fontsize=11)
        self._ax.set_xlabel("Observation #", fontsize=8)
        self._ax.set_ylabel(self._ylabel(), fontsize=8)

    def _draw_multi(self, datasets: dict[str, dict[str, Any]]) -> None:
        all_dates: list[datetime] = []
        for i, (quote, data) in enumerate(datasets.items()):
            dates, vals = self._series(quote, data)
            if dates:
                color = PALETTE[i % len(PALETTE)]
                self._ax.plot(
                    np.array(dates),
                    np.array(vals),
                    color=color,
                    label=quote,
                    linewidth=1.8,
                )
                self._register_hover(dates, quote, vals, color)
                if len(dates) > len(all_dates):
                    all_dates = dates
        if self._ax.has_data():
            self._ax.legend(loc="upper left", fontsize=8, ncol=2)
        if self._pct_mode:
            self._ax.axhline(0, color=TEXT_DIM, linewidth=0.8)
        self._fmt_x(all_dates)
        suffix = " (% Change)" if self._pct_mode else " — Multi-Currency Overlay"
        self._ax.set_title(f"{self._base}{suffix}", fontsize=11)
        self._ax.set_ylabel(self._ylabel(), fontsize=8)

    def _draw_annual(
        self, annual_changes: dict[int, float], base: str, quote: str
    ) -> None:
        ax = self._ax
        if not annual_changes:
            self._draw_message("No annual data for this range")
            return
        years = list(annual_changes.keys())
        values = list(annual_changes.values())
        colors = [ACCENT_GREEN if v >= 0 else ACCENT_RED for v in values]
        bars = ax.bar(
            np.array(years, dtype=float),
            np.array(values),
            color=colors,
            width=0.7,
            edgecolor=BG_CARD,
        )
        ax.axhline(0, color=BORDER_COLOR, linewidth=0.8)
        ax.set_title(f"{base}/{quote} — Annual % Change", fontsize=11)
        ax.set_xlabel("Year", fontsize=9)
        ax.set_ylabel("% Change", fontsize=9)
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        # Labels are offset in screen points so they sit just outside the bar
        # regardless of the y-scale (fixed data offsets overlapped on small
        # ranges and floated far away on large ones).
        if len(values) <= 40:
            for bar, val in zip(bars, values):
                ax.annotate(
                    f"{val:+.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 3 if val >= 0 else -3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom" if val >= 0 else "top",
                    fontsize=7,
                    color=TEXT_MUTED,
                )
        ax.margins(y=0.12)

    def _draw_matrix(self, matrix: dict[str, Any], codes: list[str]) -> None:
        ax = self._ax
        n = len(codes)
        data_arr = np.full((n, n), np.nan)
        for i, b in enumerate(codes):
            for j, q in enumerate(codes):
                v = matrix.get(b, {}).get(q)
                if v is not None:
                    data_arr[i, j] = v

        # log10 spreads both 0.006 (JPY→EUR) and 160 (EUR→JPY) evenly, and
        # NaN cells (missing rates) render as background rather than as "0".
        with np.errstate(divide="ignore", invalid="ignore"):
            logv = np.log10(data_arr)
        masked = np.ma.masked_invalid(logv)
        cmap = matplotlib.colormaps["YlOrBr"].copy()
        cmap.set_bad(BG_DARK)
        im = ax.imshow(masked, cmap=cmap, aspect="auto")
        ax.grid(False)
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(codes, rotation=45, ha="right", fontsize=8, color=TEXT_MUTED)
        ax.set_yticklabels(codes, fontsize=8, color=TEXT_MUTED)
        ax.set_xlabel("Quote (column)", fontsize=8)
        ax.set_ylabel("Base (row)", fontsize=8)

        finite = logv[np.isfinite(logv)]
        lo, hi = (float(finite.min()), float(finite.max())) if finite.size else (0, 1)
        span = (hi - lo) or 1.0
        for i in range(n):
            for j in range(n):
                v = data_arr[i, j]
                if np.isnan(v):
                    ax.text(
                        j, i, "—", ha="center", va="center", fontsize=7, color=TEXT_DIM
                    )
                    continue
                # Dark text on light (yellow) cells, light text on dark cells
                t = (logv[i, j] - lo) / span
                ax.text(
                    j,
                    i,
                    f"{v:.4g}",
                    ha="center",
                    va="center",
                    fontsize=6 if n > 8 else 7,
                    color=BG_DARK if t < 0.6 else TEXT_PRIMARY,
                )
        ax.set_title("Cross-Rate Matrix (log scale colour)", fontsize=10)
        self._colorbar = self._fig.colorbar(im, ax=ax, fraction=0.03)
        self._colorbar.ax.tick_params(colors=TEXT_MUTED, labelsize=7)
        self._colorbar.set_label("log₁₀(rate)", color=TEXT_MUTED, fontsize=7)
        self._colorbar.outline.set_edgecolor(BORDER_COLOR)

    def _fmt_x(self, dates: list[datetime]) -> None:
        if not dates:
            return
        span = (max(dates) - min(dates)).days
        if span <= 30:
            self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        elif span <= 365:
            self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        else:
            self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        self._fig.autofmt_xdate(rotation=30, ha="right")

    def _draw_message(self, text: str) -> None:
        self._ax.text(
            0.5,
            0.5,
            text,
            ha="center",
            va="center",
            fontsize=11,
            color=TEXT_DIM,
            transform=self._ax.transAxes,
        )

    def _draw_placeholder(self) -> None:
        self._reset_axes()
        self._draw_message("Select currencies & range, then fetch data →")
        self._ax.axis("off")
        self._mpl_canvas.draw_idle()

    # ── hover read-out ────────────────────────────────────────────────────────

    def _ensure_hover_artists(self, x0: float):
        if not self._hover_artists:
            vline = self._ax.axvline(
                x0,
                color=TEXT_MUTED,
                linewidth=0.8,
                linestyle=":",
                visible=False,
            )
            dots = self._ax.scatter([], [], s=28, zorder=6, edgecolors=BG_DARK)
            dots.set_visible(False)
            tip = self._ax.annotate(
                "",
                xy=(0, 0),
                xycoords="axes fraction",
                xytext=(8, -8),
                textcoords="offset points",
                ha="left",
                va="top",
                fontsize=8,
                family="monospace",
                color=TEXT_PRIMARY,
                bbox=dict(
                    boxstyle="round,pad=0.4", fc=BG_CARD, ec=BORDER_COLOR, alpha=0.95
                ),
                visible=False,
                zorder=10,
            )
            self._hover_artists = (vline, dots, tip)
        return self._hover_artists

    def _on_hover(self, event) -> None:
        if (
            event.inaxes is not self._ax
            or event.xdata is None
            or self._hover_x is None
            or not self._hover_series
            or self._mode not in ("series", "multi")
            or (self._mode == "series" and self._seg.get() not in self._HOVERABLE)
        ):
            return
        xs = self._hover_x
        vline, dots, tip = self._ensure_hover_artists(float(xs[0]))
        idx = int(np.clip(np.searchsorted(xs, event.xdata), 0, len(xs) - 1))
        if idx > 0 and abs(xs[idx - 1] - event.xdata) < abs(xs[idx] - event.xdata):
            idx -= 1
        x = xs[idx]
        lines = [mdates.num2date(x).strftime("%Y-%m-%d")]
        pts, cols = [], []
        for label, (sx, sy), color in self._hover_series:
            j = int(np.clip(np.searchsorted(sx, x), 0, len(sx) - 1))
            y = sy[j]
            if not np.isfinite(y):
                continue
            val = f"{y:+.3f}%" if self._pct_mode else f"{y:.5g}"
            lines.append(f"{label:<9}{val:>10}")
            pts.append((sx[j], y))
            cols.append(color)
        vline.set_xdata([x, x])
        vline.set_visible(True)
        if pts:
            dots.set_offsets(np.array(pts))
            dots.set_facecolor(cols)
            dots.set_visible(True)
        tip.set_text("\n".join(lines))
        # Keep the tooltip inside the axes: flip to the left on the right half
        ax_x = self._ax.transAxes.inverted().transform((event.x, event.y))
        right_half = ax_x[0] > 0.6
        tip.xy = (ax_x[0], 0.98)
        tip.set_position((-8, -4) if right_half else (8, -4))
        # set_ha is a runtime-generated alias; use the real method name
        tip.set_horizontalalignment("right" if right_half else "left")
        tip.set_visible(True)
        self._mpl_canvas.draw_idle()

    def _on_leave(self, _event) -> None:
        if self._hover_artists:
            for a in self._hover_artists:
                a.set_visible(False)
            self._mpl_canvas.draw_idle()

    def _save(self) -> None:
        name = (
            f"{self._base}_{self._quote}_chart"
            if self._mode != "matrix"
            else "cross_rate_matrix"
        )
        filters = {"PNG (*.png)": ".png", "SVG (*.svg)": ".svg", "PDF (*.pdf)": ".pdf"}
        p, chosen = QFileDialog.getSaveFileName(
            self, "Save chart", f"{name}.png", ";;".join(filters)
        )
        if not p:
            return
        if not p.lower().endswith((".png", ".svg", ".pdf")):
            p += filters.get(chosen, ".png")
        # Hide the hover read-out so it doesn't end up in the export
        self._on_leave(None)
        self._fig.savefig(p, dpi=150, bbox_inches="tight", facecolor=BG_CARD)
