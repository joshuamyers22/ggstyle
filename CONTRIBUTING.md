# Contributing

Bug reports and focused pull requests are welcome. For behavior changes, open an issue
first so the public API and date-axis semantics can be agreed before implementation.

## Development

Use Python 3.10 or newer:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/mypy src
```

New behavior needs tests. Changes to collapsed coordinates should test both collapsed and
expanded modes, including switching between them. Do not commit generated distributions,
virtual environments, caches, or platform metadata.

By contributing, you agree that your contributions are licensed under the MIT License.
