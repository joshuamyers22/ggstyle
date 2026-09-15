Release notes
=============

Unreleased
----------

Collapsed coordinates now use one registered matplotlib x-scale instead of rewriting
``Line2D`` data. Lines, ``scatter``, ``fill_between``, and native x-data annotations share
the same invertible display transform while their calendar geometry and date-number
limits remain unchanged. Empty registries still reject collapse; a one-observation
registry now uses one calendar day per ordinal unit in both directions.

``DateAxis.loc()`` now returns a native matplotlib date number in both modes. Code that
passes its result to matplotlib artists or limits continues to work, while code that
asserted observation ordinals should instead inspect the axis scale transform. This is a
deliberate pre-1.0 migration to avoid double-transforming native matplotlib operations.

Observation provenance is now held by an owned, revisioned registry. Lines, scatter
collections, and native ``fill_between`` polygons are discovered automatically; explicit
dates remain sticky, and removed or mutated artists are reflected by
:meth:`ggstyle.DateAxis.refresh`. Synchronized handles share one live registry, so
refreshing any member transactionally updates every member without changing their
date-number view limits. Polygon discovery supports masks, NaNs, ``where`` regions,
interpolated crossings, and multiple paths without changing vertices or path codes.
Midpoint-stepped polygons require explicit ``data=`` because Matplotlib does not retain
their complete source x sequence. ``fill_betweenx`` and non-data polygon transforms are
rejected on an x-date handle.

:meth:`ggstyle.DateAxis.dispose` disconnects callbacks and weak registry ownership while
leaving Matplotlib artists in place. Failed timezone, formatter, caption, discovery, and
shared-registry operations retain the previous valid state.

0.2.0
-----

This release completes ggstyle's built-in ggplot2-inspired theme set with ``bw``,
``linedraw``, ``light``, ``dark``, ``classic``, ``void``, and ``test``. The existing
``minimal`` default and ``grey`` theme remain unchanged. Corresponding ggplot2 function
names such as ``theme_bw`` and ``theme_classic`` are accepted as aliases.

Each theme ships as a standalone matplotlib stylesheet. See :ref:`the Themes section
<themes>` for the full list and matplotlib-specific fidelity notes.

0.1.1
-----

This maintenance release refactors date-axis behavior into focused policy modules while
preserving the public API, and strengthens reproducible build and publishing checks.

0.1.0
-----

The initial public release introduces the standalone date-axis handle, date extraction for
common dataframe and array libraries, collapsed observation spacing, date-space
annotations, and two opt-in matplotlib themes.

See :doc:`pitfalls` for current lifecycle and timezone limitations.
