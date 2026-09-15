# ggstyle

A date axis for matplotlib that is easy to use and easy to manipulate.

**v0.2 is the date axis plus the complete built-in ggplot2-inspired theme set.** No
palettes module and no `line()` yet — those remain future additions once the axis
ergonomics have real usage behind them.

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

Available names are `minimal`, `grey`, `bw`, `linedraw`, `light`, `dark`, `classic`,
`void`, and `test`. The corresponding ggplot2 function spellings, such as `theme_bw` and
`theme_classic`, are accepted as aliases. `test` is intended for stable visual tests,
while `void` removes the plotting surface for maps and other annotation-free displays.

All themes spell out the same type scale and colour cycle, so switching changes the
non-data surface rather than the plot's identity. The colour cycle is Okabe–Ito-derived
and capped at eight; past eight, direct labelling or faceting is the right answer, not a
ninth colour.

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
  or provide the complete observation registry explicitly.
- `.tz()` assumes naive data is UTC when converting for display.
- No palettes module yet: the colour cycle lives in the stylesheets.

## Tests

```bash
python -m pytest -q
ruff check .
mypy src
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete development workflow and
[SECURITY.md](SECURITY.md) for vulnerability reporting.

The structured documentation follows the same user-guide, API-reference, pitfalls, and
release-note separation used by statsmodels. Build it locally with:

```bash
pip install -e ".[docs]"
python -m sphinx -W --keep-going -b html docs/source docs/build/html
```
