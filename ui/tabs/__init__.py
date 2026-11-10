"""
All tab views for the Frankfurter GUI (originally by Florian van den
Bersselaar). One module per tab; ``BaseTab`` and shared helpers in ``base``.
"""

from ui.tabs.base import BaseTab
from ui.tabs.compare import CompareTab
from ui.tabs.converter import ConverterTab
from ui.tabs.dashboard import DashboardTab
from ui.tabs.detail import CurrencyDetailTab
from ui.tabs.heatmap import HeatmapTab
from ui.tabs.historical import HistoricalTab
from ui.tabs.matrix import MatrixTab
from ui.tabs.providers import ProvidersTab
from ui.tabs.stats import StatsTab
from ui.tabs.timeseries import TimeSeriesTab
from ui.tabs.watchlist import WatchlistTab

__all__ = [
    "BaseTab",
    "CompareTab",
    "ConverterTab",
    "CurrencyDetailTab",
    "DashboardTab",
    "HeatmapTab",
    "HistoricalTab",
    "MatrixTab",
    "ProvidersTab",
    "StatsTab",
    "TimeSeriesTab",
    "WatchlistTab",
]
