"""Rendering adapter for independently cadenced date gridlines."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.artist import Artist
from matplotlib.axes import Axes

from . import _cadence

TickPositions = Callable[
    [_cadence.Cadence, pd.Timestamp, pd.Timestamp],
    tuple[pd.DatetimeIndex, np.ndarray],
]


def render(
    ax: Axes,
    existing: Iterable[Artist],
    spec: Any,
    style_overrides: dict[str, Any],
    lo: pd.Timestamp,
    hi: pd.Timestamp,
    positions_for: TickPositions,
) -> list[Artist]:
    """Replace managed grid artists and return the current artist collection."""
    for artist in existing:
        artist.remove()
    if spec is None:
        return []

    cadence = _cadence.resolve(spec)
    _, positions = positions_for(cadence, lo, hi)
    style: dict[str, Any] = {
        "color": plt.rcParams.get("grid.color", "0.85"),
        "linewidth": plt.rcParams.get("grid.linewidth", 0.8),
        "linestyle": plt.rcParams.get("grid.linestyle", "-"),
        "zorder": 0,
    }
    style.update(style_overrides)
    return [ax.axvline(float(position), **style) for position in positions]
