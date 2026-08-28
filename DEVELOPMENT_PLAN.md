# ggstyle post-0.1 development plan

Status: proposed

Target: `v0.2.0`

Starting point: `v0.1.0` (`bdd31d0`)

Last updated: 2026-08-26

## 1. Objective

The next development cycle should make collapsed date axes safe for the Matplotlib
artists users commonly place on time-series charts, then build higher-level conveniences
on that foundation. The cycle should not broaden the public plotting API until coordinate
remapping is correct, reversible, documented, and covered by image-level regression tests.

The required outcome is a focused `v0.2.0` safety release that:

- correctly handles lines, points, and interval bands in collapsed and expanded modes;
- detects unsupported artists instead of silently drawing misleading output;
- adds deterministic visual regression coverage;
- documents the lifecycle and coordinate-space contract; and
- preserves the clean-code and documentation standards established in `v0.1.0`.

An explicit uncertainty-ribbon API, hosted gallery, palettes, and numeric formatters are
follow-on `v0.2.x` or `v0.3.0` work. They may be developed after the safety gate, but they
must not delay the coordinate-correctness release or enter the public API before the
underlying collection support has geometry and image regression coverage.

Faceting and direct labels remain valuable, but should follow this work. Building facets
before all panels share reliable artist and coordinate semantics would multiply defects
and make them harder to isolate.

## 2. Guiding constraints

### 2.1 Statistical integrity

- Never infer, fit, or label a statistical interval on the user's behalf.
- A ribbon accepts explicit lower and upper values and a caller-provided label.
- Missing values create visible breaks unless the caller explicitly chooses another
  documented policy.
- Collapsing an axis changes coordinates only. It must not resample, aggregate,
  interpolate, reorder, or otherwise alter observations.
- Unsupported or ambiguous date-bearing artist types must fail preflight by default. An
  explicitly requested permissive mode may emit a targeted warning instead.

### 2.2 API discipline

- Extend `DateAxis` only where behavior is inherently date-axis behavior.
- Prefer small typed functions over a general grammar-of-graphics abstraction.
- Keep Matplotlib available as the escape hatch.
- Preserve method chaining where configuration methods already return `DateAxis`.
- Treat all new public names as compatibility commitments under semantic versioning.
- Do not add `**kwargs` merely to avoid designing a stable signature.

### 2.3 Engineering quality

- Keep coordinate transforms separate from artist discovery and mutation.
- Store enough original state to make `collapse()` and `expand()` lossless and
  repeatable.
- Make repeated calls idempotent.
- Avoid relying on private Matplotlib attributes when a public API exists. Any unavoidable
  private dependency must be isolated, version-tested, and documented.
- New modules and public APIs require NumPy-style docstrings, user-guide coverage,
  release notes, and examples consistent with statsmodels' documentation structure.
- Artist mutation is transactional: discovery and validation complete before any artist is
  changed. If any adapter cannot prepare its new state, the axes remains unchanged.
- Correctness guarantees cover geometry, masks, path codes, limits, units/converters,
  autoscaling state, axis inversion, synchronization, and callbacks where applicable. Any
  state intentionally excluded from reversibility must be listed in the public limitations.
- Callback re-entry must be guarded. Thread safety is not promised unless explicitly
  implemented and tested.

## 3. Required design decisions before implementation

No collection adapter PR begins until these contracts are recorded in an architecture
note and represented by executable tests. Open questions must not be resolved implicitly
inside adapter code.

### 3.1 Observation provenance

The observation registry must record where each date came from. The architecture note must
define precedence and removal semantics for:

1. dates explicitly supplied through `gs.dates(ax, data=...)`;
2. supported date-bearing line and collection artists;
3. hidden, removed, unsupported, and third-party artists; and
4. annotations, which must not contribute observations.

It must also decide whether mutating or removing an artist can shrink the registry. A
collection-only chart must either establish a complete registry from supported artists or
fail with an actionable request for explicit date data; it must never collapse against an
accidentally incomplete line-only registry.

### 3.2 Coordinate-space ownership

