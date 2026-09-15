"""ggstyle -- a ggplot2-flavoured plotting layer for Python.

v0.3 makes collapsed date coordinates safe for native lines, scatter collections,
and fill-between polygons. The development API also provides pure numeric labellers
with an explicit Matplotlib adapter. No palettes module and no ``line()`` yet; those
remain future additions.

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
from .formats import (
    NumericLabeller,
    label_currency,
    label_number,
    label_percent,
    label_si,
)
from .formatters import as_formatter
from .theme import DEFAULT_THEME, available_themes, stylesheet, theme, use_theme

__version__ = version("ggstyle")
__all__ = [
    "DEFAULT_THEME",
    "AxisSummary",
    "Cadence",
    "DateAxis",
    "DateDiscoveryError",
    "NumericLabeller",
    "__version__",
    "as_formatter",
    "available_themes",
    "dates",
    "label_currency",
    "label_number",
    "label_percent",
    "label_si",
    "stylesheet",
    "sync_dates",
    "theme",
    "use_theme",
]
