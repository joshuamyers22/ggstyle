"""Timezone display policy independent of matplotlib rendering."""

from zoneinfo import ZoneInfo

import pandas as pd


def validate_display_timezone(zone: str | None) -> None:
    """Validate an IANA zone with one stable exception type across pandas versions."""
    if zone is not None:
        ZoneInfo(zone)


def apply_display_timezone(index: pd.DatetimeIndex, zone: str | None) -> pd.DatetimeIndex:
    """Convert timestamps for display, treating naive values as UTC instants."""
    if zone is None:
        return index
    aware = index.tz_localize("UTC") if index.tz is None else index
    return aware.tz_convert(zone)
