"""Pure coordinate transforms for calendar and collapsed date axes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

CoordinateMode = Literal["show", "collapse"]


@dataclass(frozen=True)
class CollapsedDateMapping:
    """Immutable numeric policy for a prepared collapsed-date registry."""

    knots: np.ndarray

    def __init__(self, knots: np.ndarray) -> None:
        object.__setattr__(self, "knots", canonical_knots(knots))

    def forward(self, values: np.ndarray) -> np.ndarray:
        """Map native date numbers to observation ordinals."""
        data, mask = _array_and_mask(values)
        shape = data.shape
        flat = data.reshape(-1)
        indexes = np.arange(self.knots.size, dtype=float)
        if self.knots.size == 1:
            return _restore_mask((flat - self.knots[0]).reshape(shape), mask)

        positions = np.interp(flat, self.knots, indexes)
        step = _typical_step(self.knots)
        below = flat < self.knots[0]
        above = flat > self.knots[-1]
        positions[below] = (flat[below] - self.knots[0]) / step
        positions[above] = indexes[-1] + (flat[above] - self.knots[-1]) / step
        return _restore_mask(positions.reshape(shape), mask)

    def inverse(self, positions: np.ndarray) -> np.ndarray:
        """Map observation ordinals back to native date numbers."""
        data, mask = _array_and_mask(positions)
        shape = data.shape
        flat = data.reshape(-1)
        indexes = np.arange(self.knots.size, dtype=float)
        if self.knots.size == 1:
            return _restore_mask((self.knots[0] + flat).reshape(shape), mask)

        values = np.interp(flat, indexes, self.knots)
        step = _typical_step(self.knots)
        below = flat < 0
        above = flat > indexes[-1]
        values[below] = self.knots[0] + flat[below] * step
        values[above] = self.knots[-1] + (flat[above] - indexes[-1]) * step
        return _restore_mask(values.reshape(shape), mask)


def dates_to_positions(
    values: np.ndarray, knots: np.ndarray, mode: CoordinateMode
) -> np.ndarray:
    """Map matplotlib date numbers into the selected coordinate system."""
    if mode == "show":
        data, mask = _array_and_mask(values)
        return _restore_mask(data, mask)

    return CollapsedDateMapping(knots).forward(values)


def positions_to_dates(
    positions: np.ndarray, knots: np.ndarray, mode: CoordinateMode
) -> np.ndarray:
    """Map axis positions back to matplotlib date numbers."""
    if mode == "show":
        data, mask = _array_and_mask(positions)
        return _restore_mask(data, mask)

    return CollapsedDateMapping(knots).inverse(positions)


def canonical_knots(knots: np.ndarray) -> np.ndarray:
    """Return finite, sorted, unique knots or reject an empty registry."""
    values = np.asarray(knots, dtype=float).reshape(-1)
    values = np.unique(values[np.isfinite(values)])
    if values.size == 0:
        raise ValueError("collapsed coordinates require at least one observed date")
    values.setflags(write=False)
    return values


def _typical_step(knots: np.ndarray) -> float:
    if knots.size == 1:
        return 1.0
    return float(np.median(np.diff(knots)))


def _array_and_mask(values: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    masked = np.ma.isMaskedArray(values)
    array = np.ma.asarray(values, dtype=float)
    data = np.array(np.ma.getdata(array), dtype=float, copy=True)
    mask = np.ma.getmaskarray(array).copy() if masked else None
    return data, mask


def _restore_mask(values: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    if mask is None:
        return values
    return np.ma.array(values, mask=mask, copy=False)
