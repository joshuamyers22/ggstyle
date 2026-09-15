"""Reproduce the v0.5 semantic-mapping architecture decision.

The default command validates and prints the checked-in scorecard without importing
optional plotting libraries. ``--probe`` executes the small prototypes that produced
the interoperability observations recorded by ADR 0003.
"""

from __future__ import annotations

import argparse
import inspect
import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.lines import Line2D

import ggstyle as gs

CandidateKey = Literal["native", "seaborn-objects", "plotnine-docs"]

CRITERIA = (
    "date correctness",
    "existing-axes support",
    "faceting access",
    "public API stability",
    "dependency weight",
    "error quality",
    "typing",
    "artist access",
    "maintenance cost",
)

HARD_GATES = {
    "date correctness": 4,
    "existing-axes support": 4,
}

TESTED_VERSIONS = {
    "matplotlib": "3.11.2",
    "seaborn": "0.13.2",
    "plotnine": "0.15.8",
}


@dataclass(frozen=True)
class Score:
    """One candidate's score and evidence for a roadmap criterion."""

    criterion: str
    value: int
    evidence: str


@dataclass(frozen=True)
class Candidate:
    """One semantic-mapping architecture candidate."""

    key: CandidateKey
    label: str
    disposition: str
    scores: tuple[Score, ...]
    sources: tuple[str, ...]

    @property
    def total(self) -> int:
        """Return the equally weighted score total."""

        return sum(score.value for score in self.scores)

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe candidate evidence."""

        return {
            "disposition": self.disposition,
            "key": self.key,
            "label": self.label,
            "scores": {
                score.criterion: {
                    "evidence": score.evidence,
                    "value": score.value,
                }
                for score in self.scores
            },
            "sources": list(self.sources),
            "total": self.total,
        }


@dataclass(frozen=True)
class ProbeResult:
    """Observed result from an executable candidate prototype."""

    candidate: CandidateKey
    package_version: str
    verified: bool
    observations: dict[str, bool | int | str]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe probe evidence."""

        return {
            "candidate": self.candidate,
            "observations": dict(sorted(self.observations.items())),
            "package_version": self.package_version,
            "verified": self.verified,
        }


def _scores(*values: tuple[int, str]) -> tuple[Score, ...]:
    return tuple(
        Score(criterion=criterion, value=value, evidence=evidence)
        for criterion, (value, evidence) in zip(CRITERIA, values, strict=True)
    )


