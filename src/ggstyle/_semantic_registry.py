"""Axes-owned transactional registry for semantic aesthetic mappings."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, TypeVar
from weakref import WeakKeyDictionary

import pandas as pd
from matplotlib.axes import Axes

from ._inspection import describe, json_safe
from ._semantic_scales import (
    Aesthetic,
    ContinuousScaleSpec,
    DiscreteScaleSpec,
    ScaleSpec,
    TrainedDiscreteScale,
    TrainedScale,
    train_scale,
)

_Result = TypeVar("_Result")


def _text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, got {value!r}")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


@dataclass(frozen=True, order=True)
class ScaleKey:
    """Identity of one trained mapping shared by participating layers."""

    aesthetic: Aesthetic
    variable: str

    def __post_init__(self) -> None:
        if self.aesthetic not in ("color", "linestyle"):
            raise ValueError(f"unsupported semantic aesthetic {self.aesthetic!r}")
        _text("variable", self.variable)

    def as_dict(self) -> dict[str, str]:
        """Return the scale identity as plain data."""

        return {"aesthetic": self.aesthetic, "variable": self.variable}


@dataclass(frozen=True)
class MappingRequest:
    """One layer's immutable contribution to an aesthetic scale."""

    layer_id: str
    variable: str
    scale: ScaleSpec
    values: tuple[object, ...]

    def __post_init__(self) -> None:
        _text("layer_id", self.layer_id)
        _text("variable", self.variable)
        if not isinstance(self.scale, (DiscreteScaleSpec, ContinuousScaleSpec)):
            raise TypeError(
                "scale must be a DiscreteScaleSpec or ContinuousScaleSpec, "
                f"got {type(self.scale).__name__}"
            )
        object.__setattr__(self, "values", tuple(self.values))

    @classmethod
    def from_values(
        cls,
        layer_id: str,
        variable: str,
        scale: ScaleSpec,
        values: Iterable[object],
    ) -> MappingRequest:
        """Create a request, preserving declared pandas categorical order."""

        resolved_scale = scale
        dtype = getattr(values, "dtype", None)
        if (
            isinstance(scale, DiscreteScaleSpec)
            and scale.order is None
            and isinstance(dtype, pd.CategoricalDtype)
        ):
            categorical: Any = getattr(values, "cat", values)
            categories = categorical.categories
            resolved_scale = scale.with_order(tuple(categories))
        return cls(layer_id, variable, resolved_scale, tuple(values))

    @property
    def aesthetic(self) -> Aesthetic:
        """Return the aesthetic trained by this request."""

        return self.scale.aesthetic

    @property
    def key(self) -> ScaleKey:
        """Return the shared scale identity for this request."""

        return ScaleKey(self.aesthetic, self.variable)

    @property
    def contribution_key(self) -> tuple[str, Aesthetic]:
        """Return the layer-local uniqueness key."""

        return self.layer_id, self.aesthetic


@dataclass(frozen=True)
class ScaleEntry:
    """One trained scale and its registry identity."""

    key: ScaleKey
    scale: TrainedScale

    def as_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe trained-scale state."""

        return {"key": self.key.as_dict(), "scale": self.scale.as_dict()}


@dataclass(frozen=True)
class MappingAssignment:
    """Mapped output prepared for one layer and aesthetic."""

    layer_id: str
    key: ScaleKey
    outputs: tuple[str | None, ...]

    def as_dict(self) -> dict[str, object]:
        """Return bounded inspection data without copying every output."""

        return {
            "dropped": sum(output is None for output in self.outputs),
            "key": self.key.as_dict(),
            "layer_id": self.layer_id,
            "output_count": len(self.outputs),
        }


@dataclass(frozen=True)
class SemanticPlan:
    """Complete trained registry state prepared before any artist is drawn."""

    owner: object = field(repr=False)
    base_revision: int
    revision: int
    contributions: tuple[MappingRequest, ...]
    scales: tuple[ScaleEntry, ...]
    assignments: tuple[MappingAssignment, ...]
    added_layers: tuple[str, ...]
    replaced_layers: tuple[str, ...]
    removed_layers: tuple[str, ...]
    diagnostics: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return deterministic strict-JSON registry inspection data."""

        layers = [
            {
                "aesthetic": request.aesthetic,
                "layer_id": request.layer_id,
                "scale_kind": request.scale.kind,
                "value_count": len(request.values),
                "variable": request.variable,
            }
            for request in self.contributions
        ]
        return {
            "assignments": [assignment.as_dict() for assignment in self.assignments],
            "base_revision": self.base_revision,
            "changes": {
                "added_layers": list(self.added_layers),
                "removed_layers": list(self.removed_layers),
                "replaced_layers": list(self.replaced_layers),
            },
            "diagnostics": list(self.diagnostics),
            "layers": cast_json(layers),
            "revision": self.revision,
            "scales": [entry.as_dict() for entry in self.scales],
        }

    def describe(self) -> str:
        """Return strict JSON describing the complete prepared state."""

        return describe(self.as_dict())


