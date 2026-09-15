"""Shared artist ownership and rollback for semantic renderers."""

from __future__ import annotations

import warnings
import weakref
from collections.abc import Mapping, Sequence
from copy import copy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, cast
from weakref import WeakKeyDictionary

import numpy as np
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection, PolyCollection
from matplotlib.lines import Line2D

from ._semantic_registry import MappingAssignment, SemanticPlan
from ._semantic_scales import Aesthetic
from .scales import AestheticScale

RendererKind = Literal["line", "points", "ribbon"]
ArtistTarget = Literal[
    "line-color",
    "line-linestyle",
    "point-color",
    "ribbon-color",
]


@dataclass(frozen=True)
class ArtistBinding:
    """Weak artist reference plus source rows and mapped setter targets."""

    artist: weakref.ReferenceType[Artist]
    indices: tuple[int, ...]
    targets: tuple[ArtistTarget, ...]


@dataclass
class RendererState:
    """Axes-local ownership for every semantic renderer."""

    next_ids: dict[RendererKind, int] = field(
        default_factory=lambda: {"line": 1, "points": 1, "ribbon": 1}
    )
    layers: dict[str, tuple[ArtistBinding, ...]] = field(default_factory=dict)

    def candidate_id(self, kind: RendererKind) -> str:
        return f"{kind}-{self.next_ids[kind]}"

    def detached_layers(self, ax: Axes) -> tuple[str, ...]:
        detached = []
        for layer_id, bindings in self.layers.items():
            artists = [binding.artist() for binding in bindings]
            if artists and not any(
                artist is not None and artist.axes is ax for artist in artists
            ):
                detached.append(layer_id)
        return tuple(detached)

    def snapshot(
        self,
    ) -> tuple[dict[RendererKind, int], dict[str, tuple[ArtistBinding, ...]]]:
        return dict(self.next_ids), dict(self.layers)

    def restore(
        self,
        snapshot: tuple[
            dict[RendererKind, int], dict[str, tuple[ArtistBinding, ...]]
        ],
    ) -> None:
        self.next_ids, self.layers = snapshot

    def commit_layer(
        self,
        ax: Axes,
        kind: RendererKind,
        layer_id: str,
        bindings: Sequence[ArtistBinding],
    ) -> None:
        detached = set(self.detached_layers(ax))
        self.layers = {
            key: value for key, value in self.layers.items() if key not in detached
        }
        self.layers[layer_id] = tuple(bindings)
        self.next_ids[kind] += 1
        _RENDERER_STATES[ax] = self


@dataclass(frozen=True)
class _CycleSnapshot:
    index: int | None
    property_cycle: object | None


@dataclass(frozen=True)
class AxesSnapshot:
    """Restorable axes mutation state shared by every semantic renderer."""

    lines: tuple[Line2D, ...]
    collections: tuple[Artist, ...]
    data_limits: np.ndarray
    view_limits: np.ndarray
    x_converter: object
    y_converter: object
    x_units: object
    y_units: object
    x_major_locator: object
    x_major_formatter: object
    x_minor_locator: object
    x_minor_formatter: object
    y_major_locator: object
    y_major_formatter: object
    y_minor_locator: object
    y_minor_formatter: object
    x_label: str
    y_label: str
    ignore_existing_data_limits: bool
    stale_view_limits: Mapping[str, bool]
    line_cycle: _CycleSnapshot
    patch_cycle: _CycleSnapshot
    stale: bool


@dataclass(frozen=True)
class ArtistChange:
    """One restorable mapped-artist property update."""

    artist: Artist
    target: ArtistTarget
    previous: object
    output: str | tuple[str, ...]


_RENDERER_STATES: WeakKeyDictionary[Axes, RendererState] = WeakKeyDictionary()


def renderer_state(ax: Axes) -> RendererState:
    """Return existing renderer ownership without storing a new empty state."""

    existing = _RENDERER_STATES.get(ax)
    return existing if existing is not None else RendererState()


def renderer_state_count() -> int:
    """Return live axes-state count for lifecycle tests."""

    return len(_RENDERER_STATES)


def constant_output(
    assignment: MappingAssignment,
    indices: Sequence[int],
    *,
    geometry: str,
) -> str:
    """Return one mapped output or reject variation within one constant artist."""

    outputs = [assignment.outputs[index] for index in indices]
    distinct = tuple(dict.fromkeys(outputs))
    if len(distinct) != 1 or distinct[0] is None:
        raise ValueError(
            f"continuous color mapping {assignment.key.variable!r} must be constant "
            f"within each resolved {geometry}; supply group= with one color value "
            "per group"
        )
    return distinct[0]


