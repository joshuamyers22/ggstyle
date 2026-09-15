"""Transactional tidy-data ribbon rendering on an existing Matplotlib axes."""

from __future__ import annotations

import math
import weakref
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import Any, Literal, cast

from matplotlib.axes import Axes
from matplotlib.collections import PolyCollection

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
from ._semantic_registry import MappingRequest, SemanticPlan, semantic_registry
from ._semantic_scales import ContinuousScaleSpec, DiscreteScaleSpec
from .line import (
    GroupMissingPolicy,
    SortPolicy,
    _assignments,
    _color_scale,
    _extract_columns,
    _group_key,
    _is_missing,
    _optional_text,
    _sorted_indices,
    _text,
)
from .scales import AestheticScale, ContinuousScale, DiscreteScale

__all__ = ["RibbonResult", "ribbon"]

RibbonMissingPolicy = Literal["break", "drop", "raise"]


@dataclass(frozen=True)
class RibbonResult:
    """Return native ribbon collections and mappings created by :func:`ribbon`."""

    axes: Axes
    artists: tuple[PolyCollection, ...]
    scales: Mapping[str, AestheticScale]
    diagnostics: tuple[str, ...]
    layer_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "artists", tuple(self.artists))
        object.__setattr__(self, "scales", MappingProxyType(dict(self.scales)))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True)
