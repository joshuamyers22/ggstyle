# ggstyle — a ggplot2-flavored plotting layer for Python

> Name settled: `ggstyle`.

> Status (2026-08-19): the public `0.1.0` release contains the standalone date axis and
> themes, structured axis summaries, explicit missing-date handling, generated captions,
> and multi-panel date synchronization. The `line()`, palette, formatter, label, and save
> APIs below remain roadmap items for `0.1b` or later.

## 1. Goal

Make it easy to produce plots in Python that look like well-made ggplot2 output, without
fighting matplotlib defaults and without giving up matplotlib's escape hatches.

**v0.1 scope: line plots with a date x-axis.** Everything else is deferred.

### Non-goals

- Re-implementing the grammar of graphics. `plotnine` and `lets-plot` already do this.
- Replacing matplotlib. This is a layer *on top of* it.
- Interactive/web output. Static figures for notebooks, papers, and reports.
- Supporting every plot type. Depth on a few, not breadth on many.

## 2. Positioning

`plotnine` gives you the ggplot2 *grammar*; it does not give you the ggplot2 *craft* —
sensible date ticks, direct labels instead of legends, restrained palettes, titles that
sit where they should. Most of the pain in Python plotting is in that second category.

So: a thin, opinionated wrapper over matplotlib that encodes good defaults, plus a
stylesheet that anyone can use standalone.

**Litmus test for scope:** if a feature can be expressed as an rcParam, it belongs in the
stylesheet, not in Python.

## 3. Design principles

