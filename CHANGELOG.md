# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## 0.1a0 - 2026-08-19

Initial public alpha.

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

The alpha designation is intentional: collapsed mode currently remaps line artists only,
and the API may change based on early usage.
