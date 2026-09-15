# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## Unreleased

- Replace line-specific coordinate mutation with an invertible registered matplotlib
  scale used uniformly by lines, `scatter`, `fill_between`, native x-data annotations,
  limits, autoscaling, and shared axes.
- Preserve artist calendar geometry across repeated collapse/expand transitions and fix
  single-observation forward/inverse extrapolation to use one calendar day per ordinal.
- Make `DateAxis.loc()` return the same native matplotlib date coordinate in both modes;
  ordinal display positions now belong exclusively to the axis transform.
- Correct collapsed-mode guidance: native `scatter` and `fill_between` collections are
  supported by the registered scale; lines and scatter offsets now contribute observation
  provenance, while polygon-only plots require explicit `data=` until PR6.
- Add a public transactional `refresh()` lifecycle backed by an owned revisioned registry,
  and make `sync_dates()` share that registry across weakly held live handles.
- Add idempotent `dispose()`, filterable `DateDiscoveryError` diagnostics, and rollback for
  failed shared refresh application.
- Fix invalid-timezone configuration poisoning, `fmt(minor=False)`, and replacement of
  externally removed captions. Add annotation artist enumeration and safe bulk removal.
  All former v0.2 safety-gap expected failures now pass.

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
