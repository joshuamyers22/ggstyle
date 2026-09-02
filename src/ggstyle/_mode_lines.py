"""Line-artist transformations for date-axis coordinate mode changes."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import numpy as np
from matplotlib.axes import Axes

from ._annotations import Annotation


def remember_calendar_positions(
    ax: Axes,
    originals: dict[int, np.ndarray],
    annotations: Iterable[Annotation],
) -> None:
    """Snapshot data-line x positions while excluding managed annotations."""
    managed_artist_ids = {
        id(artist) for annotation in annotations for artist in annotation.artists
    }
    for line in ax.lines:
        line_id = id(line)
        if line_id in managed_artist_ids or line_id in originals:
            continue
        originals[line_id] = np.asarray(line.get_xdata(orig=False), dtype=float)


def use_collapsed_positions(
    ax: Axes,
    originals: dict[int, np.ndarray],
    collapse: Callable[[np.ndarray], np.ndarray],
) -> None:
    """Map snapshotted data lines into observation-ordinal positions."""
    for line in ax.lines:
        original = originals.get(id(line))
        if original is not None:
            line.set_xdata(collapse(original))


def restore_calendar_positions(ax: Axes, originals: dict[int, np.ndarray]) -> None:
    """Restore snapshotted data lines to calendar positions."""
    for line in ax.lines:
        original = originals.get(id(line))
        if original is not None:
            line.set_xdata(original)
