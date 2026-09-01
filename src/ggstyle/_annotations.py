"""Replayable Matplotlib annotation state and rendering."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from matplotlib.artist import Artist
from matplotlib.axes import Axes


@dataclass
class Annotation:
    """Describe a date-space annotation and track its current artists."""

    kind: Literal["vline", "span"]
    dates: tuple[Any, ...]
    label: str | None
    kwargs: dict[str, Any]
    artists: list[Artist] = field(default_factory=list)


def draw(ax: Axes, annotation: Annotation, locate: Callable[[Any], float]) -> None:
    """Render an annotation using the caller's date-to-position mapping."""
    style = dict(annotation.kwargs)
    if annotation.kind == "vline":
        style.setdefault("color", "0.35")
        style.setdefault("linewidth", 1.0)
        style.setdefault("linestyle", "--")
        text_x = locate(annotation.dates[0])
        annotation.artists.append(ax.axvline(text_x, **style))
    else:
        style.setdefault("color", "0.85")
        style.setdefault("alpha", 0.5)
        style.setdefault("linewidth", 0)
        left = locate(annotation.dates[0])
        right = locate(annotation.dates[1])
        annotation.artists.append(ax.axvspan(left, right, **style))
        text_x = (left + right) / 2

    if annotation.label:
        annotation.artists.append(
            ax.text(
                text_x,
                0.98,
                annotation.label,
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize="small",
                color="0.35",
                clip_on=True,
            )
        )


def replay(
    ax: Axes,
    annotations: Iterable[Annotation],
    locate: Callable[[Any], float],
) -> None:
    """Remove existing artists and redraw annotations in current coordinates."""
    for annotation in annotations:
        for artist in annotation.artists:
            artist.remove()
        annotation.artists.clear()
        draw(ax, annotation, locate)