def _assignment_index(plan: SemanticPlan) -> dict[tuple[str, Aesthetic], MappingAssignment]:
    return {
        (assignment.layer_id, assignment.key.aesthetic): assignment
        for assignment in plan.assignments
    }


def _target_aesthetic(target: ArtistTarget) -> Aesthetic:
    return "linestyle" if target == "line-linestyle" else "color"


def _outputs_for(
    target: ArtistTarget,
    assignment: MappingAssignment,
    indices: tuple[int, ...],
) -> str | tuple[str, ...]:
    if target == "point-color":
        outputs = tuple(assignment.outputs[index] for index in indices)
        if any(output is None for output in outputs):  # pragma: no cover - preflight guard
            raise RuntimeError("dropped point rows reached artist update")
        return cast(tuple[str, ...], outputs)
    geometry = "line" if target.startswith("line-") else "ribbon"
    return constant_output(assignment, indices, geometry=geometry)


def _previous(artist: Artist, target: ArtistTarget) -> object:
    if target == "line-color":
        return cast(Line2D, artist).get_color()
    if target == "line-linestyle":
        return cast(Line2D, artist).get_linestyle()
    if target in ("point-color", "ribbon-color"):
        return cast(Any, artist).get_facecolors().copy()
    raise AssertionError(f"unknown artist target {target!r}")


def prepare_artist_changes(
    plan: SemanticPlan, state: RendererState, ax: Axes
) -> tuple[ArtistChange, ...]:
    """Resolve all existing mapped-artist updates without mutation."""

    assignments = _assignment_index(plan)
    changes: list[ArtistChange] = []
    for layer_id, bindings in state.layers.items():
        for binding in bindings:
            artist = binding.artist()
            if artist is None or artist.axes is not ax:
                continue
            for target in binding.targets:
                aesthetic = _target_aesthetic(target)
                assignment = assignments.get((layer_id, aesthetic))
                if assignment is None:
                    continue
                output = _outputs_for(target, assignment, binding.indices)
                previous = _previous(artist, target)
                if target.startswith("line-") and previous == output:
                    continue
                changes.append(ArtistChange(artist, target, previous, output))
    return tuple(changes)


def _set_output(artist: Artist, target: ArtistTarget, output: object) -> None:
    if target == "line-color":
        cast(Line2D, artist).set_color(cast(Any, output))
    elif target == "line-linestyle":
        cast(Line2D, artist).set_linestyle(cast(Any, output))
    elif target == "point-color":
        cast(PathCollection, artist).set_facecolor(cast(Any, output))
    elif target == "ribbon-color":
        cast(PolyCollection, artist).set_facecolor(cast(Any, output))
    else:  # pragma: no cover - exhaustive guard
        raise AssertionError(f"unknown artist target {target!r}")


def apply_artist_changes(changes: Sequence[ArtistChange]) -> None:
    """Apply already-prepared cross-renderer mapping changes."""

    for change in changes:
        _set_output(change.artist, change.target, change.output)


def rollback_artist_changes(changes: Sequence[ArtistChange]) -> None:
    """Restore mapped artist properties in reverse mutation order."""

    for change in reversed(changes):
        _set_output(change.artist, change.target, change.previous)


def _converter(axis: object) -> object:
    getter = getattr(axis, "get_converter", None)
    return getter() if callable(getter) else getattr(axis, "converter", None)


def _units(axis: object) -> object:
    getter = getattr(axis, "get_units", None)
    return getter() if callable(getter) else getattr(axis, "units", None)


def _capture_cycle(generator: object) -> _CycleSnapshot:
    old_cycle = getattr(generator, "prop_cycler", None)
    modern_cycle = getattr(generator, "_prop_cycle", None)
    index = getattr(modern_cycle, "_idx", getattr(generator, "_idx", None))
    return _CycleSnapshot(index, copy(old_cycle) if old_cycle is not None else None)


def capture_axes(ax: Axes) -> AxesSnapshot:
    """Capture all axes state semantic drawing may mutate."""

    return AxesSnapshot(
        tuple(ax.lines),
        tuple(ax.collections),
        np.asarray(ax.dataLim.get_points()).copy(),
        np.asarray(ax.viewLim.get_points()).copy(),
        _converter(ax.xaxis),
        _converter(ax.yaxis),
        _units(ax.xaxis),
        _units(ax.yaxis),
        ax.xaxis.get_major_locator(),
        ax.xaxis.get_major_formatter(),
        ax.xaxis.get_minor_locator(),
        ax.xaxis.get_minor_formatter(),
        ax.yaxis.get_major_locator(),
        ax.yaxis.get_major_formatter(),
        ax.yaxis.get_minor_locator(),
        ax.yaxis.get_minor_formatter(),
        ax.get_xlabel(),
        ax.get_ylabel(),
        bool(
            getattr(
                ax,
                "ignore_existing_data_limits",
                getattr(ax, "_ignore_existing_data_limits", False),
            )
        ),
        dict(getattr(ax, "_stale_viewlims", {})),
        _capture_cycle(cast(Any, ax)._get_lines),
        _capture_cycle(cast(Any, ax)._get_patches_for_fill),
        ax.stale,
    )


