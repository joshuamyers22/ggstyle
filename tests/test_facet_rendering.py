"""Callback rendering behavior for native one-variable wrap facets."""

from __future__ import annotations

import json
from collections.abc import Mapping

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.axes import Axes

import ggstyle as gs


@pytest.fixture(autouse=True)
def close_figures() -> None:
    """Keep renderer tests independent from pyplot's global figure registry."""

    yield
    plt.close("all")


def test_facets_creates_only_active_native_axes_in_plan_order() -> None:
    grid = gs.facets(
        {"group": ["B", "A", "C", "B"], "value": [1, 2, 3, 4]},
        col="group",
        wrap=2,
        scales="free",
    )

    assert grid.plan.layout == "wrap"
    assert grid.plan.shape == (2, 2)
    assert grid.plan.col_levels == ("B", "A", "C")
    assert len(grid.axes) == 3
    assert tuple(grid.figure.axes) == grid.axes
    assert all(isinstance(axes, Axes) for axes in grid.axes)
    assert [axes.get_title() for axes in grid.axes] == ["B", "A", "C"]
    assert [axes.get_label() for axes in grid.axes] == [
        "group: B",
        "group: A",
        "group: C",
    ]
    assert [
        (
            axes.get_subplotspec().rowspan.start,
            axes.get_subplotspec().colspan.start,
        )
        for axes in grid.axes
    ] == [(0, 0), (0, 1), (1, 0)]


def test_grid_renders_cartesian_panels_and_typed_empty_subsets() -> None:
    frame = pd.DataFrame(
        {
            "region": ["R2", "R1", "R2"],
            "metric": ["C1", "C2", "C2"],
            "value": [1, 2, 3],
        }
    )
    grid = gs.facets(
        frame,
        row="region",
        col="metric",
        row_order=("R1", "R2", "R3"),
        col_order=("C2", "C1"),
        include_unobserved=True,
    )
    seen: list[pd.DataFrame] = []

    def collect(panel: pd.DataFrame, axes: Axes) -> None:
        seen.append(panel)

    grid.map(collect)

    assert grid.plan.layout == "grid"
    assert grid.plan.shape == (3, 2)
    assert len(grid.axes) == 6
    assert tuple(grid.figure.axes) == grid.axes
    assert [axes.get_title() for axes in grid.axes] == [
        "R1 | C2",
        "R1 | C1",
        "R2 | C2",
        "R2 | C1",
        "R3 | C2",
        "R3 | C1",
    ]
    assert [axes.get_label() for axes in grid.axes] == [
        "region: R1, metric: C2",
        "region: R1, metric: C1",
        "region: R2, metric: C2",
        "region: R2, metric: C1",
        "region: R3, metric: C2",
        "region: R3, metric: C1",
    ]
    assert [list(panel["value"]) for panel in seen] == [[2], [], [3], [1], [], []]
    assert all(isinstance(panel, pd.DataFrame) for panel in seen)
    assert [panel.empty for panel in seen] == [False, True, False, False, True, True]


def test_row_only_and_column_only_grids_use_planned_geometry() -> None:
    row_grid = gs.facets({"group": ["A", "B"]}, row="group")
    column_grid = gs.facets({"group": ["A", "B"]}, col="group")

    assert row_grid.plan.shape == (2, 1)
    assert column_grid.plan.shape == (1, 2)
    assert [
        (
            axes.get_subplotspec().rowspan.start,
            axes.get_subplotspec().colspan.start,
        )
        for axes in row_grid.axes
    ] == [(0, 0), (1, 0)]
    assert [
        (
            axes.get_subplotspec().rowspan.start,
            axes.get_subplotspec().colspan.start,
        )
        for axes in column_grid.axes
    ] == [(0, 0), (0, 1)]
    assert [axes.get_title() for axes in row_grid.axes] == ["A", "B"]
    assert [axes.get_title() for axes in column_grid.axes] == ["A", "B"]


