"""Cross-frame parity tests for the public semantic rendering boundary."""

from __future__ import annotations

from collections.abc import Mapping

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import ggstyle as gs

polars = pytest.importorskip("polars")


def _frame(kind: str, values: Mapping[str, list[object]]) -> object:
    if kind == "pandas":
        return pd.DataFrame(values)
    return polars.DataFrame(values)


def _line_summary(kind: str) -> tuple[object, ...]:
    frame = _frame(
        kind,
        {
            "x": [2, 1, 2, 1],
            "y": [2.0, 1.0, 4.0, 3.0],
            "series": ["A", "A", "B", "B"],
        },
    )
    original = frame.copy() if kind == "pandas" else frame.clone()  # type: ignore[union-attr]
    figure, ax = plt.subplots()
    try:
        result = gs.line(
            frame,
            x="x",
            y="y",
            color="series",
            sort="x",
            ax=ax,
        )
        summary = (
            result.as_dict(),
            tuple(
                tuple(np.asarray(artist.get_xdata()).tolist())
                for artist in result.artists
            ),
            tuple(
                tuple(np.asarray(artist.get_ydata()).tolist())
                for artist in result.artists
            ),
            tuple(artist.get_color() for artist in result.artists),
            gs.guides(ax).as_dict(),
        )
    finally:
        plt.close(figure)
    if kind == "pandas":
        assert_frame_equal(frame, original)  # type: ignore[arg-type]
    else:
        assert frame.equals(original)  # type: ignore[union-attr]
    return summary


def _point_summary(kind: str) -> tuple[object, ...]:
    frame = _frame(
        kind,
        {
            "x": [1, 2, 3],
            "y": [3.0, 2.0, 1.0],
            "score": [0.0, 5.0, 10.0],
            "batch": ["one", "one", "one"],
        },
    )
    figure, ax = plt.subplots()
    try:
        result = gs.points(
            frame,
            x="x",
            y="y",
            color="score",
            group="batch",
            ax=ax,
        )
        return (
            result.as_dict(),
            tuple(
                tuple(map(tuple, artist.get_offsets().tolist()))
                for artist in result.artists
            ),
            tuple(
                tuple(map(tuple, artist.get_facecolors().round(8).tolist()))
                for artist in result.artists
            ),
            gs.guides(ax).as_dict(),
        )
    finally:
        plt.close(figure)


def _ribbon_summary(kind: str) -> tuple[object, ...]:
    frame = _frame(
        kind,
        {
            "x": [1, 2, 3, 4],
            "low": [0.0, 1.0, None, 2.0],
            "high": [1.0, 2.0, None, 3.0],
            "series": ["A", "A", "A", "A"],
        },
    )
    figure, ax = plt.subplots()
    try:
        result = gs.ribbon(
            frame,
            x="x",
            lower="low",
            upper="high",
            color="series",
            missing="break",
            ax=ax,
        )
        return (
            result.as_dict(),
            tuple(len(artist.get_paths()) for artist in result.artists),
            tuple(
                tuple(map(tuple, artist.get_facecolors().round(8).tolist()))
                for artist in result.artists
            ),
            gs.guides(ax).as_dict(),
        )
    finally:
        plt.close(figure)


@pytest.mark.parametrize("summary", [_line_summary, _point_summary, _ribbon_summary])
def test_pandas_and_polars_semantic_results_match(summary) -> None:
    assert summary("pandas") == summary("polars")