def _restore_axis_units(axis: object, converter: object, units: object) -> None:
    set_converter = getattr(axis, "set_converter", None)
    if callable(set_converter):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="This axis already has a converter set.*",
                category=UserWarning,
            )
            set_converter(converter)
    else:  # pragma: no cover - Matplotlib 3.7 compatibility fallback
        cast(Any, axis).converter = converter
    set_units = getattr(axis, "set_units", None)
    if callable(set_units):
        set_units(units)
    else:  # pragma: no cover - Matplotlib 3.7 compatibility fallback
        cast(Any, axis).units = units


def _restore_cycle(generator: object, snapshot: _CycleSnapshot) -> None:
    if snapshot.index is not None:
        modern_cycle = getattr(generator, "_prop_cycle", None)
        if modern_cycle is not None:
            modern_cycle._idx = snapshot.index
        else:  # pragma: no cover - Matplotlib compatibility fallback
            cast(Any, generator)._idx = snapshot.index
    if snapshot.property_cycle is not None:
        cast(Any, generator).prop_cycler = snapshot.property_cycle


def restore_axes(ax: Axes, snapshot: AxesSnapshot) -> None:
    """Remove new artists and restore units, limits, formatters, and cycles."""

    original_lines = set(snapshot.lines)
    for line_artist in tuple(ax.lines):
        if line_artist not in original_lines:
            line_artist.remove()
    original_collections = set(snapshot.collections)
    for collection_artist in tuple(ax.collections):
        if collection_artist not in original_collections:
            collection_artist.remove()
    ax.dataLim.set_points(snapshot.data_limits)
    ax.viewLim.set_points(snapshot.view_limits)
    _restore_axis_units(ax.xaxis, snapshot.x_converter, snapshot.x_units)
    _restore_axis_units(ax.yaxis, snapshot.y_converter, snapshot.y_units)
    ax.xaxis.set_major_locator(cast(Any, snapshot.x_major_locator))
    ax.xaxis.set_major_formatter(cast(Any, snapshot.x_major_formatter))
    ax.xaxis.set_minor_locator(cast(Any, snapshot.x_minor_locator))
    ax.xaxis.set_minor_formatter(cast(Any, snapshot.x_minor_formatter))
    ax.yaxis.set_major_locator(cast(Any, snapshot.y_major_locator))
    ax.yaxis.set_major_formatter(cast(Any, snapshot.y_major_formatter))
    ax.yaxis.set_minor_locator(cast(Any, snapshot.y_minor_locator))
    ax.yaxis.set_minor_formatter(cast(Any, snapshot.y_minor_formatter))
    ax.set_xlabel(snapshot.x_label)
    ax.set_ylabel(snapshot.y_label)
    if hasattr(ax, "ignore_existing_data_limits"):
        cast(Any, ax).ignore_existing_data_limits = snapshot.ignore_existing_data_limits
    else:  # pragma: no cover - Matplotlib compatibility fallback
        cast(Any, ax)._ignore_existing_data_limits = (
            snapshot.ignore_existing_data_limits
        )
    if hasattr(ax, "_stale_viewlims"):
        cast(Any, ax)._stale_viewlims = dict(snapshot.stale_view_limits)
    _restore_cycle(cast(Any, ax)._get_lines, snapshot.line_cycle)
    _restore_cycle(cast(Any, ax)._get_patches_for_fill, snapshot.patch_cycle)
    ax.stale = snapshot.stale


def date_handle(ax: Axes) -> object | None:
    """Return an existing ggstyle date handle without creating one."""

    return getattr(ax, "_ggstyle_date_axis", None)


def scales_for(
    plan: SemanticPlan | None, layer_id: str
) -> Mapping[str, AestheticScale]:
    """Return read-only trained scales used by one layer."""

    if plan is None:
        return MappingProxyType({})
    layer_keys = {
        assignment.key for assignment in plan.assignments if assignment.layer_id == layer_id
    }
    return MappingProxyType(
        {
            entry.key.aesthetic: cast(AestheticScale, entry.scale)
            for entry in plan.scales
            if entry.key in layer_keys
        }
    )
