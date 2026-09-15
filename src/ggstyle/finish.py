"""Transactional, layout-aware finishing for existing Matplotlib axes."""

from __future__ import annotations

import weakref
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, cast, overload

import matplotlib as mpl
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.figure import Figure, SubFigure
from matplotlib.font_manager import FontProperties
from matplotlib.text import Text
from matplotlib.transforms import ScaledTranslation, Transform

from .formats import NumericLabeller
from .formatters import as_formatter
from .theme import (
    ThemeSpec,
    _apply_theme_to_axes,
    _theme_diagnostics,
    theme_params,
    theme_spec,
)

__all__ = ["AxisSpec", "FinishPlan", "FinishResult", "axis", "finish"]

ManagedText = str | Literal[False] | None
LayoutAction = Literal["unchanged", "enable-constrained"]
HorizontalAlignment = Literal["left", "center", "right"]
VerticalAlignment = Literal["bottom", "baseline", "center", "center_baseline", "top"]


def _optional_string(name: str, value: object) -> None:
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{name} must be a string or None, got {value!r}")


def _managed_text(name: str, value: object) -> None:
    if value is None or value is False or isinstance(value, str):
        return
    raise TypeError(f"{name} must be a string, False, or None, got {value!r}")


@dataclass(frozen=True)
class AxisSpec:
    """
    Describe the labels applied to one existing Matplotlib axis.

    Parameters
    ----------
    title : str or None, optional
        Axis title. ``None`` leaves the existing title unchanged; an empty string
        clears it.
    labels : NumericLabeller or None, optional
        Numeric label policy installed through an ordinary Matplotlib
        ``FuncFormatter``. ``None`` leaves the existing formatter unchanged.

    Notes
    -----
    The model is immutable and does not retain an ``Axes``. Use :func:`axis` for
    construction and pass the result to :func:`finish`.
    """

    title: str | None = None
    labels: NumericLabeller | None = None

    def __post_init__(self) -> None:
        _optional_string("axis title", self.title)
        if self.labels is not None and not isinstance(self.labels, NumericLabeller):
            raise TypeError(
                "axis labels must be a ggstyle NumericLabeller or None, "
                f"got {self.labels!r}"
            )


def axis(*, title: str | None = None, labels: NumericLabeller | None = None) -> AxisSpec:
    """
    Create an immutable axis-finishing specification.

    Parameters
    ----------
    title : str or None, optional
        Axis title. ``None`` leaves the existing title unchanged.
    labels : NumericLabeller or None, optional
        Numeric label policy. Use :func:`label_percent`, :func:`label_currency`,
        :func:`label_number`, or :func:`label_si` to construct one.

    Returns
    -------
    AxisSpec
        Reusable, axes-independent specification.

    Examples
    --------
    >>> specification = axis(title="Share", labels=label_percent(decimals=1))
    >>> specification.title
    'Share'
    """
    return AxisSpec(title=title, labels=labels)


@dataclass(frozen=True)
class FinishPlan:
    """
    Describe a validated finishing operation without retaining live artists.

    Parameters
    ----------
    title : str or None
        Requested plot title; ``None`` means unchanged.
    subtitle : str, False, or None
        Requested managed subtitle operation.
    caption : str, False, or None
        Requested managed caption operation.
    theme : ThemeSpec or None
        Resolved theme requested for the existing axes.
    x : AxisSpec or None
        Requested x-axis changes.
    y : AxisSpec or None
        Requested y-axis changes.
    managed_changes : tuple of str
        Ordered descriptions of requested mutations.
    layout_action : {"unchanged", "enable-constrained"}
        Figure layout action required for outer managed text.
    diagnostics : tuple of str
        Non-fatal limitations discovered while planning.
    """

    title: str | None
    subtitle: ManagedText
    caption: ManagedText
    theme: ThemeSpec | None
    x: AxisSpec | None
    y: AxisSpec | None
    managed_changes: tuple[str, ...]
    layout_action: LayoutAction
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class FinishResult:
    """
    Return native Matplotlib objects and the plan applied by :func:`finish`.

    Parameters
    ----------
    axes : matplotlib.axes.Axes
        The exact axes passed to :func:`finish`.
    artists : tuple of matplotlib.artist.Artist
        Native non-data artists affected by the request and attached managed text.
    plan : FinishPlan
        Immutable plan used for the successful mutation.
    """

    axes: Axes
    artists: tuple[Artist, ...]
    plan: FinishPlan

    @property
    def diagnostics(self) -> tuple[str, ...]:
        """Return non-fatal diagnostics recorded during planning."""
        return self.plan.diagnostics


