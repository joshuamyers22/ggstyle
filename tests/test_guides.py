"""Automatic semantic legend and colorbar behavior."""

from __future__ import annotations

import gc
import weakref
from dataclasses import FrozenInstanceError

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colorbar import Colorbar
from matplotlib.legend import Legend

import ggstyle as gs
from ggstyle._semantic_registry import semantic_registry
from ggstyle.guides import _guide_state_count


@pytest.fixture
def ax():
    figure, axes = plt.subplots()
    try:
        yield axes
    finally:
        plt.close(figure)


def _legend_labels(legend: Legend) -> list[str]:
    return [item.get_text() for item in legend.get_texts()]


def test_discrete_color_builds_a_native_legend_from_the_trained_scale(ax) -> None:
    gs.line(
        {"x": [1, 2, 1, 2], "y": [1, 2, 2, 3], "series": ["A", "A", "B", "B"]},
        x="x",
        y="y",
        color="series",
        ax=ax,
    )

    result = gs.guides(ax)

    assert result.axes is ax
    assert len(result.legends) == 1
    assert isinstance(result.legends[0], Legend)
    assert result.legends[0].axes is ax
    assert result.legends[0].get_title().get_text() == "series"
    assert _legend_labels(result.legends[0]) == ["A", "B"]
    assert result.colorbars == ()
    assert ax.get_legend() is None


def test_explicit_scale_name_becomes_the_guide_title(ax) -> None:
    gs.points(
        {"x": [1, 2], "y": [3, 4], "kind": ["A", "B"]},
        x="x",
        y="y",
        color="kind",
        color_scale=gs.DiscreteScale(name="Series"),
        ax=ax,
    )
    result = gs.guides(ax)
    assert result.legends[0].get_title().get_text() == "Series"


def test_color_and_linestyle_for_the_same_variable_merge(ax) -> None:
    gs.line(
        {"x": [1, 2, 1, 2], "y": [1, 2, 2, 3], "kind": ["A", "A", "B", "B"]},
        x="x",
        y="y",
        color="kind",
        linestyle="kind",
        ax=ax,
    )

    result = gs.guides(ax)

    assert len(result.legends) == 1
    assert _legend_labels(result.legends[0]) == ["A", "B"]
    assert result.diagnostics == ("merged color and linestyle guides for 'kind'",)
    handles = result.legends[0].legend_handles
    assert [item.get_color() for item in handles] == ["#0072B2", "#D55E00"]
    assert [item.get_linestyle() for item in handles] == ["-", "--"]


def test_different_titles_or_variables_remain_distinct_guides(ax) -> None:
    gs.line(
        {"x": [1, 2], "y": [1, 2], "kind": ["A", "A"], "status": ["A", "A"]},
        x="x",
        y="y",
        color="kind",
        linestyle="status",
        color_scale=gs.DiscreteScale(name="Kind"),
        linestyle_scale=gs.DiscreteScale(name="Status"),
        ax=ax,
    )
    result = gs.guides(ax)
    assert len(result.legends) == 2
    assert [item.get_title().get_text() for item in result.legends] == [
        "Kind",
        "Status",
    ]


def test_same_variable_with_different_guide_titles_does_not_merge(ax) -> None:
    gs.line(
        {"x": [1, 2], "y": [1, 2], "kind": ["A", "A"]},
        x="x",
        y="y",
        color="kind",
        linestyle="kind",
        color_scale=gs.DiscreteScale(name="Color kind"),
        linestyle_scale=gs.DiscreteScale(name="Line kind"),
        ax=ax,
    )
    result = gs.guides(ax)
    assert [item.get_title().get_text() for item in result.legends] == [
        "Color kind",
        "Line kind",
    ]


def test_different_variables_with_same_title_and_levels_do_not_merge(ax) -> None:
    gs.points(
        {"x": [1], "y": [2], "first": ["A"]},
        x="x",
        y="y",
        color="first",
        color_scale=gs.DiscreteScale(name="Shared title"),
        ax=ax,
    )
    gs.line(
        {"x": [2], "y": [3], "second": ["A"]},
        x="x",
        y="y",
        linestyle="second",
        linestyle_scale=gs.DiscreteScale(name="Shared title"),
        ax=ax,
    )
    result = gs.guides(ax)
    assert len(result.legends) == 2
    assert all(
        item.get_title().get_text() == "Shared title" for item in result.legends
    )


