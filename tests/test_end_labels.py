"""Tests for transactional, collision-aware line endpoint labels."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import matplotlib
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import pytest
from matplotlib.text import Annotation

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs


def _labelled_lines(ax):
    first = ax.plot([0, 1, 2], [1.0, 2.0, 3.0], label="Alpha")[0]
    second = ax.plot([0, 1, 2], [1.2, 2.1, 3.02], label="Beta")[0]
    return first, second


def test_end_label_spec_is_immutable() -> None:
    specification = gs.end_labels(collision="none", fallback="raise")
    assert specification.collision == "none"
    assert specification.fallback == "raise"
    with pytest.raises(FrozenInstanceError):
        specification.collision = "avoid"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("keyword", "value", "error"),
    [
        ("collision", 1, TypeError),
        ("collision", "repel", ValueError),
        ("fallback", False, TypeError),
        ("fallback", "ignore", ValueError),
    ],
)
def test_end_label_spec_rejects_unknown_policy(
    keyword: str, value: object, error: type[Exception]
) -> None:
    with pytest.raises(error, match=keyword):
        gs.end_labels(**{keyword: value})


def test_finish_adds_colored_non_overlapping_endpoint_annotations() -> None:
    figure, ax = plt.subplots()
    first, second = _labelled_lines(ax)
    first_data = first.get_xydata().copy()
    second_data = second.get_xydata().copy()
    ax.legend()
    try:
        result = gs.finish(ax, direct_labels=gs.end_labels())
        figure.canvas.draw()

        annotations = tuple(ax.texts)
        assert all(isinstance(item, Annotation) for item in annotations)
        assert [item.get_text() for item in annotations] == ["Alpha", "Beta"]
        assert [item.xy for item in annotations] == [(2.0, 3.0), (2.0, 3.02)]
        assert [item.get_color() for item in annotations] == [
            first.get_color(),
            second.get_color(),
        ]
        assert ax.get_legend() is None
        assert result.plan.direct_label_action == "labels"
        assert result.plan.managed_changes == ("set-direct-labels",)
        assert set(annotations).issubset(result.artists)
        assert figure.get_layout_engine() is not None

        renderer = figure.canvas.get_renderer()
        first_bounds, second_bounds = [
            item.get_window_extent(renderer) for item in annotations
        ]
        assert not first_bounds.overlaps(second_bounds)
        assert max(first_bounds.x1, second_bounds.x1) <= figure.bbox.x1
        np.testing.assert_array_equal(first.get_xydata(), first_data)
        np.testing.assert_array_equal(second.get_xydata(), second_data)
    finally:
        plt.close(figure)


def test_collision_none_preserves_exact_endpoint_positions() -> None:
    figure, ax = plt.subplots()
    _labelled_lines(ax)
    try:
        gs.finish(ax, direct_labels=gs.end_labels(collision="none"))
        assert [item.get_position() for item in ax.texts] == [(6, 0.0), (6, 0.0)]
    finally:
        plt.close(figure)


def test_dry_run_preflights_without_drawing_or_mutating(monkeypatch) -> None:
    figure, ax = plt.subplots()
    _labelled_lines(ax)
    legend = ax.legend()
    view_before = ax.viewLim.get_points().copy()
    stale_before = dict(ax._stale_viewlims)  # type: ignore[attr-defined]
    draw_calls = 0

    def count_draw(*args, **kwargs) -> None:
        nonlocal draw_calls
        draw_calls += 1

    monkeypatch.setattr(figure.canvas, "draw", count_draw)
    try:
        plan = gs.finish(ax, direct_labels=gs.end_labels(), dry_run=True)

        assert plan.direct_label_action == "labels"
        assert plan.layout_action == "enable-constrained"
        assert plan.managed_changes == ("set-direct-labels",)
        assert list(ax.texts) == []
        assert ax.get_legend() is legend
        np.testing.assert_array_equal(ax.viewLim.get_points(), view_before)
        assert ax._stale_viewlims == stale_before  # type: ignore[attr-defined]
        assert figure.get_layout_engine() is None
        assert draw_calls == 0
    finally:
        plt.close(figure)


def test_mixed_artist_plot_falls_back_wholly_to_legend() -> None:
    figure, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], label="Line")
    ax.scatter([0, 1], [1, 0], label="Points")
    try:
        result = gs.finish(ax, direct_labels=gs.end_labels())

        assert result.plan.direct_label_action == "legend"
        assert result.plan.managed_changes == ("fallback-direct-labels-to-legend",)
        assert any("PathCollection" in message for message in result.diagnostics)
        assert list(ax.texts) == []
        legend = ax.get_legend()
        assert legend is not None
        assert [item.get_text() for item in legend.get_texts()] == ["Line", "Points"]
        assert legend in result.artists
    finally:
        plt.close(figure)


def test_unsupported_artist_raise_policy_is_atomic() -> None:
    figure, ax = plt.subplots()
    ax.set_title("Original")
    ax.scatter([0, 1], [1, 0], label="Points")
    try:
        with pytest.raises(ValueError, match="PathCollection"):
            gs.finish(
                ax,
                title="Changed",
                direct_labels=gs.end_labels(fallback="raise"),
            )
        assert ax.get_title() == "Original"
        assert list(ax.texts) == []
        assert figure.get_layout_engine() is None
    finally:
        plt.close(figure)


@pytest.mark.parametrize("kind", ["custom-transform", "outside-view"])
def test_unsafe_line_endpoint_uses_explicit_fallback(kind: str) -> None:
    figure, ax = plt.subplots()
    if kind == "custom-transform":
        ax.plot([0, 1], [0, 1], label="Series", transform=ax.transAxes)
    else:
        ax.plot([0, 1, 2], [0, 1, 2], label="Series")
        ax.set_xlim(0, 1)
    try:
        result = gs.finish(ax, direct_labels=gs.end_labels())
        assert result.plan.direct_label_action == "legend"
        assert ax.get_legend() is not None
        assert list(ax.texts) == []
    finally:
        plt.close(figure)


def test_no_public_labels_raises_without_matplotlib_warning() -> None:
    figure, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    try:
        with pytest.raises(ValueError, match="public label"):
            gs.finish(ax, direct_labels=gs.end_labels())
        assert list(ax.texts) == []
        assert ax.get_legend() is None
    finally:
        plt.close(figure)


def test_overcrowded_labels_fall_back_to_legend() -> None:
    figure, ax = plt.subplots(figsize=(3, 0.5))
    x = [0, 1]
    for index in range(12):
        ax.plot(x, [index, index], label=f"Series {index}")
    try:
        result = gs.finish(ax, direct_labels=gs.end_labels())
        assert result.plan.direct_label_action == "legend"
        assert any("vertical space" in message for message in result.diagnostics)
        assert ax.get_legend() is not None
        assert list(ax.texts) == []
    finally:
        plt.close(figure)


def test_overcrowded_labels_can_fail_during_preflight() -> None:
    figure, ax = plt.subplots(figsize=(3, 0.5))
    for index in range(12):
        ax.plot([0, 1], [index, index], label=f"Series {index}")
    try:
        with pytest.raises(ValueError, match="vertical space"):
            gs.finish(
                ax,
                direct_labels=gs.end_labels(fallback="raise"),
            )
        assert list(ax.texts) == []
        assert figure.get_layout_engine() is None
    finally:
        plt.close(figure)


def test_repeated_finish_reuses_and_updates_endpoint_annotations() -> None:
    figure, ax = plt.subplots()
    first, second = _labelled_lines(ax)
    try:
        gs.finish(ax, direct_labels=gs.end_labels())
        original = tuple(ax.texts)
        first.set_label("Renamed")
        second.set_ydata([1.2, 2.1, 2.8])
        ax.relim()
        ax.autoscale_view()

        result = gs.finish(ax, direct_labels=gs.end_labels())
        assert tuple(ax.texts) == original
        assert [item.get_text() for item in ax.texts] == ["Renamed", "Beta"]
        assert [item.xy for item in ax.texts] == [(2.0, 3.0), (2.0, 2.8)]
        assert set(ax.texts).issubset(result.artists)
    finally:
        plt.close(figure)


def test_removed_line_and_externally_removed_annotation_are_reconciled() -> None:
    figure, ax = plt.subplots()
    first, second = _labelled_lines(ax)
    try:
        gs.finish(ax, direct_labels=gs.end_labels())
        first_annotation, removed_annotation = ax.texts
        removed_annotation.remove()
        first.remove()

        gs.finish(ax, direct_labels=gs.end_labels())
        assert len(ax.texts) == 1
        assert ax.texts[0] is not first_annotation
        assert ax.texts[0].get_text() == "Beta"
        assert ax.texts[0] is not removed_annotation
        assert second in ax.lines
    finally:
        plt.close(figure)


def test_false_removes_managed_endpoint_labels() -> None:
    figure, ax = plt.subplots()
    _labelled_lines(ax)
    try:
        gs.finish(ax, direct_labels=gs.end_labels())
        result = gs.finish(ax, direct_labels=False)
        assert list(ax.texts) == []
        assert result.plan.direct_label_action == "remove"
        assert result.plan.managed_changes == ("remove-direct-labels",)
    finally:
        plt.close(figure)


def test_theme_controls_endpoint_typography_but_not_series_color() -> None:
    figure, ax = plt.subplots()
    line = ax.plot([0, 1], [0, 1], label="Series", color="magenta")[0]
    specification = gs.theme_spec(
        "minimal", base_size=12, base_family="DejaVu Serif"
    )
    try:
        gs.finish(
            ax,
            theme=specification,
            direct_labels=gs.end_labels(),
        )
        annotation = ax.texts[0]
        assert annotation.get_fontsize() == pytest.approx(10.8)
        assert tuple(annotation.get_fontfamily()) == ("DejaVu Serif",)
        assert annotation.get_color() == "magenta"
        assert line.get_color() == "magenta"
    finally:
        plt.close(figure)


def test_theme_styles_a_new_fallback_legend() -> None:
    figure, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], label="Line")
    ax.scatter([0, 1], [1, 0], label="Points")
    try:
        gs.finish(
            ax,
            theme=gs.theme_spec("minimal", base_size=12),
            direct_labels=gs.end_labels(),
        )
        legend = ax.get_legend()
        assert legend is not None
        assert not legend.get_frame_on()
        assert all(item.get_fontsize() == pytest.approx(10.8) for item in legend.texts)
    finally:
        plt.close(figure)


def test_annotation_failure_rolls_back_labels_title_legend_and_layout(monkeypatch) -> None:
    figure, ax = plt.subplots()
    _labelled_lines(ax)
    ax.set_title("Original")
    legend = ax.legend()
    original_annotate = ax.annotate
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected annotation failure")
        return original_annotate(*args, **kwargs)

    monkeypatch.setattr(ax, "annotate", fail_second)
    try:
        with pytest.raises(RuntimeError, match="injected annotation"):
            gs.finish(
                ax,
                title="Changed",
                direct_labels=gs.end_labels(),
            )
        assert ax.get_title() == "Original"
        assert list(ax.texts) == []
        assert ax.get_legend() is legend
        assert figure.get_layout_engine() is None
    finally:
        plt.close(figure)


def test_fallback_failure_restores_existing_endpoint_labels(monkeypatch) -> None:
    figure, ax = plt.subplots()
    _labelled_lines(ax)
    try:
        gs.finish(ax, direct_labels=gs.end_labels())
        annotations = tuple(ax.texts)
        ax.scatter([0, 1], [1, 0], label="Points")

        def fail_legend(*args, **kwargs):
            raise RuntimeError("injected legend failure")

        monkeypatch.setattr(ax, "legend", fail_legend)
        with pytest.raises(RuntimeError, match="injected legend"):
            gs.finish(ax, direct_labels=gs.end_labels())
        assert tuple(ax.texts) == annotations
        assert [item.get_text() for item in ax.texts] == ["Alpha", "Beta"]
    finally:
        plt.close(figure)


def test_collapsed_date_line_endpoint_uses_registered_scale() -> None:
    dates = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-08"])
    figure, ax = plt.subplots()
    line = ax.plot(dates, [1.0, 2.0, 1.5], label="Series")[0]
    handle = gs.dates(ax).collapse()
    try:
        gs.finish(ax, direct_labels=gs.end_labels())
        assert len(ax.texts) == 1
        assert ax.texts[0].xy == (mdates.date2num(dates[-1]), 1.5)
        np.testing.assert_allclose(
            line.get_xdata(orig=False),
            mdates.date2num(dates),
        )
        assert handle.loc(dates[-1]) == mdates.date2num(dates[-1])
    finally:
        plt.close(figure)


def test_finish_rejects_invalid_direct_label_request() -> None:
    figure, ax = plt.subplots()
    try:
        with pytest.raises(TypeError, match="EndLabelSpec"):
            gs.finish(ax, direct_labels=True)
    finally:
        plt.close(figure)