CANDIDATES = (
    Candidate(
        key="native",
        label="Narrow native helpers",
        disposition="selected",
        scores=_scores(
            (5, "Uses ggstyle's registered date scale and shared observation registry."),
            (5, "Draws ordinary artists on the caller's Axes."),
            (4, "Fits callback-based native facets without owning layout."),
            (4, "ggstyle owns a deliberately narrow provisional surface."),
            (5, "Adds no required plotting dependency."),
            (4, "Can validate mappings and fixed style before drawing."),
            (5, "Can expose typed specs and concrete result objects."),
            (5, "Returns the Axes, scales, and ordinary Matplotlib artists."),
            (3, "Requires ggstyle to train scales and construct guides."),
        ),
        sources=(
            "https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.plot.html",
            "https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.scatter.html",
            "https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.fill_between.html",
        ),
    ),
    Candidate(
        key="seaborn-objects",
        label="Optional seaborn.objects adapter",
        disposition="rejected as the v0.5 foundation; retain documented coexistence",
        scores=_scores(
            (
                4,
                "Datetime marks can feed ggstyle's date scale after compilation.",
            ),
            (4, "Plot.on supports an existing Axes for a single plot."),
            (5, "Plot.facet already provides row, column, wrap, and sharing controls."),
            (
                2,
                "The official objects tutorial describes the interface as experimental.",
            ),
            (3, "Would add an optional compiler and its dependency graph."),
            (3, "Adapter failures would cross two validation vocabularies."),
            (2, "The tested seaborn distribution does not publish a py.typed marker."),
            (3, "The caller can retain an Axes, but Plotter is the compilation result."),
            (
                4,
                "Delegates mappings and facets but needs an integration version matrix.",
            ),
        ),
        sources=(
            "https://seaborn.pydata.org/tutorial/objects_interface.html",
            "https://seaborn.pydata.org/generated/seaborn.objects.Plot.html",
            "https://seaborn.pydata.org/generated/seaborn.objects.Plot.on.html",
            "https://seaborn.pydata.org/generated/seaborn.objects.Plot.facet.html",
        ),
    ),
    Candidate(
        key="plotnine-docs",
        label="Documentation-only plotnine interoperability",
        disposition="document as an alternative; do not build an adapter",
        scores=_scores(
            (3, "Owns datetime scales separately from ggstyle's collapsed-date registry."),
            (1, "ggplot.draw creates and returns a Figure rather than adopting an Axes."),
            (5, "Provides mature wrap/grid facets and fixed/free scale policies."),
            (4, "Exposes a broad, versioned grammar API."),
            (2, "Adds a second plotting stack when installed."),
            (3, "Errors use grammar concepts outside ggstyle's vocabulary."),
            (4, "The tested distribution publishes typing metadata."),
            (2, "draw returns a Figure, not semantic scale and artist results."),
            (5, "Documentation-only coexistence creates no adapter maintenance."),
        ),
        sources=(
            "https://plotnine.org/reference/ggplot.html",
            "https://plotnine.org/reference/facet_wrap.html",
            "https://plotnine.org/guide/geometric-objects.html",
        ),
    ),
)


def validate_scorecard() -> None:
    """Raise when checked-in decision evidence is incomplete or inconsistent."""

    expected = set(CRITERIA)
    if len({candidate.key for candidate in CANDIDATES}) != len(CANDIDATES):
        raise RuntimeError("candidate keys must be unique")
    for candidate in CANDIDATES:
        actual = {score.criterion for score in candidate.scores}
        if actual != expected or len(candidate.scores) != len(CRITERIA):
            raise RuntimeError(
                f"{candidate.key} does not score every criterion exactly once"
            )
        if any(not 1 <= score.value <= 5 for score in candidate.scores):
            raise RuntimeError(f"{candidate.key} scores must be between 1 and 5")
        if any(not score.evidence.strip() for score in candidate.scores):
            raise RuntimeError(f"{candidate.key} has missing evidence")

    ranking = sorted(CANDIDATES, key=lambda candidate: candidate.total, reverse=True)
    if ranking[0].key != "native" or ranking[0].total == ranking[1].total:
        raise RuntimeError("the scorecard must have one selected native-helper direction")
    selected = [
        candidate for candidate in CANDIDATES if candidate.disposition == "selected"
    ]
    if selected != [ranking[0]]:
        raise RuntimeError("the selected disposition must match the score winner")
    selected_scores = {score.criterion: score.value for score in selected[0].scores}
    failed_gates = [
        criterion
        for criterion, minimum in HARD_GATES.items()
        if selected_scores[criterion] < minimum
    ]
    if failed_gates:
        names = ", ".join(failed_gates)
        raise RuntimeError(f"selected candidate fails hard gates: {names}")


def scorecard() -> dict[str, Any]:
    """Return the reproducible semantic-mapping decision as plain data."""

    validate_scorecard()
    ranked = sorted(CANDIDATES, key=lambda candidate: (-candidate.total, candidate.key))
    return {
        "candidates": [candidate.as_dict() for candidate in ranked],
        "criteria": list(CRITERIA),
        "decision": "narrow native helpers",
        "hard_gates": dict(sorted(HARD_GATES.items())),
        "scale": "1 (poor) to 5 (strong), equally weighted",
        "tested_versions": dict(sorted(TESTED_VERSIONS.items())),
    }


