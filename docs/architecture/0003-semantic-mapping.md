# ADR 0003: Build narrow native semantic-mapping helpers

- Status: accepted
- Date: 2026-09-15
- Applies to: the v0.5 semantic-mapping workstream

## Context

The v0.4 release finishes plots that already contain native Matplotlib artists. The next
workstream may add tidy-data mappings for lines, points, and the already-supported ribbon
geometry. It must not weaken collapsed-date correctness, obscure the distinction between
mapped and fixed values, replace caller-owned axes, or grow into an incomplete grammar.

The product plan requires a scored spike across three routes:

1. narrow native helpers implemented by ggstyle;
2. an optional adapter over `seaborn.objects`; and
3. documentation-only interoperability with plotnine.

The spike evaluates the public APIs available in Matplotlib 3.11.2, seaborn 0.13.2, and
plotnine 0.15.8. `tools/semantic_mapping_spike.py` contains the score evidence and three
executable prototypes. Third-party candidates remain isolated spike dependencies; they
are not ggstyle runtime or development dependencies.

## Method

Each route receives an equally weighted score from 1 (poor) to 5 (strong) for every
criterion named in the roadmap. Date correctness and existing-axes support are hard
gates with a minimum score of 4 because those capabilities define ggstyle's product
boundary. Scores describe suitability as ggstyle's v0.5 foundation, not the general
quality of another library.

The executable comparison uses the same tidy dataset with irregular dates and two line
groups. It checks input immutability, mapped grouping, ordinary Matplotlib artist access,
target ownership, and the available date integration boundary. The native prototype also
rejects a color supplied as both a mapping and fixed style before drawing anything.

Run the dependency-free score validation and native prototype with:

```bash
python tools/semantic_mapping_spike.py
MPLBACKEND=Agg python tools/semantic_mapping_spike.py --probe native
```

The exact isolated third-party reproduction command is recorded in
`REPRODUCIBILITY.md`.

## Evidence

| Criterion | Native helpers | seaborn objects | plotnine docs |
| --- | ---: | ---: | ---: |
| Date correctness | 5 | 4 | 3 |
| Existing-axes support | 5 | 4 | 1 |
| Faceting access | 4 | 5 | 5 |
| Public API stability | 4 | 2 | 4 |
| Dependency weight | 5 | 3 | 2 |
| Error quality | 4 | 3 | 3 |
| Typing | 5 | 2 | 4 |
| Artist access | 5 | 3 | 2 |
| Maintenance cost | 3 | 4 | 5 |
| **Total** | **40/45** | **30/45** | **29/45** |

### Narrow native helpers

The prototype groups tidy data, trains one deterministic qualitative color mapping,
draws ordinary `Line2D` instances on the supplied axes, and then adopts those artists
through the production collapsed-date scale. It retains the original axes and data and
returns direct artist access. Matplotlib's public axes methods already provide the
required line, scatter, and fill-between primitives:

- [Axes.plot](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.plot.html)
- [Axes.scatter](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.scatter.html)
- [Axes.fill_between](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.fill_between.html)

This route costs more ggstyle implementation work because scale training, registries,
and guide construction cannot be delegated. That cost buys one validation vocabulary,
one date registry, full typing ownership, and no new plotting dependency.

### Optional seaborn objects adapter

The prototype verifies that `Plot.on(ax).plot()` draws two native lines on an existing
axes and that ggstyle can subsequently install its collapsed-date scale when complete
date observations are supplied. `Plot.facet` offers a strong existing facet system.

It is not selected as the foundation because the official objects-interface guide still
calls the interface experimental, its compilation result is a `Plotter` rather than a
ggstyle result exposing trained policy, and the tested distribution does not publish a
`py.typed` marker. An adapter would also make ggstyle's error and compatibility contract
depend on a second compiler. These conclusions use only public seaborn documentation:

