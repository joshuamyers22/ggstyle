"""Matplotlib adapter for applying computed date-axis ticks and labels."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Literal, cast

from matplotlib.axes import Axes
from matplotlib.ticker import FixedFormatter, FixedLocator


def render(
    ax: Axes,
    major_positions: Iterable[float],
    major_labels: Sequence[str],
    *,
    minor_positions: Iterable[float] | None,
    minor_labels: Sequence[str] | None,
    rotation: float | None,
    horizontal_alignment: str,
) -> None:
    """Apply precomputed tick presentation without owning date policy."""
    ax.xaxis.set_major_locator(FixedLocator([float(value) for value in major_positions]))
    ax.xaxis.set_major_formatter(FixedFormatter(major_labels))

    if minor_positions is None:
        ax.xaxis.set_minor_locator(FixedLocator([]))
    else:
        positions = [float(value) for value in minor_positions]
        ax.xaxis.set_minor_locator(FixedLocator(positions))
        labels = list(minor_labels) if minor_labels is not None else [""] * len(positions)
        ax.xaxis.set_minor_formatter(FixedFormatter(labels))

    if rotation is None:
        return
    alignment = cast(Literal["left", "center", "right"], horizontal_alignment)
    for text in ax.get_xticklabels():
        text.set_rotation(rotation)
        text.set_horizontalalignment(alignment)
