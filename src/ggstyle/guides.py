"""Automatic native legends and colorbars for semantic mappings."""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import Any, Protocol, cast
from weakref import WeakKeyDictionary

from matplotlib.axes import Axes
from matplotlib.cm import ScalarMappable
from matplotlib.colorbar import Colorbar
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.legend import Legend
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from ._semantic_registry import (
    MappingRequest,
    ScaleEntry,
    SemanticPlan,
    semantic_registry,
)
from ._semantic_scales import (
    TrainedContinuousScale,
    TrainedDiscreteScale,
    _is_missing,
)
from .results import _describe_result, _guide_payload

__all__ = ["GuideResult", "guides"]


class _GuideSource(Protocol):
    @property
    def revision(self) -> int: ...

    @property
    def contributions(self) -> tuple[MappingRequest, ...]: ...

    @property
    def scales(self) -> tuple[ScaleEntry, ...]: ...


@dataclass(frozen=True)
class GuideResult:
    """
    Return native guides managed by :func:`guides`.

    Parameters
    ----------
    axes : matplotlib.axes.Axes
        The exact caller-owned semantic axes.
    legends : tuple of matplotlib.legend.Legend
        One native legend for each distinct compatible discrete guide.
    colorbars : tuple of matplotlib.colorbar.Colorbar
        One native colorbar for each continuous color scale.
    diagnostics : tuple of str
        Deterministic merge and coexistence diagnostics.
    """

    axes: Axes
    legends: tuple[Legend, ...]
    colorbars: tuple[Colorbar, ...]
    diagnostics: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "legends", tuple(self.legends))
        object.__setattr__(self, "colorbars", tuple(self.colorbars))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    def as_dict(self) -> dict[str, object]:
        """
        Return a bounded, deterministic, JSON-compatible summary.

        Returns
        -------
        dict of str to object
            Fresh containers describing native guide counts, titles, and
            diagnostics. Live Matplotlib objects are excluded.
        """

        return _guide_payload(
            legends=self.legends,
            colorbars=self.colorbars,
            diagnostics=self.diagnostics,
        )

    def describe(self) -> str:
        """
        Return the result summary as deterministic strict JSON.

        Returns
        -------
        str
            Strict JSON containing the same values as :meth:`as_dict`.
        """

        return _describe_result(self.as_dict())


@dataclass(frozen=True)
class _DiscreteGuide:
    variable: str
    title: str
    levels: tuple[object, ...]
    labels: tuple[str, ...]
    colors: tuple[str, ...] | None
    linestyles: tuple[str, ...] | None
    geometries: frozenset[str]


@dataclass(frozen=True)
class _ContinuousGuide:
    variable: str
    title: str
    scale: TrainedContinuousScale


