User guide
==========

.. _semantic-lines:

Semantic lines
--------------

:func:`ggstyle.line` draws named tidy-data columns on a caller-owned Matplotlib axes:

.. code-block:: python

   result = gs.line(
       frame,
       x="date",
       y="value",
       color="series",
       linestyle="status",
       style={"linewidth": 2},
       sort="x",
       ax=ax,
   )

``color=`` and ``linestyle=`` are column mappings. Fixed Matplotlib properties belong in
the separate ``style=`` mapping; supplying a mapped aesthetic there is an error before
the axes changes. The result retains the exact axes, ordinary ``Line2D`` artists, and
read-only trained scales through :class:`ggstyle.LineResult`.

Categorical color and linestyle imply grouping. ``group=`` partitions lines without
assigning an aesthetic and may be combined with those mappings. Numeric color is
continuous; because a ``Line2D`` has one color, that value must be constant inside every
resolved line. Use an explicit group column when several constant-valued lines share one
continuous mapping. Boolean and pandas categorical color remain discrete.

The default ``sort="input"`` preserves row order. ``sort="x"`` stably orders each line
by x; duplicate positions retain input order and are never aggregated. Missing explicit
group values use the visible ``group_missing=`` policy: ``"drop"`` (default), ``"keep"``,
or ``"raise"``. Dropped rows and accessibility warnings appear in
``result.diagnostics``.

Default inference can be overridden with immutable scale policy:

.. code-block:: python

   result = gs.line(
       frame,
       x="date",
       y="value",
       color="code",
       color_scale=gs.DiscreteScale(
           order=(1, 2, 3),
           values=("#0072B2", "#D55E00", "#009E73"),
           missing="drop",
           name="Series",
       ),
       ax=ax,
   )

Use :class:`ggstyle.ContinuousScale` with a sequential or diverging
:class:`ggstyle.Palette` to set explicit limits and missing/infinite policy. A
:class:`ggstyle.DiscreteScale` is aesthetic-independent until applied, so custom values
must be hexadecimal colors for ``color_scale=`` or one of the supported named line
styles for ``linestyle_scale=``.

Scales are shared by aesthetic and source-column name across calls on one axes. Discrete
assignments remain stable as levels are added. Expanding an automatic continuous domain
recolors earlier lines managed by this helper so all participating layers remain
consistent. Calls sharing a mapping must therefore use the same explicit scale policy;
conflicts fail before drawing. An externally removed complete layer is pruned on the next
mapped call.

The data helpers perform no aggregation, smoothing, interpolation, or axes creation.
They validate scale and grouping policy before drawing and roll back
partial artists, axes state, earlier colors/styles, and registry state if rendering or
date-axis refresh fails. If the axes already has a ggstyle date handle, the handle is
refreshed automatically, including in collapsed mode.

Semantic points and ribbons
----------------------------

:func:`ggstyle.points` reuses the line helper's ``x``, ``y``, ``color``, ``group``,
``color_scale``, and fixed ``style`` vocabulary. Discrete color creates one native
``PathCollection`` per level; continuous color is mapped independently for every point.
The helper does not aggregate or jitter observations.

.. code-block:: python

   points = gs.points(
       frame,
       x="date",
       y="value",
       color="score",
       style={"marker": "o", "size": 32, "edgecolor": "white"},
       ax=ax,
   )

:func:`ggstyle.ribbon` draws caller-provided lower and upper columns with native
``PolyCollection`` artists. It never computes an interval or synthesizes a legend label.
Missing coordinates break a ribbon by default; ``missing="drop"`` explicitly connects
across the gap, while ``missing="raise"`` rejects it. Crossed bounds are allowed unless
``validate_order=True``.

.. code-block:: python

   band = gs.ribbon(
       intervals,
       x="date",
       lower="low",
       upper="high",
       color="series",
       label="95% interval",
       alpha=0.2,
       ax=ax,
   )

Line, point, and ribbon calls on one axes share trained color state when they map the
same source-column name. A later automatic-domain expansion transactionally updates all
earlier managed artists. Continuous ribbon color, like continuous line color, must be
constant within each resolved group.

Automatic semantic guides
-------------------------

Call :func:`ggstyle.guides` after adding semantic layers. It reads the complete trained
registry and returns native Matplotlib legends and colorbars through
:class:`ggstyle.GuideResult`:

