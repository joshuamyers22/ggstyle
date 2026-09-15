# ADR 0002: Coordinate finishing through one function-first API

- Status: accepted
- Date: 2026-09-15
- Applies to: the v0.4 publication-finishing workstream

## Context

The coordinate-safety release established that ggstyle can safely adopt an existing
Matplotlib `Axes`. The next workstream covers labels, numeric labellers, palettes, theme
overrides, deterministic saving, endpoint labels, and inspection. These operations touch
different Matplotlib subsystems and must not become either a general plot grammar or a
collection of ordering-sensitive mutation helpers.

The API-shape decision considered three approaches:

1. one `finish()` function coordinating a complete request;
2. separate mutating helpers for titles, axes, themes, legends, and layout; and
3. a public reusable recipe object that users construct and apply.

The evaluation uses ten checked-in tasks viewed through five target-user perspectives:

- an analyst finishing notebook and report figures;
- a researcher who needs explicit statistical and export semantics;
- a reporting engineer who needs reproducible output;
- a ggplot2 user who expects scales and non-data themes to remain distinct; and
- a library author who must retain native axes and artists.

These perspectives are design lenses, not a claim that five external usability sessions
have occurred. Pilot sessions remain a v0.4 release activity once working APIs exist.

## Decision

Use a **function-first hybrid**. `finish()` is the only coordinator that mutates an axes
for a complete finishing request. Small factories create immutable values consumed by
that coordinator, but they do not mutate axes themselves. File output remains a separate
`save()` operation because filesystem effects cannot participate in an axes transaction.
Palette lookup also remains a pure operation because silently recolouring existing data
artists would violate axes adoption and mapped-versus-fixed semantics.

The review used a five-point score where higher is better. The function-first result
includes pure value factories, not separate mutating helpers.

| Criterion | Function-first | Mutating helpers | Recipe-first |
| --- | ---: | ---: | ---: |
| One-off recall | 5 | 3 | 2 |
| Atomic validation and rollback | 5 | 1 | 5 |
| Dry-run inspection | 5 | 2 | 5 |
| Reuse before API maturity | 3 | 2 | 5 |
| Small public vocabulary | 5 | 2 | 2 |
| Native Matplotlib access | 5 | 5 | 5 |
| **Total** | **28** | **15** | **24** |

The intended shape is:

```python
result = gs.finish(
    ax,
    title="Revenue",
    subtitle="Trailing twelve months",
    caption="Source: annual report",
    x=gs.axis(title="Date"),
    y=gs.axis(
        title="Revenue",
        labels=gs.label_currency("$", scale=1_000_000, suffix="M"),
    ),
    theme="minimal",
    legend="top",
)
```

The spelling in the usability fixtures is the accepted design target. Individual
argument details may be refined in their focused implementation PR only when the ten
fixtures, typing contract, and reduction gate remain satisfied.

### Public model and return contracts

The implementation PRs will introduce models only when they have behavior:

- `AxisSpec` is an immutable description of title, breaks, labels, limits, and transform.
  Limits and coordinate zoom are distinct; v0.4 initially implements only the fields its
  formatter work needs.
- `ThemeSpec` is an immutable theme name, base typography, and validated override map.
  It distinguishes creation-time rcParams from best-effort existing-axes application.
- `EndLabelSpec` records collision and fallback policy without reading artist geometry.
- `FinishPlan` is an immutable, serializable description of resolved operations,
  diagnostics, limitations, and managed-artist changes. It contains no live artists.
- `FinishResult` exposes the original `Axes`, managed artists, diagnostics, and the plan.
  It does not proxy, wrap, or replace Matplotlib artists.

`finish(..., dry_run=True)` returns `FinishPlan` without changing Matplotlib state;
`finish(...)` returns `FinishResult`. Literal overloads must preserve those concrete
return types for downstream type checkers. An arbitrary boolean should not erase the
return type to `Any`.

Mutable inputs such as override mappings and metadata are defensively copied into
immutable representations. Reusing a spec across figures cannot leak state.

### Mutation transaction

Every request follows `resolve -> validate -> plan -> commit`:

1. Resolve theme names, label factories, legend placement, existing managed artists, and
   date-axis state.
2. Validate the complete request, including incompatible limits/transforms, invalid
   rcParams, layout capacity, and externally removed artists.
3. Build the same `FinishPlan` returned by dry-run mode.
4. Commit in a documented order and roll back axes, figure, layout, and managed-artist
   state if an adapter fails.

