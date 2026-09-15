"""Deterministic figure builders shared by visual tests and baseline tooling."""

from __future__ import annotations

import locale
import time
from collections.abc import Callable
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.ft2font
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import PIL
import pytest
from matplotlib.axes import Axes
from matplotlib.figure import Figure

import ggstyle as gs

FigureBuilder = Callable[[], Figure]

_DATES = pd.DatetimeIndex(
    ["2024-01-02", "2024-01-03", "2024-01-08", "2024-01-09", "2024-01-19"]
)
_VALUES = np.array([1.0, 2.4, 1.8, 3.2, 2.7])
_COLORS = ("#0072B2", "#D55E00")


def _new_subplots(
    rows: int = 1, columns: int = 1, *, height: float = 2.8
) -> tuple[Figure, np.ndarray]:
    with gs.theme("test"):
        figure, axes = plt.subplots(
            rows,
            columns,
            figsize=(5.6, height),
            dpi=100,
            squeeze=False,
        )
    figure.subplots_adjust(left=0.12, right=0.92, bottom=0.2, top=0.84, hspace=0.55)
    return figure, axes


def _configure_date_axis(
    ax: Axes, title: str, ticks: pd.DatetimeIndex = _DATES
) -> gs.DateAxis:
    handle = gs.dates(ax).ticks(at=ticks).fmt("%b %d")
    ax.set_title(title)
    ax.set_ylabel("value")
    ax.set_ylim(0.6, 3.8)
    return handle


def line_modes() -> Figure:
    """Build expanded and collapsed views of one irregular line."""
    figure, axes = _new_subplots(1, 2, height=2.6)
    expanded, collapsed = axes[0]
    for ax in (expanded, collapsed):
        ax.plot(_DATES, _VALUES, marker="o", color=_COLORS[0])

    _configure_date_axis(expanded, "Expanded", _DATES[[0, 2, 4]])
    collapsed_handle = _configure_date_axis(collapsed, "Collapsed").collapse()

    assert np.allclose(
        np.asarray(expanded.lines[0].get_xdata(orig=False), dtype=float),
        mdates.date2num(_DATES),
    )
    assert np.allclose(
        np.asarray(collapsed.lines[0].get_xdata(orig=False), dtype=float),
        mdates.date2num(_DATES),
    )
    assert np.allclose(
        collapsed.xaxis.get_transform().transform(mdates.date2num(_DATES)),
        np.arange(len(_DATES), dtype=float),
    )
    assert collapsed_handle.loc(_DATES[-1]) == mdates.date2num(_DATES[-1])
    return figure


def annotation_modes() -> Figure:
    """Build date-space annotations in expanded and collapsed modes."""
    figure, axes = _new_subplots(2, 1, height=4.4)
    for index, ax in enumerate(axes[:, 0]):
        ax.plot(_DATES, _VALUES, marker="o", color=_COLORS[0])
        title = "Annotations — collapsed" if index else "Annotations — expanded"
        ticks = _DATES if index else _DATES[[0, 2, 4]]
        handle = _configure_date_axis(ax, title, ticks)
        if index:
            handle.collapse()
        handle.span("2024-01-03", "2024-01-09", color="#E69F00", alpha=0.2)
        handle.vline("2024-01-08", label="release", color=_COLORS[1])

        assert len(handle._annotations) == 2
        assert sum(len(item.artists) for item in handle._annotations) == 3
    return figure


def synchronized_panels() -> Figure:
    """Build synchronized panels with distinct observation sets."""
    figure, axes = _new_subplots(2, 1, height=4.4)
    left_dates = _DATES[:4]
    right_dates = _DATES[1:]
    axes[0, 0].plot(left_dates, _VALUES[:4], marker="o", color=_COLORS[0])
    axes[1, 0].plot(right_dates, _VALUES[1:], marker="s", color=_COLORS[1])

    handles = gs.sync_dates(axes[:, 0], mode="collapse")
    for ax, handle, title in zip(
        axes[:, 0], handles, ("Panel A", "Panel B"), strict=True
    ):
        handle.ticks(at=_DATES).fmt("%b %d")
        ax.set_title(title)
        ax.set_ylabel("value")

    assert np.allclose(axes[0, 0].get_xlim(), axes[1, 0].get_xlim())
    assert handles[0].loc(_DATES[2]) == handles[1].loc(_DATES[2])
    return figure


def theme_gallery() -> Figure:
    """Build a compact gallery containing every bundled theme."""
    figure = plt.figure(figsize=(7.2, 6.0), dpi=100, facecolor="white")
    names = gs.available_themes()
    for index, name in enumerate(names, start=1):
        with gs.theme(name):
            ax = figure.add_subplot(3, 3, index)
            x = np.array([0.0, 1.0, 2.0, 3.0])
            ax.plot(x, [0.8, 2.2, 1.5, 2.7], marker="o")
            ax.plot(x, [2.4, 1.7, 2.6, 1.1], marker="s")
            ax.set_title(name)
            ax.set_xlim(-0.2, 3.2)
            ax.set_ylim(0.5, 3.0)
            ax.set_xticks([0, 1, 2, 3])
            ax.set_yticks([1, 2, 3])

    assert len(figure.axes) == len(names) == 9
    figure.subplots_adjust(
        left=0.07,
        right=0.98,
        bottom=0.07,
        top=0.95,
        wspace=0.38,
        hspace=0.5,
    )
    return figure


CASES: dict[str, FigureBuilder] = {
    "line_modes": line_modes,
    "annotation_modes": annotation_modes,
    "synchronized_panels": synchronized_panels,
    "theme_gallery": theme_gallery,
}


def write_png(figure: Figure, destination: Path) -> None:
    """Render a figure through its Agg canvas without savefig layout metadata."""
    figure.canvas.draw()
    figure.canvas.print_png(destination, metadata={"Software": "ggstyle visual tests"})


def verify_visual_environment() -> None:
    """Raise with every mismatch when the canonical renderer is not active."""
    expected_versions = {
        "Matplotlib": "3.11.1",
        "NumPy": "2.5.2",
        "pandas": "3.0.5",
        "Pillow": "12.3.0",
        "pytest": "9.1.1",
        "FreeType": "2.14.3",
    }
    actual_versions = {
        "Matplotlib": matplotlib.__version__,
        "NumPy": np.__version__,
        "pandas": pd.__version__,
        "Pillow": PIL.__version__,
        "pytest": pytest.__version__,
        "FreeType": matplotlib.ft2font.__freetype_version__,
    }
    mismatches = [
        f"{name}={actual} (expected {expected_versions[name]})"
        for name, actual in actual_versions.items()
        if actual != expected_versions[name]
    ]

    backend = matplotlib.get_backend().lower()
    if backend != "agg":
        mismatches.append(f"backend={backend} (expected agg)")
    active_locale = locale.setlocale(locale.LC_ALL, None)
    if active_locale != "C":
        mismatches.append(f"locale={active_locale} (expected C)")
    if time.tzname != ("UTC", "UTC"):
        mismatches.append(f"timezone={time.tzname!r} (expected ('UTC', 'UTC'))")
    font = Path(fm.findfont(fm.FontProperties(family=["DejaVu Sans"]))).name
    if not font.startswith("DejaVuSans"):
        mismatches.append(f"font={font} (expected DejaVuSans*)")

    if mismatches:
        details = "\n- ".join(mismatches)
        raise RuntimeError(f"visual environment mismatch:\n- {details}")