.. code-block:: python

   gs.line(frame, x="date", y="value", color="series", ax=ax)
   gs.points(events, x="date", y="value", color="series", ax=ax)
   guide_result = gs.guides(ax)

Discrete mappings create legends; continuous color mappings create colorbars. A scale's
``name=`` becomes its guide title, or the source-column name is used by default. Missing
discrete values mapped by scale policy receive an explicit ``(missing)`` entry, and
requested unobserved levels remain visible.

Color and linestyle guides merge only when they use the same source variable, title,
ordered levels, and missing entry. Different variables or titles stay separate. This is
deliberately stricter than merging guides merely because their displayed labels happen
to match.

Once guide construction is activated, subsequent semantic layer calls refresh the
managed guides after successful scale training. A failed legend or colorbar build leaves
the previous guides, artists, and registry revision unchanged. Repeated calls within one
revision return the same native guide objects. Pass ``enabled=False`` to remove managed
guides and disable live refresh.

Caller-owned legends and colorbars are never replaced or removed. Semantic legends are
available through ``GuideResult.legends`` rather than ``ax.get_legend()``, which remains
reserved for a caller-owned axes legend. Automatic placement is intentionally bounded to
four distinct legends and four distinct colorbars per axes; larger layouts should use
facets or explicit Matplotlib guide construction.

.. _plot-finishing:

Plot finishing
--------------

:func:`ggstyle.finish` applies plot and axis labels to an existing Matplotlib
``Axes`` as one validated transaction. It returns a :class:`ggstyle.FinishResult`
containing the same axes, the native text artists affected by the request, and the
immutable plan that was applied:

.. code-block:: python

   result = gs.finish(
       ax,
       title="Revenue",
       subtitle="Trailing twelve months",
       caption="Source: annual report",
       x=gs.axis(title="Date"),
       y=gs.axis(
           title="Revenue",
           labels=gs.label_currency("$", scale=1_000_000, suffix="M"),
       ),
   )

The :func:`ggstyle.axis` factory returns an immutable :class:`ggstyle.AxisSpec`.
Numeric labellers are installed through the same explicit ``FuncFormatter`` adapter
available as :func:`ggstyle.as_formatter`.

Subtitles follow Matplotlib's active left, centre, or right title location. Captions are
right-aligned beneath the corresponding axes. Both are ordinary ``Text`` artists marked
as participating in layout. If their figure has no layout engine, ``finish`` enables
constrained layout; an existing tight, constrained, or custom engine is preserved.
Multiline outer text contributes its full bounds to constrained layout.

Repeated calls update the same managed subtitle and caption artists. ``None`` leaves a
managed value unchanged, while ``subtitle=False`` or ``caption=False`` removes it. An
empty string clears a standard plot or axis title. If managed text was removed through
Matplotlib directly, a later explicit value creates a safe replacement.

Pass ``dry_run=True`` to receive a :class:`ggstyle.FinishPlan` without drawing a canvas
or changing axes, artists, layout, or global ``rcParams``. Commit failures restore label
text, formatters, managed artists, and layout state. Data artist coordinates, transforms,
labels, and colours are never changed.

Use :meth:`ggstyle.FinishPlan.as_dict` for a fresh JSON-compatible representation or
:meth:`ggstyle.FinishPlan.describe` for deterministic formatted JSON. Both include nested
policy and diagnostics without retaining artists or callables; see :doc:`inspection`.

The coordinator also accepts a theme recipe; see :ref:`parameterized-themes` for the
existing-axes safety boundary. Saving is deliberately separate through
:func:`ggstyle.save`. Endpoint labels are an explicit finishing policy rather than
unvalidated keyword forwarding.

.. _direct-endpoint-labels:

Direct endpoint labels
----------------------

For labelled line series, :func:`ggstyle.end_labels` replaces legend lookup with labels
anchored to the final finite data point:

.. code-block:: python

   ax.plot(period, revenue, label="Revenue")
   ax.plot(period, forecast, label="Forecast")

   result = gs.finish(
       ax,
       direct_labels=gs.end_labels(collision="avoid", fallback="legend"),
   )

