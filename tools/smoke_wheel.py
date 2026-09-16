"""Exercise the installed wheel without importing the repository source tree."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import ggstyle as gs


def main() -> None:
    """Render a collapsed plot with direct labels and validate packaged resources."""
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

    facet = gs.facet_plan(
        {"segment": ["B", "A", "B"]},
        col="segment",
        wrap=2,
    )
    if facet.shape != (1, 2) or [panel.indices for panel in facet.panels] != [
        (0, 2),
        (1,),
    ]:
        raise RuntimeError("installed wheel produced an invalid facet plan")
    facet_payload = facet.as_dict()
    json.dumps(facet_payload, allow_nan=False)
    if json.loads(facet.describe()) != facet_payload:
        raise RuntimeError("installed wheel produced inconsistent facet inspection")

    facet_grid = gs.facets(
        {
            "segment": ["B", "A", "B"],
            "x": [1, 1, 2],
            "value": [1, 2, 3],
        },
        col="segment",
        wrap=2,
        scales="free_y",
    )
    try:
        facet_grid.map(
            lambda panel, axes: gs.line(
                panel,
                x="x",
                y="value",
                style={"color": "#4477AA"},
                ax=axes,
            )
        )
        if len(facet_grid.axes) != 2 or facet_grid.map_count != 1:
            raise RuntimeError("installed wheel produced an invalid facet grid")
        facet_grid.figure.canvas.draw()
        grid_payload = facet_grid.as_dict()
        json.dumps(grid_payload, allow_nan=False)
        if json.loads(facet_grid.describe()) != grid_payload:
            raise RuntimeError("installed wheel produced inconsistent grid inspection")
    finally:
        plt.close(facet_grid.figure)

    grid_facet = gs.facets(
        {
            "region": ["North", "South", "North"],
            "metric": ["Value", "Value", "Rate"],
            "value": [1, 2, 3],
        },
        row="region",
        col="metric",
    )
    try:
        grid_rows: list[int] = []
        grid_facet.map(lambda panel, axes: grid_rows.append(len(panel["value"])))
        if grid_facet.plan.shape != (2, 2) or grid_rows != [1, 1, 1, 0]:
            raise RuntimeError("installed wheel produced invalid grid facet partitions")
        if [axes.get_title() for axes in grid_facet.axes] != [
            "North | Value",
            "North | Rate",
            "South | Value",
            "South | Rate",
        ]:
            raise RuntimeError("installed wheel produced invalid grid facet order")
        grid_facet.figure.canvas.draw()
    finally:
        plt.close(grid_facet.figure)

    report_theme = gs.theme_spec(
        "minimal", base_size=11, overrides={"axes.titlesize": 14}
    )
    if gs.theme_params(report_theme)["font.size"] != 11:
        raise RuntimeError("installed wheel produced invalid theme parameters")

    dates = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-08"])
    figure, ax = plt.subplots()
    try:
        ax.fill_between(dates, [1.0, 2.0, 1.5], [1.5, 2.5, 2.0])
        semantic = gs.line(
            pd.DataFrame(
                {
                    "date": dates,
                    "value": [1.25, 2.25, 1.75],
                    "series": ["Median"] * 3,
                }
            ),
            x="date",
            y="value",
            color="series",
            color_scale=gs.DiscreteScale(order=("Median",)),
            style={"label": "Median"},
            ax=ax,
        )
        if semantic.axes is not ax or len(semantic.artists) != 1:
            raise RuntimeError("installed wheel returned invalid semantic line objects")
        if semantic.scales["color"].as_dict()["levels"] != ["Median"]:
            raise RuntimeError("installed wheel trained an invalid semantic line scale")
        semantic_payload = semantic.as_dict()
        json.dumps(semantic_payload, allow_nan=False)
        if json.loads(semantic.describe()) != semantic_payload:
            raise RuntimeError("installed wheel produced inconsistent result inspection")
        points = gs.points(
            {"date": dates, "value": [1.25, 2.25, 1.75], "series": ["Median"] * 3},
            x="date",
            y="value",
            color="series",
            color_scale=gs.DiscreteScale(order=("Median",)),
            ax=ax,
        )
        ribbon = gs.ribbon(
            {"date": dates, "low": [1.0, 2.0, 1.5], "high": [1.5, 2.5, 2.0]},
            x="date",
            lower="low",
            upper="high",
            ax=ax,
        )
        if len(points.artists) != 1 or len(ribbon.artists) != 1:
            raise RuntimeError("installed wheel returned invalid point or ribbon objects")
        semantic_guides = gs.guides(ax)
        if len(semantic_guides.legends) != 1 or semantic_guides.colorbars:
            raise RuntimeError("installed wheel returned invalid semantic guides")
        if semantic_guides.legends[0].get_title().get_text() != "series":
            raise RuntimeError("installed wheel returned an invalid guide title")
        if json.loads(semantic_guides.describe()) != semantic_guides.as_dict():
            raise RuntimeError("installed wheel produced inconsistent guide inspection")
        gs.guides(ax, enabled=False)
        line = semantic.artists[0]
        result = gs.finish(
            ax,
            title="Installed wheel",
            subtitle="Layout-aware labels",
            caption="ggstyle smoke test",
            theme=report_theme,
            direct_labels=gs.end_labels(),
            y=gs.axis(title="Value", labels=gs.label_number(decimals=1)),
        )
        if result.axes is not ax or not isinstance(result.plan, gs.FinishPlan):
            raise RuntimeError("installed wheel returned invalid finishing objects")
        plan_payload = result.plan.as_dict()
        json.dumps(plan_payload, allow_nan=False)
        if json.loads(result.plan.describe()) != plan_payload:
            raise RuntimeError("installed wheel produced inconsistent plan inspection")
        if len(result.artists) < 4:
            raise RuntimeError("installed wheel did not create every requested label")
        endpoint_labels = [item for item in ax.texts if item.get_text() == "Median"]
        if len(endpoint_labels) != 1 or endpoint_labels[0].get_color() != line.get_color():
            raise RuntimeError("installed wheel did not create the direct line label")
        handle = gs.dates(ax).ticks("daily").collapse()
        if not handle.observations.equals(dates):
            raise RuntimeError("installed wheel discovered incorrect observations")
        summary_payload = handle.summary().as_dict()
        json.dumps(summary_payload, allow_nan=False)
        if json.loads(handle.summary().describe()) != summary_payload:
            raise RuntimeError("installed wheel produced inconsistent axis inspection")
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "smoke.png"
            saved = gs.save(
                figure,
                image,
                width=4,
                height=3,
                dpi=100,
                bbox="standard",
            )
            if saved != image or image.stat().st_size == 0:
                raise RuntimeError("installed wheel rendered an empty image")
            try:
                gs.save(figure, image, width=4, height=3)
            except FileExistsError:
                pass
            else:
                raise RuntimeError("installed wheel overwrote an artifact implicitly")
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
