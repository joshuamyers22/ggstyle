Facet planning
==============

The v0.6 facet foundation separates data partitioning and layout decisions from figure
creation. :func:`ggstyle.facet_plan` validates the complete request and returns an
immutable :class:`ggstyle.FacetPlan` without creating Matplotlib axes or retaining the
source frame.

Wrap plans
----------

A wrap plan uses one column and a maximum number of layout columns:

.. code-block:: python

   plan = gs.facet_plan(
       frame,
       col="series",
       wrap=3,
       scales="free_y",
       max_panels=12,
   )

   plan.shape
   plan.panels[0].values
   plan.panels[0].indices

Levels use stable first-seen order for ordinary columns. Pandas categorical and Polars
categorical/enum columns preserve their declared order. Pass ``col_order=`` to make that
order independent of frame metadata. Observed levels are retained by default;
``include_unobserved=True`` creates empty panels for declared levels with no rows.

Grid plans
----------

Supplying row and column variables creates their row-major Cartesian product:

.. code-block:: python

   plan = gs.facet_plan(
       frame,
       row="region",
       col="metric",
       row_order=("North", "South"),
       scales="fixed",
   )

Grid combinations remain present when no source rows select them. This makes empty-panel
behavior part of the plan instead of an accident of rendering. A row-only plan has one
layout column; a column-only plan has one layout row.

Missing values and safeguards
-----------------------------

``missing="drop"`` excludes a source row when any facet value is missing and reports the
count in ``diagnostics``. ``"keep"`` creates a final ``None`` level, while ``"raise"``
rejects the first missing row. The default ``max_panels=64`` limit is checked before
panel descriptions are allocated; raising it is always an explicit caller decision.

``scales`` accepts ``"fixed"``, ``"free_x"``, ``"free_y"``, or ``"free"``. PR22 records
that policy only. Later rendering work applies coordinate sharing and synchronizes fixed
collapsed-date axes.

Inspection and rendering boundary
---------------------------------

``plan.as_dict()`` returns bounded strict-JSON data with panel row counts but not every
source index. ``plan.describe()`` formats the same payload deterministically. Concrete
panels retain immutable positional ``indices`` for the callback renderer planned next.

PR22 deliberately creates no figure, axes, artists, strips, guides, or labels. Until the
callback renderer lands, use the planned indices to partition data and construct native
Matplotlib panels directly.
