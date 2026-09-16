"""The date axis handle.

``gs.dates(ax)`` returns a :class:`DateAxis` bound to that Axes, creating one or
adopting an existing plot. Adoption is the point: it works on figures this
package never made, so the date axis is useful on its own.

Configuration and drawing methods return ``self``, so calls chain::

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
from dataclasses import dataclass
from typing import Any, Literal

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes

from . import (
    _annotations,
    _axis_data,
    _axis_sync,
    _cadence,
    _date_ranges,
    _date_scale,
    _formats,
    _grid,
    _observation_registry,
    _tick_config,
    _tick_plan,
    _tick_positions,
    _tick_rendering,
    _timezones,
)
from ._axis_data import MissingPolicy
from ._axis_summary import AxisSummary as AxisSummary
from ._axis_summary import summarize_axis as _summarize_axis
from ._captions import format_caption as _format_caption
from ._observation_registry import DateDiscoveryError as DateDiscoveryError
from ._parse import to_timestamp

__all__ = ["AxisSummary", "DateAxis", "DateDiscoveryError", "dates", "sync_dates"]

_ATTR = "_ggstyle_date_axis"
_UNSET = object()


@dataclass(frozen=True)
class _RuntimeState:
    registry: _observation_registry.ObservationRegistry
    numbers: np.ndarray
    missing_values: int
    trusted: bool
    mode: Literal["show", "collapse"]
    limits: tuple[float, float]


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
    missing : {"raise", "drop"}, default "raise"
        Policy for missing values in explicitly supplied ``data``.

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

    def __init__(
        self,
        ax: Axes,
        data: Any = None,
        *,
        mode: str = "show",
        missing: MissingPolicy = "raise",
    ) -> None:
        if mode not in ("show", "collapse"):
            raise ValueError(f"mode must be 'show' or 'collapse', got {mode!r}")
        self.ax = ax
        self._mode: Literal["show", "collapse"] = "show"
        self._nums = np.empty(0, dtype=float)
        self._explicit_data = _axis_data.AxisData(np.empty(0, dtype=float), 0, False)
        self._registry = _observation_registry.ObservationRegistry()
        self._registry.attach(self)

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
        self._caption_artist: Any | None = None

        self._annotations: list[_annotations.Annotation] = []
        self._refreshing = False
        self._deferred_registry_refreshes = 0
        self._trusted = False
        self._missing_values = 0
        self._disposed = False

        self._ingest(data, missing=missing)
        candidate = self._registry.prepare()
        self._registry.commit(candidate)
        self._accept_registry(candidate)

        setattr(ax, _ATTR, self)
        self._callback_id = ax.callbacks.connect("xlim_changed", self._on_xlim_changed)

        if mode == "collapse":
            self.collapse()
        else:
            self._refresh()

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------

    def _ingest(self, data: Any, *, missing: MissingPolicy = "raise") -> None:
        """Add sticky explicit dates without rescanning plotted artists."""
        self._explicit_data = _axis_data.collect_explicit(
            data,
            existing=self._explicit_data,
            missing=missing,
        )

    def _managed_artists(self) -> set[Any]:
        artists = set(self._grid_artists)
        for annotation in self._annotations:
            artists.update(annotation.artists)
        if self._caption_artist is not None:
            artists.add(self._caption_artist)
        return artists

    def _accept_registry(
        self, candidate: _observation_registry.RegistryCandidate
    ) -> None:
        self._nums = candidate.numbers
        self._missing_values = candidate.missing_values
        self._trusted = candidate.trusted

    def _capture_runtime(self) -> _RuntimeState:
        lower, upper = self.ax.get_xlim()
        return _RuntimeState(
            self._registry,
            self._nums,
            self._missing_values,
            self._trusted,
            self._mode,
            (float(lower), float(upper)),
        )

    def _install_scale(self) -> None:
        if self._mode == "collapse":
            _date_scale.register()
            self.ax.set_xscale(_date_scale.SCALE_NAME, observations=self._nums)
        else:
            self.ax.set_xscale("linear")

    # ------------------------------------------------------------------
    # coordinates
    # ------------------------------------------------------------------

    @property
    def mode(self) -> Literal["show", "collapse"]:
        """Return the active coordinate mode."""
        return self._mode

    @property
    def revision(self) -> int:
        """Return the committed observation-registry revision."""
        return self._registry.revision

    @property
    def disposed(self) -> bool:
        """Return whether this handle has released its axes lifecycle state."""
        return self._disposed

    @property
    def observations(self) -> pd.DatetimeIndex:
        """Return sorted, unique dates backing the collapsed axis."""
        return pd.DatetimeIndex(mdates.num2date(self._nums)).tz_localize(None)

    def summary(self) -> AxisSummary:
        """
        Return structured information about the date axis.

        Returns
        -------
        AxisSummary
            Immutable snapshot of observations and active configuration.

        See Also
        --------
        caption : Format the summary for display on a figure.
        """
        observations = self.observations
        lo, hi = self._visible_range()
        span = abs(hi - lo)
        return _summarize_axis(
            mode=self._mode,
            observations=observations,
            major_cadence=self._summary_major_cadence(span),
            minor_cadence=self._summary_minor_cadence(span),
            timezone=self._tz,
            missing_values=self._missing_values,
        )

    def _summary_major_cadence(self, span: pd.Timedelta) -> str:
        if self._explicit_ticks is not None:
            return "explicit"
        return str(self._resolve_major(span))

    def _summary_minor_cadence(self, span: pd.Timedelta) -> str | None:
        if self._explicit_ticks is not None:
            return None
        major = self._resolve_major(span)
        minor = self._resolve_minor(span, major)
        return str(minor) if minor is not None else None

    def caption(self, *, add: bool = False, **kwargs: Any) -> str:
        """
        Format a concise description of axis semantics.

        Parameters
        ----------
        add : bool, default False
            Add the caption below the axes when true.
        **kwargs
            Additional keyword arguments passed to :meth:`matplotlib.axes.Axes.text`
            when ``add`` is true.

        Returns
        -------
        str
            Generated caption text.

        Notes
        -----
        Repeated calls with ``add=True`` replace the previously managed caption.
        """
        text = _format_caption(self.summary())

        if add:
            style: dict[str, Any] = {
                "ha": "left",
                "va": "top",
                "fontsize": "small",
                "color": "0.35",
                "transform": self.ax.transAxes,
            }
            style.update(kwargs)
            replacement = self.ax.text(0, -0.14, text, **style)
            previous = self._caption_artist
            if previous is not None and previous.axes is self.ax:
                previous.remove()
            self._caption_artist = replacement
        return text

    def _require_observations(self, what: str) -> None:
        if self._nums.size == 0:
            raise RuntimeError(
                f"{what} needs observed dates, but this axis has none. "
                "Plot something first, or pass dates(ax, data=...)."
            )

    def loc(self, date: Any, *, snap: bool = False, strict: bool = False) -> float:
        """
        Return the native matplotlib data coordinate corresponding to a date.

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
            Matplotlib date number accepted by native data-space artists and limits.

        Raises
        ------
        KeyError
            If ``strict`` is true and ``date`` was not observed.
        RuntimeError
            If strict lookup is requested but no observations are registered.

        Notes
        -----
        The returned coordinate is independent of display mode. In collapsed mode,
        the registered x-scale maps it to an observation position during rendering.
        Native datetime-like inputs also work directly with matplotlib; ``loc()``
        remains useful for parsing, snapping, and strict observation lookup.
        """
        ts = to_timestamp(date)
        num = float(mdates.date2num(ts))

        if strict:
            self._require_observations("strict lookup")
            if not np.any(np.isclose(self._nums, num)):
                raise KeyError(f"{ts} is not an observed date (strict=True)")

        if snap and self._nums.size:
            num = float(self._nums[int(np.argmin(np.abs(self._nums - num)))])

        return num

    def date_at(self, position: float) -> pd.Timestamp:
        """
        Return the date corresponding to a native matplotlib data coordinate.

        Parameters
        ----------
        position : float
            Matplotlib date number, such as an x coordinate obtained from
            ``transData.inverted()``.

        Returns
        -------
        pandas.Timestamp
            Timezone-naive timestamp at ``position``.
        """
        return pd.Timestamp(mdates.num2date(float(position))).tz_localize(None)

    def _visible_range(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        lo, hi = self.ax.get_xlim()
        start = pd.Timestamp(mdates.num2date(float(lo))).tz_localize(None)
        end = pd.Timestamp(mdates.num2date(float(hi))).tz_localize(None)
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
    ) -> DateAxis:
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
        configuration = _tick_config.resolve_tick_configuration(
            current_major=self._major_spec,
            current_minor=self._minor_spec,
            current_explicit=self._explicit_ticks,
            spec=spec,
            every=every,
            n=n,
            at=at,
            major=major,
            minor=minor,
        )
        previous = self._major_spec, self._minor_spec, self._explicit_ticks
        self._major_spec = configuration.major_spec
        self._minor_spec = configuration.minor_spec
        self._explicit_ticks = configuration.explicit_ticks
        try:
            return self._refresh()
        except Exception:
            self._major_spec, self._minor_spec, self._explicit_ticks = previous
            self._refresh()
            raise

    def _resolve_major(self, span: pd.Timedelta) -> _cadence.Cadence:
        return _tick_plan.resolve_major(self._major_spec, span)

    def _resolve_minor(
        self, span: pd.Timedelta, major: _cadence.Cadence
    ) -> _cadence.Cadence | None:
        return _tick_plan.resolve_minor(self._minor_spec, self._major_spec, span, major)

    def _ticks_for(
        self, cadence: _cadence.Cadence, lo: pd.Timestamp, hi: pd.Timestamp
    ) -> tuple[pd.DatetimeIndex, np.ndarray]:
        """Return label timestamps and native data coordinates for ``cadence``."""
        if self._mode == "collapse":
            self._require_observations("tick placement")
        return _tick_positions.positions_for_cadence(
            cadence,
            lo,
            hi,
            mode=self._mode,
            knots=self._nums,
        )

    # ------------------------------------------------------------------
    # tick labels
    # ------------------------------------------------------------------

    def fmt(
        self, spec: Any = None, *, major: Any = None, minor: Any = _UNSET
    ) -> DateAxis:
        """
        Configure tick labels without moving ticks.

        Parameters
        ----------
        spec : str or callable, optional
            Preset name, ``strftime`` pattern, or callable accepting one
            :class:`pandas.Timestamp`.
        major : str or callable, optional
            Keyword form of ``spec``.
        minor : str, callable, or False, optional
            Minor tick label format. Omit to leave the current setting unchanged;
            use ``False`` to disable minor labels.

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
        proposed_major = self._fmt_major
        proposed_minor = self._fmt_minor
        if spec is not None or major is not None:
            proposed_major = spec if spec is not None else major
            _formats.resolve(proposed_major)
        if minor is not _UNSET:
            proposed_minor = minor
            if minor is not False and minor is not None:
                _formats.resolve(minor)

        previous = self._fmt_major, self._fmt_minor
        self._fmt_major, self._fmt_minor = proposed_major, proposed_minor
        try:
            return self._refresh()
        except Exception:
            self._fmt_major, self._fmt_minor = previous
            self._refresh()
            raise

    def rotate(self, degrees: float = 45, *, ha: str | None = None) -> DateAxis:
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
        if ha not in (None, "left", "center", "right"):
            raise ValueError("ha must be 'left', 'center', or 'right'")
        previous = self._rotation, self._rotation_ha
        self._rotation = degrees
        if ha is not None:
            self._rotation_ha = ha
        elif degrees:
            self._rotation_ha = "right"
        else:
            self._rotation_ha = "center"
        try:
            return self._refresh()
        except Exception:
            self._rotation, self._rotation_ha = previous
            self._refresh()
            raise

    def tz(self, zone: str | None) -> DateAxis:
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
        _timezones.validate_display_timezone(zone)
        previous = self._tz
        self._tz = zone
        try:
            return self._refresh()
        except Exception:
            self._tz = previous
            self._refresh()
            raise

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
    ) -> DateAxis:
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
        elif last is not None:
            self._require_observations("zoom(last=...)")

        start_ts, end_ts = _date_ranges.resolve_zoom_range(
            self._visible_range(),
            self.observations,
            start=start,
            end=end,
            last=last,
            ytd=ytd,
        )

        nums = mdates.date2num(pd.DatetimeIndex([start_ts, end_ts]))
        self.ax.set_xlim(float(nums[0]), float(nums[1]))
        return self._refresh()

    def pad(self, left: Any = None, right: Any = None) -> DateAxis:
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
        lo, hi = _date_ranges.pad_range(self._visible_range(), left=left, right=right)
        nums = mdates.date2num(pd.DatetimeIndex([lo, hi]))
        self.ax.set_xlim(float(nums[0]), float(nums[1]))
        return self._refresh()

    # ------------------------------------------------------------------
    # gaps
    # ------------------------------------------------------------------

    def collapse(self) -> DateAxis:
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
        The registered x-scale changes display coordinates without rewriting artist
        geometry. Native matplotlib lines, collections, and data-space annotations
        therefore retain their calendar date coordinates.
        """
        if self._mode == "collapse":
            return self
        self._require_observations("collapse()")

        limits = self.ax.get_xlim()
        self._refreshing = True
        try:
            self._mode = "collapse"
            _date_scale.register()
            self.ax.set_xscale(_date_scale.SCALE_NAME, observations=self._nums)
            self.ax.set_xlim(limits)
        except Exception:
            self._mode = "show"
            self.ax.set_xscale("linear")
            self.ax.set_xlim(limits)
            raise
        finally:
            self._refreshing = False
        return self._refresh()

    def expand(self) -> DateAxis:
        """
        Switch to calendar coordinates and restore gaps.

        Returns
        -------
        DateAxis
            This handle, for method chaining.
        """
        if self._mode == "show":
            return self
        limits = self.ax.get_xlim()
        self._refreshing = True
        try:
            self._mode = "show"
            self.ax.set_xscale("linear")
            self.ax.set_xlim(limits)
        except Exception:
            self._mode = "collapse"
            _date_scale.register()
            self.ax.set_xscale(_date_scale.SCALE_NAME, observations=self._nums)
            self.ax.set_xlim(limits)
            raise
        finally:
            self._refreshing = False
        return self._refresh()

    # ------------------------------------------------------------------
    # annotation in date space
    # ------------------------------------------------------------------

    @property
    def annotation_artists(self) -> tuple[Any, ...]:
        """Return the currently attached artists created by annotation helpers."""
        return tuple(
            artist
            for annotation in self._annotations
            for artist in annotation.artists
            if artist.axes is self.ax
        )

    def clear_annotations(self) -> DateAxis:
        """
        Remove all ggstyle-managed date annotations from this axes.

        Returns
        -------
        DateAxis
            This handle, for method chaining.
        """
        for annotation in self._annotations:
            _annotations.discard(self.ax, annotation)
        self._annotations.clear()
        return self

    def _add_annotation(self, annotation: _annotations.Annotation) -> None:
        try:
            _annotations.draw(self.ax, annotation, self.loc)
        except Exception:
            _annotations.discard(self.ax, annotation)
            raise
        self._annotations.append(annotation)

    def vline(
        self, date: Any, label: str | None = None, **kwargs: Any
    ) -> DateAxis:
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
        self._add_annotation(_annotations.Annotation("vline", (date,), label, kwargs))
        return self

    def span(
        self,
        start: Any,
        end: Any,
        label: str | None = None,
        **kwargs: Any,
    ) -> DateAxis:
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
        self._add_annotation(
            _annotations.Annotation("span", (start, end), label, kwargs)
        )
        return self

    def spans(
        self,
        frame: pd.DataFrame,
        start: str = "start",
        end: str = "end",
        label: str | None = None,
        **kwargs: Any,
    ) -> DateAxis:
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
        prepared = [
            _annotations.Annotation(
                "span",
                (row[start], row[end]),
                str(row[label]) if label is not None else None,
                kwargs,
            )
            for _, row in frame.iterrows()
        ]
        for annotation in prepared:
            for date in annotation.dates:
                self.loc(date)

        added: list[_annotations.Annotation] = []
        try:
            for annotation in prepared:
                self._add_annotation(annotation)
                added.append(annotation)
        except Exception:
            for annotation in added:
                _annotations.discard(self.ax, annotation)
                self._annotations.remove(annotation)
            raise
        return self

    # ------------------------------------------------------------------
    # gridlines, at their own cadence
    # ------------------------------------------------------------------

    def grid(self, spec: Any = None, **kwargs: Any) -> DateAxis:
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
        proposed = None if spec is False else spec
        if proposed is not None:
            _cadence.resolve(proposed)
        previous = self._grid_spec, self._grid_kwargs
        self._grid_spec = proposed
        self._grid_kwargs = kwargs
        try:
            return self._refresh()
        except Exception:
            self._grid_spec, self._grid_kwargs = previous
            self._refresh()
            raise

    def _draw_grid(self, lo: pd.Timestamp, hi: pd.Timestamp) -> None:
        self._grid_artists = _grid.render(
            self.ax,
            self._grid_artists,
            self._grid_spec,
            self._grid_kwargs,
            lo,
            hi,
            self._ticks_for,
        )

    # ------------------------------------------------------------------
    # refresh
    # ------------------------------------------------------------------

    def _on_xlim_changed(self, _ax: Axes) -> None:
        if not self._refreshing:
            self._refresh()

    def refresh(self) -> DateAxis:
        """
        Rescan live data artists and publish one shared registry revision.

        Synchronized handles refresh as a group. Existing date-number limits are
        preserved even when new observations change collapsed display positions.

        Returns
        -------
        DateAxis
            This handle, for method chaining.

        Raises
        ------
        DateDiscoveryError
            If a candidate artist uses an unsupported coordinate transform.
        RuntimeError
            If this handle has been disposed.
        """
        if self._disposed:
            raise RuntimeError("cannot refresh a disposed DateAxis")
        if self._deferred_registry_refreshes:
            return self
        registry = self._registry
        candidate = registry.prepare()
        members = candidate.members
        if candidate.numbers.size == 0 and any(
            handle.mode == "collapse" for handle in members
        ):
            raise RuntimeError(
                "refresh() cannot leave a collapsed registry empty; add date data "
                "or expand the synchronized axes first"
            )
        prepared = {
            handle: handle._prepare_render(numbers=candidate.numbers)
            for handle in members
        }
        states = {handle: handle._capture_runtime() for handle in members}
        snapshot = registry.snapshot()

        for handle in members:
            handle._refreshing = True
        try:
            registry.commit(candidate)
            for handle in members:
                handle._accept_registry(candidate)
            for handle in members:
                handle._install_scale()
                handle.ax.set_xlim(states[handle].limits)
            for handle in members:
                handle._render_prepared(*prepared[handle])
        except Exception:
            registry.restore(snapshot)
            for handle, state in states.items():
                handle._nums = state.numbers
                handle._missing_values = state.missing_values
                handle._trusted = state.trusted
                handle._mode = state.mode
            for handle, state in states.items():
                handle._install_scale()
                handle.ax.set_xlim(state.limits)
                handle._render_prepared(*handle._prepare_render())
            raise
        finally:
            for handle in members:
                handle._refreshing = False
        return self

    def _begin_deferred_registry_refresh(self) -> None:
        """Defer public registry scans while a facet mapping batch is in progress."""

        self._deferred_registry_refreshes += 1

    def _end_deferred_registry_refresh(self) -> None:
        """End one facet mapping deferral without implicitly scanning artists."""

        if self._deferred_registry_refreshes <= 0:
            raise RuntimeError("date registry refresh deferral is not active")
        self._deferred_registry_refreshes -= 1

    def dispose(self) -> None:
        """
        Disconnect callbacks and release registry and managed-artist references.

        Existing Matplotlib artists remain on the axes; ggstyle simply stops managing
        them. Calling this method repeatedly is safe.
        """
        if self._disposed:
            return
        self.ax.callbacks.disconnect(self._callback_id)
        self._registry.detach(self)
        self._registry = _observation_registry.ObservationRegistry()
        if getattr(self.ax, _ATTR, None) is self:
            delattr(self.ax, _ATTR)
        self._grid_artists.clear()
        self._annotations.clear()
        self._caption_artist = None
        self._disposed = True

    def _prepare_render(
        self,
        *,
        numbers: np.ndarray | None = None,
        mode: Literal["show", "collapse"] | None = None,
        limits: tuple[float, float] | None = None,
    ) -> tuple[pd.Timestamp, pd.Timestamp, _tick_plan.TickPlan]:
        numbers = self._nums if numbers is None else numbers
        mode = self._mode if mode is None else mode
        if limits is None:
            lo, hi = self._visible_range()
        else:
            lo = pd.Timestamp(mdates.num2date(limits[0])).tz_localize(None)
            hi = pd.Timestamp(mdates.num2date(limits[1])).tz_localize(None)
        if hi < lo:
            lo, hi = hi, lo
        explicit_positions = None
        if self._explicit_ticks is not None:
            explicit_positions = np.asarray(
                mdates.date2num(self._explicit_ticks), dtype=float
            )
        elif mode == "collapse" and numbers.size == 0:
            raise RuntimeError("tick placement needs observed dates")

        plan = _tick_plan.build_tick_plan(
            lo=lo,
            hi=hi,
            mode=mode,
            knots=numbers,
            major_spec=self._major_spec,
            minor_spec=self._minor_spec,
            explicit_ticks=self._explicit_ticks,
            explicit_positions=explicit_positions,
            major_format=self._fmt_major,
            minor_format=self._fmt_minor,
            timezone=self._tz,
        )
        return lo, hi, plan

    def _render_prepared(
        self,
        lo: pd.Timestamp,
        hi: pd.Timestamp,
        plan: _tick_plan.TickPlan,
    ) -> None:
        _tick_rendering.render(
            self.ax,
            plan.positions,
            plan.labels,
            minor_positions=plan.minor_positions,
            minor_labels=plan.minor_labels,
            rotation=self._rotation,
            horizontal_alignment=self._rotation_ha,
        )
        self._draw_grid(lo, hi)

    def _refresh(self) -> DateAxis:
        """Recompute ticks and labels from the current limits.

        Called by every mutating method and on interactive pan/zoom, so the axis
        stays correct rather than freezing the labels it was born with.
        """
        if self._refreshing:
            return self
        self._refreshing = True
        try:
            self._render_prepared(*self._prepare_render())
        finally:
            self._refreshing = False
        return self

    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover - display only
        count = self._nums.size
        return f"<DateAxis mode={self._mode!r} observations={count}>"


def sync_dates(
    axes: Iterable[Axes],
    *,
    mode: Literal["show", "collapse"] | None = None,
    limits: Literal["union", "intersection"] = "union",
) -> list[DateAxis]:
    """
    Synchronize date semantics across a collection of axes.

    Parameters
    ----------
    axes : iterable of matplotlib.axes.Axes
        Axes to adopt and synchronize.
    mode : {"show", "collapse"}, optional
        Coordinate mode applied to every axes. If omitted, existing modes must agree.
    limits : {"union", "intersection"}, default "union"
        Whether limits cover every observation or only the overlapping range.

    Returns
    -------
    list of DateAxis
        Handles in the same order as ``axes``.

    Raises
    ------
    ValueError
        If no axes are supplied, modes disagree, limits are invalid, or ranges do not
        overlap.

    Notes
    -----
    All handles join one live, revisioned observation registry. Refreshing any member
    rescans every live member and applies the resulting union transactionally.
    """
    _axis_sync.validate_options(mode, limits)

    axes_list = list(axes)
    if not axes_list:
        raise ValueError("axes must contain at least one matplotlib Axes")
    handles = []
    for ax in axes_list:
        existing = getattr(ax, _ATTR, None)
        handles.append(existing if existing is not None else DateAxis(ax))
    registry = _observation_registry.ObservationRegistry()
    for handle in handles:
        registry.attach(handle)
    candidate = registry.prepare()
    local_by_handle = dict(zip(candidate.members, candidate.local_numbers, strict=True))
    for handle in handles:
        if local_by_handle[handle].size == 0:
            handle._require_observations("sync_dates()")

    sync_plan = _axis_sync.plan(
        [local_by_handle[handle] for handle in handles],
        [handle.mode for handle in handles],
        mode=mode,
        limits=limits,
    )
    prepared = {
        handle: handle._prepare_render(
            numbers=candidate.numbers,
            mode=sync_plan.mode,
            limits=(sync_plan.lower, sync_plan.upper),
        )
        for handle in handles
    }
    states = {handle: handle._capture_runtime() for handle in handles}
    old_registries = {handle: handle._registry for handle in handles}

    for handle in handles:
        handle._refreshing = True
    try:
        registry.commit(candidate)
        for handle in handles:
            handle._registry = registry
            handle._accept_registry(candidate)
            handle._mode = sync_plan.mode
        for handle in handles:
            handle._install_scale()
            handle.ax.set_xlim(sync_plan.lower, sync_plan.upper)
        for handle in handles:
            handle._render_prepared(*prepared[handle])
    except Exception:
        for handle, state in states.items():
            handle._registry = state.registry
            handle._nums = state.numbers
            handle._missing_values = state.missing_values
            handle._trusted = state.trusted
            handle._mode = state.mode
        for handle, state in states.items():
            handle._install_scale()
            handle.ax.set_xlim(state.limits)
            handle._render_prepared(*handle._prepare_render())
        raise
    else:
        for handle, old_registry in old_registries.items():
            old_registry.detach(handle)
    finally:
        for handle in handles:
            handle._refreshing = False
    return handles


def dates(
    ax: Axes | None = None,
    data: Any = None,
    *,
    mode: str | None = None,
    missing: MissingPolicy = "raise",
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
    missing : {"raise", "drop"}, default "raise"
        Policy for missing values in explicitly supplied ``data``.

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
    Repeated calls for the same axes return the same object and refresh its observation
    registry. This discovers supported artists added, changed, or removed since the
    previous call.
    """
    if mode not in (None, "show", "collapse"):
        raise ValueError(f"mode must be 'show' or 'collapse', got {mode!r}")
    if missing not in ("raise", "drop"):
        raise ValueError(f"missing must be 'raise' or 'drop', got {missing!r}")
    ax = ax if ax is not None else plt.gca()
    handle = getattr(ax, _ATTR, None)

    if handle is None:
        return DateAxis(ax, data, mode=mode or "show", missing=missing)

    if data is not None:
        previous = handle._explicit_data
        handle._ingest(data, missing=missing)
        try:
            handle.refresh()
        except Exception:
            handle._explicit_data = previous
            raise
    else:
        handle.refresh()
    if mode == "collapse":
        handle.collapse()
    elif mode == "show":
        handle.expand()
    return handle
