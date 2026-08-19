User guide
==========

Date-axis model
---------------

A :class:`ggstyle.DateAxis` is attached to one matplotlib ``Axes``. Repeated calls to
:func:`ggstyle.dates` return the same handle. The handle has two coordinate modes:

``show``
   Use matplotlib date numbers. Missing calendar dates occupy space.

``collapse``
   Map sorted, unique observations to ordinal positions. Unobserved dates occupy no
   space.

Ticks and labels
----------------

:meth:`ggstyle.DateAxis.ticks` controls positions. Named cadences include ``daily``,
``weekly``, ``monthly``, ``quarterly``, and ``yearly``. Anchored forms such as
``month-start`` and ``month-end`` control which observation represents a period.

:meth:`ggstyle.DateAxis.fmt` controls text without changing positions. Presets include
``concise``, ``month-year``, ``quarter``, ``year``, ``iso``, and ``time``.

Ranges
------

:meth:`ggstyle.DateAxis.zoom` accepts partial strings. ``"2024"`` covers the full year,
and ``"2024-03"`` covers the full month. ``last=`` measures backward from the final
observation rather than from the current date.

Collapsed axes
--------------

Call :meth:`ggstyle.DateAxis.collapse` to remove unobserved gaps and
:meth:`ggstyle.DateAxis.expand` to restore calendar spacing. The observations come from
the plotted lines and any explicit ``data=`` passed to :func:`ggstyle.dates`.

Annotations
-----------

Use :meth:`ggstyle.DateAxis.loc`, :meth:`ggstyle.DateAxis.vline`, and
:meth:`ggstyle.DateAxis.span` for coordinates that remain correct in both modes. This is
especially important on collapsed axes, where a raw matplotlib date number is not an
axis position.

Themes
------

:func:`ggstyle.use_theme` changes matplotlib settings process-wide. Prefer the scoped
:class:`ggstyle.theme` context manager in reusable code. Importing ``ggstyle`` does not
change matplotlib global state.
