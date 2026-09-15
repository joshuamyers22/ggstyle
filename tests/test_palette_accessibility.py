"""Accessibility invariants for public palettes and theme surfaces."""

from itertools import combinations, pairwise

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs

# Severity-1 matrices from Machado, Oliveira, and Fernandes (2009),
# doi:10.1109/TVCG.2009.113. The identity matrix keeps the normal-vision case in
# the same test path. Thresholds are regression gates, not clinical pass/fail claims.
VISION_MATRICES = {
    "normal": np.eye(3),
    "protanopia": np.array(
        [
            [0.152286, 1.052583, -0.204868],
            [0.114503, 0.786281, 0.099216],
            [-0.003882, -0.048116, 1.051998],
        ]
    ),
    "deuteranopia": np.array(
        [
            [0.367322, 0.860646, -0.227968],
            [0.280085, 0.672501, 0.047413],
            [-0.011820, 0.042940, 0.968881],
        ]
    ),
    "tritanopia": np.array(
        [
            [1.255528, -0.076749, -0.178779],
            [-0.078411, 0.930809, 0.147602],
            [0.004733, 0.691367, 0.303900],
        ]
    ),
}


def _linearize(channel: np.ndarray) -> np.ndarray:
    return np.where(
        channel <= 0.04045,
        channel / 12.92,
        ((channel + 0.055) / 1.055) ** 2.4,
    )


def _encode(channel: np.ndarray) -> np.ndarray:
    channel = np.clip(channel, 0, 1)
    return np.where(
        channel <= 0.0031308,
        12.92 * channel,
        1.055 * channel ** (1 / 2.4) - 0.055,
    )


def _rgb(color: str) -> np.ndarray:
    return np.array([int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)])


def _simulate(color: str, matrix: np.ndarray) -> np.ndarray:
    return _encode(matrix @ _linearize(_rgb(color)))


def _lab(rgb: np.ndarray) -> np.ndarray:
    red, green, blue = _linearize(rgb)
    xyz = np.array(
        [
            0.4124564 * red + 0.3575761 * green + 0.1804375 * blue,
            0.2126729 * red + 0.7151522 * green + 0.0721750 * blue,
            0.0193339 * red + 0.1191920 * green + 0.9503041 * blue,
        ]
    ) / np.array([0.95047, 1.0, 1.08883])
    transformed = np.where(
        xyz > 0.008856,
        np.cbrt(xyz),
        7.787 * xyz + 16 / 116,
    )
    fx, fy, fz = transformed
    return np.array([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)])


def _perceived(color: str, matrix: np.ndarray) -> np.ndarray:
    return _lab(_simulate(color, matrix))


def test_qualitative_colors_remain_separated_under_cvd_simulations() -> None:
    colors = gs.palette("qualitative").colors
    for matrix in VISION_MATRICES.values():
        perceived = [_perceived(color, matrix) for color in colors]
        distances = [
            np.linalg.norm(left - right) for left, right in combinations(perceived, 2)
        ]
        assert min(distances) >= 15.0


def test_qualitative_colors_remain_distinct_from_theme_surfaces() -> None:
    colors = gs.palette("qualitative").colors
    backgrounds = ("#FFFFFF", "#EBEBEB", "#7F7F7F")
    for matrix in VISION_MATRICES.values():
        for background in backgrounds:
            surface = _perceived(background, matrix)
            distances = [
                np.linalg.norm(_perceived(color, matrix) - surface) for color in colors
            ]
            assert min(distances) >= 9.0


def test_sequential_lightness_is_ordered_under_cvd_simulations() -> None:
    colors = gs.palette("sequential").colors
    for matrix in VISION_MATRICES.values():
        lightness = [_perceived(color, matrix)[0] for color in colors]
        assert all(left < right for left, right in pairwise(lightness))


def test_diverging_lightness_converges_on_explicit_midpoint() -> None:
    selected = gs.palette("diverging")
    center = selected.positions.index(selected.midpoint)
    for matrix in VISION_MATRICES.values():
        lightness = [_perceived(color, matrix)[0] for color in selected.colors]
        assert all(left < right for left, right in pairwise(lightness[: center + 1]))
        assert all(left > right for left, right in pairwise(lightness[center:]))


def test_every_theme_uses_the_public_qualitative_palette() -> None:
    expected = list(gs.palette("qualitative").colors)
    for name in gs.available_themes():
        with gs.theme(name):
            assert plt.rcParams["axes.prop_cycle"].by_key()["color"] == expected


def test_palette_lookup_does_not_mutate_matplotlib_configuration() -> None:
    before = matplotlib.rcParams.copy()
    gs.palette("qualitative", n=3)
    gs.palette("sequential", n=5)
    gs.palette("diverging", n=5)
    assert matplotlib.rcParams == before