Each annotation is an ordinary Matplotlib ``Annotation`` in ``result.artists``. Its data
anchor remains the endpoint, its text uses the line colour, and only a display-space
vertical offset is used to separate nearby labels. The annotations participate in
constrained layout so the figure allocates a right margin. A successful direct-label
operation removes the axes legend without changing line data, transforms, labels, or
colours.

Participation follows Matplotlib's public legend labels: labels beginning with an
underscore are ignored. Every visible participant must be an ordinary ``Line2D`` on a
rectilinear axes using that axes' data transform, with a finite endpoint inside the
current view. Mixed line/scatter plots therefore do not receive partial direct labels.
If any participant is unsupported, an endpoint is outside the view, or all labels cannot
fit vertically, ``fallback="legend"`` creates a conventional legend for the complete
set. ``fallback="raise"`` instead fails during preflight before any finishing mutation.

``collision="none"`` leaves every text offset at the exact endpoint height.
``direct_labels=False`` removes endpoint annotations previously managed by ``finish``;
``None`` leaves them unchanged. Repeating an explicit request updates and reuses attached
annotations. Call ``finish`` again after changing the participating lines. Dry runs
perform the same eligibility and collision preflight without drawing a canvas.

This feature is deliberately narrower than general text repulsion: collections, bars,
arbitrary annotations, and non-Cartesian axes use the explicit fallback policy.

.. _figure-export:

Figure export
-------------

:func:`ggstyle.save` exports an explicit :class:`matplotlib.figure.Figure`. It never
guesses the current figure, and both output dimensions are required:

.. code-block:: python

   path = gs.save(
       figure,
       "report.png",
       width=7,
       height=4,
       units="in",
       dpi=300,
       metadata={"Creator": "ggstyle"},
   )

``units`` accepts inches, centimetres, millimetres, or pixels. Pixel dimensions are
converted through the explicit DPI even for vector output. The format is inferred from a
recognized filename extension; an explicit ``format=`` is required when there is no
extension and must agree with an existing extension.

The default ``bbox="tight"`` crops the nominal canvas to all decorated content with
0.1-inch padding. Use ``bbox="standard"`` when the final raster or vector canvas must
retain exactly ``width`` by ``height``. Output is opaque unless ``transparent=True``.
Metadata keys are backend-specific strings passed through to Matplotlib; SVG and PDF
timestamps are suppressed unless explicitly supplied, and SVG identifiers use a stable
salt for repeatable output.

Overwrite is an explicit policy. The default raises :class:`FileExistsError` before
rendering. With ``overwrite=True``, rendering still occurs in a same-directory temporary
file and the destination is replaced only after a non-empty artifact succeeds. Render
failures leave the old destination intact, temporary files are cleaned up, and the
figure's original physical size and global ``rcParams`` are restored before publication.
Parent directories are never created implicitly.

Date-axis model
---------------

A :class:`ggstyle.DateAxis` is attached to one matplotlib ``Axes``. Repeated calls to
:func:`ggstyle.dates` return the same handle. The handle has two coordinate modes:

``show``
   Use matplotlib date numbers. Missing calendar dates occupy space.

``collapse``
   Use a registered scale that maps sorted, unique observations to ordinal display
   positions. Artist data and limits remain matplotlib date numbers.

Ticks and labels
----------------

:meth:`ggstyle.DateAxis.ticks` controls positions. Named cadences include ``daily``,
``weekly``, ``monthly``, ``quarterly``, and ``yearly``. Anchored forms such as
``month-start`` and ``month-end`` control which observation represents a period.

:meth:`ggstyle.DateAxis.fmt` controls text without changing positions. Presets include
``concise``, ``month-year``, ``quarter``, ``year``, ``iso``, and ``time``.

.. _numeric-labels:

Numeric labels
--------------

Numeric label factories are separate from date formatting. They return immutable,
one-value callables that can also be used for report text. Use
:func:`ggstyle.as_formatter` to cross the Matplotlib boundary explicitly:

.. code-block:: python

   currency = gs.label_currency("$", scale=1_000_000, decimals=1, suffix="M")
   ax.yaxis.set_major_formatter(gs.as_formatter(currency))

   percent = gs.label_percent(scale=1.0, decimals=1)
   assert percent(0.125) == "12.5%"

