Choosing and migrating
======================

ggstyle is a last-mile layer for native Matplotlib, not a general grammar compiler. It is
most useful when existing ``Axes`` need reliable date semantics or consistent report
finishing without surrendering direct artist access.

Matplotlib recipe to ggstyle
----------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Task
     - Matplotlib boundary
     - ggstyle policy
   * - Date cadence and text
     - Locator and formatter objects
     - ``gs.dates(ax).ticks(...).fmt(...)``
   * - Remove unobserved date gaps
     - Custom scale and provenance management
     - ``gs.dates(ax).collapse()``
   * - Percent or currency labels
     - ``FuncFormatter`` callback
     - ``gs.axis(labels=gs.label_percent(...))``
   * - Title, subtitle, and caption
     - Several text artists and layout offsets
     - ``gs.finish(..., subtitle=..., caption=...)``
   * - Parameterized report theme
     - rcParams plus explicit existing-artist styling
     - ``gs.theme_spec(...)`` and ``gs.finish(theme=...)``
   * - Direct line labels
     - Endpoint annotations and collision handling
     - ``gs.end_labels(...)`` through ``gs.finish``
   * - Publication export
     - Figure sizing, metadata, bounds, and overwrite checks
     - ``gs.save(...)``
   * - Preflight review
     - Bespoke state inspection
     - ``gs.finish(..., dry_run=True).describe()``

Which plotting interface?
-------------------------

Use raw Matplotlib when the drawing itself is unusual or every low-level artist option
matters. Use ggstyle when native Matplotlib drawing is already appropriate and the hard
part is date coordinates, repeatable presentation, or safe export.

Use plotnine when ggplot2-compatible grammar concepts and syntax are the primary
requirement. Consider seaborn's declarative objects interface for semantic statistical
graphics in the seaborn ecosystem. Consider Altair when a declarative Vega-Lite output
and interactive or web-oriented rendering is more important than native Matplotlib
artists. These tools are complements; ggstyle does not attempt to translate their plot
specifications.

Escape hatches remain ordinary Matplotlib operations. ggstyle returns the adopted axes,
native artists, formatters, and paths instead of proxy objects.