Numeric coordinates are inherently ambiguous while an axes is collapsed. An artist added
in collapsed mode cannot be guessed to contain expanded date numbers or ordinal positions.
Therefore, such an artist must be created through a ggstyle helper, explicitly registered
with its coordinate space, or rejected during refresh. Automatic inference is not part of
the correctness contract.

Adapters must declare which transforms they support. The initial policy is:

- support ordinary `ax.transData`;
- explicitly enumerate any supported blended transform whose x component is data-space;
- reject other transforms before any mutation; and
- treat twin-axis collections according to their owning axes, never merely by membership
  in a figure.

### 3.3 Refresh and synchronization lifecycle

The refresh API must define separately whether it rescans artists, recaptures expanded
geometry, rebuilds observations, remaps against the current registry, and preserves view
limits. If one method performs several of these operations, its ordering and failure
behavior must be documented.

Synchronized handles require an owned shared-registry object rather than independent array
copies. The design must specify propagation when one axes changes, revision ownership,
axes removal, refresh scope, and whether registry changes may move existing artists. No
automatic cross-panel update is claimed until these semantics are implemented and tested.

### 3.4 Diagnostics and atomicity

Discovery must define its traversal boundary, including containers, visibility, nested
artists, and non-data decorations. Ambiguous date-bearing artists fail preflight by default.
A permissive mode may downgrade this to one deduplicated, actionable warning per artist
class using a public ggstyle warning category. A warning is never described as proof that
collapse succeeded safely.

Collapse and expand use a prepare/commit model: prepare every adapter result and validate
the complete artist set first, then commit all changes. Failure during preparation leaves
all artists and axes state unchanged; failure during commit must roll back captured state.

## 4. Branch and delivery strategy

Use short-lived branches from the protected release branch, one concern per pull request.
If a long-lived `develop` branch is retained, document why it is worth its divergence and
forward-merge cost. The proposed sequence is:

1. `feature/coordinate-transform`
2. `test/visual-regressions`
3. `feature/scatter-remapping`
4. `feature/polygon-remapping`
5. `docs/collapse-safety`

Merge each branch only after its focused tests and the full CI suite pass. Keep `main`
releasable. Urgent fixes branch from `main` and are merged forward into any active release
branch.

## 5. Workstream A: coordinate-transform foundation

### Goal

Replace artist-specific coordinate arithmetic with one internal, testable mapping object.

### Proposed internal design

Add a private immutable numeric mapping object, tentatively
`_CollapsedDateTransform`, responsible for:

- mapping date numbers to collapsed observation coordinates;
- mapping collapsed coordinates back to date numbers where the mapping is defined;
- applying the established interpolation rule; and
- exposing observation-domain bounds.

Datetime parsing, timezone validation, strict lookup, and snapping remain outside this
object. They are input and lookup policies, not properties of the numeric mapping.

The transform must not know about `Line2D`, `PathCollection`, or `PolyCollection`.
Artist adapters consume it. This separation allows mapping rules to be tested with plain
arrays and prevents every artist type from implementing slightly different gap behavior.

### Required behavior

- Exact observations map to their stable ordinal positions.
- Dates inside gaps use the same interpolation rule as `DateAxis.loc()`.
- Dates outside the observation domain use an explicitly approved extrapolation rule. The
  current median-gap behavior is retained only if tests demonstrate acceptable semantics;
  strictness remains a `DateAxis.loc()` lookup policy.
- `NaT` and masked values survive as missing markers; they are never interpreted as the
  current time or coerced to a real observation.
- A transform built from synchronized panels uses their shared observation registry.
- Forward and inverse mappings round-trip exact observations.
- Duplicate dates remain valid and map to the same coordinate.
- Unsorted artist vertices retain their input order.
- Scalar and array inputs preserve documented shape, mask, and finite-value semantics.
- Zero- and one-observation registries, infinities, floating-point equality, repeated
  knots, extrapolation, and inverse-domain failures have explicit behavior and tests.

### Acceptance criteria

