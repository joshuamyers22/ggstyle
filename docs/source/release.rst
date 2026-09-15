Release notes
=============

0.5.0 (2026-09-15)
------------------

Version 0.5 adds transactional :func:`ggstyle.line`, :func:`ggstyle.points`, and
:func:`ggstyle.ribbon` helpers for named tidy-data columns on caller-owned axes. Discrete
color and linestyle plus continuous color mappings train across layers through one weakly
axes-owned registry. Public immutable scale policies make ordering, missing values,
limits, infinite values, palettes, and guide titles explicit while retaining ordinary
Matplotlib artists and existing date-axis behavior.

:func:`ggstyle.guides` derives native legends and colorbars from the complete trained
registry. Compatible color and linestyle entries merge, distinct mappings coexist, and
managed guides refresh with later layers without replacing caller-owned guides. Artist,
scale, guide, date, and axes mutations remain transactional across failed construction
and refresh paths.

Line, point, ribbon, and guide results now implement
:class:`ggstyle.RenderedResult`. ``as_dict()`` exposes bounded JSON-compatible audit data
and ``describe()`` renders the same data as deterministic strict JSON without axes or
live artists. Concrete results continue to expose their native geometry-specific
objects.

Release gates verify equivalent pandas and Polars semantics, bounded time and memory for
representative multi-layer rendering, an executable semantic gallery, clean-wheel
inspection and rendering, supported Python/dependency profiles, documentation, typing,
and visual regressions.

0.4.0 (2026-09-15)
------------------

Version 0.4 adds a publication-finishing layer that adopts existing Matplotlib axes.
:func:`ggstyle.finish` coordinates plot titles, layout-managed subtitles and captions,
axis titles, numeric labellers, parameterized themes, and managed endpoint labels as one
validated transaction. Dry runs return the same :class:`ggstyle.FinishPlan` retained by
successful results; plans and date-axis summaries now expose deterministic, strict-JSON
inspection without live artists or callables.

Locale-independent percent, currency, grouped-number, and SI labellers install through
ordinary ``FuncFormatter`` objects. Public qualitative, sequential, and diverging
palettes provide immutable values, explicit missing and out-of-bounds policies, and
colour-vision regression gates. Theme recipes add proportional base sizing, font-family
selection, validated overrides, and a documented safe boundary for existing axes.

Line-series endpoint labels match source colours, resolve vertical collisions in display
space, reserve a constrained-layout right margin, and use a whole-plot legend-or-raise
fallback when an artist or geometry is unsupported. Repeated requests reuse managed
annotations, and commit failures restore prior labels, legends, themes, formatters, and
layout state.

:func:`ggstyle.save` adds explicit physical dimensions, deterministic SVG/PDF metadata,
tight or standard bounds, transparency policy, atomic overwrite protection, and figure
state restoration. The clean-wheel smoke test now covers finishing, direct labels,
collapsed coordinates, and export.

The documentation includes an executable finishing and theme gallery, inspection and
migration guidance, an explicit tool-selection boundary, a human pilot protocol, link
checking, and GitHub Pages deployment. Stable minimum and newest dependency profiles,
the pinned visual renderer, typing tests against the wheel, and the full Python/platform
matrix remain release-blocking.

0.3.0 (2026-09-15)
------------------

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

Public fluent methods now retain :class:`ggstyle.DateAxis` in downstream type checking.
Release CI covers Python 3.10 through 3.13, representative Linux/macOS/Windows jobs,
reproducible minimum and newest-stable dependency profiles, the pinned pixel renderer,
registry performance, and a headless plot imported from the built wheel. Offset parsing
accepts both legacy and modern pandas frequency spellings across the supported pandas
2.x and 3.x families.

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
