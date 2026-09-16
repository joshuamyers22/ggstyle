# ADR 0006: Reuse the facet callback boundary for Cartesian grids

- Status: accepted
- Date: 2026-09-15
- Applies to: the v0.6 faceting workstream

## Context

PR22 made row, column, ordering, unobserved-level, missing-value, and empty-combination
policy explicit in ``FacetPlan``. PR23 proved the native callback renderer for
one-variable wraps. Grid rendering should reuse those contracts without repartitioning
data, introducing a second callback shape, or inferring order from Matplotlib subplot
creation.

A two-variable grid differs structurally from a wrap: every resolved row-by-column level
combination owns a stable position, including combinations with no source observations.
Row-only and column-only grids are useful degenerate forms and should not require a
separate API.

## Decision

PR24 generalizes ``facets()`` to accept the same ``row``, ``col``, ``row_order``, and
``col_order`` policy as ``facet_plan()``. Supplying a positive ``wrap`` continues to
select a one-variable column wrap. Omitting ``wrap`` creates a row-only, column-only, or
two-variable grid. At least one facet variable is always required.

The renderer consumes ``FacetPlan.panels`` without deriving a second order. It creates
the exact planned rectangle, aligns axes and defensive dataframe subsets with that
row-major panel tuple, and invokes the existing ``callback(panel_data, ax)`` contract for
every panel. Empty combinations are not skipped: callbacks receive correctly typed empty
pandas or Polars frames, or empty selected mapping columns.

Until styled facet strips land, native axes titles list values in row-then-column order.
The axes label records both variable names and values for inspection and accessibility.
Missing retained levels use the same visible ``NA`` representation as wrap facets.

Explicit order and pandas/Polars categorical order remain planner responsibilities. The
renderer neither sorts nor drops levels. The existing maximum-panel check therefore runs
before any Cartesian figure or dataframe subset is allocated.

## Consequences

- Wrap and grid layouts share one public result, callback, failure, copying, inspection,
  theming, and native-axis contract.
- Empty-panel behavior is observable and testable instead of depending on plotting
  callbacks or Matplotlib autoscaling accidents.
- PR25 can apply shared collapsed-date registry semantics to both layout forms without
  changing panel partitioning or callback invocation.
- PR26 can replace plain composite titles with row and column strips without changing
  axes order or panel identity.
