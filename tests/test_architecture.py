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


def test_mode_line_adapter_does_not_depend_on_date_axis() -> None:
    source = Path("src/ggstyle/_mode_lines.py").read_text()
    assert "from .dates" not in source
    assert "import ggstyle.dates" not in source


def test_tick_rendering_adapter_does_not_depend_on_date_axis_policy() -> None:
    source = Path("src/ggstyle/_tick_rendering.py").read_text()
    assert "from .dates" not in source
    assert "_cadence" not in source
    assert "pandas" not in source


def test_tick_configuration_policy_does_not_depend_on_matplotlib_or_date_axis() -> None:
    source = Path("src/ggstyle/_tick_config.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source
    assert "from .dates" not in source


def test_tick_plan_does_not_depend_on_axis_or_rendering_adapters() -> None:
    source = Path("src/ggstyle/_tick_plan.py").read_text()
    assert "from .dates" not in source
    assert "_tick_rendering" not in source
    assert "matplotlib.axes" not in source


def test_axis_sync_policy_does_not_depend_on_matplotlib_or_date_axis() -> None:
    source = Path("src/ggstyle/_axis_sync.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source
    assert "from .dates" not in source


def test_date_range_policy_does_not_depend_on_matplotlib_or_date_axis() -> None:
    source = Path("src/ggstyle/_date_ranges.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source
    assert "from .dates" not in source
