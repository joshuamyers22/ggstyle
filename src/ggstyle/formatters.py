"""Adapters from pure ggstyle labellers to Matplotlib formatters."""

from __future__ import annotations

from collections.abc import Callable

from matplotlib.ticker import FuncFormatter

__all__ = ["as_formatter"]


def as_formatter(labeller: Callable[[float], str]) -> FuncFormatter:
    """
    Adapt a one-value numeric labeller to Matplotlib.

    Parameters
    ----------
    labeller : callable
        Callable accepting one numeric value and returning display text.

    Returns
    -------
    matplotlib.ticker.FuncFormatter
        Formatter that ignores Matplotlib's optional tick-position argument.

    Raises
    ------
    TypeError
        If ``labeller`` is not callable.

    Notes
    -----
    Creating an adapter does not install it on an axis or mutate Matplotlib
    configuration. Pass the result to ``Axis.set_major_formatter`` explicitly.

    Examples
    --------
    >>> from ggstyle import as_formatter, label_percent
    >>> formatter = as_formatter(label_percent(decimals=1))
    >>> formatter(0.125)
    '12.5%'
    """
    if not callable(labeller):
        raise TypeError(f"labeller must be callable, got {labeller!r}")
    return FuncFormatter(lambda value, _position=None: labeller(value))
