"""Production behavior for the public tidy-data point helper."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PathCollection

import ggstyle as gs
from ggstyle._semantic_registry import semantic_registry


@pytest.fixture
def ax():
    figure, axes = plt.subplots()
    try:
        yield axes
    finally:
        plt.close(figure)


def test_discrete_color_draws_native_collections_without_mutating_input(ax) -> None:
    frame = pd.DataFrame(
        {"x": [1, 2, 3], "y": [3, 1, 2], "kind": ["A", "B", "A"]}
    )
    original = frame.copy(deep=True)

    result = gs.points(frame, x="x", y="y", color="kind", ax=ax)

    assert result.axes is ax
    assert result.artists == tuple(ax.collections)
    assert all(isinstance(artist, PathCollection) for artist in result.artists)
    assert len(result.artists) == 2
    assert [len(artist.get_offsets()) for artist in result.artists] == [2, 1]
    assert result.scales["color"].as_dict()["levels"] == ["A", "B"]
    assert result.layer_id == "points-1"
    pd.testing.assert_frame_equal(frame, original)


def test_continuous_color_maps_each_point_in_one_collection(ax) -> None:
    result = gs.points(
        {"x": [1, 2, 3], "y": [4, 5, 6], "score": [0.0, 5.0, 10.0]},
        x="x",
        y="y",
        color="score",
        ax=ax,
    )

    assert len(result.artists) == 1
    assert len(result.artists[0].get_facecolors()) == 3
    assert result.scales["color"].as_dict()["domain"] == [0.0, 10.0]


def test_explicit_group_partitions_without_creating_a_scale(ax) -> None:
    result = gs.points(
        {"x": [1, 2, 3], "y": [4, 5, 6], "g": ["A", "B", "A"]},
        x="x",
        y="y",
        group="g",
        style={"color": "#123456", "size": 25, "marker": "s"},
        ax=ax,
    )
    assert len(result.artists) == 2
    assert result.scales == {}
    assert [len(artist.get_offsets()) for artist in result.artists] == [2, 1]
    assert all(artist.get_sizes().tolist() == [25.0] for artist in result.artists)


def test_scatter_color_alias_remains_available_for_fixed_style(ax) -> None:
    result = gs.points(
        {"x": [1], "y": [2]}, x="x", y="y", style={"c": "#123456"}, ax=ax
    )
    np.testing.assert_allclose(
        result.artists[0].get_facecolors()[0],
        matplotlib.colors.to_rgba("#123456"),
    )


def test_coordinate_and_group_missing_policies_are_explicit(ax) -> None:
    dropped = gs.points(
        {"x": [1, None, 3], "y": [4, 5, 6], "g": ["A", "A", None]},
        x="x",
        y="y",
        group="g",
        ax=ax,
    )
    assert len(dropped.artists[0].get_offsets()) == 1
    assert dropped.diagnostics == (
        "dropped 1 row(s) with missing point coordinates",
        "dropped 1 row(s) with missing group 'g'",
    )

    with pytest.raises(ValueError, match="missing value at row 1"):
        gs.points(
            {"x": [1, None], "y": [2, 3]},
            x="x",
            y="y",
            missing="raise",
            ax=ax,
        )
    with pytest.raises(ValueError, match="contains missing values"):
        gs.points(
            {"x": [1], "y": [2], "g": [None]},
            x="x",
            y="y",
            group="g",
            group_missing="raise",
            ax=ax,
        )


def test_missing_group_can_be_retained_as_its_own_collection(ax) -> None:
    result = gs.points(
        {"x": [1, 2], "y": [3, 4], "g": ["A", None]},
        x="x",
        y="y",
        group="g",
        group_missing="keep",
        ax=ax,
    )
    assert len(result.artists) == 2


def test_continuous_scale_is_shared_bidirectionally_with_lines(ax) -> None:
    line = gs.line(
        {
            "x": [1, 2, 1, 2],
            "y": [1, 2, 2, 3],
            "g": ["A", "A", "B", "B"],
            "score": [0.0, 0.0, 10.0, 10.0],
        },
        x="x",
        y="y",
        group="g",
        color="score",
        ax=ax,
    )
    old = tuple(artist.get_color() for artist in line.artists)
    point = gs.points(
        {"x": [3, 4], "y": [3, 4], "score": [-10.0, 20.0]},
        x="x",
        y="y",
        color="score",
        ax=ax,
    )
    assert tuple(artist.get_color() for artist in line.artists) != old
    assert point.scales["color"].as_dict()["domain"] == [-10.0, 20.0]

    figure, other = plt.subplots()
    try:
        initial = gs.points(
            {"x": [1, 2], "y": [1, 2], "score": [0.0, 10.0]},
            x="x",
            y="y",
            color="score",
            ax=other,
        )
        colors = initial.artists[0].get_facecolors().copy()
        gs.line(
            {"x": [3, 4], "y": [3, 4], "score": [20.0, 20.0]},
            x="x",
            y="y",
            color="score",
            ax=other,
        )
        assert not np.array_equal(initial.artists[0].get_facecolors(), colors)
    finally:
        plt.close(figure)


def test_failed_later_point_layer_restores_existing_artist_and_registry(
    ax, monkeypatch
) -> None:
    initial = gs.line(
        {"x": [1], "y": [2], "score": [0.0]},
        x="x",
        y="y",
        color="score",
        ax=ax,
    )
    color = initial.artists[0].get_color()
    revision = semantic_registry(ax).revision

    def fail(*args, **kwargs):
        raise RuntimeError("scatter failed")

    monkeypatch.setattr(ax, "scatter", fail)
    with pytest.raises(RuntimeError, match="scatter failed"):
        gs.points(
            {"x": [2], "y": [3], "score": [10.0]},
            x="x",
            y="y",
            color="score",
            ax=ax,
        )
    assert initial.artists[0].get_color() == color
    assert semantic_registry(ax).revision == revision
    assert list(ax.collections) == []


def test_partial_scatter_failure_rolls_back_collections_and_limits(ax, monkeypatch) -> None:
    original = ax.scatter
    calls = 0
    limits = ax.dataLim.get_points().copy()

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("scatter failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(ax, "scatter", fail_second)
    with pytest.raises(RuntimeError, match="scatter failed"):
        gs.points(
            {"x": [1, 2], "y": [3, 4], "kind": ["A", "B"]},
            x="x",
            y="y",
            color="kind",
            ax=ax,
        )
    assert list(ax.collections) == []
    np.testing.assert_array_equal(ax.dataLim.get_points(), limits)
    assert semantic_registry(ax).revision == 0


def test_existing_collapsed_date_handle_refreshes(ax) -> None:
    handle = gs.dates(ax, data=pd.to_datetime(["2024-01-01", "2024-01-03"])).collapse()
    revision = handle.revision
    gs.points(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-04"]),
            "value": [2, 4],
        },
        x="date",
        y="value",
        ax=ax,
    )
    assert handle.mode == "collapse"
    assert handle.revision == revision + 1
    assert handle.observations.equals(pd.date_range("2024-01-01", periods=4))


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"missing": "break"}, ValueError, "missing must be"),
        ({"group_missing": "ignore"}, ValueError, "group_missing must be"),
        ({"style": []}, TypeError, "style must be a mapping"),
        ({"style": {"size": 0}}, ValueError, "positive"),
        ({"style": {"cmap": "viridis"}}, ValueError, "use color_scale"),
        ({"style": {"not_a_property": 1}}, AttributeError, "invalid fixed point"),
    ],
)
def test_public_arguments_are_validated(ax, arguments, error, message) -> None:
    values = {"data": {"x": [1], "y": [2]}, "x": "x", "y": "y", "ax": ax}
    values.update(arguments)
    with pytest.raises(error, match=message):
        gs.points(**values)
    assert list(ax.collections) == []


def test_mapped_color_cannot_also_be_fixed(ax) -> None:
    with pytest.raises(ValueError, match="both mapped and fixed"):
        gs.points(
            {"x": [1], "y": [2], "kind": ["A"]},
            x="x",
            y="y",
            color="kind",
            style={"facecolor": "red"},
            ax=ax,
        )


def test_result_is_immutable_and_publicly_exported(ax) -> None:
    result = gs.points({"x": [1], "y": [2]}, x="x", y="y", ax=ax)
    with pytest.raises(TypeError):
        result.scales["color"] = object()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        result.layer_id = "changed"  # type: ignore[misc]
    assert {"points", "PointResult"} <= set(gs.__all__)
