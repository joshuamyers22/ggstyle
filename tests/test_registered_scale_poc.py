"""Executable proof of concept for the collapsed-date scale decision.

The classes in this module are intentionally test-local.  They establish that a
registered Matplotlib scale can own collapsed coordinates before the production
implementation replaces v0.2's artist mutation in PR4.
"""

from __future__ import annotations

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.scale as mscale
import matplotlib.ticker as mticker
import matplotlib.transforms as mtransforms
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")


def _knots(values: np.ndarray) -> np.ndarray:
    result = np.unique(np.asarray(values, dtype=float))
    result = result[np.isfinite(result)]
    if result.size == 0:
        raise ValueError("collapsed coordinates require at least one observed date")
    return result


def _step(knots: np.ndarray) -> float:
    if knots.size == 1:
        return 1.0
    positive = np.diff(knots)
    positive = positive[positive > 0]
    return float(np.median(positive)) if positive.size else 1.0


def _forward(values: np.ndarray, knots: np.ndarray) -> np.ndarray:
    shape = values.shape
    flat = np.asarray(values, dtype=float).reshape(-1)
    if knots.size == 1:
        return (flat - knots[0]).reshape(shape)

    indexes = np.arange(knots.size, dtype=float)
    result = np.interp(flat, knots, indexes)
    step = _step(knots)
    below = flat < knots[0]
    above = flat > knots[-1]
    result[below] = (flat[below] - knots[0]) / step
    result[above] = indexes[-1] + (flat[above] - knots[-1]) / step
    return result.reshape(shape)


def _inverse(values: np.ndarray, knots: np.ndarray) -> np.ndarray:
    shape = values.shape
    flat = np.asarray(values, dtype=float).reshape(-1)
    if knots.size == 1:
        return (knots[0] + flat).reshape(shape)

    indexes = np.arange(knots.size, dtype=float)
    result = np.interp(flat, indexes, knots)
    step = _step(knots)
    below = flat < 0
    above = flat > indexes[-1]
    result[below] = knots[0] + flat[below] * step
    result[above] = knots[-1] + (flat[above] - indexes[-1]) * step
    return result.reshape(shape)


class _CollapsedTransform(mtransforms.Transform):
    input_dims = 1
    output_dims = 1
    is_separable = True
    has_inverse = True

    def __init__(self, knots: np.ndarray) -> None:
        super().__init__()
        self._knots = knots

    def transform_non_affine(self, values: np.ndarray) -> np.ndarray:
        return _forward(np.asarray(values, dtype=float), self._knots)

    def inverted(self) -> _ExpandedTransform:
        return _ExpandedTransform(self._knots)


class _ExpandedTransform(mtransforms.Transform):
    input_dims = 1
    output_dims = 1
    is_separable = True
    has_inverse = True

    def __init__(self, knots: np.ndarray) -> None:
        super().__init__()
        self._knots = knots

    def transform_non_affine(self, values: np.ndarray) -> np.ndarray:
        return _inverse(np.asarray(values, dtype=float), self._knots)

    def inverted(self) -> _CollapsedTransform:
        return _CollapsedTransform(self._knots)


class _CollapsedDateScale(mscale.ScaleBase):
    """Minimal registered scale used only to prove Matplotlib integration."""

    name = "ggstyle-collapsed-date-poc"

    def __init__(self, *args, observations: np.ndarray) -> None:
        # Matplotlib 3.7 passes the Axis positionally; 3.11+ accepts scale
        # constructors without an explicit ``axis`` parameter.
        axis = args[0] if args else None
        super().__init__(axis)
        self._knots = _knots(observations)

    def get_transform(self) -> _CollapsedTransform:
        return _CollapsedTransform(self._knots)

    def set_default_locators_and_formatters(self, axis) -> None:
        # Production DateAxis installs its own date-aware tick plan after the scale.
        axis.set_major_locator(mticker.NullLocator())
        axis.set_major_formatter(mticker.NullFormatter())
        axis.set_minor_locator(mticker.NullLocator())
        axis.set_minor_formatter(mticker.NullFormatter())


mscale.register_scale(_CollapsedDateScale)


@pytest.fixture
def irregular_dates() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(
        ["2024-01-05", "2024-01-08", "2024-01-09", "2024-01-19"]
    )


