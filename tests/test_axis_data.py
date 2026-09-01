import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from ggstyle._axis_data import AxisData, collect, validate


def test_collect_merges_explicit_and_plotted_dates() -> None:
    _, ax = plt.subplots()
    plotted = pd.date_range("2024-01-01", periods=2)
    ax.plot(plotted, [1, 2])

    result = collect(
        ax,
        [pd.Timestamp("2024-01-03"), None],
        existing=AxisData(np.empty(0), 0, False),
        missing="drop",
    )

    assert result.numbers.size == 3
    assert result.missing_values == 1
    assert result.trusted is True
    plt.close(ax.figure)


def test_validate_rejects_untrusted_numeric_axis() -> None:
    _, ax = plt.subplots()
    ax.plot([1, 2], [3, 4])
    data = collect(
        ax,
        None,
        existing=AxisData(np.empty(0), 0, False),
        missing="raise",
    )
    with pytest.raises(TypeError, match="does not look like dates"):
        validate(ax, data)
    plt.close(ax.figure)
