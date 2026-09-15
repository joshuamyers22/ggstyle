# Reproducibility

Python 3.12 is the default local runtime; CI tests Python 3.10 through 3.13. Run
`uv sync --frozen --all-extras` followed by `make check`. Dependency updates must be
made through `uv lock --upgrade` and committed with `uv.lock`.

Two blocking compatibility profiles live under `.github/constraints`:

- `minimum.txt`: Matplotlib 3.7.5, NumPy 1.24.4, and pandas 2.0.3 on Python 3.10.
- `newest.txt`: Matplotlib 3.11.2, NumPy 2.5.3, and pandas 3.0.5 on Python 3.13.

The newest pins were reviewed against stable PyPI releases on 2026-09-15. Update that
file deliberately as releases arrive; do not make a job called "newest" silently reuse an
old lock. Scheduled prerelease testing uses the newest available prereleases and is
informational rather than release-blocking.

The pinned visual profile is separate because renderer updates require explicit image
review. `make visual` verifies it. `python tools/benchmark_registry.py` guards against
gross registry-complexity regressions, while the package CI job builds a wheel and runs
`tools/smoke_wheel.py` from an isolated environment.

The publication gallery is executable policy documentation rather than a pixel baseline.
`python tools/validate_gallery.py` renders every published gallery builder into a
temporary directory and validates its artifacts; `--write` is the explicit reviewed
asset-update operation. Pixel-sensitive contracts remain in the separately pinned visual
suite.
