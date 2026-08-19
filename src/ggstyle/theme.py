"""Theme application.

Two themes ship: ``"minimal"`` (the default) and ``"grey"``. Both spell out the
same type scale and colour cycle, so switching changes the panel surface and
nothing else.

Importing ``ggstyle`` never mutates ``rcParams``. Theming is always something the
caller asks for, either process-wide via :func:`use_theme` or scoped via
:class:`theme`.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

import matplotlib.pyplot as plt

__all__ = ["DEFAULT_THEME", "available_themes", "theme", "use_theme"]

#: Themes in preference order. ``minimal`` is the default; ``grey`` is the
#: ggplot2 theme_grey analogue, kept for fidelity.
_THEMES = {
    "minimal": "ggstyle-minimal.mplstyle",
    "grey": "ggstyle-grey.mplstyle",
}

#: Spelling and intent aliases. Americans write "gray".
_ALIASES = {
    "gray": "grey",
    "default": "minimal",
    "ggstyle": "minimal",
    "theme_minimal": "minimal",
    "theme_grey": "grey",
    "theme_gray": "grey",
}

DEFAULT_THEME = "minimal"

_THEME_DIR = Path(__file__).parent / "themes"


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
    use_theme : Apply a theme process-wide.

    Examples
    --------
    >>> available_themes()
    ['minimal', 'grey']
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


def use_theme(name: str = DEFAULT_THEME) -> None:
    """
    Apply a theme to matplotlib process-wide.

    This function delegates to matplotlib's style system and intentionally
    changes global ``rcParams``.

    Parameters
    ----------
    name : str, default "minimal"
        Theme name or accepted alias.

    See Also
    --------
    theme : Apply a theme temporarily.
    stylesheet : Return a theme's stylesheet path.

    Notes
    -----
    ``gs.use_theme()`` applies ``"minimal"``; ``gs.use_theme("grey")`` applies the
    ggplot2-style grey panel. ``"gray"`` is accepted for ``"grey"``.

    Examples
    --------
    >>> use_theme("minimal")
    """
    plt.style.use(str(stylesheet(name)))


class theme:
    """
    Temporarily apply a matplotlib theme.

    Parameters
    ----------
    name : str, default "minimal"
        Theme name or accepted alias.

    See Also
    --------
    use_theme : Apply a theme process-wide.
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

    def __init__(self, name: str = DEFAULT_THEME) -> None:
        self.name = _canonical(name)
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
