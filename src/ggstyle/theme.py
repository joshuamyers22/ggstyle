"""Theme application.

Nine ggplot2-inspired themes ship. ``"minimal"`` remains the default. The
presentation themes share a type scale and colour cycle, so switching changes
the non-data surface rather than the plot's identity.

Importing ``ggstyle`` never mutates ``rcParams``. Theming is always something the
caller asks for: process-wide via :func:`use_theme`, scoped via :class:`theme`, or
resolved as pure policy via :func:`theme_params` for an existing axes.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from numbers import Real
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Any, cast

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.text import Text

__all__ = [
    "DEFAULT_THEME",
    "ThemeSpec",
    "available_themes",
    "stylesheet",
    "theme",
    "theme_params",
    "theme_spec",
    "use_theme",
]

#: Themes in preference order. ``minimal`` is the default; ``grey`` is the
#: ggplot2 theme_grey analogue, kept for fidelity.
_THEMES = {
    "minimal": "ggstyle-minimal.mplstyle",
    "grey": "ggstyle-grey.mplstyle",
    "bw": "ggstyle-bw.mplstyle",
    "linedraw": "ggstyle-linedraw.mplstyle",
    "light": "ggstyle-light.mplstyle",
    "dark": "ggstyle-dark.mplstyle",
    "classic": "ggstyle-classic.mplstyle",
    "void": "ggstyle-void.mplstyle",
    "test": "ggstyle-test.mplstyle",
}

#: Spelling and intent aliases. Americans write "gray".
_ALIASES = {
    "gray": "grey",
    "default": "minimal",
    "ggstyle": "minimal",
    "theme_minimal": "minimal",
    "theme_grey": "grey",
    "theme_gray": "grey",
    "theme_bw": "bw",
    "theme_linedraw": "linedraw",
    "theme_light": "light",
    "theme_dark": "dark",
    "theme_classic": "classic",
    "theme_void": "void",
    "theme_test": "test",
}

DEFAULT_THEME = "minimal"

_THEME_DIR = Path(__file__).parent / "themes"

_TEXT_SIZE_KEYS = (
    "font.size",
    "axes.titlesize",
    "axes.labelsize",
    "xtick.labelsize",
    "ytick.labelsize",
    "legend.fontsize",
    "legend.title_fontsize",
)

# Operational rcParams are intentionally excluded from Matplotlib style files. Keep the
# same boundary without importing matplotlib.style.core's private blacklist.
_NON_STYLE_OVERRIDES = frozenset(
    {
        "backend",
        "backend_fallback",
        "date.epoch",
        "docstring.hardcopy",
        "figure.max_open_warning",
        "figure.raise_window",
        "interactive",
        "savefig.directory",
        "timezone",
        "tk.window_focus",
        "toolbar",
        "webagg.address",
        "webagg.open_in_browser",
        "webagg.port",
        "webagg.port_retries",
    }
)

_EXISTING_AXES_KEYS = frozenset(
    {
        "axes.axisbelow",
        "axes.edgecolor",
        "axes.facecolor",
        "axes.labelcolor",
        "axes.labelpad",
        "axes.labelsize",
        "axes.linewidth",
        "axes.spines.bottom",
        "axes.spines.left",
        "axes.spines.right",
        "axes.spines.top",
        "axes.titlecolor",
        "axes.titlesize",
        "axes.grid",
        "axes.grid.axis",
        "figure.edgecolor",
        "figure.facecolor",
        "font.family",
        "grid.alpha",
        "grid.color",
        "grid.linestyle",
        "grid.linewidth",
        "legend.fontsize",
        "legend.frameon",
        "legend.title_fontsize",
        "xtick.bottom",
        "xtick.color",
        "xtick.labelbottom",
        "xtick.labelcolor",
        "xtick.labelsize",
        "xtick.labeltop",
        "xtick.major.pad",
        "xtick.major.size",
        "xtick.major.width",
        "xtick.minor.pad",
        "xtick.minor.size",
        "xtick.minor.width",
        "xtick.top",
        "ytick.color",
        "ytick.labelcolor",
        "ytick.labelleft",
        "ytick.labelright",
        "ytick.labelsize",
        "ytick.left",
        "ytick.major.pad",
        "ytick.major.size",
        "ytick.major.width",
        "ytick.minor.pad",
        "ytick.minor.size",
        "ytick.minor.width",
        "ytick.right",
    }
)


def _positive_size(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"base_size must be a positive real number, got {value!r}")
    resolved = float(value)
    if not math.isfinite(resolved) or resolved <= 0:
        raise ValueError(f"base_size must be finite and positive, got {value!r}")
    return resolved


def _family(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"base_family must be a non-empty string, got {value!r}")
    if not value.strip():
        raise ValueError("base_family must be a non-empty string")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _validated_override(key: object, value: object) -> tuple[str, object]:
    if not isinstance(key, str):
        raise TypeError(f"theme override names must be strings, got {key!r}")
    if key not in mpl.rcParams:
        raise ValueError(f"unknown Matplotlib rcParam override {key!r}")
    if key in _NON_STYLE_OVERRIDES:
        raise ValueError(f"theme override {key!r} is not a presentation-style rcParam")
    validated = mpl.RcParams()
    dynamic_params = cast(Any, validated)
    try:
        dynamic_params[key] = value
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid value for theme override {key!r}: {value!r}") from error
    return key, _freeze(dynamic_params[key])


@dataclass(frozen=True)
class ThemeSpec:
    """
    Describe an immutable parameterized ggstyle theme.

    Parameters
    ----------
    name : str, default "minimal"
        Canonical theme name or accepted alias.
    base_size : float or None, optional
        Base font size in points. Related theme text sizes scale proportionally.
        ``None`` preserves the packaged stylesheet values exactly.
    base_family : str or None, optional
        Font family used by the theme. ``None`` preserves the stylesheet family.
    overrides : mapping or None, optional
        Explicit Matplotlib rcParam replacements. Values are validated immediately
        and defensively copied; explicit overrides win over base scaling.

    Notes
    -----
    A specification is pure policy and does not change ``rcParams``. Pass it to
    :func:`theme_params`, :class:`theme`, :func:`use_theme`, or ``ggstyle.finish``.
    """

    name: str = DEFAULT_THEME
    base_size: float | None = None
    base_family: str | None = None
    overrides: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(f"theme name must be a string, got {self.name!r}")
        object.__setattr__(self, "name", _canonical(self.name))
        if self.base_size is not None:
            object.__setattr__(self, "base_size", _positive_size(self.base_size))
        if self.base_family is not None:
            object.__setattr__(self, "base_family", _family(self.base_family))
        if self.overrides is None:
            resolved: dict[str, object] = {}
        elif not isinstance(self.overrides, Mapping):
            raise TypeError(
                f"theme overrides must be a mapping or None, got {self.overrides!r}"
            )
        else:
            resolved = dict(
                _validated_override(key, value) for key, value in self.overrides.items()
            )
        object.__setattr__(self, "overrides", MappingProxyType(resolved))


def theme_spec(
    name: str = DEFAULT_THEME,
    *,
    base_size: float | None = None,
    base_family: str | None = None,
    overrides: Mapping[str, object] | None = None,
) -> ThemeSpec:
    """
    Create an immutable, validated theme specification.

    Parameters
    ----------
    name : str, default "minimal"
        Canonical theme name or accepted alias.
    base_size : float or None, optional
        Base font size in points.
    base_family : str or None, optional
        Font family name.
    overrides : mapping or None, optional
        Matplotlib rcParam values applied after base size and family resolution.

    Returns
    -------
    ThemeSpec
        Reusable theme policy that retains no Matplotlib artists.

    Examples
    --------
    >>> specification = theme_spec("minimal", base_size=11)
    >>> specification.name
    'minimal'
    """
    return ThemeSpec(
        name=name,
        base_size=base_size,
        base_family=base_family,
        overrides=overrides,
    )


@lru_cache(maxsize=len(_THEMES))
def _stylesheet_params(name: str) -> dict[str, object]:
    loaded = mpl.rc_params_from_file(
        str(stylesheet(name)), fail_on_error=True, use_default_template=False
    )
    return dict(cast(Mapping[str, object], loaded).items())


def theme_params(
    specification: str | ThemeSpec = DEFAULT_THEME,
) -> Mapping[str, object]:
    """
    Return a validated, read-only parameter mapping for one theme.

    Parameters
    ----------
    specification : str or ThemeSpec, default "minimal"
        Packaged theme name or parameterized theme specification.

    Returns
    -------
    collections.abc.Mapping
        Read-only resolved rcParam mapping suitable for ``matplotlib.rc_context`` or
        third-party integrations.

    Raises
    ------
    TypeError
        If ``specification`` is neither a string nor a :class:`ThemeSpec`.

    Notes
    -----
    Calling this function does not mutate Matplotlib global configuration. Returned
    sequences are immutable defensive values.

    Examples
    --------
    >>> parameters = theme_params(theme_spec("minimal", base_size=11))
    >>> parameters["font.size"]
    11.0
    """
    if isinstance(specification, str):
        resolved = theme_spec(specification)
    elif isinstance(specification, ThemeSpec):
        resolved = specification
    else:
        raise TypeError(
            f"theme specification must be a string or ThemeSpec, got {specification!r}"
        )

    parameters = _stylesheet_params(resolved.name).copy()
    if resolved.base_size is not None:
        original_size = float(cast(Any, parameters["font.size"]))
        ratio = resolved.base_size / original_size
        for key in _TEXT_SIZE_KEYS:
            if key in parameters:
                parameters[key] = float(cast(Any, parameters[key])) * ratio
    if resolved.base_family is not None:
        parameters["font.family"] = (resolved.base_family,)
    assert resolved.overrides is not None
    parameters.update(resolved.overrides)
    return MappingProxyType({key: _freeze(value) for key, value in parameters.items()})


def available_themes() -> list[str]:
    """
    Return available theme names in preference order.

    Theme aliases are excluded. The first entry is the default used by
    :func:`use_theme` and :class:`theme`.

    Returns
    -------
    list of str
        Canonical names with the default theme first.

    See Also
    --------
    stylesheet : Return the stylesheet for a theme.
    theme_spec : Create a parameterized theme recipe.
    use_theme : Apply a theme process-wide.

    Examples
    --------
    >>> available_themes()
    ['minimal', 'grey', 'bw', 'linedraw', 'light', 'dark', 'classic', 'void', 'test']
    """
    return list(_THEMES)


def _canonical(name: str) -> str:
    key = str(name).strip().lower().replace("_", "-")
    key = _ALIASES.get(key, _ALIASES.get(key.replace("-", "_"), key))
    if key not in _THEMES:
        raise ValueError(
            f"unknown theme {name!r}; available themes are {available_themes()}"
        )
    return key


def stylesheet(name: str = DEFAULT_THEME) -> Path:
    """
    Return the path to a packaged matplotlib stylesheet.

    Accepted aliases are normalized to one of the names returned by
    :func:`available_themes`.

    Parameters
    ----------
    name : str, default "minimal"
        Theme name or accepted alias.

    Returns
    -------
    pathlib.Path
        Existing stylesheet path.

    Raises
    ------
    ValueError
        If ``name`` is unknown.
    FileNotFoundError
        If the installed package is missing the requested stylesheet.

    See Also
    --------
    available_themes : Return canonical theme names.
    theme_params : Resolve a parameterized theme without applying it.
    use_theme : Apply a stylesheet process-wide.

    Examples
    --------
    Useful on its own: ``plt.style.use(gs.stylesheet())`` works without importing
    anything else from this package.
    """
    path = _THEME_DIR / _THEMES[_canonical(name)]
    if not path.exists():  # pragma: no cover - packaging failure
        raise FileNotFoundError(f"stylesheet missing from the installed package: {path}")
    return path


def use_theme(name: str | ThemeSpec = DEFAULT_THEME) -> None:
    """
    Apply a theme to matplotlib process-wide.

    This function delegates to matplotlib's style system and intentionally
    changes global ``rcParams``.

    Parameters
    ----------
    name : str or ThemeSpec, default "minimal"
        Theme name, accepted alias, or parameterized specification.

    See Also
    --------
    theme : Apply a theme temporarily.
    theme_spec : Create a parameterized theme recipe.
    stylesheet : Return a theme's stylesheet path.

    Notes
    -----
    ``gs.use_theme()`` applies ``"minimal"``; ``gs.use_theme("grey")`` applies the
    ggplot2-style grey panel. ggplot2 function spellings such as ``"theme_bw"``
    are accepted as aliases, as is ``"gray"`` for ``"grey"``.

    Examples
    --------
    >>> use_theme("minimal")
    """
    if isinstance(name, ThemeSpec):
        cast(Any, mpl.rcParams).update(dict(theme_params(name)))
    else:
        plt.style.use(str(stylesheet(name)))


class theme:
    """
    Temporarily apply a matplotlib theme.

    Parameters
    ----------
    name : str or ThemeSpec, default "minimal"
        Theme name, accepted alias, or parameterized specification.

    See Also
    --------
    use_theme : Apply a theme process-wide.
    theme_spec : Create a parameterized theme recipe.
    stylesheet : Return a theme's stylesheet path.

    Notes
    -----
    Wraps ``matplotlib.pyplot.style.context``, so every rcParam is restored
    on exit including ones the caller changed inside the block.

    Examples
    --------
    Use the context manager around figure creation::

        with gs.theme("grey"):
            fig, ax = plt.subplots()
    """

    def __init__(self, name: str | ThemeSpec = DEFAULT_THEME) -> None:
        if isinstance(name, ThemeSpec):
            self.name = name.name
            self.specification = name
            self._context = plt.style.context(dict(theme_params(name)))
        else:
            self.name = _canonical(name)
            self.specification = theme_spec(self.name)
            self._context = plt.style.context(str(stylesheet(self.name)))

    def __enter__(self) -> theme:
        self._context.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._context.__exit__(exc_type, exc_value, traceback)

    def __repr__(self) -> str:  # pragma: no cover - display only
        return f"theme({self.name!r})"


@dataclass(frozen=True)
class _ThemeApplication:
    artists: tuple[Artist, ...]
    diagnostics: tuple[str, ...]
    undo: tuple[Callable[[], None], ...]

    def rollback(self) -> None:
        for operation in reversed(self.undo):
            operation()


def _theme_diagnostics(specification: ThemeSpec) -> tuple[str, ...]:
    parameters = theme_params(specification)
    unapplied = sorted(set(parameters) - _EXISTING_AXES_KEYS)
    if not unapplied:
        return ()
    return (
        "Existing-axes theming preserved creation-, data-, or output-time settings: "
        + ", ".join(unapplied),
    )


def _apply_theme_to_axes(ax: Axes, specification: ThemeSpec) -> _ThemeApplication:
    parameters = theme_params(specification)
    undo: list[Callable[[], None]] = []
    artists: list[Artist] = []

    def change(
        getter: Callable[[], Any], setter: Callable[[Any], None], value: object
    ) -> None:
        previous = getter()
        undo.append(lambda: setter(previous))
        setter(value)

    def truncate_ticks(axis: Any, attribute: str, count: int) -> Callable[[], None]:
        def operation() -> None:
            del getattr(axis, attribute)[count:]

        return operation

    def style_text(artist: Text, *, size_key: str, color_key: str | None = None) -> None:
        if size_key in parameters:
            change(artist.get_fontsize, artist.set_fontsize, parameters[size_key])
        if color_key is not None and color_key in parameters:
            color = parameters[color_key]
            if color != "auto":
                change(artist.get_color, artist.set_color, color)
        if "font.family" in parameters:
            change(artist.get_fontfamily, artist.set_fontfamily, parameters["font.family"])
        artists.append(artist)

    def style_line(
        artist: Any,
        *,
        color: object | None = None,
        linewidth: object | None = None,
        linestyle: object | None = None,
        alpha: object | None = None,
        visible: object | None = None,
        markersize: object | None = None,
        markeredgewidth: object | None = None,
    ) -> None:
        if color is not None:
            change(artist.get_color, artist.set_color, color)
        if linewidth is not None:
            change(artist.get_linewidth, artist.set_linewidth, linewidth)
        if linestyle is not None:
            change(artist.get_linestyle, artist.set_linestyle, linestyle)
        if alpha is not None:
            change(artist.get_alpha, artist.set_alpha, alpha)
        if visible is not None:
            change(artist.get_visible, artist.set_visible, visible)
        if markersize is not None:
            change(artist.get_markersize, artist.set_markersize, markersize)
        if markeredgewidth is not None:
            change(
                artist.get_markeredgewidth,
                artist.set_markeredgewidth,
                markeredgewidth,
            )
        artists.append(artist)

    try:
        figure = ax.figure
        if "figure.facecolor" in parameters:
            change(
                figure.get_facecolor, figure.set_facecolor, parameters["figure.facecolor"]
            )
        if "figure.edgecolor" in parameters:
            change(
                figure.get_edgecolor, figure.set_edgecolor, parameters["figure.edgecolor"]
            )
        if "axes.facecolor" in parameters:
            change(ax.get_facecolor, ax.set_facecolor, parameters["axes.facecolor"])
        if "axes.axisbelow" in parameters:
            change(ax.get_axisbelow, ax.set_axisbelow, parameters["axes.axisbelow"])

        for name, spine in ax.spines.items():
            visible_key = f"axes.spines.{name}"
            if visible_key in parameters:
                change(spine.get_visible, spine.set_visible, parameters[visible_key])
            if "axes.edgecolor" in parameters:
                change(
                    spine.get_edgecolor, spine.set_edgecolor, parameters["axes.edgecolor"]
                )
            if "axes.linewidth" in parameters:
                change(
                    spine.get_linewidth, spine.set_linewidth, parameters["axes.linewidth"]
                )
            artists.append(spine)

        titles = (
            cast(Text, ax._left_title),  # type: ignore[attr-defined]
            ax.title,
            cast(Text, ax._right_title),  # type: ignore[attr-defined]
        )
        for title_artist in titles:
            style_text(
                title_artist,
                size_key="axes.titlesize",
                color_key="axes.titlecolor",
            )
        for label in (ax.xaxis.label, ax.yaxis.label):
            style_text(label, size_key="axes.labelsize", color_key="axes.labelcolor")
        if "axes.labelpad" in parameters:
            change(
                lambda: ax.xaxis.labelpad,
                lambda value: setattr(ax.xaxis, "labelpad", value),
                parameters["axes.labelpad"],
            )
            change(
                lambda: ax.yaxis.labelpad,
                lambda value: setattr(ax.yaxis, "labelpad", value),
                parameters["axes.labelpad"],
            )

        grid_axis = parameters.get("axes.grid.axis", "both")
        grid_visible = bool(parameters.get("axes.grid", False))
        for axis_name, matplotlib_axis in (("x", ax.xaxis), ("y", ax.yaxis)):
            dynamic_axis = cast(Any, matplotlib_axis)
            major_count = len(dynamic_axis.majorTicks)
            minor_count = len(dynamic_axis.minorTicks)
            undo.append(truncate_ticks(dynamic_axis, "minorTicks", minor_count))
            undo.append(truncate_ticks(dynamic_axis, "majorTicks", major_count))
            label_size_key = f"{axis_name}tick.labelsize"
            label_color_key = f"{axis_name}tick.labelcolor"
            tick_color = parameters.get(f"{axis_name}tick.color")
            show_primary = parameters.get(
                "xtick.bottom" if axis_name == "x" else "ytick.left"
            )
            show_secondary = parameters.get(
                "xtick.top" if axis_name == "x" else "ytick.right"
            )
            label_primary = parameters.get(
                "xtick.labelbottom" if axis_name == "x" else "ytick.labelleft"
            )
            label_secondary = parameters.get(
                "xtick.labeltop" if axis_name == "x" else "ytick.labelright"
            )
            for level, ticks in (
                ("major", matplotlib_axis.get_major_ticks()),
                ("minor", matplotlib_axis.get_minor_ticks()),
            ):
                size = parameters.get(f"{axis_name}tick.{level}.size")
                width = parameters.get(f"{axis_name}tick.{level}.width")
                pad = parameters.get(f"{axis_name}tick.{level}.pad")
                for tick in ticks:
                    style_line(
                        tick.tick1line,
                        color=tick_color,
                        visible=show_primary,
                        markersize=size,
                        markeredgewidth=width,
                    )
                    style_line(
                        tick.tick2line,
                        color=tick_color,
                        visible=show_secondary,
                        markersize=size,
                        markeredgewidth=width,
                    )
                    style_text(
                        tick.label1,
                        size_key=label_size_key,
                        color_key=label_color_key,
                    )
                    style_text(
                        tick.label2,
                        size_key=label_size_key,
                        color_key=label_color_key,
                    )
                    if label_primary is not None:
                        change(
                            tick.label1.get_visible,
                            tick.label1.set_visible,
                            label_primary,
                        )
                    if label_secondary is not None:
                        change(
                            tick.label2.get_visible,
                            tick.label2.set_visible,
                            label_secondary,
                        )
                    if pad is not None:
                        change(tick.get_pad, tick.set_pad, pad)
                    style_line(
                        tick.gridline,
                        color=parameters.get("grid.color"),
                        linewidth=parameters.get("grid.linewidth"),
                        linestyle=parameters.get("grid.linestyle"),
                        alpha=parameters.get("grid.alpha"),
                        visible=(
                            grid_visible
                            and level == "major"
                            and grid_axis in ("both", axis_name)
                        ),
                    )

        legend = ax.get_legend()
        if legend is not None:
            if "legend.frameon" in parameters:
                change(
                    legend.get_frame_on,
                    legend.set_frame_on,
                    parameters["legend.frameon"],
                )
            for legend_text in legend.get_texts():
                style_text(legend_text, size_key="legend.fontsize")
            style_text(legend.get_title(), size_key="legend.title_fontsize")

    except Exception:
        for operation in reversed(undo):
            operation()
        raise

    return _ThemeApplication(
        artists=tuple(dict.fromkeys(artists)),
        diagnostics=_theme_diagnostics(specification),
        undo=tuple(undo),
    )
