"""Static assertions for the public fluent API shipped with ``py.typed``."""

from collections.abc import Mapping
from pathlib import Path

import pandas as pd
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection, PolyCollection
from matplotlib.colorbar import Colorbar
from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
from typing_extensions import assert_type

import ggstyle as gs


def check_date_axis_types(ax: Axes, events: pd.DataFrame) -> None:
    """Assert that public operations retain useful concrete result types."""
    handle = assert_type(gs.dates(ax), gs.DateAxis)
    assert_type(handle.ticks("monthly"), gs.DateAxis)
    assert_type(handle.fmt("month-year"), gs.DateAxis)
    assert_type(handle.rotate(30), gs.DateAxis)
    assert_type(handle.tz("UTC"), gs.DateAxis)
    assert_type(handle.zoom("2024", "2025"), gs.DateAxis)
    assert_type(handle.pad(left="1D"), gs.DateAxis)
    assert_type(handle.collapse(), gs.DateAxis)
    assert_type(handle.expand(), gs.DateAxis)
    assert_type(handle.vline("2024-01-01"), gs.DateAxis)
    assert_type(handle.span("2024-01-01", "2024-01-02"), gs.DateAxis)
    assert_type(handle.spans(events), gs.DateAxis)
    assert_type(handle.grid("monthly"), gs.DateAxis)
    assert_type(handle.clear_annotations(), gs.DateAxis)
    assert_type(handle.refresh(), gs.DateAxis)
    summary = assert_type(handle.summary(), gs.AxisSummary)
    assert_type(summary.as_dict(), dict[str, object])
    assert_type(summary.describe(), str)
    assert_type(handle.observations, pd.DatetimeIndex)
    assert_type(gs.sync_dates([ax]), list[gs.DateAxis])


def check_theme_types() -> None:
    """Assert concrete return types for public theme discovery helpers."""
    assert_type(gs.available_themes(), list[str])
    specification = assert_type(
        gs.theme_spec("minimal", base_size=11), gs.ThemeSpec
    )
    assert_type(gs.theme_params(specification), Mapping[str, object])


def check_numeric_labeller_types() -> None:
    """Assert that numeric factories and their adapter retain useful types."""
    percent = assert_type(gs.label_percent(decimals=1), gs.NumericLabeller)
    assert_type(percent(0.125), str)
    assert_type(gs.label_currency("$"), gs.NumericLabeller)
    assert_type(gs.label_number(), gs.NumericLabeller)
    assert_type(gs.label_si(unit="B"), gs.NumericLabeller)
    assert_type(gs.as_formatter(percent), FuncFormatter)


def check_palette_types() -> None:
    """Assert immutable palette construction and lookup result types."""
    selected = assert_type(gs.palette("sequential"), gs.Palette)
    assert_type(selected.colors, tuple[str, ...])
    assert_type(selected.sample(5), tuple[str, ...])
    assert_type(selected.at(0.5), str)
    assert_type(gs.available_palettes(), list[str])


def check_semantic_scale_types() -> None:
    """Assert reusable semantic-scale configuration remains concrete."""
    discrete = assert_type(
        gs.DiscreteScale(order=("A", "B"), missing="drop"),
        gs.DiscreteScale,
    )
    continuous = assert_type(
        gs.ContinuousScale(palette=gs.palette("sequential"), limits=(0, 1)),
        gs.ContinuousScale,
    )
    assert_type(discrete.values, tuple[str, ...] | None)
    assert_type(continuous.palette, gs.Palette)


def check_finish_types(ax: Axes, dry_run: bool) -> None:
    """Assert concrete types for axis specs, plans, and committed results."""
    specification = assert_type(
        gs.axis(title="Share", labels=gs.label_percent()), gs.AxisSpec
    )
    report_theme = gs.theme_spec("minimal", base_size=11)
    endpoints = assert_type(gs.end_labels(), gs.EndLabelSpec)
    result = assert_type(
        gs.finish(
            ax,
            title="Report",
            theme=report_theme,
            direct_labels=endpoints,
            y=specification,
        ),
        gs.FinishResult,
    )
    assert_type(result.axes, Axes)
    assert_type(result.artists, tuple[Artist, ...])
    assert_type(result.plan, gs.FinishPlan)
    plan = assert_type(gs.finish(ax, dry_run=True), gs.FinishPlan)
    assert_type(plan.as_dict(), dict[str, object])
    assert_type(plan.describe(), str)
    assert_type(gs.finish(ax, dry_run=dry_run), gs.FinishPlan | gs.FinishResult)


