"""Timezone display policy independent of matplotlib rendering."""

import pandas as pd


def apply_display_timezone(index: pd.DatetimeIndex, zone: str | None) -> pd.DatetimeIndex:
    """Convert timestamps for display, treating naive values as UTC instants."""
    if zone is None:
        return index
    aware = index.tz_localize("UTC") if index.tz is None else index
    return aware.tz_convert(zone)
