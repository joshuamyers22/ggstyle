"""Static assertions for the public fluent API shipped with ``py.typed``."""

import pandas as pd
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter
from typing_extensions import assert_type

import ggstyle as gs


def check_date_axis_types(ax: Axes, events: pd.DataFrame) -> None:
    """Assert that public operations retain useful concrete result types."""
    handle = assert_type(gs.dates(ax), gs.DateAxis)
    assert_type(handle.ticks("monthly"), gs.DateAxis)
    assert_type(handle.fmt("month-year"), gs.DateAxis)
    assert_type(handle.rotate(30), gs.DateAxis)
    assert_type(handle.tz("UTC"), gs.DateAxis)
    assert_type(handle.zoom("2024", "2025"), gs.DateAxis)
    assert_type(handle.pad(left="1D"), gs.DateAxis)
    assert_type(handle.collapse(), gs.DateAxis)
    assert_type(handle.expand(), gs.DateAxis)
    assert_type(handle.vline("2024-01-01"), gs.DateAxis)
    assert_type(handle.span("2024-01-01", "2024-01-02"), gs.DateAxis)
    assert_type(handle.spans(events), gs.DateAxis)
    assert_type(handle.grid("monthly"), gs.DateAxis)
    assert_type(handle.clear_annotations(), gs.DateAxis)
    assert_type(handle.refresh(), gs.DateAxis)
    assert_type(handle.summary(), gs.AxisSummary)
    assert_type(handle.observations, pd.DatetimeIndex)
    assert_type(gs.sync_dates([ax]), list[gs.DateAxis])


def check_theme_types() -> None:
    """Assert concrete return types for public theme discovery helpers."""
    assert_type(gs.available_themes(), list[str])


def check_numeric_labeller_types() -> None:
    """Assert that numeric factories and their adapter retain useful types."""
    percent = assert_type(gs.label_percent(decimals=1), gs.NumericLabeller)
    assert_type(percent(0.125), str)
    assert_type(gs.label_currency("$"), gs.NumericLabeller)
    assert_type(gs.label_number(), gs.NumericLabeller)
    assert_type(gs.label_si(unit="B"), gs.NumericLabeller)
    assert_type(gs.as_formatter(percent), FuncFormatter)


def check_palette_types() -> None:
    """Assert immutable palette construction and lookup result types."""
    selected = assert_type(gs.palette("sequential"), gs.Palette)
    assert_type(selected.colors, tuple[str, ...])
    assert_type(selected.sample(5), tuple[str, ...])
    assert_type(selected.at(0.5), str)
    assert_type(gs.available_palettes(), list[str])
