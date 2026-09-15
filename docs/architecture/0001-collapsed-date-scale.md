# ADR 0001: Use a registered scale for collapsed date coordinates

- Status: accepted
- Date: 2026-09-15
- Applies to: the v0.3 collapsed-coordinate redesign

## Context

Version 0.2 implements collapsed dates by replacing the x data of selected
`Line2D` artists with observation ordinals and retaining copies keyed by Python
object IDs. That model cannot safely cover collections, artists added after
adoption, arbitrary transforms, shared registries, or partial failures. It also
makes every new artist type responsible for duplicating coordinate conversion and
restoration logic.

Matplotlib already separates unit conversion from axis scaling. A registered x
scale can receive Matplotlib date numbers after unit conversion, map them to a
continuous observation-ordinal display coordinate, and supply the inverse mapping.
The focused executable spike demonstrated that this route works without rewriting artist
geometry; its cases now live as production regressions in `tests/test_date_scale.py`.

## Decision

The production collapsed-coordinate engine is a registered Matplotlib
`ScaleBase`. Artist-specific mutation adapters are not a second coordinate
architecture. Discovery adapters may inspect artists to build provenance and
diagnostics, but they must not rewrite their geometry.

The proof of concept establishes these properties:

| Capability | Result | Contract |
| --- | --- | --- |
| `Line2D` | Pass | Calendar x data remains unchanged; `transData` collapses gaps. |
| `PathCollection` (`scatter`) | Pass | Offsets use the same scale through `transData`. |
| `PolyCollection` (`fill_between`) | Pass | Path vertices use the same scale without mutation. |
| Native `axvline` | Pass | Its blended transform applies the x data scale. |
| Date limits and autoscaling | Pass | Limits remain Matplotlib date numbers. |
| Shared x axes | Pass | Every shared axes receives an equivalent scale instance. |
| Inverse coordinate readout | Pass | The scale transform is invertible inside and outside the registry. |

This is the sole production direction. The private implementation lives in
`ggstyle._date_scale`, and `DateAxis` installs or removes it when switching modes.

## Coordinate mapping

Observed dates are unique, sorted Matplotlib date numbers called *knots*. For two
or more knots, knot `i` maps exactly to ordinal `i`; values between knots are
piecewise-linearly interpolated. Outside the observed domain, both forward and
inverse transforms use the median positive adjacent knot difference as one ordinal
unit. The median is deterministic and resists a single unusually large boundary
gap.

A one-knot registry uses one calendar day per ordinal unit in both directions. An
empty registry cannot enter collapsed mode. Non-finite values remain non-finite,
and duplicate observations are removed before a transform is constructed. The
mapping must be monotone and round-trip, including beyond either endpoint.

The scale changes display coordinates only. Artist x data, axis limits, and public
locations remain Matplotlib date numbers. `DateAxis.loc()` therefore parses, validates,
and optionally snaps a date but returns its native date number; it must not apply the
scale a second time. `date_at()` converts the native data coordinate returned by
Matplotlib's inverted `transData`. Direct access to ordinal positions remains private to
the scale transform. This intentionally replaces v0.2's mode-dependent `loc()` result
and requires a migration note in the implementation PR.

## Observation provenance

The observation registry is an owned, revisioned object. Each contribution records
its source as explicit input or a supported native artist.
Its effective observations are the sorted unique union of live contributions.

- Dates passed explicitly to `gs.dates(ax, data=...)` are sticky. Repeated calls add
  explicit observations. They remain until a future explicit replacement or removal
  operation is invoked.
- Supported artists contribute dates obtained from their original input or unit-aware
  data, never from screen coordinates. Lines, scatter collections, and polygon
  collections are required initial sources. A collection-only chart must therefore
  build a complete registry or fail preflight with an instruction to supply `data=`.
- Invisible artists still contribute because visibility is presentation state.
  Removed artists stop contributing on the next registry rebuild. Mutated artists
  replace their prior contribution on that rebuild.
- ggstyle-managed annotations, ticks, grids, captions, and other decorations never
  contribute observations.
- Third-party collection adapters are not public in v0.3. An unrecognized date-bearing
  artist is unsupported, not silently ignored; explicit dates do not make an unsupported
  transform safe.

Registry rebuilds may shrink the effective union when a contributing artist is
removed or mutated. Explicit contributions do not shrink as a side effect of artist
changes.

## Coordinate-space and transform ownership

The owning `Axes` determines an artist's x coordinate system, including on twin
axes. The supported transform boundary is:

- ordinary `ax.transData`;
- public blended transforms whose x branch is the owning axes' data transform,
  including the transform used by `axvline` for rendering. Blended-transform
  presentation artists do not contribute observations.

Axes-, figure-, display-, or otherwise arbitrary transforms do not contain date
observations. An artist that appears date-bearing but uses an unsupported transform
fails preflight.

