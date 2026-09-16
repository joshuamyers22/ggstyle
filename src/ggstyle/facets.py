"""Pure dataframe partition and layout planning for native facets."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, cast

import pandas as pd

from ._frames import column
from ._inspection import describe, json_safe
from ._semantic_scales import _is_missing

__all__ = ["FacetPanel", "FacetPlan", "facet_plan"]

FacetScales = Literal["fixed", "free_x", "free_y", "free"]
FacetMissingPolicy = Literal["drop", "keep", "raise"]
FacetLayout = Literal["wrap", "grid"]

_ABSENT = object()
_MISSING = object()


@dataclass(frozen=True)
class FacetPanel:
    """
    Describe one planned facet panel without retaining source data.

    Parameters
    ----------
    index : int
        Zero-based row-major position in the plan's panel sequence.
    row : int
        Zero-based layout row.
    column : int
        Zero-based layout column.
    values : mapping of str to object
        Facet-variable values selecting this panel. A missing facet level is ``None``.
    indices : tuple of int
        Zero-based source-row positions assigned to the panel.
    """

    index: int
    row: int
    column: int
    values: Mapping[str, object]
    indices: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "indices", tuple(self.indices))

    @property
    def empty(self) -> bool:
        """Return whether no source rows belong to this panel."""

        return not self.indices

    def as_dict(self) -> dict[str, object]:
        """
        Return bounded JSON-compatible panel inspection data.

        Returns
        -------
        dict of str to object
            Panel position, facet values, row count, and empty status. Source-row
            positions are intentionally excluded from the bounded representation.
        """

        return {
            "column": self.column,
            "empty": self.empty,
            "index": self.index,
            "row": self.row,
            "row_count": len(self.indices),
            "values": json_safe(self.values),
        }


@dataclass(frozen=True)
class FacetPlan:
    """
    Describe a validated facet partition and layout without creating a figure.

    Parameters
    ----------
    layout : {"wrap", "grid"}
        Resolved layout strategy.
    row, col : str or None
        Source columns assigned to layout rows and columns.
    wrap : int or None
        Maximum wrap columns for a one-variable wrap layout.
    scales : {"fixed", "free_x", "free_y", "free"}
        Planned coordinate-sharing policy for later rendering.
    include_unobserved : bool
        Whether explicit or categorical levels absent from the data receive panels.
    missing : {"drop", "keep", "raise"}
        Facet-variable missing-value policy.
    max_panels : int
        Validated panel-count safety limit.
    nrows, ncols : int
        Resolved rectangular layout dimensions.
    panels : tuple of FacetPanel
        Row-major immutable panel descriptions.
    row_levels, col_levels : tuple of object
        Resolved facet levels. Missing levels appear as ``None``.
    input_rows : int
        Number of rows in the supplied dataframe-like input.
    dropped_rows : int
        Number excluded by the missing-value policy.
    diagnostics : tuple of str
        Deterministic non-fatal planning diagnostics.
    """

    layout: FacetLayout
    row: str | None
    col: str | None
    wrap: int | None
    scales: FacetScales
    include_unobserved: bool
    missing: FacetMissingPolicy
    max_panels: int
    nrows: int
    ncols: int
    panels: tuple[FacetPanel, ...]
    row_levels: tuple[object, ...]
    col_levels: tuple[object, ...]
    input_rows: int
    dropped_rows: int
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "panels", tuple(self.panels))
        object.__setattr__(self, "row_levels", tuple(self.row_levels))
        object.__setattr__(self, "col_levels", tuple(self.col_levels))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    @property
    def shape(self) -> tuple[int, int]:
        """Return the resolved ``(rows, columns)`` layout shape."""

        return self.nrows, self.ncols

    def as_dict(self) -> dict[str, object]:
        """
        Return deterministic strict-JSON facet inspection data.

        Returns
        -------
        dict of str to object
            Fresh bounded containers describing policy, levels, shape, panels, and
            row accounting without retaining or serializing source data.
        """

        return {
            "diagnostics": list(self.diagnostics),
            "dropped_rows": self.dropped_rows,
            "include_unobserved": self.include_unobserved,
            "input_rows": self.input_rows,
            "layout": self.layout,
            "levels": {
                "column": json_safe(self.col_levels),
                "row": json_safe(self.row_levels),
            },
            "max_panels": self.max_panels,
            "missing": self.missing,
            "panel_count": len(self.panels),
            "panels": [panel.as_dict() for panel in self.panels],
            "scales": self.scales,
            "shape": [self.nrows, self.ncols],
            "variables": {"column": self.col, "row": self.row},
            "wrap": self.wrap,
        }

    def describe(self) -> str:
        """
        Return the facet plan as deterministic formatted strict JSON.

        Returns
        -------
        str
            Strict JSON containing the same values as :meth:`as_dict`.
        """

        return describe(self.as_dict())


def _name(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a column-name string or None, got {value!r}")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _positive_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a positive integer, got {value!r}")
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return value


def _values(name: str, selected: object) -> tuple[object, ...]:
    if getattr(selected, "ndim", 1) != 1:
        raise ValueError(f"column {name!r} must be one-dimensional and uniquely named")
    if isinstance(selected, (str, bytes)):
        raise TypeError(f"column {name!r} must be a one-dimensional sequence")
    converter = getattr(selected, "to_list", None)
    if callable(converter):
        return tuple(converter())
    try:
        return tuple(cast(Iterable[object], selected))
    except TypeError as error:
        raise TypeError(
            f"column {name!r} must be a one-dimensional sequence"
        ) from error


def _level(value: object, *, variable: str) -> object:
    try:
        hash(value)
    except TypeError as error:
        raise TypeError(
            f"facet column {variable!r} must contain hashable scalar values, "
            f"got {value!r}"
        ) from error
    return value


def _unique(values: Iterable[object], *, variable: str) -> tuple[object, ...]:
    result: dict[object, None] = {}
    for value in values:
        result.setdefault(_level(value, variable=variable), None)
    return tuple(result)


def _order(name: str, value: object, *, variable: str | None) -> tuple[object, ...] | None:
    if value is None:
        return None
    if variable is None:
        raise ValueError(f"{name} requires its corresponding facet variable")
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence of facet levels or None")
    levels = tuple(value)
    if any(_is_missing(level) for level in levels):
        raise ValueError(f"{name} cannot contain missing levels")
    unique = _unique(levels, variable=variable)
    if len(unique) != len(levels):
        raise ValueError(f"{name} must contain unique levels")
    return levels


def _declared_levels(source: object, *, variable: str) -> tuple[object, ...] | None:
    dtype = getattr(source, "dtype", None)
    if isinstance(dtype, pd.CategoricalDtype):
        return _unique(dtype.categories, variable=variable)
    if type(source).__module__.split(".")[0] != "polars":
        return None
    if type(dtype).__name__ == "Enum":
        categories = cast(Any, dtype).categories
        return _unique(cast(Iterable[object], categories), variable=variable)
    if type(dtype).__name__ == "Categorical":
        categories = cast(Any, source).cat.get_categories()
        return _unique(categories.to_list(), variable=variable)
    return None


def _resolved_levels(
    *,
    variable: str,
    source: object,
    values: Sequence[object],
    order: tuple[object, ...] | None,
    include_unobserved: bool,
    missing: FacetMissingPolicy,
) -> tuple[object, ...]:
    observed = _unique(
        (value for value in values if not _is_missing(value)), variable=variable
    )
    declared = _declared_levels(source, variable=variable)
    candidates = order if order is not None else declared
    if candidates is None:
        levels = observed
    else:
        candidate_set = set(candidates)
        unknown = [value for value in observed if value not in candidate_set]
        if unknown:
            raise ValueError(
                f"facet column {variable!r} contains values absent from its explicit "
                f"or categorical order: {unknown!r}"
            )
        observed_set = set(observed)
        levels = (
            candidates
            if include_unobserved
            else tuple(value for value in candidates if value in observed_set)
        )
    if missing == "keep" and any(_is_missing(value) for value in values):
        levels += (_MISSING,)
    return levels


def _public_levels(levels: Sequence[object]) -> tuple[object, ...]:
    return tuple(None if value is _MISSING else value for value in levels)


def _panel_values(
    row: str | None,
    col: str | None,
    row_level: object,
    col_level: object,
) -> Mapping[str, object]:
    values: dict[str, object] = {}
    if row is not None:
        values[row] = None if row_level is _MISSING else row_level
    if col is not None:
        values[col] = None if col_level is _MISSING else col_level
    return values


def facet_plan(
    data: object,
    *,
    row: str | None = None,
    col: str | None = None,
    wrap: int | None = None,
    scales: FacetScales = "fixed",
    row_order: Sequence[object] | None = None,
    col_order: Sequence[object] | None = None,
    include_unobserved: bool = False,
    missing: FacetMissingPolicy = "drop",
    max_panels: int = 64,
) -> FacetPlan:
    """
    Plan deterministic dataframe partitions and a facet layout without rendering.

    Parameters
    ----------
    data : dataframe-like
        Column-bearing dataframe-like or mapping-like data. Input is never mutated or
        retained by the returned plan.
    row, col : str or None, optional
        Columns assigned to grid rows and columns. At least one is required and they
        must be distinct.
    wrap : int or None, optional
        Maximum number of columns for a one-variable ``col`` wrap. It cannot be combined
        with ``row``.
    scales : {"fixed", "free_x", "free_y", "free"}, default "fixed"
        Coordinate-sharing policy recorded for later rendering.
    row_order, col_order : sequence or None, optional
        Explicit facet-level order. Observed values outside it are rejected.
    include_unobserved : bool, default False
        Retain explicit or categorical levels absent from the observed data.
    missing : {"drop", "keep", "raise"}, default "drop"
        Drop rows with any missing facet value, retain a final missing level, or reject
        the input.
    max_panels : int, default 64
        Positive safety limit checked before panel descriptions are allocated.

    Returns
    -------
    FacetPlan
        Immutable row-major partitions, layout shape, policy, and bounded inspection.

    Notes
    -----
    Grid plans use the Cartesian product of resolved row and column levels, retaining
    empty combinations. Wrap plans contain one panel per resolved column level. This
    function creates no Matplotlib figure, axes, artists, callbacks, or global state.
    """

    row = _name("row", row)
    col = _name("col", col)
    if row is None and col is None:
        raise ValueError("at least one of row or col is required")
    if row is not None and row == col:
        raise ValueError("row and col must name distinct columns")
    resolved_wrap = None if wrap is None else _positive_integer("wrap", wrap)
    if resolved_wrap is not None and (row is not None or col is None):
        raise ValueError("wrap requires one col facet and no row facet")
    if scales not in ("fixed", "free_x", "free_y", "free"):
        raise ValueError(
            "scales must be 'fixed', 'free_x', 'free_y', or 'free', "
            f"got {scales!r}"
        )
    if not isinstance(include_unobserved, bool):
        raise TypeError("include_unobserved must be a bool")
    if missing not in ("drop", "keep", "raise"):
        raise ValueError(
            f"missing must be 'drop', 'keep', or 'raise', got {missing!r}"
        )
    resolved_max = _positive_integer("max_panels", max_panels)
    resolved_row_order = _order("row_order", row_order, variable=row)
    resolved_col_order = _order("col_order", col_order, variable=col)

    if (
        type(data).__module__.split(".")[0] == "polars"
        and type(data).__name__ == "LazyFrame"
    ):
        raise TypeError(
            "data must be materialized before facet planning; call collect() on LazyFrame"
        )
    selected: dict[str, object] = {}
    extracted: dict[str, tuple[object, ...]] = {}
    for variable in (row, col):
        if variable is None:
            continue
        source = column(data, variable)
        selected[variable] = source
        extracted[variable] = _values(variable, source)
    lengths = {len(values) for values in extracted.values()}
    if len(lengths) > 1:
        raise ValueError("facet columns must have equal length")
    input_rows = next(iter(lengths), 0)

    row_levels = (
        (_ABSENT,)
        if row is None
        else _resolved_levels(
            variable=row,
            source=selected[row],
            values=extracted[row],
            order=resolved_row_order,
            include_unobserved=include_unobserved,
            missing=missing,
        )
    )
    col_levels = (
        (_ABSENT,)
        if col is None
        else _resolved_levels(
            variable=col,
            source=selected[col],
            values=extracted[col],
            order=resolved_col_order,
            include_unobserved=include_unobserved,
            missing=missing,
        )
    )
    if not row_levels or not col_levels:
        raise ValueError(
            "facet planning produced no panels; provide observed rows or retain "
            "explicit unobserved levels"
        )

    panel_count = (
        len(col_levels) if resolved_wrap is not None else len(row_levels) * len(col_levels)
    )
    if panel_count > resolved_max:
        raise ValueError(
            f"facet plan requires {panel_count} panels, exceeding max_panels="
            f"{resolved_max}; filter levels or raise the explicit limit"
        )

    buckets: dict[tuple[object, object], list[int]] = {}
    dropped_rows = 0
    for index in range(input_rows):
        raw_row = _ABSENT if row is None else extracted[row][index]
        raw_col = _ABSENT if col is None else extracted[col][index]
        missing_variables = [
            variable
            for variable, value in ((row, raw_row), (col, raw_col))
            if variable is not None and _is_missing(value)
        ]
        if missing_variables:
            if missing == "raise":
                joined = ", ".join(repr(variable) for variable in missing_variables)
                raise ValueError(
                    f"facet column(s) {joined} contain a missing value at row {index}"
                )
            if missing == "drop":
                dropped_rows += 1
                continue
        row_key = _MISSING if row is not None and _is_missing(raw_row) else raw_row
        col_key = _MISSING if col is not None and _is_missing(raw_col) else raw_col
        if row is not None:
            row_key = _level(row_key, variable=row)
        if col is not None:
            col_key = _level(col_key, variable=col)
        buckets.setdefault((row_key, col_key), []).append(index)

    panels: list[FacetPanel] = []
    if resolved_wrap is not None:
        ncols = min(resolved_wrap, len(col_levels))
        nrows = math.ceil(len(col_levels) / ncols)
        for index, col_level in enumerate(col_levels):
            panels.append(
                FacetPanel(
                    index,
                    index // ncols,
                    index % ncols,
                    _panel_values(None, col, _ABSENT, col_level),
                    tuple(buckets.get((_ABSENT, col_level), ())),
                )
            )
        layout: FacetLayout = "wrap"
    else:
        nrows = len(row_levels)
        ncols = len(col_levels)
        for row_index, row_level in enumerate(row_levels):
            for col_index, col_level in enumerate(col_levels):
                panels.append(
                    FacetPanel(
                        len(panels),
                        row_index,
                        col_index,
                        _panel_values(row, col, row_level, col_level),
                        tuple(buckets.get((row_level, col_level), ())),
                    )
                )
        layout = "grid"

    diagnostics = (
        (f"dropped {dropped_rows} row(s) with missing facet values",)
        if dropped_rows
        else ()
    )
    return FacetPlan(
        layout=layout,
        row=row,
        col=col,
        wrap=resolved_wrap,
        scales=cast(FacetScales, scales),
        include_unobserved=include_unobserved,
        missing=cast(FacetMissingPolicy, missing),
        max_panels=resolved_max,
        nrows=nrows,
        ncols=ncols,
        panels=tuple(panels),
        row_levels=() if row is None else _public_levels(row_levels),
        col_levels=() if col is None else _public_levels(col_levels),
        input_rows=input_rows,
        dropped_rows=dropped_rows,
        diagnostics=diagnostics,
    )
