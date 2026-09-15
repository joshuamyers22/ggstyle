Release notes
=============

Unreleased
----------

Collapsed coordinates now use one registered matplotlib x-scale instead of rewriting
``Line2D`` data. Lines, ``scatter``, ``fill_between``, and native x-data annotations share
the same invertible display transform while their calendar geometry and date-number
limits remain unchanged. Empty registries still reject collapse; a one-observation
registry now uses one calendar day per ordinal unit in both directions.

``DateAxis.loc()`` now returns a native matplotlib date number in both modes. Code that
passes its result to matplotlib artists or limits continues to work, while code that
asserted observation ordinals should instead inspect the axis scale transform. This is a
deliberate pre-1.0 migration to avoid double-transforming native matplotlib operations.

0.2.0
-----

This release completes ggstyle's built-in ggplot2-inspired theme set with ``bw``,
``linedraw``, ``light``, ``dark``, ``classic``, ``void``, and ``test``. The existing
``minimal`` default and ``grey`` theme remain unchanged. Corresponding ggplot2 function
names such as ``theme_bw`` and ``theme_classic`` are accepted as aliases.

Each theme ships as a standalone matplotlib stylesheet. See :ref:`the Themes section
<themes>` for the full list and matplotlib-specific fidelity notes.

0.1.1
-----

This maintenance release refactors date-axis behavior into focused policy modules while
preserving the public API, and strengthens reproducible build and publishing checks.

0.1.0
-----

The initial public release introduces the standalone date-axis handle, date extraction for
common dataframe and array libraries, collapsed observation spacing, date-space
annotations, and two opt-in matplotlib themes.

See :doc:`pitfalls` for current lifecycle and timezone limitations.