def _sample_data() -> pd.DataFrame:
    dates = pd.to_datetime(
        [
            "2024-01-05",
            "2024-01-08",
            "2024-01-19",
            "2024-01-05",
            "2024-01-08",
            "2024-01-19",
        ]
    )
    return pd.DataFrame(
        {
            "date": dates,
            "series": ["A", "A", "A", "B", "B", "B"],
            "value": [1.0, 1.5, 1.25, 0.8, 1.1, 1.6],
        }
    )


def _native_line_prototype(
    data: pd.DataFrame,
    *,
    x: str,
    y: str,
    color: str | None = None,
    group: str | None = None,
    style: dict[str, Any] | None = None,
    ax: Axes,
) -> tuple[Axes, tuple[Line2D, ...]]:
    """Prototype explicit mapped/fixed separation without defining public API."""

    missing = [name for name in (x, y, color, group) if name and name not in data]
    if missing:
        raise ValueError(f"unknown mapped columns: {', '.join(missing)}")
    fixed = dict(style or {})
    if color is not None and "color" in fixed:
        raise ValueError("color cannot be both mapped and fixed")

    grouping = list(dict.fromkeys(name for name in (group, color) if name is not None))
    color_values = list(pd.unique(data[color])) if color is not None else []
    colors = gs.palette("qualitative", n=len(color_values)).colors
    color_map = dict(zip(color_values, colors, strict=True))
    pieces: Any
    if grouping:
        pieces = data.groupby(grouping, sort=False, observed=True, dropna=False)
    else:
        pieces = [(None, data)]

    artists: list[Line2D] = []
    for _, frame in pieces:
        properties = dict(fixed)
        if color is not None:
            properties["color"] = color_map[frame[color].iloc[0]]
        artists.extend(ax.plot(frame[x], frame[y], **properties))
    return ax, tuple(artists)


def _installed_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError as error:
        raise RuntimeError(
            f"{distribution} is required for this optional probe; use the command in "
            "REPRODUCIBILITY.md"
        ) from error


def probe_native() -> ProbeResult:
    """Run the no-dependency native-helper prototype."""

    data = _sample_data()
    original = data.copy(deep=True)
    figure, ax = plt.subplots()
    try:
        returned_axes, artists = _native_line_prototype(
            data,
            x="date",
            y="value",
            color="series",
            group="series",
            style={"linewidth": 2.0},
            ax=ax,
        )
        date_axis = gs.dates(ax).collapse()
        observations = {
            "adopts_existing_axes": returned_axes is ax and figure.axes == [ax],
            "collapsed_date_scale": date_axis.mode == "collapse",
            "mapped_groups": len(artists),
            "ordinary_line_artists": all(isinstance(artist, Line2D) for artist in artists),
            "preserves_input": data.equals(original),
            "returns_artists": len(artists) == 2,
            "separates_fixed_style": all(
                artist.get_linewidth() == 2.0 for artist in artists
            ),
        }
        verified = all(value is True or value == 2 for value in observations.values())
        return ProbeResult(
            candidate="native",
            package_version=version("matplotlib"),
            verified=verified,
            observations=observations,
        )
    finally:
        plt.close(figure)


