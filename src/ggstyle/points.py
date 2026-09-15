"""Transactional tidy-data point rendering on an existing Matplotlib axes."""

from __future__ import annotations

import math
import weakref
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import Any, Literal, cast

from matplotlib.axes import Axes
from matplotlib.collections import PathCollection
from matplotlib.markers import MarkerStyle

from ._semantic_artists import (
    ArtistBinding,
    ArtistChange,
    apply_artist_changes,
    capture_axes,
    date_handle,
    prepare_artist_changes,
    renderer_state,
    restore_axes,
    rollback_artist_changes,
    scales_for,
)
from ._semantic_registry import MappingRequest, SemanticPlan, semantic_registry
from ._semantic_scales import ContinuousScaleSpec, DiscreteScaleSpec
from .guides import _GuideUpdate, _prepare_guide_refresh
from .line import (
    GroupMissingPolicy,
    _assignments,
    _color_scale,
    _extract_columns,
    _group_key,
    _is_missing,
    _optional_text,
    _text,
)
from .scales import AestheticScale, ContinuousScale, DiscreteScale

__all__ = ["PointResult", "points"]

PointMissingPolicy = Literal["drop", "raise"]


@dataclass(frozen=True)
class PointResult:
    """Return native point collections and mappings created by :func:`points`.

    Parameters
    ----------
    axes : matplotlib.axes.Axes
        The exact caller-owned axes passed to :func:`points`.
    artists : tuple of matplotlib.collections.PathCollection
        Ordinary Matplotlib scatter collections, one per resolved group.
    scales : mapping of str to AestheticScale
        Read-only trained scales used by this layer.
    diagnostics : tuple of str
        Non-fatal accessibility or dropped-row diagnostics.
    layer_id : str
        Stable identifier for this committed semantic layer.
    """

    axes: Axes
    artists: tuple[PathCollection, ...]
    scales: Mapping[str, AestheticScale]
    diagnostics: tuple[str, ...]
    layer_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "artists", tuple(self.artists))
        object.__setattr__(self, "scales", MappingProxyType(dict(self.scales)))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True)
class _PointStyle:
    marker: MarkerStyle
    size: float
    properties: Mapping[str, object]


@dataclass(frozen=True)
class _PreparedPoints:
    indices: tuple[int, ...]
    x: tuple[object, ...]
    y: tuple[object, ...]
    colors: str | tuple[str, ...] | None


def _positive_size(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"point size must be a positive real number, got {value!r}")
    resolved = float(value)
    if not math.isfinite(resolved) or resolved <= 0:
        raise ValueError(f"point size must be finite and positive, got {value!r}")
    return resolved


def _point_style(
    value: object, *, color: str | None
) -> _PointStyle:
    if value is None:
        properties: dict[str, object] = {}
    elif isinstance(value, Mapping):
        properties = dict(value)
    else:
        raise TypeError(f"style must be a mapping or None, got {value!r}")
    if not all(isinstance(key, str) for key in properties):
        raise TypeError("style keys must be strings")
    if color is not None and {
        "c",
        "color",
        "facecolor",
        "facecolors",
        "fc",
    } & properties.keys():
        raise ValueError("color cannot be both mapped and fixed in style")
    forbidden = {"cmap", "norm", "vmin", "vmax"} & properties.keys()
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise ValueError(
            f"point style cannot contain scale properties ({names}); use color_scale="
        )
    marker_value = properties.pop("marker", "o")
    if "size" in properties and "s" in properties:
        raise ValueError("point style cannot contain both 'size' and 's'")
    size = _positive_size(properties.pop("size", properties.pop("s", 36.0)))
    try:
        marker = MarkerStyle(cast(Any, marker_value))
        path = marker.get_path().transformed(marker.get_transform())
        validation = dict(properties)
        if "c" in validation:
            validation["color"] = validation.pop("c")
        PathCollection((path,), sizes=(size,), **cast(Any, validation))
    except (AttributeError, TypeError, ValueError) as error:
        raise type(error)(f"invalid fixed point style: {error}") from error
    return _PointStyle(marker, size, MappingProxyType(properties))


def _ordered_groups(
    indices: list[int],
    grouping: list[tuple[str, tuple[object, ...]]],
) -> tuple[tuple[int, ...], ...]:
    if not indices:
        return ()
    if not grouping:
        return (tuple(indices),)
    groups: dict[tuple[object, ...], list[int]] = {}
    for index in indices:
        key = tuple(
            _group_key(values[index], variable=name) for name, values in grouping
        )
        groups.setdefault(key, []).append(index)
    return tuple(tuple(group) for group in groups.values())


