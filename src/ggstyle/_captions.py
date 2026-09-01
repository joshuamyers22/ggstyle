"""Pure text policy for date-axis captions."""

from ._axis_summary import AxisSummary
from ._date_summary import format_date_range


def format_caption(summary: AxisSummary) -> str:
    """Describe visible date-axis semantics without rendering an artist."""
    parts = [f"{summary.observations:,} observations"]
    if summary.start is not None and summary.end is not None:
        parts.append(format_date_range(summary.start, summary.end))
    parts.append(
        "unobserved dates collapsed"
        if summary.mode == "collapse"
        else "calendar gaps shown"
    )
    if summary.missing_values:
        parts.append(f"{summary.missing_values:,} missing excluded")
    if summary.timezone:
        parts.append(f"labels: {summary.timezone}")
    return " · ".join(parts)
