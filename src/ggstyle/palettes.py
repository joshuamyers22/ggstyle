"""Immutable, accessible colour palettes.

Palette construction and interpolation are pure policy. This module does not
import Matplotlib or mutate its global colour cycle. Qualitative colours are
selected, never interpolated; sequential and diverging colours interpolate in
CIELAB space for more even perceptual steps.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from itertools import pairwise
from numbers import Integral, Real
from typing import Literal, cast

__all__ = ["Palette", "available_palettes", "palette"]

PaletteKind = Literal["qualitative", "sequential", "diverging"]
OutOfBoundsPolicy = Literal["clip", "color", "raise"]

_QUALITATIVE = (
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#56B4E9",
    "#E69F00",
    "#000000",
    "#4C3B7A",
)

_SEQUENTIAL = (
    "#440154",
    "#46327E",
    "#365C8D",
    "#277F8E",
    "#1FA187",
    "#4AC16D",
    "#A0DA39",
    "#FDE725",
)

_DIVERGING = (
    "#3D52A1",
    "#2185B5",
    "#41B6C4",
    "#A1DAB4",
    "#F7F7F7",
    "#FEC44F",
    "#EC7014",
    "#CC4C02",
    "#8C2D04",
)

_PALETTES: dict[str, tuple[PaletteKind, tuple[str, ...]]] = {
    "qualitative": ("qualitative", _QUALITATIVE),
    "sequential": ("sequential", _SEQUENTIAL),
    "diverging": ("diverging", _DIVERGING),
}

_ALIASES = {
    "okabe-ito": "qualitative",
    "viridis": "sequential",
    "blue-orange": "diverging",
}


def _hex_color(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a '#RRGGBB' string, got {value!r}")
    if len(value) != 7 or not value.startswith("#"):
        raise ValueError(f"{name} must use '#RRGGBB' form, got {value!r}")
    try:
        int(value[1:], 16)
    except ValueError as error:
        raise ValueError(f"{name} must use '#RRGGBB' form, got {value!r}") from error
    return value.upper()


def _positive_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"n must be a positive integer, got {value!r}")
    if value <= 0:
        raise ValueError(f"n must be a positive integer, got {value!r}")
    return int(value)


def _midpoint(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"midpoint must be a real number, got {value!r}")
    resolved = float(value)
    if not math.isfinite(resolved) or not 0 < resolved < 1:
        raise ValueError(f"midpoint must be finite and between 0 and 1, got {value!r}")
    return resolved


def _out_of_bounds(value: object) -> OutOfBoundsPolicy:
    if not isinstance(value, str):
        raise TypeError(f"out_of_bounds must be a string, got {value!r}")
    if value not in ("clip", "color", "raise"):
        raise ValueError(
            f"out_of_bounds must be 'clip', 'color', or 'raise', got {value!r}"
        )
    return cast(OutOfBoundsPolicy, value)


def _positions(kind: PaletteKind, count: int, midpoint: float | None) -> tuple[float, ...]:
    if kind == "qualitative":
        return ()
    if count == 1:
        return (0.5,)
    if kind == "sequential":
        return tuple(index / (count - 1) for index in range(count))

    assert midpoint is not None
    center = count // 2
    left = tuple(midpoint * index / center for index in range(center + 1))
    right_count = count - center - 1
    right = tuple(
        midpoint + (1 - midpoint) * index / right_count
        for index in range(1, right_count + 1)
    )
    return left + right


def _srgb_to_linear(value: float) -> float:
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(value: float) -> float:
    value = min(1.0, max(0.0, value))
    if value <= 0.0031308:
        return 12.92 * value
    return 1.055 * value ** (1 / 2.4) - 0.055


def _hex_to_lab(color: str) -> tuple[float, float, float]:
    rgb = tuple(int(color[index : index + 2], 16) / 255 for index in (1, 3, 5))
    red, green, blue = (_srgb_to_linear(channel) for channel in rgb)
    x = (0.4124564 * red + 0.3575761 * green + 0.1804375 * blue) / 0.95047
    y = 0.2126729 * red + 0.7151522 * green + 0.0721750 * blue
    z = (0.0193339 * red + 0.1191920 * green + 0.9503041 * blue) / 1.08883

    def transform(value: float) -> float:
        if value > 0.008856:
            return value ** (1 / 3)
        return 7.787 * value + 16 / 116

    fx, fy, fz = transform(x), transform(y), transform(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _lab_to_hex(lab: tuple[float, float, float]) -> str:
    lightness, green_red, blue_yellow = lab
    fy = (lightness + 16) / 116
    fx = green_red / 500 + fy
    fz = fy - blue_yellow / 200

    def inverse(value: float) -> float:
        cubed = value**3
        if cubed > 0.008856:
            return cubed
        return (value - 16 / 116) / 7.787

    x = 0.95047 * inverse(fx)
    y = inverse(fy)
    z = 1.08883 * inverse(fz)
    red = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    green = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    blue = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    channels = (round(255 * _linear_to_srgb(channel)) for channel in (red, green, blue))
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def _interpolate(left: str, right: str, fraction: float) -> str:
    if fraction <= 0:
        return left
    if fraction >= 1:
        return right
    left_lab = _hex_to_lab(left)
    right_lab = _hex_to_lab(right)
    mixed = tuple(
        start + fraction * (end - start)
        for start, end in zip(left_lab, right_lab, strict=True)
    )
    return _lab_to_hex(cast(tuple[float, float, float], mixed))


@dataclass(frozen=True)
class Palette:
    """
    Describe an immutable collection of related colours.

    Parameters
    ----------
    name : str
        Canonical palette name.
    kind : {"qualitative", "sequential", "diverging"}
        Semantic palette kind.
    colors : tuple of str
        Stable ``#RRGGBB`` colours. Qualitative order is meaningful.
    positions : tuple of float
        Normalized positions for continuous and diverging colours; empty for a
        qualitative palette.
    missing_color : str
        Colour returned for a missing normalized value.
    out_of_bounds : {"clip", "color", "raise"}
        Policy for normalized values outside zero through one.
    under_color : str or None
        Colour below zero when ``out_of_bounds="color"``.
    over_color : str or None
        Colour above one when ``out_of_bounds="color"``.
    midpoint : float or None
        Normalized neutral position for a diverging palette.

    Notes
    -----
    Use :func:`palette` instead of constructing this model directly. The model
    remains public so policy is inspectable and reusable without Matplotlib.
    """

    name: str
    kind: PaletteKind
    colors: tuple[str, ...]
    positions: tuple[float, ...]
    missing_color: str
    out_of_bounds: OutOfBoundsPolicy
    under_color: str | None
    over_color: str | None
    midpoint: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(f"palette name must be a string, got {self.name!r}")
        if self.kind not in ("qualitative", "sequential", "diverging"):
            raise ValueError(f"unknown palette kind {self.kind!r}")
        if not self.colors:
            raise ValueError("a palette must contain at least one color")
        object.__setattr__(
            self,
            "colors",
            tuple(_hex_color("color", color) for color in self.colors),
        )
        object.__setattr__(
            self,
            "missing_color",
            _hex_color("missing_color", self.missing_color),
        )
        if self.kind == "qualitative":
            if self.positions:
                raise ValueError("qualitative palettes must not define positions")
            if self.midpoint is not None:
                raise ValueError("qualitative palettes must not define a midpoint")
        else:
            positions: list[float] = []
            for value in self.positions:
                if isinstance(value, bool) or not isinstance(value, Real):
                    raise TypeError(f"palette positions must be real, got {value!r}")
                positions.append(float(value))
            object.__setattr__(self, "positions", tuple(positions))
            if len(positions) != len(self.colors):
                raise ValueError("palette positions must match the colors")
            if any(not math.isfinite(value) for value in positions):
                raise ValueError("palette positions must be finite")
            if any(left >= right for left, right in pairwise(positions)):
                raise ValueError("palette positions must be strictly increasing")
            if positions[0] < 0 or positions[-1] > 1:
                raise ValueError("palette positions must be between 0 and 1")
        if self.kind == "diverging":
            if self.midpoint is None:
                raise ValueError("diverging palettes require a midpoint")
            object.__setattr__(self, "midpoint", _midpoint(self.midpoint))
        elif self.midpoint is not None:
            raise ValueError("only diverging palettes define a midpoint")

        policy = _out_of_bounds(self.out_of_bounds)
        object.__setattr__(self, "out_of_bounds", policy)
        if policy == "color":
            if self.under_color is None or self.over_color is None:
                raise ValueError(
                    "out_of_bounds='color' requires under_color and over_color"
                )
            object.__setattr__(
                self,
                "under_color",
                _hex_color("under_color", self.under_color),
            )
            object.__setattr__(
                self,
                "over_color",
                _hex_color("over_color", self.over_color),
            )
        elif self.under_color is not None or self.over_color is not None:
            raise ValueError("under_color and over_color require out_of_bounds='color'")

    def at(self, position: float | None, /) -> str:
        """
        Return the colour at one normalized numeric position.

        Parameters
        ----------
        position : float or None
            Value from zero through one. ``None`` and NaN use
            :attr:`missing_color`.

        Returns
        -------
        str
            Uppercase ``#RRGGBB`` colour.

        Raises
        ------
        TypeError
            If this is a qualitative palette or ``position`` is not numeric.
        ValueError
            If an out-of-bounds value is rejected by the configured policy.

        Notes
        -----
        This method maps an already-normalized value. Training a data domain and
        assigning category colours belong to semantic scales, not palettes.
        """
        if self.kind == "qualitative":
            raise TypeError("qualitative palettes select categories; use .colors")
        if position is None:
            return self.missing_color
        if isinstance(position, bool) or not isinstance(position, Real):
            raise TypeError(f"position must be a real number or None, got {position!r}")
        try:
            resolved = float(position)
        except OverflowError as error:
            raise ValueError(
                f"position is outside the floating-point range: {position!r}"
            ) from error
        if math.isnan(resolved):
            return self.missing_color
        if resolved < 0 or resolved > 1:
            if self.out_of_bounds == "raise":
                raise ValueError(
                    f"normalized palette position must be between 0 and 1, got {position!r}"
                )
            if self.out_of_bounds == "color":
                return cast(str, self.under_color if resolved < 0 else self.over_color)
            resolved = min(1.0, max(0.0, resolved))

        if len(self.colors) == 1:
            return self.colors[0]
        index = bisect.bisect_right(self.positions, resolved)
        if index == 0:
            return self.colors[0]
        if index == len(self.positions):
            return self.colors[-1]
        left_position, right_position = self.positions[index - 1 : index + 1]
        fraction = (resolved - left_position) / (right_position - left_position)
        return _interpolate(self.colors[index - 1], self.colors[index], fraction)

    def sample(self, n: int) -> tuple[str, ...]:
        """
        Return ``n`` deterministic colours from the palette.

        Parameters
        ----------
        n : int
            Positive number of colours. Qualitative palettes cannot exceed their
            declared cardinality. Diverging samples require an odd value of at
            least three so the neutral midpoint remains present.

        Returns
        -------
        tuple of str
            Immutable sequence of uppercase ``#RRGGBB`` colours.

        Raises
        ------
        TypeError
            If ``n`` is not an integer.
        ValueError
            If ``n`` is outside the palette's supported cardinality.
        """
        count = _positive_count(n)
        if self.kind == "qualitative":
            if count > len(self.colors):
                raise ValueError(
                    f"qualitative palette supports at most {len(self.colors)} colors; "
                    "use direct labels, facets, or an explicit custom palette"
                )
            return self.colors[:count]
        if self.kind == "sequential" and count < 2:
            raise ValueError("sequential palette samples require n >= 2")
        if self.kind == "diverging" and (count < 3 or count % 2 == 0):
            raise ValueError("diverging palette samples require an odd n >= 3")
        positions = _positions(self.kind, count, self.midpoint)
        return tuple(self.at(position) for position in positions)


def available_palettes() -> list[str]:
    """
    Return canonical palette names in semantic order.

    Returns
    -------
    list of str
        Qualitative, sequential, and diverging palette names.

    Examples
    --------
    >>> available_palettes()
    ['qualitative', 'sequential', 'diverging']
    """
    return list(_PALETTES)


def palette(
    name: str = "qualitative",
    n: int | None = None,
    *,
    missing_color: str = "#B3B3B3",
    out_of_bounds: OutOfBoundsPolicy = "clip",
    under_color: str | None = None,
    over_color: str | None = None,
    midpoint: float | None = None,
) -> Palette:
    """
    Create an immutable qualitative, sequential, or diverging palette.

    Parameters
    ----------
    name : str, default "qualitative"
        Canonical name or ``"okabe-ito"``, ``"viridis"``, or
        ``"blue-orange"`` alias.
    n : int or None, optional
        Number of colours to materialize. ``None`` retains the reviewed anchor
        set. Qualitative palettes support at most eight colours; diverging
        palettes require an odd value of at least three.
    missing_color : str, default "#B3B3B3"
        ``#RRGGBB`` colour for missing normalized values.
    out_of_bounds : {"clip", "color", "raise"}, default "clip"
        Policy for normalized values outside zero through one.
    under_color : str or None, optional
        Colour below zero when ``out_of_bounds="color"``.
    over_color : str or None, optional
        Colour above one when ``out_of_bounds="color"``.
    midpoint : float or None, optional
        Neutral normalized position for a diverging palette. The default is
        ``0.5``. Other palette kinds reject this argument.

    Returns
    -------
    Palette
        Immutable palette with stable colour order and explicit policies.

    Raises
    ------
    TypeError
        If an option has the wrong type.
    ValueError
        If a name, colour, cardinality, midpoint, or policy is invalid.

    Notes
    -----
    The qualitative palette is the cycle used by ggstyle themes. Requesting more
    than eight colours fails instead of synthesizing hard-to-distinguish values.
    Continuous and diverging sampling interpolates in CIELAB space.

    Examples
    --------
    >>> palette("qualitative", n=3).colors
    ('#0072B2', '#D55E00', '#009E73')
    >>> palette("sequential").at(0.5)
    '#26908B'
    """
    if not isinstance(name, str):
        raise TypeError(f"palette name must be a string, got {name!r}")
    key = name.strip().lower().replace("_", "-")
    key = _ALIASES.get(key, key)
    if key not in _PALETTES:
        raise ValueError(
            f"unknown palette {name!r}; available palettes are {available_palettes()}"
        )
    kind, colors = _PALETTES[key]
    if midpoint is not None and kind != "diverging":
        raise ValueError("midpoint is only valid for a diverging palette")
    resolved_midpoint = (
        _midpoint(0.5 if midpoint is None else midpoint) if kind == "diverging" else None
    )
    base = Palette(
        name=key,
        kind=kind,
        colors=colors,
        positions=_positions(kind, len(colors), resolved_midpoint),
        missing_color=missing_color,
        out_of_bounds=out_of_bounds,
        under_color=under_color,
        over_color=over_color,
        midpoint=resolved_midpoint,
    )
    if n is None:
        return base
    sampled = base.sample(n)
    return Palette(
        name=base.name,
        kind=base.kind,
        colors=sampled,
        positions=_positions(base.kind, len(sampled), base.midpoint),
        missing_color=base.missing_color,
        out_of_bounds=base.out_of_bounds,
        under_color=base.under_color,
        over_color=base.over_color,
        midpoint=base.midpoint,
    )