def _prepare_points(
    *,
    values: Mapping[str, tuple[object, ...]],
    x: str,
    y: str,
    color: str | None,
    group: str | None,
    missing: PointMissingPolicy,
    group_missing: GroupMissingPolicy,
    plan: SemanticPlan | None,
    layer_id: str,
    color_spec: DiscreteScaleSpec | ContinuousScaleSpec | None,
) -> tuple[tuple[_PreparedPoints, ...], int, int, int]:
    assignments = {} if plan is None else _assignments(plan, layer_id)
    keep = [True] * len(values[x])
    mapped_dropped = 0
    if color is not None:
        for index, output in enumerate(assignments["color"].outputs):
            if output is None:
                keep[index] = False
                mapped_dropped += 1

    coordinate_dropped = 0
    for index, (x_value, y_value) in enumerate(zip(values[x], values[y], strict=True)):
        if not (_is_missing(x_value) or _is_missing(y_value)):
            continue
        if missing == "raise":
            raise ValueError(f"point coordinates contain a missing value at row {index}")
        if keep[index]:
            keep[index] = False
            coordinate_dropped += 1

    group_dropped = 0
    if group is not None:
        for index, value in enumerate(values[group]):
            if not _is_missing(value):
                continue
            if group_missing == "raise":
                raise ValueError(f"grouping column {group!r} contains missing values")
            if group_missing == "drop" and keep[index]:
                keep[index] = False
                group_dropped += 1

    grouping: list[tuple[str, tuple[object, ...]]] = []
    if group is not None:
        grouping.append((group, values[group]))
    if color is not None and isinstance(color_spec, DiscreteScaleSpec):
        grouping.append((color, values[color]))
    groups = _ordered_groups(
        [index for index, retained in enumerate(keep) if retained], grouping
    )

    prepared: list[_PreparedPoints] = []
    for indices in groups:
        colors: str | tuple[str, ...] | None = None
        if color is not None:
            outputs = tuple(assignments["color"].outputs[index] for index in indices)
            assert all(output is not None for output in outputs)
            resolved = cast(tuple[str, ...], outputs)
            colors = resolved[0] if isinstance(color_spec, DiscreteScaleSpec) else resolved
        prepared.append(
            _PreparedPoints(
                indices,
                tuple(values[x][index] for index in indices),
                tuple(values[y][index] for index in indices),
                colors,
            )
        )
    return tuple(prepared), mapped_dropped, coordinate_dropped, group_dropped


