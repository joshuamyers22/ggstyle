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

Version 0.1 remaps ``Line2D`` artists when switching coordinate modes. Collections made
by ``scatter`` and ``fill_between`` are not remapped. Collapse the axis before creating
those artists, or keep the axis in ``show`` mode.

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
