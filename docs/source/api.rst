API reference
=============

The top-level API contains date-axis semantics, publication-finishing values, figure
export, numeric labels, palettes, and opt-in themes. Internal modules are not
compatibility guarantees.

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