@dataclass(frozen=True)
class _GuidePlan:
    revision: int
    discrete: tuple[_DiscreteGuide, ...]
    continuous: tuple[_ContinuousGuide, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class _GuideState:
    revision: int
    legends: tuple[weakref.ReferenceType[Legend], ...]
    colorbars: tuple[weakref.ReferenceType[Colorbar], ...]
    diagnostics: tuple[str, ...]


@dataclass
class _GuideUpdate:
    ax: Axes
    plan: _GuidePlan
    previous: _GuideState | None
    legends: tuple[Legend, ...]
    colorbars: tuple[Colorbar, ...]
    unchanged: GuideResult | None = None
    committed: bool = False

    def commit(self) -> GuideResult:
        """Publish prepared guides after the surrounding transaction is safe."""

        if self.unchanged is not None:
            self.committed = True
            return self.unchanged
        if self.previous is not None:
            _remove(self.ax, *_attached_parts(self.ax, self.previous))
        state = _GuideState(
            self.plan.revision,
            tuple(weakref.ref(legend) for legend in self.legends),
            tuple(weakref.ref(colorbar) for colorbar in self.colorbars),
            self.plan.diagnostics,
        )
        _GUIDE_STATES[self.ax] = state
        self.committed = True
        return GuideResult(
            self.ax,
            self.legends,
            self.colorbars,
            self.plan.diagnostics,
        )

    def rollback(self) -> None:
        """Remove uncommitted replacement guides, retaining the prior set."""

        if not self.committed and self.unchanged is None:
            _remove(self.ax, self.legends, self.colorbars)


_GUIDE_STATES: WeakKeyDictionary[Axes, _GuideState] = WeakKeyDictionary()


def _title(entry: ScaleEntry) -> str:
    return entry.scale.spec.name or entry.key.variable


def _geometry(layer_id: str) -> str:
    return layer_id.split("-", 1)[0]


def _geometries(
    contributions: tuple[MappingRequest, ...], entry: ScaleEntry
) -> frozenset[str]:
    return frozenset(
        _geometry(item.layer_id) for item in contributions if item.key == entry.key
    )


def _has_mapped_missing(
    contributions: tuple[MappingRequest, ...], entry: ScaleEntry
) -> bool:
    if entry.scale.spec.missing != "map":
        return False
    return any(
        _is_missing(value)
        for request in contributions
        if request.key == entry.key
        for value in request.values
    )


def _level_labels(levels: tuple[object, ...], *, missing: bool) -> tuple[str, ...]:
    labels = [str(level) for level in levels]
    if len(set(labels)) != len(labels):
        labels = [repr(level) for level in levels]
    if len(set(labels)) != len(labels):
        labels = [f"{type(level).__name__}: {level!r}" for level in levels]
    if len(set(labels)) != len(labels):  # pragma: no cover - pathological repr collision
        raise ValueError("discrete guide levels do not have unique display labels")
    if missing:
        missing_label = "(missing)"
        if missing_label in labels:
            labels = [repr(level) for level in levels]
        if missing_label in labels:
            raise ValueError(
                "discrete guide level labels conflict with the missing-value label"
            )
        labels.append(missing_label)
    return tuple(labels)


def _discrete_parts(
    source: _GuideSource,
) -> tuple[tuple[_DiscreteGuide, ...], tuple[str, ...]]:
    candidates: list[_DiscreteGuide] = []
    for entry in source.scales:
        trained = entry.scale
        if not isinstance(trained, TrainedDiscreteScale):
            continue
        include_missing = _has_mapped_missing(source.contributions, entry)
        levels = trained.levels + ((None,) if include_missing else ())
        if not levels:
            continue
        outputs = trained.outputs + (
            (cast(str, trained.spec.missing_value),) if include_missing else ()
        )
        candidates.append(
            _DiscreteGuide(
                entry.key.variable,
                _title(entry),
                levels,
                _level_labels(trained.levels, missing=include_missing),
                outputs if entry.key.aesthetic == "color" else None,
                outputs if entry.key.aesthetic == "linestyle" else None,
                _geometries(source.contributions, entry),
            )
        )

    merged: list[_DiscreteGuide] = []
    diagnostics: list[str] = []
    for candidate in candidates:
        match = next(
            (
                index
                for index, existing in enumerate(merged)
                if (existing.variable == candidate.variable
                and existing.title == candidate.title
                and existing.levels == candidate.levels
                and existing.labels == candidate.labels
                and existing.colors is None
                and candidate.colors is not None)
                or (existing.variable == candidate.variable
                and existing.title == candidate.title
                and existing.levels == candidate.levels
                and existing.labels == candidate.labels
                and existing.linestyles is None
                and candidate.linestyles is not None)
            ),
            None,
        )
        if match is None:
            merged.append(candidate)
            continue
        existing = merged[match]
        if (existing.colors is None) == (candidate.colors is None):
            merged.append(candidate)
            continue
        merged[match] = _DiscreteGuide(
            existing.variable,
            existing.title,
            existing.levels,
            existing.labels,
            existing.colors if existing.colors is not None else candidate.colors,
            existing.linestyles
            if existing.linestyles is not None
            else candidate.linestyles,
            existing.geometries | candidate.geometries,
        )
        diagnostics.append(
            f"merged color and linestyle guides for {candidate.variable!r}"
        )
    return tuple(merged), tuple(diagnostics)


def _plan(source: _GuideSource, ax: Axes) -> _GuidePlan:
    discrete, merge_diagnostics = _discrete_parts(source)
    continuous = tuple(
        _ContinuousGuide(entry.key.variable, _title(entry), entry.scale)
        for entry in source.scales
        if isinstance(entry.scale, TrainedContinuousScale)
    )
    if len(discrete) > 4:
        raise ValueError(
            "automatic guides support at most 4 distinct legends on one axes; "
            "reduce mapped variables or construct custom Matplotlib legends"
        )
    if len(continuous) > 4:
        raise ValueError(
            "automatic guides support at most 4 distinct colorbars on one axes; "
            "reduce mapped variables or construct custom Matplotlib colorbars"
        )
    diagnostics = list(merge_diagnostics)
    if ax.get_legend() is not None and discrete:
        diagnostics.append("preserved existing caller-owned axes legend")
    return _GuidePlan(source.revision, discrete, continuous, tuple(diagnostics))


def _legend_handle(guide: _DiscreteGuide, index: int) -> Line2D | Patch:
    color = None if guide.colors is None else guide.colors[index]
    linestyle = "None" if guide.linestyles is None else guide.linestyles[index]
    if guide.geometries == {"ribbon"} and guide.linestyles is None:
        return Patch(facecolor=color, edgecolor="none")
    marker = "o" if "points" in guide.geometries else "None"
    line_color = color or "#333333"
    return Line2D(
        [],
        [],
        color=line_color,
        linestyle=cast(
            Any,
            linestyle
            if guide.linestyles is not None
            else ("-" if "line" in guide.geometries else "None"),
        ),
        marker=marker,
        markerfacecolor=line_color,
        markeredgecolor=line_color,
    )


def _add_legend(ax: Axes, guide: _DiscreteGuide, index: int) -> Legend:
    handles = [_legend_handle(guide, level) for level in range(len(guide.labels))]
    legend = Legend(
        ax,
        handles,
        guide.labels,
        title=guide.title,
        loc="upper right",
        bbox_to_anchor=(1.0, 1.0 - 0.22 * index),
        borderaxespad=0.5,
    )
    legend.set_in_layout(True)
    ax.add_artist(legend)
    return legend


def _colormap(scale: TrainedContinuousScale) -> LinearSegmentedColormap:
    palette = scale.spec.palette
    samples = tuple(palette.at(value / 256) for value in range(257))
    cmap = LinearSegmentedColormap.from_list(
        f"ggstyle-{palette.name}", samples, N=256
    )
    extremes: dict[str, str] = {"bad": palette.missing_color}
    if palette.out_of_bounds == "color":
        extremes["under"] = cast(str, palette.under_color)
        extremes["over"] = cast(str, palette.over_color)
    return cast(LinearSegmentedColormap, cmap.with_extremes(**extremes))


def _normalization(scale: TrainedContinuousScale) -> tuple[Normalize, list[float] | None]:
    lower, upper = scale.domain
    if lower != upper:
        normalization = Normalize(
            lower,
            upper,
            clip=scale.spec.palette.out_of_bounds == "clip",
        )
        return normalization, None
    delta = abs(lower) * 0.01 or 0.5
    return Normalize(lower - delta, upper + delta), [lower]


def _add_colorbar(
    ax: Axes, guide: _ContinuousGuide, index: int, count: int
) -> Colorbar:
    norm, ticks = _normalization(guide.scale)
    mappable = ScalarMappable(norm=norm, cmap=_colormap(guide.scale))
    gap = 0.05
    height = (0.9 - gap * (count - 1)) / max(count, 1)
    bottom = 0.95 - (index + 1) * height - index * gap
    color_axes = ax.inset_axes((1.04, bottom, 0.04, height))
    color_axes.set_in_layout(True)
    extend = "both" if guide.scale.spec.palette.out_of_bounds == "color" else "neither"
    try:
        colorbar = ax.figure.colorbar(
            mappable,
            cax=color_axes,
            extend=extend,
            ticks=ticks,
        )
    except BaseException:
        color_axes.remove()
        raise
    colorbar.set_label(guide.title)
    return colorbar


def _remove(
    ax: Axes, legends: tuple[Legend, ...], colorbars: tuple[Colorbar, ...]
) -> None:
    for legend in legends:
        if legend.axes is not None:
            legend.remove()
    for colorbar in colorbars:
        if colorbar.ax in ax.child_axes:
            colorbar.remove()


def _attached_parts(
    ax: Axes, state: _GuideState
) -> tuple[tuple[Legend, ...], tuple[Colorbar, ...]]:
    legends = tuple(
        legend
        for reference in state.legends
        if (legend := reference()) is not None and legend.axes is ax
    )
    colorbars = tuple(
        colorbar
        for reference in state.colorbars
        if (colorbar := reference()) is not None
        and colorbar.ax in ax.child_axes
    )
    return legends, colorbars


def _current(ax: Axes, state: _GuideState) -> GuideResult | None:
    legends = tuple(reference() for reference in state.legends)
    colorbars = tuple(reference() for reference in state.colorbars)
    if any(legend is None or legend.axes is not ax for legend in legends):
        return None
    if any(
        colorbar is None or colorbar.ax not in ax.child_axes
        for colorbar in colorbars
    ):
        return None
    return GuideResult(
        ax,
        cast(tuple[Legend, ...], legends),
        cast(tuple[Colorbar, ...], colorbars),
        state.diagnostics,
    )


def _prepare_update(ax: Axes, plan: _GuidePlan) -> _GuideUpdate:
    previous = _GUIDE_STATES.get(ax)
    if previous is not None and previous.revision == plan.revision:
        current = _current(ax, previous)
        if current is not None:
            return _GuideUpdate(ax, plan, previous, (), (), unchanged=current)

    legends: list[Legend] = []
    colorbars: list[Colorbar] = []
    try:
        legends.extend(
            _add_legend(ax, item, index) for index, item in enumerate(plan.discrete)
        )
        colorbars.extend(
            _add_colorbar(ax, item, index, len(plan.continuous))
            for index, item in enumerate(plan.continuous)
        )
    except BaseException:
        _remove(ax, tuple(legends), tuple(colorbars))
        raise
    return _GuideUpdate(
        ax,
        plan,
        previous,
        tuple(legends),
        tuple(colorbars),
    )


def _apply(ax: Axes, plan: _GuidePlan) -> GuideResult:
    return _prepare_update(ax, plan).commit()


def _prepare_guide_refresh(
    ax: Axes, plan: SemanticPlan | None
) -> _GuideUpdate | None:
    """Prepare active replacement guides without removing the committed set."""

    if plan is None or ax not in _GUIDE_STATES:
        return None
    return _prepare_update(ax, _plan(plan, ax))


def guides(ax: Axes, *, enabled: bool = True) -> GuideResult:
    """
    Build native legends and colorbars from an axes' trained mappings.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Existing caller-owned axes whose complete semantic registry supplies the guides.
    enabled : bool, default True
        Build or refresh managed guides. False removes managed guides and disables their
        automatic refresh without touching caller-owned guides.

    Returns
    -------
    GuideResult
        The original axes, native managed legends and colorbars, and diagnostics.

    Notes
    -----
    Guide entries, titles, ordering, and colors/styles are derived from the complete
    semantic registry. Compatible color and linestyle mappings for the same variable are
    merged. Distinct variables or titles remain distinct guides. Caller-owned native
    legends and colorbars are preserved.

    Once called, the managed guides refresh automatically when later :func:`line`,
    :func:`points`, or :func:`ribbon` calls retrain the axes. Pass ``enabled=False`` to
    remove managed guides and disable that refresh behavior.
    """

    if not isinstance(ax, Axes):
        raise TypeError(f"ax must be a matplotlib Axes, got {ax!r}")
    if not isinstance(enabled, bool):
        raise TypeError(f"enabled must be bool, got {enabled!r}")
    if not enabled:
        previous = _GUIDE_STATES.pop(ax, None)
        if previous is not None:
            _remove(ax, *_attached_parts(ax, previous))
        return GuideResult(ax, (), (), ())
    registry = semantic_registry(ax)
    return _apply(ax, _plan(registry.snapshot(), ax))


def _guide_state_count() -> int:
    """Return live axes guide-state count for lifecycle tests."""

    return len(_GUIDE_STATES)
