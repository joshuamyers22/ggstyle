# ADR 0005: Render native wrap facets through explicit callbacks

- Status: accepted
- Date: 2026-09-15
- Applies to: the v0.6 faceting workstream

## Context

ADR 0004 separated pure facet partition and layout policy from rendering. The next layer
must turn a validated one-variable wrap plan into useful small multiples without adding a
grammar compiler, hiding Matplotlib axes, or coupling dataframe partitioning to semantic
geometry helpers. It must also preserve the panel-count guard and the pandas/Polars
boundary already established by the planner.

Callbacks can execute arbitrary user code. A renderer therefore cannot promise complete
transactional rollback of titles, limits, artists, third-party state, and external side
effects. This limitation needs to be explicit and diagnosable rather than implied away.

## Decision

PR23 adds the public ``facets()`` constructor and ``FacetGrid.map()``. The constructor
validates a one-variable wrap through ``facet_plan()``, takes defensive per-panel data
snapshots before creating a figure, and returns a grid that owns an ordinary Matplotlib
``Figure`` and a row-major tuple of ordinary ``Axes``.

The figure uses constrained layout. Native ``sharex`` and ``sharey`` relationships are
selected from the recorded fixed/free policy at subplot construction, because those
relationships are structural. Unused cells in the rectangular wrap are deleted. Native
axes titles provide an initial visible and accessible panel identity; richer strip
presentation remains separate.

Each ``map(callback)`` pass invokes ``callback(panel_data, ax)`` once per panel and returns
the same grid so callers can add layers. Pandas and Polars subsets preserve their type;
mapping inputs receive selected column dictionaries. Every pass receives fresh copies,
so ordinary dataframe or column assignment cannot mutate the source or corrupt later
layers. Nested mutable Python objects inside cells retain the dataframe library's normal
copy semantics. Callback returns are not stored because artists already belong to the
native axes.

Callback failure raises ``FacetCallbackError`` with the panel index, values, completed
call count, and original exception as its cause. Changes made by earlier callbacks remain
visible; guessing how to reverse arbitrary user code would be unsafe. A failed pass does
not increment the grid's completed map count.

Inspection is bounded and strict JSON. It includes the pure plan, active panel count,
theme name, diagnostics, and completed map count, but excludes source data, concrete row
indices, figures, axes, callbacks, and callback results.

## Consequences

- Users can mix native Matplotlib calls and ggstyle semantic helpers inside one stable
  callback boundary without a new declarative grammar.
- Source frames and subsequent mapping passes are insulated from callback mutation.
- Structural native axis sharing is present now, while PR25 still owns shared
  collapsed-date registries and their refresh lifecycle.
- PR24 can add row/column grid rendering over the same planner and callback contract.
- PR26 can replace plain titles with styled strips and add shared labels and collected
  guides without changing how panels receive data.
- Callback failure is contextual and honest but intentionally not transactional.
