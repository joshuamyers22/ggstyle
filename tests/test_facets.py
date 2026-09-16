"""Pure partition, layout, and inspection behavior for facet planning."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

import ggstyle as gs


def test_wrap_plan_uses_first_seen_order_and_row_major_positions() -> None:
    frame = pd.DataFrame(
        {"group": ["B", "A", "B", "C", "A"], "value": [0, 1, 2, 3, 4]}
    )
    original = frame.copy(deep=True)

    plan = gs.facet_plan(frame, col="group", wrap=2)

    assert plan.layout == "wrap"
    assert plan.shape == (2, 2)
    assert plan.row_levels == ()
    assert plan.col_levels == ("B", "A", "C")
    assert [panel.values for panel in plan.panels] == [
        {"group": "B"},
        {"group": "A"},
        {"group": "C"},
    ]
    assert [(panel.row, panel.column) for panel in plan.panels] == [
        (0, 0),
        (0, 1),
        (1, 0),
    ]
    assert [panel.indices for panel in plan.panels] == [(0, 2), (1, 4), (3,)]
    pd.testing.assert_frame_equal(frame, original)


def test_grid_plan_retains_empty_cross_product_panels() -> None:
    plan = gs.facet_plan(
        {
            "region": ["R2", "R1", "R2"],
            "metric": ["C1", "C2", "C2"],
        },
        row="region",
        col="metric",
        scales="free_y",
    )

    assert plan.layout == "grid"
    assert plan.shape == (2, 2)
    assert plan.scales == "free_y"
    assert [dict(panel.values) for panel in plan.panels] == [
        {"region": "R2", "metric": "C1"},
        {"region": "R2", "metric": "C2"},
        {"region": "R1", "metric": "C1"},
        {"region": "R1", "metric": "C2"},
    ]
    assert [panel.indices for panel in plan.panels] == [(0,), (2,), (), (1,)]
    assert [panel.empty for panel in plan.panels] == [False, False, True, False]


def test_row_only_and_column_only_grid_shapes_are_explicit() -> None:
    row = gs.facet_plan({"group": ["A", "B"]}, row="group")
    column = gs.facet_plan({"group": ["A", "B"]}, col="group")

    assert row.shape == (2, 1)
    assert column.shape == (1, 2)
    assert [(panel.row, panel.column) for panel in row.panels] == [(0, 0), (1, 0)]
    assert [(panel.row, panel.column) for panel in column.panels] == [(0, 0), (0, 1)]


def test_explicit_and_categorical_orders_control_unobserved_panels() -> None:
    frame = pd.DataFrame(
        {
            "priority": pd.Categorical(
                ["low", "high"],
                categories=["high", "medium", "low"],
                ordered=True,
            )
        }
    )

    observed = gs.facet_plan(frame, col="priority")
    declared = gs.facet_plan(frame, col="priority", include_unobserved=True)
    explicit = gs.facet_plan(
        {"priority": [2, 1]},
        col="priority",
        col_order=(1, 3, 2),
        include_unobserved=True,
    )

    assert observed.col_levels == ("high", "low")
    assert declared.col_levels == ("high", "medium", "low")
    assert declared.panels[1].empty
    assert explicit.col_levels == (1, 3, 2)
    assert explicit.panels[1].empty


def test_missing_facet_policy_is_visible_and_counts_rows_once() -> None:
    data = {
        "row": ["R", "R", None, "R"],
        "col": ["A", None, "B", "B"],
    }

    dropped = gs.facet_plan(data, row="row", col="col", missing="drop")
    kept = gs.facet_plan(data, row="row", col="col", missing="keep")

    assert dropped.input_rows == 4
    assert dropped.dropped_rows == 2
    assert dropped.diagnostics == ("dropped 2 row(s) with missing facet values",)
    assert sum(len(panel.indices) for panel in dropped.panels) == 2
    assert kept.row_levels == ("R", None)
    assert kept.col_levels == ("A", "B", None)
    assert kept.dropped_rows == 0
    assert sum(len(panel.indices) for panel in kept.panels) == 4

    with pytest.raises(ValueError, match="missing value at row 1"):
        gs.facet_plan(data, row="row", col="col", missing="raise")


def test_panel_limit_rejects_layout_before_rendering() -> None:
    with pytest.raises(ValueError, match="4 panels, exceeding max_panels=3"):
        gs.facet_plan(
            {"row": ["A", "B"], "col": ["X", "Y"]},
            row="row",
            col="col",
            max_panels=3,
        )


def test_empty_input_requires_retained_explicit_levels() -> None:
    with pytest.raises(ValueError, match="produced no panels"):
        gs.facet_plan({"group": []}, col="group")

    plan = gs.facet_plan(
        {"group": []},
        col="group",
        col_order=("A", "B"),
        include_unobserved=True,
    )
    assert plan.shape == (1, 2)
    assert all(panel.empty for panel in plan.panels)


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({}, ValueError, "at least one"),
        ({"row": "g", "col": "g"}, ValueError, "distinct"),
        ({"row": 1}, TypeError, "column-name"),
        ({"col": "g", "wrap": True}, TypeError, "positive integer"),
        ({"col": "g", "wrap": 0}, ValueError, "positive"),
        ({"row": "g", "wrap": 2}, ValueError, "wrap requires"),
        ({"col": "g", "scales": "shared"}, ValueError, "scales must"),
        ({"col": "g", "missing": "ignore"}, ValueError, "missing must"),
        ({"col": "g", "include_unobserved": 1}, TypeError, "must be a bool"),
        ({"col": "g", "max_panels": 0}, ValueError, "must be positive"),
        ({"col": "g", "row_order": ("A",)}, ValueError, "requires"),
        ({"col": "g", "col_order": "A"}, TypeError, "must be a sequence"),
        ({"col": "g", "col_order": ("A", "A")}, ValueError, "unique"),
        ({"col": "g", "col_order": (None,)}, ValueError, "missing"),
    ],
)
def test_facet_policy_validation_is_explicit(kwargs, error, message) -> None:
    with pytest.raises(error, match=message):
        gs.facet_plan({"g": ["A"]}, **kwargs)


def test_unknown_and_unhashable_levels_are_rejected() -> None:
    with pytest.raises(ValueError, match="absent from"):
        gs.facet_plan(
            {"g": ["A", "B"]},
            col="g",
            col_order=("A",),
        )
    with pytest.raises(TypeError, match="hashable scalar"):
        gs.facet_plan({"g": [["A"]]}, col="g")


def test_facet_plan_inspection_is_strict_bounded_json_and_defensive() -> None:
    plan = gs.facet_plan(
        {"group": ["A", "B", "A"]},
        col="group",
        wrap=2,
        scales="free_x",
    )
    payload = plan.as_dict()

    assert payload == {
        "diagnostics": [],
        "dropped_rows": 0,
        "include_unobserved": False,
        "input_rows": 3,
        "layout": "wrap",
        "levels": {"column": ["A", "B"], "row": []},
        "max_panels": 64,
        "missing": "drop",
        "panel_count": 2,
        "panels": [
            {
                "column": 0,
                "empty": False,
                "index": 0,
                "row": 0,
                "row_count": 2,
                "values": {"group": "A"},
            },
            {
                "column": 1,
                "empty": False,
                "index": 1,
                "row": 0,
                "row_count": 1,
                "values": {"group": "B"},
            },
        ],
        "scales": "free_x",
        "shape": [1, 2],
        "variables": {"column": "group", "row": None},
        "wrap": 2,
    }
    assert all("indices" not in panel for panel in payload["panels"])
    json.dumps(payload, allow_nan=False)
    assert json.loads(plan.describe()) == payload

    payload["diagnostics"].append("changed")
    assert plan.as_dict()["diagnostics"] == []
    with pytest.raises(TypeError):
        plan.panels[0].values["group"] = "changed"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        plan.nrows = 10  # type: ignore[misc]


def test_pandas_and_polars_plans_match() -> None:
    polars = pytest.importorskip("polars")
    values = {
        "row": ["R2", "R1", "R2", "R1"],
        "col": ["C1", "C1", "C2", "C2"],
    }
    pandas_plan = gs.facet_plan(pd.DataFrame(values), row="row", col="col")
    polars_plan = gs.facet_plan(polars.DataFrame(values), row="row", col="col")

    assert pandas_plan.as_dict() == polars_plan.as_dict()
    assert [panel.indices for panel in pandas_plan.panels] == [
        panel.indices for panel in polars_plan.panels
    ]


def test_lazy_polars_and_mismatched_mapping_columns_are_rejected() -> None:
    polars = pytest.importorskip("polars")
    with pytest.raises(TypeError, match="call collect"):
        gs.facet_plan(polars.DataFrame({"g": ["A"]}).lazy(), col="g")
    with pytest.raises(ValueError, match="equal length"):
        gs.facet_plan({"row": ["A"], "col": ["B", "C"]}, row="row", col="col")