- [objects interface](https://seaborn.pydata.org/tutorial/objects_interface.html)
- [Plot](https://seaborn.pydata.org/generated/seaborn.objects.Plot.html)
- [Plot.on](https://seaborn.pydata.org/generated/seaborn.objects.Plot.on.html)
- [Plot.facet](https://seaborn.pydata.org/generated/seaborn.objects.Plot.facet.html)

Seaborn objects remains a supported coexistence story: users may compile onto a native
axes and apply ggstyle finishing or a date policy afterward. ggstyle will not subclass
or inspect private seaborn compiler objects.

### Documentation-only plotnine interoperability

The prototype verifies that plotnine maps the two groups to ordinary lines and returns a
Matplotlib `Figure`. Its public `draw` signature does not accept an existing axes, so it
fails the axes-adoption hard gate. Its grammar, datetime scales, facets, themes, and
guides also form a separate policy system rather than an extension point for ggstyle's
date registry.

Plotnine is the recommended alternative when a user wants a broad grammar rather than
incremental helpers on an existing axes. ggstyle will document that choice but will not
wrap plotnine objects or depend on their internals. Public evidence:

- [ggplot](https://plotnine.org/reference/ggplot.html)
- [facet_wrap](https://plotnine.org/reference/facet_wrap.html)
- [geometric objects](https://plotnine.org/guide/geometric-objects.html)

## Decision

Build **narrow native helpers**. The v0.5 public scope is limited to:

- tidy `x`, `y`, `color`, `group`, and optional `linestyle` mappings;
- a separate fixed-style argument that cannot duplicate a mapped aesthetic;
- immutable discrete and continuous scale policy trained through one axes-owned semantic
  registry;
- deterministic line, point, and ribbon drawing with ordinary Matplotlib artists;
- automatic legends or colorbars only when trained mappings are compatible; and
- a typed `RenderedResult` exposing the original axes, artists, scales, and diagnostics.

PR17 implements immutable aesthetic-scale and semantic-registry foundations. PR18 adds
the public line renderer described below; PR19 adds points and ribbons; PR20 adds guides;
PR21 completes results, frame parity, benchmarks, gallery, and release hardening.

### Foundation contract (PR17)

The private `ggstyle._semantic_scales` module keeps training independent of Matplotlib.
It defines immutable discrete color/linestyle and continuous color policies and their
trained counterparts:

- ordinary discrete input uses stable first-seen order across layer registration order;
- pandas categorical input preserves its declared categories, with an explicit choice to
  retain or drop unobserved levels;
- explicit discrete order rejects observations outside that order rather than silently
  assigning a fallback;
- palette cardinality is a preflight error, including the eight-color accessibility cap;
- missing values have `map`, `drop`, or `raise` policy;
- infinity has independent `clip`, `color`, `drop`, or `raise` policy on continuous
  scales;
- explicit continuous limits delegate out-of-bounds behavior to the immutable palette;
  automatic limits use the finite union across every participating layer; and
- a constant continuous domain maps to the palette midpoint.

The private `ggstyle._semantic_registry` module associates one registry with a live axes
through a weak-key map. A mapping request defensively captures its values, source column,
aesthetic, scale policy, and stable layer ID. `prepare()` combines every committed and
candidate contribution, validates compatible scale policy, trains shared scales, and
maps all layer outputs without drawing. `commit()` accepts only a current plan created by
that registry; stale or cross-axes plans fail without changing state.

Rendering PRs must use `transact()` with an artist rollback callback. If drawing fails,
the callback removes or restores partial artist changes and the registry restores its
prior immutable snapshot. Re-entrant transactions fail. Inspection reports scale policy,
layer/output counts, dropped observations, changes, diagnostics, and revisions as strict
JSON without serializing full per-row mapped output.

These modules remain private until drawing use establishes the smallest stable public
configuration vocabulary. The PR17 tests exercise policy, ordering, multi-layer
retraining, axes/date-registry independence, weak lifetime, stale/cross-registry plans,
and successful and failed transactions. They intentionally create no data artists.

The prototype function in `tools/semantic_mapping_spike.py` is evidence, not a public or
private production API. Production work must not copy its deliberately minimal grouping
logic without the scale and registry contracts from PR17.

### Line renderer contract (PR18)

The public `line()` helper accepts named `x`, `y`, `color`, `group`, and `linestyle`
columns plus a separate fixed `style` mapping. Mapped color/linestyle cannot also be
fixed, including through Matplotlib aliases. Column strings are names only and are never
evaluated as expressions.

Discrete color and linestyle participate in grouping; explicit `group` partitions rows
without creating an aesthetic scale. Numeric color is continuous and must be constant
within each resolved `Line2D`. Input order is the default, while `sort="x"` is stable and
does not aggregate duplicate x values. Missing explicit groups have an explicit
drop/keep/raise policy.

Every call trains the complete axes registry before drawing. Later discrete levels keep
prior assignments. If a later layer expands an automatic continuous domain, earlier
managed lines are recolored from the newly trained assignments. A transaction failure
restores new artists, previous line properties, limits, units, locators, formatters,
property-cycle position, renderer ownership, and semantic registry state. An existing
date handle refreshes after artist creation and participates in the same failure path.

`LineResult` exposes the exact axes, ordinary `Line2D` artists, read-only trained scales,
diagnostics, and a layer identifier. Guide construction and final cross-geom result
inspection remain PR20 and PR21 responsibilities respectively.

PR18 also promotes the smallest reusable configuration boundary proven by the renderer:
public immutable `DiscreteScale` and `ContinuousScale` policies. The public policies do
not carry an aesthetic name; `color_scale=` or `linestyle_scale=` supplies that context.
This keeps one vocabulary reusable by later point/ribbon renderers while preserving
context-specific validation for hexadecimal colors and supported line styles.

## Explicit exclusions

Version 0.5 will not add bars, histograms, boxplots, density estimates, smoothing,
arbitrary statistics, position adjustments, a general layer compiler, expression
evaluation, or a theme/coordinate grammar. A full grammar requires a new project charter,
staffing estimate, and competitive justification.

## Consequences

ggstyle keeps its existing-axes identity and can reuse the date registry, palettes,
formatters, themes, and finishing transactions already under test. Users receive a small
typed mapping vocabulary while retaining every native artist and axes method.

The project accepts responsibility for scale training, aesthetic consistency across
layers, guide merging, and high-quality preflight errors. This is intentionally more
maintenance than documentation-only interoperability. The later PR sequence isolates
that risk by building the immutable registry before any drawing helper becomes public.

The decision may be revisited only if the native foundation cannot satisfy the date and
existing-axes hard gates, or if a stable third-party public protocol exposes equivalent
trained scales, artists, and diagnostics without private integration.
