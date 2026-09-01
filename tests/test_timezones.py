"""Tests for timezone display policy."""

import pandas as pd

from ggstyle._timezones import apply_display_timezone


def test_disabled_display_timezone_preserves_index() -> None:
    index = pd.date_range("2024-01-01", periods=2)
    assert apply_display_timezone(index, None) is index


def test_naive_values_are_interpreted_as_utc_instants() -> None:
    index = pd.DatetimeIndex(["2024-01-01 12:00"])
    converted = apply_display_timezone(index, "America/New_York")
    assert converted[0] == pd.Timestamp("2024-01-01 07:00", tz="America/New_York")


def test_aware_values_are_converted_from_their_existing_zone() -> None:
    index = pd.DatetimeIndex(["2024-07-01 13:00"], tz="Europe/London")
    converted = apply_display_timezone(index, "America/New_York")
    assert converted[0] == pd.Timestamp("2024-07-01 08:00", tz="America/New_York")
