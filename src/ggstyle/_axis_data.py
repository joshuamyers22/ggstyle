"""Observation collection and validation for adopted Matplotlib axes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import matplotlib.dates as mdates
import numpy as np
from matplotlib.axes import Axes

from ._frames import to_datetime_index

MissingPolicy = Literal["raise", "drop"]

_NUM_MIN, _NUM_MAX = -220_000, 200_000


@dataclass(frozen=True)
class AxisData:
    """Collected observation numbers and their provenance."""

    numbers: np.ndarray
    missing_values: int
    trusted: bool


def collect(
    ax: Axes,
    data: Any,
    *,
    existing: AxisData,
    missing: MissingPolicy,
) -> AxisData:
    """Combine explicit dates, existing observations, and plotted line data."""
    if missing not in ("raise", "drop"):
        raise ValueError(f"missing must be 'raise' or 'drop', got {missing!r}")

    batches: list[np.ndarray] = []
    if existing.numbers.size:
        batches.append(existing.numbers.copy())
    missing_values = existing.missing_values
    trusted = existing.trusted

    if data is not None:
        index = to_datetime_index(data)
        missing_count = int(np.count_nonzero(index.isna()))
        if missing_count and missing == "raise":
            raise ValueError(
                f"date data contains {missing_count} missing value(s); "
                "pass missing='drop' to exclude them explicitly"
            )
        missing_values += missing_count
        batches.append(np.asarray(mdates.date2num(index[index.notna()]), dtype=float))
        trusted = True

    for line in ax.lines:
        values = np.asarray(line.get_xdata(orig=False), dtype=float)
        if values.size:
            batches.append(values)

    if not batches:
        numbers = np.empty(0, dtype=float)
    else:
        stacked = np.concatenate(batches)
        numbers = np.unique(stacked[np.isfinite(stacked)])
    return AxisData(numbers, missing_values, trusted)


def validate(ax: Axes, data: AxisData) -> None:
    """Raise when collected observations do not plausibly represent dates."""
    if data.numbers.size == 0:
        return
    if not data.trusted and not _has_date_converter(ax):
        raise TypeError(
            "x axis does not look like dates: matplotlib has no date converter "
            "installed on it. Plot datetimes, or pass the dates explicitly via "
            "dates(ax, data=...)."
        )

    lo, hi = float(data.numbers[0]), float(data.numbers[-1])
    if lo < _NUM_MIN or hi > _NUM_MAX:
        raise TypeError(
            "x axis does not look like dates: values span "
            f"{lo:.6g} to {hi:.6g}, which is outside the plausible range for "
            "matplotlib date numbers."
        )


def _has_date_converter(ax: Axes) -> bool:
    axis = ax.xaxis
    getter = getattr(axis, "get_converter", None)
    converter = getter() if getter is not None else getattr(axis, "converter", None)
    if converter is None:
        return False
    if isinstance(converter, (mdates.DateConverter, mdates.ConciseDateConverter)):
        return True
    return "Date" in type(converter).__name__