:func:`ggstyle.label_number` provides fixed decimal precision and optional comma
grouping. :func:`ggstyle.label_si` selects a power-of-1000 prefix such as ``k``, ``M``,
or ``µ`` and accepts an explicit unit.

The ``scale`` argument is always explicit. For percentages it is the input value that
means 100 percent; for number and currency labels it is a positive divisor. Formatting
uses Python's fixed-point, round-half-even behavior and never reads the process locale.
Negative values use a leading minus by default or parentheses when
``negative="parentheses"``. The complete default labels for non-finite values are
``"NaN"``, ``"∞"``, and ``"-∞"``; callers may replace the first two strings.

Creating a labeller or adapter does not install it, alter axis limits, or mutate global
Matplotlib settings. Installation remains an ordinary Matplotlib operation, and the
returned :class:`matplotlib.ticker.FuncFormatter` remains available for further
customization.

.. _palettes:

Palettes
--------

:func:`ggstyle.palette` returns an immutable :class:`ggstyle.Palette`. The qualitative
palette is the eight-colour cycle shared by every ggstyle theme. Selection preserves its
reviewed order and a request above eight raises instead of silently creating colours that
are difficult to distinguish:

.. code-block:: python

   series_colors = gs.palette("qualitative", n=4).colors
   ax.set_prop_cycle(color=series_colors)

Sequential and diverging palettes provide deterministic CIELAB interpolation over an
already-normalized interval. Diverging samples require an odd count so the neutral colour
is always represented, and ``midpoint=`` controls its normalized position:

.. code-block:: python

   sequential = gs.palette("sequential", n=5)
   diverging = gs.palette("diverging", n=5, midpoint=0.4)

   assert sequential.at(0.0) == sequential.colors[0]
   assert diverging.at(0.4) == "#F7F7F7"

``None`` and NaN return ``missing_color``. Values outside zero through one are clipped by
default; ``out_of_bounds="raise"`` rejects them, while ``"color"`` requires explicit
``under_color`` and ``over_color`` values. These policies are part of the palette object
and survive resampling.

The qualitative cycle has regression gates for pairwise separation under the
Machado–Oliveira–Fernandes colour-vision simulations and against light, grey, and dark
theme surfaces. Sequential lightness and both sides of the diverging palette are also
ordered under those simulations. These tests reduce predictable accessibility failures;
they do not replace checking a finished figure with its actual line weights, markers,
background, and labels.

Palette construction is pure: it neither imports Matplotlib nor changes ``rcParams``.
The public semantic helpers train color domains using these palette policies through
:class:`ggstyle.ContinuousScale`; :func:`ggstyle.guides` renders the corresponding native
colorbars.

Ranges
------

:meth:`ggstyle.DateAxis.zoom` accepts partial strings. ``"2024"`` covers the full year,
and ``"2024-03"`` covers the full month. ``last=`` measures backward from the final
observation rather than from the current date.

Collapsed axes
--------------

Call :meth:`ggstyle.DateAxis.collapse` to remove unobserved gaps and
:meth:`ggstyle.DateAxis.expand` to restore calendar spacing. The observations come from
plotted lines, scatter offsets, native ``fill_between`` polygons, and any explicit
``data=`` passed to :func:`ggstyle.dates`. Lines, ``scatter``, ``fill_between``, and
native data-space annotations all pass through the same scale without having their
geometry rewritten. Midpoint-stepped polygons are the exception: Matplotlib retains
their generated midpoints instead of all source x values, so
``fill_between(..., step="mid")`` requires the complete dates through ``data=``.

Annotations
-----------

Use :meth:`ggstyle.DateAxis.loc`, :meth:`ggstyle.DateAxis.vline`, and
:meth:`ggstyle.DateAxis.span` for coordinates that remain correct in both modes.
:meth:`ggstyle.DateAxis.loc` returns a native matplotlib date number in either mode;
collapsed display positioning belongs to the registered scale. Native calls such as
``ax.axvline(timestamp)`` therefore work as expected.

The artists created by ggstyle annotation helpers are available through
:attr:`ggstyle.DateAxis.annotation_artists` for ordinary Matplotlib styling. Call
:meth:`ggstyle.DateAxis.clear_annotations` to remove every managed annotation; externally
removed artists are tolerated.

Axis summaries and captions
---------------------------