@dataclass
class _FinishState:
    subtitle: Text | None = None
    caption: Text | None = None
    title_artist: Text | None = None
    title_base_transform: Transform | None = None


@dataclass(frozen=True)
class _TextSnapshot:
    artist: Text
    axes: Axes | None
    text: str
    position: tuple[float, float]
    transform: Transform
    horizontalalignment: HorizontalAlignment
    verticalalignment: VerticalAlignment
    fontsize: float
    fontfamily: tuple[str, ...]
    color: Any
    clip_on: bool
    in_layout: bool


_STATES: weakref.WeakKeyDictionary[Axes, _FinishState] = weakref.WeakKeyDictionary()


def _snapshot_text(artist: Text) -> _TextSnapshot:
    return _TextSnapshot(
        artist=artist,
        axes=cast(Axes | None, artist.axes),
        text=artist.get_text(),
        position=artist.get_position(),
        transform=artist.get_transform(),
        horizontalalignment=cast(HorizontalAlignment, artist.get_horizontalalignment()),
        verticalalignment=cast(VerticalAlignment, artist.get_verticalalignment()),
        fontsize=float(artist.get_fontsize()),
        fontfamily=tuple(artist.get_fontfamily()),
        color=artist.get_color(),
        clip_on=artist.get_clip_on(),
        in_layout=artist.get_in_layout(),
    )


def _restore_text(snapshot: _TextSnapshot) -> None:
    artist = snapshot.artist
    if snapshot.axes is not None and artist.axes is None:
        snapshot.axes.add_artist(artist)
    artist.set_text(snapshot.text)
    artist.set_position(snapshot.position)
    artist.set_transform(snapshot.transform)
    artist.set_horizontalalignment(snapshot.horizontalalignment)
    artist.set_verticalalignment(snapshot.verticalalignment)
    artist.set_fontsize(snapshot.fontsize)
    artist.set_fontfamily(snapshot.fontfamily)
    artist.set_color(snapshot.color)
    artist.set_clip_on(snapshot.clip_on)
    artist.set_in_layout(snapshot.in_layout)


def _title_artists(ax: Axes) -> dict[str, Text]:
    # Matplotlib exposes the center title as ``ax.title`` but not the Text objects
    # for its public left/right title locations. Keep the compatibility boundary
    # isolated here and exercise all three locations in the supported-version jobs.
    return {
        "left": cast(Text, ax._left_title),  # type: ignore[attr-defined]
        "center": ax.title,
        "right": cast(Text, ax._right_title),  # type: ignore[attr-defined]
    }


def _active_title(
    ax: Axes, state: _FinishState, preferred: HorizontalAlignment
) -> tuple[HorizontalAlignment, Text]:
    titles = _title_artists(ax)
    if state.title_artist in titles.values():
        for location, artist in titles.items():
            if artist is state.title_artist:
                return cast(HorizontalAlignment, location), artist

    order = (
        preferred,
        *(name for name in ("left", "center", "right") if name != preferred),
    )
    for location in order:
        if titles[location].get_text():
            return cast(HorizontalAlignment, location), titles[location]
    return preferred, titles[preferred]


def _attached(artist: Text | None, ax: Axes) -> bool:
    return artist is not None and artist.axes is ax and artist in ax.texts


def _font_size(value: float | str | None) -> float:
    return float(FontProperties(size=value).get_size_in_points())


def _root_figure(ax: Axes) -> Figure:
    figure = ax.figure
    while isinstance(figure, SubFigure):
        figure = figure.get_figure()
    return cast(Figure, figure)


def _value(parameters: Mapping[str, object], key: str) -> object:
    return parameters.get(key, cast(Any, mpl.rcParams)[key])


def _subtitle_transform(ax: Axes, parameters: Mapping[str, object]) -> Transform:
    offset = max(3.0, float(cast(Any, _value(parameters, "axes.titlepad"))) / 2)
    return ax.transAxes + ScaledTranslation(
        0, offset / 72, _root_figure(ax).dpi_scale_trans
    )


def _caption_transform(ax: Axes, parameters: Mapping[str, object]) -> Transform:
    label_size = _font_size(cast(Any, _value(parameters, "axes.labelsize")))
    tick_size = _font_size(cast(Any, _value(parameters, "xtick.labelsize")))
    tick_pad = float(cast(Any, _value(parameters, "xtick.major.pad")))
    offset = label_size + tick_size + tick_pad + 10
    return ax.transAxes + ScaledTranslation(
        0, -offset / 72, _root_figure(ax).dpi_scale_trans
    )