def test_grid_preserves_declared_categorical_order() -> None:
    frame = pd.DataFrame(
        {
            "region": pd.Categorical(
                ["South", "North"],
                categories=["North", "South", "West"],
                ordered=True,
            ),
            "metric": pd.Categorical(
                ["M1", "M2"],
                categories=["M2", "M1"],
                ordered=True,
            ),
        }
    )

    grid = gs.facets(
        frame,
        row="region",
        col="metric",
        include_unobserved=True,
    )

    assert grid.plan.row_levels == ("North", "South", "West")
    assert grid.plan.col_levels == ("M2", "M1")
    assert [axes.get_title() for axes in grid.axes] == [
        "North | M2",
        "North | M1",
        "South | M2",
        "South | M1",
        "West | M2",
        "West | M1",
    ]
    assert [panel.empty for panel in grid.plan.panels] == [
        False,
        True,
        True,
        False,
        True,
        True,
    ]


def test_map_receives_defensive_pandas_subsets_and_matching_axes() -> None:
    frame = pd.DataFrame(
        {"group": ["A", "B", "A"], "x": [1, 2, 3], "value": [10, 20, 30]},
        index=[5, 6, 7],
    )
    original = frame.copy(deep=True)
    grid = gs.facets(frame, col="group", wrap=2)
    seen: list[tuple[pd.DataFrame, Axes]] = []

    def draw(panel: object, axes: Axes) -> None:
        assert isinstance(panel, pd.DataFrame)
        seen.append((panel.copy(deep=True), axes))
        panel.loc[:, "value"] = -1
        axes.plot(panel["x"], panel["value"])

    returned = grid.map(draw)

    assert returned is grid
    assert grid.map_count == 1
    assert [list(panel.index) for panel, _ in seen] == [[5, 7], [6]]
    assert [list(panel["value"]) for panel, _ in seen] == [[10, 30], [20]]
    assert [axes for _, axes in seen] == list(grid.axes)
    assert [len(axes.lines) for axes in grid.axes] == [1, 1]
    pd.testing.assert_frame_equal(frame, original)


def test_each_map_pass_receives_fresh_panel_data() -> None:
    frame = pd.DataFrame({"group": ["A", "A"], "value": [1, 2]})
    grid = gs.facets(frame, col="group")

    def mutate(panel: object, axes: Axes) -> None:
        assert isinstance(panel, pd.DataFrame)
        panel.loc[:, "value"] = 99

    observed: list[int] = []
    grid.map(mutate).map(
        lambda panel, axes: observed.extend(
            list(panel["value"]) if isinstance(panel, pd.DataFrame) else []
        )
    )

    assert observed == [1, 2]
    assert grid.map_count == 2


def test_grid_uses_construction_time_snapshot_after_source_changes() -> None:
    frame = pd.DataFrame({"group": ["A", "B"], "value": [1, 2]})
    grid = gs.facets(frame, col="group")
    frame.loc[:, "value"] = [100, 200]
    observed: list[int] = []

    grid.map(
        lambda panel, axes: observed.extend(
            list(panel["value"]) if isinstance(panel, pd.DataFrame) else []
        )
    )

    assert observed == [1, 2]


@pytest.mark.parametrize(
    ("scales", "share_x", "share_y"),
    [
        ("fixed", True, True),
        ("free_x", False, True),
        ("free_y", True, False),
        ("free", False, False),
    ],
)
def test_scales_select_native_matplotlib_axis_sharing(
    scales: str, share_x: bool, share_y: bool
) -> None:
    grid = gs.facets(
        {"group": ["A", "B"], "value": [1, 2]},
        col="group",
        wrap=2,
        scales=scales,  # type: ignore[arg-type]
    )
    first, second = grid.axes

    assert first.get_shared_x_axes().joined(first, second) is share_x
    assert first.get_shared_y_axes().joined(first, second) is share_y


def test_mapping_subsets_include_all_columns_and_empty_panels() -> None:
    source = {
        "group": ["A", "B", "A"],
        "value": [1, 2, 3],
        "label": ("one", "two", "three"),
    }
    grid = gs.facets(
        source,
        col="group",
        wrap=2,
        col_order=("B", "C", "A"),
        include_unobserved=True,
    )
    seen: list[dict[object, object]] = []

    def collect(panel: object, axes: Axes) -> None:
        assert isinstance(panel, dict)
        seen.append(panel)

    grid.map(collect)

    assert [panel["value"] for panel in seen] == [[2], [], [1, 3]]
    assert [panel["label"] for panel in seen] == [
        ["two"],
        [],
        ["one", "three"],
    ]
    assert grid.axes[1].get_title() == "C"
    assert grid.plan.panels[1].empty


