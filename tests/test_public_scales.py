"""Public configuration vocabulary for mapped aesthetic scales."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs
from ggstyle._semantic_registry import semantic_registry


def test_discrete_scale_defensively_copies_reusable_policy() -> None:
    values = ["#112233", "#445566"]
    order = ["B", "A"]
    scale = gs.DiscreteScale(
        values=values,  # type: ignore[arg-type]
        order=order,  # type: ignore[arg-type]
        include_unobserved=True,
        missing="drop",
        name="Series",
    )
    values.append("#778899")
    order.append("C")

    assert scale.values == ("#112233", "#445566")
    assert scale.order == ("B", "A")
    assert scale.name == "Series"
    with pytest.raises(FrozenInstanceError):
        scale.name = "Changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"values": ()}, ValueError, "must not be empty"),
        ({"values": ("solid", "solid")}, ValueError, "must be unique"),
        ({"values": (1,)}, TypeError, "must be strings"),
        ({"values": tuple(str(index) for index in range(9))}, ValueError, "at most 8"),
        ({"order": ("A", "A")}, ValueError, "unique levels"),
        ({"order": (None,)}, ValueError, "missing values"),
        ({"include_unobserved": 1}, TypeError, "must be a bool"),
        ({"missing": "ignore"}, ValueError, "missing must be"),
        ({"missing": "drop", "missing_value": "solid"}, ValueError, "requires"),
        ({"missing_value": 1}, TypeError, "must be a string"),
        ({"name": ""}, ValueError, "must not be empty"),
        ({"name": 1}, TypeError, "non-empty string"),
    ],
)
def test_discrete_scale_rejects_invalid_context_free_policy(
    arguments, error, message
) -> None:
    with pytest.raises(error, match=message):
        gs.DiscreteScale(**arguments)


def test_continuous_scale_reuses_public_palette_policy() -> None:
    selected = gs.palette(
        "diverging",
        out_of_bounds="color",
        under_color="#001122",
        over_color="#EEDDCC",
    )
    scale = gs.ContinuousScale(
        palette=selected,
        limits=(-1, 1),
        missing="drop",
        infinite="color",
        name="Change",
    )

    assert scale.palette is selected
    assert scale.limits == (-1.0, 1.0)
    assert scale.name == "Change"
    with pytest.raises(FrozenInstanceError):
        scale.limits = (0, 1)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"palette": gs.palette("qualitative")}, "sequential or diverging"),
        ({"limits": (1, 0)}, "lower < upper"),
        ({"missing": "ignore"}, "missing must be"),
        ({"infinite": "ignore"}, "infinite must be"),
        ({"name": ""}, "must not be empty"),
    ],
)
def test_continuous_scale_rejects_invalid_policy(arguments, message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        gs.ContinuousScale(**arguments)


def test_numeric_color_can_be_explicitly_discrete() -> None:
    figure, ax = plt.subplots()
    try:
        frame = pd.DataFrame({"x": [1, 2], "y": [3, 4], "code": [2, 1]})
        result = gs.line(
            frame,
            x="x",
            y="y",
            color="code",
            color_scale=gs.DiscreteScale(
                order=(1, 2), values=("#112233", "#445566")
            ),
            ax=ax,
        )

        assert len(result.artists) == 2
        assert result.scales["color"].kind == "discrete"
        assert result.scales["color"].as_dict()["levels"] == [1, 2]
        assert [artist.get_color() for artist in result.artists] == [
            "#445566",
            "#112233",
        ]
    finally:
        plt.close(figure)


def test_explicit_discrete_missing_drop_reports_and_omits_rows() -> None:
    figure, ax = plt.subplots()
    try:
        frame = pd.DataFrame(
            {"x": [1, 2, 3], "y": [4, 5, 6], "kind": ["A", None, "A"]}
        )
        result = gs.line(
            frame,
            x="x",
            y="y",
            color="kind",
            color_scale=gs.DiscreteScale(missing="drop"),
            ax=ax,
        )
        assert len(result.artists) == 1
        assert result.artists[0].get_xdata().tolist() == [1, 3]
        assert result.diagnostics[-1] == (
            "dropped 1 row(s) under mapped-aesthetic missing policy"
        )
    finally:
        plt.close(figure)


def test_explicit_linestyle_values_and_unobserved_order() -> None:
    figure, ax = plt.subplots()
    try:
        frame = pd.DataFrame({"x": [1, 2], "y": [3, 4], "kind": ["B", "A"]})
        result = gs.line(
            frame,
            x="x",
            y="y",
            linestyle="kind",
            linestyle_scale=gs.DiscreteScale(
                values=("dotted", "dashed", "solid"),
                order=("A", "B", "C"),
                include_unobserved=True,
            ),
            ax=ax,
        )
        assert result.scales["linestyle"].as_dict()["levels"] == ["A", "B", "C"]
        assert [artist.get_linestyle() for artist in result.artists] == ["--", ":"]
    finally:
        plt.close(figure)


def test_explicit_continuous_limits_and_palette_are_applied() -> None:
    figure, ax = plt.subplots()
    try:
        frame = pd.DataFrame(
            {
                "x": [1, 2, 1, 2],
                "y": [2, 3, 4, 5],
                "group": ["low", "low", "high", "high"],
                "score": [0.0, 0.0, 1.0, 1.0],
            }
        )
        result = gs.line(
            frame,
            x="x",
            y="y",
            group="group",
            color="score",
            color_scale=gs.ContinuousScale(
                palette=gs.palette("diverging"), limits=(-1, 1), name="Score"
            ),
            ax=ax,
        )
        description = result.scales["color"].as_dict()
        assert description["domain"] == [-1.0, 1.0]
        assert description["palette"] == "diverging"
        assert description["name"] == "Score"
        assert result.artists[0].get_color() == "#F7F7F7"
    finally:
        plt.close(figure)


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"color_scale": gs.DiscreteScale()}, ValueError, "requires a mapped color"),
        ({"color": "kind", "color_scale": object()}, TypeError, "color_scale must be"),
        (
            {"linestyle_scale": gs.DiscreteScale()},
            ValueError,
            "requires a mapped linestyle",
        ),
        (
            {"linestyle": "kind", "linestyle_scale": object()},
            TypeError,
            "linestyle_scale must be",
        ),
    ],
)
def test_scale_configuration_requires_its_mapping(arguments, error, message) -> None:
    figure, ax = plt.subplots()
    try:
        values = {
            "data": {"x": [1], "y": [2], "kind": ["A"]},
            "x": "x",
            "y": "y",
            "ax": ax,
        }
        values.update(arguments)
        with pytest.raises(error, match=message):
            gs.line(**values)
        assert list(ax.lines) == []
    finally:
        plt.close(figure)


def test_aesthetic_specific_values_are_validated_when_applied() -> None:
    figure, ax = plt.subplots()
    try:
        frame = {"x": [1], "y": [2], "kind": ["A"]}
        with pytest.raises(ValueError, match="linestyle values"):
            gs.line(
                frame,
                x="x",
                y="y",
                linestyle="kind",
                linestyle_scale=gs.DiscreteScale(values=("#112233",)),
                ax=ax,
            )
        with pytest.raises(ValueError, match="discrete color"):
            gs.line(
                frame,
                x="x",
                y="y",
                color="kind",
                color_scale=gs.DiscreteScale(values=("dotted",)),
                ax=ax,
            )
        assert list(ax.lines) == []
    finally:
        plt.close(figure)


def test_conflicting_scale_configuration_fails_without_new_layer() -> None:
    figure, ax = plt.subplots()
    try:
        frame = {"x": [1], "y": [2], "kind": ["A"]}
        original = gs.line(frame, x="x", y="y", color="kind", ax=ax)
        revision = semantic_registry(ax).revision
        with pytest.raises(ValueError, match="conflicting color scales"):
            gs.line(
                frame,
                x="x",
                y="y",
                color="kind",
                color_scale=gs.DiscreteScale(values=("#112233",)),
                ax=ax,
            )
        assert tuple(ax.lines) == original.artists
        assert semantic_registry(ax).revision == revision
    finally:
        plt.close(figure)


def test_public_scale_policy_module_does_not_import_matplotlib() -> None:
    source = Path("src/ggstyle/scales.py").read_text()
    assert "import matplotlib" not in source


def test_public_scale_types_are_exported() -> None:
    assert "DiscreteScale" in gs.__all__
    assert "ContinuousScale" in gs.__all__
