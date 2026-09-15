"""ggstyle -- a ggplot2-flavoured plotting layer for Python.

v0.4 combines production-safe collapsed date coordinates with transactional plot labels,
pure numeric labellers, accessible palettes, parameterized themes, collision-aware direct
labels, inspectable plans, and publication-safe figure export. No ``line()`` helper or
general grammar compiler exists.

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
from .end_labels import EndLabelSpec, end_labels
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
from .save import save
from .theme import (
    DEFAULT_THEME,
    ThemeSpec,
    available_themes,
    stylesheet,
    theme,
    theme_params,
    theme_spec,
    use_theme,
)

__version__ = version("ggstyle")
__all__ = [
    "DEFAULT_THEME",
    "AxisSpec",
    "AxisSummary",
    "Cadence",
    "DateAxis",
    "DateDiscoveryError",
    "EndLabelSpec",
    "FinishPlan",
    "FinishResult",
    "NumericLabeller",
    "Palette",
    "ThemeSpec",
    "__version__",
    "as_formatter",
    "available_palettes",
    "available_themes",
    "axis",
    "dates",
    "end_labels",
    "finish",
    "label_currency",
    "label_number",
    "label_percent",
    "label_si",
    "palette",
    "save",
    "stylesheet",
    "sync_dates",
    "theme",
    "theme_params",
    "theme_spec",
    "use_theme",
]
