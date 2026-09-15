"""Tests for transactional plot labels and layout-aware managed text."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import matplotlib
import numpy as np
import pytest
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs


def test_axis_spec_is_immutable_and_axes_independent() -> None:
    specification = gs.axis(title="Share", labels=gs.label_percent(decimals=1))
    assert specification.title == "Share"
    assert isinstance(specification.labels, gs.NumericLabeller)
    with pytest.raises(FrozenInstanceError):
        specification.title = "Changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"title": 1}, "axis title"),
        ({"labels": lambda value: value}, "NumericLabeller"),
    ],
)
def test_axis_spec_rejects_ambiguous_values(arguments, message: str) -> None:
    with pytest.raises(TypeError, match=message):
        gs.axis(**arguments)


def test_finish_applies_coherent_labels_and_returns_native_artists() -> None:
    figure, ax = plt.subplots()
    try:
        result = gs.finish(
            ax,
            title="Revenue",
            subtitle="Trailing twelve months",
            caption="Source: annual report",
            x=gs.axis(title="Date"),
            y=gs.axis(title="USD", labels=gs.label_currency("$", decimals=0)),
        )

        assert result.axes is ax
        assert isinstance(result, gs.FinishResult)
        assert ax.get_title() == "Revenue"
        assert ax.get_xlabel() == "Date"
        assert ax.get_ylabel() == "USD"
        assert isinstance(ax.yaxis.get_major_formatter(), FuncFormatter)
        assert ax.yaxis.get_major_formatter()(1250) == "$1,250"
        assert {artist.get_text() for artist in result.artists} == {
            "Revenue",
            "Trailing twelve months",
            "Source: annual report",
            "Date",
            "USD",
        }
        assert figure.get_layout_engine() is not None
    finally:
        plt.close(figure)


def test_dry_run_reports_the_same_operations_without_mutation(monkeypatch) -> None:
    figure, ax = plt.subplots()
    draw_calls = 0

    def count_draw(*args, **kwargs) -> None:
        nonlocal draw_calls
        draw_calls += 1

    monkeypatch.setattr(figure.canvas, "draw", count_draw)
    try:
        before = matplotlib.rcParams.copy()
        plan = gs.finish(
            ax,
            title="Revenue",
            subtitle="TTM",
            caption="Source",
            x=gs.axis(title="Date"),
            dry_run=True,
        )

        assert isinstance(plan, gs.FinishPlan)
        assert plan.managed_changes == (
            "set-title",
            "set-x-title",
            "set-subtitle",
            "set-caption",
        )
        assert plan.layout_action == "enable-constrained"
        assert ax.get_title() == ""
        assert ax.get_xlabel() == ""
        assert list(ax.texts) == []
        assert figure.get_layout_engine() is None
        assert draw_calls == 0
        assert matplotlib.rcParams == before
    finally:
        plt.close(figure)


def test_axis_only_finishing_does_not_enable_a_layout_engine() -> None:
    figure, ax = plt.subplots()
    try:
        gs.finish(ax, x=gs.axis(title="Date"), y=gs.axis(labels=gs.label_number()))
        assert figure.get_layout_engine() is None
    finally:
        plt.close(figure)


def test_existing_layout_engine_is_preserved() -> None:
    figure, ax = plt.subplots(layout="tight")
    try:
        engine = figure.get_layout_engine()
        result = gs.finish(ax, title="Title", subtitle="Subtitle", caption="Caption")
        assert figure.get_layout_engine() is engine
        assert result.plan.layout_action == "unchanged"
    finally:
        plt.close(figure)


def test_repeated_finish_reuses_managed_text_artists() -> None:
    figure, ax = plt.subplots()
    try:
        first = gs.finish(ax, title="First", subtitle="One", caption="A")
        subtitle, caption = ax.texts
        second = gs.finish(ax, title="Second", subtitle="Two", caption="B")

        assert list(ax.texts) == [subtitle, caption]
        assert subtitle.get_text() == "Two"
        assert caption.get_text() == "B"
        assert len(first.artists) == len(second.artists) == 3
    finally:
        plt.close(figure)


def test_omitted_values_leave_existing_state_unchanged() -> None:
    figure, ax = plt.subplots()
    try:
        gs.finish(ax, title="Title", subtitle="Subtitle", caption="Caption")
        subtitle, caption = ax.texts
        gs.finish(ax, x=gs.axis(title="Date"))

        assert ax.get_title() == "Title"
        assert subtitle.get_text() == "Subtitle"
        assert caption.get_text() == "Caption"
        assert ax.get_xlabel() == "Date"
    finally:
        plt.close(figure)


def test_false_removes_managed_outer_text_and_restores_title_position() -> None:
    figure, ax = plt.subplots()
    try:
        base_transform = ax.title.get_transform()
        gs.finish(ax, title="Title", subtitle="Subtitle", caption="Caption")
        assert ax.title.get_transform() is not base_transform

        result = gs.finish(ax, subtitle=False, caption=False)
        assert list(ax.texts) == []
        assert ax.title.get_transform() is base_transform
        assert result.plan.managed_changes == ("remove-subtitle", "remove-caption")
    finally:
        plt.close(figure)


def test_externally_removed_managed_text_is_replaced_safely() -> None:
    figure, ax = plt.subplots()
    try:
        gs.finish(ax, title="Title", subtitle="First", caption="Source")
        removed = ax.texts[0]
        removed.remove()

        gs.finish(ax, subtitle="Replacement")
        assert len(ax.texts) == 2
        assert removed not in ax.texts
        assert {text.get_text() for text in ax.texts} == {"Replacement", "Source"}
    finally:
        plt.close(figure)


def test_omitting_an_externally_removed_subtitle_restores_the_title() -> None:
    figure, ax = plt.subplots()
    try:
        base_transform = ax.title.get_transform()
        gs.finish(ax, title="Title", subtitle="Subtitle")
        ax.texts[0].remove()

        gs.finish(ax, caption="Source")
        assert ax.title.get_transform() is base_transform
        assert [text.get_text() for text in ax.texts] == ["Source"]
    finally:
        plt.close(figure)


@pytest.mark.parametrize(
    ("keyword", "value", "message"),
    [
        ("ax", object(), "matplotlib Axes"),
        ("title", False, "title"),
        ("subtitle", True, "subtitle"),
        ("caption", 1, "caption"),
        ("x", "Date", "AxisSpec"),
        ("y", "USD", "AxisSpec"),
        ("dry_run", 1, "bool"),
    ],
)
def test_finish_validates_every_public_input(keyword: str, value, message: str) -> None:
    figure, ax = plt.subplots()
    arguments = {"ax": ax, keyword: value}
    if keyword == "ax":
        arguments = {"ax": value}
    try:
        with pytest.raises(TypeError, match=message):
            gs.finish(**arguments)
    finally:
        plt.close(figure)


def test_invalid_request_is_atomic() -> None:
    figure, ax = plt.subplots()
    try:
        ax.set_title("Original")
        with pytest.raises(TypeError, match="AxisSpec"):
            gs.finish(ax, title="Changed", subtitle="Added", x="invalid")
        assert ax.get_title() == "Original"
        assert list(ax.texts) == []
        assert figure.get_layout_engine() is None
    finally:
        plt.close(figure)


def test_commit_failure_rolls_back_axes_artists_formatters_and_layout(monkeypatch) -> None:
    figure, ax = plt.subplots()
    ax.set_title("Original")
    ax.set_xlabel("Old x")
    formatter = ax.yaxis.get_major_formatter()

    original_setter = ax.yaxis.set_major_formatter
    calls = 0

    def fail_once(replacement) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected formatter failure")
        original_setter(replacement)

    monkeypatch.setattr(ax.yaxis, "set_major_formatter", fail_once)
    try:
        with pytest.raises(RuntimeError, match="injected formatter"):
            gs.finish(
                ax,
                title="Changed",
                subtitle="Added",
                caption="Source",
                x=gs.axis(title="New x"),
                y=gs.axis(labels=gs.label_number()),
            )

        assert ax.get_title() == "Original"
        assert ax.get_xlabel() == "Old x"
        assert ax.yaxis.get_major_formatter() is formatter
        assert list(ax.texts) == []
        assert figure.get_layout_engine() is None
    finally:
        plt.close(figure)


def test_failure_after_managed_removal_reattaches_previous_artists(monkeypatch) -> None:
    figure, ax = plt.subplots()
    try:
        gs.finish(ax, title="Title", subtitle="Subtitle", caption="Caption")
        subtitle, caption = ax.texts
        title_transform = ax.title.get_transform()
        original_setter = ax.yaxis.set_major_formatter
        calls = 0

        def fail_once(formatter) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("injected formatter failure")
            original_setter(formatter)

        monkeypatch.setattr(ax.yaxis, "set_major_formatter", fail_once)
        with pytest.raises(RuntimeError, match="injected"):
            gs.finish(
                ax,
                subtitle=False,
                caption=False,
                y=gs.axis(labels=gs.label_number()),
            )

        assert list(ax.texts) == [subtitle, caption]
        assert subtitle.get_text() == "Subtitle"
        assert caption.get_text() == "Caption"
        assert ax.title.get_transform() is title_transform
    finally:
        plt.close(figure)


def test_finish_does_not_change_data_artists_or_global_configuration() -> None:
    figure, ax = plt.subplots()
    line = ax.plot([0, 1, 2], [2, 1, 3], label="series")[0]
    x_before = np.asarray(line.get_xdata()).copy()
    y_before = np.asarray(line.get_ydata()).copy()
    transform_before = line.get_transform()
    rc_before = matplotlib.rcParams.copy()
    try:
        gs.finish(ax, title="Title", subtitle="Subtitle", caption="Caption")
        assert np.array_equal(line.get_xdata(), x_before)
        assert np.array_equal(line.get_ydata(), y_before)
        assert line.get_transform() is transform_before
        assert matplotlib.rcParams == rc_before
    finally:
        plt.close(figure)


@pytest.mark.parametrize("location", ["left", "center", "right"])
def test_subtitle_tracks_every_matplotlib_title_location(location: str) -> None:
    with matplotlib.rc_context({"axes.titlelocation": location}):
        figure, ax = plt.subplots()
        try:
            gs.finish(ax, title="Title", subtitle="Subtitle")
            subtitle = ax.texts[0]
            assert subtitle.get_horizontalalignment() == location
            assert (
                subtitle.get_position()[0]
                == {"left": 0, "center": 0.5, "right": 1}[location]
            )
        finally:
            plt.close(figure)


def test_subtitle_adopts_an_existing_nondefault_title_without_restyling_it() -> None:
    figure, ax = plt.subplots()
    try:
        title = ax.set_title("Existing", loc="right", color="purple", fontsize=17)
        gs.finish(ax, subtitle="Subtitle")
        assert title.get_text() == "Existing"
        assert title.get_color() == "purple"
        assert title.get_fontsize() == 17
        assert ax.texts[0].get_horizontalalignment() == "right"
    finally:
        plt.close(figure)


def test_constrained_layout_keeps_multiline_labels_inside_figure() -> None:
    figure, axes = plt.subplots(2, 1, figsize=(6, 5))
    try:
        for index, ax in enumerate(axes):
            ax.plot([0, 1], [index, index + 1])
            gs.finish(
                ax,
                title=f"Panel {index + 1}",
                subtitle="First subtitle line\nSecond subtitle line",
                caption=f"Source for panel {index + 1}",
                x=gs.axis(title="Date"),
                y=gs.axis(title="Value"),
            )

        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        figure_box = figure.bbox
        for ax in axes:
            title_box = ax.title.get_window_extent(renderer)
            subtitle_box, caption_box = (
                text.get_window_extent(renderer) for text in ax.texts
            )
            assert figure_box.contains(*subtitle_box.get_points()[0])
            assert figure_box.contains(*subtitle_box.get_points()[1])
            assert figure_box.contains(*caption_box.get_points()[0])
            assert figure_box.contains(*caption_box.get_points()[1])
            assert subtitle_box.y1 < title_box.y0
            assert caption_box.y1 < ax.xaxis.label.get_window_extent(renderer).y0
    finally:
        plt.close(figure)


def test_finish_accepts_axes_subclasses() -> None:
    figure, ax = plt.subplots()
    try:
        assert isinstance(ax, Axes)
        assert gs.finish(ax).axes is ax
    finally:
        plt.close(figure)