def probe_seaborn_objects() -> ProbeResult:
    """Run the public ``seaborn.objects`` existing-Axes prototype."""

    seaborn_version = _installed_version("seaborn")
    import seaborn
    import seaborn.objects as so

    data = _sample_data()
    original = data.copy(deep=True)
    figure, ax = plt.subplots()
    try:
        result = (
            so.Plot(data, x="date", y="value", color="series")
            .add(so.Line(linewidth=2))
            .on(ax)
            .plot()
        )
        date_axis = gs.dates(ax, data=data["date"]).collapse()
        lines = tuple(ax.get_lines())
        observations = {
            "adopts_existing_axes": figure.axes == [ax],
            "collapsed_date_scale": date_axis.mode == "collapse",
            "mapped_groups": len(lines),
            "ordinary_line_artists": all(isinstance(artist, Line2D) for artist in lines),
            "plotter_result": type(result).__name__ == "Plotter",
            "preserves_input": data.equals(original),
            "publishes_py_typed": Path(seaborn.__file__).with_name("py.typed").is_file(),
        }
        verified = (
            observations["adopts_existing_axes"] is True
            and observations["collapsed_date_scale"] is True
            and observations["mapped_groups"] == 2
            and observations["ordinary_line_artists"] is True
            and observations["plotter_result"] is True
            and observations["preserves_input"] is True
            and observations["publishes_py_typed"] is False
        )
        return ProbeResult(
            candidate="seaborn-objects",
            package_version=seaborn_version,
            verified=verified,
            observations=observations,
        )
    finally:
        plt.close(figure)


def probe_plotnine() -> ProbeResult:
    """Run the public plotnine draw/interoperability prototype."""

    plotnine_version = _installed_version("plotnine")
    import plotnine
    from plotnine import aes, geom_line, ggplot

    data = _sample_data()
    original = data.copy(deep=True)
    plot = ggplot(data, aes(x="date", y="value", color="series")) + geom_line(size=1)
    figure = plot.draw(show=False)
    try:
        draw_parameters = inspect.signature(plot.draw).parameters
        lines = tuple(figure.axes[0].get_lines())
        observations = {
            "creates_figure": len(figure.axes) == 1,
            "draw_accepts_existing_axes": "ax" in draw_parameters,
            "mapped_groups": len(lines),
            "ordinary_line_artists": all(isinstance(artist, Line2D) for artist in lines),
            "preserves_input": data.equals(original),
            "publishes_py_typed": Path(plotnine.__file__).with_name("py.typed").is_file(),
            "returns_figure": type(figure).__name__ == "Figure",
        }
        verified = (
            observations["creates_figure"] is True
            and observations["draw_accepts_existing_axes"] is False
            and observations["mapped_groups"] == 2
            and observations["ordinary_line_artists"] is True
            and observations["preserves_input"] is True
            and observations["publishes_py_typed"] is True
            and observations["returns_figure"] is True
        )
        return ProbeResult(
            candidate="plotnine-docs",
            package_version=plotnine_version,
            verified=verified,
            observations=observations,
        )
    finally:
        plt.close(figure)


def run_probes(selection: str) -> list[ProbeResult]:
    """Execute one or all candidate prototypes."""

    probes = {
        "native": probe_native,
        "plotnine-docs": probe_plotnine,
        "seaborn-objects": probe_seaborn_objects,
    }
    keys = tuple(probes) if selection == "all" else (selection,)
    results = [probes[key]() for key in keys]
    failed = [result.candidate for result in results if not result.verified]
    if failed:
        raise RuntimeError(f"semantic mapping probe failed: {', '.join(failed)}")
    return results


def _print_human(payload: dict[str, Any], probes: list[ProbeResult]) -> None:
    print("semantic mapping decision: narrow native helpers")
    for candidate in payload["candidates"]:
        print(f"  {candidate['total']:>2}/45  {candidate['label']}")
    if probes:
        print("executable probes:")
        for probe in probes:
            print(f"  verified  {probe.candidate} {probe.package_version}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit strict JSON")
    parser.add_argument(
        "--probe",
        choices=("all", "native", "seaborn-objects", "plotnine-docs"),
        help="execute prototype interoperability checks",
    )
    args = parser.parse_args()
    payload = scorecard()
    probes = run_probes(args.probe) if args.probe else []
    if probes:
        payload["probes"] = [probe.as_dict() for probe in probes]
    if args.json:
        print(json.dumps(payload, allow_nan=False, indent=2, sort_keys=True))
    else:
        _print_human(payload, probes)


if __name__ == "__main__":
    main()