- `DateAxis.loc()`, line remapping, and future collection adapters use the same transform.
- No behavior regression in the suite recorded at the `v0.1.0` branch point. Do not use a
  hard-coded test count as a gate.
- Unit tests cover daily, intraday, irregular, timezone-aware, duplicate, unsorted,
  missing, and empty inputs.
- Property-style tests verify monotonic mapping for monotonic finite inputs and exact
  round trips at observations.

## 6. Workstream B: reversible collection remapping

### Goal

Support the Matplotlib collections most relevant to date charts without corrupting artist
geometry or losing the original expanded coordinates.

### Initial supported matrix

| Artist/API | Matplotlib type | `v0.2.0` target |
|---|---|---|
| `ax.plot` | `Line2D` | Preserve existing support through the shared transform |
| `ax.scatter` | `PathCollection` | Remap finite x offsets and preserve masks |
| `ax.fill_between` | `FillBetweenPolyCollection`/`PolyCollection` | Remap x vertices for every path |
| `ax.fill_betweenx` | collection with date-valued y | Explicitly unsupported on an x-date handle |
| `ax.eventplot` | `EventCollection` | Evaluate after scatter and ribbons; warn if deferred |
| third-party custom collections | arbitrary subclass | Detect and warn unless an adapter is registered |

### State model

Use a `weakref.WeakKeyDictionary` keyed by artist object, not integer `id()`, so removal
does not leak state and object-id reuse cannot associate stale geometry with a new artist.
Each adapter entry records:

- the artist type and supported adapter;
- the exact per-adapter fields needed to restore coordinates, masks, path codes, unit and
  converter state, sticky edges, and relevant autoscale state;
- the artist's explicitly known coordinate space;
- the observation-registry revision used for its current mapping.

Never derive expanded coordinates by inverting already-mutated geometry when the original
coordinates are available. `expand()` restores captured originals. `collapse()` always
recomputes from originals against the current observation registry, which prevents drift
after repeated mode switches.

### Mutation scenarios to support

- Artist exists before `gs.dates(ax)` adopts the axes.
- Artist is added after adoption but before collapse.
- Artist is added while already collapsed through a ggstyle helper or explicit
  coordinate-space registration; ambiguous native additions are rejected.
- Existing artist data is changed with `set_data`, `set_offsets`, or equivalent.
- New observations are added and the collapsed registry expands.
- Artist is removed between mode changes.
- Multiple axes are synchronized, then one receives additional data.
- `collapse().expand().collapse()` produces the same collapsed geometry.

Automatic detection of in-place artist mutation is not assumed. Provide an explicit
refresh operation with the rescan/recapture/rebuild/remap semantics defined in Section
3.3, and document exactly when it is required. Do not pretend stale geometry is current.

### Adversarial tests

- Scatter offsets with masked x or y values.
- `fill_between` with crossing bounds, `where=`, `interpolate=True`, and internal NaNs.
- Several disconnected polygon paths in one collection.
- Shared x arrays that are non-contiguous or read-only.
- Empty collections and single-observation collections.
- Dates before and after the registered observation domain.
- Duplicate timestamps and daylight-saving transitions.
- Collection transforms that are not `ax.transData`.
- Collections placed on twin axes.
- Repeated remapping after zooming, formatting, and synchronized-panel operations.
- Failure in the last adapter after earlier adapters have prepared changes, proving that
  collapse is atomic and leaves the axes unchanged.
- Inverted axes, shared axes, sticky edges, autoscaling, callbacks, unit converters, and
  artists removed and replaced after garbage collection.
- Large scatter and multi-path inputs sufficient to detect accidental quadratic behavior.

### Acceptance criteria

- Scatter points and `fill_between` boundaries align exactly with line observations in
  both modes.
- Expanded geometry, masks, and path codes are byte-for-byte equal where Matplotlib
  preserves input arrays, or numerically equal within a documented tolerance otherwise.
  Limits, inversion, units/converters, autoscale state, sticky edges, and callbacks are
  also restored or explicitly documented as exclusions.