def _title_transform(
    ax: Axes, base: Transform, subtitle: str, subtitle_size: float
) -> Transform:
    lines = max(1, subtitle.count("\n") + 1)
    extra = lines * subtitle_size * 1.3
    return base + ScaledTranslation(0, extra / 72, _root_figure(ax).dpi_scale_trans)


def _validate_request(
    ax: object,
    *,
    title: object,
    subtitle: object,
    caption: object,
    theme: object,
    x: object,
    y: object,
    dry_run: object,
) -> tuple[Axes, ThemeSpec | None]:
    if not isinstance(ax, Axes):
        raise TypeError(f"ax must be a matplotlib Axes, got {ax!r}")
    _optional_string("title", title)
    _managed_text("subtitle", subtitle)
    _managed_text("caption", caption)
    if theme is None:
        resolved_theme = None
    elif isinstance(theme, ThemeSpec):
        resolved_theme = theme
    elif isinstance(theme, str):
        resolved_theme = theme_spec(theme)
    else:
        raise TypeError(f"theme must be a string, ThemeSpec, or None, got {theme!r}")
    if x is not None and not isinstance(x, AxisSpec):
        raise TypeError(f"x must be an AxisSpec or None, got {x!r}")
    if y is not None and not isinstance(y, AxisSpec):
        raise TypeError(f"y must be an AxisSpec or None, got {y!r}")
    if not isinstance(dry_run, bool):
        raise TypeError(f"dry_run must be a bool, got {dry_run!r}")
    return ax, resolved_theme


def _resolved_outer_text(
    requested: ManagedText, existing: Text | None, ax: Axes
) -> str | None:
    if requested is False:
        return None
    if isinstance(requested, str):
        return requested
    if _attached(existing, ax):
        return cast(Text, existing).get_text()
    return None


def _build_plan(
    ax: Axes,
    *,
    title: str | None,
    subtitle: ManagedText,
    caption: ManagedText,
    theme: ThemeSpec | None,
    x: AxisSpec | None,
    y: AxisSpec | None,
) -> FinishPlan:
    changes: list[str] = []
    if theme is not None:
        changes.append("apply-theme")
    if title is not None:
        changes.append("set-title")
    for name, specification in (("x", x), ("y", y)):
        if specification is not None and specification.title is not None:
            changes.append(f"set-{name}-title")
        if specification is not None and specification.labels is not None:
            changes.append(f"set-{name}-labels")
    if subtitle is not None:
        changes.append("remove-subtitle" if subtitle is False else "set-subtitle")
    if caption is not None:
        changes.append("remove-caption" if caption is False else "set-caption")

    state = _STATES.get(ax, _FinishState())
    has_outer_text = any(
        value is not None
        for value in (
            _resolved_outer_text(subtitle, state.subtitle, ax),
            _resolved_outer_text(caption, state.caption, ax),
        )
    )
    layout_action: LayoutAction = (
        "enable-constrained"
        if has_outer_text and _root_figure(ax).get_layout_engine() is None
        else "unchanged"
    )
    return FinishPlan(
        title=title,
        subtitle=subtitle,
        caption=caption,
        theme=theme,
        x=x,
        y=y,
        managed_changes=tuple(changes),
        layout_action=layout_action,
        diagnostics=_theme_diagnostics(theme) if theme is not None else (),
    )


def _apply_managed_text(
    ax: Axes,
    artist: Text | None,
    text: str,
    *,
    position: tuple[float, float],
    transform: Transform,
    horizontalalignment: HorizontalAlignment,
    verticalalignment: VerticalAlignment,
    fontsize: float,
    color: object,
    family: object,
) -> Text:
    if not _attached(artist, ax):
        return ax.text(
            *position,
            text,
            transform=transform,
            ha=horizontalalignment,
            va=verticalalignment,
            fontsize=fontsize,
            color=color,
            family=family,
            clip_on=False,
            in_layout=True,
        )
    assert artist is not None
    artist.set_text(text)
    artist.set_position(position)
    artist.set_transform(transform)
    artist.set_horizontalalignment(horizontalalignment)
    artist.set_verticalalignment(verticalalignment)
    artist.set_fontsize(fontsize)
    artist.set_color(cast(Any, color))
    artist.set_fontfamily(cast(Any, family))
    artist.set_clip_on(False)
    artist.set_in_layout(True)
    return artist


def _remove_if_attached(artist: Text | None, ax: Axes) -> None:
    if _attached(artist, ax):
        cast(Text, artist).remove()


