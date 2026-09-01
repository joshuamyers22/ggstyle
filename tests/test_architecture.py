"""Dependency rules for pure date policy."""

from pathlib import Path


def test_date_summary_does_not_import_matplotlib() -> None:
    source = Path("src/ggstyle/_date_summary.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source
