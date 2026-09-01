import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import pytest

from ggstyle import _cadence
from ggstyle._tick_positions import positions_for_cadence


def test_show_mode_returns_calendar_boundaries() -> None:
    labels, positions = positions_for_cadence(
        _cadence.Cadence("month"),
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-03-31"),
        mode="show",
        knots=np.empty(0),
    )
    assert list(labels) == [
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-02-01"),
        pd.Timestamp("2024-03-01"),
    ]
    assert np.allclose(positions, mdates.date2num(labels))


def test_collapsed_mode_uses_first_observation_in_each_period() -> None:
    observations = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-02-05"])
    labels, positions = positions_for_cadence(
        _cadence.Cadence("month"),
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-02-29"),
        mode="collapse",
        knots=np.asarray(mdates.date2num(observations), dtype=float),
    )
    assert list(labels) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")]
    assert np.array_equal(positions, [0.0, 2.0])


def test_collapsed_mode_requires_observations() -> None:
    with pytest.raises(ValueError, match="requires observed dates"):
        positions_for_cadence(
            _cadence.Cadence("month"),
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-02-01"),
            mode="collapse",
            knots=np.empty(0),
        )
