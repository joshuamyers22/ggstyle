"""Validate the public API's NumPy-style docstrings with numpydoc."""

from __future__ import annotations

from numpydoc.validate import validate

PUBLIC_OBJECTS = (
    "ggstyle._cadence.Cadence",
    "ggstyle.dates.AxisSummary",
    "ggstyle.dates.DateAxis",
    "ggstyle.dates.DateDiscoveryError",
    "ggstyle.dates.dates",
    "ggstyle.dates.sync_dates",
    "ggstyle.formats.NumericLabeller",
    "ggstyle.formats.label_currency",
    "ggstyle.formats.label_number",
    "ggstyle.formats.label_percent",
    "ggstyle.formats.label_si",
    "ggstyle.finish.AxisSpec",
    "ggstyle.finish.FinishPlan",
    "ggstyle.finish.FinishResult",
    "ggstyle.finish.axis",
    "ggstyle.finish.finish",
    "ggstyle.formatters.as_formatter",
    "ggstyle.palettes.Palette",
    "ggstyle.palettes.Palette.at",
    "ggstyle.palettes.Palette.sample",
    "ggstyle.palettes.available_palettes",
    "ggstyle.palettes.palette",
    "ggstyle.theme.available_themes",
    "ggstyle.theme.stylesheet",
    "ggstyle.theme.theme",
    "ggstyle.theme.ThemeSpec",
    "ggstyle.theme.theme_params",
    "ggstyle.theme.theme_spec",
    "ggstyle.theme.use_theme",
)

DATE_AXIS_METHODS = (
    "clear_annotations",
    "collapse",
    "caption",
    "date_at",
    "dispose",
    "expand",
    "fmt",
    "grid",
    "loc",
    "pad",
    "rotate",
    "refresh",
    "span",
    "spans",
    "summary",
    "ticks",
    "tz",
    "vline",
    "zoom",
)

# Simple accessors do not need an extended summary, See Also, and an example.
# Structural and contract errors remain release blockers.
IGNORED_CODES = {"ES01", "SA01", "EX01"}


def main() -> int:
    """Return a nonzero status when a public docstring violates its contract."""
    names = list(PUBLIC_OBJECTS)
    names.extend(f"ggstyle.dates.DateAxis.{name}" for name in DATE_AXIS_METHODS)

    failed = False
    for name in names:
        errors = [
            error for error in validate(name)["errors"] if error[0] not in IGNORED_CODES
        ]
        for code, message in errors:
            failed = True
            print(f"{name}: {code}: {message}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
