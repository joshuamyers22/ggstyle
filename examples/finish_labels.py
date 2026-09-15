"""Finish an existing Matplotlib axes with one coherent label request."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import ggstyle as gs


def main() -> None:
    """Save a labelled report figure next to this script."""
    quarters = np.arange(1, 9)
    revenue = np.array([2.1, 2.3, 2.6, 2.5, 2.9, 3.2, 3.4, 3.8]) * 1_000_000

    figure, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(quarters, revenue, marker="o")
    gs.finish(
        ax,
        title="Revenue",
        subtitle="Quarterly revenue continues to grow",
        caption="Source: illustrative company data",
        theme=gs.theme_spec(
            "minimal",
            base_size=11,
            overrides={"axes.titlesize": 14},
        ),
        x=gs.axis(title="Quarter"),
        y=gs.axis(
            title="Revenue",
            labels=gs.label_currency("$", scale=1_000_000, suffix="M"),
        ),
    )
    figure.savefig(Path(__file__).with_suffix(".png"), dpi=160)
    plt.close(figure)


if __name__ == "__main__":
    main()
