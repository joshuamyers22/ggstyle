"""Tick cadence: the spec object, named vocabulary, and the auto table.

A :class:`Cadence` is *where ticks go*. It says nothing about what the labels
look like — that is ``_formats``. Keeping these apart is the point: changing a
format must never move a tick.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from ._parse import to_offset

__all__ = ["LADDER", "Cadence", "auto_cadence", "resolve"]

_UNITS = ("minute", "hour", "day", "week", "month", "quarter", "year")

#: Approximate length of one unit, for span arithmetic and ladder search.
_UNIT_SECONDS = {
    "minute": 60.0,
    "hour": 3600.0,
    "day": 86400.0,
    "week": 604800.0,
    "month": 2629800.0,
    "quarter": 7889400.0,
    "year": 31557600.0,
}

#: Offset alias for each unit at each anchor.
_ALIAS = {
    ("minute", "start"): "min",
    ("minute", "end"): "min",
    ("hour", "start"): "h",
    ("hour", "end"): "h",
    ("day", "start"): "D",
    ("day", "end"): "D",
    ("week", "start"): "W-MON",
    ("week", "end"): "W-SUN",
    ("month", "start"): "MS",
    ("month", "end"): "ME",
    ("quarter", "start"): "QS",
    ("quarter", "end"): "QE",
    ("year", "start"): "YS",
    ("year", "end"): "YE",
}

#: Period alias for grouping observations, used in collapsed mode.
_PERIOD_ALIAS = {
    "minute": "min",
    "hour": "h",
    "day": "D",
    "week": "W",
    "month": "M",
    "quarter": "Q",
    "year": "Y",
}


@dataclass(frozen=True)
class Cadence:
    """
    Describe a recurring tick cadence.

    A cadence controls tick placement only. Label text is configured separately
    by :meth:`ggstyle.DateAxis.fmt`.

    Parameters
    ----------
    unit : {"minute", "hour", "day", "week", "month", "quarter", "year"}
        One of minute, hour, day, week, month, quarter, year.
    interval : int, default 1
        Every *n*-th unit.
    anchor : {"start", "end"}, default "start"
        ``"start"`` or ``"end"`` of each period. Month-start vs. month-end is the
        difference between labels that line up with observations and labels that
        float between them.

    Raises
    ------
    ValueError
        If the unit, interval, or anchor is invalid.

    See Also
    --------
    ggstyle.DateAxis.ticks : Apply a cadence to an axis.

    Examples
    --------
    >>> Cadence("month", interval=3)
    Cadence(unit='month', interval=3, anchor='start')
    """

    unit: str
    interval: int = 1
    anchor: str = "start"

    def __post_init__(self) -> None:
        if self.unit not in _UNITS:
            raise ValueError(
                f"unknown cadence unit {self.unit!r}; expected one of {_UNITS}"
            )
        if self.interval < 1:
            raise ValueError(f"interval must be >= 1, got {self.interval}")
        if self.anchor not in ("start", "end"):
            raise ValueError(f"anchor must be 'start' or 'end', got {self.anchor!r}")

    @property
    def freq(self) -> str:
        """Return the pandas offset alias used to generate ticks."""
        alias = _ALIAS[(self.unit, self.anchor)]
        return alias if self.interval == 1 else f"{self.interval}{alias}"

    @property
    def period_alias(self) -> str:
        """Return the pandas period alias used to group observations."""
        return _PERIOD_ALIAS[self.unit]

    @property
    def approx_seconds(self) -> float:
        """Return the approximate cadence duration in seconds."""
        return _UNIT_SECONDS[self.unit] * self.interval

    def __str__(self) -> str:  # pragma: no cover - display only
        every = "" if self.interval == 1 else f"{self.interval}x "
        return f"{every}{self.unit}[{self.anchor}]"


#: Named vocabulary. The bare names are the ones people reach for; the anchored
#: names exist because financial data cares which end of the period it lands on.
_NAMED = {
    "minutely": Cadence("minute"),
    "hourly": Cadence("hour"),
    "daily": Cadence("day"),
    "weekly": Cadence("week"),
    "monthly": Cadence("month"),
    "quarterly": Cadence("quarter"),
    "yearly": Cadence("year"),
    "annual": Cadence("year"),
    "annually": Cadence("year"),
    "week-start": Cadence("week", anchor="start"),
    "week-end": Cadence("week", anchor="end"),
    "month-start": Cadence("month", anchor="start"),
    "month-end": Cadence("month", anchor="end"),
    "quarter-start": Cadence("quarter", anchor="start"),
    "quarter-end": Cadence("quarter", anchor="end"),
    "year-start": Cadence("year", anchor="start"),
    "year-end": Cadence("year", anchor="end"),
}

#: Candidate cadences in increasing coarseness, searched when the caller asks
#: for "about n ticks".
LADDER: tuple[Cadence, ...] = (
    Cadence("minute", 1),
    Cadence("minute", 5),
    Cadence("minute", 15),
    Cadence("minute", 30),
    Cadence("hour", 1),
    Cadence("hour", 3),
    Cadence("hour", 6),
    Cadence("hour", 12),
    Cadence("day", 1),
    Cadence("day", 2),
    Cadence("week", 1),
    Cadence("week", 2),
    Cadence("month", 1),
    Cadence("month", 2),
    Cadence("month", 3),
    Cadence("month", 6),
    Cadence("year", 1),
    Cadence("year", 2),
    Cadence("year", 5),
    Cadence("year", 10),
    Cadence("year", 25),
)


def resolve(spec) -> Cadence:
    """Turn a user-facing cadence spec into a :class:`Cadence`.

    Accepts a :class:`Cadence`, a named string (``"quarterly"``,
    ``"month-end"``), or an offset alias (``"3M"``, ``"6ME"``, ``"2W"``).
    """
    if isinstance(spec, Cadence):
        return spec
    if not isinstance(spec, str):
        raise TypeError(f"cannot interpret {spec!r} as a cadence")

    key = spec.strip().lower()
    if key in _NAMED:
        return _NAMED[key]
    return _from_alias(spec.strip())


def _from_alias(alias: str) -> Cadence:
    """Interpret an offset alias such as ``"3M"`` or ``"6ME"`` as a Cadence."""
    offset = to_offset(alias)
    interval = int(getattr(offset, "n", 1)) or 1
    name = type(offset).__name__

    mapping = {
        "Minute": ("minute", "start"),
        "Hour": ("hour", "start"),
        "Day": ("day", "start"),
        "Week": ("week", "start"),
        "MonthBegin": ("month", "start"),
        "MonthEnd": ("month", "end"),
        "QuarterBegin": ("quarter", "start"),
        "QuarterEnd": ("quarter", "end"),
        "YearBegin": ("year", "start"),
        "YearEnd": ("year", "end"),
        "BusinessDay": ("day", "start"),
    }
    if name not in mapping:
        raise ValueError(
            f"offset {alias!r} has no cadence equivalent; pass a named "
            f"cadence such as 'monthly', or an explicit tick list via at=[...]"
        )
    unit, anchor = mapping[name]
    return Cadence(unit, interval, anchor)


def auto_cadence(span: pd.Timedelta) -> tuple[Cadence, Cadence, str]:
    """Pick major cadence, minor cadence, and label preset for a visible span.

    This is the zero-config path and the spec that §6.7 of the plan describes.
    Thresholds are deliberately blunt round numbers so the behaviour is easy to
    predict and easy to test.
    """
    days = max(float(pd.Timedelta(span) / pd.Timedelta(days=1)), 0.0)

    if days < 1:
        return Cadence("hour"), Cadence("minute", 15), "time"
    if days <= 7:
        return Cadence("day"), Cadence("hour", 6), "weekday"
    if days <= 92:
        return Cadence("week"), Cadence("day"), "day"
    if days <= 548:
        return Cadence("month"), Cadence("week"), "month"
    if days <= 1826:
        return Cadence("quarter"), Cadence("month"), "quarter-short"
    if days <= 5479:
        return Cadence("year"), Cadence("quarter"), "year"
    return Cadence("year", 5), Cadence("year"), "year"


def best_for_count(span: pd.Timedelta, n: int) -> Cadence:
    """Coarsest-to-finest search for the cadence yielding closest to ``n`` ticks."""
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    seconds = max(float(pd.Timedelta(span).total_seconds()), 1.0)
    best: Cadence | None = None
    best_error = float("inf")
    for cadence in LADDER:
        count = seconds / cadence.approx_seconds
        error = abs(count - n)
        if error < best_error:
            best, best_error = cadence, error
    assert best is not None
    return best


#: Floor the generated range's start before building candidates. pandas keeps the
#: time-of-day of the start value even for anchored offsets, so a padded start of
#: 13:30 yields "month starts" at 13:30 on the 1st -- which then sort after the
#: midnight observation they are meant to mark. Sub-day cadences floor to their
#: own unit; everything calendar-based floors to midnight.
_FLOOR_ALIAS = {
    "minute": "min",
    "hour": "h",
    "day": "D",
    "week": "D",
    "month": "D",
    "quarter": "D",
    "year": "D",
}


def periods_between(
    cadence: Cadence, lo: pd.Timestamp, hi: pd.Timestamp
) -> pd.DatetimeIndex:
    """Candidate tick timestamps for ``cadence`` covering ``[lo, hi]``.

    Generated one cadence step wide on each side so that the caller can snap to
    nearby observations without losing edge ticks.
    """
    pad = pd.Timedelta(seconds=cadence.approx_seconds)
    start = lo - pad
    floor = _FLOOR_ALIAS.get(cadence.unit)
    if floor is not None:
        start = start.floor(floor)
    return pd.date_range(start=start, end=hi + pad, freq=cadence.freq)


def _iter_units() -> Iterable[str]:  # pragma: no cover - introspection helper
    return _UNITS
