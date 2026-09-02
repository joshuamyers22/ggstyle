"""Pure date-axis range calculations."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._parse import to_offset, to_timestamp


def resolve_zoom_range(
    current: tuple[pd.Timestamp, pd.Timestamp],
    observations: pd.DatetimeIndex,
    *,
    start: Any = None,
    end: Any = None,
    last: Any = None,
    ytd: bool = False,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Resolve zoom options to concrete date bounds."""
    if ytd:
        anchor = observations[-1]
        return pd.Timestamp(year=anchor.year, month=1, day=1), anchor
    if last is not None:
        anchor = observations[-1]
        return anchor - to_offset(last), anchor

    current_start, current_end = current
    start_ts = to_timestamp(start, side="start") if start is not None else current_start
    end_ts = to_timestamp(end, side="end") if end is not None else current_end
    return start_ts, end_ts


def pad_range(
    current: tuple[pd.Timestamp, pd.Timestamp],
    *,
    left: Any = None,
    right: Any = None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Extend concrete date bounds by optional offsets."""
    start, end = current
    if left is not None:
        start -= to_offset(left)
    if right is not None:
        end += to_offset(right)
    return start, end
