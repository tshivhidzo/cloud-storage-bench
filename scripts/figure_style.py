"""
figure_style.py -- CPUT/Dr Kabaso figure presentation: Times New Roman, black
and white, grayscale-friendly line styles and hatches. Call apply() at the top
of any plotting script so every Chapter 5 figure is produced in the correct font
and a print-safe monochrome cycle by construction.
"""
from __future__ import annotations


def apply():
    import matplotlib as mpl
    from cycler import cycler
    mpl.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "axes.prop_cycle": cycler(color=["black", "0.35", "0.6"]) +
                           cycler(linestyle=["-", "--", ":"]),
        "axes.grid": True, "grid.color": "0.85", "grid.linewidth": 0.5,
        "figure.dpi": 150, "savefig.dpi": 300,
        "axes.edgecolor": "black", "axes.linewidth": 0.8,
        "legend.frameon": False, "image.cmap": "gray",
    })


HATCHES = ["", "///", "...", "xxx", "\\\\\\"]  # for bar charts, grayscale-safe
