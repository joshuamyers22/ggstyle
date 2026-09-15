"""Tests for immutable theme recipes and safe existing-axes application."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs


def test_theme_spec_is_canonical_immutable_and_defensive() -> None:
    families = ["DejaVu Sans", "sans-serif"]
    specification = gs.theme_spec(
        "theme_gray",
        base_size=11,
        overrides={"font.sans-serif": families},
    )
    families.append("Mutated")

    assert specification.name == "grey"
    assert specification.base_size == 11.0
    assert isinstance(specification.overrides, MappingProxyType)
    assert specification.overrides["font.sans-serif"] == (
        "DejaVu Sans",
        "sans-serif",
    )
    with pytest.raises(TypeError):
        specification.overrides["axes.titlesize"] = 99  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        specification.name = "dark"  # type: ignore[misc]


def test_theme_params_are_read_only_and_do_not_mutate_globals() -> None:
    before = matplotlib.rcParams.copy()
    parameters = gs.theme_params("minimal")

    assert isinstance(parameters, MappingProxyType)
    assert parameters["axes.facecolor"] == "white"
    assert isinstance(parameters["font.family"], tuple)
    with pytest.raises(TypeError):
        parameters["axes.facecolor"] = "black"  # type: ignore[index]
    assert matplotlib.rcParams == before


def test_base_size_scales_the_complete_theme_type_system() -> None:
    base = gs.theme_params("minimal")
    scaled = gs.theme_params(gs.theme_spec("minimal", base_size=15))
    ratio = 1.5
    for key in (
        "font.size",
        "axes.titlesize",
        "axes.labelsize",
        "xtick.labelsize",
        "ytick.labelsize",
        "legend.fontsize",
        "legend.title_fontsize",
    ):
        assert scaled[key] == pytest.approx(base[key] * ratio)


def test_base_family_and_explicit_overrides_have_clear_precedence() -> None:
    specification = gs.theme_spec(
        "minimal",
        base_size=11,
        base_family="DejaVu Serif",
        overrides={"axes.titlesize": 18, "font.family": "monospace"},
    )
    parameters = gs.theme_params(specification)

    assert parameters["font.size"] == 11
    assert parameters["axes.labelsize"] == 11
    assert parameters["axes.titlesize"] == 18
    assert parameters["font.family"] == ("monospace",)


@pytest.mark.parametrize("value", [True, "11", object()])
def test_base_size_must_be_numeric(value) -> None:
    with pytest.raises(TypeError, match="base_size"):
        gs.theme_spec(base_size=value)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_base_size_must_be_finite_and_positive(value: float) -> None:
    with pytest.raises(ValueError, match="base_size"):
        gs.theme_spec(base_size=value)


@pytest.mark.parametrize("value", [1, True, object()])
def test_base_family_must_be_a_string(value) -> None:
    with pytest.raises(TypeError, match="base_family"):
        gs.theme_spec(base_family=value)


@pytest.mark.parametrize("value", ["", "   "])
def test_base_family_must_not_be_empty(value: str) -> None:
    with pytest.raises(ValueError, match="base_family"):
        gs.theme_spec(base_family=value)


def test_theme_overrides_must_be_a_mapping() -> None:
    with pytest.raises(TypeError, match="mapping"):
        gs.theme_spec(overrides=[("axes.titlesize", 12)])


def test_theme_override_names_and_values_are_validated() -> None:
    with pytest.raises(TypeError, match="names must be strings"):
        gs.theme_spec(overrides={1: "white"})
    with pytest.raises(ValueError, match="unknown Matplotlib rcParam"):
        gs.theme_spec(overrides={"axes.unknown": 1})
    with pytest.raises(ValueError, match="not a presentation-style rcParam"):
        gs.theme_spec(overrides={"backend": "Agg"})
    with pytest.raises(ValueError, match=r"axes\.facecolor"):
        gs.theme_spec(overrides={"axes.facecolor": "not-a-color"})


def test_theme_params_rejects_unrecognized_input() -> None:
    with pytest.raises(TypeError, match="string or ThemeSpec"):
        gs.theme_params(1)


def test_parameterized_theme_context_restores_every_rcparam() -> None:
    before = matplotlib.rcParams.copy()
    specification = gs.theme_spec("dark", base_size=13, overrides={"axes.titlesize": 17})
    with gs.theme(specification):
        assert matplotlib.rcParams["axes.facecolor"] == "#7F7F7F"
        assert matplotlib.rcParams["font.size"] == 13
        assert matplotlib.rcParams["axes.titlesize"] == 17
    assert matplotlib.rcParams == before


def test_use_theme_accepts_a_parameterized_specification() -> None:
    before = matplotlib.rcParams.copy()
    try:
        gs.use_theme(gs.theme_spec("minimal", base_size=12))
        assert matplotlib.rcParams["font.size"] == 12
        assert matplotlib.rcParams["axes.facecolor"] == "white"
    finally:
        matplotlib.rcParams.update(before)


def test_finish_applies_safe_theme_properties_without_restyling_data() -> None:
    figure, ax = plt.subplots()
    line = ax.plot([0, 1], [1, 2], color="magenta", linewidth=7, label="Series")[0]
    ax.set_title("Title")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    legend = ax.legend(title="Guide")
    specification = gs.theme_spec(
        "minimal",
        base_size=11,
        base_family="DejaVu Serif",
        overrides={"axes.titlesize": 16, "axes.facecolor": "#FAFAFA"},
    )
    try:
        result = gs.finish(ax, theme=specification)
        figure.canvas.draw()

        assert result.plan.theme is specification
        assert result.plan.managed_changes == ("apply-theme",)
        assert ax.get_facecolor() == pytest.approx((250 / 255, 250 / 255, 250 / 255, 1))
        assert not any(spine.get_visible() for spine in ax.spines.values())
        assert ax.title.get_fontsize() == 16
        assert ax.xaxis.label.get_fontsize() == 11
        assert ax.title.get_fontfamily() == ["DejaVu Serif"]
        assert legend.get_frame_on() is False
        assert legend.get_title().get_fontsize() == pytest.approx(9.9)
        assert all(gridline.get_visible() for gridline in ax.get_xgridlines())
        assert line.get_color() == "magenta"
        assert line.get_linewidth() == 7
        assert line.get_label() == "Series"
        assert line not in result.artists
        assert any("axes.prop_cycle" in message for message in result.diagnostics)
        assert any("lines.linewidth" in message for message in result.diagnostics)
    finally:
        plt.close(figure)


def test_finish_theme_styles_managed_text_without_mutating_global_params() -> None:
    before = matplotlib.rcParams.copy()
    specification = gs.theme_spec(
        "dark",
        base_size=12,
        base_family="DejaVu Serif",
        overrides={"axes.labelcolor": "cyan"},
    )
    figure, ax = plt.subplots()
    try:
        result = gs.finish(
            ax,
            title="Title",
            subtitle="Subtitle",
            caption="Caption",
            theme=specification,
        )

        subtitle, caption = ax.texts
        assert result.plan.theme is specification
        assert subtitle.get_fontsize() == 12
        assert caption.get_fontsize() == pytest.approx(10.8)
        assert subtitle.get_fontfamily() == ["DejaVu Serif"]
        assert caption.get_fontfamily() == ["DejaVu Serif"]
        assert subtitle.get_color() == "cyan"
        assert caption.get_color() == "cyan"
        assert matplotlib.rcParams == before
    finally:
        plt.close(figure)


def test_finish_theme_preserves_the_existing_axes_property_cycle() -> None:
    figure, ax = plt.subplots()
    ax.set_prop_cycle(color=["red", "blue"])
    first = ax.plot([0, 1], [0, 1])[0]
    try:
        gs.finish(ax, theme="minimal")
        second = ax.plot([0, 1], [1, 0])[0]

        assert first.get_color() == "red"
        assert second.get_color() == "blue"
    finally:
        plt.close(figure)


@pytest.mark.parametrize("name", gs.available_themes())
def test_finish_matches_each_theme_core_surface(name: str) -> None:
    parameters = gs.theme_params(name)
    figure, ax = plt.subplots()
    ax.set_title("Title")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    try:
        gs.finish(ax, theme=name)
        figure.canvas.draw()

        assert ax.get_facecolor() == pytest.approx(
            matplotlib.colors.to_rgba(parameters["axes.facecolor"])
        )
        assert ax.get_axisbelow() == parameters["axes.axisbelow"]
        for side, spine in ax.spines.items():
            assert spine.get_visible() is parameters[f"axes.spines.{side}"]
            assert spine.get_edgecolor() == pytest.approx(
                matplotlib.colors.to_rgba(parameters["axes.edgecolor"])
            )
            assert spine.get_linewidth() == parameters["axes.linewidth"]
        assert ax.title.get_fontsize() == parameters["axes.titlesize"]
        if parameters["axes.titlecolor"] != "auto":
            assert matplotlib.colors.to_rgba(ax.title.get_color()) == pytest.approx(
                matplotlib.colors.to_rgba(parameters["axes.titlecolor"])
            )
        assert ax.xaxis.label.get_fontsize() == parameters["axes.labelsize"]
        assert matplotlib.colors.to_rgba(ax.xaxis.label.get_color()) == pytest.approx(
            matplotlib.colors.to_rgba(parameters["axes.labelcolor"])
        )
        expected_grid = parameters["axes.grid"]
        assert all(line.get_visible() is expected_grid for line in ax.get_xgridlines())
    finally:
        plt.close(figure)


def test_finish_theme_dry_run_is_inert_and_reports_the_boundary() -> None:
    figure, ax = plt.subplots()
    before = matplotlib.rcParams.copy()
    facecolor = ax.get_facecolor()
    try:
        plan = gs.finish(ax, theme="dark", dry_run=True)
        assert isinstance(plan.theme, gs.ThemeSpec)
        assert plan.theme.name == "dark"
        assert plan.managed_changes == ("apply-theme",)
        assert any("figure.figsize" in message for message in plan.diagnostics)
        assert ax.get_facecolor() == facecolor
        assert matplotlib.rcParams == before
    finally:
        plt.close(figure)


def test_invalid_theme_request_is_atomic() -> None:
    figure, ax = plt.subplots()
    ax.set_title("Original")
    facecolor = ax.get_facecolor()
    try:
        with pytest.raises(ValueError, match="unknown theme"):
            gs.finish(ax, title="Changed", theme="unknown")
        assert ax.get_title() == "Original"
        assert ax.get_facecolor() == facecolor
    finally:
        plt.close(figure)


def test_theme_application_failure_rolls_back_earlier_properties(monkeypatch) -> None:
    figure, ax = plt.subplots()
    figure_facecolor = figure.get_facecolor()
    axes_facecolor = ax.get_facecolor()
    spine = ax.spines["left"]
    visible = spine.get_visible()
    original_setter = spine.set_visible
    calls = 0

    def fail_once(value) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected theme failure")
        original_setter(value)

    monkeypatch.setattr(spine, "set_visible", fail_once)
    try:
        with pytest.raises(RuntimeError, match="injected theme"):
            gs.finish(ax, theme="dark")
        assert figure.get_facecolor() == figure_facecolor
        assert ax.get_facecolor() == axes_facecolor
        assert spine.get_visible() is visible
    finally:
        plt.close(figure)


def test_later_finish_failure_rolls_back_the_applied_theme(monkeypatch) -> None:
    figure, ax = plt.subplots()
    ax.set_title("Original")
    facecolor = ax.get_facecolor()
    title_size = ax.title.get_fontsize()
    tick_counts = (
        len(ax.xaxis.majorTicks),
        len(ax.xaxis.minorTicks),
        len(ax.yaxis.majorTicks),
        len(ax.yaxis.minorTicks),
    )
    original_setter = ax.yaxis.set_major_formatter
    calls = 0

    def fail_once(formatter) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected label failure")
        original_setter(formatter)

    monkeypatch.setattr(ax.yaxis, "set_major_formatter", fail_once)
    try:
        with pytest.raises(RuntimeError, match="injected label"):
            gs.finish(
                ax,
                title="Changed",
                subtitle="Subtitle",
                theme=gs.theme_spec("dark", base_size=14),
                y=gs.axis(labels=gs.label_number()),
            )
        assert ax.get_facecolor() == facecolor
        assert ax.get_title() == "Original"
        assert ax.title.get_fontsize() == title_size
        assert list(ax.texts) == []
        assert (
            len(ax.xaxis.majorTicks),
            len(ax.xaxis.minorTicks),
            len(ax.yaxis.majorTicks),
            len(ax.yaxis.minorTicks),
        ) == tick_counts
    finally:
        plt.close(figure)


def test_repeated_theme_application_reuses_all_existing_artists() -> None:
    figure, ax = plt.subplots()
    ax.plot([0, 1], [1, 2])
    try:
        before = tuple(ax.get_children())
        first = gs.finish(ax, theme="minimal")
        second = gs.finish(ax, theme="minimal")
        assert tuple(ax.get_children()) == before
        assert first.plan == second.plan
    finally:
        plt.close(figure)
