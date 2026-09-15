"""Immutable summary contract and assembly policy for a configured date axis."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from ._date_summary import infer_frequency
from ._inspection import describe


@dataclass(frozen=True)
class AxisSummary:
    """
    Describe the data and configuration behind a date axis.

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

    def as_dict(self) -> dict[str, object]:
        """
        Return a JSON-compatible description of the resolved date-axis state.

        Timestamp values use ISO 8601 text. The returned dictionary retains no
        Matplotlib artists and may be passed directly to :func:`json.dumps`.

        Returns
        -------
        dict of str to object
            Fresh nested values suitable for strict JSON serialization.
        """
        return {
            "mode": self.mode,
            "observations": self.observations,
            "start": self.start.isoformat() if self.start is not None else None,
            "end": self.end.isoformat() if self.end is not None else None,
            "inferred_frequency": self.inferred_frequency,
            "major_cadence": self.major_cadence,
            "minor_cadence": self.minor_cadence,
            "timezone": self.timezone,
            "missing_values": self.missing_values,
        }

    def describe(self) -> str:
        """
        Return the resolved date-axis state as deterministic formatted JSON.

        Returns
        -------
        str
            Strict JSON containing the same values as :meth:`as_dict`.
        """
        return describe(self.as_dict())


def summarize_axis(
    *,
    mode: Literal["show", "collapse"],
    observations: pd.DatetimeIndex,
    major_cadence: str,
    minor_cadence: str | None,
    timezone: str | None,
    missing_values: int,
) -> AxisSummary:
    """
    Build a serializable description from resolved date-axis policy.
    """
    return AxisSummary(
        mode=mode,
        observations=len(observations),
        start=observations[0] if len(observations) else None,
        end=observations[-1] if len(observations) else None,
        inferred_frequency=infer_frequency(observations),
        major_cadence=major_cadence,
        minor_cadence=minor_cadence,
        timezone=timezone,
        missing_values=missing_values,
    )