- Unsupported or ambiguous date-bearing collections fail preflight by default. A requested
  permissive mode emits one actionable, filterable warning naming the artist class.
- No silent partial remapping: an artist is either handled completely or reported.
- Repeated toggling does not accumulate numerical error.
- Adapter preparation has documented complexity and representative performance checks;
  repeatedly copying every path on every cosmetic refresh is avoided.

## 7. Follow-on workstream: explicit uncertainty ribbons

### Goal

Expose interval drawing only after `fill_between` remapping is proven correct and released
or has passed the complete v0.2 safety gate. This API is not required for `v0.2.0`.

### Proposed public API

The first API should remain deliberately small:

```python
gs.ribbon(
    ax,
    dates,
    lower,
    upper,
    *,
    label=None,
    color=None,
    alpha=0.2,
    missing="break",
)
```

The module-level function is preferred because a ribbon is a plotting primitive with
y-value, styling, missing-data, and legend semantics; it is not inherently date-axis
configuration. It may register its returned collection with the axes' `DateAxis`
internally. Adding `DateAxis.ribbon()` instead requires an API review that reconciles it
with Section 2.2.

The final signature should be confirmed through a focused API review. In particular:

- `dates`, `lower`, and `upper` must have compatible one-dimensional lengths;
- crossing bounds are allowed by default. If ordered intervals are required by a concrete
  use case, expose explicit `validate_order=True` behavior with index-aware errors and
  define whether validation occurs before or after missing-value handling;
- `missing="break"` preserves gaps, while any drop policy must be explicit;
- `label` is displayed verbatim and is never synthesized as “confidence interval”;
- the return value should be the created Matplotlib collection, not a new wrapper type,
  unless lifecycle requirements demonstrate a concrete need; and
- ordinary Matplotlib styling should remain available through a narrow documented escape
  hatch rather than an unlimited undocumented argument tunnel.

### Non-goals

- Fitting regressions, smoothers, or statistical models.
- Computing standard errors, confidence levels, or prediction intervals.
- Guessing whether bounds are Bayesian, frequentist, bootstrap, or descriptive.
- Coupling `ggstyle` to statsmodels, SciPy, or a solver.

### Acceptance criteria

- A caller can plot a statsmodels-produced interval by passing its explicit bounds.
- The same collection survives collapse, expand, and re-collapse.
- Legend labels and colors behave consistently with Matplotlib.
- Invalid bounds and missing-value policy errors are clear and tested.
- Documentation explains statistical meaning remains the caller's responsibility.

## 8. Workstream C: visual regression testing

### Goal

Catch rendering defects that array assertions cannot detect.

### Approach

- Use Matplotlib's testing utilities or `pytest-mpl`; choose after a small proof of concept.
- Force the Agg backend, fixed figure sizes, fixed DPI, bundled/default fonts, and a fixed
  style context.
- Keep baseline images small and purposeful.
- Use numeric geometry assertions alongside images so a baseline update cannot conceal a
  semantic mapping defect.
- Document the baseline-update command and require reviewers to inspect image diffs.
- Pin the renderer stack, including Matplotlib, NumPy, Pillow, FreeType/font assets,
  backend, antialiasing-relevant settings, DPI, and comparison tolerance. Normalize or
  ignore non-rendering image metadata.
- Store baselines and diff artifacts under a documented retention and review policy.

### Baseline gallery

At minimum include:

1. irregular line series, expanded and collapsed;
2. scatter over a matching line;
3. `fill_between` over a matching line with an internal missing segment;
4. annotations and spans in both modes;
5. two synchronized panels with different observation sets;
6. timezone-aware intraday data; and
7. both bundled themes.

### CI considerations

- Run geometry tests on every supported Python version.
- Run pixel comparisons on one pinned Python/Matplotlib job to avoid meaningless
  cross-version raster differences.
- Keep a separate job on the lowest supported Matplotlib version for compatibility.
- Treat unexplained baseline changes as failures, not routine snapshot churn.

## 9. Follow-on workstream: hosted documentation and gallery

### Goal

