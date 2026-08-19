Getting started
===============

Installation
------------

Install the public package with pip::

   python -m pip install ggstyle

The package requires Python 3.10 or newer. Polars support is optional::

   python -m pip install "ggstyle[polars]"

Adopt a matplotlib axis
-----------------------

``ggstyle`` does not replace matplotlib. Plot normally, then adopt the x-axis:

.. code-block:: python

   import matplotlib.pyplot as plt
   import pandas as pd
   import ggstyle as gs

   index = pd.date_range("2024-01-01", periods=180)
   values = range(len(index))

   with gs.theme("minimal"):
       fig, ax = plt.subplots()
       ax.plot(index, values)
       gs.dates(ax).ticks("monthly").fmt("month-year")

The :func:`ggstyle.dates` call returns a :class:`ggstyle.DateAxis`. Its methods return
the same handle, so operations can be chained.

Choose what to configure
------------------------

Tick placement and label formatting are deliberately separate:

.. code-block:: python

   handle = gs.dates(ax)
   handle.ticks("quarterly")
   handle.fmt("quarter")
   handle.zoom("2022", "2024")

See the :doc:`user-guide` for collapsed axes and annotations.