def test_registered_scale_handles_lines_collections_and_axvline_uniformly(
    irregular_dates: pd.DatetimeIndex,
) -> None:
    nums = np.asarray(mdates.date2num(irregular_dates), dtype=float)
    values = np.arange(nums.size, dtype=float)
    fig, ax = plt.subplots()
    try:
        line = ax.plot(irregular_dates, values)[0]
        ax.set_xscale(_CollapsedDateScale.name, observations=nums)

        # These artists are deliberately added after the collapsed scale is active.
        points = ax.scatter(irregular_dates, values + 1)
        band = ax.fill_between(irregular_dates, values + 2, values + 3)
        marker = ax.axvline(irregular_dates[1])

        line_calendar = np.asarray(line.get_xdata(orig=False), dtype=float).copy()
        point_calendar = np.asarray(points.get_offsets()[:, 0], dtype=float).copy()
        band_calendar = np.concatenate(
            [path.vertices[:, 0] for path in band.get_paths()]
        ).copy()

        fig.canvas.draw()

        assert np.allclose(ax.xaxis.get_transform().transform(nums), np.arange(nums.size))
        expected_pixels = ax.transData.transform(
            np.column_stack([nums, np.zeros(nums.size)])
        )[:, 0]

        line_pixels = line.get_transform().transform(line.get_path().vertices)[:, 0]
        point_pixels = points.get_offset_transform().transform(points.get_offsets())[:, 0]
        band_pixels = np.concatenate(
            [
                band.get_transform().transform(path.vertices)[:, 0]
                for path in band.get_paths()
            ]
        )
        marker_pixels = marker.get_transform().transform(marker.get_path().vertices)[:, 0]

        assert np.allclose(line_pixels, expected_pixels)
        assert np.allclose(point_pixels, expected_pixels)
        for expected in expected_pixels:
            assert np.any(np.isclose(band_pixels, expected))
        assert np.allclose(marker_pixels, expected_pixels[1])

        # Installing the scale changes display coordinates, never artist geometry.
        assert np.array_equal(
            np.asarray(line.get_xdata(orig=False), dtype=float), line_calendar
        )
        assert np.array_equal(
            np.asarray(points.get_offsets()[:, 0], dtype=float), point_calendar
        )
        assert np.array_equal(
            np.concatenate([path.vertices[:, 0] for path in band.get_paths()]),
            band_calendar,
        )
    finally:
        plt.close(fig)


def test_registered_scale_preserves_date_limits_and_autoscaling(
    irregular_dates: pd.DatetimeIndex,
) -> None:
    nums = np.asarray(mdates.date2num(irregular_dates), dtype=float)
    fig, ax = plt.subplots()
    try:
        ax.plot(irregular_dates, np.arange(nums.size, dtype=float))
        ax.set_xscale(_CollapsedDateScale.name, observations=nums)
        ax.relim()
        ax.autoscale_view()

        lower, upper = ax.get_xlim()
        assert lower < nums[0]
        assert upper > nums[-1]

        ax.set_xlim(irregular_dates[1], irregular_dates[-2])
        assert np.allclose(ax.get_xlim(), nums[[1, -2]])
        assert np.allclose(
            ax.xaxis.get_transform().transform(np.asarray(ax.get_xlim())), [1.0, 2.0]
        )
    finally:
        plt.close(fig)


def test_registered_scale_propagates_across_shared_x_axes(
    irregular_dates: pd.DatetimeIndex,
) -> None:
    nums = np.asarray(mdates.date2num(irregular_dates), dtype=float)
    fig, axes = plt.subplots(2, 1, sharex=True)
    try:
        for ax in axes:
            ax.plot(irregular_dates, np.arange(nums.size, dtype=float))

        axes[0].set_xscale(_CollapsedDateScale.name, observations=nums)

        assert all(ax.get_xscale() == _CollapsedDateScale.name for ax in axes)
        for ax in axes:
            assert np.allclose(
                ax.xaxis.get_transform().transform(nums), np.arange(nums.size)
            )
    finally:
        plt.close(fig)


@pytest.mark.parametrize(
    ("observations", "probes"),
    [
        ([10.0], [8.0, 10.0, 12.0]),
        ([10.0, 20.0, 40.0], [-5.0, 10.0, 15.0, 40.0, 55.0]),
    ],
)
def test_registered_scale_inverse_round_trips_inside_and_outside_domain(
    observations: list[float], probes: list[float]
) -> None:
    transform = _CollapsedTransform(_knots(np.asarray(observations)))
    values = np.asarray(probes)
    assert np.allclose(transform.inverted().transform(transform.transform(values)), values)
