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

## Semantic-mapping decision spike

ADR 0003 is backed by a dependency-free scorecard and native prototype. The ordinary
development gate runs:

```bash
MPLBACKEND=Agg uv run python tools/semantic_mapping_spike.py --probe native
```

The two rejected integration routes are deliberately not project dependencies. Reproduce
all three probes in one isolated environment with the versions reviewed by the ADR:

```bash
MPLBACKEND=Agg uv run --isolated --no-project \
  --with . --with seaborn==0.13.2 --with plotnine==0.15.8 \
  python tools/semantic_mapping_spike.py --json --probe all
```

The command must report verified probes for native Matplotlib, seaborn objects, and
plotnine without modifying `uv.lock`. Update the ADR, the checked-in version labels, and
the evidence together if a later decision deliberately re-runs the third-party review.
