# Contributing

Bug reports and focused pull requests are welcome. For behavior changes, open an issue
first so the public API and date-axis semantics can be agreed before implementation.

## Development

Use Python 3.10 or newer:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev,docs]"
.venv/bin/python -m pytest -q --cov=ggstyle --cov-report=term-missing
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python tools/benchmark_registry.py
.venv/bin/python tools/benchmark_semantic.py
.venv/bin/python tools/semantic_mapping_spike.py --probe native
.venv/bin/python tools/validate_docstrings.py
.venv/bin/python tools/validate_gallery.py
.venv/bin/python -m sphinx -W --keep-going -b html docs/source docs/build/html
.venv/bin/python -m sphinx -W -b doctest docs/source docs/build/doctest
.venv/bin/python -m sphinx -W -b linkcheck docs/source docs/build/linkcheck
```

Public functions, classes, methods, and attributes use the NumPy docstring standard, as
in statsmodels. New functionality also belongs in the appropriate page under
`docs/source` and in the changelog. Documentation must build without warnings.

New behavior needs tests. Changes to collapsed coordinates should test both collapsed and
expanded modes, including switching between them. Do not commit generated distributions,
virtual environments, caches, or platform metadata.

Collapsed-coordinate changes must follow
[ADR 0001](docs/architecture/0001-collapsed-date-scale.md), which records the observation,
refresh, synchronization, diagnostic, and transaction contracts for the v0.3 redesign.
Rendering changes must also follow the
[visual regression workflow](docs/visual-regression.md); baseline replacements require
an explanation and review of the generated image diff.

Publication-finishing APIs must follow
[ADR 0002](docs/architecture/0002-finishing-api.md). Changes to the accepted vocabulary
must update its canonical fixtures and keep `python tools/finishing_usability.py` above
the documented code-reduction gate. The fixtures measure API ceremony; they do not
replace geometry, image, typing, accessibility, or external pilot-user tests.

Semantic-mapping work must follow
[ADR 0003](docs/architecture/0003-semantic-mapping.md). Keep mapped aesthetics separate
from fixed artist style, train shared scales before drawing, return ordinary Matplotlib
artists, and preserve the existing-axes and date-correctness hard gates. The executable
spike is decision evidence, not a production helper implementation. Scale and registry
internals remain private; the public scale policies and result protocols are the stable
inspection boundary. Renderer transactions must supply artist rollback alongside
registry rollback.

Before release-sensitive changes, run both scripts under `tools/benchmark_*.py` and
build the wheel. CI installs that wheel into an isolated environment and renders a
collapsed plot with publication finishing and semantic layers through
`tools/smoke_wheel.py`. Minimum and newest
direct-dependency pins are documented in [REPRODUCIBILITY.md](REPRODUCIBILITY.md);
scheduled prerelease failures are informational, while failures on stable supported
versions block release.

By contributing, you agree that your contributions are licensed under the MIT License.

## Releasing

Releases use PyPI trusted publishing; maintainers must not store a long-lived PyPI token
in GitHub. The trusted publisher for project `ggstyle`
on PyPI uses these values:

- Owner: `joshuamyers22`
- Repository: `ggstyle`
- Workflow: `publish.yml`
- Environment: `pypi`

After the release commit passes CI, create and push a tag matching the package version,
for example `v0.5.0`. The publish workflow independently repeats the test, type,
documentation, and package checks; publishes the distributions to PyPI; and creates the
GitHub release only after publication succeeds.
