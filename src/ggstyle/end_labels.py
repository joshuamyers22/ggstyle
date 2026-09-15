"""Pure policy and preflight planning for line endpoint labels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias, cast

import numpy as np
from matplotlib.axes import Axes
from matplotlib.lines import Line2D

__all__ = ["EndLabelSpec", "end_labels"]

CollisionPolicy: TypeAlias = Literal["avoid", "none"]
FallbackPolicy: TypeAlias = Literal["legend", "raise"]
EndLabelAction: TypeAlias = Literal["labels", "legend"]


@dataclass(frozen=True)
class EndLabelSpec:
    """
    Describe collision and fallback policy for line endpoint labels.

    Parameters
    ----------
    collision : {"avoid", "none"}, default "avoid"
        Resolve vertical overlap in display space, or retain exact endpoint positions.
    fallback : {"legend", "raise"}, default "legend"
        Use an ordinary Matplotlib legend when every participating artist cannot be
        labelled safely, or raise before mutating the axes.

    Notes
    -----
    The specification is immutable and retains no Matplotlib artists. Pass it to
    :func:`ggstyle.finish` through ``direct_labels=``.
    """

    collision: CollisionPolicy = "avoid"
    fallback: FallbackPolicy = "legend"

    def __post_init__(self) -> None:
        if not isinstance(self.collision, str):
            raise TypeError(
                f"collision must be a string, got {self.collision!r}"
            )
        if self.collision not in ("avoid", "none"):
            raise ValueError(
                "collision must be 'avoid' or 'none', "
                f"got {self.collision!r}"
            )
        if not isinstance(self.fallback, str):
            raise TypeError(f"fallback must be a string, got {self.fallback!r}")
        if self.fallback not in ("legend", "raise"):
            raise ValueError(
                "fallback must be 'legend' or 'raise', "
                f"got {self.fallback!r}"
            )


def end_labels(
    *,
    collision: CollisionPolicy = "avoid",
    fallback: FallbackPolicy = "legend",
) -> EndLabelSpec:
    """
    Create an immutable line endpoint-label specification.

    Parameters
    ----------
    collision : {"avoid", "none"}, default "avoid"
        Vertical collision policy.
    fallback : {"legend", "raise"}, default "legend"
        Policy for unsupported artists, invisible endpoints, or insufficient space.

    Returns
    -------
    EndLabelSpec
        Reusable policy that retains no Matplotlib artists.

    Examples
    --------
    >>> specification = end_labels(collision="avoid", fallback="legend")
    >>> specification.collision
    'avoid'
    """
    return EndLabelSpec(collision=collision, fallback=fallback)


@dataclass(frozen=True)
class _EndLabelCandidate:
    line: Line2D
    label: str
    endpoint: tuple[float, float]
    color: Any
    y_offset_points: float


@dataclass(frozen=True)
class _EndLabelPreparation:
    action: EndLabelAction
    candidates: tuple[_EndLabelCandidate, ...]
    diagnostics: tuple[str, ...] = ()


def _fallback_or_raise(
    specification: EndLabelSpec, reason: str
) -> _EndLabelPreparation:
    if specification.fallback == "raise":
        raise ValueError(f"direct labels cannot be applied safely: {reason}")
    return _EndLabelPreparation(
        action="legend",
        candidates=(),
        diagnostics=(f"Direct labels fell back to a legend: {reason}",),
    )


def _endpoint(line: Line2D) -> tuple[float, float] | None:
    try:
        values = np.asarray(line.get_xydata(), dtype=float)
    except (TypeError, ValueError):
        return None
    if values.ndim != 2 or values.shape[1] != 2 or not len(values):
        return None
    finite = np.isfinite(values).all(axis=1)
    if not finite.any():
        return None
    x_value, y_value = values[np.flatnonzero(finite)[-1]]
    return float(x_value), float(y_value)


def _axis_fraction(ax: Axes, axis_name: Literal["x", "y"], value: float) -> float:
    index = 0 if axis_name == "x" else 1
    matplotlib_axis = ax.xaxis if axis_name == "x" else ax.yaxis
    # Reading this private flag avoids triggering Matplotlib's lazy autoscaling during
    # a dry run. Keep that compatibility boundary isolated to this helper.
    stale = bool(ax._stale_viewlims[axis_name])  # type: ignore[attr-defined]
    if stale:
        interval = np.asarray(
            ax.dataLim.intervalx if axis_name == "x" else ax.dataLim.intervaly,
            dtype=float,
        )
    else:
        interval = np.asarray(
            ax.viewLim.intervalx if axis_name == "x" else ax.viewLim.intervaly,
            dtype=float,
        )
    transformed = np.asarray(
        matplotlib_axis.get_transform().transform(
            np.asarray([interval[0], value, interval[1]], dtype=float)
        ),
        dtype=float,
    )
    lower, position, upper = transformed
    if stale:
        if lower == upper:
            return 0.5
        margins = cast(tuple[float, float], ax.margins())
        margin = margins[index]
        expansion = (upper - lower) * margin
        lower -= expansion
        upper += expansion
    if not np.isfinite([lower, position, upper]).all() or lower == upper:
        return float("nan")
    return float((position - lower) / (upper - lower))


def _collision_offsets(
    desired: list[float], *, bottom: float, top: float, separation: float, dpi: float
) -> list[float] | None:
    if not desired:
        return []
    if separation * (len(desired) - 1) > top - bottom:
        return None

    order = sorted(range(len(desired)), key=lambda index: (desired[index], index))
    positions: list[float] = []
    for index in order:
        bounded = min(max(desired[index], bottom), top)
        positions.append(
            max(bounded, positions[-1] + separation) if positions else bounded
        )
    if positions[-1] > top:
        positions[-1] = top
        for index in range(len(positions) - 2, -1, -1):
            positions[index] = min(positions[index], positions[index + 1] - separation)
    if positions[0] < bottom:
        return None

    offsets = [0.0] * len(desired)
    for ordered_index, source_index in enumerate(order):
        offsets[source_index] = (
            positions[ordered_index] - desired[source_index]
        ) * 72 / dpi
    return offsets


def _prepare_end_labels(
    ax: Axes, specification: EndLabelSpec, *, font_size: float
) -> _EndLabelPreparation:
    handles, labels = ax.get_legend_handles_labels()
    participants = [
        (handle, label)
        for handle, label in zip(handles, labels, strict=True)
        if not hasattr(handle, "get_visible") or handle.get_visible()
    ]
    if not participants:
        raise ValueError(
            "direct labels require at least one visible artist with a public label"
        )

    raw: list[tuple[Line2D, str, tuple[float, float], Any, float]] = []
    unsupported: list[str] = []
    for handle, label in participants:
        description = f"{label!r} ({type(handle).__name__})"
        if not isinstance(handle, Line2D):
            unsupported.append(description)
            continue
        if ax.name != "rectilinear":
            unsupported.append(f"{description} is on a non-Cartesian axes")
            continue
        if handle.axes is not ax or handle.get_transform() is not ax.transData:
            unsupported.append(f"{description} does not use this axes' data transform")
            continue
        endpoint = _endpoint(handle)
        if endpoint is None:
            unsupported.append(f"{description} has no finite endpoint")
            continue
        x_fraction = _axis_fraction(ax, "x", endpoint[0])
        y_fraction = _axis_fraction(ax, "y", endpoint[1])
        if not np.isfinite([x_fraction, y_fraction]).all() or not (
            -1e-9 <= x_fraction <= 1 + 1e-9
            and -1e-9 <= y_fraction <= 1 + 1e-9
        ):
            unsupported.append(f"{description} has an endpoint outside the visible axes")
            continue
        display_y = float(ax.bbox.y0 + y_fraction * ax.bbox.height)
        raw.append((handle, label, endpoint, handle.get_color(), display_y))

    if unsupported:
        return _fallback_or_raise(specification, "; ".join(unsupported))

    offsets = [0.0] * len(raw)
    if specification.collision == "avoid":
        dpi = float(ax.figure.dpi)
        label_height = font_size * dpi / 72
        separation = label_height * 1.25
        half_height = label_height / 2
        resolved = _collision_offsets(
            [item[4] for item in raw],
            bottom=float(ax.bbox.y0) + half_height,
            top=float(ax.bbox.y1) - half_height,
            separation=separation,
            dpi=dpi,
        )
        if resolved is None:
            return _fallback_or_raise(
                specification,
                f"{len(raw)} labels do not fit in the available vertical space",
            )
        offsets = resolved

    candidates = tuple(
        _EndLabelCandidate(
            line=line,
            label=label,
            endpoint=endpoint,
            color=color,
            y_offset_points=offset,
        )
        for (line, label, endpoint, color, _), offset in zip(raw, offsets, strict=True)
    )
    return _EndLabelPreparation(action="labels", candidates=candidates)