def test_missing_and_unobserved_discrete_levels_have_deterministic_entries(ax) -> None:
    gs.points(
        {"x": [1, 2], "y": [3, 4], "kind": ["A", None]},
        x="x",
        y="y",
        color="kind",
        color_scale=gs.DiscreteScale(
            order=("A", "B"), include_unobserved=True, missing="map"
        ),
        ax=ax,
    )
    result = gs.guides(ax)
    assert _legend_labels(result.legends[0]) == ["A", "B", "(missing)"]
    handles = result.legends[0].legend_handles
    assert [item.get_color() for item in handles] == [
        "#0072B2",
        "#D55E00",
        "#B3B3B3",
    ]


def test_continuous_color_builds_a_native_colorbar(ax) -> None:
    gs.points(
        {"x": [1, 2, 3], "y": [3, 4, 5], "score": [0.0, 5.0, 10.0]},
        x="x",
        y="y",
        color="score",
        color_scale=gs.ContinuousScale(name="Score"),
        ax=ax,
    )

    result = gs.guides(ax)

    assert result.legends == ()
    assert len(result.colorbars) == 1
    colorbar = result.colorbars[0]
    assert isinstance(colorbar, Colorbar)
    assert colorbar.ax.get_ylabel() == "Score"
    assert colorbar.mappable.norm.vmin == 0.0
    assert colorbar.mappable.norm.vmax == 10.0
    np.testing.assert_allclose(
        colorbar.mappable.to_rgba(0.0), matplotlib.colors.to_rgba("#440154")
    )
    np.testing.assert_allclose(
        colorbar.mappable.to_rgba(10.0), matplotlib.colors.to_rgba("#FDE725")
    )


def test_constant_continuous_domain_uses_one_truthful_tick(ax) -> None:
    gs.line(
        {"x": [1, 2], "y": [2, 3], "score": [5.0, 5.0]},
        x="x",
        y="y",
        color="score",
        ax=ax,
    )
    colorbar = gs.guides(ax).colorbars[0]
    assert colorbar.get_ticks().tolist() == [5.0]


def test_multiple_continuous_variables_remain_separate_colorbars(ax) -> None:
    gs.points(
        {"x": [1, 2], "y": [2, 3], "first": [0.0, 1.0]},
        x="x",
        y="y",
        color="first",
        ax=ax,
    )
    gs.points(
        {"x": [3, 4], "y": [4, 5], "second": [10.0, 20.0]},
        x="x",
        y="y",
        color="second",
        ax=ax,
    )
    result = gs.guides(ax)
    assert len(result.colorbars) == 2
    assert [item.ax.get_ylabel() for item in result.colorbars] == ["first", "second"]


def test_repeated_call_is_idempotent_for_one_registry_revision(ax) -> None:
    gs.points(
        {"x": [1], "y": [2], "kind": ["A"]},
        x="x",
        y="y",
        color="kind",
        ax=ax,
    )
    first = gs.guides(ax)
    second = gs.guides(ax)
    assert second.legends == first.legends


def test_active_guides_refresh_after_a_later_semantic_layer(ax) -> None:
    gs.line(
        {"x": [1], "y": [2], "kind": ["A"]},
        x="x",
        y="y",
        color="kind",
        ax=ax,
    )
    first = gs.guides(ax)
    old_legend = first.legends[0]

    gs.points(
        {"x": [2], "y": [3], "kind": ["B"]},
        x="x",
        y="y",
        color="kind",
        ax=ax,
    )
    refreshed = gs.guides(ax)

    assert refreshed.legends[0] is not old_legend
    assert old_legend.axes is None
    assert _legend_labels(refreshed.legends[0]) == ["A", "B"]
    assert semantic_registry(ax).revision == 2


