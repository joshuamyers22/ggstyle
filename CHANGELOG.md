# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## Unreleased

- Select narrow native line, point, and ribbon helpers for the v0.5 semantic-mapping
  direction through a reproducible three-route scorecard and executable Matplotlib,
  seaborn objects, and plotnine prototypes. Record axes adoption and date correctness as
  hard gates; keep third-party compilers out of ggstyle's dependency graph.
- Add the private v0.5 semantic foundation: immutable discrete color/linestyle and
  continuous color-scale policies, explicit category/missing/infinite/out-of-bounds
  behavior, complete multi-layer training, and one weakly axes-owned transactional
  registry with stale-plan, cross-axes, rollback, and strict-JSON inspection contracts.
- Add a narrow public `line()` helper for named tidy-data columns with explicit
  mapped-versus-fixed style, stable grouping and sorting policy, shared discrete and
  continuous mappings across calls, ordinary `Line2D` results, collapsed-date refresh,
  transactional rollback of artists, axis state, property cycles, and semantic state,
  plus immutable public `DiscreteScale` and `ContinuousScale` configuration.

## 0.4.0 - 2026-09-15

- Select a function-first, transactional architecture for the v0.4 publication-finishing
  API and add ten machine-checked usability fixtures spanning five target-user
  perspectives. The fixture gate preserves native Matplotlib access and requires at least
  a 35% reduction in non-data formatting statements.
- Add immutable, locale-independent percent, currency, grouped-number, and SI-prefix
  labellers with explicit scaling, precision, negative, NaN, and infinity policies, plus
  a typed adapter to Matplotlib's native `FuncFormatter`.
- Add immutable qualitative, sequential, and diverging palettes with strict qualitative
  cardinality, CIELAB interpolation, explicit missing/out-of-bounds policies, theme-cycle
  integration, and colour-vision regression gates.
- Add transactional `finish()` and immutable `axis()` specifications for coherent plot,
  subtitle, caption, and axis labels. Managed outer text participates in figure layout,
  supports safe replacement/removal, and retains native Matplotlib axes and artists.
- Add immutable, validated theme recipes with proportional base sizing, font-family and
  rcParam overrides, a pure resolved-parameter mapping, and transactional safe theming of
  existing axes through `finish()` without restyling data or mutating global `rcParams`.
- Add publication-safe `save()` with required physical dimensions, unit and format
  validation, deterministic SVG/PDF metadata, explicit bounding and transparency, atomic
  overwrite protection, and restoration of figure state after success or failure.
- Add transactional line endpoint labels with display-space collision avoidance,
  line-colour matching, constrained-layout right margins, managed annotation reuse, and
  an explicit whole-plot legend-or-raise fallback for unsupported artists or geometry.
- Add strict-JSON inspection for dry-run finishing plans and date-axis summaries, an
  executable publication gallery, task-oriented migration and tool-selection guidance,
  link-checked documentation, and GitHub Pages deployment.

## 0.3.0 - 2026-09-15

- Replace line-specific coordinate mutation with an invertible registered matplotlib
  scale used uniformly by lines, `scatter`, `fill_between`, native x-data annotations,
  limits, autoscaling, and shared axes.
- Preserve artist calendar geometry across repeated collapse/expand transitions and fix
  single-observation forward/inverse extrapolation to use one calendar day per ordinal.
- Make `DateAxis.loc()` return the same native matplotlib date coordinate in both modes;
  ordinal display positions now belong exclusively to the axis transform.
- Correct collapsed-mode guidance: native `scatter` and `fill_between` collections are
  supported by the registered scale; lines, scatter offsets, and native fill-between paths
  now contribute observation provenance.
- Discover multi-path `fill_between` observations across masks, NaNs, `where` regions,
  and interpolated crossings without mutating vertices or path codes. Require explicit
  source dates for unrecoverable midpoint steps, and reject `fill_betweenx`, custom
  polygon transforms, and unrecognized polygon collections.
- Add a public transactional `refresh()` lifecycle backed by an owned revisioned registry,
  and make `sync_dates()` share that registry across weakly held live handles.
- Add idempotent `dispose()`, filterable `DateDiscoveryError` diagnostics, and rollback for
  failed shared refresh application.
- Fix invalid-timezone configuration poisoning, `fmt(minor=False)`, and replacement of
  externally removed captions. Add annotation artist enumeration and safe bulk removal.
  All former v0.2 safety-gap expected failures now pass.
- Preserve concrete `DateAxis` return types across fluent calls and verify them from a
  downstream typed module.
- Add blocking minimum/newest dependency profiles, representative macOS and Windows jobs,
  a bounded registry benchmark, and a clean-wheel headless rendering smoke test. Scheduled
  dependency-prerelease results are informational.
- Support legacy and modern pandas offset aliases across the declared pandas 2.x and 3.x
  range.

## 0.2.0 - 2026-09-13

- Add `bw`, `linedraw`, `light`, `dark`, `classic`, `void`, and `test` themes alongside
  the existing `minimal` and `grey` themes.
- Accept the corresponding ggplot2 `theme_*` names as aliases and document matplotlib's
  facet-strip and void-theme layout limitations.

## 0.1.1 - 2026-09-09

- Refactor date-axis behavior into focused policy modules for coordinate handling,
  tick planning and rendering, annotations, captions, grids, synchronization, and
  timezone display while preserving the public API.
- Add architectural and policy-level tests for the extracted components.
- Add reproducible development and package-build tooling and strengthen CI and
  publishing checks.

## 0.1.0 - 2026-08-19

Initial public release.

- Add a date-axis handle that adopts existing matplotlib axes.
- Add independent tick cadence, label formatting, range, and grid controls.
- Add observation-based gap collapsing and date-space annotations.
- Add pandas, polars, pyarrow, NumPy, and plain-sequence date extraction.
- Add opt-in minimal and grey themes without import-time global state changes.
- Add NumPy-style API documentation and a warning-free Sphinx user guide modeled on the
  documentation structure used by statsmodels.
- Replace loosely typed annotation dictionaries with explicit internal state objects and
  broaden automated clean-code checks.
- Add structured ``AxisSummary`` metadata and captions generated from the same source.
- Add explicit ``missing="raise"`` and ``missing="drop"`` date policies.
- Add ``sync_dates`` for comparable date coordinates and limits across multiple panels.
