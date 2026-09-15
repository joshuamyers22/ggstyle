"""Production behavior for the public tidy-data ribbon helper."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.testing.decorators import check_figures_equal

import ggstyle as gs
from ggstyle._semantic_registry import semantic_registry


@pytest.fixture
def ax():
    figure, axes = plt.subplots()
    try:
        yield axes
    finally:
        plt.close(figure)


def test_ribbon_draws_explicit_bounds_as_a_native_collection(ax) -> None:
    frame = pd.DataFrame({"x": [1, 2, 3], "low": [0, 1, 2], "high": [2, 3, 4]})
    original = frame.copy(deep=True)

    result = gs.ribbon(
        frame, x="x", lower="low", upper="high", label="Observed interval", ax=ax
    )

    assert result.axes is ax
    assert result.artists == tuple(ax.collections)
    assert len(result.artists) == 1
    assert isinstance(result.artists[0], PolyCollection)
    assert result.artists[0].get_alpha() == 0.2
    assert result.artists[0].get_label() == "Observed interval"
    assert result.layer_id == "ribbon-1"
    assert result.scales == {}
    pd.testing.assert_frame_equal(frame, original)


def test_discrete_color_and_group_create_separate_ribbons(ax) -> None:
    result = gs.ribbon(
        {
            "x": [1, 2, 1, 2],
            "low": [0, 1, 2, 3],
            "high": [2, 3, 4, 5],
            "kind": ["A", "A", "B", "B"],
        },
        x="x",
        lower="low",
        upper="high",
        color="kind",
        ax=ax,
    )
    assert len(result.artists) == 2
    assert result.scales["color"].as_dict()["levels"] == ["A", "B"]
    assert all(len(artist.get_facecolors()) == 1 for artist in result.artists)


def test_continuous_color_must_be_constant_within_each_ribbon(ax) -> None:
    valid = gs.ribbon(
        {
            "x": [1, 2, 1, 2],
            "low": [0, 1, 2, 3],
            "high": [2, 3, 4, 5],
            "g": ["A", "A", "B", "B"],
            "score": [0.0, 0.0, 10.0, 10.0],
        },
        x="x",
        lower="low",
        upper="high",
        group="g",
        color="score",
        ax=ax,
    )
    assert len(valid.artists) == 2
    assert valid.scales["color"].as_dict()["domain"] == [0.0, 10.0]

    figure, other = plt.subplots()
    try:
        with pytest.raises(ValueError, match="constant within each resolved ribbon"):
            gs.ribbon(
                {"x": [1, 2], "low": [0, 1], "high": [2, 3], "score": [0, 1]},
                x="x",
                lower="low",
                upper="high",
                color="score",
                ax=other,
            )
        assert list(other.collections) == []
        assert semantic_registry(other).revision == 0
    finally:
        plt.close(figure)


def test_missing_break_is_default_and_drop_connects_explicitly(ax) -> None:
    frame = {
        "x": [1, 2, 3, 4, 5],
        "low": [0, 1, None, 3, 4],
        "high": [2, 3, None, 5, 6],
    }
    broken = gs.ribbon(
        frame,
        x="x",
        lower="low",
        upper="high",
        label="Range",
        ax=ax,
    )
    assert len(broken.artists) == 2
    assert [artist.get_label() for artist in broken.artists] == ["Range", "_nolegend_"]
    assert broken.diagnostics == ("dropped 1 row(s) with missing ribbon coordinates",)

    dropped = gs.ribbon(
        frame, x="x", lower="low", upper="high", missing="drop", ax=ax
    )
    assert len(dropped.artists) == 1


def test_missing_raise_fails_before_drawing(ax) -> None:
    with pytest.raises(ValueError, match="missing value at row 1"):
        gs.ribbon(
            {"x": [1, 2], "low": [0, None], "high": [2, 3]},
            x="x",
            lower="low",
            upper="high",
            missing="raise",
            ax=ax,
        )
    assert list(ax.collections) == []


def test_crossed_bounds_are_allowed_unless_validation_is_requested(ax) -> None:
    result = gs.ribbon(
        {"x": [1, 2], "low": [0, 4], "high": [2, 3]},
        x="x",
        lower="low",
        upper="high",
        ax=ax,
    )
    assert len(result.artists) == 1

    with pytest.raises(ValueError, match="lower bound exceeds upper bound at row 1"):
        gs.ribbon(
            {"x": [1, 2], "low": [0, 4], "high": [2, 3]},
            x="x",
            lower="low",
            upper="high",
            validate_order=True,
            ax=ax,
        )


@pytest.mark.parametrize(
    ("value", "error", "message"),
    [
        ("bad", TypeError, "must contain real numbers"),
        (True, TypeError, "must contain real numbers"),
        (float("inf"), ValueError, "must contain finite values"),
    ],
)
def test_bounds_must_be_finite_real_values(ax, value, error, message) -> None:
    with pytest.raises(error, match=message):
        gs.ribbon(
            {"x": [1], "low": [value], "high": [2]},
            x="x",
            lower="low",
            upper="high",
            ax=ax,
        )


def test_sort_x_is_stable_for_duplicate_values(ax) -> None:
    result = gs.ribbon(
        {"x": [2, 1, 1], "low": [20, 10, 11], "high": [22, 12, 13]},
        x="x",
        lower="low",
        upper="high",
        sort="x",
        ax=ax,
    )
    vertices = result.artists[0].get_paths()[0].vertices
    # The lower edge begins at x=1 and retains both duplicate-x observations.
    assert vertices[1:4, 0].tolist() == [1.0, 1.0, 2.0]
    assert vertices[1:4, 1].tolist() == [10.0, 11.0, 20.0]


def test_label_is_never_synthesized_and_rejects_multiple_groups(ax) -> None:
    result = gs.ribbon(
        {"x": [1, 2], "low": [0, 1], "high": [2, 3], "kind": ["A", "A"]},
        x="x",
        lower="low",
        upper="high",
        color="kind",
        ax=ax,
    )
    assert result.artists[0].get_label().startswith("_child")

    with pytest.raises(ValueError, match="exactly one resolved ribbon group"):
        gs.ribbon(
            {
                "x": [1, 2],
                "low": [0, 1],
                "high": [2, 3],
                "kind": ["A", "B"],
            },
            x="x",
            lower="low",
            upper="high",
            color="kind",
            label="Range",
            ax=ax,
        )


def test_shared_scale_retrains_existing_line_point_and_ribbon_artists(ax) -> None:
    line = gs.line(
        {"x": [1], "y": [1], "score": [5.0]},
        x="x",
        y="y",
        color="score",
        ax=ax,
    )
    points = gs.points(
        {"x": [2], "y": [2], "score": [10.0]},
        x="x",
        y="y",
        color="score",
        ax=ax,
    )
    line_color = line.artists[0].get_color()
    point_color = points.artists[0].get_facecolors().copy()
    ribbon = gs.ribbon(
        {
            "x": [1, 2, 1, 2],
            "low": [0, 0, 2, 2],
            "high": [1, 1, 3, 3],
            "g": ["A", "A", "B", "B"],
            "score": [0.0, 0.0, 20.0, 20.0],
        },
        x="x",
        lower="low",
        upper="high",
        group="g",
        color="score",
        ax=ax,
    )
    assert line.artists[0].get_color() != line_color
    assert not np.array_equal(points.artists[0].get_facecolors(), point_color)
    assert ribbon.scales["color"].as_dict()["domain"] == [0.0, 20.0]


def test_partial_render_failure_rolls_back_collections_and_registry(
    ax, monkeypatch
) -> None:
    original = ax.fill_between
    calls = 0
    limits = ax.dataLim.get_points().copy()

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("fill failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(ax, "fill_between", fail_second)
    with pytest.raises(RuntimeError, match="fill failed"):
        gs.ribbon(
            {
                "x": [1, 2, 1, 2],
                "low": [0, 1, 2, 3],
                "high": [2, 3, 4, 5],
                "kind": ["A", "A", "B", "B"],
            },
            x="x",
            lower="low",
            upper="high",
            color="kind",
            ax=ax,
        )
    assert list(ax.collections) == []
    np.testing.assert_array_equal(ax.dataLim.get_points(), limits)
    assert semantic_registry(ax).revision == 0


def test_failed_ribbon_restores_cross_geometry_scale_updates(ax, monkeypatch) -> None:
    points = gs.points(
        {"x": [1, 2], "y": [2, 3], "score": [0.0, 10.0]},
        x="x",
        y="y",
        color="score",
        ax=ax,
    )
    colors = points.artists[0].get_facecolors().copy()
    revision = semantic_registry(ax).revision

    def fail(*args, **kwargs):
        raise RuntimeError("fill failed")

    monkeypatch.setattr(ax, "fill_between", fail)
    with pytest.raises(RuntimeError, match="fill failed"):
        gs.ribbon(
            {
                "x": [1, 2, 1, 2],
                "low": [0, 0, 2, 2],
                "high": [1, 1, 3, 3],
                "g": ["A", "A", "B", "B"],
                "score": [-10.0, -10.0, 20.0, 20.0],
            },
            x="x",
            lower="low",
            upper="high",
            group="g",
            color="score",
            ax=ax,
        )
    np.testing.assert_array_equal(points.artists[0].get_facecolors(), colors)
    assert semantic_registry(ax).revision == revision
    assert tuple(ax.collections) == points.artists


def test_existing_collapsed_date_handle_refreshes(ax) -> None:
    handle = gs.dates(ax, data=pd.to_datetime(["2024-01-01", "2024-01-03"])).collapse()
    revision = handle.revision
    result = gs.ribbon(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-04"]),
            "low": [1, 2],
            "high": [2, 3],
        },
        x="date",
        lower="low",
        upper="high",
        ax=ax,
    )
    assert len(result.artists) == 1
    assert handle.mode == "collapse"
    assert handle.revision == revision + 1
    assert handle.observations.equals(pd.date_range("2024-01-01", periods=4))


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"sort": "value"}, ValueError, "sort must be"),
        ({"missing": "ignore"}, ValueError, "missing must be"),
        ({"group_missing": "ignore"}, ValueError, "group_missing must be"),
        ({"alpha": 2}, ValueError, "between 0 and 1"),
        ({"validate_order": 1}, TypeError, "validate_order must be bool"),
        ({"label": 1}, TypeError, "label must be a string"),
        ({"style": []}, TypeError, "style must be a mapping"),
        ({"style": {"alpha": 0.5}}, ValueError, "both alpha= and style"),
        ({"style": {"label": "Range"}}, ValueError, "both label= and style"),
        ({"style": {"cmap": "viridis"}}, ValueError, "use color_scale"),
        ({"style": {"not_a_property": 1}}, AttributeError, "invalid fixed ribbon"),
    ],
)
def test_public_arguments_are_validated(ax, arguments, error, message) -> None:
    values = {
        "data": {"x": [1], "low": [0], "high": [2]},
        "x": "x",
        "lower": "low",
        "upper": "high",
        "ax": ax,
    }
    values.update(arguments)
    with pytest.raises(error, match=message):
        gs.ribbon(**values)
    assert list(ax.collections) == []


@pytest.mark.parametrize("fixed", [{"facecolor": "red"}, {"c": "red"}])
def test_mapped_color_cannot_also_be_fixed(ax, fixed) -> None:
    with pytest.raises(ValueError, match="both mapped and fixed"):
        gs.ribbon(
            {"x": [1], "low": [0], "high": [2], "kind": ["A"]},
            x="x",
            lower="low",
            upper="high",
            color="kind",
            style=fixed,
            ax=ax,
        )


def test_result_is_immutable_and_publicly_exported(ax) -> None:
    result = gs.ribbon(
        {"x": [1], "low": [0], "high": [2]},
        x="x",
        lower="low",
        upper="high",
        ax=ax,
    )
    with pytest.raises(TypeError):
        result.scales["color"] = object()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        result.layer_id = "changed"  # type: ignore[misc]
    assert {"ribbon", "RibbonResult"} <= set(gs.__all__)


@check_figures_equal()
def test_ribbon_matches_equivalent_native_fill_between(fig_test, fig_ref) -> None:
    test_ax = fig_test.subplots()
    ref_ax = fig_ref.subplots()
    frame = {"x": [3, 1, 2], "low": [2, 0, 1], "high": [4, 2, 3]}

    gs.ribbon(
        frame,
        x="x",
        lower="low",
        upper="high",
        sort="x",
        alpha=0.3,
        style={"facecolor": "#123456", "edgecolor": "#654321"},
        ax=test_ax,
    )
    ref_ax.fill_between(
        [1, 2, 3],
        [0, 1, 2],
        [2, 3, 4],
        alpha=0.3,
        facecolor="#123456",
        edgecolor="#654321",
    )
