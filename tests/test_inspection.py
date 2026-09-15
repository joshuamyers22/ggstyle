"""Tests for JSON-safe date-axis and finishing inspection."""

from __future__ import annotations

import json
from dataclasses import dataclass

import matplotlib
import pandas as pd
from cycler import cycler

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs


@dataclass(frozen=True)
class _CustomLabeller(gs.NumericLabeller):
    threshold: float = float("nan")
    callback: object = len

    def __call__(self, value: float, /) -> str:
        return str(value)


def test_axis_summary_is_strict_json_and_uses_iso_timestamps() -> None:
    dates = pd.DatetimeIndex(["2024-01-02", "2024-01-05"])
    figure, ax = plt.subplots()
    ax.plot(dates, [1.0, 2.0])
    try:
        summary = gs.dates(ax).ticks("daily").summary()
        payload = summary.as_dict()

        assert payload == {
            "mode": "show",
            "observations": 2,
            "start": "2024-01-02T00:00:00",
            "end": "2024-01-05T00:00:00",
            "inferred_frequency": "irregular (median 3 days 00:00:00)",
            "major_cadence": "day[start]",
            "minor_cadence": "6x hour[start]",
            "timezone": None,
            "missing_values": 0,
        }
        assert json.loads(summary.describe()) == payload
        json.dumps(payload, allow_nan=False)
    finally:
        plt.close(figure)


def test_finish_plan_serializes_complete_nested_policy_without_mutation() -> None:
    figure, ax = plt.subplots()
    ax.plot([0, 1], [0.1, 0.2], label="Share")
    try:
        plan = gs.finish(
            ax,
            title="Performance",
            subtitle="Preliminary",
            caption=False,
            theme=gs.theme_spec(
                "minimal",
                base_size=11,
                base_family="DejaVu Sans",
                overrides={"axes.spines.top": False},
            ),
            direct_labels=gs.end_labels(fallback="raise"),
            x=gs.axis(title="Period"),
            y=gs.axis(title="Share", labels=gs.label_percent(decimals=1)),
            dry_run=True,
        )
        payload = plan.as_dict()

        assert payload["title"] == "Performance"
        assert payload["subtitle"] == "Preliminary"
        assert payload["caption"] is False
        assert payload["direct_labels"] == {
            "collision": "avoid",
            "fallback": "raise",
        }
        assert payload["direct_label_action"] == "labels"
        assert payload["layout_action"] == "enable-constrained"
        assert payload["x"] == {"title": "Period", "labels": None}
        assert payload["theme"] == {
            "name": "minimal",
            "base_size": 11.0,
            "base_family": "DejaVu Sans",
            "overrides": {"axes.spines.top": False},
        }
        y_axis = payload["y"]
        assert isinstance(y_axis, dict)
        labels = y_axis["labels"]
        assert isinstance(labels, dict)
        assert labels["type"] == "number"
        assert labels["parameters"]["multiplier"] == 100.0

        serialized = plan.describe()
        assert json.loads(serialized) == payload
        json.dumps(payload, allow_nan=False)
        assert ax.get_title() == ""
        assert ax.get_ylabel() == ""
        assert list(ax.texts) == []
        assert figure.get_layout_engine() is None
    finally:
        plt.close(figure)


def test_inspection_payloads_are_defensive() -> None:
    figure, ax = plt.subplots()
    try:
        plan = gs.finish(ax, title="Original", dry_run=True)
        first = plan.as_dict()
        first["title"] = "Changed"
        first["managed_changes"].append("external")

        second = plan.as_dict()
        assert second["title"] == "Original"
        assert second["managed_changes"] == ["set-title"]
    finally:
        plt.close(figure)


def test_inspection_normalizes_supported_containers_and_unknown_objects() -> None:
    figure, ax = plt.subplots()
    try:
        plan = gs.finish(
            ax,
            theme=gs.theme_spec(
                "minimal",
                overrides={"axes.prop_cycle": cycler(color=["red", "blue"])},
            ),
            y=gs.axis(labels=_CustomLabeller()),
            dry_run=True,
        )
        payload = plan.as_dict()

        theme = payload["theme"]
        assert isinstance(theme, dict)
        assert theme["overrides"] == {
            "axes.prop_cycle": {"color": ["red", "blue"]}
        }
        y_axis = payload["y"]
        assert isinstance(y_axis, dict)
        labels = y_axis["labels"]
        assert isinstance(labels, dict)
        assert labels["parameters"] == {
            "threshold": "nan",
            "callback": "<builtins.builtin_function_or_method>",
        }
        json.dumps(payload, allow_nan=False)
    finally:
        plt.close(figure)
