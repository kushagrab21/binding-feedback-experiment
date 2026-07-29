"""Shared style for all figures — reference dataviz palette, light mode."""
import matplotlib as mpl

# Reference palette (light mode)
SURFACE   = "#fcfcfb"
INK       = "#0b0b0b"
INK2      = "#52514e"
MUTED     = "#898781"
GRID      = "#e1e0d9"
BASELINE  = "#c3c2b7"

# Categorical slots, fixed order
S1_BLUE    = "#2a78d6"
S2_ORANGE  = "#eb6834"
S3_AQUA    = "#1baf7a"
S4_YELLOW  = "#eda100"
S5_MAGENTA = "#e87ba4"
S6_GREEN   = "#008300"
S7_VIOLET  = "#4a3aa7"
S8_RED     = "#e34948"


# --- Editorial theme (validated 2026-07-29: all six checks pass, light mode) ---
ADVISORY  = "#c2801f"   # warm amber: the baseline condition
BINDING   = "#1668a1"   # deep blue: the intervention
S_BLUE    = "#1668a1"
S_OCHRE   = "#c2801f"
S_PLUM    = "#9550a6"
S_JADE    = "#2f8f6e"
S_PERI    = "#6a74c9"
S_BRICK   = "#b34a38"

CRITICAL = "#d03b3b"   # status: used only for the negative-Δ annotation zone

def apply():
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "text.color": INK,
        "axes.edgecolor": BASELINE,
        "axes.labelcolor": INK2,
        "axes.titlecolor": INK,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK2,
        "ytick.labelcolor": INK2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 1.0,
        "legend.frameon": False,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.25,
    })
