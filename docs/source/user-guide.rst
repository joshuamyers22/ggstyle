User guide
==========

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
The API selects colours and maps normalized values only. Training a data domain, assigning
categories, and constructing legends or colorbars remain ordinary Matplotlib operations
until semantic scales land in a later release.

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
