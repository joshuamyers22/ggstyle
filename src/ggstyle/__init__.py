"""ggstyle -- a ggplot2-flavoured plotting layer for Python.

v0.1a is the date axis plus themes. No palettes module and no ``line()`` yet;
those arrive in v0.1b.

    import matplotlib.pyplot as plt
    import ggstyle as gs

    gs.use_theme()                      # "minimal" is the default
    fig, ax = plt.subplots()
    ax.plot(df["date"], df["close"])    # pandas or polars

    gs.dates(ax).ticks("quarterly").fmt("month-year").zoom("2020", "2022")
"""

from ._cadence import Cadence
from .dates import AxisSummary, DateAxis, dates, sync_dates
from .theme import DEFAULT_THEME, available_themes, stylesheet, theme, use_theme

__version__ = "0.1a0"
__all__ = [
    "DEFAULT_THEME",
    "AxisSummary",
    "Cadence",
    "DateAxis",
    "__version__",
    "available_themes",
    "dates",
    "stylesheet",
    "sync_dates",
    "theme",
    "use_theme",
]
