"""Public immutable configuration for semantic aesthetic scales."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from ._semantic_scales import (
    Aesthetic,
    ContinuousScaleSpec,
    DiscreteScaleSpec,
    InfinitePolicy,
    MissingPolicy,
    _category,
)
from .palettes import Palette, palette

__all__ = ["AestheticScale", "ContinuousScale", "DiscreteScale"]


class AestheticScale(Protocol):
    """Public inspection boundary for a trained semantic scale."""

    @property
    def kind(self) -> Literal["discrete", "continuous"]:
        """Return whether the trained scale is discrete or continuous."""

    def as_dict(self) -> dict[str, object]:
        """Return the trained scale as deterministic JSON-compatible data."""

    def describe(self) -> str:
        """Return a deterministic strict-JSON description of the scale."""


def _optional_name(value: object) -> None:
    if value is not None and not isinstance(value, str):
        raise TypeError(f"name must be a non-empty string or None, got {value!r}")
    if isinstance(value, str) and not value.strip():
        raise ValueError("name must not be empty")


@dataclass(frozen=True)
class DiscreteScale:
    """Configure a reusable discrete color or linestyle mapping.

    Parameters
    ----------
    values : tuple of str or None, optional
        Ordered output values. Use ``#RRGGBB`` colors for ``color_scale=`` or
        ``solid``, ``dashed``, ``dashdot``, and ``dotted`` for
        ``linestyle_scale=``. ``None`` uses ggstyle's accessible defaults.
    order : tuple of object or None, optional
        Explicit category order. Observations outside it are errors.
    include_unobserved : bool, default False
        Retain explicit or pandas categorical levels absent from the current data.
    missing : {"map", "drop", "raise"}, default "map"
        Missing-value policy.
    missing_value : str or None, optional
        Output used when ``missing="map"``. The aesthetic default is used when
        omitted.
    name : str or None, optional
        Guide title. The mapped source-column name is used when omitted.

    Notes
    -----
    The policy is axes-independent and immutable. Context-specific validation, such
    as hexadecimal colors versus named line styles, occurs when the policy is applied
    to a mapped aesthetic.
    """

    values: tuple[str, ...] | None = None
    order: tuple[object, ...] | None = None
    include_unobserved: bool = False
    missing: MissingPolicy = "map"
    missing_value: str | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if self.values is not None:
            values = tuple(self.values)
            if not values:
                raise ValueError("discrete scale values must not be empty")
            if not all(isinstance(value, str) for value in values):
                raise TypeError("discrete scale values must be strings")
            if len(set(values)) != len(values):
                raise ValueError("discrete scale values must be unique")
            if len(values) > 8:
                raise ValueError("discrete scales support at most 8 values")
            object.__setattr__(self, "values", values)
        if self.order is not None:
            order = tuple(_category(value) for value in self.order)
            if len(order) > 8:
                raise ValueError("discrete scale order supports at most 8 levels")
            if len(set(order)) != len(order):
                raise ValueError("discrete scale order must contain unique levels")
            object.__setattr__(self, "order", order)
        if not isinstance(self.include_unobserved, bool):
            raise TypeError("include_unobserved must be a bool")
        if self.missing not in ("map", "drop", "raise"):
            raise ValueError(
                "missing must be 'map', 'drop', or 'raise', "
                f"got {self.missing!r}"
            )
        if self.missing_value is not None and not isinstance(self.missing_value, str):
            raise TypeError("missing_value must be a string or None")
        if self.missing != "map" and self.missing_value is not None:
            raise ValueError("missing_value requires missing='map'")
        _optional_name(self.name)


@dataclass(frozen=True)
class ContinuousScale:
    """Configure a reusable continuous color mapping.

    Parameters
    ----------
    palette : Palette, optional
        Sequential or diverging palette policy.
    limits : tuple of float or None, optional
        Explicit lower and upper data-domain limits. Automatic training uses the
        finite union of all participating layers.
    missing : {"map", "drop", "raise"}, default "map"
        Missing-value policy.
    infinite : {"clip", "color", "drop", "raise"}, default "raise"
        Policy for positive and negative infinity.
    name : str or None, optional
        Guide title. The mapped source-column name is used when omitted.
    """

    palette: Palette = field(default_factory=lambda: palette("sequential"))
    limits: tuple[float, float] | None = None
    missing: MissingPolicy = "map"
    infinite: InfinitePolicy = "raise"
    name: str | None = None

    def __post_init__(self) -> None:
        resolved = ContinuousScaleSpec(
            palette=self.palette,
            limits=self.limits,
            missing=self.missing,
            infinite=self.infinite,
            name=self.name,
        )
        object.__setattr__(self, "palette", resolved.palette)
        object.__setattr__(self, "limits", resolved.limits)
        object.__setattr__(self, "missing", resolved.missing)


def _resolve_discrete(scale: DiscreteScale, aesthetic: Aesthetic) -> DiscreteScaleSpec:
    return DiscreteScaleSpec(
        aesthetic=aesthetic,
        values=scale.values,
        order=scale.order,
        include_unobserved=scale.include_unobserved,
        missing=scale.missing,
        missing_value=scale.missing_value,
        name=scale.name,
    )


def _resolve_continuous(scale: ContinuousScale) -> ContinuousScaleSpec:
    return ContinuousScaleSpec(
        palette=scale.palette,
        limits=scale.limits,
        missing=scale.missing,
        infinite=scale.infinite,
        name=scale.name,
    )
