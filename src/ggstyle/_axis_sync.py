"""Numerical policy for synchronizing multiple date axes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

AxisMode = Literal["show", "collapse"]
LimitMode = Literal["union", "intersection"]


@dataclass(frozen=True)
class SyncPlan:
    """Shared coordinates and bounds to apply to a collection of axes."""

    mode: AxisMode
    lower: float
    upper: float
    observations: FloatArray


def validate_options(mode: AxisMode | None, limits: LimitMode) -> None:
    """Validate synchronization options before axes are adopted."""
    if mode not in (None, "show", "collapse"):
        raise ValueError(f"mode must be 'show' or 'collapse', got {mode!r}")
    if limits not in ("union", "intersection"):
        raise ValueError(f"limits must be 'union' or 'intersection', got {limits!r}")


def plan(
    observations: list[FloatArray],
    modes: list[AxisMode],
    *,
    mode: AxisMode | None,
    limits: LimitMode,
) -> SyncPlan:
    """Build a synchronization plan without consulting Matplotlib objects."""
    validate_options(mode, limits)
    if not observations:
        raise ValueError("axes must contain at least one matplotlib Axes")

    existing_modes = set(modes)
    if mode is None and len(existing_modes) != 1:
        raise ValueError("axes use different modes; pass mode='show' or mode='collapse'")
    target_mode = mode or modes[0]

    ranges = [(values[0], values[-1]) for values in observations]
    if limits == "union":
        lower = min(item[0] for item in ranges)
        upper = max(item[1] for item in ranges)
    else:
        lower = max(item[0] for item in ranges)
        upper = min(item[1] for item in ranges)
        if lower > upper:
            raise ValueError("axes have no overlapping observation range")

    return SyncPlan(
        target_mode,
        float(lower),
        float(upper),
        np.unique(np.concatenate(observations)),
    )