def check_facet_plan_types(frame: pd.DataFrame) -> None:
    """Assert pure facet planning retains useful immutable result types."""
    plan = assert_type(
        gs.facet_plan(frame, col="series", wrap=3, scales="free_y"),
        gs.FacetPlan,
    )
    assert_type(plan.shape, tuple[int, int])
    assert_type(plan.panels, tuple[gs.FacetPanel, ...])
    panel = plan.panels[0]
    assert_type(panel.values, Mapping[str, object])
    assert_type(panel.indices, tuple[int, ...])
    assert_type(panel.empty, bool)
    assert_type(panel.as_dict(), dict[str, object])
    assert_type(plan.as_dict(), dict[str, object])
    assert_type(plan.describe(), str)


def check_facet_grid_types(frame: pd.DataFrame) -> None:
    """Assert callback wrap rendering retains native Matplotlib object types."""
    grid = assert_type(
        gs.facets(frame, col="series", wrap=3, scales="free_y"),
        gs.FacetGrid,
    )

    def draw(panel: pd.DataFrame, axes: Axes) -> object:
        return axes.plot(panel["date"], panel["value"])

    assert_type(grid.figure, Figure)
    assert_type(grid.axes, tuple[Axes, ...])
    assert_type(grid.plan, gs.FacetPlan)
    assert_type(grid.diagnostics, tuple[str, ...])
    assert_type(grid.map_count, int)
    assert_type(grid.map(draw), gs.FacetGrid)
    assert_type(grid.as_dict(), dict[str, object])
    assert_type(grid.describe(), str)
    assert_type(
        gs.facets(frame, row="region", col="series", wrap=None),
        gs.FacetGrid,
    )


def check_line_types(ax: Axes, frame: pd.DataFrame) -> None:
    """Assert concrete line results and the trained-scale inspection boundary."""
    result = assert_type(
        gs.line(
            frame,
            x="date",
            y="value",
            color="series",
            color_scale=gs.DiscreteScale(),
            ax=ax,
        ),
        gs.LineResult,
    )
    assert_type(result.axes, Axes)
    assert_type(result.artists, tuple[Line2D, ...])
    assert_type(result.as_dict(), dict[str, object])
    assert_type(result.describe(), str)
    common: gs.RenderedResult = result
    assert_type(common.diagnostics, tuple[str, ...])
    scale = assert_type(result.scales["color"], gs.AestheticScale)
    assert_type(scale.as_dict(), dict[str, object])
    assert_type(scale.describe(), str)


def check_point_and_ribbon_types(ax: Axes, frame: pd.DataFrame) -> None:
    """Assert concrete native collection result types."""
    points = assert_type(
        gs.points(frame, x="date", y="value", color="series", ax=ax),
        gs.PointResult,
    )
    assert_type(points.axes, Axes)
    assert_type(points.artists, tuple[PathCollection, ...])
    assert_type(points.as_dict(), dict[str, object])
    assert_type(points.describe(), str)
    ribbon = assert_type(
        gs.ribbon(frame, x="date", lower="low", upper="high", ax=ax),
        gs.RibbonResult,
    )
    assert_type(ribbon.axes, Axes)
    assert_type(ribbon.artists, tuple[PolyCollection, ...])
    assert_type(ribbon.as_dict(), dict[str, object])
    assert_type(ribbon.describe(), str)


def check_guide_types(ax: Axes) -> None:
    """Assert native legend and colorbar result types."""
    result = assert_type(gs.guides(ax), gs.GuideResult)
    assert_type(result.axes, Axes)
    assert_type(result.legends, tuple[Legend, ...])
    assert_type(result.colorbars, tuple[Colorbar, ...])
    assert_type(result.diagnostics, tuple[str, ...])
    assert_type(result.as_dict(), dict[str, object])
    assert_type(result.describe(), str)


def check_save_types(figure: Figure, destination: Path) -> None:
    """Assert that saving requires an explicit figure and returns its path."""
    assert_type(
        gs.save(figure, destination, width=7, height=4),
        Path,
    )