With the scale architecture, supported artists added with datetime-like original x values are
safe before or after collapse: Matplotlib unit conversion supplies date numbers and
the scale supplies display positions. Raw numeric x values are ambiguous. They are
accepted from lines only when the complete dates supplied through `dates(ax, data=...)`
cover them; numeric ordinal input is not inferred. A refresh rejects an ambiguous
candidate instead of guessing.

## Refresh lifecycle

The public refresh operation performs one transaction in this order:

1. rescan supported artists on every live axes in the registry group;
2. discover provenance and validate transforms and coordinate spaces;
3. build a complete candidate registry snapshot and increment its revision;
4. prepare scale instances, tick plans, annotations, limits, and diagnostics;
5. commit the candidate to every attached handle and request redraws.

Refresh rebuilds observations from current live sources. It does not capture or
rewrite artist geometry. Existing view limits are preserved as date-number bounds,
so the visible date domain is stable even when new registry knots move screen
positions. A private cosmetic render path may redraw ticks and managed artists
without rescanning or rebuilding.

If discovery or preparation fails, nothing is committed. If commit fails, the prior
registry revision, scales, limits, tick state, annotations, and configuration are
restored before the exception escapes. Re-entrant callbacks are guarded.

## Synchronization and ownership

`sync_dates()` attaches its handles to one shared registry object rather than copying a
union into independent arrays. Refreshing any member rescans all live member axes,
commits one new revision, invalidates all member scale transforms, and redraws all
members. A registry change may move artists on every synchronized axes; their date
limits remain unchanged unless the caller explicitly requests a new union or
intersection view.

The registry holds member handles weakly; each live handle owns its Matplotlib axes.
Disposing a handle detaches it, releases registry and managed-artist references, and
disconnects callbacks. The remaining group is unchanged and excludes that axes on its
next refresh. Disposal is idempotent and managed artists already removed externally are
treated as absent.

## Discovery and diagnostics

Discovery traverses supported data artists owned by each axes (`lines` and
`collections`) exactly once. It does not recursively treat children of supported
containers as additional sources, and it excludes managed decorations and artists
whose x transform is not data-bearing. Visibility does not alter traversal.

The v0.3 policy for an ambiguous or unsupported date-bearing artist is a
dedicated ggstyle exception raised during preflight, with the artist class where
available, the unsupported transform or coordinate space, and a corrective action.
There is no permissive warning mode in v0.3.

## Configuration and managed artists

Every public mutator validates its full proposed configuration and prepares all
Matplotlib objects before changing handle or axes state. Its reset vocabulary must
distinguish:

- omitted: leave the existing value unchanged;
- automatic/reset sentinel: restore ggstyle's automatic value; and
- `False` or an explicit disable sentinel: remove the feature.

Invalid timezone, formatter, cadence, range, alignment, grid, or annotation input
leaves the last valid configuration usable. Managed annotations have public enumeration
and bulk-removal operations. Replay and disposal tolerate external artist removal,
disconnect callbacks, and release registry references.

## Consequences

The scale applies one mapping uniformly to current and future Matplotlib artists,
keeps original calendar geometry authoritative, and removes the need for ID-keyed
restoration snapshots. Collections no longer need bespoke vertex or offset
remapping. The implementation installs the scale before rebuilding
ggstyle locators and formatters because `set_xscale()` may replace them, and registry
changes must install or invalidate an immutable transform snapshot transactionally.

The scale is verified on the minimum and pinned Matplotlib environments in addition to
the ordinary CI matrix.
Transforms outside the declared boundary remain explicit exclusions. The subsequent
roadmap should treat scatter and polygon work as provenance, diagnostics, and
regression coverage—not as geometry-mutation adapters.

PR5 implements the owned revisioned registry, line and scatter provenance, live
synchronization, transactional refresh rollback, and weak disposal semantics described
above. PR6 adds native `fill_between` provenance without mutating geometry. The isolated
decoder uses public paths and codes to select the mirrored source-side x vertices from
every polygon path; it excludes closing endpoints and interpolation crossings. Modern
Matplotlib identifies these artists as `FillBetweenPolyCollection`, while supported older
versions expose the same topology as `PolyCollection`, so both environments are tested.
Midpoint-stepped paths cannot reproduce their omitted interior source dates and therefore
require complete explicit `data=`. `fill_betweenx`, unrecognized polygons, and non-data
transforms fail preflight.

## Rejected alternative

Artist-by-artist mutation was rejected. It requires a growing adapter for every
artist representation, creates partial-mutation and stale-snapshot failure modes,
cannot naturally cover artists added while collapsed, and makes shared-registry
updates expensive and fragile. Maintaining it alongside a registered scale would
double the semantic and testing surface without adding a supported capability.
