"""Tick-position policy independent of Matplotlib axes and artists."""

from __future__ import annotations

import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from . import _cadence, _coordinates

MAX_TICKS = 10_000


def positions_for_cadence(
    cadence: _cadence.Cadence,
    lo: pd.Timestamp,
    hi: pd.Timestamp,
    *,
    mode: _coordinates.CoordinateMode,
    knots: np.ndarray,
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Return label dates and axis positions for a visible date range."""
    estimated = int(max((hi - lo).total_seconds(), 0) / cadence.approx_seconds) + 3
    if estimated > MAX_TICKS:
        raise ValueError(
            f"tick cadence would create about {estimated:,} ticks; choose a "
            "coarser cadence or narrow the visible range"
        )

    candidates = _cadence.periods_between(cadence, lo, hi)
    if len(candidates) > MAX_TICKS:
        raise ValueError(
            f"tick cadence would create {len(candidates):,} ticks; choose a "
            "coarser cadence or narrow the visible range"
        )
    if len(candidates) == 0:
        return pd.DatetimeIndex([]), np.empty(0)

    candidate_numbers = np.asarray(mdates.date2num(candidates), dtype=float)
    if mode == "show":
        positions = candidate_numbers
        labels = candidates
    else:
        positions, labels = _collapsed_positions(
            cadence, candidates, candidate_numbers, knots
        )
        if positions.size == 0:
            return pd.DatetimeIndex([]), positions

    limit_numbers = np.asarray(mdates.date2num(pd.DatetimeIndex([lo, hi])), dtype=float)
    limits = _coordinates.dates_to_positions(limit_numbers, knots, mode)
    inside = (positions >= min(limits) - 1e-9) & (positions <= max(limits) + 1e-9)
    return pd.DatetimeIndex(labels)[inside], positions[inside]


def _collapsed_positions(
    cadence: _cadence.Cadence,
    candidates: pd.DatetimeIndex,
    candidate_numbers: np.ndarray,
    knots: np.ndarray,
) -> tuple[np.ndarray, pd.DatetimeIndex]:
    if knots.size == 0:
        raise ValueError("collapsed tick placement requires observed dates")

    if cadence.anchor == "end":
        indexes = np.searchsorted(knots, candidate_numbers, side="right") - 1
        previous = np.concatenate(([-np.inf], candidate_numbers[:-1]))
        inside_period = knots[np.clip(indexes, 0, knots.size - 1)] > previous
    else:
        indexes = np.searchsorted(knots, candidate_numbers, side="left")
        following = np.concatenate((candidate_numbers[1:], [np.inf]))
        inside_period = knots[np.clip(indexes, 0, knots.size - 1)] < following

    valid = (indexes >= 0) & (indexes < knots.size) & inside_period
    return indexes[valid].astype(float), candidates[valid]
