"""Caption wording tests that require no Matplotlib axes."""

import pandas as pd

from ggstyle._axis_summary import AxisSummary
from ggstyle._captions import format_caption


def _summary(**changes) -> AxisSummary:
    values = {
        "mode": "show",
        "observations": 0,
        "start": None,
        "end": None,
        "inferred_frequency": None,
        "major_cadence": "month[start]",
        "minor_cadence": None,
        "timezone": None,
        "missing_values": 0,
    }
    values.update(changes)
    return AxisSummary(**values)


def test_calendar_caption_omits_unavailable_details() -> None:
    assert format_caption(_summary()) == "0 observations · calendar gaps shown"


def test_collapsed_caption_includes_range_missing_count_and_timezone() -> None:
    summary = _summary(
        mode="collapse",
        observations=1_234,
        start=pd.Timestamp("2024-01-02"),
        end=pd.Timestamp("2024-12-31"),
        timezone="America/New_York",
        missing_values=3,
    )

    assert format_caption(summary) == (
        "1,234 observations · Jan 2, 2024 - Dec 31, 2024 · unobserved dates collapsed · "
        "3 missing excluded · labels: America/New_York"
    )