Validation and planning must not draw the canvas or change global rcParams. Repeated
application is idempotent. Existing data artist geometry, transforms, labels, colours,
and semantic registrations remain unchanged unless a future API explicitly names that
operation. Callback re-entry uses the same guard as date-axis refresh.

### Boundaries

- `finish()` adopts an existing axes and never creates data artists.
- `finish()` may create only managed non-data artists such as subtitle and caption text.
- `theme="minimal"` applies documented properties that can be changed safely on an
  existing axes and reports creation-only properties it cannot reproduce. It never
  claims that an rcParams context retroactively restyles every artist.
- `palette()` returns immutable or defensive colour values for subsequent artists. A
  semantic colour mapping belongs to v0.5.
- `save()` accepts an explicit figure and owns size, units, DPI, format, transparency,
  bounding, metadata, and overwrite validation. It never guesses a current figure.
- Endpoint labels may inspect supported lines, but collision preparation completes before
  any label is drawn. Unsupported artists use an explicit legend fallback or fail.
- Date-axis state is consumed through public `DateAxis` contracts; finishing code does
  not duplicate coordinate conversion or observation registries.

### Error and reset vocabulary

- Omitted values leave existing state unchanged.
- `None` means automatic only where that meaning is explicitly documented.
- `False` disables only options whose type explicitly admits it.
- Invalid values name the field, received value, allowed forms, and recovery action.
- Dry-run and commit produce the same diagnostics for the same starting state.
- No `**kwargs` tunnel forwards unvalidated values to Matplotlib.

## Alternatives considered

### Separate mutating helpers

Focused mutators are easy to implement but make ordering, rollback, layout ownership,
and managed-artist replacement the caller's problem. They also make it difficult to
inspect one complete request. Pure formatter and palette factories are retained; the
mutating-helper architecture is rejected.

### Public recipe object first

A recipe naturally supports reuse and inspection, but asks one-off users to learn object
construction, application, and result vocabulary before the behavior has stabilized.
Reusable and serializable recipes remain scheduled for v0.7, after real finishing and
composition use cases can determine their fields. A private immutable plan is not a
promise of a public recipe hierarchy.

### `finish()` with unrestricted keyword forwarding

Forwarding Matplotlib keywords would keep calls short at the cost of stable typing,
validation, diagnostics, and compatibility. It is rejected. Focused specs expose a
deliberately small vocabulary and Matplotlib remains the escape hatch.

## Usability fixtures and gate

`tools/finishing_usability.py` stores only non-data finishing operations. It parses both
snippets and counts AST statements, making the comparison insensitive to line wrapping,
comments, or formatting. Every candidate must be shorter than its idiomatic Matplotlib
baseline, preserve the native axes, avoid data mutation, and use no drawing primitive.
The aggregate candidate must reduce logical statements by at least 35%.

| ID | Canonical task | Primary capability |
| --- | --- | --- |
| F01 | Title, subtitle, caption, and axis titles | Labels and layout |
| F02 | Percent axis with explicit scale and precision | Numeric labels |
| F03 | Currency axis scaled to millions | Numeric labels |
| F04 | Grouped numbers and SI notation on two axes | Numeric labels |
| F05 | Accessible qualitative palette for subsequent artists | Palettes |
| F06 | Scoped theme with typography and validated overrides | Themes |
| F07 | Top legend with an explicit title | Legend layout |
| F08 | Reproducible raster and vector export | Save |
| F09 | Collision-aware endpoint labels with legend fallback | Direct labels |
| F10 | Inspect a request without mutation | Inspection |

Run the gate with:

```bash
python tools/finishing_usability.py
python tools/finishing_usability.py --json
```

The gate measures API ceremony, not task completion, discoverability, layout quality, or
accessibility. Focused implementation PRs must add geometry, image, lifecycle, typing,
and clean-wheel tests. Before v0.4 freezes the API, at least five external pilot users
must attempt representative fixtures without coaching; results and resulting changes
will be recorded in a follow-up usability report.

## Consequences

The selected design gives common one-off work one discoverable entry point while keeping
formatters, palettes, and saving independently useful. A complete request can be checked
and committed atomically, and callers always recover the original axes and real artists.

The tradeoff is that `finish()` has an explicit keyword budget and requires careful
signature review as features land. New keywords need a recurring fixture or user task.
Anything that draws or transforms data remains outside this API.
