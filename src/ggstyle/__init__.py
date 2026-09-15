"""ggstyle -- a ggplot2-flavoured plotting layer for Python.

v0.3 makes collapsed date coordinates safe for native lines, scatter collections,
and fill-between polygons. The development API also provides transactional plot labels,
pure numeric labellers, accessible palettes, and explicit Matplotlib adapters. No
``line()`` helper exists yet.

    import matplotlib.pyplot as plt
    import ggstyle as gs

    gs.use_theme()                      # "minimal" is the default
    fig, ax = plt.subplots()
    ax.plot(df["date"], df["close"])    # pandas or polars

    gs.dates(ax).ticks("quarterly").fmt("month-year").zoom("2020", "2022")
"""

from importlib.metadata import version

from ._cadence import Cadence
from .dates import AxisSummary, DateAxis, DateDiscoveryError, dates, sync_dates
from .finish import AxisSpec, FinishPlan, FinishResult, axis, finish
from .formats import (
    NumericLabeller,
    label_currency,
    label_number,
    label_percent,
    label_si,
)
from .formatters import as_formatter
from .palettes import Palette, available_palettes, palette
from .theme import DEFAULT_THEME, available_themes, stylesheet, theme, use_theme

__version__ = version("ggstyle")
__all__ = [
    "DEFAULT_THEME",
    "AxisSpec",
    "AxisSummary",
    "Cadence",
    "DateAxis",
    "DateDiscoveryError",
    "FinishPlan",
    "FinishResult",
    "NumericLabeller",
    "Palette",
    "__version__",
    "as_formatter",
    "available_palettes",
    "available_themes",
    "axis",
    "dates",
    "finish",
    "label_currency",
    "label_number",
    "label_percent",
    "label_si",
    "palette",
    "stylesheet",
    "sync_dates",
    "theme",
    "use_theme",
]