@dataclass(frozen=True)
class RegistrySnapshot:
    """Immutable committed registry state used for rollback."""

    owner: object = field(repr=False)
    revision: int
    contributions: tuple[MappingRequest, ...]
    scales: tuple[ScaleEntry, ...]
    assignments: tuple[MappingAssignment, ...]

    def as_dict(self) -> dict[str, object]:
        """Return bounded JSON-safe committed-state inspection."""

        return {
            "assignment_count": len(self.assignments),
            "layer_count": len({item.layer_id for item in self.contributions}),
            "revision": self.revision,
            "scales": [entry.as_dict() for entry in self.scales],
        }

    def describe(self) -> str:
        """Return strict JSON describing committed registry state."""

        return describe(self.as_dict())


def cast_json(value: object) -> object:
    """Narrow the shared inspection normalizer for typed dictionary values."""

    return json_safe(value)


class SemanticRegistry:
    """Revisioned mapping state owned by one live Matplotlib axes."""

    def __init__(self) -> None:
        self._owner = object()
        self._revision = 0
        self._contributions: tuple[MappingRequest, ...] = ()
        self._scales: tuple[ScaleEntry, ...] = ()
        self._assignments: tuple[MappingAssignment, ...] = ()
        self._applying = False

    @property
    def revision(self) -> int:
        """Return the current committed registry revision."""

        return self._revision

    @property
    def contributions(self) -> tuple[MappingRequest, ...]:
        """Return immutable committed layer contributions."""

        return self._contributions

    @property
    def scales(self) -> tuple[ScaleEntry, ...]:
        """Return immutable committed trained scales."""

        return self._scales

    @property
    def assignments(self) -> tuple[MappingAssignment, ...]:
        """Return immutable committed mapped outputs."""

        return self._assignments

    def prepare(
        self,
        additions: Iterable[MappingRequest] = (),
        *,
        remove_layers: Iterable[str] = (),
    ) -> SemanticPlan:
        """Train complete candidate state without mutating the registry."""

        additions = tuple(additions)
        removals = tuple(_text("remove layer", value) for value in remove_layers)
        if len(set(removals)) != len(removals):
            raise ValueError("remove_layers must not contain duplicates")
        overlapping_layers = {request.layer_id for request in additions} & set(removals)
        if overlapping_layers:
            names = ", ".join(sorted(overlapping_layers))
            raise ValueError(
                f"layers cannot be added and removed in one plan: {names}; "
                "replace their mappings through additions only"
            )
        addition_keys = [request.contribution_key for request in additions]
        if len(set(addition_keys)) != len(addition_keys):
            raise ValueError("one plan cannot map an aesthetic twice for the same layer")

        current = {item.contribution_key: item for item in self._contributions}
        old_layers = {item.layer_id for item in self._contributions}
        for layer_id in removals:
            current = {
                key: request
                for key, request in current.items()
                if request.layer_id != layer_id
            }
        replaced_layers = {
            request.layer_id
            for request in additions
            if request.contribution_key in current
        }
        for request in additions:
            current[request.contribution_key] = request

        contributions = tuple(current.values())
        grouped: dict[ScaleKey, list[MappingRequest]] = {}
        for request in contributions:
            grouped.setdefault(request.key, []).append(request)

        scales: list[ScaleEntry] = []
        assignments: list[MappingAssignment] = []
        for key in sorted(grouped):
            requests = grouped[key]
            specs = {request.scale for request in requests}
            if len(specs) != 1:
                layers = ", ".join(request.layer_id for request in requests)
                raise ValueError(
                    f"conflicting {key.aesthetic} scales for variable {key.variable!r} "
                    f"across layers: {layers}"
                )
            spec = requests[0].scale
            trained = train_scale(spec, (request.values for request in requests))
            scales.append(ScaleEntry(key, trained))
            assignments.extend(
                MappingAssignment(
                    request.layer_id,
                    key,
                    trained.map_values(request.values),
                )
                for request in requests
            )

        new_layers = {item.layer_id for item in contributions}
        added_layers = new_layers - old_layers
        removed_layers = old_layers - new_layers
        diagnostics = _diagnostics(scales)
        return SemanticPlan(
            owner=self._owner,
            base_revision=self._revision,
            revision=self._revision + 1,
            contributions=contributions,
            scales=tuple(scales),
            assignments=tuple(sorted(assignments, key=_assignment_sort_key)),
            added_layers=tuple(sorted(added_layers)),
            replaced_layers=tuple(sorted(replaced_layers)),
            removed_layers=tuple(sorted(removed_layers)),
            diagnostics=diagnostics,
        )

    def commit(self, plan: SemanticPlan) -> None:
        """Publish a fully trained, current plan as one registry revision."""

        if not isinstance(plan, SemanticPlan):
            raise TypeError(f"plan must be a SemanticPlan, got {type(plan).__name__}")
        if plan.owner is not self._owner:
            raise ValueError("semantic plan belongs to a different axes registry")
        if plan.base_revision != self._revision or plan.revision != self._revision + 1:
            raise RuntimeError(
                f"stale semantic plan for revision {plan.base_revision}; "
                f"current revision is {self._revision}"
            )
        self._contributions = plan.contributions
        self._scales = plan.scales
        self._assignments = plan.assignments
        self._revision = plan.revision

    def transact(
        self,
        plan: SemanticPlan,
        apply: Callable[[SemanticPlan], _Result],
        rollback: Callable[[], None],
    ) -> _Result:
        """Commit and apply a plan, restoring registry and caller state on failure."""

        if self._applying:
            raise RuntimeError("semantic registry transaction is already in progress")
        snapshot = self.snapshot()
        self._applying = True
        try:
            self.commit(plan)
            try:
                return apply(plan)
            except BaseException:
                try:
                    rollback()
                finally:
                    self.restore(snapshot)
                raise
        finally:
            self._applying = False

    def snapshot(self) -> RegistrySnapshot:
        """Capture the committed registry state for rollback or inspection."""

        return RegistrySnapshot(
            self._owner,
            self._revision,
            self._contributions,
            self._scales,
            self._assignments,
        )

    def restore(self, snapshot: RegistrySnapshot) -> None:
        """Restore an earlier immutable registry snapshot."""

        if not isinstance(snapshot, RegistrySnapshot):
            raise TypeError(
                f"snapshot must be a RegistrySnapshot, got {type(snapshot).__name__}"
            )
        if snapshot.owner is not self._owner:
            raise ValueError("semantic snapshot belongs to a different axes registry")
        self._revision = snapshot.revision
        self._contributions = snapshot.contributions
        self._scales = snapshot.scales
        self._assignments = snapshot.assignments

    def as_dict(self) -> dict[str, object]:
        """Return bounded strict-JSON committed-state inspection."""

        return self.snapshot().as_dict()

    def describe(self) -> str:
        """Return strict JSON describing committed registry state."""

        return describe(self.as_dict())


