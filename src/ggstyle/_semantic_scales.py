"""Pure immutable policy for v0.5 semantic aesthetic scales."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from numbers import Real
from typing import Any, Literal, TypeAlias, cast

import numpy as np
import pandas as pd

from ._inspection import describe, json_safe
from .palettes import Palette, palette

Aesthetic = Literal["color", "linestyle"]
MissingPolicy = Literal["map", "drop", "raise"]
InfinitePolicy = Literal["clip", "color", "drop", "raise"]
ScaleKind = Literal["discrete", "continuous"]

_LINESTYLES = ("solid", "dashed", "dashdot", "dotted")


def _is_missing(value: object) -> bool:
    if value is None or value is pd.NA:
        return True
    try:
        result = pd.isna(cast(Any, value))
    except (TypeError, ValueError):
        return False
    return isinstance(result, (bool, np.bool_)) and bool(result)


def _nonempty_text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, got {value!r}")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _missing_policy(value: object) -> MissingPolicy:
    if value not in ("map", "drop", "raise"):
        raise ValueError(f"missing must be 'map', 'drop', or 'raise', got {value!r}")
    return cast(MissingPolicy, value)


def _hex_color(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a '#RRGGBB' string, got {value!r}")
    if len(value) != 7 or not value.startswith("#"):
        raise ValueError(f"{name} must use '#RRGGBB' form, got {value!r}")
    try:
        int(value[1:], 16)
    except ValueError as error:
        raise ValueError(f"{name} must use '#RRGGBB' form, got {value!r}") from error
    return value.upper()


def _category(value: object) -> object:
    if _is_missing(value):
        raise ValueError("missing values cannot be discrete scale levels")
    try:
        hash(value)
    except TypeError as error:
        raise TypeError(
            f"discrete values must be hashable scalars, got {value!r}"
        ) from error
    return value


def _unique(values: Iterable[object]) -> tuple[object, ...]:
    result: list[object] = []
    for value in values:
        if not any(value == existing for existing in result):
            result.append(value)
    return tuple(result)


@dataclass(frozen=True)
class DiscreteScaleSpec:
    """Immutable policy for one discrete color or line-style mapping."""

    aesthetic: Aesthetic = "color"
    values: tuple[str, ...] | None = None
    order: tuple[object, ...] | None = None
    include_unobserved: bool = False
    missing: MissingPolicy = "map"
    missing_value: str | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if self.aesthetic not in ("color", "linestyle"):
            raise ValueError(
                "discrete aesthetic must be 'color' or 'linestyle', "
                f"got {self.aesthetic!r}"
            )
        if not isinstance(self.include_unobserved, bool):
            raise TypeError("include_unobserved must be a bool")
        if self.name is not None:
            _nonempty_text("name", self.name)
        policy = _missing_policy(self.missing)
        object.__setattr__(self, "missing", policy)

        default_values = (
            palette("qualitative").colors
            if self.aesthetic == "color"
            else _LINESTYLES
        )
        resolved_values = tuple(default_values if self.values is None else self.values)
        if not resolved_values:
            raise ValueError("discrete scale values must not be empty")
        if self.aesthetic == "color":
            if len(resolved_values) > 8:
                raise ValueError(
                    "discrete color scales support at most 8 values; use direct "
                    "labels, facets, or another aesthetic"
                )
            resolved_values = tuple(
                _hex_color("discrete color", value) for value in resolved_values
            )
            default_missing = palette("qualitative").missing_color
        else:
            invalid = [value for value in resolved_values if value not in _LINESTYLES]
            if invalid:
                raise ValueError(
                    f"linestyle values must be chosen from {_LINESTYLES}, got {invalid!r}"
                )
            default_missing = "solid"
        if len(set(resolved_values)) != len(resolved_values):
            raise ValueError("discrete scale values must be unique")
        object.__setattr__(self, "values", resolved_values)

        if self.order is not None:
            resolved_order = tuple(_category(value) for value in self.order)
            if len(_unique(resolved_order)) != len(resolved_order):
                raise ValueError("discrete scale order must contain unique levels")
            if len(resolved_order) > len(resolved_values):
                raise ValueError(
                    f"discrete scale order has {len(resolved_order)} levels but only "
                    f"{len(resolved_values)} aesthetic values"
                )
            object.__setattr__(self, "order", resolved_order)

        if policy == "map":
            missing_value = (
                default_missing if self.missing_value is None else self.missing_value
            )
            if self.aesthetic == "color":
                missing_value = _hex_color("missing_value", missing_value)
            elif missing_value not in _LINESTYLES:
                raise ValueError(
                    f"missing_value must be chosen from {_LINESTYLES}, "
                    f"got {missing_value!r}"
                )
            object.__setattr__(self, "missing_value", missing_value)
        elif self.missing_value is not None:
            raise ValueError("missing_value requires missing='map'")

    @property
    def kind(self) -> ScaleKind:
        return "discrete"

    def with_order(self, order: Sequence[object]) -> DiscreteScaleSpec:
        """Return an equivalent spec with an explicit category order."""

        return DiscreteScaleSpec(
            aesthetic=self.aesthetic,
            values=self.values,
            order=tuple(order),
            include_unobserved=self.include_unobserved,
            missing=self.missing,
            missing_value=self.missing_value,
            name=self.name,
        )


@dataclass(frozen=True)
class ContinuousScaleSpec:
    """Immutable policy for one continuous color mapping."""

    aesthetic: Literal["color"] = "color"
    palette: Palette = field(default_factory=lambda: palette("sequential"))
    limits: tuple[float, float] | None = None
    missing: MissingPolicy = "map"
    infinite: InfinitePolicy = "raise"
    name: str | None = None

    def __post_init__(self) -> None:
        if self.aesthetic != "color":
            raise ValueError("continuous scales support only the 'color' aesthetic")
        if not isinstance(self.palette, Palette):
            raise TypeError(f"palette must be a Palette, got {type(self.palette).__name__}")
        if self.palette.kind == "qualitative":
            raise ValueError("continuous scales require a sequential or diverging palette")
        object.__setattr__(self, "missing", _missing_policy(self.missing))
        if self.infinite not in ("clip", "color", "drop", "raise"):
            raise ValueError(
                "infinite must be 'clip', 'color', 'drop', or 'raise', "
                f"got {self.infinite!r}"
            )
        if self.infinite == "color" and self.palette.out_of_bounds != "color":
            raise ValueError(
                "infinite='color' requires a palette with out_of_bounds='color'"
            )
        if self.name is not None:
            _nonempty_text("name", self.name)
        if self.limits is not None:
            if not isinstance(self.limits, tuple) or len(self.limits) != 2:
                raise TypeError("limits must be a (lower, upper) tuple")
            lower = _finite_number("lower limit", self.limits[0])
            upper = _finite_number("upper limit", self.limits[1])
            if lower >= upper:
                raise ValueError("continuous scale limits require lower < upper")
            object.__setattr__(self, "limits", (lower, upper))

    @property
    def kind(self) -> ScaleKind:
        return "continuous"


ScaleSpec: TypeAlias = DiscreteScaleSpec | ContinuousScaleSpec


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number, got {value!r}")
    resolved = float(value)
    if not math.isfinite(resolved):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return resolved


@dataclass(frozen=True)
class TrainedDiscreteScale:
    """A discrete scale with stable levels and aesthetic assignments."""

    spec: DiscreteScaleSpec
    levels: tuple[object, ...]
    outputs: tuple[str, ...]

    @property
    def kind(self) -> ScaleKind:
        return "discrete"

    def map_one(self, value: object) -> str | None:
        """Map one category according to the trained scale."""

        if _is_missing(value):
            if self.spec.missing == "raise":
                raise ValueError("discrete mapping contains a missing value")
            return self.spec.missing_value if self.spec.missing == "map" else None
        for level, output in zip(self.levels, self.outputs, strict=True):
            if value == level:
                return output
        raise ValueError(f"untrained discrete level {value!r}")

    def map_values(self, values: Iterable[object]) -> tuple[str | None, ...]:
        """Map values without changing their order."""

        return tuple(self.map_one(value) for value in values)

    def as_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe trained-scale policy."""

        return {
            "aesthetic": self.spec.aesthetic,
            "kind": self.kind,
            "levels": cast(list[object], json_safe(self.levels)),
            "missing": self.spec.missing,
            "missing_value": self.spec.missing_value,
            "name": self.spec.name,
            "outputs": list(self.outputs),
        }

    def describe(self) -> str:
        """Return strict JSON describing the trained scale."""

        return describe(self.as_dict())


