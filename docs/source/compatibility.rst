Compatibility contract
======================

Version 0.3 supports Python 3.10 through 3.13, Matplotlib 3.7.5 or newer, pandas
2.0 or newer, and NumPy 1.24 or newer. The reproducible floor job uses the final
Matplotlib 3.7 patch release so the declared minimum includes that minor series' complete
maintenance fixes.

Supported artists and transforms
--------------------------------

The collapsed scale changes display coordinates; it never rewrites artist geometry.
Observation discovery has a narrower, explicit contract:

.. list-table::
   :header-rows: 1

   * - Artist
     - Rendering
     - Observation provenance
   * - ``Line2D`` from ``ax.plot``
     - ``ax.transData``
     - Original unit-aware x data
   * - ``PathCollection`` from ``ax.scatter``
     - Data-space offset transform
     - Finite, unmasked x offsets
   * - Native ``fill_between`` polygon
     - ``ax.transData``
     - Source-side vertices from every retained path
   * - ``axvline`` and ggstyle annotations
     - Native x-data blended transform
     - None; presentation artists never add observations

Invisible supported artists still contribute. Removed artists disappear and mutated
artists replace their prior contribution on the next :meth:`ggstyle.DateAxis.refresh`.
Explicit ``data=`` observations are sticky and remain in the union.

``fill_between`` masks, NaNs, and ``where=False`` regions do not contribute because
Matplotlib omits them from retained polygon paths. Closing vertices and interpolated
crossings are generated geometry and are excluded. ``step="pre"`` and ``step="post"``
are recoverable; ``step="mid"`` requires the complete source dates through ``data=``.

Strict diagnostics
------------------

Unsupported or ambiguous date-bearing artists raise
:class:`ggstyle.DateDiscoveryError` during preflight. Version 0.3 deliberately has no
permissive warning mode: a warning could leave a plausible-looking but incorrect plot.
Failure does not commit a registry revision or partially update synchronized axes.

The following are explicit exclusions on an x-date handle:

* ``fill_betweenx`` because its date coordinate belongs to y;
* data artists using axes-, figure-, display-, or custom transforms;
* arbitrary third-party collection subclasses without a supported provenance adapter;
* numeric line coordinates whose status as Matplotlib date numbers is ambiguous, unless
  the complete observations are supplied through ``data=``; and
* automatic thread safety or automatic refresh after arbitrary Matplotlib mutation.

Refresh and synchronization
---------------------------

Call :meth:`ggstyle.DateAxis.refresh` after adding, changing, or removing data artists.
It rescans every live member of a synchronized registry, validates the complete candidate,
commits one revision, reinstalls collapsed scale snapshots, and redraws managed ticks and
annotations. Existing date-number limits are preserved. Any prepare or apply failure
restores the previous registry, modes, limits, and rendered configuration.

:func:`ggstyle.sync_dates` gives all supplied handles one weakly owned registry.
Refreshing any member updates every member. :meth:`ggstyle.DateAxis.dispose` disconnects
callbacks and detaches that handle without removing Matplotlib artists; repeated disposal
is safe.

Verification environments
-------------------------

Continuous integration runs the full Python 3.10--3.13 matrix on Linux, representative
Python 3.12 jobs on macOS and Windows, exact minimum and newest-stable dependency profiles,
and one pinned Ubuntu renderer for pixels. Prerelease dependency runs are scheduled and
informational; stable supported releases are blocking. See ``REPRODUCIBILITY.md`` and the
visual regression guide for exact pins and commands.
