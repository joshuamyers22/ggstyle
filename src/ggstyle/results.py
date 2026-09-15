"""Common inspection boundary for semantic rendering results."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection, PolyCollection
from matplotlib.colorbar import Colorbar
from matplotlib.legend import Legend
from matplotlib.lines import Line2D

from ._inspection import describe, json_safe
from .scales import AestheticScale

__all__ = ["RenderedResult"]


@runtime_checkable
class RenderedResult(Protocol):
    """
    Common inspection boundary for a committed semantic render.

    Concrete line, point, ribbon, and guide results retain their native artist
    attributes. This protocol exposes the stable subset that monitoring, notebooks,
    and tests can consume without depending on those geometry-specific attributes.
    """

    @property
    def axes(self) -> Axes:
        """Return the caller-owned axes containing the rendered result."""

    @property
    def diagnostics(self) -> tuple[str, ...]:
        """Return deterministic non-fatal diagnostics from the render."""

    def as_dict(self) -> dict[str, object]:
        """Return a bounded, deterministic, JSON-compatible summary."""

    def describe(self) -> str:
        """Return the result summary as deterministic strict JSON."""


def _artist_counts(artists: Sequence[Artist]) -> dict[str, int]:
    def public_type(artist: Artist) -> str:
        for artist_type in (Line2D, PathCollection, PolyCollection):
            if isinstance(artist, artist_type):
                return artist_type.__name__
        return type(artist).__name__

    counts = Counter(public_type(artist) for artist in artists)
    return dict(sorted(counts.items()))


def _geometry_payload(
    *,
    kind: str,
    artists: Sequence[Artist],
    scales: Mapping[str, AestheticScale],
    diagnostics: Sequence[str],
    layer_id: str,
) -> dict[str, object]:
    """Build the common bounded payload for one semantic geometry result."""

    return {
        "artist_count": len(artists),
        "artist_types": _artist_counts(artists),
        "diagnostics": list(diagnostics),
        "kind": kind,
        "layer_id": layer_id,
        "scales": {
            aesthetic: json_safe(scale.as_dict())
            for aesthetic, scale in sorted(scales.items())
        },
    }


def _colorbar_title(colorbar: Colorbar) -> str:
    return (
        colorbar.ax.get_ylabel()
        if colorbar.orientation == "vertical"
        else colorbar.ax.get_xlabel()
    )


def _guide_payload(
    *,
    legends: Sequence[Legend],
    colorbars: Sequence[Colorbar],
    diagnostics: Sequence[str],
) -> dict[str, object]:
    """Build the common bounded payload for an automatic-guide result."""

    return {
        "colorbar_count": len(colorbars),
        "colorbar_titles": [_colorbar_title(colorbar) for colorbar in colorbars],
        "diagnostics": list(diagnostics),
        "kind": "guides",
        "legend_count": len(legends),
        "legend_titles": [legend.get_title().get_text() for legend in legends],
    }


def _describe_result(payload: Mapping[str, object]) -> str:
    return describe(payload)
