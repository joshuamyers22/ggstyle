"""Pure coordinate transforms for calendar and collapsed date axes."""

from __future__ import annotations

from typing import Literal

import numpy as np

CoordinateMode = Literal["show", "collapse"]


def dates_to_positions(
    values: np.ndarray, knots: np.ndarray, mode: CoordinateMode
) -> np.ndarray:
    """Map matplotlib date numbers into the selected coordinate system."""
    values = np.atleast_1d(np.asarray(values, dtype=float))
    if mode == "show":
        return values

    knots = _require_knots(knots)
    indexes = np.arange(knots.size, dtype=float)
    if knots.size == 1:
        return values - knots[0]

    positions = np.interp(values, knots, indexes)
    step = _typical_step(knots)
    below = values < knots[0]
    above = values > knots[-1]
    positions[below] = (values[below] - knots[0]) / step
    positions[above] = indexes[-1] + (values[above] - knots[-1]) / step
    return positions


def positions_to_dates(
    positions: np.ndarray, knots: np.ndarray, mode: CoordinateMode
) -> np.ndarray:
    """Map axis positions back to matplotlib date numbers."""
    positions = np.atleast_1d(np.asarray(positions, dtype=float))
    if mode == "show":
        return positions

    knots = _require_knots(knots)
    indexes = np.arange(knots.size, dtype=float)
    if knots.size == 1:
        return np.full_like(positions, knots[0])

    values = np.interp(positions, indexes, knots)
    step = _typical_step(knots)
    below = positions < 0
    above = positions > indexes[-1]
    values[below] = knots[0] + positions[below] * step
    values[above] = knots[-1] + (positions[above] - indexes[-1]) * step
    return values


def _require_knots(knots: np.ndarray) -> np.ndarray:
    values = np.atleast_1d(np.asarray(knots, dtype=float))
    if values.size == 0:
        raise ValueError("collapsed coordinates require at least one observed date")
    return values


def _typical_step(knots: np.ndarray) -> float:
    return float(np.median(np.diff(knots))) or 1.0
