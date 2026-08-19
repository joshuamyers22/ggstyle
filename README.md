# ggstyle

A date axis for matplotlib that is easy to use and easy to manipulate.

**v0.1a is the date axis plus themes.** No palettes module and no `line()` yet — those
come in v0.1b, once the axis ergonomics have real usage behind them.

This is a public alpha. The date-axis behavior is tested, but the API may change before
the first stable release. See the [known limits](#known-limits-in-v01a) before using
collapsed mode in production.

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

Every method returns the handle, so calls chain.

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
.loc("2020-03-23")                    # -> axis position; the escape-hatch primitive
.vline("2020-03-23", label="trough")
.span("2020-02-19", "2020-03-23", label="drawdown")
.spans(events_df, start="begin", end="end", label="name")
.grid("yearly")                       # gridline cadence, independent of ticks
```

In collapsed mode a date that falls inside a gap (a Sunday, a holiday) is placed by linear
interpolation between its neighbours. `loc(date, snap=True)` rounds to the nearest
observation instead; `loc(date, strict=True)` raises if the date was never observed.

### Escape hatch

`.loc()` is the primitive that keeps raw matplotlib correct:

```python
handle = gs.dates(ax).collapse()
ax.axvline(handle.loc("2020-03-23"))   # lands in the right place
ax.set_xlim(handle.loc("2020-01"), handle.loc("2021-01"))
```

## Themes

Two ship. `minimal` is the default; `grey` is the ggplot2 `theme_grey` analogue.

```python
gs.use_theme()             # minimal, process-wide
gs.use_theme("grey")       # "gray" also accepted

with gs.theme("grey"):     # scoped; restores every rcParam on exit
    ...

plt.style.use(gs.stylesheet())   # the .mplstyle on its own, no ggstyle import needed
```

Both spell out the same type scale, colour cycle, and layout, so switching changes the
panel surface and nothing else — the same separation ggplot2 makes. The colour cycle is
Okabe–Ito-derived and capped at eight; past eight, direct labelling or faceting is the
right answer, not a ninth colour.

Importing `ggstyle` never mutates `rcParams`. Theming is always something you ask for.

Almost all of it is plain rcParams in a `.mplstyle` file, including spine removal
(`axes.spines.left: False`), which an earlier draft of the design wrongly assumed needed
Python.

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

## Design rules

- The date axis is a standalone object, not a side effect of plotting.
- Importing the package is inert; theming is opt-in.
- Placement, labels, gridline cadence, and range are four independent knobs.
- Fail loudly: a non-date axis raises, and mixed tz-aware/naive input raises rather than
  guessing UTC.
- Never resample or interpolate the data silently.
- Never rotate tick labels by default. Rotation is a symptom of bad tick selection.

## Known limits in v0.1a

- Collapsed mode remaps `Line2D` artists only. Collections (`fill_between`, `scatter`) are
  not yet remapped; annotate through the handle instead.
- Native `ax.axvline(timestamp)` is still wrong in collapsed mode — go through `.loc()`.
  A registered matplotlib scale would remove that caveat and is the v0.2 candidate.
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
