"""Render the built-in qualitative, sequential, and diverging palettes."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import ggstyle as gs


def main() -> None:
    """Save a compact palette reference image next to this script."""
    palettes = [
        gs.palette("qualitative"),
        gs.palette("sequential", n=8),
        gs.palette("diverging", n=9),
    ]
    with gs.theme("minimal"):
        figure, axes = plt.subplots(len(palettes), 1, figsize=(8, 3.6))
        for ax, selected in zip(axes, palettes, strict=True):
            for index, color in enumerate(selected.colors):
                ax.add_patch(Rectangle((index, 0), 1, 1, color=color))
            ax.set_xlim(0, len(selected.colors))
            ax.set_ylim(0, 1)
            ax.set_title(selected.name, loc="left")
            ax.axis("off")
        figure.tight_layout()
        figure.savefig(Path(__file__).with_suffix(".png"), dpi=160)
        plt.close(figure)


if __name__ == "__main__":
    main()