def test_active_colorbar_refreshes_after_continuous_domain_expansion(ax) -> None:
    gs.points(
        {"x": [1, 2], "y": [2, 3], "score": [0.0, 10.0]},
        x="x",
        y="y",
        color="score",
        ax=ax,
    )
    first = gs.guides(ax).colorbars[0]
    old_axes = first.ax

    gs.line(
        {"x": [3, 4], "y": [4, 5], "score": [20.0, 20.0]},
        x="x",
        y="y",
        color="score",
        ax=ax,
    )
    refreshed = gs.guides(ax).colorbars[0]

    assert refreshed is not first
    assert refreshed.mappable.norm.vmin == 0.0
    assert refreshed.mappable.norm.vmax == 20.0
    assert old_axes not in ax.child_axes


def test_guides_can_be_activated_before_the_first_semantic_layer(ax) -> None:
    assert gs.guides(ax).legends == ()
    gs.points(
        {"x": [1], "y": [2], "kind": ["A"]},
        x="x",
        y="y",
        color="kind",
        ax=ax,
    )
    assert _legend_labels(gs.guides(ax).legends[0]) == ["A"]


def test_empty_automatic_discrete_scale_does_not_create_an_empty_legend(ax) -> None:
    gs.points(
        {"x": [], "y": [], "kind": []},
        x="x",
        y="y",
        color="kind",
        color_scale=gs.DiscreteScale(),
        ax=ax,
    )
    assert gs.guides(ax).legends == ()


def test_automatic_guide_count_is_bounded_before_mutation(ax) -> None:
    for index in range(5):
        variable = f"score_{index}"
        gs.points(
            {"x": [index], "y": [index], variable: [float(index)]},
            x="x",
            y="y",
            color=variable,
            ax=ax,
        )
    with pytest.raises(ValueError, match="at most 4 distinct colorbars"):
        gs.guides(ax)
    assert ax.child_axes == []


def test_disable_removes_managed_guides_and_stops_automatic_refresh(ax) -> None:
    gs.points(
        {"x": [1], "y": [2], "kind": ["A"]},
        x="x",
        y="y",
        color="kind",
        ax=ax,
    )
    legend = gs.guides(ax).legends[0]
    disabled = gs.guides(ax, enabled=False)
    assert disabled.legends == ()
    assert legend.axes is None

    gs.points(
        {"x": [2], "y": [3], "kind": ["B"]},
        x="x",
        y="y",
        color="kind",
        ax=ax,
    )
    assert not any(isinstance(item, Legend) for item in ax.artists)


def test_externally_removed_managed_legend_is_rebuilt(ax) -> None:
    gs.points(
        {"x": [1], "y": [2], "kind": ["A"]},
        x="x",
        y="y",
        color="kind",
        ax=ax,
    )
    original = gs.guides(ax).legends[0]
    original.remove()
    rebuilt = gs.guides(ax).legends[0]
    assert rebuilt is not original
    assert rebuilt.axes is ax


def test_caller_owned_legend_and_colorbar_are_preserved(ax) -> None:
    native_line = ax.plot([1, 2], [2, 3], label="Native")[0]
    native_legend = ax.legend()
    image = ax.imshow([[0, 1], [1, 0]], alpha=0.1)
    native_colorbar = ax.figure.colorbar(image, ax=ax)
    native_colorbar_axes = native_colorbar.ax

    gs.points(
        {"x": [1, 2], "y": [3, 4], "kind": ["A", "B"]},
        x="x",
        y="y",
        color="kind",
        ax=ax,
    )
    result = gs.guides(ax)

    assert native_line.axes is ax
    assert ax.get_legend() is native_legend
    assert native_colorbar.ax is native_colorbar_axes
    assert native_colorbar_axes.figure is ax.figure
    assert result.diagnostics == ("preserved existing caller-owned axes legend",)

    gs.guides(ax, enabled=False)
    assert ax.get_legend() is native_legend
    assert native_colorbar_axes.figure is ax.figure


