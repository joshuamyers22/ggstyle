"""Dependency rules for pure date policy."""

from pathlib import Path


def test_date_summary_does_not_import_matplotlib() -> None:
    source = Path("src/ggstyle/_date_summary.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source


def test_axis_summary_model_does_not_import_matplotlib() -> None:
    source = Path("src/ggstyle/_axis_summary.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source


def test_axis_summary_policy_does_not_depend_on_axis_or_rendering_adapters() -> None:
    source = Path("src/ggstyle/_axis_summary.py").read_text()
    assert "_axis_data" not in source
    assert "_grid" not in source
    assert "_tick_positions" not in source


def test_caption_policy_does_not_import_matplotlib() -> None:
    source = Path("src/ggstyle/_captions.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source


def test_timezone_policy_does_not_import_matplotlib() -> None:
    source = Path("src/ggstyle/_timezones.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source
