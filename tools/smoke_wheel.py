"""Exercise the installed wheel without importing the repository source tree."""

from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import ggstyle as gs


def main() -> None:
    """Render a collapsed polygon-only plot and validate packaged resources."""
    repository = Path(__file__).resolve().parents[1]
    installed = Path(gs.__file__).resolve()
    if installed.is_relative_to(repository / "src"):
        raise RuntimeError(f"smoke test imported repository source: {installed}")
    if not installed.with_name("py.typed").is_file():
        raise RuntimeError("installed wheel is missing its py.typed marker")
    if gs.available_palettes() != ["qualitative", "sequential", "diverging"]:
        raise RuntimeError("installed wheel is missing the public palettes")
    if gs.palette("sequential", n=3).at(0.5) != "#26908B":
        raise RuntimeError("installed wheel produced an unexpected palette lookup")
    try:
        gs.palette("qualitative", n=9)
    except ValueError:
        pass
    else:
        raise RuntimeError("installed wheel synthesized a ninth qualitative color")

    report_theme = gs.theme_spec(
        "minimal", base_size=11, overrides={"axes.titlesize": 14}
    )
    if gs.theme_params(report_theme)["font.size"] != 11:
        raise RuntimeError("installed wheel produced invalid theme parameters")

    dates = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-08"])
    figure, ax = plt.subplots()
    try:
        ax.fill_between(dates, [1.0, 2.0, 1.5], [1.5, 2.5, 2.0])
        result = gs.finish(
            ax,
            title="Installed wheel",
            subtitle="Layout-aware labels",
            caption="ggstyle smoke test",
            theme=report_theme,
            y=gs.axis(title="Value", labels=gs.label_number(decimals=1)),
        )
        if result.axes is not ax or not isinstance(result.plan, gs.FinishPlan):
            raise RuntimeError("installed wheel returned invalid finishing objects")
        if len(result.artists) < 4:
            raise RuntimeError("installed wheel did not create every requested label")
        handle = gs.dates(ax).ticks("daily").collapse()
        if not handle.observations.equals(dates):
            raise RuntimeError("installed wheel discovered incorrect observations")
        with tempfile.NamedTemporaryFile(suffix=".png") as image:
            figure.savefig(image.name)
            if Path(image.name).stat().st_size == 0:
                raise RuntimeError("installed wheel rendered an empty image")
    finally:
        plt.close(figure)

    if len(gs.available_themes()) != 9:
        raise RuntimeError("installed wheel does not contain every theme")
    for name in gs.available_themes():
        if not gs.stylesheet(name).is_file():
            raise RuntimeError(f"installed wheel is missing theme {name!r}")

    print(f"wheel smoke passed: ggstyle {gs.__version__} from {installed}")


if __name__ == "__main__":
    main()
