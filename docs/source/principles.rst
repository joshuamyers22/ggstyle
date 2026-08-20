Graphics and reporting principles
=================================

ggstyle borrows the discipline of projects such as ggstatsplot while retaining a much
narrower purpose. The library manages time axes and presentation; it does not select or
run statistical tests.

Show the data
-------------

Position on a common scale is easier to compare than area, angle, or decorative encodings.
Time-series values therefore remain on ordinary matplotlib axes, and synchronized panels
use common date positions and limits whenever comparison is intended.

Make transformations explicit
-----------------------------

Collapsed time is useful but changes the meaning of horizontal distance. The mode is
available through :meth:`ggstyle.DateAxis.summary`, appears in generated captions, and is
documented as an axis transformation rather than presented as ordinary calendar time.

Keep calculation separate from rendering
----------------------------------------

Future confidence or prediction ribbons will accept caller-provided bounds. ggstyle will
not infer whether a band is a confidence interval, choose a statistical model, or compute
a hypothesis test as a side effect of plotting. Statistical work belongs to libraries
such as statsmodels and SciPy; ggstyle can present their explicit outputs.

Keep displayed and extractable meaning synchronized
---------------------------------------------------

Information used in a caption is generated from the same :class:`ggstyle.AxisSummary`
available to application code. This avoids manually copying observation counts, ranges,
timezones, or gap semantics into reports.

Do not hide excluded data
-------------------------

Explicit date data containing missing values raises unless ``missing="drop"`` is passed.
When values are dropped, their count remains available in summaries and generated
captions.

Prefer a small orthogonal API
-----------------------------

Tick placement, formatting, range, grid cadence, coordinate mode, and annotations remain
independent controls. Grouped views use :func:`ggstyle.sync_dates` instead of separate
``grouped_*`` copies of every plotting function.
