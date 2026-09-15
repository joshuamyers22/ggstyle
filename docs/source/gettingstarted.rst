Getting started
===============

Installation
------------

Install the public package with pip::

   python -m pip install ggstyle

The package requires Python 3.10 or newer. Polars support is optional::

   python -m pip install "ggstyle[polars]"

Adopt a matplotlib axis
-----------------------

``ggstyle`` does not replace matplotlib. Plot normally, then adopt the x-axis:

.. code-block:: python

   import matplotlib.pyplot as plt
   import pandas as pd
   import ggstyle as gs

   index = pd.date_range("2024-01-01", periods=180)
   values = range(len(index))

   with gs.theme("minimal"):
       fig, ax = plt.subplots()
       ax.plot(index, values)
       gs.dates(ax).ticks("monthly").fmt("month-year")

The :func:`ggstyle.dates` call returns a :class:`ggstyle.DateAxis`. Its methods return
the same handle, so operations can be chained.

Finish plot labels
------------------

Add the plot and axis labels as one validated operation:

.. code-block:: python

   result = gs.finish(
       ax,
       title="Revenue",
       subtitle="Trailing twelve months",
       caption="Source: annual report",
       x=gs.axis(title="Date"),
       y=gs.axis(title="USD"),
   )

``result.axes`` is the original Matplotlib axes and ``result.artists`` contains ordinary
Matplotlib text artists. See :ref:`plot-finishing` for layout, replacement, and dry-run
behavior.

Preview the same validated operation without mutation and retain plain audit data:

.. code-block:: python

   plan = gs.finish(ax, title="Revenue", theme="minimal", dry_run=True)
   print(plan.describe())

See :doc:`inspection` for JSON-safe finishing plans and date-axis summaries.

For several labelled lines, replace legend lookup with collision-aware endpoint labels:

.. code-block:: python

   ax.plot(index, actual, label="Actual")
   ax.plot(index, forecast, label="Forecast")
   gs.finish(ax, direct_labels=gs.end_labels())

Unsupported legend entries fall back to an ordinary legend by default. See
:ref:`direct-endpoint-labels` for the supported artist boundary and strict policy.

Save the figure
---------------

Export requires the figure, destination, and physical dimensions explicitly:

.. code-block:: python

   gs.save(
       fig,
       "report.png",
       width=7,
       height=4,
       units="in",
       dpi=300,
   )

Existing files are protected unless ``overwrite=True`` is passed. See
:ref:`figure-export` for bounding, transparency, metadata, deterministic vector output,
and failure behavior.

Parameterize a theme
--------------------

Build one validated recipe and use it either while creating a figure or to finish an
existing axes:

.. code-block:: python

   report_theme = gs.theme_spec(
       "minimal",
       base_size=11,
       overrides={"axes.titlesize": 14},
   )

   with gs.theme(report_theme):
       fig, ax = plt.subplots()

   gs.finish(ax, theme=report_theme)

Applying a theme after axes creation changes only safely retroactive, non-data styling.
See :ref:`parameterized-themes` for the exact boundary and diagnostics.

Choose what to configure
------------------------

Tick placement and label formatting are deliberately separate:

.. code-block:: python

   handle = gs.dates(ax)
   handle.ticks("quarterly")
   handle.fmt("quarter")
   handle.zoom("2022", "2024")

See the :doc:`user-guide` for collapsed axes and annotations.

Format a numeric axis
---------------------

Numeric label factories remain independent of the date-axis handle:

.. code-block:: python

   dollars = gs.label_currency("$", decimals=0)
   ax.yaxis.set_major_formatter(gs.as_formatter(dollars))

See :ref:`numeric-labels` for percentage, grouped-number, SI-prefix, scaling, and
non-finite-value behavior.

Choose a palette
----------------

Use the public qualitative cycle for several series, or sample a continuous palette:

.. code-block:: python

   ax.set_prop_cycle(color=gs.palette("qualitative").colors)
   five_colors = gs.palette("sequential", n=5).colors

Palette construction does not apply a theme or mutate global Matplotlib settings. See
:ref:`palettes` for missing values, out-of-bounds policies, and diverging midpoints.
