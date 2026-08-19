"""Tick label formats.

A *labeller* takes the full list of tick timestamps and returns the full list of
label strings. Working on the whole list rather than one tick at a time is what
makes ``"concise"`` possible: it can show the year once instead of on every
label, because it can see its neighbours.

Formats never influence tick placement. That orthogonality is enforced by tests.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pandas as pd

__all__ = ["PRESETS", "resolve", "base_preset_for"]

Labeller = Callable[[Sequence[pd.Timestamp]], list[str]]


def _quarter_of(ts: pd.Timestamp) -> int:
    return (ts.month - 1) // 3 + 1


#: Per-tick presets. Written as callables rather than strftime strings wherever
#: platform differences bite: ``%-d`` is not portable to Windows.
PRESETS: dict[str, Callable[[pd.Timestamp], str]] = {
    "iso": lambda d: f"{d:%Y-%m-%d}",
    "iso-datetime": lambda d: f"{d:%Y-%m-%d %H:%M}",
    "year": lambda d: f"{d:%Y}",
    "year-short": lambda d: f"'{d:%y}",
    "month": lambda d: f"{d:%b}",
    "month-year": lambda d: f"{d:%b} {d:%Y}",
    "month-num": lambda d: f"{d:%m}",
    "quarter-short": lambda d: f"Q{_quarter_of(d)}",
    "quarter": lambda d: f"Q{_quarter_of(d)} {d:%Y}",
    "day": lambda d: f"{d:%b} {d.day}",
    "day-num": lambda d: str(d.day),
    "weekday": lambda d: f"{d:%a} {d.day}",
    "weekday-name": lambda d: f"{d:%a}",
    "time": lambda d: f"{d:%H:%M}",
    "datetime": lambda d: f"{d:%b} {d.day} {d:%H:%M}",
}

#: Which preset ``"concise"`` starts from, per cadence unit.
_BASE_BY_UNIT = {
    "minute": "time",
    "hour": "time",
    "day": "day",
    "week": "day",
    "month": "month",
    "quarter": "quarter-short",
    "year": "year",
}


def base_preset_for(unit: str) -> str:
    """The preset ``"concise"`` uses as its starting point for ``unit``."""
    return _BASE_BY_UNIT.get(unit, "iso")


def _concise(ticks: Sequence[pd.Timestamp], unit: str) -> list[str]:
    """Base label per tick, with the larger unit added only where it changes.

    For date cadences that means the year appears on the first tick and at each
    year boundary. For intraday cadences it means the date appears at each day
    boundary, so a multi-session intraday plot stays readable without repeating
    the date on every label.
    """
    base = PRESETS[base_preset_for(unit)]
    labels: list[str] = []
    intraday = unit in ("minute", "hour")

    previous: pd.Timestamp | None = None
    for ts in ticks:
        text = base(ts)
        if intraday:
            changed = previous is None or ts.date() != previous.date()
            if changed:
                text = f"{ts:%b} {ts.day}\n{text}"
        elif unit != "year":
            changed = previous is None or ts.year != previous.year
            if changed:
                text = f"{text}\n{ts:%Y}"
        labels.append(text)
        previous = ts
    return labels


def resolve(spec, unit: str = "day") -> Labeller:
    """Turn a user-facing format spec into a labeller.

    Accepts:

    * ``None`` or ``"concise"`` -- context-aware default
    * a preset name from :data:`PRESETS`
    * a strftime string (anything containing ``%``)
    * a callable taking a single ``Timestamp`` and returning a string
    """
    if spec is None or spec == "concise":
        return lambda ticks: _concise(ticks, unit)

    if callable(spec):
        return lambda ticks: [str(spec(ts)) for ts in ticks]

    if isinstance(spec, str):
        if spec in PRESETS:
            fn = PRESETS[spec]
            return lambda ticks: [fn(ts) for ts in ticks]
        if "%" in spec:
            return lambda ticks: [ts.strftime(spec) for ts in ticks]
        raise ValueError(
            f"unknown format {spec!r}; expected one of {sorted(PRESETS)}, "
            f"'concise', a strftime string, or a callable"
        )

    raise TypeError(f"cannot interpret {spec!r} as a tick format")
