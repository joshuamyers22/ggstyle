.PHONY: sync lint type test docs build check

sync:
	uv sync --frozen --all-extras

lint:
	uv run ruff check .

type:
	uv run mypy src

test:
	uv run pytest -q --cov=ggstyle --cov-report=term-missing

docs:
	uv run python tools/validate_docstrings.py
	LANG=C LC_ALL=C uv run sphinx-build -W --keep-going -b html docs/source docs/build/html

build:
	uv build
	uv run twine check dist/*

check: lint type test docs build
