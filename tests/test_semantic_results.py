"""Tests for the common semantic-result inspection boundary."""

from __future__ import annotations

import json

import matplotlib.pyplot as plt

import ggstyle as gs


def test_geometry_results_share_bounded_strict_json_inspection() -> None:
    figure, ax = plt.subplots()
    try:
        line = gs.line(
            {"x": [0, 1, 0, 1], "y": [1, 2, 2, 3], "series": ["A", "A", "B", "B"]},
            x="x",
            y="y",
            color="series",
            ax=ax,
        )
        points = gs.points(
            {"x": [0, 1], "y": [1, 2], "score": [0.0, 10.0]},
            x="x",
            y="y",
            color="score",
            ax=ax,
        )
        ribbon = gs.ribbon(
            {"x": [0, 1], "low": [0.5, 1.5], "high": [1.5, 2.5]},
            x="x",
            lower="low",
            upper="high",
            ax=ax,
        )

        for result, kind, artist_type in (
            (line, "line", "Line2D"),
            (points, "points", "PathCollection"),
            (ribbon, "ribbon", "PolyCollection"),
        ):
            assert isinstance(result, gs.RenderedResult)
            payload = result.as_dict()
            assert payload["kind"] == kind
            assert payload["layer_id"] == result.layer_id
            assert payload["artist_count"] == len(result.artists)
            assert payload["artist_types"] == {artist_type: len(result.artists)}
            assert payload["diagnostics"] == list(result.diagnostics)
            assert "axes" not in payload
            assert "artists" not in payload
            json.dumps(payload, allow_nan=False)
            assert json.loads(result.describe()) == payload
    finally:
        plt.close(figure)


def test_result_payloads_are_fresh_and_scale_keys_are_sorted() -> None:
    figure, ax = plt.subplots()
    try:
        result = gs.line(
            {
                "x": [0, 1, 0, 1],
                "y": [1, 2, 2, 3],
                "series": ["A", "A", "B", "B"],
                "phase": ["actual", "actual", "forecast", "forecast"],
            },
            x="x",
            y="y",
            color="series",
            linestyle="phase",
            ax=ax,
        )
        first = result.as_dict()
        assert list(first["scales"]) == ["color", "linestyle"]  # type: ignore[arg-type]
        first["diagnostics"] = ["changed"]
        second = result.as_dict()
        assert second["diagnostics"] == list(result.diagnostics)
    finally:
        plt.close(figure)


def test_guide_result_inspection_reports_counts_and_titles() -> None:
    figure, ax = plt.subplots()
    try:
        gs.line(
            {"x": [0, 1, 0, 1], "y": [1, 2, 2, 3], "series": ["A", "A", "B", "B"]},
            x="x",
            y="y",
            color="series",
            ax=ax,
        )
        gs.points(
            {"x": [0, 1], "y": [1, 2], "score": [0.0, 10.0]},
            x="x",
            y="y",
            color="score",
            ax=ax,
        )
        result = gs.guides(ax)

        assert isinstance(result, gs.RenderedResult)
        assert result.as_dict() == {
            "colorbar_count": 1,
            "colorbar_titles": ["score"],
            "diagnostics": [],
            "kind": "guides",
            "legend_count": 1,
            "legend_titles": ["series"],
        }
        json.dumps(result.as_dict(), allow_nan=False)
        assert json.loads(result.describe()) == result.as_dict()
    finally:
        plt.close(figure)
