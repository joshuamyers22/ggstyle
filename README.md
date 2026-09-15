# ggstyle

Publication finishing and safe date axes for Matplotlib.

**v0.5 adds narrow semantic helpers to the v0.4 publication-finishing kit.**
Transactional tidy-data `line()`, `points()`, and `ribbon()` helpers share trained color
mappings. Native Matplotlib axes and artists remain the intended path; ggstyle is not a
general grammar compiler.

The date-axis behavior is tested, but the project is still young and follows semantic
versioning. See the [known limits](#known-limits) before using collapsed mode in
production.

## Why

Most of the pain in Python time-series plotting is not the grammar, it's the axis: ticks in
the wrong places, labels rotated to hide the fact that there are too many of them, weekend
gaps shredding an intraday chart, and annotation code that quietly puts your vertical line
three days off. `ggstyle` fixes the axis first.

## Install

```bash
pip install ggstyle
```

For development from a clone:

```bash
pip install -e ".[dev]"
```

## Use

It adopts any Axes, including plots it never made:

```python
import matplotlib.pyplot as plt
import ggstyle as gs

gs.use_theme()                            # "minimal" is the default

fig, ax = plt.subplots()
ax.plot(df["date"], df["close"])          # plain matplotlib, seaborn, or df.plot()

gs.dates(ax).ticks("quarterly").fmt("month-year").zoom("2020", "2022")
```

Configuration and drawing methods return the handle, so calls chain.

Axis semantics are also available as structured data rather than only rendered output:

```python
summary = gs.dates(ax).summary()
caption = gs.dates(ax).caption(add=True)
```

### Finish labels

Apply a coherent title hierarchy and axis labels to the existing axes:

```python
result = gs.finish(
    ax,
    title="Revenue",
    subtitle="Trailing twelve months",
    caption="Source: annual report",
    theme=gs.theme_spec("minimal", base_size=11),
    x=gs.axis(title="Date"),
    y=gs.axis(title="USD", labels=gs.label_currency("$", decimals=0)),
)
```

`result.axes` is exactly `ax`; all returned artists are native Matplotlib objects.
Subtitle and caption artists participate in figure layout, repeated calls replace them
in place, and `False` removes them. Use `dry_run=True` to validate and inspect the
operation without mutation. `finish()` never edits data artists or global `rcParams`.
When a theme is supplied, its diagnostic reports settings such as colour cycles and
figure size that can only be applied safely before artists or figures are created.

Inspect the complete validated request without drawing or mutation:

```python
plan = gs.finish(ax, title="Revenue", theme="minimal", dry_run=True)
payload = plan.as_dict()  # strict JSON-compatible plain values
print(plan.describe())    # stable formatted JSON
```

### Tidy-data lines

Draw grouped lines on an existing axes while keeping mapped columns separate from fixed
Matplotlib style:

```python
result = gs.line(
    df,
    x="date",
    y="value",
    color="series",                    # mapped column
    linestyle="status",               # mapped column
    color_scale=gs.DiscreteScale(order=("A", "B")),
    style={"linewidth": 2},           # fixed artist properties
    sort="x",
    ax=ax,
)
```

`result.axes` is exactly `ax`, `result.artists` contains ordinary Matplotlib `Line2D`
artists, and `result.scales` exposes immutable trained color and linestyle mappings.
Discrete aesthetics imply grouping and retain stable first-seen assignments across
repeated calls on the same axes. Numeric color is continuous and must be constant within
each resolved line; supply `group=` when several lines share one numeric color column.

Input order is preserved by default. `sort="x"` performs a stable within-line sort and
retains duplicate x values without aggregation. Missing explicit groups are dropped by
default; choose `group_missing="keep"` or `"raise"` to make the alternative policy
explicit. A mapped aesthetic cannot also occur in `style`, including through the `c` or
`ls` aliases.

Pass an immutable `DiscreteScale` to control output values, category order, unobserved
levels, missing policy, or guide name. `ContinuousScale` accepts a sequential/diverging
`Palette`, explicit limits, and missing/infinite policies. Supplying a discrete color
scale also makes numeric codes categorical instead of continuous.

The operation validates and trains before drawing. If artist creation or an existing
date-axis refresh fails, artists, limits, units, property-cycle position, earlier mapped
styles, and semantic registry state are restored.

Points and explicit ribbons reuse the same trained mappings:

```python
gs.points(df, x="date", y="value", color="series", style={"size": 28}, ax=ax)
gs.ribbon(
    intervals,
    x="date",
    lower="low",
    upper="high",
    color="series",
    alpha=0.2,
    ax=ax,
)
```

`points()` maps continuous color per observation and returns native `PathCollection`
artists. `ribbon()` only renders caller-supplied lower/upper columns—it performs no
statistical inference—and returns native `PolyCollection` artists. Missing ribbon
coordinates break a band by default; use `missing="drop"` to connect across gaps.

Build guides from the complete trained registry after adding semantic layers:

```python
guide_result = gs.guides(ax)
```

Discrete mappings become native legends and continuous color mappings become native
colorbars. Color and linestyle guides merge only when they describe the same variable,
title, and ordered levels. Distinct mappings remain distinct. Once activated, managed
guides refresh transactionally after later semantic-layer calls. Existing caller-owned
legends and colorbars are preserved; `gs.guides(ax, enabled=False)` removes only guides
owned by ggstyle.

All four semantic operations return a common runtime-checkable `RenderedResult`:

```python
payload = result.as_dict()  # bounded strict-JSON-compatible summary
print(result.describe())    # stable formatted JSON
```

The summary includes artist counts and types, trained scale descriptions, layer identity,
and diagnostics without serializing axes or live artists. Concrete results still expose
their geometry-specific native objects directly.

Replace a multi-series line legend with labels at the final visible data points:

```python
ax.plot(x, revenue, label="Revenue")
ax.plot(x, forecast, label="Forecast")

result = gs.finish(
    ax,
    direct_labels=gs.end_labels(collision="avoid", fallback="legend"),
)
```

Endpoint labels use each line's colour, reserve figure space on the right, and separate
nearby labels vertically without moving the data anchors. The operation is all-or-nothing:
if a public legend entry is not a visible ordinary `Line2D`, its endpoint is outside the
view, or the labels do not fit, the default policy builds a conventional legend instead.
Use `fallback="raise"` to reject that plot during preflight, `collision="none"` to retain
exact endpoint positions, and `direct_labels=False` to remove labels managed by ggstyle.

### Save figures

Export an explicit figure with publication-oriented defaults and overwrite protection:

```python
path = gs.save(
    fig,
    "report.png",
    width=7,
    height=4,
    units="in",
    dpi=300,
    metadata={"Creator": "ggstyle"},
)
```

Both dimensions are required, units may be `in`, `cm`, `mm`, or `px`, and the format is
inferred from the suffix unless supplied explicitly. Output is opaque and tightly bounded
by default; use `transparent=True` or `bbox="standard"` explicitly when needed. Tight
bounds crop the requested canvas to its decorated content, while standard bounds retain
the exact canvas dimensions.

`save()` refuses to overwrite by default. With `overwrite=True`, it renders to a temporary
file and replaces the destination only after success. A renderer failure therefore leaves
an existing file intact, and the figure's original size is restored in every case. SVG IDs
are stable and variable SVG/PDF timestamps are suppressed by default.

### Ticks — where they go

```python
.ticks("monthly")                   # daily | weekly | monthly | quarterly | yearly
.ticks("month-end")                 # anchored: month-start, quarter-end, year-start, ...
.ticks(every="3M")                  # any offset alias; legacy M/Q/Y/H accepted
.ticks(n=6)                         # about six ticks, snapped to a natural cadence
.ticks(at=["2020-01-01", "2021-07-01"])
.ticks(major="yearly", minor="monthly")
```

Anchoring is not cosmetic: month-start vs. month-end is the difference between labels that
line up with your observations and labels that float between them.

### Labels — what they say

```python
.fmt("concise")      # default: year shown once, not on every label
.fmt("month-year")   # Jun 2020
.fmt("quarter")      # Q2 2020
.fmt("year") / .fmt("month") / .fmt("day") / .fmt("iso") / .fmt("time")
.fmt("%b '%y")       # any strftime string
.fmt(lambda d: f"week {d.isocalendar().week}")
```

Changing the format never moves a tick, and changing the cadence never changes the format.
That orthogonality is a test, not an aspiration.

### Numeric axes

Percent, currency, grouped-number, and SI-prefix labels are locale-independent callables:

```python
currency = gs.label_currency("$", scale=1_000_000, decimals=1, suffix="M")
ax.yaxis.set_major_formatter(gs.as_formatter(currency))

gs.label_percent(decimals=1)(0.125)   # "12.5%"
gs.label_number(decimals=2)(1234.5)  # "1,234.50"
gs.label_si(unit="B")(1_500_000)     # "1.5 MB"
```

Factories do not mutate Matplotlib. The explicit adapter returns an ordinary
`matplotlib.ticker.FuncFormatter`, so axes and formatter objects remain directly
available.

### Palettes

The palette API exposes the shared eight-colour theme cycle and perceptually ordered
continuous options without changing Matplotlib configuration:

```python
ax.set_prop_cycle(color=gs.palette("qualitative").colors)

colors = gs.palette("sequential", n=5).colors
neutral = gs.palette("diverging").at(0.5)  # "#F7F7F7"
```

Qualitative requests above eight fail instead of manufacturing ambiguous colours.
Diverging samples require an odd count so their explicit neutral midpoint is retained.
Continuous lookup makes missing and out-of-bounds behavior explicit through
`missing_color=` and `out_of_bounds=`. Palette values are immutable and can be passed to
ordinary Matplotlib cycles and colormaps.

### Range

Partial strings expand to whole periods, pandas-style:

```python
.zoom("2020", "2022")      # three complete years
.zoom("2020-03", None)     # open-ended
.zoom(last="6M")           # trailing window from the last observation, not from today
.zoom(ytd=True)
.pad(left="1M", right="1M")
```

### Gaps

```python
.collapse()   # unobserved dates get no space
.expand()     # true datetime axis, gaps restored
```

Collapsed mode is defined by **the dates present in your data**, not by a holiday calendar.
Anything not observed is not allocated space. That is correct for any market or region and
needs no extra dependency. With several series, the axis uses the union of observed dates.

### Annotation in date space

Every one of these is correct in both modes — that is the whole point of the handle:

```python
.loc("2020-03-23")                    # -> native matplotlib date coordinate
.vline("2020-03-23", label="trough")
.span("2020-02-19", "2020-03-23", label="drawdown")
.spans(events_df, start="begin", end="end", label="name")
.clear_annotations()                    # remove managed annotation artists safely
.grid("yearly")                       # gridline cadence, independent of ticks
```

In collapsed mode the scale places a date inside a gap (a Sunday, a holiday) by linear
interpolation between its neighbours. `loc()` always returns the same native matplotlib
date coordinate in either mode; `loc(date, snap=True)` rounds to the nearest observation,
and `loc(date, strict=True)` raises if the date was never observed.

### Escape hatch

Native matplotlib date input now passes through the same registered scale. Use datetime
values directly, or use `.loc()` when you want ggstyle's parsing, snapping, or strict
lookup:

```python
handle = gs.dates(ax).collapse()
ax.axvline(pd.Timestamp("2020-03-23")) # lands in the right place
ax.set_xlim(handle.loc("2020-01"), handle.loc("2021-01"))
```

## Themes

Nine ggplot2-inspired themes ship. `minimal` remains the default.

```python
gs.use_theme()             # minimal, process-wide
gs.use_theme("grey")       # "gray" also accepted
gs.use_theme("bw")

with gs.theme("dark"):     # scoped; restores every rcParam on exit
    ...

plt.style.use(gs.stylesheet())   # the .mplstyle on its own, no ggstyle import needed
```

Create a reusable recipe when a report needs a different type scale, family, or a small
set of Matplotlib overrides:

```python
report_theme = gs.theme_spec(
    "minimal",
    base_size=11,
    base_family="DejaVu Sans",
    overrides={"axes.titlesize": 14},
)

with gs.theme(report_theme):
    fig, ax = plt.subplots()      # complete creation-time styling

gs.finish(ax, theme=report_theme) # safe non-data styling on an existing axes
params = gs.theme_params(report_theme)  # pure, read-only resolved mapping
```

Recipes validate names and values immediately. Base sizing scales the full theme type
system proportionally, base family is applied next, and explicit overrides win. Applying
a recipe through `finish()` updates panel and figure surfaces, spines, grid lines, ticks,
titles, labels, and an existing legend. It deliberately preserves data artists, property
cycles, figure geometry, line defaults, save settings, and global `rcParams`; those
creation-, data-, and output-time settings are listed in `result.diagnostics`.

Available names are `minimal`, `grey`, `bw`, `linedraw`, `light`, `dark`, `classic`,
`void`, and `test`. The corresponding ggplot2 function spellings, such as `theme_bw` and
`theme_classic`, are accepted as aliases. `test` is intended for stable visual tests,
while `void` removes the plotting surface for maps and other annotation-free displays.

All themes spell out the same type scale and public qualitative colour cycle, so switching
changes the non-data surface rather than the plot's identity. The cycle is Okabe–Ito-derived,
uses black in place of grey for stronger separation from the dark-theme surface, and is
capped at eight; past eight, direct labelling or faceting is the right answer, not a ninth
colour.

Importing `ggstyle` never mutates `rcParams`. Theming is always something you ask for.

Almost all of it is plain rcParams in a `.mplstyle` file, including spine removal
(`axes.spines.left: False`), which an earlier draft of the design wrongly assumed needed
Python. Facet-strip styling has no core matplotlib equivalent, and transparent axis
labels in `void` may still reserve layout space.

## Data frames

pandas and polars both work, as do pyarrow arrays, numpy `datetime64`, and plain lists:

```python
gs.dates(ax, data=frame["date"])     # pandas Series, polars Series, or Index
```

Polars is detected by module name rather than imported, so installing `ggstyle` never
pulls it in and pandas-only users pay nothing for the support. Timezone-aware input from
either library is converted to UTC instants for positioning; display timezones stay a
separate concern handled by `.tz()`.

Two things are deliberately *not* guessed: a whole DataFrame passed where a column was
meant, and a string column that might be dates. Both raise.

Missing values in explicit date data also raise unless exclusion is requested with
``missing="drop"``. The number excluded remains available through ``.summary()`` and in
generated captions.

## Multiple panels

Synchronize comparable axes with a live observation registry and common limits:

```python
handles = gs.sync_dates(axes, mode="collapse", limits="union")
```

This prevents the same date from receiving different ordinal positions in independently
collapsed panels. The handles share one revisioned registry: calling `.refresh()` on any
member rescans every live member and updates every collapsed scale transactionally.

Call `.refresh()` after adding, changing, or removing plotted artists. A repeated
`gs.dates(ax)` call also refreshes an existing handle. Call `.dispose()` to disconnect a
handle and release its registry and managed-artist references without removing artists
from the Matplotlib axes.

## Design rules

- The date axis is a standalone object, not a side effect of plotting.
- Importing the package is inert; theming is opt-in.
- Placement, labels, gridline cadence, and range are four independent knobs.
- Fail loudly: a non-date axis raises, and mixed tz-aware/naive input raises rather than
  guessing UTC.
- Never resample or interpolate the data silently.
- Never rotate tick labels by default. Rotation is a symptom of bad tick selection.

## Known limits

- Collapsed mode supports lines, `scatter`, `fill_between`, and native data-space or
  x-data blended transforms without rewriting their geometry. Lines, scatter collections,
  and native `fill_between` polygons contribute observations automatically. Because
  Matplotlib does not retain the source x array for `step="mid"`, that form still requires
  the complete dates through `gs.dates(ax, data=dates)`.
- Data artists with custom x transforms are rejected during refresh; use `ax.transData`
  because explicit dates cannot make a non-data transform safe.
- Unsupported or ambiguous date-bearing artists raise `DateDiscoveryError` during
  preflight. Version 0.5 retains the strict policy and has no permissive warning mode.
- `.tz()` assumes naive data is UTC when converting for display.
- `line()`, `points()`, and `ribbon()` share mappings, and `guides()` derives legends and
  colorbars from them. Automatic guide placement supports at most four distinct legends
  and four distinct colorbars per axes. Numeric color must be constant within a resolved
  line or ribbon because each native artist has one color; points map color per
  observation.
- The current `finish()` surface coordinates plot, subtitle, caption, axis-title,
  numeric-label formatting, safe existing-axes theming, and direct labels for ordinary
  Cartesian `Line2D` series. General label repulsion, scatter endpoint labels, and guide
  layout remain later work; filesystem export is intentionally separate in `save()`.

## Tests

```bash
python -m pytest -q
ruff check .
mypy
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete development workflow and
[SECURITY.md](SECURITY.md) for vulnerability reporting.

The executable publication and nine-theme figures are in the
[documentation gallery](docs/source/gallery.rst); regenerate their reviewed assets with
`python tools/validate_gallery.py --write`. The complete HTML documentation is published
through [GitHub Pages](https://joshuamyers22.github.io/ggstyle/).

The structured documentation follows the same user-guide, API-reference, pitfalls, and
release-note separation used by statsmodels. Build it locally with:

```bash
pip install -e ".[docs]"
python -m sphinx -W --keep-going -b html docs/source docs/build/html
```