def _commit(ax: Axes, plan: FinishPlan) -> FinishResult:
    previous = _STATES.get(ax, _FinishState())
    state = _FinishState(
        subtitle=previous.subtitle if _attached(previous.subtitle, ax) else None,
        caption=previous.caption if _attached(previous.caption, ax) else None,
        title_artist=previous.title_artist,
        title_base_transform=previous.title_base_transform,
    )
    figure = _root_figure(ax)
    layout_before = figure.get_layout_engine()
    texts_before = tuple(ax.texts)
    title_snapshots = tuple(_snapshot_text(item) for item in _title_artists(ax).values())
    xlabel_before = ax.xaxis.label.get_text()
    ylabel_before = ax.yaxis.label.get_text()
    xformatter_before = ax.xaxis.get_major_formatter()
    yformatter_before = ax.yaxis.get_major_formatter()
    existing_managed = tuple(
        _snapshot_text(item) for item in (state.subtitle, state.caption) if item is not None
    )

    affected: list[Artist] = []
    theme_application = None
    parameters: Mapping[str, object]
    try:
        if plan.theme is not None:
            theme_application = _apply_theme_to_axes(ax, plan.theme)
            affected.extend(theme_application.artists)
            parameters = theme_params(plan.theme)
        else:
            parameters = MappingProxyType({})
        if plan.layout_action == "enable-constrained":
            figure.set_layout_engine("constrained")

        preferred = cast(HorizontalAlignment, str(_value(parameters, "axes.titlelocation")))
        location, title_artist = _active_title(ax, state, preferred)
        if plan.title is not None:
            title_artist = _title_artists(ax)[preferred]
            location = preferred
            if state.title_artist is not title_artist:
                if (
                    state.title_artist is not None
                    and state.title_base_transform is not None
                ):
                    state.title_artist.set_transform(state.title_base_transform)
                state.title_artist = title_artist
                state.title_base_transform = title_artist.get_transform()
            elif state.title_base_transform is not None:
                title_artist.set_transform(state.title_base_transform)
            title_artist.set_text(plan.title)
            affected.append(title_artist)

        subtitle = _resolved_outer_text(plan.subtitle, state.subtitle, ax)
        if subtitle is not None:
            subtitle_size = _font_size(cast(Any, _value(parameters, "axes.labelsize")))
            state.subtitle = _apply_managed_text(
                ax,
                state.subtitle,
                subtitle,
                position={"left": (0, 1), "center": (0.5, 1), "right": (1, 1)}[location],
                transform=_subtitle_transform(ax, parameters),
                horizontalalignment=location,
                verticalalignment="bottom",
                fontsize=subtitle_size,
                color=_value(parameters, "axes.labelcolor"),
                family=_value(parameters, "font.family"),
            )
            if title_artist.get_text():
                if state.title_artist is not title_artist:
                    if (
                        state.title_artist is not None
                        and state.title_base_transform is not None
                    ):
                        state.title_artist.set_transform(state.title_base_transform)
                    state.title_artist = title_artist
                    state.title_base_transform = title_artist.get_transform()
                assert state.title_base_transform is not None
                title_artist.set_transform(
                    _title_transform(
                        ax, state.title_base_transform, subtitle, subtitle_size
                    )
                )
            affected.append(state.subtitle)
        else:
            if state.title_artist is not None and state.title_base_transform is not None:
                state.title_artist.set_transform(state.title_base_transform)
            if plan.subtitle is False:
                _remove_if_attached(state.subtitle, ax)
            state.subtitle = None

        caption = _resolved_outer_text(plan.caption, state.caption, ax)
        if caption is not None:
            state.caption = _apply_managed_text(
                ax,
                state.caption,
                caption,
                position=(1, 0),
                transform=_caption_transform(ax, parameters),
                horizontalalignment="right",
                verticalalignment="top",
                fontsize=_font_size(cast(Any, _value(parameters, "xtick.labelsize"))),
                color=_value(parameters, "axes.labelcolor"),
                family=_value(parameters, "font.family"),
            )
            affected.append(state.caption)
        else:
            if plan.caption is False:
                _remove_if_attached(state.caption, ax)
            state.caption = None

        for specification, matplotlib_axis, label_artist in (
            (plan.x, ax.xaxis, ax.xaxis.label),
            (plan.y, ax.yaxis, ax.yaxis.label),
        ):
            if specification is None:
                continue
            if specification.title is not None:
                label_artist.set_text(specification.title)
                affected.append(label_artist)
            if specification.labels is not None:
                matplotlib_axis.set_major_formatter(as_formatter(specification.labels))

    except Exception:
        for artist in tuple(ax.texts):
            if artist not in texts_before:
                artist.remove()
        for snapshot in (*title_snapshots, *existing_managed):
            _restore_text(snapshot)
        ax.xaxis.label.set_text(xlabel_before)
        ax.yaxis.label.set_text(ylabel_before)
        ax.xaxis.set_major_formatter(xformatter_before)
        ax.yaxis.set_major_formatter(yformatter_before)
        if figure.get_layout_engine() is not layout_before:
            figure.set_layout_engine(layout_before)
        if theme_application is not None:
            theme_application.rollback()
        raise

    _STATES[ax] = state
    for managed_artist in (state.subtitle, state.caption):
        if _attached(managed_artist, ax) and managed_artist not in affected:
            affected.append(cast(Text, managed_artist))
    return FinishResult(axes=ax, artists=tuple(dict.fromkeys(affected)), plan=plan)