def points(
    data: object,
    *,
    x: str,
    y: str,
    ax: Axes,
    color: str | None = None,
    group: str | None = None,
    color_scale: DiscreteScale | ContinuousScale | None = None,
    style: Mapping[str, object] | None = None,
    missing: PointMissingPolicy = "drop",
    group_missing: GroupMissingPolicy = "drop",
) -> PointResult:
    """Draw mapped points from named tidy-data columns on an existing axes.

    Parameters
    ----------
    data : dataframe-like
        Column-bearing dataframe-like or mapping-like data. Input is never mutated.
    x, y : str
        Required coordinate column names.
    ax : matplotlib.axes.Axes
        Existing caller-owned target axes.
    color : str or None, optional
        Column mapped to point face color.
    group : str or None, optional
        Column partitioning points into separate native collections.
    color_scale : DiscreteScale, ContinuousScale, or None, optional
        Explicit color policy. Omit for dtype-based inference.
    style : mapping or None, optional
        Fixed scatter style. ``marker`` and scalar ``size``/``s`` are supported with
        ordinary collection properties such as alpha, edgecolor, and linewidth.
    missing : {"drop", "raise"}, default "drop"
        Policy for rows with missing x or y coordinates.
    group_missing : {"drop", "keep", "raise"}, default "drop"
        Policy for rows with a missing explicit group value.

    Returns
    -------
    PointResult
        Original axes, ordinary ``PathCollection`` artists, trained scales,
        diagnostics, and the committed layer identifier.

    Notes
    -----
    Discrete color implies separate collections by level. Continuous color maps each
    retained point independently. No aggregation, jitter, or statistical transform is
    performed. Existing semantic artists and date handles update transactionally.
    """

    if not isinstance(ax, Axes):
        raise TypeError(f"ax must be a matplotlib Axes, got {ax!r}")
    x = _text("x", x)
    y = _text("y", y)
    color = _optional_text("color", color)
    group = _optional_text("group", group)
    if color_scale is not None and not isinstance(
        color_scale, (DiscreteScale, ContinuousScale)
    ):
        raise TypeError(
            "color_scale must be a DiscreteScale, ContinuousScale, or None"
        )
    if color is None and color_scale is not None:
        raise ValueError("color_scale requires a mapped color column")
    if missing not in ("drop", "raise"):
        raise ValueError(f"missing must be 'drop' or 'raise', got {missing!r}")
    if group_missing not in ("drop", "keep", "raise"):
        raise ValueError(
            "group_missing must be 'drop', 'keep', or 'raise', "
            f"got {group_missing!r}"
        )
    fixed = _point_style(style, color=color)

    names = [x, y]
    names.extend(name for name in (color, group) if name is not None)
    selected, values = _extract_columns(data, names)
    state = renderer_state(ax)
    layer_id = state.candidate_id("points")

    requests: list[MappingRequest] = []
    color_spec: DiscreteScaleSpec | ContinuousScaleSpec | None = None
    if color is not None:
        color_spec = _color_scale(selected[color], values[color], color_scale)
        requests.append(
            MappingRequest.from_values(
                layer_id,
                color,
                color_spec,
                cast(Iterable[object], selected[color]),
            )
        )
    registry = semantic_registry(ax) if requests else None
    semantic_plan = (
        registry.prepare(requests, remove_layers=state.detached_layers(ax))
        if registry is not None
        else None
    )
    groups, mapped_dropped, coordinate_dropped, group_dropped = _prepare_points(
        values=values,
        x=x,
        y=y,
        color=color,
        group=group,
        missing=cast(PointMissingPolicy, missing),
        group_missing=cast(GroupMissingPolicy, group_missing),
        plan=semantic_plan,
        layer_id=layer_id,
        color_spec=color_spec,
    )
    diagnostics = list(semantic_plan.diagnostics if semantic_plan is not None else ())
    for count, reason in (
        (mapped_dropped, "under mapped-aesthetic missing policy"),
        (coordinate_dropped, "with missing point coordinates"),
        (group_dropped, f"with missing group {group!r}"),
    ):
        if count:
            diagnostics.append(f"dropped {count} row(s) {reason}")

    axes_snapshot = capture_axes(ax)
    state_snapshot = state.snapshot()
    property_changes: tuple[ArtistChange, ...] = ()
    guide_update: _GuideUpdate | None = None
    artists: list[PathCollection] = []

    def rollback() -> None:
        if guide_update is not None:
            guide_update.rollback()
        rollback_artist_changes(property_changes)
        restore_axes(ax, axes_snapshot)
        state.restore(state_snapshot)

    def apply(plan: SemanticPlan | None) -> PointResult:
        nonlocal guide_update, property_changes
        if plan is not None:
            property_changes = prepare_artist_changes(plan, state, ax)
            apply_artist_changes(property_changes)
        bindings: list[ArtistBinding] = []
        marker_path = fixed.marker.get_path().transformed(fixed.marker.get_transform())
        for item in groups:
            properties = dict(fixed.properties)
            if item.colors is not None:
                properties["c"] = item.colors
            artist = ax.scatter(
                cast(Any, item.x),
                cast(Any, item.y),
                s=fixed.size,
                marker=marker_path,
                **cast(Any, properties),
            )
            artists.append(artist)
            targets = ("point-color",) if color is not None else ()
            bindings.append(
                ArtistBinding(
                    cast(Any, weakref.ref(artist)),
                    item.indices,
                    cast(Any, targets),
                )
            )
        guide_update = _prepare_guide_refresh(ax, plan)
        handle = date_handle(ax)
        if handle is not None and artists:
            cast(Any, handle).refresh()
        if guide_update is not None:
            guide_update.commit()
        state.commit_layer(ax, "points", layer_id, bindings)
        return PointResult(
            ax,
            tuple(artists),
            scales_for(plan, layer_id),
            tuple(diagnostics),
            layer_id,
        )

    if registry is not None and semantic_plan is not None:
        return registry.transact(semantic_plan, apply, rollback)
    try:
        return apply(None)
    except BaseException:
        rollback()
        raise
