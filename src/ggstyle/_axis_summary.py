"""Immutable public summary contract for a configured date axis."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass(frozen=True)
class AxisSummary:
    """Describe the data and configuration behind a date axis.

    Parameters
    ----------
    mode : {"show", "collapse"}
        Active coordinate mode.
    observations : int
        Number of unique, non-missing observed dates.
    start : pandas.Timestamp or None
        First observed date.
    end : pandas.Timestamp or None
        Final observed date.
    inferred_frequency : str or None
        Pandas frequency alias, or a median-spacing description for irregular data.
    major_cadence : str
        Resolved major tick cadence or ``"explicit"``.
    minor_cadence : str or None
        Resolved minor tick cadence.
    timezone : str or None
        Label display timezone.
    missing_values : int
        Number of explicitly supplied missing dates that were dropped.

    Notes
    -----
    Summaries contain plain values and can be logged, tested, or serialized without
    inspecting matplotlib artists.
    """

    mode: Literal["show", "collapse"]
    observations: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    inferred_frequency: str | None
    major_cadence: str
    minor_cadence: str | None
    timezone: str | None
    missing_values: int