Make the public package understandable without reading source or cloning the repository.
Collapse safety documentation and examples are required for `v0.2.0`; automated gallery
and Pages deployment may follow without blocking that release.

### Deliverables

- Publish Sphinx HTML from `main`, preferably to GitHub Pages.
- Generate gallery figures from executable example scripts during the docs build.
- Add a landing-page example that demonstrates adoption of an existing Matplotlib axes.
- Add focused examples for missing dates, synchronization, scatter, and ribbons.
- Link API pages, user guide, pitfalls, changelog, PyPI, and GitHub Release pages.
- Show the supported-version and known-limit statements prominently.

Generated images must come from checked example code. Do not hand-edit screenshots or
commit examples that the documentation build does not execute.

### Acceptance criteria

- Documentation builds with `-W` and doctests pass.
- Every public object appears in the API reference and docstring validator.
- Gallery examples run headlessly from a clean environment.
- Links are checked in CI or through a scheduled job.
- The README points to the hosted documentation.
- Pages permissions, deployment environment, artifact retention, fork behavior, and
  publication rollback are documented before enabling deployment.

## 10. Deferred workstream: palettes and numeric formatters

This work is explicitly outside the `v0.2.0` release gate. It belongs in `v0.2.x` or
`v0.3.0` so unrelated convenience APIs cannot delay the collapsed-axis safety release.

### Palettes

- Expose the existing Okabe-Ito-derived cycle through a typed public function.
- Define behavior for `n` beyond the qualitative palette size; never silently create
  indistinguishable colors.
- Return immutable or defensive-copy values so callers cannot mutate global state.
- Test accessibility properties and stable ordering.
- Keep theme application opt-in and import-time behavior inert.

### Formatters

Provide small formatter factories compatible with Matplotlib:

- percent;
- currency with explicit symbol and decimal count;
- grouped decimal/comma;
- SI-prefix notation; and
- possibly basis points if actual use cases justify it.

Locale-dependent behavior must be explicit. Tests should not depend on the machine locale.
Formatters belong in a focused module and must work independently of `DateAxis`.

### Acceptance criteria

- Formatters handle zero, negative values, large/small magnitudes, NaN, and infinity.
- Public signatures and output rules are documented with examples.
- Palette and formatter APIs do not mutate Matplotlib global configuration.

## 11. Proposed pull-request sequence

### PR 1: lifecycle and coordinate contracts

- Record observation provenance, coordinate-space registration, refresh,
  synchronization, diagnostic, transform-support, and transactional mutation contracts.
- Add characterization tests for current `v0.1.0` behavior.
- Decide and test the out-of-domain extrapolation rule.

### PR 2: visual regression infrastructure

- Add the pinned rendering environment and deterministic image comparisons.
- Establish line, annotation, synchronization, and theme baselines before collection
  mutation work begins.
- Document baseline generation, review, diff artifacts, and update policy.

### PR 3: transform extraction

- Introduce the private transform.
- Route `loc()` and `Line2D` through it.
- Add pure-array and regression tests.
- No new public API.

### PR 4: collection registry and scatter

- Add shared observation-registry ownership and `WeakKeyDictionary` artist state.
- Implement `PathCollection` offset remapping.
- Implement the already-approved refresh and synchronization semantics.
- Add unsupported-collection preflight and filterable diagnostics.
- Prove prepare/commit atomicity and rollback.

### PR 5: polygon and `fill_between` support

- Implement multi-path vertex remapping.
- Cover NaNs, masks, `where`, and interpolated crossings.
- Prove reversible mode switching, state restoration, and supported-transform behavior.
- Add collection geometry and pixel baselines.

### PR 6: v0.2 safety documentation and release hardening

- Document refresh, synchronization, supported artists/transforms, warning policy, and
  known exclusions.
- Add minimum, pinned-renderer, and newest-dependency CI jobs.
- Complete release notes and clean-wheel smoke testing.

### Follow-on PRs after the v0.2 safety gate

- Review and add the module-level ribbon API.
- Add hosted gallery/Pages deployment.
- Add palettes and numeric formatters.

## 12. Release gates

### API freeze gate

