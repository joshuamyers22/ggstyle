"""Transactional tidy-data line rendering on an existing Matplotlib axes."""

from __future__ import annotations

import weakref
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.lines import Line2D

from ._frames import column
from ._semantic_artists import (
    ArtistBinding,
    ArtistChange,
    apply_artist_changes,
    capture_axes,
    constant_output,
    date_handle,
    prepare_artist_changes,
    renderer_state,
    restore_axes,
    rollback_artist_changes,
    scales_for,
)
from ._semantic_registry import (
    MappingAssignment,
    MappingRequest,
    SemanticPlan,
    semantic_registry,
)
from ._semantic_scales import ContinuousScaleSpec, DiscreteScaleSpec
from .guides import _GuideUpdate, _prepare_guide_refresh
from .results import _describe_result, _geometry_payload
from .scales import (
    AestheticScale,
    ContinuousScale,
    DiscreteScale,
    _resolve_continuous,
    _resolve_discrete,
)

__all__ = ["LineResult", "line"]

SortPolicy = Literal["input", "x"]
GroupMissingPolicy = Literal["drop", "keep", "raise"]
_MISSING_GROUP = object()


@dataclass(frozen=True)
class LineResult:
    """
    Return native artists and trained mappings created by :func:`line`.

    Parameters
    ----------
    axes : matplotlib.axes.Axes
        The exact caller-owned axes passed to :func:`line`.
    artists : tuple of matplotlib.lines.Line2D
        Ordinary Matplotlib line artists, one per resolved group.
    scales : mapping of str to AestheticScale
        Trained scales used by this layer, keyed by ``"color"`` or
        ``"linestyle"``. The mapping is read-only.
    diagnostics : tuple of str
        Non-fatal accessibility or dropped-row diagnostics.
    layer_id : str
        Stable identifier for this committed semantic layer.
    """

    axes: Axes
    artists: tuple[Line2D, ...]
    scales: Mapping[str, AestheticScale]
    diagnostics: tuple[str, ...]
    layer_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "artists", tuple(self.artists))
        object.__setattr__(self, "scales", MappingProxyType(dict(self.scales)))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    def as_dict(self) -> dict[str, object]:
        """
        Return a bounded, deterministic, JSON-compatible summary.

        Returns
        -------
        dict of str to object
            Fresh containers describing the layer, native artist counts, trained
            scales, and diagnostics. Live Matplotlib objects are excluded.
        """

        return _geometry_payload(
            kind="line",
            artists=self.artists,
            scales=self.scales,
            diagnostics=self.diagnostics,
            layer_id=self.layer_id,
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
class _PreparedGroup:
    indices: tuple[int, ...]
    x: tuple[object, ...]
    y: tuple[object, ...]
    properties: Mapping[str, object]


@dataclass(frozen=True)
class _PreparedLine:
    layer_id: str
    groups: tuple[_PreparedGroup, ...]
    semantic_plan: SemanticPlan | None
    diagnostics: tuple[str, ...]


def _text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a column-name string, got {value!r}")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _optional_text(name: str, value: object) -> str | None:
    return None if value is None else _text(name, value)


def _is_missing(value: object) -> bool:
    if value is None or value is pd.NA:
        return True
    try:
        result = pd.isna(cast(Any, value))
    except (TypeError, ValueError):
        return False
    return isinstance(result, (bool, np.bool_)) and bool(result)


def _values(name: str, selected: object) -> tuple[object, ...]:
    if getattr(selected, "ndim", 1) != 1:
        raise ValueError(f"column {name!r} must be one-dimensional and uniquely named")
    if isinstance(selected, (str, bytes)):
        raise TypeError(f"column {name!r} must be a one-dimensional sequence")
    converter = getattr(selected, "to_list", None)
    if callable(converter):
        return tuple(converter())
    try:
        return tuple(cast(Iterable[object], selected))
    except TypeError as error:
        raise TypeError(
            f"column {name!r} must be a one-dimensional sequence"
        ) from error


def _extract_columns(
    data: object, names: Sequence[str]
) -> tuple[dict[str, object], dict[str, tuple[object, ...]]]:
    if isinstance(data, (str, bytes)):
        raise TypeError("data must be a dataframe-like object, not a string")
    if (
        type(data).__module__.split(".")[0] == "polars"
        and type(data).__name__ == "LazyFrame"
    ):
        raise TypeError(
            "data must be materialized before plotting; call collect() on LazyFrame"
        )

    selected: dict[str, object] = {}
    values: dict[str, tuple[object, ...]] = {}
    for name in dict.fromkeys(names):
        source = column(data, name)
        selected[name] = source
        values[name] = _values(name, source)
    expected = len(values[names[0]])
    mismatches = [name for name in names if len(values[name]) != expected]
    if mismatches:
        joined = ", ".join(dict.fromkeys(mismatches))
        raise ValueError(f"mapped columns must have equal length; mismatched: {joined}")
    return selected, values


def _style(value: object, *, color: str | None, linestyle: str | None) -> dict[str, object]:
    if value is None:
        result: dict[str, object] = {}
    elif isinstance(value, Mapping):
        result = dict(value)
    else:
        raise TypeError(f"style must be a mapping or None, got {value!r}")
    if not all(isinstance(key, str) for key in result):
        raise TypeError("style keys must be strings")
    if color is not None and {"color", "c"} & result.keys():
        raise ValueError("color cannot be both mapped and fixed in style")
    if linestyle is not None and {"linestyle", "ls"} & result.keys():
        raise ValueError("linestyle cannot be both mapped and fixed in style")
    try:
        Line2D([], [], **cast(Any, result))
    except (AttributeError, TypeError, ValueError) as error:
        raise type(error)(f"invalid fixed line style: {error}") from error
    return result


def _color_scale(
    source: object,
    values: tuple[object, ...],
    configured: DiscreteScale | ContinuousScale | None,
) -> DiscreteScaleSpec | ContinuousScaleSpec:
    if isinstance(configured, DiscreteScale):
        return _resolve_discrete(configured, "color")
    if isinstance(configured, ContinuousScale):
        return _resolve_continuous(configured)
    dtype = getattr(source, "dtype", None)
    if isinstance(dtype, pd.CategoricalDtype) or (
        dtype is not None and pd.api.types.is_bool_dtype(dtype)
    ):
        return DiscreteScaleSpec(aesthetic="color")
    if dtype is not None and pd.api.types.is_numeric_dtype(dtype):
        return ContinuousScaleSpec(aesthetic="color")
    observed = [value for value in values if not _is_missing(value)]
    if observed and all(
        isinstance(value, Real) and not isinstance(value, bool) for value in observed
    ):
        return ContinuousScaleSpec(aesthetic="color")
    return DiscreteScaleSpec(aesthetic="color")


def _group_key(value: object, *, variable: str) -> object:
    if _is_missing(value):
        return _MISSING_GROUP
    try:
        hash(value)
    except TypeError as error:
        raise TypeError(
            f"grouping column {variable!r} must contain hashable scalar values, "
            f"got {value!r}"
        ) from error
    return value


def _assignments(plan: SemanticPlan, layer_id: str) -> dict[str, MappingAssignment]:
    return {
        assignment.key.aesthetic: assignment
        for assignment in plan.assignments
        if assignment.layer_id == layer_id
    }


def _ordered_groups(
    row_indices: Sequence[int],
    grouping: Sequence[tuple[str, tuple[object, ...]]],
) -> tuple[tuple[int, ...], ...]:
    if not row_indices:
        return ()
    if not grouping:
        return (tuple(row_indices),)
    groups: dict[tuple[object, ...], list[int]] = {}
    for index in row_indices:
        key = tuple(
            _group_key(values[index], variable=name) for name, values in grouping
        )
        groups.setdefault(key, []).append(index)
    return tuple(tuple(indices) for indices in groups.values())


def _sorted_indices(
    indices: tuple[int, ...], x_values: tuple[object, ...], sort: SortPolicy
) -> tuple[int, ...]:
    if sort == "input":
        return indices
    try:
        return tuple(sorted(indices, key=lambda index: cast(Any, x_values[index])))
    except (TypeError, ValueError) as error:
        raise TypeError(
            "x values must be mutually orderable when sort='x'; use sort='input' "
            "to preserve row order"
        ) from error


def _prepare_groups(
    *,
    values: Mapping[str, tuple[object, ...]],
    x: str,
    y: str,
    color: str | None,
    group: str | None,
    linestyle: str | None,
    style: Mapping[str, object],
    sort: SortPolicy,
    group_missing: GroupMissingPolicy,
    plan: SemanticPlan | None,
    layer_id: str,
    color_spec: DiscreteScaleSpec | ContinuousScaleSpec | None,
) -> tuple[tuple[_PreparedGroup, ...], int, int]:
    assignments = {} if plan is None else _assignments(plan, layer_id)
    row_count = len(values[x])
    keep = [True] * row_count
    mapped_dropped = 0
    for assignment in assignments.values():
        for index, output in enumerate(assignment.outputs):
            if output is None and keep[index]:
                keep[index] = False
                mapped_dropped += 1

    missing_groups = 0
    if group is not None:
        for index, value in enumerate(values[group]):
            if not _is_missing(value):
                continue
            missing_groups += 1
            if group_missing == "raise":
                raise ValueError(f"grouping column {group!r} contains missing values")
            if group_missing == "drop" and keep[index]:
                keep[index] = False
            elif group_missing == "drop":
                missing_groups -= 1

    grouping: list[tuple[str, tuple[object, ...]]] = []
    if group is not None:
        grouping.append((group, values[group]))
    if color is not None and isinstance(color_spec, DiscreteScaleSpec):
        grouping.append((color, values[color]))
    if linestyle is not None:
        grouping.append((linestyle, values[linestyle]))

    groups = _ordered_groups(
        [index for index, retained in enumerate(keep) if retained], grouping
    )
    prepared: list[_PreparedGroup] = []
    for indices in groups:
        indices = _sorted_indices(indices, values[x], sort)
        properties = dict(style)
        if color is not None:
            color_assignment = assignments["color"]
            if isinstance(color_spec, ContinuousScaleSpec):
                properties["color"] = constant_output(
                    color_assignment, indices, geometry="line"
                )
            else:
                output = color_assignment.outputs[indices[0]]
                assert output is not None
                properties["color"] = output
        if linestyle is not None:
            output = assignments["linestyle"].outputs[indices[0]]
            assert output is not None
            properties["linestyle"] = output
        prepared.append(
            _PreparedGroup(
                indices,
                tuple(values[x][index] for index in indices),
                tuple(values[y][index] for index in indices),
                MappingProxyType(properties),
            )
        )
    return tuple(prepared), mapped_dropped, missing_groups


def line(
    data: object,
    *,
    x: str,
    y: str,
    ax: Axes,
    color: str | None = None,
    group: str | None = None,
    linestyle: str | None = None,
    color_scale: DiscreteScale | ContinuousScale | None = None,
    linestyle_scale: DiscreteScale | None = None,
    style: Mapping[str, object] | None = None,
    sort: SortPolicy = "input",
    group_missing: GroupMissingPolicy = "drop",
) -> LineResult:
    """
    Draw deterministic grouped lines from named tidy-data columns.

    Parameters
    ----------
    data : dataframe-like
        Column-bearing dataframe-like or mapping-like data. Input data is never
        mutated.
    x, y : str
        Required coordinate column names. Strings are names only; expressions are
        never evaluated.
    ax : matplotlib.axes.Axes
        Existing caller-owned target axes.
    color : str or None, optional
        Column mapped to color. Numeric values use a continuous scale; categorical,
        boolean, and other values use a discrete scale.
    group : str or None, optional
        Column that partitions rows into separate lines without assigning an
        aesthetic. Discrete color and linestyle mappings also imply grouping.
    linestyle : str or None, optional
        Column mapped to a discrete line style.
    color_scale : DiscreteScale, ContinuousScale, or None, optional
        Explicit color policy. Omit to infer continuous numeric color and discrete
        categorical color.
    linestyle_scale : DiscreteScale or None, optional
        Explicit discrete line-style policy.
    style : mapping or None, optional
        Fixed ``Line2D`` properties. A mapped color or linestyle cannot also appear
        here, including through Matplotlib's ``c`` and ``ls`` aliases.
    sort : {"input", "x"}, default "input"
        Preserve input order within each line or stably sort by x. Duplicate x values
        retain their relative input order; no aggregation is performed.
    group_missing : {"drop", "keep", "raise"}, default "drop"
        Policy for rows whose explicit ``group`` value is missing.

    Returns
    -------
    LineResult
        The original axes, ordinary line artists, trained scales, diagnostics, and
        committed layer identifier.

    Raises
    ------
    TypeError
        If inputs, columns, grouping values, or fixed style are invalid.
    ValueError
        If columns conflict, scale training fails, or a continuous color varies
        within one resolved line.

    Notes
    -----
    The operation resolves and validates every group before drawing, then commits
    semantic state and artists transactionally. Adding a layer may retrain a shared
    continuous scale and update earlier managed lines on the same axes. Existing
    ggstyle date handles are refreshed after drawing, including collapsed axes.

    This helper does not aggregate, smooth, interpolate, construct guides, or create
    axes. Use ``style={"color": ...}`` for a fixed color and ``color="column"`` for
    a semantic mapping.
    """

    if not isinstance(ax, Axes):
        raise TypeError(f"ax must be a matplotlib Axes, got {ax!r}")
    x = _text("x", x)
    y = _text("y", y)
    color = _optional_text("color", color)
    group = _optional_text("group", group)
    linestyle = _optional_text("linestyle", linestyle)
    if color_scale is not None and not isinstance(
        color_scale, (DiscreteScale, ContinuousScale)
    ):
        raise TypeError(
            "color_scale must be a DiscreteScale, ContinuousScale, or None"
        )
    if color is None and color_scale is not None:
        raise ValueError("color_scale requires a mapped color column")
    if linestyle_scale is not None and not isinstance(linestyle_scale, DiscreteScale):
        raise TypeError("linestyle_scale must be a DiscreteScale or None")
    if linestyle is None and linestyle_scale is not None:
        raise ValueError("linestyle_scale requires a mapped linestyle column")
    if sort not in ("input", "x"):
        raise ValueError(f"sort must be 'input' or 'x', got {sort!r}")
    if group_missing not in ("drop", "keep", "raise"):
        raise ValueError(
            "group_missing must be 'drop', 'keep', or 'raise', "
            f"got {group_missing!r}"
        )
    fixed = _style(style, color=color, linestyle=linestyle)

    names = [x, y]
    names.extend(name for name in (color, group, linestyle) if name is not None)
    selected, values = _extract_columns(data, names)

    state = renderer_state(ax)
    layer_id = state.candidate_id("line")
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
    if linestyle is not None:
        requests.append(
            MappingRequest.from_values(
                layer_id,
                linestyle,
                _resolve_discrete(
                    DiscreteScale() if linestyle_scale is None else linestyle_scale,
                    "linestyle",
                ),
                cast(Iterable[object], selected[linestyle]),
            )
        )

    registry = semantic_registry(ax) if requests else None
    semantic_plan = (
        registry.prepare(requests, remove_layers=state.detached_layers(ax))
        if registry is not None
        else None
    )
    groups, mapped_dropped, missing_groups = _prepare_groups(
        values=values,
        x=x,
        y=y,
        color=color,
        group=group,
        linestyle=linestyle,
        style=fixed,
        sort=cast(SortPolicy, sort),
        group_missing=cast(GroupMissingPolicy, group_missing),
        plan=semantic_plan,
        layer_id=layer_id,
        color_spec=color_spec,
    )
    diagnostics = list(semantic_plan.diagnostics if semantic_plan is not None else ())
    if mapped_dropped:
        diagnostics.append(
            f"dropped {mapped_dropped} row(s) under mapped-aesthetic missing policy"
        )
    if group_missing == "drop" and missing_groups:
        diagnostics.append(
            f"dropped {missing_groups} row(s) with missing group {group!r}"
        )
    prepared = _PreparedLine(layer_id, groups, semantic_plan, tuple(diagnostics))

    axes_snapshot = capture_axes(ax)
    property_changes: tuple[ArtistChange, ...] = ()
    guide_update: _GuideUpdate | None = None
    artists: list[Line2D] = []
    state_snapshot = state.snapshot()

    def rollback() -> None:
        if guide_update is not None:
            guide_update.rollback()
        rollback_artist_changes(property_changes)
        restore_axes(ax, axes_snapshot)
        state.restore(state_snapshot)

    def apply(plan: SemanticPlan | None) -> LineResult:
        nonlocal guide_update, property_changes
        if plan is not None:
            property_changes = prepare_artist_changes(plan, state, ax)
            apply_artist_changes(property_changes)
        bindings: list[ArtistBinding] = []
        targets = tuple(
            target
            for mapped, target in (
                (color, "line-color"),
                (linestyle, "line-linestyle"),
            )
            if mapped is not None
        )
        for item in prepared.groups:
            created = ax.plot(
                cast(Any, item.x),
                cast(Any, item.y),
                **cast(Any, dict(item.properties)),
            )
            if len(created) != 1:
                raise RuntimeError("Matplotlib returned an unexpected line count")
            artist = created[0]
            artists.append(artist)
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

        state.commit_layer(ax, "line", layer_id, bindings)
        return LineResult(
            ax,
            tuple(artists),
            scales_for(plan, layer_id),
            prepared.diagnostics,
            layer_id,
        )

    if registry is not None and semantic_plan is not None:
        return registry.transact(semantic_plan, apply, rollback)
    try:
        return apply(None)
    except BaseException:
        rollback()
        raise
