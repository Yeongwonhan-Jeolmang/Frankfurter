"""
ChartPanel — embedded matplotlib with 8 chart types. (Worked on by Anna Zieleman and Simon Roberge)
"""

import customtkinter as ctk
import matplotlib

matplotlib.use("TkAgg")
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import pandas as pd
import numpy as np
from datetime import datetime

from ui.theme import *


def _style(ax):
    ax.set_facecolor(BG_DARK)
    ax.figure.set_facecolor(BG_CARD)
    for sp in ax.spines.values():
        sp.set_edgecolor(BORDER_COLOR)
    ax.tick_params(colors=TEXT_MUTED, labelsize=8)
    ax.xaxis.label.set_color(TEXT_MUTED)
    ax.yaxis.label.set_color(TEXT_MUTED)
    ax.title.set_color(TEXT_PRIMARY)
    ax.grid(True, color=BORDER_COLOR, linestyle="--", alpha=0.35)


class ChartPanel(ctk.CTkFrame):
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

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG_CARD, corner_radius=CORNER_RADIUS, **kw)
        self._data: dict = {}
        self._base: str = "EUR"
        self._quote: str = "USD"
        self._build_toolbar()
        self._build_figure()

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=PAD_MD, pady=(PAD_MD, 0))
        ctk.CTkLabel(bar, text="Chart:", font=FONT_LABEL, text_color=TEXT_MUTED).pack(
            side="left"
        )
        self._seg = ctk.CTkSegmentedButton(
            bar,
            values=self.CHART_TYPES,
            font=FONT_SMALL,
            fg_color=BG_INPUT,
            selected_color=ACCENT_GOLD,
            selected_hover_color="#B8960C",
            unselected_color=BG_INPUT,
            unselected_hover_color=BG_HOVER,
            text_color=TEXT_PRIMARY,
            command=lambda _: self._render(),
        )
        self._seg.set("Line")
        self._seg.pack(side="left", padx=PAD_MD)
        ctk.CTkButton(
            bar,
            text="💾 PNG",
            width=80,
            height=26,
            fg_color=BG_INPUT,
            hover_color=BG_HOVER,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_PRIMARY,
            font=FONT_SMALL,
            command=self._save,
        ).pack(side="right")

    def _build_figure(self):
        self._fig = Figure(figsize=(8, 4), dpi=96)
        self._fig.set_facecolor(BG_CARD)
        self._ax = self._fig.add_subplot(111)
        _style(self._ax)
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(
            fill="both", expand=True, padx=PAD_MD, pady=PAD_SM
        )
        tf = ctk.CTkFrame(self, fg_color=BG_CARD, height=28)
        tf.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))
        nav = NavigationToolbar2Tk(self._canvas, tf)
        nav.config(background=BG_CARD)
        for ch in nav.winfo_children():
            try:
                ch.config(background=BG_CARD)
            except:
                pass
        nav.update()
        self._draw_placeholder()

    # ── public ────────────────────────────────────────────────────────────────

    def plot_series(self, data: dict, base: str, quote: str):
        self._data = data
        self._base = base
        self._quote = quote
        self._render()

    def plot_multi(self, datasets: dict[str, dict], base: str):
        self._data = {"_multi": datasets}
        self._base = base
        self._quote = "multi"
        self._seg.set("Multi-Overlay")
        self._render()

    def plot_heatmap(self, annual_changes: dict[int, float], base: str, quote: str):
        """Year-by-year bar chart coloured green/red."""
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        _style(ax)
        years = list(annual_changes.keys())
        values = list(annual_changes.values())
        colors = [ACCENT_GREEN if v >= 0 else ACCENT_RED for v in values]
        bars = ax.bar(years, values, color=colors, width=0.7, edgecolor=BG_CARD)
        ax.axhline(0, color=BORDER_COLOR, linewidth=0.8)
        ax.set_title(f"{base}/{quote} — Annual % Change", fontsize=11)
        ax.set_xlabel("Year", fontsize=9)
        ax.set_ylabel("% Change", fontsize=9)
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (0.3 if val >= 0 else -0.8),
                f"{val:+.1f}%",
                ha="center",
                va="bottom",
                fontsize=7,
                color=TEXT_MUTED,
            )
        self._fig.tight_layout()
        self._canvas.draw()

    def plot_matrix_heatmap(self, matrix: dict, codes: list):
        """Cross-rate correlation-style heatmap."""
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        n = len(codes)
        data_arr = np.zeros((n, n))
        for i, b in enumerate(codes):
            for j, q in enumerate(codes):
                v = matrix.get(b, {}).get(q)
                data_arr[i, j] = v if v is not None else 0

        im = ax.imshow(np.log1p(data_arr), cmap="YlOrBr", aspect="auto")
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(codes, rotation=45, ha="right", fontsize=8, color=TEXT_MUTED)
        ax.set_yticklabels(codes, fontsize=8, color=TEXT_MUTED)
        for i in range(n):
            for j in range(n):
                v = matrix.get(codes[i], {}).get(codes[j])
                if v is not None:
                    ax.text(
                        j,
                        i,
                        f"{v:.2f}",
                        ha="center",
                        va="center",
                        fontsize=6,
                        color=TEXT_PRIMARY,
                    )
        ax.set_facecolor(BG_DARK)
        ax.figure.set_facecolor(BG_CARD)
        ax.set_title(
            "Cross-Rate Matrix (log scale colour)", fontsize=10, color=TEXT_PRIMARY
        )
        cb = self._fig.colorbar(im, ax=ax, fraction=0.03)
        cb.ax.tick_params(colors=TEXT_MUTED, labelsize=7)
        self._fig.tight_layout()
        self._canvas.draw()

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render(self):
        if not self._data:
            self._draw_placeholder()
            return
        ctype = self._seg.get()
        self._fig.clear()
        self._ax = self._fig.add_subplot(111)
        _style(self._ax)

        if "_multi" in self._data:
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

        self._fig.tight_layout()
        self._canvas.draw()

    def _series(self, quote=None):
        target = quote or self._quote
        dates, vals = [], []
        for d, day in sorted(self._data.get("rates", {}).items()):
            if target in day:
                try:
                    dates.append(datetime.strptime(d, "%Y-%m-%d"))
                    vals.append(day[target])
                except:
                    pass
        return dates, vals

    def _draw_line(self, all_q=False):
        rates = self._data.get("rates", {})
        if not rates:
            return
        all_quotes = list(next(iter(rates.values())).keys())
        if all_q:
            for i, q in enumerate(all_quotes[: len(PALETTE)]):
                dates, vals = self._series(q)
                if dates:
                    self._ax.plot(dates, vals, color=PALETTE[i], label=q, linewidth=1.6)
            self._ax.legend(loc="upper left", fontsize=7, ncol=2)
        else:
            dates, vals = self._series()
            if dates:
                self._ax.plot(dates, vals, color=ACCENT_GOLD, linewidth=2)
                self._ax.scatter(
                    [dates[-1]], [vals[-1]], color=ACCENT_GOLD, s=50, zorder=5
                )
        self._fmt_x(dates if not all_q else [])
        self._ax.set_title(f"{self._base}/{self._quote}", fontsize=11)

    def _draw_area(self):
        dates, vals = self._series()
        if not dates:
            return
        self._ax.fill_between(dates, vals, alpha=0.25, color=ACCENT_GOLD)
        self._ax.plot(dates, vals, color=ACCENT_GOLD, linewidth=2)
        self._fmt_x(dates)
        self._ax.set_title(f"{self._base}/{self._quote} — Area", fontsize=11)

    def _draw_bar(self):
        dates, vals = self._series()
        if not dates:
            return
        colors = [ACCENT_GOLD] + [
            ACCENT_GREEN if vals[i] >= vals[i - 1] else ACCENT_RED
            for i in range(1, len(vals))
        ]
        self._ax.bar(dates, vals, color=colors, width=0.8)
        self._fmt_x(dates)
        self._ax.set_title(f"{self._base}/{self._quote} — Bar", fontsize=11)

    def _draw_histogram(self):
        _, vals = self._series()
        if not vals:
            return
        self._ax.hist(vals, bins=35, color=ACCENT_BLUE, edgecolor=BG_DARK, alpha=0.85)
        mean = np.mean(vals)
        self._ax.axvline(
            mean, color=ACCENT_GOLD, linestyle="--", label=f"Mean: {mean:.4f}"
        )
        self._ax.legend(fontsize=8)
        self._ax.set_title(f"{self._base}/{self._quote} — Distribution", fontsize=11)

    def _draw_rolling(self):
        dates, vals = self._series()
        if len(vals) < 7:
            return
        s = pd.Series(vals, index=dates)
        r7 = s.rolling(7).mean()
        r30 = s.rolling(30).mean()
        self._ax.plot(
            dates, vals, color=ACCENT_GOLD, alpha=0.3, linewidth=1, label="Daily"
        )
        self._ax.plot(
            r7.index, r7.values, color=ACCENT_BLUE, linewidth=1.8, label="7-day MA"
        )
        self._ax.plot(
            r30.index, r30.values, color=ACCENT_GREEN, linewidth=1.8, label="30-day MA"
        )
        self._ax.legend(fontsize=8)
        self._fmt_x(dates)
        self._ax.set_title(
            f"{self._base}/{self._quote} — Rolling Averages", fontsize=11
        )

    def _draw_candle(self):
        """Monthly OHLC candlestick using bar chart approximation."""
        dates, vals = self._series()
        if not dates:
            return
        s = pd.Series(vals, index=pd.DatetimeIndex(dates))
        m = s.resample("ME").agg(["first", "max", "min", "last"])
        m.columns = ["open", "high", "low", "close"]
        for idx, row in m.iterrows():
            color = ACCENT_GREEN if row["close"] >= row["open"] else ACCENT_RED
            self._ax.plot(
                [idx, idx], [row["low"], row["high"]], color=TEXT_MUTED, linewidth=0.8
            )
            self._ax.bar(
                idx,
                row["close"] - row["open"],
                bottom=row["open"],
                color=color,
                width=15,
                alpha=0.8,
            )
        self._ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        self._fig.autofmt_xdate(rotation=30, ha="right")
        self._ax.set_title(f"{self._base}/{self._quote} — Monthly OHLC", fontsize=11)

    def _draw_scatter(self):
        dates, vals = self._series()
        if not dates:
            return
        x = list(range(len(vals)))
        self._ax.scatter(x, vals, c=vals, cmap="YlOrBr", s=12, alpha=0.7)
        self._ax.set_title(f"{self._base}/{self._quote} — Rate Scatter", fontsize=11)

    def _draw_multi(self, datasets):
        for i, (quote, data) in enumerate(datasets.items()):
            dates, vals = [], []
            for d, day in sorted(data.get("rates", {}).items()):
                if quote in day:
                    try:
                        dates.append(datetime.strptime(d, "%Y-%m-%d"))
                        vals.append(day[quote])
                    except:
                        pass
            if dates:
                self._ax.plot(
                    dates,
                    vals,
                    color=PALETTE[i % len(PALETTE)],
                    label=quote,
                    linewidth=1.8,
                )
        self._ax.legend(loc="upper left", fontsize=8, ncol=2)
        self._ax.set_title(f"{self._base} — Multi-Currency Overlay", fontsize=11)

    def _fmt_x(self, dates):
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

    def _draw_placeholder(self):
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        _style(ax)
        ax.text(
            0.5,
            0.5,
            "Select currencies & range, then fetch data →",
            ha="center",
            va="center",
            fontsize=12,
            color=TEXT_DIM,
            transform=ax.transAxes,
        )
        ax.axis("off")
        self._canvas.draw()

    def _save(self):
        from tkinter import filedialog

        p = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("SVG", "*.svg")],
            title="Save chart",
        )
        if p:
            self._fig.savefig(p, dpi=150, bbox_inches="tight", facecolor=BG_CARD)
