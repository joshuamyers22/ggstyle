"""Production behavior for the public tidy-data line helper."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import matplotlib
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
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


def _grouped_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-03", "2024-01-01", "2024-01-02"] * 2
            ),
            "value": [3.0, 1.0, 2.0, 6.0, 4.0, 5.0],
            "series": ["A"] * 3 + ["B"] * 3,
            "status": ["actual"] * 3 + ["forecast"] * 3,
        }
    )


def test_discrete_color_draws_native_grouped_lines_without_mutating_input(ax) -> None:
    frame = _grouped_frame()
    original = frame.copy(deep=True)

    result = gs.line(frame, x="date", y="value", color="series", ax=ax)

    assert result.axes is ax
    assert result.artists == tuple(ax.lines)
    assert all(isinstance(artist, Line2D) for artist in result.artists)
    assert len(result.artists) == 2
    assert [artist.get_color() for artist in result.artists] == ["#0072B2", "#D55E00"]
    assert result.scales["color"].kind == "discrete"
    assert result.scales["color"].as_dict()["levels"] == ["A", "B"]
    assert result.layer_id == "line-1"
    assert ax.get_legend() is None
    pd.testing.assert_frame_equal(frame, original)


def test_discrete_linestyle_implies_grouping(ax) -> None:
    frame = _grouped_frame()
    result = gs.line(
        frame,
        x="date",
        y="value",
        linestyle="status",
        style={"color": "#112233"},
        ax=ax,
    )

    assert len(result.artists) == 2
    assert [artist.get_linestyle() for artist in result.artists] == ["-", "--"]
    assert {artist.get_color() for artist in result.artists} == {"#112233"}
    assert result.scales["linestyle"].as_dict()["levels"] == ["actual", "forecast"]


def test_explicit_group_partitions_without_creating_a_scale(ax) -> None:
    frame = _grouped_frame()
    result = gs.line(
        frame,
        x="date",
        y="value",
        group="series",
        style={"color": "#123456", "linewidth": 2.5},
        ax=ax,
    )

    assert len(result.artists) == 2
    assert dict(result.scales) == {}
    assert all(artist.get_color() == "#123456" for artist in result.artists)
    assert all(artist.get_linewidth() == 2.5 for artist in result.artists)


def test_input_order_is_default_and_x_sort_is_stable_for_duplicates(ax) -> None:
    frame = pd.DataFrame(
        {"x": [2, 1, 1, 3], "y": [20, 10, 11, 30], "g": ["A"] * 4}
    )
    first = gs.line(frame, x="x", y="y", group="g", ax=ax)
    second = gs.line(frame, x="x", y="y", group="g", sort="x", ax=ax)

    assert np.asarray(first.artists[0].get_xdata()).tolist() == [2, 1, 1, 3]
    assert np.asarray(second.artists[0].get_xdata()).tolist() == [1, 1, 2, 3]
    assert np.asarray(second.artists[0].get_ydata()).tolist() == [10, 11, 20, 30]


def test_continuous_color_requires_and_uses_one_value_per_resolved_line(ax) -> None:
    frame = pd.DataFrame(
        {
            "x": [1, 2, 1, 2],
            "y": [2, 3, 4, 5],
            "series": ["A", "A", "B", "B"],
            "score": [0.0, 0.0, 10.0, 10.0],
        }
    )
    result = gs.line(
        frame, x="x", y="y", group="series", color="score", ax=ax
    )

    assert len(result.artists) == 2
    assert [artist.get_color() for artist in result.artists] == ["#440154", "#FDE725"]
    assert result.scales["color"].kind == "continuous"
    assert result.scales["color"].as_dict()["domain"] == [0.0, 10.0]


def test_varying_continuous_color_fails_before_drawing(ax) -> None:
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4], "score": [0.0, 1.0]})

    with pytest.raises(ValueError, match="must be constant within each resolved line"):
        gs.line(frame, x="x", y="y", color="score", ax=ax)

    assert list(ax.lines) == []
    assert semantic_registry(ax).revision == 0


def test_later_discrete_layer_reuses_existing_assignments(ax) -> None:
    first = pd.DataFrame(
        {"x": [1, 2, 1, 2], "y": [1, 2, 2, 3], "series": ["B", "B", "A", "A"]}
    )
    second = pd.DataFrame(
        {"x": [3, 4, 3, 4], "y": [3, 4, 4, 5], "series": ["A", "A", "C", "C"]}
    )

    initial = gs.line(first, x="x", y="y", color="series", ax=ax)
    added = gs.line(second, x="x", y="y", color="series", ax=ax)

    assert [artist.get_color() for artist in initial.artists] == ["#0072B2", "#D55E00"]
    assert [artist.get_color() for artist in added.artists] == ["#D55E00", "#009E73"]
    assert added.scales["color"].as_dict()["levels"] == ["B", "A", "C"]
    assert semantic_registry(ax).revision == 2


def test_later_continuous_layer_recolors_existing_managed_lines(ax) -> None:
    first = pd.DataFrame(
        {
            "x": [1, 2, 1, 2],
            "y": [1, 2, 2, 3],
            "series": ["A", "A", "B", "B"],
            "score": [0.0, 0.0, 10.0, 10.0],
        }
    )
    second = pd.DataFrame(
        {
            "x": [3, 4, 3, 4],
            "y": [2, 3, 3, 4],
            "series": ["C", "C", "D", "D"],
            "score": [-10.0, -10.0, 20.0, 20.0],
        }
    )
    initial = gs.line(first, x="x", y="y", color="score", group="series", ax=ax)
    old_colors = tuple(artist.get_color() for artist in initial.artists)

    added = gs.line(second, x="x", y="y", color="score", group="series", ax=ax)

    assert tuple(artist.get_color() for artist in initial.artists) != old_colors
    assert added.scales["color"].as_dict()["domain"] == [-10.0, 20.0]
    assert [artist.get_color() for artist in added.artists] == ["#440154", "#FDE725"]


def test_discrete_color_and_explicit_group_use_their_interaction(ax) -> None:
    frame = pd.DataFrame(
        {
            "x": [1, 2, 1, 2],
            "y": [1, 2, 3, 4],
            "group": ["one", "one", "one", "one"],
            "kind": ["A", "A", "B", "B"],
        }
    )
    result = gs.line(
        frame, x="x", y="y", group="group", color="kind", ax=ax
    )

    assert len(result.artists) == 2
    assert [np.asarray(artist.get_ydata()).tolist() for artist in result.artists] == [
        [1, 2],
        [3, 4],
    ]


def test_boolean_color_is_discrete(ax) -> None:
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4], "flag": [True, False]})
    result = gs.line(frame, x="x", y="y", color="flag", ax=ax)
    assert result.scales["color"].kind == "discrete"
    assert len(result.artists) == 2


def test_categorical_color_preserves_declared_observed_order(ax) -> None:
    frame = pd.DataFrame(
        {
            "x": [1, 2],
            "y": [3, 4],
            "kind": pd.Categorical(
                ["low", "high"], categories=["high", "medium", "low"], ordered=True
            ),
        }
    )
    result = gs.line(frame, x="x", y="y", color="kind", ax=ax)
    assert result.scales["color"].as_dict()["levels"] == ["high", "low"]
    assert [artist.get_color() for artist in result.artists] == ["#D55E00", "#0072B2"]


@pytest.mark.parametrize("policy", ["drop", "keep", "raise"])
def test_missing_explicit_group_policy_is_visible(ax, policy: str) -> None:
    frame = pd.DataFrame(
        {"x": [1, 2, 3], "y": [4, 5, 6], "group": ["A", None, "A"]}
    )
    if policy == "raise":
        with pytest.raises(ValueError, match="contains missing values"):
            gs.line(
                frame,
                x="x",
                y="y",
                group="group",
                group_missing=policy,  # type: ignore[arg-type]
                ax=ax,
            )
        assert list(ax.lines) == []
        return

    result = gs.line(
        frame,
        x="x",
        y="y",
        group="group",
        group_missing=policy,  # type: ignore[arg-type]
        ax=ax,
    )
    if policy == "drop":
        assert len(result.artists) == 1
        assert np.asarray(result.artists[0].get_xdata()).tolist() == [1, 3]
        assert result.diagnostics == ("dropped 1 row(s) with missing group 'group'",)
    else:
        assert len(result.artists) == 2
        assert result.diagnostics == ()


def test_missing_discrete_aesthetic_maps_to_an_explicit_group(ax) -> None:
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4], "kind": ["A", None]})
    result = gs.line(frame, x="x", y="y", color="kind", ax=ax)

    assert len(result.artists) == 2
    assert [artist.get_color() for artist in result.artists] == ["#0072B2", "#B3B3B3"]


def test_externally_removed_layer_is_pruned_before_retraining(ax) -> None:
    first = pd.DataFrame({"x": [1], "y": [2], "kind": ["A"]})
    second = pd.DataFrame({"x": [2], "y": [3], "kind": ["B"]})
    removed = gs.line(first, x="x", y="y", color="kind", ax=ax)
    removed.artists[0].remove()

    current = gs.line(second, x="x", y="y", color="kind", ax=ax)

    assert current.scales["color"].as_dict()["levels"] == ["B"]
    assert [item.layer_id for item in semantic_registry(ax).contributions] == ["line-2"]


def test_existing_collapsed_date_handle_refreshes_with_new_observations(ax) -> None:
    initial = pd.to_datetime(["2024-01-01", "2024-01-03"])
    added = pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-02", "2024-01-04"]), "value": [2, 4]}
    )
    handle = gs.dates(ax, data=initial).collapse()
    revision = handle.revision

    result = gs.line(added, x="date", y="value", ax=ax)

    assert len(result.artists) == 1
    assert handle.mode == "collapse"
    assert handle.revision == revision + 1
    assert handle.observations.equals(pd.date_range("2024-01-01", periods=4))


def test_partial_matplotlib_failure_rolls_back_artists_limits_and_registry(
    ax, monkeypatch
) -> None:
    frame = _grouped_frame()
    original_plot = ax.plot
    calls = 0
    data_limits = ax.dataLim.get_points().copy()
    view_limits = ax.viewLim.get_points().copy()

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("renderer failed")
        return original_plot(*args, **kwargs)

    monkeypatch.setattr(ax, "plot", fail_second)
    with pytest.raises(RuntimeError, match="renderer failed"):
        gs.line(frame, x="date", y="value", color="series", ax=ax)

    assert list(ax.lines) == []
    np.testing.assert_array_equal(ax.dataLim.get_points(), data_limits)
    np.testing.assert_array_equal(ax.viewLim.get_points(), view_limits)
    assert semantic_registry(ax).revision == 0


def test_rollback_restores_axis_units_formatters_and_property_cycle(
    ax, monkeypatch
) -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"]
            ),
            "value": [1, 2, 3, 4],
            "group": ["A", "A", "B", "B"],
        }
    )
    original_plot = ax.plot
    original_locator = ax.xaxis.get_major_locator()
    original_formatter = ax.xaxis.get_major_formatter()
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("renderer failed")
        return original_plot(*args, **kwargs)

    monkeypatch.setattr(ax, "plot", fail_second)
    with pytest.raises(RuntimeError, match="renderer failed"):
        gs.line(frame, x="date", y="value", group="group", ax=ax)

    assert ax.xaxis.get_converter() is None
    assert ax.xaxis.get_units() is None
    assert ax.xaxis.get_major_locator() is original_locator
    assert ax.xaxis.get_major_formatter() is original_formatter
    assert not isinstance(ax.xaxis.get_major_locator(), mdates.AutoDateLocator)

    monkeypatch.setattr(ax, "plot", original_plot)
    result = gs.line(
        {"x": [1, 2, 1, 2], "y": [1, 2, 3, 4], "g": ["A", "A", "B", "B"]},
        x="x",
        y="y",
        group="g",
        ax=ax,
    )
    expected = matplotlib.rcParams["axes.prop_cycle"].by_key()["color"][:2]
    assert [artist.get_color() for artist in result.artists] == expected


def test_failed_later_layer_restores_recolored_existing_lines(ax, monkeypatch) -> None:
    first = pd.DataFrame(
        {
            "x": [1, 2, 1, 2],
            "y": [1, 2, 2, 3],
            "g": ["A", "A", "B", "B"],
            "score": [0.0, 0.0, 10.0, 10.0],
        }
    )
    initial = gs.line(first, x="x", y="y", group="g", color="score", ax=ax)
    colors = tuple(artist.get_color() for artist in initial.artists)
    revision = semantic_registry(ax).revision
    second = pd.DataFrame(
        {"x": [3, 4], "y": [3, 4], "g": ["C", "C"], "score": [20.0, 20.0]}
    )

    def fail(*args, **kwargs):
        raise RuntimeError("renderer failed")

    monkeypatch.setattr(ax, "plot", fail)
    with pytest.raises(RuntimeError, match="renderer failed"):
        gs.line(second, x="x", y="y", group="g", color="score", ax=ax)

    assert tuple(artist.get_color() for artist in initial.artists) == colors
    assert semantic_registry(ax).revision == revision
    assert tuple(ax.lines) == initial.artists


def test_date_refresh_failure_rolls_back_line_and_semantic_state(ax, monkeypatch) -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    handle = gs.dates(ax, data=dates)
    frame = pd.DataFrame({"x": dates, "y": [1, 2], "kind": ["A", "A"]})

    def fail() -> None:
        raise RuntimeError("date refresh failed")

    monkeypatch.setattr(handle, "refresh", fail)
    with pytest.raises(RuntimeError, match="date refresh failed"):
        gs.line(frame, x="x", y="y", color="kind", ax=ax)

    assert list(ax.lines) == []
    assert semantic_registry(ax).revision == 0


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"ax": object()}, TypeError, "matplotlib Axes"),
        ({"x": 1}, TypeError, "x must be a column-name string"),
        ({"y": ""}, ValueError, "y must not be empty"),
        ({"color": 1}, TypeError, "color must be a column-name string"),
        ({"group": 1}, TypeError, "group must be a column-name string"),
        ({"linestyle": 1}, TypeError, "linestyle must be a column-name string"),
        ({"sort": "value"}, ValueError, "sort must be"),
        ({"group_missing": "ignore"}, ValueError, "group_missing must be"),
        ({"style": []}, TypeError, "style must be a mapping"),
        ({"style": {1: "red"}}, TypeError, "style keys must be strings"),
        ({"style": {"not_a_property": 1}}, AttributeError, "invalid fixed line style"),
    ],
)
def test_public_arguments_are_validated_before_drawing(
    ax, arguments, error, message
) -> None:
    values = {"data": {"x": [1], "y": [2]}, "x": "x", "y": "y", "ax": ax}
    values.update(arguments)
    with pytest.raises(error, match=message):
        gs.line(**values)
    assert list(ax.lines) == []


@pytest.mark.parametrize("fixed", [{"color": "red"}, {"c": "red"}])
def test_mapped_color_cannot_also_be_fixed(ax, fixed) -> None:
    with pytest.raises(ValueError, match="both mapped and fixed"):
        gs.line(
            {"x": [1], "y": [2], "kind": ["A"]},
            x="x",
            y="y",
            color="kind",
            style=fixed,
            ax=ax,
        )


@pytest.mark.parametrize("fixed", [{"linestyle": "--"}, {"ls": "--"}])
def test_mapped_linestyle_cannot_also_be_fixed(ax, fixed) -> None:
    with pytest.raises(ValueError, match="both mapped and fixed"):
        gs.line(
            {"x": [1], "y": [2], "kind": ["A"]},
            x="x",
            y="y",
            linestyle="kind",
            style=fixed,
            ax=ax,
        )


def test_unknown_or_ambiguous_columns_fail_without_mutation(ax) -> None:
    with pytest.raises(KeyError, match="no column 'missing'"):
        gs.line({"x": [1], "y": [2]}, x="x", y="missing", ax=ax)

    duplicate = pd.DataFrame([[1, 2, 3]], columns=["x", "x", "y"])
    with pytest.raises(ValueError, match="one-dimensional and uniquely named"):
        gs.line(duplicate, x="x", y="y", ax=ax)
    assert list(ax.lines) == []


def test_mismatched_mapping_lengths_fail_before_drawing(ax) -> None:
    with pytest.raises(ValueError, match="equal length"):
        gs.line({"x": [1, 2], "y": [3]}, x="x", y="y", ax=ax)
    assert list(ax.lines) == []


def test_unhashable_group_values_fail_before_drawing(ax) -> None:
    frame = {"x": [1], "y": [2], "g": [["nested"]]}
    with pytest.raises(TypeError, match="hashable scalar"):
        gs.line(frame, x="x", y="y", group="g", ax=ax)
    assert list(ax.lines) == []


def test_unorderable_x_fails_only_when_sorting_is_requested(ax) -> None:
    frame = {"x": [1, "two"], "y": [1, 2]}
    unsorted = gs.line(frame, x="x", y="y", ax=ax)
    assert np.asarray(unsorted.artists[0].get_xdata()).tolist() == ["1", "two"]

    with pytest.raises(TypeError, match="mutually orderable"):
        gs.line(frame, x="x", y="y", sort="x", ax=ax)


def test_empty_unmapped_data_returns_no_artists(ax) -> None:
    result = gs.line({"x": [], "y": []}, x="x", y="y", ax=ax)
    assert result.artists == ()
    assert result.scales == {}


def test_result_and_style_are_defensive_and_immutable(ax) -> None:
    style = {"color": "#123456"}
    result = gs.line({"x": [1], "y": [2]}, x="x", y="y", style=style, ax=ax)
    style["color"] = "#654321"

    assert result.artists[0].get_color() == "#123456"
    with pytest.raises(TypeError):
        result.scales["color"] = object()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        result.layer_id = "changed"  # type: ignore[misc]


def test_line_is_exported_in_the_public_namespace() -> None:
    assert "line" in gs.__all__
    assert "LineResult" in gs.__all__
    assert "AestheticScale" in gs.__all__


def test_basic_polars_frame_uses_the_same_mapping_boundary(ax) -> None:
    polars = pytest.importorskip("polars")
    frame = polars.DataFrame(
        {
            "x": [1, 2, 1, 2],
            "y": [1.0, 2.0, 2.0, 3.0],
            "series": ["A", "A", "B", "B"],
        }
    )
    result = gs.line(frame, x="x", y="y", color="series", ax=ax)

    assert len(result.artists) == 2
    assert result.scales["color"].as_dict()["levels"] == ["A", "B"]


def test_accessibility_diagnostic_is_returned_for_many_color_levels(ax) -> None:
    frame = pd.DataFrame(
        {
            "x": list(range(7)),
            "y": list(range(7)),
            "series": list("ABCDEFG"),
        }
    )
    result = gs.line(frame, x="x", y="y", color="series", ax=ax)
    assert result.diagnostics == (
        "color mapping for 'series' has 7 levels; prefer direct labels or facets",
    )


def test_color_cardinality_fails_before_axes_or_registry_mutation(ax) -> None:
    frame = pd.DataFrame(
        {"x": range(9), "y": range(9), "series": [f"S{index}" for index in range(9)]}
    )
    with pytest.raises(ValueError, match="supports at most 8 levels"):
        gs.line(frame, x="x", y="y", color="series", ax=ax)
    assert list(ax.lines) == []
    assert semantic_registry(ax).revision == 0


@check_figures_equal()
def test_semantic_line_matches_equivalent_native_lines(fig_test, fig_ref) -> None:
    frame = _grouped_frame()
    test_ax = fig_test.subplots()
    ref_ax = fig_ref.subplots()

    gs.line(
        frame,
        x="date",
        y="value",
        color="series",
        sort="x",
        style={"linewidth": 2},
        ax=test_ax,
    )
    for series, color in (("A", "#0072B2"), ("B", "#D55E00")):
        subset = frame.loc[frame["series"] == series].sort_values("date", kind="stable")
        ref_ax.plot(subset["date"], subset["value"], color=color, linewidth=2)