- Public signatures reviewed for naming, typing, return values, and error policy.
- Deprecation is preferred over breaking any `v0.1.0` behavior.
- Known limitations are explicit and testable.
- The observation, coordinate-space, refresh, synchronization, transform, diagnostic, and
  rollback contracts are approved before collection implementation begins.

### Release-candidate gate

- Full tests pass on Python 3.10 through 3.13.
- Explicit CI jobs pass for declared minimum dependencies, a fully pinned visual stack,
  and newest stable supported Matplotlib/Pandas/NumPy combinations. Constraint files or
  equivalent exact pins make each environment reproducible.
- The project documents whether dependency prereleases are informational or blocking and
  how upper bounds or urgent incompatibilities are handled.
- Coverage remains at or above the configured threshold, with meaningful branch coverage
  for all new adapters.
- Ruff, mypy, docstring validation, Sphinx warnings-as-errors, doctests, package build,
  Twine checks, and clean-wheel smoke tests pass.
- Visual baselines have been reviewed, not merely regenerated.
- `CHANGELOG.md`, release notes, README, API reference, pitfalls, and security support
  statement agree on the version and supported behavior.

### Publication gate

- Build from a clean tagged commit through trusted publishing.
- Confirm wheel and source distribution metadata before upload.
- Install the exact version from canonical PyPI in a clean supported interpreter.
- Run a headless smoke plot from the installed wheel.
- Verify GitHub Release assets and the published release documentation. Hosted Pages is
  verified here only if its follow-on deployment has already landed.

## 13. Risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Matplotlib collection internals vary by version | Broken or corrupt polygons | Isolate adapters, test minimum/latest versions, prefer public getters/setters |
| Original geometry is lost | `expand()` cannot recover the plot | Capture originals before mutation; never invert mutated data when originals exist |
| New observations stale existing mappings | Misaligned multi-artist figures | Registry revisions and explicit refresh/recompute behavior |
| Partial artist support appears successful | Scientifically misleading plot | Detect unsupported artists during preflight and abort before mutation by default |
| Ambiguous artists added while collapsed | Expanded originals are unrecoverable | Require helper creation or explicit coordinate-space registration; reject guessing |
| Adapter failure after partial mutation | Mixed coordinate spaces on one axes | Preflight every artist and use transactional prepare/commit with rollback |
| Integer artist IDs are reused | New artists receive stale state | Key state with `WeakKeyDictionary` artist objects |
| Synchronized registries diverge | Same date maps differently by panel | Give synchronized handles one owned revisioned registry with defined propagation |
| Pixel tests are platform-sensitive | Noisy CI and ignored failures | Pin rendering job, fonts, backend, DPI, and tolerance |
| Ribbon API implies statistical meaning | Mislabelled uncertainty | Require explicit bounds and labels; perform no inference |
| Feature breadth delays correctness | Fragile release | Land transform, scatter, and polygons before higher-level APIs |
| Facets amplify unresolved coordinate bugs | Hard-to-debug multi-panel failures | Defer facets until collection remapping and synchronization are stable |
| Full rescans and path copies are expensive | Interactive and large plots become unusable | Define complexity expectations and add representative performance checks |

## 14. Definition of done for `v0.2.0`

`v0.2.0` is ready when a user can create a line, scatter layer, and `fill_between` band on
irregular dates; switch repeatedly between expanded and collapsed modes; synchronize
multiple panels; and obtain geometrically correct, documented, visually tested output
without silent data transformation or unsupported-artist failure.

The release is not done merely because the new examples look correct. The underlying
geometry must be reversible, the failure modes must be explicit, the package must install
from its built wheel, and the public documentation must describe both capabilities and
limits accurately.

Specifically, collection-only plots establish a complete registry or fail clearly;
ambiguous additions in collapsed mode are rejected; supported state round-trips within
the documented equality rules; synchronization cannot silently diverge; unsupported or
failed adapters leave the axes unchanged; and all minimum, pinned-renderer, newest-stable,
package, documentation, geometry, and image-regression jobs pass.
