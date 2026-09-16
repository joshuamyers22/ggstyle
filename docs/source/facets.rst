Facet planning and rendering
============================

The v0.6 facet foundation separates data partitioning and layout decisions from figure
creation. :func:`ggstyle.facet_plan` validates the complete request and returns an
immutable :class:`ggstyle.FacetPlan` without creating Matplotlib axes or retaining the
source frame.

Render facets
-------------

:func:`ggstyle.facets` turns a validated wrap or grid policy into an owned Matplotlib
figure and row-major tuple of ordinary axes. A one-variable wrap looks like:

.. code-block:: python

   grid = gs.facets(
       frame,
       col="series",
       wrap=3,
       scales="free_y",
       theme="minimal",
       max_panels=12,
   )
   grid.map(lambda panel, ax: gs.line(panel, x="date", y="value", ax=ax))
   grid.map(lambda panel, ax: gs.points(panel, x="date", y="value", ax=ax))

``grid.figure`` is a native :class:`matplotlib.figure.Figure`; ``grid.axes`` contains one
native :class:`matplotlib.axes.Axes` per planned panel. Rectangular cells beyond the panel
count are removed. Plain axes titles identify facet values, including ``NA`` for a kept
missing level. Styled strips and shared figure labels arrive in the later presentation
workstream.

Omit ``wrap`` and provide ``row``, ``col``, or both to render a grid. Two-variable grids
materialize the complete row-by-column Cartesian product already recorded in the plan:

.. code-block:: python

   grid = gs.facets(
       frame,
       row="region",
       col="metric",
       row_order=("North", "South"),
       col_order=("Revenue", "Margin"),
       include_unobserved=True,
   )
   grid.map(lambda panel, ax: gs.line(panel, x="date", y="value", ax=ax))

Axes and callbacks follow row-major plan order. Empty combinations remain real panels and
receive empty subsets of the same pandas or Polars dataframe type. Titles list resolved
values in row-then-column order; native axes labels retain the corresponding variable
names for inspection and accessibility.

Callbacks run in plan order as ``callback(panel_data, ax)``. Pandas and Polars inputs
retain their dataframe type, mapping inputs become dictionaries of selected columns, and
every call receives a fresh defensive subset. Callback return values are ignored, making
repeated ``map`` calls a simple way to add layers. If a callback raises,
:class:`ggstyle.FacetCallbackError` identifies its panel and chains the original error.
Earlier arbitrary callback mutations cannot be rolled back safely and remain visible.

``scales`` wires native Matplotlib sharing at subplot construction: ``fixed`` shares both
axes, ``free_x`` shares only y, ``free_y`` shares only x, and ``free`` shares neither.
Shared collapsed-date registry training remains deferred to its dedicated integration
workstream.

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

``scales`` accepts ``"fixed"``, ``"free_x"``, ``"free_y"``, or ``"free"``. Pure plans
record that policy without rendering; :func:`ggstyle.facets` applies native sharing for
wrap layouts.

Inspection and rendering boundary
---------------------------------

``plan.as_dict()`` returns bounded strict-JSON data with panel row counts but not every
source index. ``plan.describe()`` formats the same payload deterministically. Concrete
panels retain immutable positional ``indices`` used by the callback renderer.

Pure planning still creates no figure, axes, artists, callbacks, or global state. PR23
adds wrap rendering and PR24 extends the same callback boundary to grids. Shared date
registries follow in PR25; styled strips, shared labels, and guide collection follow in
PR26.
