"""Registered Matplotlib scale for observation-collapsed date coordinates."""

from __future__ import annotations

from typing import Any

import matplotlib.scale as mscale
import matplotlib.ticker as mticker
import matplotlib.transforms as mtransforms
import numpy as np

from . import _coordinates

SCALE_NAME = "ggstyle-collapsed-date"


class CollapsedDateTransform(mtransforms.Transform):
    """Map native Matplotlib date coordinates to observation ordinals."""

    input_dims = 1
    output_dims = 1
    is_separable = True
    has_inverse = True

    def __init__(self, observations: np.ndarray) -> None:
        super().__init__()
        self._mapping = _coordinates.CollapsedDateMapping(observations)

    @property
    def observations(self) -> np.ndarray:
        """Return the immutable date-number knots owned by this transform."""
        return self._mapping.knots

    def transform_non_affine(self, values: Any) -> np.ndarray:
        """Transform native date numbers without applying an affine component."""
        return self._mapping.forward(values)

    def inverted(self) -> InvertedCollapsedDateTransform:
        """Return the ordinal-to-date inverse transform."""
        return InvertedCollapsedDateTransform(self._mapping.knots)


class InvertedCollapsedDateTransform(mtransforms.Transform):
    """Map observation ordinals back to native Matplotlib date coordinates."""

    input_dims = 1
    output_dims = 1
    is_separable = True
    has_inverse = True

    def __init__(self, observations: np.ndarray) -> None:
        super().__init__()
        self._mapping = _coordinates.CollapsedDateMapping(observations)

    def transform_non_affine(self, values: Any) -> np.ndarray:
        """Transform ordinals without applying an affine component."""
        return self._mapping.inverse(values)

    def inverted(self) -> CollapsedDateTransform:
        """Return the date-to-ordinal forward transform."""
        return CollapsedDateTransform(self._mapping.knots)


class CollapsedDateScale(mscale.ScaleBase):
    """Apply a collapsed-date transform uniformly through ``Axes.transData``."""

    name = SCALE_NAME

    def __init__(self, *args: Any, observations: np.ndarray) -> None:
        # Matplotlib 3.7 passes Axis positionally. Matplotlib 3.11+ supports
        # constructors without an explicit ``axis`` parameter.
        axis = args[0] if args else None
        super().__init__(axis)
        self._transform = CollapsedDateTransform(observations)

    def get_transform(self) -> CollapsedDateTransform:
        """Return this immutable scale instance's coordinate transform."""
        return self._transform

    def set_default_locators_and_formatters(self, axis: Any) -> None:
        """Clear defaults before ``DateAxis`` installs its prepared tick plan."""
        axis.set_major_locator(mticker.NullLocator())
        axis.set_major_formatter(mticker.NullFormatter())
        axis.set_minor_locator(mticker.NullLocator())
        axis.set_minor_formatter(mticker.NullFormatter())


def register() -> None:
    """Register the scale when collapsed mode is first requested."""
    mscale.register_scale(CollapsedDateScale)