def test_callback_can_use_semantic_helpers_on_native_panel_axes() -> None:
    frame = pd.DataFrame(
        {
            "group": ["A", "A", "B", "B"],
            "x": [1, 2, 1, 2],
            "value": [2, 3, 4, 5],
        }
    )
    grid = gs.facets(frame, col="group", wrap=2, scales="free")

    grid.map(
        lambda panel, axes: gs.line(
            panel,
            x="x",
            y="value",
            style={"color": "#4477AA"},
            ax=axes,
        )
    )

    assert [len(axes.lines) for axes in grid.axes] == [1, 1]
    assert [list(axes.lines[0].get_ydata()) for axes in grid.axes] == [[2, 3], [4, 5]]


def test_semantic_helpers_leave_empty_grid_panels_empty() -> None:
    frame = pd.DataFrame({"row": ["R1"], "col": ["C1"], "x": [1], "y": [2]})
    grid = gs.facets(
        frame,
        row="row",
        col="col",
        row_order=("R1", "R2"),
        col_order=("C1", "C2"),
        include_unobserved=True,
        scales="free",
    )

    grid.map(lambda panel, axes: gs.line(panel, x="x", y="y", ax=axes))

    assert [len(axes.lines) for axes in grid.axes] == [1, 0, 0, 0]


def test_missing_keep_uses_accessible_na_title() -> None:
    grid = gs.facets(
        {"group": ["A", None], "value": [1, 2]},
        col="group",
        missing="keep",
    )

    assert [axes.get_title() for axes in grid.axes] == ["A", "NA"]
    assert grid.axes[1].get_label() == "group: NA"


def test_polars_callbacks_preserve_frame_type_and_partition_order() -> None:
    polars = pytest.importorskip("polars")
    frame = polars.DataFrame(
        {"group": ["B", "A", "B"], "value": [1, 2, 3]}
    )
    grid = gs.facets(frame, col="group", wrap=2)
    seen: list[object] = []

    grid.map(lambda panel, axes: seen.append(panel))

    assert all(isinstance(panel, polars.DataFrame) for panel in seen)
    assert [panel["value"].to_list() for panel in seen] == [[1, 3], [2]]
    assert frame["value"].to_list() == [1, 2, 3]


def test_polars_grid_matches_pandas_panel_values_and_empty_partitions() -> None:
    polars = pytest.importorskip("polars")
    values = {
        "row": ["R2", "R1", "R2"],
        "col": ["C1", "C2", "C2"],
        "value": [1, 2, 3],
    }
    pandas_grid = gs.facets(pd.DataFrame(values), row="row", col="col")
    polars_grid = gs.facets(polars.DataFrame(values), row="row", col="col")
    pandas_values: list[list[int]] = []
    polars_values: list[list[int]] = []

    pandas_grid.map(
        lambda panel, axes: pandas_values.append(list(panel["value"]))
    )
    polars_grid.map(
        lambda panel, axes: polars_values.append(panel["value"].to_list())
    )

    assert polars_grid.plan.as_dict() == pandas_grid.plan.as_dict()
    assert polars_values == pandas_values == [[1], [3], [], [2]]


def test_polars_enum_order_controls_grid_and_unobserved_panels() -> None:
    polars = pytest.importorskip("polars")
    frame = polars.DataFrame(
        {
            "region": polars.Series(
                ["South", "North"],
                dtype=polars.Enum(["North", "South", "West"]),
            ),
            "metric": polars.Series(
                ["M1", "M2"],
                dtype=polars.Enum(["M2", "M1"]),
            ),
            "value": [1, 2],
        }
    )
    grid = gs.facets(
        frame,
        row="region",
        col="metric",
        include_unobserved=True,
    )
    row_counts: list[int] = []

    grid.map(lambda panel, axes: row_counts.append(panel.height))

    assert grid.plan.row_levels == ("North", "South", "West")
    assert grid.plan.col_levels == ("M2", "M1")
    assert row_counts == [1, 0, 0, 1, 0, 0]


def test_callback_failure_reports_panel_context_and_preserves_cause() -> None:
    grid = gs.facets(
        {"group": ["A", "B", "C"], "value": [1, 2, 3]},
        col="group",
        wrap=2,
    )

    def fail_on_second(panel: object, axes: Axes) -> None:
        axes.plot([0], [0])
        if axes is grid.axes[1]:
            raise LookupError("broken layer")

    with pytest.raises(gs.FacetCallbackError, match="panel 1") as caught:
        grid.map(fail_on_second)

    assert caught.value.panel_index == 1
    assert caught.value.panel_values == {"group": "B"}
    assert caught.value.completed_panels == 1
    assert isinstance(caught.value.__cause__, LookupError)
    assert grid.map_count == 0
    assert [len(axes.lines) for axes in grid.axes] == [1, 1, 0]


