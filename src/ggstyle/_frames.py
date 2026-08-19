"""Frame-agnostic date extraction.

Accepts pandas, polars, pyarrow, numpy, and plain sequences without importing
any of them eagerly. Polars is detected by module name rather than by import, so
``ggstyle`` never adds a dependency it does not use, and a pandas-only user pays
nothing for polars support.

Everything ends up as a timezone-naive :class:`pandas.DatetimeIndex`. Aware input
is converted to UTC instants first, which is what the date-number axis needs;
display timezones are a separate concern handled by ``DateAxis.tz()``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from ._parse import to_timestamp

__all__ = ["to_datetime_index", "column"]


def _module_root(obj: Any) -> str:
    return type(obj).__module__.split(".")[0]


def _is_polars(obj: Any) -> bool:
    return _module_root(obj) == "polars"


def _is_frame(obj: Any) -> bool:
    """True for two-dimensional, column-bearing objects."""
    if isinstance(obj, pd.DataFrame):
        return True
    if _is_polars(obj) and type(obj).__name__ in ("DataFrame", "LazyFrame"):
        return True
    return _module_root(obj) == "pyarrow" and type(obj).__name__ == "Table"


def column(frame: Any, name: str) -> Any:
    """Pull a column out of a pandas or polars frame by name.

    Small helper so callers can write ``column(df, "date")`` without branching on
    which library the frame came from. Both libraries happen to support
    ``frame[name]``; this exists to give a clear error when they do not.
    """
    try:
        return frame[name]
    except Exception as exc:
        raise KeyError(f"no column {name!r} in {type(frame).__name__}") from exc


def to_datetime_index(data: Any) -> pd.DatetimeIndex:
    """Coerce ``data`` to a timezone-naive DatetimeIndex.

    Raises
    ------
    TypeError
        If given a whole frame rather than a column, or a sequence mixing
        timezone-aware and naive values. Neither is guessed at.
    """
    if _is_frame(data):
        raise TypeError(
            f"pass a column of dates, not a whole {type(data).__name__} -- "
            f'e.g. dates(ax, data=df["date"])'
        )

    if isinstance(data, (str, bytes)) or not isinstance(data, Iterable):
        raise TypeError(
            "expected a one-dimensional sequence of dates, not a scalar; "
            "wrap a single date in a list"
        )

    if _is_polars(data):
        return _from_polars(data)

    if isinstance(data, pd.DatetimeIndex):
        return data.tz_convert(None) if data.tz is not None else data

    if isinstance(data, pd.Series):
        if isinstance(data.dtype, pd.DatetimeTZDtype):
            return pd.DatetimeIndex(data).tz_convert(None)
        if pd.api.types.is_datetime64_any_dtype(data.dtype):
            return pd.DatetimeIndex(data)
        return _from_sequence(list(data))

    if isinstance(data, np.ndarray) and np.issubdtype(data.dtype, np.datetime64):
        return pd.DatetimeIndex(data)

    if _module_root(data) == "pyarrow":
        return _from_arrow(data)

    return _from_sequence(list(data))


def _from_polars(series: Any) -> pd.DatetimeIndex:
    """Convert a polars Series of Date or Datetime.

    ``to_numpy()`` is used rather than ``to_pandas()`` because the latter needs
    pyarrow installed. For a tz-aware Datetime, polars returns the underlying UTC
    instants as naive datetime64, which is exactly the representation wanted.
    """
    if type(series).__name__ != "Series":
        raise TypeError(
            f"expected a polars Series of dates, got {type(series).__name__}"
        )

    dtype_name = type(series.dtype).__name__
    if dtype_name not in ("Date", "Datetime"):
        # Strings and integers are not silently parsed as dates; make the caller
        # be explicit about what they meant.
        raise TypeError(
            f"polars Series has dtype {series.dtype}, which is not a date type. "
            f'Cast it first, e.g. df["date"].str.to_datetime().'
        )

    values = series.to_numpy()
    if values.dtype == object:  # nulls can force an object array
        return _from_sequence(list(values))
    return pd.DatetimeIndex(values)


def _from_arrow(array: Any) -> pd.DatetimeIndex:
    converter = getattr(array, "to_pandas", None)
    if converter is None:
        raise TypeError(f"cannot read dates from {type(array).__name__}")
    return to_datetime_index(converter())


def _from_sequence(values: list) -> pd.DatetimeIndex:
    stamps = [to_timestamp(v) for v in values]
    aware = [s.tzinfo is not None for s in stamps]
    if any(aware) and not all(aware):
        raise TypeError(
            "mixed timezone-aware and timezone-naive dates; make them consistent "
            "before plotting. Never guessing UTC is deliberate."
        )
    index = pd.DatetimeIndex(stamps)
    return index.tz_convert(None) if index.tz is not None else index
