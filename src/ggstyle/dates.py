"""The date axis handle.

``gs.dates(ax)`` returns a :class:`DateAxis` bound to that Axes, creating one or
adopting an existing plot. Adoption is the point: it works on figures this
package never made, so the date axis is useful on its own.

Every method returns ``self``, so calls chain::

    gs.dates(ax).ticks("quarterly").fmt("month-year").zoom("2020", "2022")

Two coordinate modes:

``"show"``
    A true datetime axis. Positions are matplotlib date numbers. Weekends and
    holidays occupy space.

``"collapse"``
    An observation-ordinal axis. Position *i* is the *i*-th observed date; dates
    in between are placed by linear interpolation. Nothing that was not observed
    gets space. Which dates count is decided entirely by the data, not by a
    holiday calendar, so this is correct for any market or region and needs no
    extra dependency.

Every date-space operation (:meth:`DateAxis.loc`, :meth:`DateAxis.vline`,
:meth:`DateAxis.span`, :meth:`DateAxis.zoom`) works identically in both modes.
That is what keeps annotations honest when the mode changes.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.ticker import FixedFormatter, FixedLocator

from . import _cadence, _formats
from ._frames import to_datetime_index as _as_datetime_index
from ._parse import to_offset, to_timestamp

__all__ = ["DateAxis", "dates"]

_ATTR = "_ggstyle_date_axis"

#: Plausible range for a matplotlib date number, used to catch non-date axes.
#: Roughly years 1400 to 2500 either side of the 1970 epoch.
_NUM_MIN, _NUM_MAX = -220_000, 200_000
_MAX_TICKS = 10_000


@dataclass
class _Annotation:
    """Store a replayable date-space annotation."""

    kind: Literal["vline", "span"]
    dates: tuple[Any, ...]
    label: str | None
    kwargs: dict[str, Any]
    artists: list[Any] = field(default_factory=list)


class DateAxis:
    """
    Manage a date-aware x-axis bound to a matplotlib axes.

    Obtain instances with :func:`dates` instead of constructing them directly.
    The accessor caches one handle per axes, so repeated calls return the same
    object.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Axes whose x-axis will be managed.
    data : array-like, optional
        Additional observed dates. Values must already have a datetime dtype or
        be unambiguously date-like Python objects.
    mode : {"show", "collapse"}, default "show"
        Initial coordinate mode. ``"show"`` preserves calendar gaps;
        ``"collapse"`` uses observation-ordinal positions.

    Attributes
    ----------
    ax : matplotlib.axes.Axes
        Bound matplotlib axes.

    See Also
    --------
    dates : Create or retrieve a date-axis handle.
    ggstyle.theme : Apply a scoped matplotlib theme.

    Notes
    -----
    The handle updates tick locators when x-axis limits change. Importing
    ``ggstyle`` never creates a handle or changes matplotlib global state.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> import pandas as pd
    >>> fig, ax = plt.subplots()
    >>> _ = ax.plot(pd.date_range("2024-01-01", periods=10), range(10))
    >>> handle = dates(ax).ticks("daily").fmt("day")
    """

    def __init__(self, ax: Axes, data: Any = None, *, mode: str = "show") -> None:
        if mode not in ("show", "collapse"):
            raise ValueError(f"mode must be 'show' or 'collapse', got {mode!r}")
        self.ax = ax
        self._mode = "show"
        self._nums = np.empty(0, dtype=float)

        self._major_spec: Any = None  # None -> auto
        self._minor_spec: Any = "auto"
        self._explicit_ticks: pd.DatetimeIndex | None = None
        self._fmt_major: Any = None
        self._fmt_minor: Any = False  # False -> minor ticks unlabelled

        self._tz: str | None = None
        self._rotation: float | None = None
        self._rotation_ha: str = "right"

        self._grid_spec: Any = None
        self._grid_kwargs: dict[str, Any] = {}
        self._grid_artists: list[Any] = []

        self._annotations: list[_Annotation] = []
        self._original_x: dict[int, np.ndarray] = {}
        self._refreshing = False
        self._trusted = False

        self._ingest(data)
        self._validate()

        setattr(ax, _ATTR, self)
        ax.callbacks.connect("xlim_changed", self._on_xlim_changed)

        if mode == "collapse":
            self.collapse()
        else:
            self._refresh()

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------

    def _ingest(self, data: Any) -> None:
        """Collect observed dates from explicit input and from existing artists."""
        nums: list[np.ndarray] = []

        if data is not None:
            index = _as_datetime_index(data)
            nums.append(mdates.date2num(index))
            self._trusted = True

        for line in self.ax.lines:
            xdata = np.asarray(line.get_xdata(orig=False), dtype=float)
            if xdata.size:
                nums.append(xdata)

        if nums:
            stacked = np.concatenate(nums)
            stacked = stacked[np.isfinite(stacked)]
            self._nums = np.unique(stacked)

    def _has_date_converter(self) -> bool:
        """Whether matplotlib is treating this axis as dates."""
        axis = self.ax.xaxis
        getter = getattr(axis, "get_converter", None)
        converter = getter() if getter is not None else getattr(axis, "converter", None)
        if converter is None:
            return False
        if isinstance(converter, (mdates.DateConverter, mdates.ConciseDateConverter)):
            return True
        # matplotlib >= 3.9 installs a switchable converter by default.
        return "Date" in type(converter).__name__

    def _validate(self) -> None:
        """Fail loudly if this does not look like a date axis."""
        if self._nums.size == 0:
            return

        if not self._trusted and not self._has_date_converter():
            raise TypeError(
                "x axis does not look like dates: matplotlib has no date converter "
                "installed on it. Plot datetimes, or pass the dates explicitly via "
                "dates(ax, data=...)."
            )

        lo, hi = float(self._nums[0]), float(self._nums[-1])
        if lo < _NUM_MIN or hi > _NUM_MAX:
            raise TypeError(
                "x axis does not look like dates: values span "
                f"{lo:.6g} to {hi:.6g}, which is outside the plausible range for "
                "matplotlib date numbers."
            )

    # ------------------------------------------------------------------
    # coordinates
    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        """Return the active coordinate mode."""
        return self._mode

    @property
    def observations(self) -> pd.DatetimeIndex:
        """Return sorted, unique dates backing the collapsed axis."""
        return pd.DatetimeIndex(mdates.num2date(self._nums)).tz_localize(None)

    def _require_observations(self, what: str) -> None:
        if self._nums.size == 0:
            raise RuntimeError(
                f"{what} needs observed dates, but this axis has none. "
                "Plot something first, or pass dates(ax, data=...)."
            )

    def _nums_to_pos(self, nums: np.ndarray) -> np.ndarray:
        """Map matplotlib date numbers to axis positions for the current mode."""
        nums = np.atleast_1d(np.asarray(nums, dtype=float))
        if self._mode == "show":
            return nums

        self._require_observations("collapsed positioning")
        knots = self._nums
        index = np.arange(knots.size, dtype=float)
        if knots.size == 1:
            step = 1.0
            return (nums - knots[0]) / step

        pos = np.interp(nums, knots, index)
        # np.interp clamps; extrapolate outside the observed range using median
        # spacing so that .pad() and out-of-range annotations still behave.
        step = float(np.median(np.diff(knots))) or 1.0
        below = nums < knots[0]
        above = nums > knots[-1]
        pos[below] = (nums[below] - knots[0]) / step
        pos[above] = index[-1] + (nums[above] - knots[-1]) / step
        return pos

    def _pos_to_nums(self, pos: np.ndarray) -> np.ndarray:
        """Inverse of :meth:`_nums_to_pos`."""
        pos = np.atleast_1d(np.asarray(pos, dtype=float))
        if self._mode == "show":
            return pos

        self._require_observations("collapsed positioning")
        knots = self._nums
        index = np.arange(knots.size, dtype=float)
        if knots.size == 1:
            return np.full_like(pos, knots[0])

        nums = np.interp(pos, index, knots)
        step = float(np.median(np.diff(knots))) or 1.0
        below = pos < 0
        above = pos > index[-1]
        nums[below] = knots[0] + pos[below] * step
        nums[above] = knots[-1] + (pos[above] - index[-1]) * step
        return nums

    def loc(self, date: Any, *, snap: bool = False, strict: bool = False) -> float:
        """
        Return the axis position corresponding to a date.

        Parameters
        ----------
        date : date-like
            Anything :func:`~ggstyle._parse.to_timestamp` accepts, including
            partial strings.
        snap : bool, default False
            Round to the nearest observed date rather than interpolating.
        strict : bool, default False
            Raise if ``date`` is not itself an observation.

        Returns
        -------
        float
            Position in the active coordinate system.

        Raises
        ------
        KeyError
            If ``strict`` is true and ``date`` was not observed.
        RuntimeError
            If strict lookup is requested but no observations are registered.

        Notes
        -----
        This method is the escape hatch for native matplotlib operations in
        collapsed mode. For example, ``ax.axvline(handle.loc(date))`` remains
        correct after switching coordinate modes.
        """
        ts = to_timestamp(date)
        num = float(mdates.date2num(ts))

        if strict:
            self._require_observations("strict lookup")
            if not np.any(np.isclose(self._nums, num)):
                raise KeyError(f"{ts} is not an observed date (strict=True)")

        if snap and self._nums.size:
            num = float(self._nums[int(np.argmin(np.abs(self._nums - num)))])

        return float(self._nums_to_pos(np.array([num]))[0])

    def date_at(self, position: float) -> pd.Timestamp:
        """
        Return the date corresponding to an axis position.

        Parameters
        ----------
        position : float
            Position in the active coordinate system.

        Returns
        -------
        pandas.Timestamp
            Timezone-naive timestamp at ``position``.
        """
        num = float(self._pos_to_nums(np.array([float(position)]))[0])
        return pd.Timestamp(mdates.num2date(num)).tz_localize(None)

    def _visible_range(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        lo, hi = self.ax.get_xlim()
        nums = self._pos_to_nums(np.array([lo, hi], dtype=float))
        start = pd.Timestamp(mdates.num2date(float(nums[0]))).tz_localize(None)
        end = pd.Timestamp(mdates.num2date(float(nums[1]))).tz_localize(None)
        return start, end

    # ------------------------------------------------------------------
    # tick placement
    # ------------------------------------------------------------------

    def ticks(
        self,
        spec: Any = None,
        *,
        every: Any = None,
        n: int | None = None,
        at: Iterable[Any] | None = None,
        major: Any = None,
        minor: Any = None,
    ):
        """
        Configure tick positions without changing label formatting.

        Parameters
        ----------
        spec : str or Cadence, optional
            Named cadence such as ``"monthly"`` or an offset alias.
        every : str or pandas offset, optional
            Explicit interval such as ``"3M"``.
        n : int, optional
            Approximate desired number of major ticks.
        at : iterable of date-like, optional
            Explicit major tick dates.
        major : str or Cadence, optional
            Keyword form of ``spec``.
        minor : str, Cadence, or False, optional
            Minor tick cadence. Use ``False`` to disable minor ticks.

        Returns
        -------
        DateAxis
            This handle, for method chaining.

        Raises
        ------
        TypeError
            If conflicting major tick specifications are supplied.
        ValueError
            If ``n`` is not a positive integer or the cadence is invalid.

        Examples
        --------
        ``.ticks("quarterly")``, ``.ticks(every="3M")``, ``.ticks(n=6)``,
        ``.ticks(at=["2020-01-01", "2021-07-01"])``,
        ``.ticks(major="yearly", minor="monthly")``, ``.ticks("month-end")``.
        """
        given = [x for x in (spec, every, n, at, major) if x is not None]
        if len(given) > 1:
            raise TypeError(
                "pass only one of spec, every=, n=, at=, or major= to ticks()"
            )

        if at is not None:
            self._explicit_ticks = _as_datetime_index(at)
            self._major_spec = None
        elif n is not None:
            if isinstance(n, bool) or not isinstance(n, int) or n < 1:
                raise ValueError(f"n must be a positive integer, got {n!r}")
            self._explicit_ticks = None
            self._major_spec = ("count", n)
        elif every is not None:
            self._explicit_ticks = None
            self._major_spec = _cadence.resolve(every)
        elif spec is not None or major is not None:
            self._explicit_ticks = None
            value = spec if spec is not None else major
            self._major_spec = None if value == "auto" else _cadence.resolve(value)

        if minor is not None:
            if minor == "auto":
                self._minor_spec = "auto"
            elif minor is False:
                self._minor_spec = None
            else:
                self._minor_spec = _cadence.resolve(minor)

        return self._refresh()

    def _resolve_major(self, span: pd.Timedelta) -> _cadence.Cadence:
        spec = self._major_spec
        if spec is None:
            return _cadence.auto_cadence(span)[0]
        if isinstance(spec, tuple) and spec[0] == "count":
            return _cadence.best_for_count(span, spec[1])
        return spec

    def _resolve_minor(
        self, span: pd.Timedelta, major: _cadence.Cadence
    ) -> _cadence.Cadence | None:
        spec = self._minor_spec
        if spec is None:
            return None
        if spec == "auto":
            if self._major_spec is None:
                return _cadence.auto_cadence(span)[1]
            return _minor_below(major)
        return spec

    def _ticks_for(
        self, cadence: _cadence.Cadence, lo: pd.Timestamp, hi: pd.Timestamp
    ) -> tuple[pd.DatetimeIndex, np.ndarray]:
        """Return (label timestamps, axis positions) for ``cadence``.

        In collapsed mode a candidate period boundary is positioned at the first
        observation inside that period (or the last, for end-anchored cadences),
        so monthly ticks land on real trading days while still being labelled as
        the month they open.
        """
        estimated = int(max((hi - lo).total_seconds(), 0) / cadence.approx_seconds) + 3
        if estimated > _MAX_TICKS:
            raise ValueError(
                f"tick cadence would create about {estimated:,} ticks; choose a "
                "coarser cadence or narrow the visible range"
            )
        candidates = _cadence.periods_between(cadence, lo, hi)
        if len(candidates) > _MAX_TICKS:
            raise ValueError(
                f"tick cadence would create {len(candidates):,} ticks; choose a "
                "coarser cadence or narrow the visible range"
            )
        if len(candidates) == 0:
            return pd.DatetimeIndex([]), np.empty(0)

        cand_nums = mdates.date2num(candidates)

        if self._mode == "show":
            positions = cand_nums
            labels = candidates
        else:
            self._require_observations("tick placement")
            knots = self._nums
            if cadence.anchor == "end":
                idx = np.searchsorted(knots, cand_nums, side="right") - 1
                # The matched observation must fall after the previous candidate,
                # i.e. inside this candidate's own period. Otherwise a period with
                # no observations would borrow its neighbour's and be mislabelled.
                previous = np.concatenate(([-np.inf], cand_nums[:-1]))
                inside_period = knots[np.clip(idx, 0, knots.size - 1)] > previous
            else:
                idx = np.searchsorted(knots, cand_nums, side="left")
                following = np.concatenate((cand_nums[1:], [np.inf]))
                inside_period = knots[np.clip(idx, 0, knots.size - 1)] < following

            valid = (idx >= 0) & (idx < knots.size) & inside_period
            idx, labels = idx[valid], candidates[valid]
            if idx.size == 0:
                return pd.DatetimeIndex([]), np.empty(0)
            positions = idx.astype(float)

        lo_pos = float(self._nums_to_pos(np.array([mdates.date2num(lo)]))[0])
        hi_pos = float(self._nums_to_pos(np.array([mdates.date2num(hi)]))[0])
        inside = (positions >= min(lo_pos, hi_pos) - 1e-9) & (
            positions <= max(lo_pos, hi_pos) + 1e-9
        )
        return pd.DatetimeIndex(labels)[inside], np.asarray(positions)[inside]

    # ------------------------------------------------------------------
    # tick labels
    # ------------------------------------------------------------------

    def fmt(self, spec: Any = None, *, major: Any = None, minor: Any = False):
        """
        Configure tick labels without moving ticks.

        Parameters
        ----------
        spec : str or callable, optional
            Preset name, ``strftime`` pattern, or callable accepting one
            :class:`pandas.Timestamp`.
        major : str or callable, optional
            Keyword form of ``spec``.
        minor : str, callable, or False, default False
            Minor tick label format. The default leaves minor ticks unlabeled.

        Returns
        -------
        DateAxis
            This handle, for method chaining.

        Raises
        ------
        TypeError
            If both ``spec`` and ``major`` are supplied.
        ValueError
            If a named format is unknown.
        """
        if spec is not None and major is not None:
            raise TypeError("pass either spec or major=, not both")
        if spec is not None or major is not None:
            self._fmt_major = spec if spec is not None else major
        if minor is not False:
            self._fmt_minor = minor
        return self._refresh()

    def rotate(self, degrees: float = 45, *, ha: str | None = None):
        """
        Rotate major tick labels.

        Parameters
        ----------
        degrees : float, default 45
            Rotation in degrees.
        ha : {"left", "center", "right"}, optional
            Horizontal alignment. Defaults to ``"right"`` for nonzero rotation
            and ``"center"`` otherwise.

        Returns
        -------
        DateAxis
            This handle, for method chaining.

        Notes
        -----
        Rotation is usually a symptom of bad tick selection; try ``.ticks(n=...)``
        or a coarser cadence first.
        """
        self._rotation = degrees
        if ha is not None:
            self._rotation_ha = ha
        elif degrees:
            self._rotation_ha = "right"
        else:
            self._rotation_ha = "center"
        return self._refresh()

    def tz(self, zone: str | None):
        """
        Set the display timezone used for labels.

        Parameters
        ----------
        zone : str or None
            IANA timezone name. Use ``None`` to display naive UTC values.

        Returns
        -------
        DateAxis
            This handle, for method chaining.

        Notes
        -----
        This operation changes labels only; it never changes artist data.
        """
        self._tz = zone
        return self._refresh()

    def _apply_tz(self, index: pd.DatetimeIndex) -> pd.DatetimeIndex:
        if self._tz is None:
            return index
        aware = index.tz_localize("UTC") if index.tz is None else index
        return aware.tz_convert(self._tz)

    # ------------------------------------------------------------------
    # range
    # ------------------------------------------------------------------

    def zoom(
        self,
        start: Any = None,
        end: Any = None,
        *,
        last: Any = None,
        ytd: bool = False,
    ):
        """
        Set the visible date range.

        Parameters
        ----------
        start : date-like, optional
            Left bound. Partial strings expand to the start of their period.
        end : date-like, optional
            Right bound. Partial strings expand to the end of their period.
        last : str or pandas offset, optional
            Trailing window measured from the final observation.
        ytd : bool, default False
            Display the year containing the final observation through that
            observation.

        Returns
        -------
        DateAxis
            This handle, for method chaining.

        Raises
        ------
        RuntimeError
            If ``last`` or ``ytd`` is requested without observations.

        Notes
        -----
        ``"2020"`` means the whole year and ``"2020-03"`` the whole month, so
        ``.zoom("2020", "2022")`` covers three complete years.
        """
        if ytd:
            self._require_observations("zoom(ytd=True)")
            anchor = self.observations[-1]
            start_ts = pd.Timestamp(year=anchor.year, month=1, day=1)
            end_ts = anchor
        elif last is not None:
            self._require_observations("zoom(last=...)")
            anchor = self.observations[-1]
            start_ts = anchor - to_offset(last)
            end_ts = anchor
        else:
            lo, hi = self._visible_range()
            start_ts = to_timestamp(start, side="start") if start is not None else lo
            end_ts = to_timestamp(end, side="end") if end is not None else hi

        nums = mdates.date2num(pd.DatetimeIndex([start_ts, end_ts]))
        positions = self._nums_to_pos(np.asarray(nums, dtype=float))
        self.ax.set_xlim(float(positions[0]), float(positions[1]))
        return self._refresh()

    def pad(self, left: Any = None, right: Any = None):
        """
        Extend the visible range without changing artist data.

        Parameters
        ----------
        left : str or pandas offset, optional
            Amount added before the current left limit.
        right : str or pandas offset, optional
            Amount added after the current right limit.

        Returns
        -------
        DateAxis
            This handle, for method chaining.
        """
        lo, hi = self._visible_range()
        if left is not None:
            lo = lo - to_offset(left)
        if right is not None:
            hi = hi + to_offset(right)
        nums = mdates.date2num(pd.DatetimeIndex([lo, hi]))
        positions = self._nums_to_pos(np.asarray(nums, dtype=float))
        self.ax.set_xlim(float(positions[0]), float(positions[1]))
        return self._refresh()

    # ------------------------------------------------------------------
    # gaps
    # ------------------------------------------------------------------

    def collapse(self):
        """
        Switch to observation-ordinal coordinates.

        Returns
        -------
        DateAxis
            This handle, for method chaining.

        Raises
        ------
        RuntimeError
            If no observations are registered.

        Notes
        -----
        Only line artists are remapped in version 0.1. See the project pitfalls
        guide before using collections such as scatter plots.
        """
        if self._mode == "collapse":
            return self
        self._require_observations("collapse()")

        lo, hi = self._visible_range()
        self._remember_original_x()
        self._mode = "collapse"

        for line in self.ax.lines:
            if id(line) in self._original_x:
                line.set_xdata(self._nums_to_pos(self._original_x[id(line)]))

        self._replay_annotations()
        return self.zoom(lo, hi)

    def expand(self):
        """
        Switch to calendar coordinates and restore gaps.

        Returns
        -------
        DateAxis
            This handle, for method chaining.
        """
        if self._mode == "show":
            return self
        lo, hi = self._visible_range()
        self._mode = "show"

        for line in self.ax.lines:
            original = self._original_x.get(id(line))
            if original is not None:
                line.set_xdata(original)

        self._replay_annotations()
        return self.zoom(lo, hi)

    def _remember_original_x(self) -> None:
        annotation_ids = {
            id(artist) for entry in self._annotations for artist in entry.artists
        }
        for line in self.ax.lines:
            if id(line) in annotation_ids or id(line) in self._original_x:
                continue
            self._original_x[id(line)] = np.asarray(
                line.get_xdata(orig=False), dtype=float
            )

    # ------------------------------------------------------------------
    # annotation in date space
    # ------------------------------------------------------------------

    def vline(self, date: Any, label: str | None = None, **kwargs):
        """
        Draw a vertical line in date coordinates.

        Parameters
        ----------
        date : date-like
            Date at which to draw the line.
        label : str, optional
            Text drawn near the top of the axes.
        **kwargs
            Additional keyword arguments passed to
            :meth:`matplotlib.axes.Axes.axvline`.

        Returns
        -------
        DateAxis
            This handle, for method chaining.
        """
        self._annotations.append(
            _Annotation("vline", (date,), label, kwargs)
        )
        self._draw_annotation(self._annotations[-1])
        return self

    def span(self, start: Any, end: Any, label: str | None = None, **kwargs):
        """
        Draw a shaded region in date coordinates.

        Parameters
        ----------
        start : date-like
            Start of the region.
        end : date-like
            End of the region.
        label : str, optional
            Text drawn near the top of the axes.
        **kwargs
            Additional keyword arguments passed to
            :meth:`matplotlib.axes.Axes.axvspan`.

        Returns
        -------
        DateAxis
            This handle, for method chaining.
        """
        self._annotations.append(
            _Annotation("span", (start, end), label, kwargs)
        )
        self._draw_annotation(self._annotations[-1])
        return self

    def spans(
        self,
        frame: pd.DataFrame,
        start: str = "start",
        end: str = "end",
        label: str | None = None,
        **kwargs,
    ):
        """
        Draw multiple shaded regions from an event table.

        Parameters
        ----------
        frame : pandas.DataFrame
            Event table containing start and end columns.
        start : str, default "start"
            Name of the start-date column.
        end : str, default "end"
            Name of the end-date column.
        label : str, optional
            Name of a column containing annotation text.
        **kwargs
            Additional keyword arguments forwarded to :meth:`span`.

        Returns
        -------
        DateAxis
            This handle, for method chaining.
        """
        for _, row in frame.iterrows():
            text = str(row[label]) if label is not None else None
            self.span(row[start], row[end], label=text, **kwargs)
        return self

    def _draw_annotation(self, entry: _Annotation) -> None:
        kwargs = dict(entry.kwargs)

        if entry.kind == "vline":
            kwargs.setdefault("color", "0.35")
            kwargs.setdefault("linewidth", 1.0)
            kwargs.setdefault("linestyle", "--")
            position = self.loc(entry.dates[0])
            entry.artists.append(self.ax.axvline(position, **kwargs))
            text_x = position
        else:
            kwargs.setdefault("color", "0.85")
            kwargs.setdefault("alpha", 0.5)
            kwargs.setdefault("linewidth", 0)
            left = self.loc(entry.dates[0])
            right = self.loc(entry.dates[1])
            entry.artists.append(self.ax.axvspan(left, right, **kwargs))
            text_x = (left + right) / 2

        if entry.label:
            entry.artists.append(
                self.ax.text(
                    text_x,
                    0.98,
                    entry.label,
                    transform=self.ax.get_xaxis_transform(),
                    ha="center",
                    va="top",
                    fontsize="small",
                    color="0.35",
                    clip_on=True,
                )
            )

    def _replay_annotations(self) -> None:
        for entry in self._annotations:
            for artist in entry.artists:
                artist.remove()
            entry.artists.clear()
            self._draw_annotation(entry)

    # ------------------------------------------------------------------
    # gridlines, at their own cadence
    # ------------------------------------------------------------------

    def grid(self, spec: Any = None, **kwargs):
        """
        Configure gridlines independently of ticks.

        Parameters
        ----------
        spec : str, Cadence, or False, optional
            Grid cadence. Use ``False`` to remove managed gridlines.
        **kwargs
            Additional keyword arguments passed to
            :meth:`matplotlib.axes.Axes.axvline`.

        Returns
        -------
        DateAxis
            This handle, for method chaining.

        Examples
        --------
        ``.grid(False)`` removes them; ``.grid("yearly")`` draws them once a year
        regardless of how often ticks appear.
        """
        self._grid_spec = None if spec is False else spec
        self._grid_kwargs = kwargs
        return self._refresh()

    def _draw_grid(self, lo: pd.Timestamp, hi: pd.Timestamp) -> None:
        for artist in self._grid_artists:
            artist.remove()
        self._grid_artists = []
        if self._grid_spec is None:
            return

        cadence = _cadence.resolve(self._grid_spec)
        _, positions = self._ticks_for(cadence, lo, hi)
        style = {
            "color": plt.rcParams.get("grid.color", "0.85"),
            "linewidth": plt.rcParams.get("grid.linewidth", 0.8),
            "linestyle": plt.rcParams.get("grid.linestyle", "-"),
            "zorder": 0,
        }
        style.update(self._grid_kwargs)
        for position in positions:
            self._grid_artists.append(self.ax.axvline(float(position), **style))

    # ------------------------------------------------------------------
    # refresh
    # ------------------------------------------------------------------

    def _on_xlim_changed(self, _ax: Axes) -> None:
        if not self._refreshing:
            self._refresh()

    def _refresh(self):
        """Recompute ticks and labels from the current limits.

        Called by every mutating method and on interactive pan/zoom, so the axis
        stays correct rather than freezing the labels it was born with.
        """
        if self._refreshing:
            return self
        self._refreshing = True
        try:
            lo, hi = self._visible_range()
            if hi < lo:
                lo, hi = hi, lo
            span = hi - lo

            if self._explicit_ticks is not None:
                label_ts = self._explicit_ticks
                nums = np.asarray(mdates.date2num(label_ts), dtype=float)
                positions = self._nums_to_pos(nums)
                unit = _cadence.auto_cadence(span)[0].unit
                minor_cadence = None
            else:
                major = self._resolve_major(span)
                unit = major.unit
                label_ts, positions = self._ticks_for(major, lo, hi)
                minor_cadence = self._resolve_minor(span, major)

            labeller = _formats.resolve(self._fmt_major, unit)
            labels = labeller(list(self._apply_tz(pd.DatetimeIndex(label_ts))))

            self.ax.xaxis.set_major_locator(FixedLocator(list(map(float, positions))))
            self.ax.xaxis.set_major_formatter(FixedFormatter(labels))

            if minor_cadence is not None:
                minor_ts, minor_positions = self._ticks_for(minor_cadence, lo, hi)
                self.ax.xaxis.set_minor_locator(
                    FixedLocator(list(map(float, minor_positions)))
                )
                if self._fmt_minor is False or self._fmt_minor is None:
                    self.ax.xaxis.set_minor_formatter(
                        FixedFormatter([""] * len(minor_positions))
                    )
                else:
                    minor_labeller = _formats.resolve(
                        self._fmt_minor, minor_cadence.unit
                    )
                    self.ax.xaxis.set_minor_formatter(
                        FixedFormatter(
                            minor_labeller(list(self._apply_tz(pd.DatetimeIndex(minor_ts))))
                        )
                    )
            else:
                self.ax.xaxis.set_minor_locator(FixedLocator([]))

            if self._rotation is not None:
                for text in self.ax.get_xticklabels():
                    text.set_rotation(self._rotation)
                    alignment = cast(
                        Literal["left", "center", "right"], self._rotation_ha
                    )
                    text.set_horizontalalignment(alignment)

            self._draw_grid(lo, hi)
        finally:
            self._refreshing = False
        return self

    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover - display only
        count = self._nums.size
        return f"<DateAxis mode={self._mode!r} observations={count}>"


def _minor_below(cadence: _cadence.Cadence) -> _cadence.Cadence | None:
    """A sensible minor cadence one step finer than ``cadence``."""
    below = {
        "year": _cadence.Cadence("quarter"),
        "quarter": _cadence.Cadence("month"),
        "month": _cadence.Cadence("week"),
        "week": _cadence.Cadence("day"),
        "day": _cadence.Cadence("hour", 6),
        "hour": _cadence.Cadence("minute", 15),
        "minute": None,
    }
    return below.get(cadence.unit)


def dates(
    ax: Axes | None = None, data: Any = None, *, mode: str | None = None
) -> DateAxis:
    """
    Return the date-axis handle for a matplotlib axes.

    Works on any Axes, including plots this package never made::

        fig, ax = plt.subplots()
        ax.plot(df["date"], df["close"])       # plain matplotlib
        gs.dates(ax).ticks("quarterly")        # adopted

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        Target Axes. Defaults to the current one.
    data : array-like, optional
        Optional dates to register as observations, in addition to whatever is
        already plotted. Needed only when collapsing an axis whose dates are not
        recoverable from its artists.
    mode : {"show", "collapse"}, optional
        ``"show"`` or ``"collapse"``. Omit to leave an existing handle alone.

    Returns
    -------
    DateAxis
        Cached handle bound to ``ax``.

    Raises
    ------
    TypeError
        If the target does not appear to use a date x-axis.
    ValueError
        If ``mode`` is invalid.

    Notes
    -----
    Repeated calls for the same axes return the same object.
    """
    if mode not in (None, "show", "collapse"):
        raise ValueError(f"mode must be 'show' or 'collapse', got {mode!r}")
    ax = ax if ax is not None else plt.gca()
    handle = getattr(ax, _ATTR, None)

    if handle is None:
        return DateAxis(ax, data, mode=mode or "show")

    if data is not None:
        handle._ingest(data)
        handle._validate()
        handle._refresh()
    if mode == "collapse":
        handle.collapse()
    elif mode == "show":
        handle.expand()
    return handle