def test_guide_creation_failure_is_atomic(ax, monkeypatch) -> None:
    gs.line(
        {
            "x": [1, 2],
            "y": [2, 3],
            "kind": ["A", "A"],
            "score": [0.0, 0.0],
        },
        x="x",
        y="y",
        linestyle="kind",
        color="score",
        ax=ax,
    )

    def fail(*args, **kwargs):
        raise RuntimeError("colorbar failed")

    monkeypatch.setattr(ax.figure, "colorbar", fail)
    with pytest.raises(RuntimeError, match="colorbar failed"):
        gs.guides(ax)
    assert not any(isinstance(item, Legend) for item in ax.artists)
    assert ax.child_axes == []


def test_failed_live_refresh_preserves_old_guides_and_semantic_state(
    ax, monkeypatch
) -> None:
    initial = gs.points(
        {"x": [1], "y": [2], "kind": ["A"]},
        x="x",
        y="y",
        color="kind",
        ax=ax,
    )
    old = gs.guides(ax).legends[0]
    revision = semantic_registry(ax).revision

    def fail(*args, **kwargs):
        raise RuntimeError("legend failed")

    monkeypatch.setattr(ax, "add_artist", fail)
    with pytest.raises(RuntimeError, match="legend failed"):
        gs.points(
            {"x": [2], "y": [3], "kind": ["B"]},
            x="x",
            y="y",
            color="kind",
            ax=ax,
        )

    assert old.axes is ax
    assert _legend_labels(old) == ["A"]
    assert tuple(ax.collections) == initial.artists
    assert semantic_registry(ax).revision == revision


def test_date_refresh_failure_discards_prepared_replacement_guides(
    ax, monkeypatch
) -> None:
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    handle = gs.dates(ax, data=dates)
    initial = gs.points(
        {"date": [dates[0]], "value": [1], "kind": ["A"]},
        x="date",
        y="value",
        color="kind",
        ax=ax,
    )
    old = gs.guides(ax).legends[0]
    revision = semantic_registry(ax).revision

    def fail() -> None:
        raise RuntimeError("date refresh failed")

    monkeypatch.setattr(handle, "refresh", fail)
    with pytest.raises(RuntimeError, match="date refresh failed"):
        gs.points(
            {"date": [dates[1]], "value": [2], "kind": ["B"]},
            x="date",
            y="value",
            color="kind",
            ax=ax,
        )
    assert old.axes is ax
    assert tuple(item for item in ax.artists if isinstance(item, Legend)) == (old,)
    assert tuple(ax.collections) == initial.artists
    assert semantic_registry(ax).revision == revision


def test_incompatible_scale_names_fail_before_guides_or_artists_change(ax) -> None:
    initial = gs.points(
        {"x": [1], "y": [2], "kind": ["A"]},
        x="x",
        y="y",
        color="kind",
        color_scale=gs.DiscreteScale(name="First"),
        ax=ax,
    )
    legend = gs.guides(ax).legends[0]

    with pytest.raises(ValueError, match="conflicting color scales"):
        gs.points(
            {"x": [2], "y": [3], "kind": ["B"]},
            x="x",
            y="y",
            color="kind",
            color_scale=gs.DiscreteScale(name="Second"),
            ax=ax,
        )
    assert tuple(ax.collections) == initial.artists
    assert gs.guides(ax).legends == (legend,)


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"ax": object()}, TypeError, "matplotlib Axes"),
        ({"enabled": 1}, TypeError, "enabled must be bool"),
    ],
)
def test_arguments_are_validated(arguments, error, message, ax) -> None:
    values = {"ax": ax}
    values.update(arguments)
    with pytest.raises(error, match=message):
        gs.guides(**values)


def test_result_is_frozen_and_publicly_exported(ax) -> None:
    result = gs.guides(ax)
    with pytest.raises(FrozenInstanceError):
        result.diagnostics = ()  # type: ignore[misc]
    assert {"guides", "GuideResult"} <= set(gs.__all__)


def test_guide_state_does_not_keep_axes_alive() -> None:
    gc.collect()
    before = _guide_state_count()
    figure, axes = plt.subplots()
    gs.points(
        {"x": [1], "y": [2], "kind": ["A"]},
        x="x",
        y="y",
        color="kind",
        ax=axes,
    )
    gs.guides(axes)
    reference = weakref.ref(axes)
    plt.close(figure)
    del axes, figure
    gc.collect()
    assert reference() is None
    assert _guide_state_count() == before