@overload
def finish(
    ax: Axes,
    *,
    title: str | None = None,
    subtitle: ManagedText = None,
    caption: ManagedText = None,
    theme: str | ThemeSpec | None = None,
    x: AxisSpec | None = None,
    y: AxisSpec | None = None,
    dry_run: Literal[True],
) -> FinishPlan: ...


@overload
def finish(
    ax: Axes,
    *,
    title: str | None = None,
    subtitle: ManagedText = None,
    caption: ManagedText = None,
    theme: str | ThemeSpec | None = None,
    x: AxisSpec | None = None,
    y: AxisSpec | None = None,
    dry_run: Literal[False] = False,
) -> FinishResult: ...


@overload
def finish(
    ax: Axes,
    *,
    title: str | None = None,
    subtitle: ManagedText = None,
    caption: ManagedText = None,
    theme: str | ThemeSpec | None = None,
    x: AxisSpec | None = None,
    y: AxisSpec | None = None,
    dry_run: bool,
) -> FinishPlan | FinishResult: ...


def finish(
    ax: Axes,
    *,
    title: str | None = None,
    subtitle: ManagedText = None,
    caption: ManagedText = None,
    theme: str | ThemeSpec | None = None,
    x: AxisSpec | None = None,
    y: AxisSpec | None = None,
    dry_run: bool = False,
) -> FinishPlan | FinishResult:
    """
    Apply coherent labels to an existing Matplotlib axes transactionally.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Existing axes to finish. The axes and its data artists are not wrapped.
    title : str or None, optional
        Plot title. ``None`` leaves every existing title unchanged.
    subtitle : str, False, or None, optional
        Layout-managed subtitle. ``None`` leaves an existing ggstyle subtitle
        unchanged and ``False`` removes it.
    caption : str, False, or None, optional
        Layout-managed caption. ``None`` leaves an existing ggstyle caption unchanged
        and ``False`` removes it.
    theme : str, ThemeSpec, or None, optional
        Complete theme for the existing axes. Only safely retroactive properties are
        applied; the plan reports preserved creation-, data-, and output-time settings.
    x : AxisSpec or None, optional
        X-axis title and numeric label policy.
    y : AxisSpec or None, optional
        Y-axis title and numeric label policy.
    dry_run : bool, default False
        Return the validated plan without changing Matplotlib state when true.

    Returns
    -------
    FinishResult or FinishPlan
        Native axes and artists after commit, or an immutable plan for a dry run.

    Raises
    ------
    TypeError
        If an argument has the wrong type.

    Notes
    -----
    A subtitle or caption participates in the active figure layout. If no layout
    engine is configured, ggstyle enables constrained layout for that figure. Existing
    layout engines are preserved. Validation and dry runs never draw the canvas or
    mutate the axes, artists, figure, or global ``rcParams``.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> fig, ax = plt.subplots()
    >>> result = finish(
    ...     ax,
    ...     title="Revenue",
    ...     subtitle="Trailing twelve months",
    ...     caption="Source: annual report",
    ...     x=axis(title="Date"),
    ... )
    >>> result.axes is ax
    True
    >>> plt.close(fig)
    """
    resolved_ax, resolved_theme = _validate_request(
        ax,
        title=title,
        subtitle=subtitle,
        caption=caption,
        theme=theme,
        x=x,
        y=y,
        dry_run=dry_run,
    )
    plan = _build_plan(
        resolved_ax,
        title=title,
        subtitle=subtitle,
        caption=caption,
        theme=resolved_theme,
        x=x,
        y=y,
    )
    if dry_run:
        return plan
    return _commit(resolved_ax, plan)