class _PreparedRibbon:
    indices: tuple[int, ...]
    x: tuple[object, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    properties: Mapping[str, object]
    label: str | None


def _alpha(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"alpha must be a real number, got {value!r}")
    resolved = float(value)
    if not math.isfinite(resolved) or not 0 <= resolved <= 1:
        raise ValueError(f"alpha must be finite and between 0 and 1, got {value!r}")
    return resolved


def _ribbon_style(
    value: object, *, color: str | None, alpha: float
) -> Mapping[str, object]:
    if value is None:
        result: dict[str, object] = {}
    elif isinstance(value, Mapping):
        result = dict(value)
    else:
        raise TypeError(f"style must be a mapping or None, got {value!r}")
    if not all(isinstance(key, str) for key in result):
        raise TypeError("style keys must be strings")
    if "alpha" in result:
        raise ValueError("alpha cannot appear in both alpha= and style")
    if "label" in result:
        raise ValueError("label cannot appear in both label= and style")
    if color is not None and {
        "c",
        "color",
        "facecolor",
        "facecolors",
        "fc",
    } & result.keys():
        raise ValueError("color cannot be both mapped and fixed in style")
    forbidden = {"cmap", "norm", "vmin", "vmax"} & result.keys()
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise ValueError(
            f"ribbon style cannot contain scale properties ({names}); use color_scale="
        )
    try:
        PolyCollection([], alpha=alpha, **cast(Any, result))
    except (AttributeError, TypeError, ValueError) as error:
        raise type(error)(f"invalid fixed ribbon style: {error}") from error
    return MappingProxyType(result)


def _bound(value: object, *, name: str, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(
            f"ribbon bound column {name!r} must contain real numbers; "
            f"row {index} is {value!r}"
        )
    resolved = float(value)
    if not math.isfinite(resolved):
        raise ValueError(
            f"ribbon bound column {name!r} must contain finite values; "
            f"row {index} is {value!r}"
        )
    return resolved


def _ordered_groups(
    indices: Sequence[int],
    grouping: Sequence[tuple[str, tuple[object, ...]]],
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


def _segments(
    indices: Sequence[int], missing: Sequence[bool]
) -> tuple[tuple[int, ...], ...]:
    segments: list[tuple[int, ...]] = []
    current: list[int] = []
    for index in indices:
        if missing[index]:
            if current:
                segments.append(tuple(current))
                current = []
        else:
            current.append(index)
    if current:
        segments.append(tuple(current))
    return tuple(segments)


def _prepare_ribbons(
    *,
    values: Mapping[str, tuple[object, ...]],
    x: str,
    lower: str,
    upper: str,
    color: str | None,
    group: str | None,
    style: Mapping[str, object],
    label: str | None,
    sort: SortPolicy,
    missing: RibbonMissingPolicy,
    group_missing: GroupMissingPolicy,
    validate_order: bool,
    plan: SemanticPlan | None,
    layer_id: str,
    color_spec: DiscreteScaleSpec | ContinuousScaleSpec | None,
) -> tuple[tuple[_PreparedRibbon, ...], int, int, int]:
    assignments = {} if plan is None else _assignments(plan, layer_id)
    count = len(values[x])
    keep = [True] * count
    mapped_dropped = 0
    if color is not None:
        for index, output in enumerate(assignments["color"].outputs):
            if output is None:
                keep[index] = False
                mapped_dropped += 1

    coordinate_missing = [False] * count
    coordinate_dropped = 0
    resolved_lower: list[float | None] = [None] * count
    resolved_upper: list[float | None] = [None] * count
    for index, (x_value, low_value, high_value) in enumerate(
        zip(values[x], values[lower], values[upper], strict=True)
    ):
        if _is_missing(x_value) or _is_missing(low_value) or _is_missing(high_value):
            coordinate_missing[index] = True
            if missing == "raise":
                raise ValueError(
                    f"ribbon coordinates contain a missing value at row {index}"
                )
            if keep[index]:
                coordinate_dropped += 1
            continue
        low = _bound(low_value, name=lower, index=index)
        high = _bound(high_value, name=upper, index=index)
        if validate_order and low > high:
            raise ValueError(
                f"lower bound exceeds upper bound at row {index}: {low!r} > {high!r}"
            )
        resolved_lower[index] = low
        resolved_upper[index] = high

    group_dropped = 0
    if group is not None:
        for index, value in enumerate(values[group]):
            if not _is_missing(value):
                continue
            if group_missing == "raise":
                raise ValueError(f"grouping column {group!r} contains missing values")
            if group_missing == "drop" and keep[index] and not coordinate_missing[index]:
                group_dropped += 1
            if group_missing == "drop":
                keep[index] = False

    grouping: list[tuple[str, tuple[object, ...]]] = []
    if group is not None:
        grouping.append((group, values[group]))
    if color is not None and isinstance(color_spec, DiscreteScaleSpec):
        grouping.append((color, values[color]))
    candidates = [index for index, retained in enumerate(keep) if retained]
    logical_groups = _ordered_groups(candidates, grouping)
    if label is not None and len(logical_groups) > 1:
        raise ValueError("label requires exactly one resolved ribbon group")

    prepared: list[_PreparedRibbon] = []
    label_available = True
    for logical in logical_groups:
        if missing == "break":
            pieces = _segments(logical, coordinate_missing)
        else:
            pieces = (tuple(index for index in logical if not coordinate_missing[index]),)
        for indices in pieces:
            if not indices:
                continue
            indices = _sorted_indices(indices, values[x], sort)
            properties = dict(style)
            if color is not None:
                assignment = assignments["color"]
                if isinstance(color_spec, ContinuousScaleSpec):
                    properties["facecolor"] = constant_output(
                        assignment, indices, geometry="ribbon"
                    )
                else:
                    output = assignment.outputs[indices[0]]
                    assert output is not None
                    properties["facecolor"] = output
            low_values = tuple(cast(float, resolved_lower[index]) for index in indices)
            high_values = tuple(cast(float, resolved_upper[index]) for index in indices)
            segment_label = label if label_available else "_nolegend_"
            prepared.append(
                _PreparedRibbon(
                    indices,
                    tuple(values[x][index] for index in indices),
                    low_values,
                    high_values,
                    MappingProxyType(properties),
                    segment_label,
                )
            )
            if label is not None:
                label_available = False
    return tuple(prepared), mapped_dropped, coordinate_dropped, group_dropped


def ribbon(
    data: object,
    *,
    x: str,
    lower: str,
    upper: str,
    ax: Axes,
    color: str | None = None,
    group: str | None = None,
    color_scale: DiscreteScale | ContinuousScale | None = None,
    style: Mapping[str, object] | None = None,
    alpha: float = 0.2,
    label: str | None = None,
    sort: SortPolicy = "input",
    missing: RibbonMissingPolicy = "break",
    group_missing: GroupMissingPolicy = "drop",
    validate_order: bool = False,
) -> RibbonResult:
    """Draw caller-supplied lower/upper bounds as native Matplotlib ribbons.

    The helper performs no statistical inference. Missing coordinates break a ribbon
    by default, while ``missing="drop"`` explicitly connects across gaps. Crossed
    bounds are accepted unless ``validate_order=True``. A caller label is preserved
    verbatim and never synthesized from mappings.
    """

    if not isinstance(ax, Axes):
        raise TypeError(f"ax must be a matplotlib Axes, got {ax!r}")
    x = _text("x", x)
    lower = _text("lower", lower)
    upper = _text("upper", upper)
    color = _optional_text("color", color)
    group = _optional_text("group", group)
    if color_scale is not None and not isinstance(
        color_scale, (DiscreteScale, ContinuousScale)
    ):
        raise TypeError("color_scale must be a DiscreteScale, ContinuousScale, or None")
    if color is None and color_scale is not None:
        raise ValueError("color_scale requires a mapped color column")
    if sort not in ("input", "x"):
        raise ValueError(f"sort must be 'input' or 'x', got {sort!r}")
    if missing not in ("break", "drop", "raise"):
        raise ValueError(f"missing must be 'break', 'drop', or 'raise', got {missing!r}")
    if group_missing not in ("drop", "keep", "raise"):
        raise ValueError(
            "group_missing must be 'drop', 'keep', or 'raise', "
            f"got {group_missing!r}"
        )
    if not isinstance(validate_order, bool):
        raise TypeError(f"validate_order must be bool, got {validate_order!r}")
    if label is not None and not isinstance(label, str):
        raise TypeError(f"label must be a string or None, got {label!r}")
    resolved_alpha = _alpha(alpha)
    fixed = _ribbon_style(style, color=color, alpha=resolved_alpha)

    names = [x, lower, upper]
    names.extend(name for name in (color, group) if name is not None)
    selected, values = _extract_columns(data, names)
    state = renderer_state(ax)
    layer_id = state.candidate_id("ribbon")

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
    groups, mapped_dropped, coordinate_dropped, group_dropped = _prepare_ribbons(
        values=values,
        x=x,
        lower=lower,
        upper=upper,
        color=color,
        group=group,
        style=fixed,
        label=label,
        sort=cast(SortPolicy, sort),
        missing=cast(RibbonMissingPolicy, missing),
        group_missing=cast(GroupMissingPolicy, group_missing),
        validate_order=validate_order,
        plan=semantic_plan,
        layer_id=layer_id,
        color_spec=color_spec,
    )
    diagnostics = list(semantic_plan.diagnostics if semantic_plan is not None else ())
    for count, reason in (
        (mapped_dropped, "under mapped-aesthetic missing policy"),
        (coordinate_dropped, "with missing ribbon coordinates"),
        (group_dropped, f"with missing group {group!r}"),
    ):
        if count:
            diagnostics.append(f"dropped {count} row(s) {reason}")

    axes_snapshot = capture_axes(ax)
    state_snapshot = state.snapshot()
    property_changes: tuple[ArtistChange, ...] = ()
    artists: list[PolyCollection] = []

    def rollback() -> None:
        rollback_artist_changes(property_changes)
        restore_axes(ax, axes_snapshot)
        state.restore(state_snapshot)

    def apply(plan: SemanticPlan | None) -> RibbonResult:
        nonlocal property_changes
        if plan is not None:
            property_changes = prepare_artist_changes(plan, state, ax)
            apply_artist_changes(property_changes)
        bindings: list[ArtistBinding] = []
        for item in groups:
            artist = ax.fill_between(
                cast(Any, item.x),
                item.lower,
                item.upper,
                alpha=resolved_alpha,
                label=item.label,
                **cast(Any, dict(item.properties)),
            )
            artists.append(artist)
            targets = ("ribbon-color",) if color is not None else ()
            bindings.append(
                ArtistBinding(
                    cast(Any, weakref.ref(artist)),
                    item.indices,
                    cast(Any, targets),
                )
            )
        handle = date_handle(ax)
        if handle is not None and artists:
            cast(Any, handle).refresh()
        state.commit_layer(ax, "ribbon", layer_id, bindings)
        return RibbonResult(
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