:meth:`ggstyle.DateAxis.summary` returns an immutable :class:`ggstyle.AxisSummary`
instead of requiring callers to inspect locators or artists. It records the observation
range, inferred frequency, resolved cadences, display timezone, coordinate mode, and
number of explicitly dropped dates.

Use :meth:`ggstyle.DateAxis.caption` to format the same semantics for a report:

.. code-block:: python

   handle = gs.dates(ax)
   metadata = handle.summary()
   caption = handle.caption()          # return text only
   handle.caption(add=True)            # also draw below the axes

Missing dates
-------------

Missing values in explicitly supplied date data raise by default. Dropping them must be
requested and remains visible in the summary:

.. code-block:: python

   handle = gs.dates(ax, data=dates, missing="drop")
   assert handle.summary().missing_values == 2

Missing positions already embedded in plotted line artists are preserved as line breaks;
they are not treated as discarded source observations.

Synchronized panels
-------------------

:func:`ggstyle.sync_dates` adopts several axes, attaches them to one live observation
registry, and applies common date limits. This matters in collapsed mode: without a
common registry, the same date can have a different ordinal position in each panel.

.. code-block:: python

   handles = gs.sync_dates(axes, mode="collapse", limits="union")

Use ``limits="intersection"`` to display only the overlapping observation range. If the
panels already use different modes, pass an explicit mode rather than relying on an
arbitrary panel to win.

Call :meth:`ggstyle.DateAxis.refresh` after adding, changing, or removing plotted artists.
Refreshing any synchronized handle rescans every live member, commits one new registry
revision, and updates every member scale while preserving date-number view limits. A
repeated :func:`ggstyle.dates` call refreshes an existing handle as well.

Call :meth:`ggstyle.DateAxis.dispose` to disconnect callbacks and detach a handle from its
registry. Disposal is idempotent and leaves existing Matplotlib artists on the axes.

.. _themes:

Themes
------

:func:`ggstyle.use_theme` changes matplotlib settings process-wide. Prefer the scoped
:class:`ggstyle.theme` context manager in reusable code. Importing ``ggstyle`` does not
change matplotlib global state.

Nine ggplot2-inspired themes are available: ``minimal``, ``grey``, ``bw``, ``linedraw``,
``light``, ``dark``, ``classic``, ``void``, and ``test``. ``minimal`` is the default and
``test`` is intended for stable visual tests rather than presentation output. The
corresponding ggplot2 spellings, such as ``theme_bw`` and ``theme_classic``, are accepted
as aliases.

.. code-block:: python

   with gs.theme("classic"):
       fig, ax = plt.subplots()

Each theme is also a standalone matplotlib stylesheet returned by
:func:`ggstyle.stylesheet`. Facet-strip styling has no direct core matplotlib equivalent.
The ``void`` theme hides axis-label text through static matplotlib settings, which can
leave some layout space reserved for a label.

.. _parameterized-themes:

Parameterized themes
--------------------

:func:`ggstyle.theme_spec` creates an immutable, validated theme recipe. ``base_size``
scales the theme's complete text hierarchy proportionally, ``base_family`` replaces its
font family, and explicit ``overrides`` are applied last:

.. code-block:: python

   report_theme = gs.theme_spec(
       "minimal",
       base_size=11,
       base_family="DejaVu Sans",
       overrides={"axes.titlesize": 14},
   )

Unknown rcParams, invalid values, and operational settings such as ``backend`` are
rejected when the recipe is created. :func:`ggstyle.theme_params` resolves a recipe to a
read-only mapping without mutating global ``rcParams``. This is the integration boundary
for code that needs Matplotlib settings rather than a context manager.

The same recipe works process-wide with :func:`ggstyle.use_theme`, temporarily with
:class:`ggstyle.theme`, or transactionally on an existing axes:

.. code-block:: python

   result = gs.finish(ax, theme=report_theme)

Existing-axes theming updates figure and panel surfaces, spines, major grids, ticks,
titles, axis labels, and an existing legend. It does not recolour data artists or alter
the axes property cycle, figure geometry, line defaults, save settings, or global
``rcParams``. ``result.diagnostics`` names the creation-, data-, and output-time rcParams
that were preserved. Theme application participates in the same rollback contract as
the rest of :func:`ggstyle.finish`, and repeated application reuses existing artists.