def _assignment_sort_key(assignment: MappingAssignment) -> tuple[str, str, str]:
    return assignment.layer_id, assignment.key.aesthetic, assignment.key.variable


def _diagnostics(scales: Iterable[ScaleEntry]) -> tuple[str, ...]:
    diagnostics: list[str] = []
    for entry in scales:
        trained = entry.scale
        if isinstance(trained, TrainedDiscreteScale) and len(trained.levels) > 6:
            diagnostics.append(
                f"{entry.key.aesthetic} mapping for {entry.key.variable!r} has "
                f"{len(trained.levels)} levels; prefer direct labels or facets"
            )
    return tuple(diagnostics)


_REGISTRIES: WeakKeyDictionary[Axes, SemanticRegistry] = WeakKeyDictionary()


def semantic_registry(ax: Axes) -> SemanticRegistry:
    """Return the one semantic registry weakly owned by ``ax``."""

    if not isinstance(ax, Axes):
        raise TypeError(f"ax must be a matplotlib Axes, got {type(ax).__name__}")
    registry = _REGISTRIES.get(ax)
    if registry is None:
        registry = SemanticRegistry()
        _REGISTRIES[ax] = registry
    return registry


def discard_semantic_registry(ax: Axes) -> None:
    """Discard semantic policy associated with an axes, if present."""

    _REGISTRIES.pop(ax, None)


def registry_count() -> int:
    """Return the number of live axes registries for lifecycle tests."""

    return len(_REGISTRIES)