0. **The date axis is the product.** When a design choice trades off date-axis ergonomics
   against anything else, date-axis ergonomics wins. See [§6](#6-the-date-axis--the-center-of-the-project).
1. **Always return `(Figure, Axes)`.** The moment a wrapper hides matplotlib, it becomes
   useless for the one plot that needs customizing. Convenience on top, escape hatch
   underneath, always.
2. **Tidy/long data is the contract.** Accept wide frames through an explicit shim, not by
   guessing. pandas and polars are equal citizens; neither is imported eagerly.
3. **No hidden global state.** Theming is opt-in via a context manager or explicit call —
   importing the package must not mutate `rcParams`.
4. **Defaults are opinions, and they are documented.** Every default that differs from
   matplotlib gets a one-line rationale in the docs.
5. **Fail loudly on ambiguous input.** Silent coercion of a string column to dates is a bug
   factory.

## 4. Repository layout

```
ggstyle/
  pyproject.toml
  README.md
  src/ggstyle/
    __init__.py
    themes/
      ggstyle-minimal.mplstyle  # white panel, grey grid, no spines  (DEFAULT)
      ggstyle-grey.mplstyle     # grey panel, white grid  (theme_grey analogue)
    theme.py                  # use_theme(), theme() context manager
    _frames.py                # pandas / polars / arrow / numpy date extraction
    _parse.py                 # partial date strings, offset alias normalization
    _cadence.py               # Cadence spec, auto-cadence table
    _formats.py               # tick label presets, concise labeller
    palettes.py               # discrete + sequential scales           (v0.1b)
    text.py                   # richtext(), textbox(), enrich()        (v0.4)
    _richtext/                # the gridtext analogue -- see §11       (v0.4)
    dates.py                  # the DateAxis handle
    formats.py                # dollar/percent/comma/SI tick formatters (v0.1b)
    labels.py                 # direct end-of-line labeling             (v0.2)
    plots/
      __init__.py
      line.py
    facets.py                 # v0.2
    save.py
  tests/
    test_dates.py
    test_line.py
    test_theme.py
    baseline/                 # small set of pytest-mpl reference images
  examples/
    quickstart.ipynb
```

`src/` layout, matching `binspect`.

## 5. Planned convenience API (v0.1b)

```python
import ggstyle as gs

fig, ax = gs.line(
    df,                       # tidy/long DataFrame
    x="date",
    y="close",
    color="ticker",           # optional grouping column
    title="Closing prices",
    subtitle="Daily, split-adjusted",
    caption="Source: ...",
    y_format="dollar",        # "percent" | "comma" | "si" | callable | None
    labels="end",             # "end" | "legend" | None
    gaps="show",              # "show" | "collapse"
    ax=None,                  # draw into an existing Axes
)

gs.save(fig, "prices.png")    # sane dpi, tight bbox, no surprises
```

Supporting surface:

```python
gs.use_theme("bw")                       # sets rcParams process-wide
with gs.theme("grey"):  ...              # scoped, restores on exit
gs.palette("muted")                      # returns list of hex colors
gs.line(df, wide=True, x="date")         # melts internally; all other cols become series

gs.dates(ax)                             # date-axis handle for ANY Axes — see §6
```

The `gs.dates(ax)` accessor is the load-bearing piece of the API. `line()` is a convenience
shell around it, and the accessor must be equally usable on a plot this package never
touched.

### Signature rules

- `x`, `y`, `color` are **column names**, never arrays. One input contract, no branching.
- `ax=None` creates a figure; passing an `Axes` draws into it. This is what makes the
  package composable with subplot grids and with `binspect`.
- Anything not covered by a keyword is done by the caller on the returned `ax`.

## 6. The date axis — the center of the project

**This is the primary requirement, not a feature of `line()`.** Everything else in the
package exists to support it. Two consequences follow, and they shape the architecture:

1. **The date axis is a standalone object, not a side effect of plotting.** It must work on
   *any* matplotlib Axes, including ones this package didn't create. `gs.line()` calls it
   internally; it is not the other way around.
2. **The zero-config path must be excellent, and every part of it must be overridable
   independently.** Tick placement, tick labels, gridline cadence, and axis range are four
   separate concerns. Matplotlib conflates them; ggplot2 doesn't; neither should we.

### 6.1 The handle

```python
gs.dates(ax)     # returns a DateAxis handle for that Axes, creating or adopting it
```

Adoption is the point: it works on a plot made by seaborn, by pandas `.plot()`, or by raw
matplotlib. That makes the date axis useful on day one, independently of the rest of the
package. All methods are chainable and return the handle.

```python
gs.dates(ax) \
  .ticks("quarterly") \
  .fmt("month-year") \
  .zoom("2020-03", "2021-06") \
  .span("2020-02-19", "2020-03-23", label="drawdown")
```

### 6.2 Tick placement

```python
.ticks("auto")                       # default, see cadence table below
.ticks("monthly")                    # daily | weekly | monthly | quarterly | yearly
.ticks(every="3M")                   # any pandas offset alias
.ticks(n=6)                          # ~6 ticks, snapped to a natural cadence
.ticks(at=["2020-01-01", "2021-07-01"])   # explicit
.ticks(major="yearly", minor="monthly")   # two levels at once
.ticks("quarter-end")                # snap to period ends, not starts
```

Snapping matters more than it looks: month-start vs. month-end ticks on financial data
is the difference between labels that line up with the observations and labels that float
between them.

### 6.3 Tick labels — separate from placement

```python
.fmt("concise")        # default: shortest unambiguous form, year shown once
.fmt("month-year")     # Jan 2024
.fmt("month")          # Jan
.fmt("year")           # 2024
.fmt("quarter")        # Q1 2024
.fmt("iso")            # 2024-01-15
.fmt("%b '%y")         # any strftime string
.fmt(lambda d: ...)    # any callable
.fmt(major="year", minor="month")
```

Named presets cover ~95% of uses so nobody has to remember `%b`; strftime and callables
cover the rest. Changing the format never changes where ticks land.

### 6.4 Range

Partial-string parsing throughout, with pandas semantics — `"2020"` means the whole year,
`"2020-03"` means the whole month:

```python
.zoom("2020", "2022")          # inclusive of both whole periods
.zoom("2020-03", None)         # open-ended
.zoom(last="6M")               # trailing window from the last observation
.zoom(ytd=True)
.pad(left="1M", right="1M")    # breathing room without changing the data
```

### 6.5 Gaps

`gaps="collapse"` is defined by **the dates observed in the data**, not by a holiday
calendar. Any date not present is simply not allocated space. This is calendar-free,
correct by construction for any market or region, and adds no dependency. With multiple
series, the axis uses the union of observed dates.

| | |
|---|---|
| `gaps="show"` | True datetime axis; weekends and holidays appear as gaps |
| `gaps="collapse"` | Observation-ordinal axis with date labels; no gaps |
| Default | `"show"` for daily-or-coarser, `"collapse"` for intraday |
| Switch after the fact | `.collapse()` / `.expand()` |

Frequency inference for the default: `pandas.infer_freq` where possible, median
inter-observation delta as fallback, explicit kwarg always wins.

### 6.6 Closing the collapse leak

In collapsed mode the axis is ordinal, so a caller's `ax.axvline(pd.Timestamp("2020-03-23"))`
lands in the wrong place. This is the one real hazard in the design, and the handle exists
partly to close it. Every date-space operation goes through the handle and works
identically in both modes:

```python
.loc("2020-03-23")                       # → float x position (the primitive)
.vline("2020-03-23", label="trough")
.span("2020-02-19", "2020-03-23", label="drawdown")
.spans(events_df, start="begin", end="end")   # many at once
.grid("yearly")                          # gridline cadence, independent of ticks
```

`.loc()` is the escape hatch: given it, a caller can do anything in raw matplotlib and stay
correct. Dates falling inside a collapsed gap snap to the nearest observation, and
`.loc(..., strict=True)` raises instead.

**v0.2 refinement:** implement a custom monotone piecewise-linear `matplotlib.scale` for
collapsed mode, registered via `register_scale`. That makes *native* calls
(`ax.axvline(timestamp)`, `ax.set_xlim(dates)`) work without the handle. It's the elegant
answer, but it's real transform work — the handle ships first and does not become wasted
effort, since `.zoom()`/`.ticks()` are wanted regardless.

### 6.7 Auto-cadence table

The zero-config path, and a directly testable spec:

| Span | Major | Minor | Format |
|---|---|---|---|
| < 1 day | hours | 15 min | `14:30` |
| 1–7 days | days | 6 hours | `Mon 3` |
| 1–3 months | weeks | days | `Mar 3` |
| 3–18 months | months | weeks | `Jan`, year offset below |
| 18 months – 5 years | quarters | months | `Q1 2024` |
| 5–15 years | years | quarters | `2024` |
| > 15 years | 5-year | years | `2020` |

### 6.8 Standing rules

- **Never rotate tick labels by default.** Rotation is a symptom of bad tick selection; fix
  the ticks. `.rotate(45)` exists for when the caller insists.
- **Year boundaries** get a major tick with the year offset below the axis, not repeated on
  every label.
- **Timezone:** require consistently tz-aware or tz-naive input; raise on mixed. Never guess
  UTC. `.tz("America/New_York")` changes display only, never the underlying data.
- **Irregular sampling:** plot as-is. Never resample or interpolate silently.
- **Non-date columns** passed as `x` raise immediately with a clear message rather than
  being coerced.

## 7. Theming

Encode in `.mplstyle` (no Python needed):

- Figure and axes background, panel color
- Grid color, linewidth, `axes.axisbelow: True` (gridlines behind data — matplotlib gets
  this wrong often enough to be worth stating)
- Font family and the full size ladder (title / subtitle / axis label / tick / caption)
- Tick direction and length, `xtick.top: False`, `ytick.right: False`
- Default color cycle from `palettes.py`
- Legend frame off, `savefig.dpi`, `savefig.bbox: tight`

Requires Python (can't be an rcParam):

- Removing top/right spines per-Axes
- Left-aligned title + subtitle stacked above the panel (matplotlib centers over the axes;
  ggplot2's convention is left-aligned to the panel edge)
- Caption in the lower-left below the panel
- Direct end-of-line labels with collision avoidance
- Facet strip labels and shared-axis logic (v0.2)

### Palettes

Ship three discrete palettes (muted / bright / grey-scale) and two sequential ones. All
checked against deuteranopia and protanopia simulation. Cap the discrete cycle at 8 — past
that, direct labeling or faceting is the right answer, not a ninth color, and the docs
should say so.

## 8. Testing

Pixel-diff tests are brittle across matplotlib versions and OS font stacks, so they are the
smoke test, not the suite.

**Primary — the date axis, tested hardest:**
- **Cadence table as a parametrized test.** Every row of §6.7 becomes a case: construct a
  series of that span, assert the resulting major/minor cadence and format. ~20 spans,
  including the boundaries on either side of each threshold.
- `.loc(date)` returns the same *visual* position in `"show"` and `"collapse"` mode for any
  date present in the data — the invariant that keeps annotations honest.
- `.vline()` / `.span()` land on the correct position in both modes.
- Dates inside a collapsed gap snap to the nearest observation; `strict=True` raises.
- Partial-string parsing: `"2020"` → whole year bounds, `"2020-03"` → whole month bounds.
- `.zoom(last="6M")` measures from the last observation, not from today.
- Every named `.fmt()` preset produces expected output for a fixed set of dates.
- Changing `.fmt()` does not move tick locations; changing `.ticks()` does not change label
  format. Orthogonality is a test, not a hope.
- Mixed tz-aware/naive input raises; `.tz()` changes labels without changing data.
- Multi-series collapse uses the union of observed dates.

**Also — general artist properties:**
- number of `Line2D` objects and their colors for a known grouping
- formatter output for known values (`0.0525 → "5.25%"`, `1_200_000 → "$1.2M"`)
- spine visibility, grid z-order, title alignment after theming
- theme context manager restores `rcParams` exactly on exit

**Secondary — `pytest-mpl` baselines:** ~5 reference images, one per theme plus one facet
grid, pinned to a single matplotlib version in CI.

**Property test:** any DataFrame with a valid date column and numeric y should produce a
figure without raising. Hypothesis for the input generation.

## 9. Packaging and CI

- `pyproject.toml`, hatchling, `src/` layout, version in `__init__.py` via
  `importlib.metadata`
- Dependencies: `matplotlib`, `pandas`, `numpy`. Nothing else — a plotting convenience
  package that drags in a solver is a package people route around. polars is supported
  but never required: the frame adapter detects it by module name
- Python 3.10+
- ruff + mypy (strict on `src/`, lenient on `tests/`)
- GitHub Actions: test matrix on 3.10–3.13, lint, and a docs build
- Docs: mkdocs-material with a gallery page where every image is generated at build time
  from the example code — a stale gallery is worse than no gallery

## 10. Milestones

**v0.1 — The date axis, plus themes** *(built)*
`gs.dates(ax)` with the full §6 surface: adoption of foreign Axes, ticks, fmt, zoom, gaps,
`.loc`/`.vline`/`.span`/`.grid`, auto-cadence. Frame adapter for pandas and polars. Two
stylesheets with `use_theme`/`theme`. Structured `AxisSummary`, generated semantic
captions, explicit missing-date policy, and `sync_dates()` for comparable panels.
*Done when:* it improves a plot made by raw `ax.plot()` or pandas `.plot()` with a single
call, and the §6.7 cadence table passes end to end. ✓

**Post-v0.1 — Line plots**
`line()`, tick value formatters (dollar/percent/comma/SI), `save()`, palettes module,
README gallery.
*Done when:* a daily price series and an intraday series both render publication-ready with
no post-hoc matplotlib calls.

**v0.2 — Facets and direct labels**
`facet="col"` with wrapped grids, shared/free axes, strip labels. End-of-line labeling with
collision avoidance. Build on `sync_dates()` rather than adding separate grouped plotting
functions.
*Done when:* a 12-panel facet grid of tickers renders with readable strips and no
overlapping labels.

**v0.3 — More geoms**
`area()`, `step()`, `ribbon()` (confidence/prediction bands), `scatter()`. Same signature
shape as `line()`. `ribbon()` accepts explicit lower and upper columns and a caller-supplied
interval label; it does not fit a model or infer the statistical meaning of the bounds.
Collapsed-mode support is blocked until collection remapping is correct.

**v0.4 — Rich text (`ggtext` port)**
`_richtext` parse/measure/layout/draw, then `richtext()`, `textbox()`, `enrich()`,
`rich_ticks()`, and inline images. See §11 for the full design.
*Done when:* a title with mixed styling, a wrapped caption box, and an axis label
containing an inline image all survive `savefig(bbox_inches="tight")` unclipped on both
Agg and SVG.

**v0.5 — Shared identity with `binspect`**
Extract the theme + palette layer so `binspect`'s viz module imports it rather than
duplicating. Decide whether that's a dependency or a vendored stylesheet.

## 11. Rich text — porting `ggtext`

### What is actually being ported

R splits this across two packages, and the port should keep the split:

| R package | Does | Python home |
|---|---|---|
| `gridtext` | Parses Markdown/HTML, lays out a box model, renders grobs | `ggstyle/_richtext/` |
| `ggtext` | ggplot2 integration: `element_markdown()`, `element_textbox()`, `geom_richtext()`, `geom_textbox()` | `ggstyle/text.py` |

Almost all the hard work is `gridtext`. `ggtext` is a thin adapter, and its Python
equivalent will be thinner still — see §11.5 on why the theme-element half doesn't
translate directly.

### 11.1 Prior art, honestly

Two Python packages already occupy part of this ground:

- **`flexitext`** — explicitly inspired by `ggtext`. It draws styled runs with a tag syntax
  of its own (`<weight:bold, size:24>...</>`) rather than Markdown or HTML, and it
  deliberately isn't HTML/CSS. Nested tags work. No word wrap, no textboxes, no images, no
  axis-label integration. Low release activity.
- **`highlight_text`** — same goal, styles passed as a separate list of dicts rather than
  inline in the string; it does more with bounding boxes and path effects on the
  highlighted spans.

So the inline-styled-runs problem is solved twice over. **Do not rebuild that.** What
neither does, and what makes `ggtext` worth porting:

1. **Markdown and real HTML subset** rather than a bespoke tag dialect.
2. **Word-wrapping textboxes** with padding, margins, background, and border — the
   `element_textbox_simple()` / `geom_textbox()` half.
3. **Inline images** (`<img>`) sized in `em`, which is what drives most `ggtext` adoption:
   logos or icons in axis labels and facet strips.
4. **Integration with axis machinery**, so a tick label or title *is* rich text rather than
   a separately-placed artist.

If those four aren't wanted, the correct plan is "depend on `flexitext`" and this section
should be deleted.

### 11.2 The constraint everything else follows from

**Matplotlib cannot measure text without a renderer.** `get_text_width_height_descent`
needs one, and a renderer only exists during a draw. Therefore:

- Layout happens in `draw()`, not at construction. The artist stores parsed runs and
  re-lays them out each draw.
- `get_window_extent()` must also work, because `savefig(bbox_inches="tight")`,
  `tight_layout`, and `constrained_layout` all call it — sometimes before a full draw. This
  is the single most common way a custom text artist ends up clipped in saved output.
- Layout caches key on `(dpi, backend, available width, font state)`. Any change
  invalidates. Metrics differ between Agg, PDF, and SVG, so a cache that crosses backends
  produces subtly wrong wrapping in saved files.

`gridtext` reaches the same conclusion in R for the same reason; this is not a matplotlib
quirk to engineer around.

### 11.3 Layout

```
src/ggstyle/_richtext/
  parse.py      # markup -> run tree
  model.py      # Run, Line, Block dataclasses; style inheritance
  measure.py    # renderer-backed metrics, cached per (dpi, backend)
  layout.py     # line breaking, baseline alignment, the box model
  images.py     # <img> loading, em-sizing, DPI-correct placement
  draw.py       # emit matplotlib primitives
```

The pipeline, once per draw:

1. **Parse** (cached; input string rarely changes) into a tree of runs, each carrying an
   inherited style: family, size, weight, style, colour, baseline shift.
2. **Split runs at word boundaries.** A bold phrase containing spaces must be able to break
   across lines while staying bold — so the breaking unit is the word, not the run.
3. **Measure** every word once per layout pass, via the renderer.
4. **Break lines** greedily against the available width. No width → single line.
5. **Align baselines.** Line height is `max(ascent) + max(descent)`, scaled by line spacing.
   Superscript and subscript shift the baseline by a fraction of the *parent* size and
   shrink the run.
6. **Position** the block according to horizontal/vertical alignment, then padding, then
   margin, then the background patch.
7. **Draw** each run as a `Text` primitive at its computed position; images as `BboxImage`.

### 11.4 Markup subset

Scoping this is the decision that determines whether the port is finishable.

**In:** `**bold**`, `*italic*`, `` `code` ``, `<b>`, `<i>`, `<br>`, `<sup>`, `<sub>`,
`<span style="color:...; font-size:...; font-family:...; font-weight:...">`, `<img src=...
width=... height=...>`, and HTML entities.

**Out:** tables, lists, block quotes, nested block elements, links (no click target in a
static image — render the label text and drop the href), arbitrary CSS, and full
CommonMark. A hand-written parser over this subset is a few hundred lines; pulling in a
full Markdown engine buys features that then have to be *rejected* at layout time.

Where Markdown and the HTML subset disagree, HTML wins — it's the escape hatch.

### 11.5 The `ggtext` half doesn't translate directly

In R you swap a theme slot: `theme(axis.text.x = element_markdown())`. Matplotlib has no
theme-element system, and `Tick.label1` must be a `Text` instance, so a rich artist cannot
simply be assigned into it.

The matplotlib-shaped equivalent is imperative:

```python
gs.richtext(ax, x, y, "**Fed funds** vs *SOFR*")     # geom_richtext analogue
gs.textbox(ax, x, y, long_text, width=0.4)           # geom_textbox analogue, wraps
gs.enrich(ax)                                        # element_markdown analogue
gs.rich_ticks(ax, axis="x")                          # markup in tick labels
```

`enrich(ax)` walks the title, axis labels, tick labels, and legend entries, and upgrades
any whose text contains markup — leaving plain strings alone so it is safe to call
unconditionally.

For tick labels specifically: hide the native labels and manage our own artists positioned
in the axis transform, re-placed whenever the ticks move. **`DateAxis._refresh()` already
does exactly this bookkeeping**, so rich tick labels hook the existing refresh path rather
than inventing a second one. That synergy is the main argument for rich text living in this
package rather than being a separate project.

### 11.6 Traps worth writing down now

- **Rotation** applies to the assembled block, not per run. Rotating each run individually
  is the obvious wrong implementation and looks fine until the text isn't horizontal.
- **Missing font faces.** Many families ship no bold-italic. Define the fallback order
  (synthesise italic? fall back to bold?) and warn once per family, not once per run.
- **Images in vector backends.** A rasterised logo in an SVG or PDF needs deliberate
  handling; decide whether `<img>` embeds or rasterises, and at what DPI.
- **`constrained_layout`** will clip titles if `get_window_extent` is even slightly wrong.
  Test it explicitly rather than eyeballing one figure.
- **Empty and whitespace-only markup**, unclosed tags, and unknown tags all need defined
  behaviour. Prefer rendering the text literally over raising, since these strings often
  come from data.

### 11.7 Testing

The font-dependence problem is solved with a **stub renderer** that reports deterministic
metrics — a fixed advance width per character, fixed ascent and descent. Line breaking,
baseline alignment, and the box model then become exactly testable with no font on the
machine mattering:

- **Parser tests** (pure, fast, the bulk): markup in, run tree out. Nesting, style
  inheritance, malformed input.
- **Layout tests** against the stub renderer: given known widths, assert which words land
  on which line, and where baselines sit.
- **Integration tests**: `get_window_extent` matches the drawn extent; `bbox_inches="tight"`
  doesn't clip; a dpi change re-wraps; Agg and SVG agree on line count.
- **Baseline images**: a handful only, same policy as the rest of the suite.

## 12. Decisions

### Settled

1. **Name: `ggstyle`.** Kept. Check PyPI availability before publishing.
2. **Polars support: in from the start.** Handled by a duck-typed frame adapter
   (`_frames.py`) that detects polars by module name rather than importing it, so
   installing `ggstyle` never pulls polars in and pandas-only users pay nothing. pyarrow
   arrays, numpy `datetime64`, and plain sequences come along for free. Narwhals was not
   needed — the only ingress point is date extraction, so an adapter beats a dependency.
3. **Themes: `minimal` is the default, `grey` is second.** `bw` is dropped for now; it sits
   close enough to `minimal` that it wasn't earning its slot. Both shipped themes share one
   type scale and colour cycle, so switching changes the panel surface and nothing else.
4. **Collapsed positions interpolate rather than snap.** The piecewise-linear mapping turned
   out to be a few lines of `np.interp`, so it landed in v0.1 instead of v0.2. Snapping
   survives as `loc(date, snap=True)`; `strict=True` raises.
5. **Spine removal is an rcParam.** `axes.spines.left: False` exists, so it belongs in the
   stylesheet, not in Python. The original §7 split was wrong about this.

### Still open

6. **Function calls vs. chaining** for the eventual plotting layer: `gs.line(df, ...)` vs.
   `gs.plot(df).line().facet()`. Start with functions; add chaining only if layering
   pressure actually shows up.
7. **Custom scale for collapsed mode (§6.6).** Registering a piecewise-linear date scale
   would make native `ax.axvline(timestamp)` work without the handle. Now the *only*
   remaining v0.2 item from §6.6, since interpolation already shipped.
8. **`binspect` relationship.** Shared dependency (one source of truth, coupled release
   cadence) vs. vendored stylesheet (decoupled, drifts over time).
9. **Package split.** If the date axis earns users standalone, does it become its own
   package that the plotting layer depends on? One package is simpler; two makes the axis
   adoptable by people who don't want a theming opinion. `_richtext` raises the same
   question a second time — it is useful to any matplotlib user, `ggstyle` or not.
10. **Build rich text or depend on `flexitext`?** (§11.1) Justified only by the four gaps:
    Markdown/HTML, wrapping textboxes, inline images, axis integration. Drop any of those
    from the requirements and depending on `flexitext` becomes the better answer.
11. **Markdown parser: hand-written or a dependency?** A hand-written parser over the §11.4
    subset is a few hundred lines and rejects nothing at layout time. A full CommonMark
    engine is less code to own but produces constructs the layout has to refuse.
