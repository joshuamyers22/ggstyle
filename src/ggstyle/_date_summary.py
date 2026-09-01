"""Pure date-summary policy, independent of Matplotlib axis state."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import _cadence


def minor_below(cadence: _cadence.Cadence) -> _cadence.Cadence | None:
    """Return a sensible minor cadence one step finer than ``cadence``."""
    below = {
        "year": _cadence.Cadence("quarter"),
        "quarter": _cadence.Cadence("month"),
        "month": _cadence.Cadence("week"),
        "week": _cadence.Cadence("day"),
        "day": _cadence.Cadence("hour", 6),
        "hour": _cadence.Cadence("minute", 15),
        "minute": None,
    }
    return below.get(cadence.unit)


def infer_frequency(observations: pd.DatetimeIndex) -> str | None:
    """Infer a stable frequency description from unique observations."""
    if len(observations) < 2:
        return None
    if len(observations) >= 3:
        try:
            inferred = pd.infer_freq(observations)
        except ValueError:
            inferred = None
        if inferred is not None:
            return inferred
    values = np.asarray(observations, dtype="datetime64[ns]").astype("int64")
    deltas = np.diff(values)
    median = pd.Timedelta(int(np.median(deltas)), unit="ns")
    return f"irregular (median {median})"


def format_date_range(start: pd.Timestamp, end: pd.Timestamp) -> str:
    """Format an inclusive range without platform-specific directives."""
    left = f"{start:%b} {start.day}, {start.year}"
    right = f"{end:%b} {end.day}, {end.year}"
    return f"{left} - {right}"
