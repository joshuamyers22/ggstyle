Pitfalls
========

This page collects limitations that can otherwise produce plausible but incorrect
figures, following the prominent pitfalls guidance used by statsmodels.

Coordinate transforms on collapsed axes
----------------------------------------

Collapsed mode is a registered matplotlib x-scale. Ordinary ``ax.transData`` artists and
public blended transforms with an x-data component, including
``ax.axvline(timestamp)``, pass through that scale. Axes-, figure-, display-, and custom
transforms do not automatically become date-bearing; use native matplotlib semantics for
those coordinate systems.

Collection observation discovery
--------------------------------

Lines, ``scatter`` collections, and ``fill_between`` polygons retain matplotlib date
numbers and render correctly before or after collapse. Version 0.3 does not yet discover
observations from a collection-only plot. Supply its complete date sequence explicitly::

   handle = gs.dates(ax, data=dates).collapse()

Without a plotted line or explicit ``data=``, collapse fails rather than selecting an
accidentally incomplete coordinate map.

Dates between observations
--------------------------

:meth:`ggstyle.DateAxis.loc` interpolates a missing date between neighboring
observations. Use ``snap=True`` to select the nearest observation or ``strict=True`` to
reject dates that were not observed.

Timezone display
----------------

Timezone-aware inputs are converted to naive UTC instants for positioning.
:meth:`ggstyle.DateAxis.tz` changes labels only. For naive input, display-timezone
conversion assumes that the original values represent UTC.

Input interpretation
--------------------

Whole data frames, scalar dates, and string-typed pandas or polars columns are rejected.
Select one column and convert it to a datetime dtype explicitly. This prevents accidental
interpretation of identifiers or ambiguous date strings.

Missing explicit dates
----------------------

Explicit data containing missing dates raises by default. ``missing="drop"`` excludes
those values and records their count in :meth:`ggstyle.DateAxis.summary`. Missing x-values
already present in a line are treated as intentional line breaks and are not counted.

Synchronized collapsed panels
-----------------------------

Calling :meth:`ggstyle.DateAxis.collapse` independently on several panels can assign
different ordinal positions to the same date. Use :func:`ggstyle.sync_dates` when panels
are intended for comparison.

Version 0.2 synchronization is a snapshot operation: each handle receives a copy of the
combined observations and limits at call time. Adding or registering observations on one
handle does not update the others automatically. Register new observations explicitly,
then call :func:`ggstyle.sync_dates` again before comparing the panels.

Known lifecycle limitations
---------------------------

The following lifecycle limitations are covered by strict expected-failure tests while
their contracts are designed for version 0.3:

* calling :func:`ggstyle.dates` without explicit ``data`` does not rescan lines added
  after adoption;
* an invalid display timezone can remain stored after the operation raises;
* ``fmt(minor=False)`` does not disable minor labels after they have been enabled; and
* externally removing a managed caption can make later replacement raise.

These are documented constraints, not supported behavior. The tests describe the desired
safe contracts and must be converted to ordinary passing regressions as each fix lands.
