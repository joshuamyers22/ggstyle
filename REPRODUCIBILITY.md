# Reproducibility

Python 3.12 is the default local runtime; CI tests the full supported matrix.
Run `uv sync --frozen --all-extras` followed by `make check`. Dependency updates
must be made through `uv lock --upgrade` and committed with `uv.lock`.
