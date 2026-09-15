"""Tests for the explicit Matplotlib formatting boundary."""

import matplotlib
import pytest
from matplotlib.ticker import FuncFormatter

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs


def test_adapter_returns_func_formatter() -> None:
    formatter = gs.as_formatter(gs.label_percent(decimals=1))
    assert isinstance(formatter, FuncFormatter)
    assert formatter(0.125) == "12.5%"


def test_adapter_accepts_a_compatible_custom_callable() -> None:
    formatter = gs.as_formatter(lambda value: f"value={value:.0f}")
    assert formatter(12.0, 3) == "value=12"


def test_adapter_rejects_a_noncallable() -> None:
    with pytest.raises(TypeError, match="labeller must be callable"):
        gs.as_formatter(12)  # type: ignore[arg-type]


def test_adapter_installs_on_native_matplotlib_axis() -> None:
    figure, ax = plt.subplots()
    try:
        formatter = gs.as_formatter(gs.label_currency("$", decimals=0))
        ax.yaxis.set_major_formatter(formatter)
        ax.set_ylim(0, 2000)
        figure.canvas.draw()
        assert ax.yaxis.get_major_formatter() is formatter
        assert "$" in {tick.get_text()[:1] for tick in ax.get_yticklabels()}
    finally:
        plt.close(figure)


def test_adapter_creation_does_not_mutate_rcparams() -> None:
    before = matplotlib.rcParams.copy()
    gs.as_formatter(gs.label_si(unit="B"))
    assert matplotlib.rcParams == before
