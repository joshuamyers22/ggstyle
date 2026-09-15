"""Validate the v0.4 finishing-API usability fixtures.

The snippets in this module are design fixtures, not executable examples of the
currently released API.  They keep the accepted vocabulary and the code-reduction
claim measurable while the v0.4 implementation lands in focused pull requests.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from textwrap import dedent

MINIMUM_REDUCTION = 0.35
TARGET_PERSONAS = frozenset(
    {
        "analyst",
        "ggplot2-migrant",
        "library-author",
        "reporting-engineer",
        "researcher",
    }
)
REQUIRED_CAPABILITIES = frozenset(
    {
        "direct-labels",
        "inspection",
        "labels",
        "legend",
        "numeric-labels",
        "palettes",
        "save",
        "themes",
    }
)


@dataclass(frozen=True)
class UsabilityCase:
    """Describe one canonical, non-data figure-finishing task."""

    case_id: str
    title: str
    personas: tuple[str, ...]
    capabilities: tuple[str, ...]
    baseline: str
    proposed: str
    guarantees: tuple[str, ...] = ("native-axes", "no-data-mutation")


@dataclass(frozen=True)
class UsabilityReport:
    """Summarize the stable logical-statement comparison."""

    cases: int
    baseline_statements: int
    proposed_statements: int
    reduction: float
    personas: tuple[str, ...]
    capabilities: tuple[str, ...]


CASES = (
    UsabilityCase(
        case_id="F01",
        title="Title, subtitle, caption, and axis titles",
        personas=("analyst", "researcher", "ggplot2-migrant"),
        capabilities=("labels",),
        baseline="""
            ax.set_title("Revenue")
            ax.set_xlabel("Date")
            ax.set_ylabel("USD")
            fig.text(0.125, 0.91, "Trailing twelve months")
            fig.text(0.99, 0.01, "Source: annual report", ha="right")
        """,
        proposed="""
            gs.finish(
                ax,
                title="Revenue",
                subtitle="Trailing twelve months",
                caption="Source: annual report",
                x=gs.axis(title="Date"),
                y=gs.axis(title="USD"),
            )
        """,
        guarantees=("native-axes", "no-data-mutation", "layout-aware"),
    ),
    UsabilityCase(
        case_id="F02",
        title="Percent axis with explicit scale and precision",
        personas=("analyst", "reporting-engineer"),
        capabilities=("numeric-labels",),
        baseline="""
            ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=1))
            ax.set_ylabel("Share")
        """,
        proposed="""
            gs.finish(
                ax,
                y=gs.axis(
                    title="Share",
                    labels=gs.label_percent(scale=1.0, decimals=1),
                ),
            )
        """,
    ),
    UsabilityCase(
        case_id="F03",
        title="Currency axis scaled to millions",
        personas=("analyst", "reporting-engineer"),
        capabilities=("numeric-labels",),
        baseline="""
            formatter = mticker.FuncFormatter(
                lambda value, _: f"${value / 1_000_000:,.1f}M"
            )
            ax.yaxis.set_major_formatter(formatter)
            ax.set_ylabel("Revenue")
        """,
        proposed="""
            gs.finish(
                ax,
                y=gs.axis(
                    title="Revenue",
                    labels=gs.label_currency(
                        "$", scale=1_000_000, decimals=1, suffix="M"
                    ),
                ),
            )
        """,
    ),
    UsabilityCase(
        case_id="F04",
        title="Grouped numbers and SI notation on two axes",
        personas=("researcher", "library-author"),
        capabilities=("numeric-labels",),
        baseline="""
            ax.xaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
            ax.yaxis.set_major_formatter(mticker.EngFormatter(unit="B"))
            ax.set_xlabel("Observations")
            ax.set_ylabel("Bytes")
        """,
        proposed="""
            gs.finish(
                ax,
                x=gs.axis(
                    title="Observations", labels=gs.label_number(grouping=True)
                ),
                y=gs.axis(title="Bytes", labels=gs.label_si(unit="B")),
            )
        """,
    ),
    UsabilityCase(
        case_id="F05",
        title="Accessible qualitative palette for subsequent artists",
        personas=("researcher", "ggplot2-migrant", "library-author"),
        capabilities=("palettes",),
        baseline="""
            colors = [
                "#000000",
                "#E69F00",
                "#56B4E9",
                "#009E73",
                "#F0E442",
                "#0072B2",
                "#D55E00",
                "#CC79A7",
            ]
            ax.set_prop_cycle(color=colors)
            palette_metadata = {"name": "Okabe-Ito", "maximum": len(colors)}
        """,
        proposed="""
            ax.set_prop_cycle(color=gs.palette("qualitative").colors)
        """,
        guarantees=("native-axes", "no-data-mutation", "defensive-values"),
    ),
    UsabilityCase(
        case_id="F06",
        title="Scoped theme with base typography and validated overrides",
        personas=("ggplot2-migrant", "library-author"),
        capabilities=("themes",),
        baseline="""
            ax.set_facecolor("white")
            ax.grid(color="#D9D9D9")
            ax.title.set_fontsize(14)
            ax.xaxis.label.set_fontfamily("DejaVu Sans")
            ax.yaxis.label.set_fontfamily("DejaVu Sans")
        """,
        proposed="""
            gs.finish(
                ax,
                theme=gs.theme_spec(
                    "minimal",
                    base_size=11,
                    base_family="DejaVu Sans",
                    overrides={"axes.titlesize": 14},
                ),
            )
        """,
        guarantees=(
            "native-axes",
            "no-data-mutation",
            "existing-axes-boundary-reported",
        ),
    ),
    UsabilityCase(
        case_id="F07",
        title="Top legend with an explicit title",
        personas=("analyst", "ggplot2-migrant"),
        capabilities=("legend",),
        baseline="""
            legend = ax.legend(
                title="Region",
                loc="lower center",
                bbox_to_anchor=(0.5, 1.02),
                ncols=3,
            )
            legend.set_frame_on(False)
            figure.subplots_adjust(top=0.82)
        """,
        proposed="""
            gs.finish(ax, legend="top", legend_title="Region")
        """,
        guarantees=("native-axes", "no-data-mutation", "layout-aware"),
    ),
    UsabilityCase(
        case_id="F08",
        title="Reproducible raster and vector export",
        personas=("reporting-engineer", "researcher"),
        capabilities=("save",),
        baseline="""
            figure.set_size_inches(7.0, 4.0)
            figure.savefig(
                "report.png",
                dpi=300,
                bbox_inches="tight",
                metadata={"Creator": "ggstyle"},
            )
            figure.savefig(
                "report.svg",
                bbox_inches="tight",
                metadata={"Creator": "ggstyle"},
            )
        """,
        proposed="""
            gs.save(
                figure,
                "report.png",
                width=7,
                height=4,
                units="in",
                dpi=300,
                metadata={"Creator": "ggstyle"},
            )
            gs.save(
                figure,
                "report.svg",
                width=7,
                height=4,
                units="in",
                metadata={"Creator": "ggstyle"},
            )
        """,
        guarantees=("native-axes", "no-data-mutation", "explicit-overwrite-policy"),
    ),
    UsabilityCase(
        case_id="F09",
        title="Collision-aware endpoint labels with legend fallback",
        personas=("analyst", "researcher", "ggplot2-migrant"),
        capabilities=("direct-labels", "legend"),
        baseline="""
            annotations = []
            for line in ax.lines:
                x_value, y_value = line.get_xdata()[-1], line.get_ydata()[-1]
                annotations.append(
                    ax.annotate(
                        line.get_label(),
                        (x_value, y_value),
                        color=line.get_color(),
                    )
                )
            legend = ax.get_legend()
            if legend is not None:
                legend.remove()
        """,
        proposed="""
            gs.finish(ax, direct_labels=gs.end_labels(collision="avoid", fallback="legend"))
        """,
        guarantees=("native-axes", "no-data-mutation", "artist-handles-returned"),
    ),
    UsabilityCase(
        case_id="F10",
        title="Inspect a finishing request without mutation",
        personas=("library-author", "reporting-engineer"),
        capabilities=("inspection", "labels", "themes"),
        baseline="""
            current_title = ax.get_title()
            current_xlabel = ax.get_xlabel()
            current_ylabel = ax.get_ylabel()
            current_legend = ax.get_legend()
            state = {
                "title": current_title,
                "x": current_xlabel,
                "y": current_ylabel,
                "legend": current_legend is not None,
            }
        """,
        proposed="""
            plan = gs.finish(ax, title="Preview", theme="minimal", dry_run=True)
        """,
        guarantees=("native-axes", "no-data-mutation", "serializable-plan"),
    ),
)


def logical_statement_count(source: str) -> int:
    """Count formatting-independent Python statements in a snippet."""
    tree = ast.parse(dedent(source).strip())
    return sum(isinstance(node, ast.stmt) for node in ast.walk(tree))


def validate_cases(cases: Sequence[UsabilityCase] = CASES) -> None:
    """Raise ``ValueError`` when the fixture registry violates the ADR contract."""
    if len(cases) != 10:
        raise ValueError(f"expected 10 finishing cases, found {len(cases)}")
    identifiers = [case.case_id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("finishing case identifiers must be unique")

    personas = {persona for case in cases for persona in case.personas}
    if personas != TARGET_PERSONAS:
        raise ValueError(f"persona coverage differs: {sorted(personas)}")
    capabilities = {capability for case in cases for capability in case.capabilities}
    if capabilities != REQUIRED_CAPABILITIES:
        raise ValueError(f"capability coverage differs: {sorted(capabilities)}")

    for case in cases:
        if (
            "native-axes" not in case.guarantees
            or "no-data-mutation" not in case.guarantees
        ):
            raise ValueError(f"{case.case_id} does not preserve core escape hatches")
        baseline_count = logical_statement_count(case.baseline)
        proposed_count = logical_statement_count(case.proposed)
        if proposed_count >= baseline_count:
            raise ValueError(
                f"{case.case_id} is not shorter: {proposed_count} >= {baseline_count}"
            )
        proposed = dedent(case.proposed)
        if "gs." not in proposed or ("ax" not in proposed and "figure" not in proposed):
            raise ValueError(f"{case.case_id} does not retain native object access")
        if any(token in proposed for token in (".plot(", ".scatter(", ".fill_between(")):
            raise ValueError(f"{case.case_id} mixes data drawing into finishing policy")


def build_report(cases: Sequence[UsabilityCase] = CASES) -> UsabilityReport:
    """Build the aggregate usability report after validating every fixture."""
    validate_cases(cases)
    baseline = sum(logical_statement_count(case.baseline) for case in cases)
    proposed = sum(logical_statement_count(case.proposed) for case in cases)
    return UsabilityReport(
        cases=len(cases),
        baseline_statements=baseline,
        proposed_statements=proposed,
        reduction=1.0 - proposed / baseline,
        personas=tuple(sorted({persona for case in cases for persona in case.personas})),
        capabilities=tuple(
            sorted({capability for case in cases for capability in case.capabilities})
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Print the report and fail when the accepted reduction gate regresses."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument(
        "--minimum-reduction",
        type=float,
        default=MINIMUM_REDUCTION,
        help="minimum aggregate logical-statement reduction",
    )
    arguments = parser.parse_args(argv)
    if not 0.0 <= arguments.minimum_reduction < 1.0:
        parser.error("--minimum-reduction must be at least 0 and less than 1")

    report = build_report()
    if arguments.json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        print(
            "finishing usability: "
            f"{report.cases} cases, {len(report.personas)} personas, "
            f"{report.baseline_statements} -> {report.proposed_statements} statements "
            f"({report.reduction:.1%} reduction)"
        )
    if report.reduction < arguments.minimum_reduction:
        raise RuntimeError(
            f"usability reduction {report.reduction:.1%} is below "
            f"{arguments.minimum_reduction:.1%}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
