"""Central design tokens brought to you by Florian van den Bersselaar"""

BG_DARK = "#0D1117"
BG_CARD = "#161B22"
BG_INPUT = "#1C2128"
BG_HOVER = "#21262D"
BG_SELECTED = "#2D333B"

ACCENT_GOLD = "#D4AF37"
ACCENT_GREEN = "#3FB950"
ACCENT_RED = "#F85149"
ACCENT_BLUE = "#58A6FF"
ACCENT_PURPLE = "#BC8CFF"
ACCENT_ORANGE = "#FF9F1C"
ACCENT_CYAN = "#2EC4B6"

TEXT_PRIMARY = "#E6EDF3"
TEXT_MUTED = "#7D8590"
TEXT_DIM = "#484F58"

BORDER_COLOR = "#30363D"

FONT_DISPLAY = ("Georgia", 22, "bold")
FONT_HEADING = ("Georgia", 14, "bold")
FONT_SUBHEAD = ("Georgia", 11, "bold")
FONT_BODY = ("Helvetica Neue", 11)
FONT_MONO = ("Courier New", 11)
FONT_MONO_LG = ("Courier New", 18, "bold")
FONT_SMALL = ("Helvetica Neue", 9)
FONT_LABEL = ("Helvetica Neue", 10)

CORNER_RADIUS = 8
PAD_SM = 6
PAD_MD = 12
PAD_LG = 20

PALETTE = [
    ACCENT_GOLD,
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_RED,
    ACCENT_PURPLE,
    ACCENT_ORANGE,
    ACCENT_CYAN,
    "#E71D36",
    "#F72585",
    "#4CC9F0",
    "#7BF1A8",
    "#FFD166",
]

MPL_STYLE = {
    "figure.facecolor": BG_CARD,
    "axes.facecolor": BG_DARK,
    "axes.edgecolor": BORDER_COLOR,
    "axes.labelcolor": TEXT_MUTED,
    "xtick.color": TEXT_MUTED,
    "ytick.color": TEXT_MUTED,
    "text.color": TEXT_PRIMARY,
    "grid.color": BORDER_COLOR,
    "grid.linestyle": "--",
    "grid.alpha": 0.4,
    "lines.linewidth": 2,
    "legend.facecolor": BG_CARD,
    "legend.edgecolor": BORDER_COLOR,
    "legend.labelcolor": TEXT_PRIMARY,
}
