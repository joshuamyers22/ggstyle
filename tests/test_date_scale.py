"""Integration tests for the production collapsed-date Matplotlib scale."""

from __future__ import annotations

import subprocess
import sys

import matplotlib
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs
from ggstyle._date_scale import SCALE_NAME, CollapsedDateTransform


def test_import_does_not_register_the_collapsed_scale() -> None:
    code = f"""
import matplotlib.scale as scale
assert {SCALE_NAME!r} not in scale.get_scale_names()
import ggstyle
assert {SCALE_NAME!r} not in scale.get_scale_names()
"""
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.fixture
def irregular_dates() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(
        ["2024-01-05", "2024-01-08", "2024-01-09", "2024-01-19"]
    )


@pytest.mark.parametrize("kind", ["scatter", "fill_between"])
def test_scale_handles_collections_without_mutating_geometry(
    irregular_dates: pd.DatetimeIndex, kind: str
) -> None:
    nums = np.asarray(mdates.date2num(irregular_dates), dtype=float)
    values = np.arange(nums.size, dtype=float)
    fig, ax = plt.subplots()
    try:
        line = ax.plot(irregular_dates, values)[0]
        handle = gs.dates(ax).collapse()
        if kind == "scatter":
            collection = ax.scatter(irregular_dates, values + 1)
            calendar_x = np.asarray(collection.get_offsets()[:, 0], dtype=float).copy()
        else:
            collection = ax.fill_between(irregular_dates, values + 1, values + 2)
            calendar_x = np.concatenate(
                [path.vertices[:, 0] for path in collection.get_paths()]
            ).copy()

        fig.canvas.draw()
        expected_pixels = ax.transData.transform(
            np.column_stack([nums, np.zeros(nums.size)])
        )[:, 0]
        if kind == "scatter":
            actual_pixels = collection.get_offset_transform().transform(
                collection.get_offsets()
            )[:, 0]
            assert np.allclose(actual_pixels, expected_pixels)
            assert np.array_equal(
                np.asarray(collection.get_offsets()[:, 0], dtype=float), calendar_x
            )
        else:
            actual_pixels = np.concatenate(
                [
                    collection.get_transform().transform(path.vertices)[:, 0]
                    for path in collection.get_paths()
                ]
            )
            assert all(
                np.any(np.isclose(actual_pixels, value)) for value in expected_pixels
            )
            assert np.array_equal(
                np.concatenate(
                    [path.vertices[:, 0] for path in collection.get_paths()]
                ),
                calendar_x,
            )

        assert handle.mode == "collapse"
        assert np.array_equal(
            np.asarray(line.get_xdata(orig=False), dtype=float), nums
        )
        handle.expand().collapse()
        assert np.array_equal(
            np.asarray(line.get_xdata(orig=False), dtype=float), nums
        )
    finally:
        plt.close(fig)


def test_collection_only_scatter_discovers_observations(
    irregular_dates: pd.DatetimeIndex,
) -> None:
    fig, ax = plt.subplots()
    try:
        ax.scatter(irregular_dates, np.arange(len(irregular_dates), dtype=float))
        handle = gs.dates(ax).collapse()
        assert handle.mode == "collapse"
        assert list(handle.observations) == list(irregular_dates)
    finally:
        plt.close(fig)


def test_registered_scale_preserves_date_limits_and_autoscaling(
    irregular_dates: pd.DatetimeIndex,
) -> None:
    nums = np.asarray(mdates.date2num(irregular_dates), dtype=float)
    fig, ax = plt.subplots()
    try:
        ax.plot(irregular_dates, np.arange(nums.size, dtype=float))
        handle = gs.dates(ax).collapse()
        lower, upper = ax.get_xlim()
        assert lower < nums[0]
        assert upper > nums[-1]

        ax.set_xlim(irregular_dates[1], irregular_dates[-2])
        assert np.allclose(ax.get_xlim(), nums[[1, -2]])

        handle.zoom(irregular_dates[1], irregular_dates[-2])
        assert np.allclose(ax.get_xlim(), nums[[1, -2]])
        assert np.allclose(
            ax.xaxis.get_transform().transform(np.asarray(ax.get_xlim())), [1.0, 2.0]
        )
    finally:
        plt.close(fig)


def test_mode_switches_preserve_inverted_date_limits(
    irregular_dates: pd.DatetimeIndex,
) -> None:
    fig, ax = plt.subplots()
    try:
        ax.plot(irregular_dates, np.arange(len(irregular_dates), dtype=float))
        handle = gs.dates(ax)
        ax.set_xlim(irregular_dates[-1], irregular_dates[0])
        expected = ax.get_xlim()

        handle.collapse().collapse()
        assert ax.xaxis_inverted()
        assert np.allclose(ax.get_xlim(), expected)

        handle.expand().expand()
        assert ax.xaxis_inverted()
        assert np.allclose(ax.get_xlim(), expected)
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

        gs.dates(axes[0]).collapse()

        assert all(ax.get_xscale() == SCALE_NAME for ax in axes)
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
        ([40.0, 10.0, 20.0, 20.0], [-5.0, 10.0, 15.0, 40.0, 55.0]),
    ],
)
def test_registered_transform_round_trips_inside_and_outside_domain(
    observations: list[float], probes: list[float]
) -> None:
    transform = CollapsedDateTransform(np.asarray(observations))
    values = np.asarray(probes)
    assert np.allclose(transform.inverted().transform(transform.transform(values)), values)
    assert not transform.observations.flags.writeable