def test_map_rejects_noncallable_without_changing_grid() -> None:
    grid = gs.facets({"group": ["A"]}, col="group")

    with pytest.raises(TypeError, match="callback must be callable"):
        grid.map(None)  # type: ignore[arg-type]

    assert grid.map_count == 0


def test_theme_is_scoped_and_figure_options_are_applied() -> None:
    before = mpl.rcParams.copy()
    specification = gs.theme_spec("minimal", base_size=14)

    grid = gs.facets(
        {"group": ["A"]},
        col="group",
        theme=specification,
        figsize=(6, 4),
        subplot_kw={"facecolor": "#abcdef"},
    )

    assert tuple(grid.figure.get_size_inches()) == pytest.approx((6, 4))
    assert grid.axes[0].get_facecolor() == pytest.approx(mpl.colors.to_rgba("#abcdef"))
    expected_title_size = gs.theme_params(specification)["axes.titlesize"]
    assert grid.axes[0].title.get_fontsize() == pytest.approx(expected_title_size)
    assert grid.figure.get_layout_engine() is not None
    assert grid.as_dict()["theme"] == "minimal"
    assert mpl.rcParams == before


def test_render_inspection_is_bounded_strict_json_and_defensive() -> None:
    grid = gs.facets(
        {"group": ["A", "B", "A"], "value": [1, 2, 3]},
        col="group",
        wrap=2,
    ).map(lambda panel, axes: axes.plot(panel["value"]))  # type: ignore[index]
    payload = grid.as_dict()

    assert payload["kind"] == "facet_grid"
    assert payload["map_count"] == 1
    assert payload["panel_count"] == 2
    assert payload["diagnostics"] == []
    assert isinstance(payload["plan"], Mapping)
    assert "indices" not in json.dumps(payload)
    json.dumps(payload, allow_nan=False)
    assert json.loads(grid.describe()) == payload

    payload["diagnostics"].append("changed")  # type: ignore[union-attr]
    assert grid.as_dict()["diagnostics"] == []


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"figsize": (4,)}, ValueError, "exactly width and height"),
        ({"figsize": (4, 0)}, ValueError, "finite and positive"),
        ({"figsize": "4,3"}, TypeError, "two-item sequence"),
        ({"subplot_kw": []}, TypeError, "must be a mapping"),
        ({"subplot_kw": {1: "value"}}, TypeError, "keys must be strings"),
        ({"theme": 1}, TypeError, "string, ThemeSpec, or None"),
    ],
)
def test_renderer_option_validation_precedes_figure_creation(
    kwargs: dict[str, object], error: type[Exception], message: str
) -> None:
    existing = tuple(plt.get_fignums())

    with pytest.raises(error, match=message):
        gs.facets({"group": ["A"]}, col="group", **kwargs)  # type: ignore[arg-type]

    assert tuple(plt.get_fignums()) == existing


def test_renderer_rejects_missing_variables_and_wrapped_grid_before_creation() -> None:
    existing = tuple(plt.get_fignums())

    with pytest.raises(ValueError, match="at least one"):
        gs.facets({"group": ["A"]})
    with pytest.raises(ValueError, match="wrap requires"):
        gs.facets({"group": ["A"]}, row="group", wrap=2)

    assert tuple(plt.get_fignums()) == existing


def test_mapping_columns_must_all_match_facet_row_count() -> None:
    existing = tuple(plt.get_fignums())

    with pytest.raises(ValueError, match="column 'value' has 1 row"):
        gs.facets(
            {"group": ["A", "B"], "value": [1]},
            col="group",
        )

    assert tuple(plt.get_fignums()) == existing


def test_subplot_failure_closes_the_partially_created_figure() -> None:
    existing = tuple(plt.get_fignums())

    with pytest.raises(ValueError):
        gs.facets(
            {"group": ["A"]},
            col="group",
            subplot_kw={"projection": "not-a-projection"},
        )

    assert tuple(plt.get_fignums()) == existing
