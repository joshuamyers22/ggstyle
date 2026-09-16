# ADR 0007: Bind facet date registries to fixed/free x semantics

- Status: accepted
- Date: 2026-09-15
- Applies to: the v0.6 faceting workstream

## Context

PR23 created Matplotlib ``sharex`` and ``sharey`` relationships from the facet scale
policy, and PR24 reused them for Cartesian grids. Structural sharing gives ordinary
numeric panels common limits, but it is insufficient for collapsed dates: independently
trained observation registries can assign the same date different ordinal coordinates.

Facet callbacks are intentionally geometry-agnostic, so the grid cannot know which
column represents x before a callback draws. Empty panels also have no observations and
must not be given fabricated date provenance merely to satisfy a rectangular layout.

## Decision

PR25 adds the explicit fluent ``FacetGrid.dates()`` operation. Users call it after the
first date layer is mapped. It discovers supported date-bearing panel artists through the
existing date-axis boundary and applies ``mode="collapse"`` by default.

``fixed`` and ``free_y`` layouts have fixed x coordinates. Their populated panels pass
through one ``sync_dates()`` transaction and own one live revisioned observation
registry. ``free_x`` and ``free`` layouts synchronize each populated panel as a singleton,
preserving independent registries and visible ranges. No separate facet date registry is
introduced.

An empty fixed-x panel remains handle-free but inherits the transform and limits of its
native shared-x group. Inspection aligns ``date_handles`` with panel axes using ``None``
for such panels. Numeric-only grids are rejected by ``dates()`` rather than interpreted
as Matplotlib date numbers.

The chosen policy persists on the grid. Later ``map()`` passes defer semantic helpers'
otherwise eager registry scans and publish one group refresh after every callback
completes. Newly populated panels cause the configured groups to be rebuilt. A callback
failure retains the existing documented partial-artist behavior and always releases the
refresh deferral.

Fixed-group synchronization inherits ``sync_dates()`` prepare/commit rollback. Facet
cleanup disposes handles created only by a failed integration request. Inspection records
mode, limits, handle count, and registry-group count without serializing observations.

## Consequences

- The same date maps to the same collapsed coordinate in every fixed-x populated panel.
- Free-x panels cannot leak observations or visible ranges into one another.
- Empty panels remain visually comparable under fixed x without claiming false data.
- Multiple semantic layers avoid an accidental panel-squared registry-rescan pattern.
- Date integration remains explicit and uses existing public date semantics rather than
  teaching the facet renderer about x column names.
- PR26 can collect labels and guides without changing coordinate ownership.
