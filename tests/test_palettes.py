"""Tests for immutable palette policy and normalized lookup."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

from ggstyle.palettes import Palette, available_palettes, palette

EXPECTED_QUALITATIVE = (
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#56B4E9",
    "#E69F00",
    "#000000",
    "#4C3B7A",
)


def test_public_palette_inventory_and_default_are_stable() -> None:
    assert available_palettes() == ["qualitative", "sequential", "diverging"]
    assert palette().name == "qualitative"
    assert palette().colors == EXPECTED_QUALITATIVE


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("okabe-ito", "qualitative"),
        ("okabe_ito", "qualitative"),
        ("viridis", "sequential"),
        ("blue-orange", "diverging"),
    ],
)
def test_aliases_resolve_to_canonical_palettes(alias: str, canonical: str) -> None:
    assert palette(alias) == palette(canonical)


def test_qualitative_selection_preserves_order() -> None:
    selected = palette(n=3)
    assert selected.colors == EXPECTED_QUALITATIVE[:3]
    assert selected.colors == palette().sample(3)


@pytest.mark.parametrize("count", [9, 20])
def test_qualitative_palette_never_synthesizes_extra_colors(count: int) -> None:
    with pytest.raises(ValueError, match="at most 8 colors"):
        palette(n=count)


@pytest.mark.parametrize("count", [0, -1])
def test_palette_count_must_be_positive(count: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        palette(n=count)


@pytest.mark.parametrize("count", [True, 2.5])
def test_palette_count_must_be_an_integer(count) -> None:
    with pytest.raises(TypeError, match="positive integer"):
        palette(n=count)


def test_numpy_integer_count_is_supported() -> None:
    assert len(palette(n=np.int64(2)).colors) == 2


def test_sequential_sampling_is_deterministic_and_keeps_endpoints() -> None:
    selected = palette("sequential", n=5)
    assert selected.colors == (
        "#440154",
        "#3C5289",
        "#26908B",
        "#65C762",
        "#FDE725",
    )
    assert selected.positions == (0.0, 0.25, 0.5, 0.75, 1.0)


def test_sequential_sampling_requires_two_colors() -> None:
    with pytest.raises(ValueError, match="n >= 2"):
        palette("sequential", n=1)


def test_diverging_sampling_retains_an_explicit_midpoint() -> None:
    selected = palette("diverging", n=5)
    assert selected.midpoint == 0.5
    assert selected.colors == (
        "#3D52A1",
        "#41B6C4",
        "#F7F7F7",
        "#EC7014",
        "#8C2D04",
    )
    assert selected.at(selected.midpoint) == "#F7F7F7"


def test_diverging_midpoint_controls_color_positions() -> None:
    selected = palette("diverging", n=5, midpoint=0.25)
    assert selected.positions == (0.0, 0.125, 0.25, 0.625, 1.0)
    assert selected.at(0.25) == "#F7F7F7"


@pytest.mark.parametrize("count", [1, 2, 4, 6])
def test_diverging_samples_require_a_neutral_center(count: int) -> None:
    with pytest.raises(ValueError, match="odd n >= 3"):
        palette("diverging", n=count)


def test_normalized_lookup_interpolates_in_lab_space() -> None:
    sequential = palette("sequential")
    assert sequential.at(0) == sequential.colors[0]
    assert sequential.at(0.5) == "#26908B"
    assert sequential.at(1) == sequential.colors[-1]


@pytest.mark.parametrize("missing", [None, float("nan"), np.float64("nan")])
def test_missing_normalized_values_use_explicit_color(missing) -> None:
    assert palette("sequential", missing_color="#abcdef").at(missing) == "#ABCDEF"


def test_out_of_bounds_clip_is_the_default() -> None:
    sequential = palette("sequential")
    assert sequential.at(float("-inf")) == sequential.colors[0]
    assert sequential.at(-0.1) == sequential.colors[0]
    assert sequential.at(1.1) == sequential.colors[-1]
    assert sequential.at(float("inf")) == sequential.colors[-1]


def test_out_of_bounds_can_use_dedicated_colors() -> None:
    sequential = palette(
        "sequential",
        out_of_bounds="color",
        under_color="#102030",
        over_color="#f0e0d0",
    )
    assert sequential.at(-1) == "#102030"
    assert sequential.at(2) == "#F0E0D0"


def test_out_of_bounds_can_raise() -> None:
    sequential = palette("sequential", out_of_bounds="raise")
    with pytest.raises(ValueError, match="between 0 and 1"):
        sequential.at(-0.01)


def test_qualitative_palette_rejects_normalized_lookup() -> None:
    with pytest.raises(TypeError, match="qualitative palettes"):
        palette().at(0.5)


@pytest.mark.parametrize("value", [True, "0.5", 1 + 2j])
def test_normalized_position_must_be_real(value) -> None:
    with pytest.raises(TypeError, match="real number"):
        palette("sequential").at(value)


@pytest.mark.parametrize("name", ["rainbow", "", "unknown"])
def test_unknown_palette_is_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="unknown palette"):
        palette(name)


def test_palette_name_must_be_a_string() -> None:
    with pytest.raises(TypeError, match="palette name"):
        palette(1)


@pytest.mark.parametrize("midpoint", [0, 1, -0.1, float("inf"), float("nan")])
def test_diverging_midpoint_must_be_inside_domain(midpoint: float) -> None:
    with pytest.raises(ValueError, match="midpoint"):
        palette("diverging", midpoint=midpoint)


@pytest.mark.parametrize("midpoint", [True, "0.5"])
def test_diverging_midpoint_must_be_real(midpoint) -> None:
    with pytest.raises(TypeError, match="midpoint"):
        palette("diverging", midpoint=midpoint)


def test_other_palette_kinds_reject_midpoint() -> None:
    with pytest.raises(ValueError, match="only valid for a diverging"):
        palette("sequential", midpoint=0.5)


@pytest.mark.parametrize(
    "options",
    [
        {"missing_color": "red"},
        {"missing_color": "#12345Z"},
        {"missing_color": 123},
        {"out_of_bounds": "ignore"},
        {"out_of_bounds": 1},
    ],
)
def test_color_and_policy_options_are_validated(options) -> None:
    with pytest.raises((TypeError, ValueError)):
        palette("sequential", **options)


def test_color_policy_requires_both_dedicated_colors() -> None:
    with pytest.raises(ValueError, match="requires under_color and over_color"):
        palette("sequential", out_of_bounds="color", under_color="#000000")


def test_unused_dedicated_colors_are_rejected() -> None:
    with pytest.raises(ValueError, match="require out_of_bounds='color'"):
        palette("sequential", under_color="#000000")


def test_palette_and_colors_are_immutable() -> None:
    selected = palette()
    assert isinstance(selected.colors, tuple)
    with pytest.raises(FrozenInstanceError):
        selected.name = "changed"  # type: ignore[misc]


def test_palette_policy_does_not_import_matplotlib() -> None:
    source = Path("src/ggstyle/palettes.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source


def test_direct_model_construction_validates_position_topology() -> None:
    base = palette("sequential")
    with pytest.raises(ValueError, match="strictly increasing"):
        Palette(
            name=base.name,
            kind=base.kind,
            colors=base.colors,
            positions=tuple(reversed(base.positions)),
            missing_color=base.missing_color,
            out_of_bounds=base.out_of_bounds,
            under_color=None,
            over_color=None,
            midpoint=None,
        )
