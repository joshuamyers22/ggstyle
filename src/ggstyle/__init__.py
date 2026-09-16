"""ggstyle -- a ggplot2-flavoured plotting layer for Python.

ggstyle combines production-safe collapsed date coordinates with transactional plot
finishing, narrow tidy-data line, point, and ribbon helpers, and callback-based native
facets. It remains a layer over ordinary Matplotlib rather than a general grammar
compiler.

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
from .facets import (
    FacetCallbackError,
    FacetGrid,
    FacetPanel,
    FacetPlan,
    facet_plan,
    facets,
)
from .finish import AxisSpec, FinishPlan, FinishResult, axis, finish
from .formats import (
    NumericLabeller,
    label_currency,
    label_number,
    label_percent,
    label_si,
)
from .formatters import as_formatter
from .guides import GuideResult, guides
from .line import LineResult, line
from .palettes import Palette, available_palettes, palette
from .points import PointResult, points
from .results import RenderedResult
from .ribbon import RibbonResult, ribbon
from .save import save
from .scales import AestheticScale, ContinuousScale, DiscreteScale
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
    "AestheticScale",
    "AxisSpec",
    "AxisSummary",
    "Cadence",
    "ContinuousScale",
    "DateAxis",
    "DateDiscoveryError",
    "DiscreteScale",
    "EndLabelSpec",
    "FacetCallbackError",
    "FacetGrid",
    "FacetPanel",
    "FacetPlan",
    "FinishPlan",
    "FinishResult",
    "GuideResult",
    "LineResult",
    "NumericLabeller",
    "Palette",
    "PointResult",
    "RenderedResult",
    "RibbonResult",
    "ThemeSpec",
    "__version__",
    "as_formatter",
    "available_palettes",
    "available_themes",
    "axis",
    "dates",
    "end_labels",
    "facet_plan",
    "facets",
    "finish",
    "guides",
    "label_currency",
    "label_number",
    "label_percent",
    "label_si",
    "line",
    "palette",
    "points",
    "ribbon",
    "save",
    "stylesheet",
    "sync_dates",
    "theme",
    "theme_params",
    "theme_spec",
    "use_theme",
]
