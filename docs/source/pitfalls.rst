Pitfalls
========

This page collects limitations that can otherwise produce plausible but incorrect
figures, following the prominent pitfalls guidance used by statsmodels.

Native annotations on collapsed axes
------------------------------------

In collapsed mode, the x-axis contains ordinal positions rather than matplotlib date
numbers. A native ``ax.axvline(timestamp)`` is therefore misplaced. Convert through
:meth:`ggstyle.DateAxis.loc` or use :meth:`ggstyle.DateAxis.vline`.

Unsupported artist remapping
----------------------------

Version 0.2 remaps ``Line2D`` artists when switching coordinate modes. Collections made
by ``scatter`` and ``fill_between`` are not remapped. Creating a collection before or
after collapsing is unsafe: existing collections retain matplotlib date numbers, and new
collections receive date numbers even though the collapsed axis uses observation
ordinals. Keep the axis in ``show`` mode whenever those collections are present. There is
currently no supported creation order or automatic collection-remapping workaround.

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

The following version 0.2 limitations are covered by strict expected-failure tests while
their contracts are designed for version 0.3:

* calling :func:`ggstyle.dates` without explicit ``data`` does not rescan lines added
  after adoption;
* a one-observation collapsed axis does not yet provide a consistent inverse mapping;
* an invalid display timezone can remain stored after the operation raises;
* ``fmt(minor=False)`` does not disable minor labels after they have been enabled; and
* externally removing a managed annotation or caption can make later replay or
  replacement raise.

These are documented constraints, not supported behavior. The tests describe the desired
safe contracts and must be converted to ordinary passing regressions as each fix lands.
