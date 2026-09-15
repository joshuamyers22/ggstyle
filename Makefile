.PHONY: sync lint type test visual visual-update docs build check

sync:
	uv sync --frozen --all-extras

lint:
	uv run ruff check .

type:
	uv run mypy src

test:
	uv run pytest -q --cov=ggstyle --cov-report=term-missing

visual:
	LANG=C LC_ALL=C TZ=UTC MPLBACKEND=Agg GGSTYLE_RUN_VISUAL=1 uv run --frozen --group visual pytest -q tests/test_visual_regressions.py

visual-update:
	LANG=C LC_ALL=C TZ=UTC MPLBACKEND=Agg uv run --frozen --group visual python tools/update_visual_baselines.py --accept

docs:
	uv run python tools/validate_docstrings.py
	LANG=C LC_ALL=C uv run sphinx-build -W --keep-going -b html docs/source docs/build/html

build:
	uv build
	uv run twine check dist/*

check: lint type test docs build
