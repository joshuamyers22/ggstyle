"""Tick cadence, position, and label planning independent of axis mutation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from . import _cadence, _coordinates, _formats, _tick_positions
from ._date_summary import minor_below
from ._timezones import apply_display_timezone


@dataclass(frozen=True)
class TickPlan:
    positions: np.ndarray
    labels: list[str]
    minor_positions: np.ndarray | None
    minor_labels: list[str] | None


def resolve_major(spec: Any, span: pd.Timedelta) -> _cadence.Cadence:
    """Resolve automatic, count-based, or explicit major cadence policy."""
    if spec is None:
        return _cadence.auto_cadence(span)[0]
    if isinstance(spec, tuple) and spec[0] == "count":
        return _cadence.best_for_count(span, spec[1])
    return spec


def resolve_minor(
    spec: Any,
    major_spec: Any,
    span: pd.Timedelta,
    major: _cadence.Cadence,
) -> _cadence.Cadence | None:
    """Resolve disabled, automatic, or explicit minor cadence policy."""
    if spec is None:
        return None
    if spec == "auto":
        if major_spec is None:
            return _cadence.auto_cadence(span)[1]
        return minor_below(major)
    return spec


def build_tick_plan(
    *,
    lo: pd.Timestamp,
    hi: pd.Timestamp,
    mode: _coordinates.CoordinateMode,
    knots: np.ndarray,
    major_spec: Any,
    minor_spec: Any,
    explicit_ticks: pd.DatetimeIndex | None,
    explicit_positions: np.ndarray | None,
    major_format: Any,
    minor_format: Any,
    timezone: str | None,
) -> TickPlan:
    """Build all tick positions and labels for a visible date range."""
    span = hi - lo
    minor_cadence = None
    if explicit_ticks is not None:
        if explicit_positions is None:
            raise ValueError("explicit tick positions are required")
        label_ts = explicit_ticks
        positions = explicit_positions
        unit = _cadence.auto_cadence(span)[0].unit
    else:
        major = resolve_major(major_spec, span)
        unit = major.unit
        label_ts, positions = _tick_positions.positions_for_cadence(
            major, lo, hi, mode=mode, knots=knots
        )
        minor_cadence = resolve_minor(minor_spec, major_spec, span, major)

    labels = _formats.resolve(major_format, unit)(
        list(apply_display_timezone(pd.DatetimeIndex(label_ts), timezone))
    )
    minor_positions = None
    minor_labels = None
    if minor_cadence is not None:
        minor_ts, minor_positions = _tick_positions.positions_for_cadence(
            minor_cadence, lo, hi, mode=mode, knots=knots
        )
        if minor_format is not False and minor_format is not None:
            minor_labels = _formats.resolve(minor_format, minor_cadence.unit)(
                list(apply_display_timezone(pd.DatetimeIndex(minor_ts), timezone))
            )

    return TickPlan(positions, labels, minor_positions, minor_labels)