@dataclass(frozen=True)
class TrainedContinuousScale:
    """A continuous color scale with one trained numeric domain."""

    spec: ContinuousScaleSpec
    domain: tuple[float, float]

    @property
    def kind(self) -> ScaleKind:
        return "continuous"

    def map_one(self, value: object) -> str | None:
        """Map one numeric value according to the trained scale."""

        if _is_missing(value):
            if self.spec.missing == "raise":
                raise ValueError("continuous mapping contains a missing value")
            return (
                self.spec.palette.missing_color if self.spec.missing == "map" else None
            )
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"continuous values must be real numbers, got {value!r}")
        resolved = float(value)
        if math.isinf(resolved):
            if self.spec.infinite == "raise":
                raise ValueError(f"continuous mapping contains infinity: {value!r}")
            if self.spec.infinite == "drop":
                return None
            position = -1.0 if resolved < 0 else 2.0
            if self.spec.infinite == "clip":
                position = 0.0 if resolved < 0 else 1.0
            return self.spec.palette.at(position)

        lower, upper = self.domain
        if lower == upper:
            position = 0.5 if resolved == lower else (-1.0 if resolved < lower else 2.0)
        else:
            position = (resolved - lower) / (upper - lower)
        return self.spec.palette.at(position)

    def map_values(self, values: Iterable[object]) -> tuple[str | None, ...]:
        """Map values without changing their order."""

        return tuple(self.map_one(value) for value in values)

    def as_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe trained-scale policy."""

        return {
            "aesthetic": self.spec.aesthetic,
            "domain": list(self.domain),
            "infinite": self.spec.infinite,
            "kind": self.kind,
            "missing": self.spec.missing,
            "missing_color": self.spec.palette.missing_color,
            "name": self.spec.name,
            "out_of_bounds": self.spec.palette.out_of_bounds,
            "palette": self.spec.palette.name,
        }

    def describe(self) -> str:
        """Return strict JSON describing the trained scale."""

        return describe(self.as_dict())


TrainedScale: TypeAlias = TrainedDiscreteScale | TrainedContinuousScale


def train_discrete(
    spec: DiscreteScaleSpec,
    batches: Iterable[Iterable[object]],
) -> TrainedDiscreteScale:
    """Train one discrete scale across every participating layer batch."""

    aesthetic_values = cast(tuple[str, ...], spec.values)
    observed: list[object] = []
    saw_missing = False
    for batch in batches:
        for value in batch:
            if _is_missing(value):
                saw_missing = True
                continue
            category = _category(value)
            if not any(category == existing for existing in observed):
                observed.append(category)
                if len(observed) > len(aesthetic_values):
                    raise ValueError(
                        f"{spec.aesthetic} scale supports at most "
                        f"{len(aesthetic_values)} levels; observed {len(observed)}"
                    )

    if saw_missing and spec.missing == "raise":
        raise ValueError("discrete mapping contains a missing value")
    if spec.order is None:
        levels = tuple(observed)
    else:
        unknown = [
            value
            for value in observed
            if not any(value == level for level in spec.order)
        ]
        if unknown:
            raise ValueError(f"observed levels are absent from explicit order: {unknown!r}")
        levels = (
            spec.order
            if spec.include_unobserved
            else tuple(
                level
                for level in spec.order
                if any(level == value for value in observed)
            )
        )

    return TrainedDiscreteScale(
        spec,
        levels,
        aesthetic_values[: len(levels)],
    )


def train_continuous(
    spec: ContinuousScaleSpec,
    batches: Iterable[Iterable[object]],
) -> TrainedContinuousScale:
    """Train one continuous scale across every participating layer batch."""

    finite: list[float] = []
    saw_missing = False
    saw_infinite = False
    for batch in batches:
        for value in batch:
            if _is_missing(value):
                saw_missing = True
                continue
            if isinstance(value, bool) or not isinstance(value, Real):
                raise TypeError(f"continuous values must be real numbers, got {value!r}")
            resolved = float(value)
            if math.isinf(resolved):
                saw_infinite = True
            else:
                finite.append(resolved)

    if saw_missing and spec.missing == "raise":
        raise ValueError("continuous mapping contains a missing value")
    if saw_infinite and spec.infinite == "raise":
        raise ValueError("continuous mapping contains infinity")
    if spec.limits is not None:
        domain = spec.limits
    elif finite:
        domain = (min(finite), max(finite))
    else:
        raise ValueError(
            "continuous scale has no finite values; provide explicit limits or data"
        )
    return TrainedContinuousScale(spec, domain)


def train_scale(
    spec: ScaleSpec,
    batches: Iterable[Iterable[object]],
) -> TrainedScale:
    """Train a concrete scale using every supplied layer batch."""

    if isinstance(spec, DiscreteScaleSpec):
        return train_discrete(spec, batches)
    return train_continuous(spec, batches)
