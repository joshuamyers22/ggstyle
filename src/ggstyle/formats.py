"""Pure numeric labellers for plot axes and report text.

The factories in this module return immutable one-value callables. They do not
import Matplotlib, read the process locale, or mutate global configuration. Use
:func:`ggstyle.as_formatter` at the Matplotlib boundary.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Literal, cast

__all__ = [
    "NumericLabeller",
    "label_currency",
    "label_number",
    "label_percent",
    "label_si",
]

NegativeStyle = Literal["minus", "parentheses"]


class NumericLabeller(ABC):
    """
    Convert one numeric value to display text.

    Notes
    -----
    Labellers operate on one value at a time so they compose with Matplotlib's
    formatter protocol and remain useful outside an axis. Factory results are
    immutable; callers may also supply any compatible callable to
    :func:`ggstyle.as_formatter`.
    """

    @abstractmethod
    def __call__(self, value: float, /) -> str:
        """Return display text for ``value``."""
        ...


def _real(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number, got {value!r}")
    try:
        return float(value)
    except OverflowError as error:
        raise ValueError(f"{name} is outside the supported floating-point range") from error


def _scale(value: object) -> float:
    resolved = _real("scale", value)
    if not math.isfinite(resolved) or resolved <= 0:
        raise ValueError(f"scale must be finite and greater than zero, got {value!r}")
    return resolved


def _decimals(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"decimals must be a non-negative integer, got {value!r}")
    if value < 0:
        raise ValueError(f"decimals must be a non-negative integer, got {value!r}")
    return int(value)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, got {value!r}")
    return value


def _negative_style(value: object) -> NegativeStyle:
    if not isinstance(value, str):
        raise TypeError(f"negative must be a string, got {value!r}")
    if value not in ("minus", "parentheses"):
        raise ValueError(f"negative must be 'minus' or 'parentheses', got {value!r}")
    return cast(NegativeStyle, value)


def _grouping(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"grouping must be a boolean, got {value!r}")
    return value


def _signed(text: str, *, negative: bool, style: NegativeStyle) -> str:
    if not negative:
        return text
    if style == "parentheses":
        return f"({text})"
    return f"-{text}"


def _special(
    value: float,
    *,
    negative: NegativeStyle,
    nan: str,
    infinity: str,
) -> str | None:
    if math.isnan(value):
        return nan
    if math.isinf(value):
        return _signed(infinity, negative=value < 0, style=negative)
    return None


@dataclass(frozen=True)
class _NumberLabeller(NumericLabeller):
    scale: float
    multiplier: float
    decimals: int
    grouping: bool
    prefix: str
    suffix: str
    negative: NegativeStyle
    nan: str
    infinity: str

    def __call__(self, value: float, /) -> str:
        number = _real("value", value)
        special = _special(
            number,
            negative=self.negative,
            nan=self.nan,
            infinity=self.infinity,
        )
        if special is not None:
            return special

        magnitude = abs(number) * self.multiplier / self.scale
        rounded = round(magnitude, self.decimals)
        is_negative = number < 0 and rounded != 0
        grouping = "," if self.grouping else ""
        rendered = format(magnitude, f"{grouping}.{self.decimals}f")
        return _signed(
            f"{self.prefix}{rendered}{self.suffix}",
            negative=is_negative,
            style=self.negative,
        )


_SI_PREFIXES = {
    -30: "q",
    -27: "r",
    -24: "y",
    -21: "z",
    -18: "a",
    -15: "f",
    -12: "p",
    -9: "n",
    -6: "µ",
    -3: "m",
    0: "",
    3: "k",
    6: "M",
    9: "G",
    12: "T",
    15: "P",
    18: "E",
    21: "Z",
    24: "Y",
    27: "R",
    30: "Q",
}


@dataclass(frozen=True)
class _SILabeller(NumericLabeller):
    unit: str
    decimals: int
    separator: str
    negative: NegativeStyle
    nan: str
    infinity: str

    def __call__(self, value: float, /) -> str:
        number = _real("value", value)
        special = _special(
            number,
            negative=self.negative,
            nan=self.nan,
            infinity=self.infinity,
        )
        if special is not None:
            return special

        magnitude = abs(number)
        exponent = 0
        if magnitude:
            exponent = 3 * math.floor(math.log10(magnitude) / 3)
            exponent = max(min(exponent, max(_SI_PREFIXES)), min(_SI_PREFIXES))
        scaled = magnitude / (10.0**exponent)

        rounded = round(scaled, self.decimals)
        if rounded >= 1000 and exponent < max(_SI_PREFIXES):
            exponent += 3
            scaled /= 1000
            rounded = round(scaled, self.decimals)

        is_negative = number < 0 and rounded != 0
        prefix_and_unit = f"{_SI_PREFIXES[exponent]}{self.unit}"
        separator = self.separator if prefix_and_unit else ""
        rendered = f"{scaled:.{self.decimals}f}{separator}{prefix_and_unit}"
        return _signed(rendered, negative=is_negative, style=self.negative)


def _number_labeller(
    *,
    scale: object,
    multiplier: float,
    decimals: object,
    grouping: object,
    prefix: object,
    suffix: object,
    negative: object,
    nan: object,
    infinity: object,
) -> NumericLabeller:
    return _NumberLabeller(
        scale=_scale(scale),
        multiplier=multiplier,
        decimals=_decimals(decimals),
        grouping=_grouping(grouping),
        prefix=_text("prefix", prefix),
        suffix=_text("suffix", suffix),
        negative=_negative_style(negative),
        nan=_text("nan", nan),
        infinity=_text("infinity", infinity),
    )


def label_percent(
    *,
    scale: float = 1.0,
    decimals: int = 0,
    grouping: bool = False,
    suffix: str = "%",
    negative: NegativeStyle = "minus",
    nan: str = "NaN",
    infinity: str = "∞",
) -> NumericLabeller:
    """
    Create a locale-independent percentage labeller.

    Parameters
    ----------
    scale : float, default 1.0
        Input value corresponding to 100 percent. Use ``100`` for inputs already
        expressed as percentages.
    decimals : int, default 0
        Fixed number of digits after the decimal point.
    grouping : bool, default False
        Whether to group thousands with commas.
    suffix : str, default "%"
        Text appended to each finite value.
    negative : {"minus", "parentheses"}, default "minus"
        Presentation for negative finite values and negative infinity.
    nan : str, default "NaN"
        Complete label used for not-a-number values.
    infinity : str, default "∞"
        Unsigned complete label used for infinite values.

    Returns
    -------
    NumericLabeller
        Immutable callable accepting one numeric value.

    Raises
    ------
    TypeError
        If an option has the wrong type.
    ValueError
        If ``scale``, ``decimals``, or ``negative`` is invalid.

    Examples
    --------
    >>> percent = label_percent(decimals=1)
    >>> percent(0.125)
    '12.5%'
    """
    return _number_labeller(
        scale=scale,
        multiplier=100.0,
        decimals=decimals,
        grouping=grouping,
        prefix="",
        suffix=suffix,
        negative=negative,
        nan=nan,
        infinity=infinity,
    )


def label_currency(
    symbol: str = "$",
    *,
    scale: float = 1.0,
    decimals: int = 2,
    grouping: bool = True,
    suffix: str = "",
    negative: NegativeStyle = "minus",
    nan: str = "NaN",
    infinity: str = "∞",
) -> NumericLabeller:
    """
    Create a locale-independent currency labeller.

    Parameters
    ----------
    symbol : str, default "$"
        Currency symbol or code placed before finite values.
    scale : float, default 1.0
        Positive divisor applied before formatting. For example, ``1_000_000``
        formats source units as millions.
    decimals : int, default 2
        Fixed number of digits after the decimal point.
    grouping : bool, default True
        Whether to group thousands with commas.
    suffix : str, optional
        Text appended to each finite value, such as ``"M"``.
    negative : {"minus", "parentheses"}, default "minus"
        Presentation for negative finite values and negative infinity.
    nan : str, default "NaN"
        Complete label used for not-a-number values.
    infinity : str, default "∞"
        Unsigned complete label used for infinite values.

    Returns
    -------
    NumericLabeller
        Immutable callable accepting one numeric value.

    Raises
    ------
    TypeError
        If an option has the wrong type.
    ValueError
        If ``scale``, ``decimals``, or ``negative`` is invalid.

    Examples
    --------
    >>> currency = label_currency("$", scale=1_000_000, decimals=1, suffix="M")
    >>> currency(2_500_000)
    '$2.5M'
    """
    return _number_labeller(
        scale=scale,
        multiplier=1.0,
        decimals=decimals,
        grouping=grouping,
        prefix=_text("symbol", symbol),
        suffix=suffix,
        negative=negative,
        nan=nan,
        infinity=infinity,
    )


def label_number(
    *,
    scale: float = 1.0,
    decimals: int = 0,
    grouping: bool = True,
    prefix: str = "",
    suffix: str = "",
    negative: NegativeStyle = "minus",
    nan: str = "NaN",
    infinity: str = "∞",
) -> NumericLabeller:
    """
    Create a locale-independent decimal number labeller.

    Parameters
    ----------
    scale : float, default 1.0
        Positive divisor applied before formatting.
    decimals : int, default 0
        Fixed number of digits after the decimal point.
    grouping : bool, default True
        Whether to group thousands with commas.
    prefix : str, optional
        Text placed before each finite value.
    suffix : str, optional
        Text appended to each finite value.
    negative : {"minus", "parentheses"}, default "minus"
        Presentation for negative finite values and negative infinity.
    nan : str, default "NaN"
        Complete label used for not-a-number values.
    infinity : str, default "∞"
        Unsigned complete label used for infinite values.

    Returns
    -------
    NumericLabeller
        Immutable callable accepting one numeric value.

    Raises
    ------
    TypeError
        If an option has the wrong type.
    ValueError
        If ``scale``, ``decimals``, or ``negative`` is invalid.

    Examples
    --------
    >>> number = label_number(decimals=1)
    >>> number(12345.6)
    '12,345.6'
    """
    return _number_labeller(
        scale=scale,
        multiplier=1.0,
        decimals=decimals,
        grouping=grouping,
        prefix=prefix,
        suffix=suffix,
        negative=negative,
        nan=nan,
        infinity=infinity,
    )


def label_si(
    *,
    unit: str = "",
    decimals: int = 1,
    separator: str = " ",
    negative: NegativeStyle = "minus",
    nan: str = "NaN",
    infinity: str = "∞",
) -> NumericLabeller:
    """
    Create a labeller using powers-of-1000 SI prefixes.

    Parameters
    ----------
    unit : str, optional
        Unit appended after the SI prefix.
    decimals : int, default 1
        Fixed number of digits after the decimal point.
    separator : str, default " "
        Text between the number and the combined SI prefix and unit.
    negative : {"minus", "parentheses"}, default "minus"
        Presentation for negative finite values and negative infinity.
    nan : str, default "NaN"
        Complete label used for not-a-number values.
    infinity : str, default "∞"
        Unsigned complete label used for infinite values.

    Returns
    -------
    NumericLabeller
        Immutable callable accepting one numeric value.

    Raises
    ------
    TypeError
        If an option has the wrong type.
    ValueError
        If ``decimals`` or ``negative`` is invalid.

    Notes
    -----
    Prefixes cover powers from quecto (``q``, 10^-30) through quetta
    (``Q``, 10^30). Values beyond that range use the nearest available prefix.
    Rounding uses Python's locale-independent fixed-point formatting.

    Examples
    --------
    >>> storage = label_si(unit="B")
    >>> storage(1_500_000)
    '1.5 MB'
    """
    return _SILabeller(
        unit=_text("unit", unit),
        decimals=_decimals(decimals),
        separator=_text("separator", separator),
        negative=_negative_style(negative),
        nan=_text("nan", nan),
        infinity=_text("infinity", infinity),
    )
