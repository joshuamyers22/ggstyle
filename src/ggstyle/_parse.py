"""Parsing of dates, partial date strings, and frequency offsets.

Two jobs:

1. Partial-string parsing with pandas ``Period`` semantics, so ``"2020"`` means the
   whole year and ``"2020-03"`` means the whole month, with the caller choosing
   which end of the period they want.
2. Frequency alias normalization. pandas 3.0 removed the legacy ``M``/``Q``/``Y``/``H``
   aliases in favour of ``ME``/``QE``/``YE``/``h``. Users have a decade of muscle
   memory for the old ones, so we accept both.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any

import pandas as pd
from pandas.tseries.frequencies import to_offset as _pd_to_offset

__all__ = ["is_date_like", "normalize_alias", "to_offset", "to_timestamp"]


#: Legacy alias -> modern alias. Applied to the letter part of an offset string.
_LEGACY = {
    "M": "ME",
    "Q": "QE",
    "Y": "YE",
    "A": "YE",
    "H": "h",
    "T": "min",
    "S": "s",
    "L": "ms",
    "U": "us",
    "N": "ns",
}

_OFFSET_RE = re.compile(r"^\s*([+-]?\d*)\s*([A-Za-z]+)\s*(.*)$")


def normalize_alias(alias: str) -> str:
    """Normalize a frequency alias, translating legacy spellings.

    ``"6M"`` -> ``"6ME"``, ``"H"`` -> ``"h"``, ``"3ME"`` -> ``"3ME"`` (unchanged).
    Anchored aliases such as ``"W-MON"`` keep their suffix.
    """
    if not isinstance(alias, str):
        return alias
    match = _OFFSET_RE.match(alias)
    if match is None:
        return alias
    count, letters, suffix = match.groups()
    letters = _LEGACY.get(letters, letters)
    return f"{count}{letters}{suffix}"


def to_offset(value: Any):
    """Convert to a pandas offset, accepting legacy aliases.

    Tries the string as given first so that anything pandas already understands
    keeps working untouched; only falls back to normalization on failure.
    """
    if value is None:
        return None
    if isinstance(value, str):
        normalized = normalize_alias(value)
        try:
            return _pd_to_offset(normalized)
        except ValueError:
            # Preserve pandas' own error for aliases our compatibility map does
            # not recognize.
            return _pd_to_offset(value)
    return _pd_to_offset(value)


def to_timestamp(value: Any, side: str = "start") -> pd.Timestamp:
    """Convert ``value`` to a Timestamp, expanding partial date strings.

    Parameters
    ----------
    value
        A string, ``datetime``, ``date``, ``Timestamp``, or numpy datetime.
    side
        ``"start"`` or ``"end"``. Controls which end of a partial period is
        returned: ``to_timestamp("2020", "end")`` is the last instant of 2020.
        Ignored for values that are already a specific instant.

    Raises
    ------
    TypeError
        If the value cannot be interpreted as a date.
    """
    if side not in ("start", "end"):
        raise ValueError(f"side must be 'start' or 'end', got {side!r}")

    if isinstance(value, pd.Timestamp):
        return value
    if isinstance(value, _dt.datetime):
        return pd.Timestamp(value)
    if isinstance(value, _dt.date):
        ts = pd.Timestamp(value)
        return ts if side == "start" else ts + pd.Timedelta(days=1) - pd.Timedelta(1, "ns")

    if isinstance(value, str):
        try:
            period = pd.Period(value.strip())
        except Exception:
            pass
        else:
            # matplotlib date numbers are floating-point microseconds at modern
            # dates. A nanosecond period end can round into the next day on some
            # pandas/Python combinations, so normalize to the finest precision
            # matplotlib can represent reliably.
            return period.start_time if side == "start" else period.end_time.floor("us")
        try:
            return pd.Timestamp(value)
        except Exception as exc:  # pragma: no cover - message path
            raise TypeError(f"could not interpret {value!r} as a date") from exc

    try:
        return pd.Timestamp(value)
    except Exception as exc:
        raise TypeError(
            f"could not interpret {value!r} (type {type(value).__name__}) as a date"
        ) from exc


def is_date_like(value: Any) -> bool:
    """True if ``value`` can be read as a date."""
    try:
        to_timestamp(value)
    except (TypeError, ValueError):
        return False
    return True
