API reference
=============

The top-level API contains narrow semantic rendering, date-axis semantics,
publication-finishing values, figure export, numeric labels, palettes, and opt-in themes.
Internal modules are not compatibility guarantees.

Facet planning and rendering
----------------------------

.. autofunction:: ggstyle.facets

.. autoclass:: ggstyle.FacetGrid
   :members: figure, axes, plan, diagnostics, map_count, date_handles, map, dates, as_dict, describe

.. autoexception:: ggstyle.FacetCallbackError

.. autofunction:: ggstyle.facet_plan

.. autoclass:: ggstyle.FacetPlan
   :members: as_dict, describe, shape

.. autoclass:: ggstyle.FacetPanel
   :members: as_dict, empty

Semantic rendering
------------------

.. autoclass:: ggstyle.RenderedResult
   :members: as_dict, describe

.. autofunction:: ggstyle.line

.. autoclass:: ggstyle.LineResult
   :members:

.. autofunction:: ggstyle.points

.. autoclass:: ggstyle.PointResult
   :members:

.. autofunction:: ggstyle.ribbon

.. autoclass:: ggstyle.RibbonResult
   :members:

.. autofunction:: ggstyle.guides

.. autoclass:: ggstyle.GuideResult
   :members:

.. autoclass:: ggstyle.AestheticScale
   :members: as_dict, describe

.. autoclass:: ggstyle.DiscreteScale

.. autoclass:: ggstyle.ContinuousScale

Plot finishing
--------------

.. autofunction:: ggstyle.finish

.. autofunction:: ggstyle.axis

.. autoclass:: ggstyle.AxisSpec

.. autoclass:: ggstyle.FinishPlan
   :members: as_dict, describe

.. autoclass:: ggstyle.FinishResult
   :members:

.. autofunction:: ggstyle.end_labels

.. autoclass:: ggstyle.EndLabelSpec

Figure export
-------------

.. autofunction:: ggstyle.save

Date axes
---------

.. autofunction:: ggstyle.dates

.. autoclass:: ggstyle.DateAxis
   :members:

.. autoclass:: ggstyle.AxisSummary
   :members: as_dict, describe

.. autoexception:: ggstyle.DateDiscoveryError

.. autoclass:: ggstyle.Cadence
   :members:

.. autofunction:: ggstyle.sync_dates

Numeric labels
--------------

.. autoclass:: ggstyle.NumericLabeller

.. autofunction:: ggstyle.label_percent

.. autofunction:: ggstyle.label_currency

.. autofunction:: ggstyle.label_number

.. autofunction:: ggstyle.label_si

.. autofunction:: ggstyle.as_formatter

Palettes
--------

.. autoclass:: ggstyle.Palette
   :members:

.. autofunction:: ggstyle.palette

.. autofunction:: ggstyle.available_palettes

Themes
------

.. autoclass:: ggstyle.ThemeSpec

.. autofunction:: ggstyle.theme_spec

.. autofunction:: ggstyle.theme_params

.. autofunction:: ggstyle.use_theme

.. autoclass:: ggstyle.theme
   :members:

.. autofunction:: ggstyle.stylesheet

.. autofunction:: ggstyle.available_themes
