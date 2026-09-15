Inspection
==========

ggstyle exposes resolved policy as plain data before callers commit a finishing request.
Inspection never draws a canvas, changes artists, installs a layout engine, or mutates
global Matplotlib settings.

Finishing plans
---------------

Pass ``dry_run=True`` to :func:`ggstyle.finish` to receive the same
:class:`ggstyle.FinishPlan` that a successful commit would retain:

.. code-block:: python

   plan = gs.finish(
       ax,
       title="Revenue",
       theme=gs.theme_spec("minimal", base_size=11),
       y=gs.axis(
           title="USD",
           labels=gs.label_currency("$", scale=1_000_000, suffix="M"),
       ),
       dry_run=True,
   )

   payload = plan.as_dict()
   print(plan.describe())

``as_dict()`` returns fresh JSON-compatible containers containing the requested text,
nested theme, numeric-labeller and endpoint-label policy, resolved direct-label and
layout actions, ordered managed changes, and diagnostics. ``describe()`` renders that
same payload as deterministic, strict JSON. Neither form contains axes, artists,
callables, mapping proxies, or pandas objects.

The representation is intended for logs, review, and snapshot tests. It is not a
round-trip recipe format: reusable recipe serialization remains deferred until real
composition use cases establish its schema.

Date-axis summaries
-------------------

:meth:`ggstyle.DateAxis.summary` returns an immutable :class:`ggstyle.AxisSummary`.
Its matching inspection methods expose the resolved coordinate mode, observation range,
frequency, cadences, display timezone, and missing-value count:

.. code-block:: python

   summary = gs.dates(ax).ticks("monthly").summary()
   audit_record = summary.as_dict()
   print(summary.describe())

Timestamp values use ISO 8601 strings in the JSON-safe representation. The original
``summary.start`` and ``summary.end`` attributes remain pandas ``Timestamp`` objects for
ordinary Python analysis.
