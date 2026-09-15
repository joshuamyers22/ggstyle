API reference
=============

The top-level API contains the date-axis handle, cadence specification, and opt-in theme
helpers. Internal modules are not compatibility guarantees.

Plot finishing
--------------

.. autofunction:: ggstyle.finish

.. autofunction:: ggstyle.axis

.. autoclass:: ggstyle.AxisSpec

.. autoclass:: ggstyle.FinishPlan

.. autoclass:: ggstyle.FinishResult
   :members:

Date axes
---------

.. autofunction:: ggstyle.dates

.. autoclass:: ggstyle.DateAxis
   :members:

.. autoclass:: ggstyle.AxisSummary
   :members:

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
