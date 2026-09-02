"""Pure configuration policy for date-axis major and minor ticks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from . import _cadence
from ._frames import to_datetime_index


@dataclass(frozen=True)
class TickConfiguration:
    """Resolved tick state ready to apply atomically to a date axis."""

    major_spec: Any
    minor_spec: Any
    explicit_ticks: pd.DatetimeIndex | None


def resolve_tick_configuration(
    *,
    current_major: Any,
    current_minor: Any,
    current_explicit: pd.DatetimeIndex | None,
    spec: Any = None,
    every: Any = None,
    n: int | None = None,
    at: Iterable[Any] | None = None,
    major: Any = None,
    minor: Any = None,
) -> TickConfiguration:
    """Validate one tick request and return its complete resulting state."""

    given = [value for value in (spec, every, n, at, major) if value is not None]
    if len(given) > 1:
        raise TypeError("pass only one of spec, every=, n=, at=, or major= to ticks()")

    major_spec = current_major
    minor_spec = current_minor
    explicit_ticks = current_explicit
    if at is not None:
        explicit_ticks = to_datetime_index(at)
        major_spec = None
    elif n is not None:
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError(f"n must be a positive integer, got {n!r}")
        explicit_ticks = None
        major_spec = ("count", n)
    elif every is not None:
        explicit_ticks = None
        major_spec = _cadence.resolve(every)
    elif spec is not None or major is not None:
        explicit_ticks = None
        value = spec if spec is not None else major
        major_spec = None if value == "auto" else _cadence.resolve(value)

    if minor is not None:
        if minor == "auto":
            minor_spec = "auto"
        elif minor is False:
            minor_spec = None
        else:
            minor_spec = _cadence.resolve(minor)

    return TickConfiguration(major_spec, minor_spec, explicit_ticks)
