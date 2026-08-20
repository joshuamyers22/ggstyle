# Contributing

Bug reports and focused pull requests are welcome. For behavior changes, open an issue
first so the public API and date-axis semantics can be agreed before implementation.

## Development

Use Python 3.10 or newer:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest -q --cov=ggstyle --cov-report=term-missing
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/python tools/validate_docstrings.py
.venv/bin/python -m sphinx -W --keep-going -b html docs/source docs/build/html
```

Public functions, classes, methods, and attributes use the NumPy docstring standard, as
in statsmodels. New functionality also belongs in the appropriate page under
`docs/source` and in the changelog. Documentation must build without warnings.

New behavior needs tests. Changes to collapsed coordinates should test both collapsed and
expanded modes, including switching between them. Do not commit generated distributions,
virtual environments, caches, or platform metadata.

By contributing, you agree that your contributions are licensed under the MIT License.

## Releasing

Releases use PyPI trusted publishing; maintainers must not store a long-lived PyPI token
in GitHub. Before the first release, register a pending publisher for project ``ggstyle``
on PyPI with these values:

- Owner: ``joshuamyers22``
- Repository: ``ggstyle``
- Workflow: ``publish.yml``
- Environment: ``pypi``

After the release commit passes CI, create and push a tag matching the package version,
for example ``v0.1.0``. The publish workflow independently repeats the test, type,
documentation, and package checks; publishes the distributions to PyPI; and creates the
GitHub release only after publication succeeds.
