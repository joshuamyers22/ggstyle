"""Generate the checked-source v0.4 publication-finishing gallery."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

import ggstyle as gs


def finishing_figure() -> Figure:
    """Build labels, direct labels, numeric formats, and palette examples."""
    with gs.theme(gs.theme_spec("minimal", base_size=10)):
        figure, axes = plt.subplots(
            2,
            2,
            figsize=(9, 6.5),
            dpi=120,
            layout="constrained",
        )

    periods = np.arange(1, 9)
    revenue = np.array([2.1, 2.3, 2.6, 2.5, 2.9, 3.2, 3.4, 3.8]) * 1_000_000
    axes[0, 0].plot(periods, revenue, marker="o")
    gs.finish(
        axes[0, 0],
        title="Coherent labels",
        subtitle="Native axes, managed hierarchy",
        caption="Source: illustrative data",
        x=gs.axis(title="Quarter"),
        y=gs.axis(
            title="Revenue",
            labels=gs.label_currency("$", scale=1_000_000, decimals=1, suffix="M"),
        ),
    )

    direct = axes[0, 1]
    series = (
        ("North", [1.0, 1.5, 1.8, 2.2, 2.7, 3.04]),
        ("Central", [1.3, 1.7, 2.0, 2.4, 2.8, 3.00]),
        ("South", [0.8, 1.2, 1.7, 2.1, 2.6, 2.96]),
    )
    for label, values in series:
        direct.plot(np.arange(6), values, marker="o", label=label)
    gs.finish(
        direct,
        title="Collision-aware direct labels",
        direct_labels=gs.end_labels(),
        x=gs.axis(title="Period"),
        y=gs.axis(title="Index"),
    )

    share = axes[1, 0]
    categories = ["A", "B", "C", "D"]
    values = np.array([0.18, 0.27, 0.31, 0.24])
    share.bar(categories, values, color=gs.palette("sequential", n=4).colors)
    gs.finish(
        share,
        title="Explicit numeric semantics",
        y=gs.axis(title="Share", labels=gs.label_percent(decimals=0)),
    )

    palette_axis = axes[1, 1]
    selected = (
        gs.palette("qualitative"),
        gs.palette("sequential", n=8),
        gs.palette("diverging", n=9),
    )
    for row, palette in enumerate(selected):
        for column, color in enumerate(palette.colors):
            palette_axis.add_patch(Rectangle((column, row), 1, 0.72, color=color))
        palette_axis.text(-0.15, row + 0.36, palette.name, ha="right", va="center")
    palette_axis.set_xlim(-1.2, 9)
    palette_axis.set_ylim(-0.15, 3)
    palette_axis.set_title("Accessible palette policies", loc="left")
    palette_axis.axis("off")
    return figure


def theme_figure() -> Figure:
    """Build a compact comparison of every packaged theme."""
    figure = plt.figure(figsize=(9, 7), dpi=120, facecolor="white", layout="constrained")
    x = np.arange(4)
    for index, name in enumerate(gs.available_themes(), start=1):
        with gs.theme(name):
            ax = figure.add_subplot(3, 3, index)
            ax.plot(x, [0.8, 2.2, 1.5, 2.7], marker="o")
            ax.plot(x, [2.4, 1.7, 2.6, 1.1], marker="s")
            ax.set_title(name)
            ax.set_xlim(-0.2, 3.2)
            ax.set_ylim(0.5, 3.0)
            ax.set_xticks([0, 1, 2, 3])
            ax.set_yticks([1, 2, 3])
    return figure


def render(output_directory: Path) -> tuple[Path, Path]:
    """Render every gallery figure into an existing output directory."""
    destinations = (
        output_directory / "finishing_gallery.png",
        output_directory / "theme_gallery.png",
    )
    for builder, destination, size in (
        (finishing_figure, destinations[0], (9.0, 6.5)),
        (theme_figure, destinations[1], (9.0, 7.0)),
    ):
        figure = builder()
        try:
            gs.save(
                figure,
                destination,
                width=size[0],
                height=size[1],
                dpi=120,
                bbox="standard",
                metadata={"Creator": "ggstyle v0.4 gallery"},
                overwrite=True,
            )
        finally:
            plt.close(figure)
    return destinations


def main() -> None:
    """Render gallery images beside this script or into an explicit directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent)
    arguments = parser.parse_args()
    for destination in render(arguments.output_dir):
        print(destination)


if __name__ == "__main__":
    main()
