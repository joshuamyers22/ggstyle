.PHONY: sync lint type test benchmark usability gallery visual visual-update docs build check

sync:
	uv sync --frozen --all-extras

lint:
	uv run ruff check .

type:
	uv run mypy

test:
	uv run python -m pytest -q --cov=ggstyle --cov-report=term-missing

benchmark:
	uv run python tools/benchmark_registry.py

usability:
	uv run python tools/finishing_usability.py

gallery:
	MPLBACKEND=Agg uv run python tools/validate_gallery.py

visual:
	LANG=C LC_ALL=C TZ=UTC MPLBACKEND=Agg GGSTYLE_RUN_VISUAL=1 uv run --frozen --group visual python -m pytest -q tests/test_visual_regressions.py

visual-update:
	LANG=C LC_ALL=C TZ=UTC MPLBACKEND=Agg uv run --frozen --group visual python tools/update_visual_baselines.py --accept

docs:
	uv run python tools/validate_docstrings.py
	MPLBACKEND=Agg uv run python tools/validate_gallery.py
	LANG=C LC_ALL=C uv run sphinx-build -W --keep-going -b html docs/source docs/build/html
	LANG=C LC_ALL=C MPLBACKEND=Agg uv run sphinx-build -W -b doctest docs/source docs/build/doctest
	LANG=C LC_ALL=C uv run sphinx-build -W -b linkcheck docs/source docs/build/linkcheck

build:
	uv build
	uv run twine check dist/*

check: lint type test benchmark usability docs build
