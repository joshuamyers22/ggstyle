# ADR 0004: Separate facet planning from native panel rendering

- Status: accepted
- Date: 2026-09-15
- Applies to: the v0.6 faceting workstream

## Context

The v0.5 semantic helpers provide stable dataframe mappings, native artists, axes-owned
scales, automatic guides, and bounded result inspection. Faceting can now build on those
contracts, but immediately combining dataframe partitioning, subplot creation, callback
execution, date synchronization, free scales, strips, labels, and guide collection would
make failures difficult to localize.

The product plan selects native Matplotlib subplots and callback-based mapping. It also
requires category order, observed and unobserved levels, missing values, empty panels,
fixed/free scales, and panel-count safeguards to be explicit rather than consequences of
Matplotlib layout behavior.

## Decision

PR22 adds a pure public :func:`facet_plan` boundary. It accepts a dataframe-like object,
validates wrap or grid policy, and returns immutable row-major `FacetPanel` partitions in
a `FacetPlan`. Planning creates no figure, axes, artists, callbacks, or global state and
does not retain the source frame.

One-variable wrapping uses ``col=`` plus a positive ``wrap=`` column limit. Grid planning
accepts row, column, or both dimensions and retains the Cartesian product of resolved
levels, including empty combinations. Ordinary levels use first-seen order; explicit and
categorical orders are preserved. Unobserved declared levels are opt-in. Missing facet
values are dropped, retained as a final level, or rejected through one explicit policy.

Every request has a positive ``max_panels`` limit, defaulting to 64. The candidate panel
count is checked before panel descriptions are allocated. Scale sharing is validated and
recorded as ``fixed``, ``free_x``, ``free_y``, or ``free`` but is not applied in PR22.

The concrete plan retains source-row positions needed by the next callback renderer.
Bounded inspection reports only per-panel row counts, so JSON size depends on the guarded
panel count rather than input-row count.

## Consequences

- Partition, ordering, missing-value, shape, and safety failures are testable without a
  renderer or GUI backend.
- pandas and Polars share one positional partition contract.
- PR23 can create ordinary Matplotlib axes and invoke callbacks from an already validated
  plan.
- PR24 can extend the same planner to richer grid and empty-panel rendering without
  changing the partition boundary.
- PR25 owns coordinate sharing and collapsed-date synchronization; PR26 owns strips,
  shared labels, and guide collection.
- Plans intentionally do not serialize recipes or source data and are not a round-trip
  dataframe format.
