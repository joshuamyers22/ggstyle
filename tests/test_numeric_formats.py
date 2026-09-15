"""Tests for pure, locale-independent numeric labellers."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

from ggstyle.formats import (
    label_currency,
    label_number,
    label_percent,
    label_si,
)


class TestPercent:
    def test_fraction_scale_and_fixed_precision(self) -> None:
        labeller = label_percent(decimals=1)
        assert [labeller(value) for value in (0, 0.125, 1)] == [
            "0.0%",
            "12.5%",
            "100.0%",
        ]

    def test_already_percent_scale(self) -> None:
        assert label_percent(scale=100, decimals=2)(12.5) == "12.50%"

    def test_optional_grouping_and_suffix(self) -> None:
        labeller = label_percent(grouping=True, suffix=" percent")
        assert labeller(12.5) == "1,250 percent"


class TestCurrency:
    def test_symbol_scale_suffix_and_grouping(self) -> None:
        millions = label_currency("$", scale=1_000_000, decimals=1, suffix="M")
        assert millions(2_500_000) == "$2.5M"
        assert label_currency("€", decimals=2)(1234.5) == "€1,234.50"

    def test_negative_styles(self) -> None:
        assert label_currency(decimals=0)(-1250) == "-$1,250"
        accounting = label_currency(decimals=0, negative="parentheses")
        assert accounting(-1250) == "($1,250)"


class TestNumber:
    def test_grouping_precision_scale_and_affixes(self) -> None:
        labeller = label_number(
            scale=1000,
            decimals=2,
            prefix="~",
            suffix="k",
        )
        assert labeller(1_234_560) == "~1,234.56k"

    def test_grouping_can_be_disabled(self) -> None:
        assert label_number(decimals=1, grouping=False)(1234.5) == "1234.5"

    def test_negative_values_rounded_to_zero_lose_the_sign(self) -> None:
        assert label_number(decimals=1)(-0.01) == "0.0"

    def test_accepts_numpy_real_scalars(self) -> None:
        assert label_number()(np.float64(1200)) == "1,200"

    def test_accepts_numpy_integer_precision(self) -> None:
        assert label_number(decimals=np.int64(2))(1.5) == "1.50"


class TestSI:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, "0.0 B"),
            (999, "999.0 B"),
            (1500, "1.5 kB"),
            (2_500_000, "2.5 MB"),
            (3e-6, "3.0 µB"),
            (4e27, "4.0 RB"),
            (5e-30, "5.0 qB"),
        ],
    )
    def test_si_prefixes(self, value: float, expected: str) -> None:
        assert label_si(unit="B")(value) == expected

    def test_rounding_promotes_to_the_next_prefix(self) -> None:
        assert label_si(decimals=1)(999.99) == "1.0 k"

    def test_separator_and_parentheses_are_explicit(self) -> None:
        labeller = label_si(unit="W", separator="", negative="parentheses")
        assert labeller(-1500) == "(1.5kW)"

    def test_values_beyond_prefix_range_are_clamped(self) -> None:
        assert label_si(decimals=1)(1e33) == "1000.0 Q"


@pytest.mark.parametrize(
    "factory",
    [label_number, label_percent, label_currency, label_si],
)
def test_nonfinite_values_have_stable_explicit_labels(factory) -> None:
    labeller = factory(nan="missing", infinity="infinite")
    assert labeller(float("nan")) == "missing"
    assert labeller(float("inf")) == "infinite"
    assert labeller(float("-inf")) == "-infinite"


def test_parentheses_apply_to_negative_infinity() -> None:
    assert label_number(negative="parentheses")(float("-inf")) == "(∞)"


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True, "100"])
def test_scale_must_be_positive_and_finite(value) -> None:
    expected = TypeError if value is True or isinstance(value, str) else ValueError
    with pytest.raises(expected, match="scale"):
        label_number(scale=value)


@pytest.mark.parametrize("value", [-1, 1.5, True])
def test_decimals_must_be_a_nonnegative_integer(value) -> None:
    expected = ValueError if value == -1 else TypeError
    with pytest.raises(expected, match="decimals"):
        label_number(decimals=value)


def test_grouping_must_be_boolean() -> None:
    with pytest.raises(TypeError, match="grouping"):
        label_number(grouping=1)


def test_negative_style_is_validated() -> None:
    with pytest.raises(ValueError, match="negative"):
        label_number(negative="red")
    with pytest.raises(TypeError, match="negative must be a string"):
        label_number(negative=1)


@pytest.mark.parametrize(
    ("factory", "arguments"),
    [
        (label_number, {"prefix": 1}),
        (label_percent, {"suffix": 1}),
        (label_currency, {"symbol": 1}),
        (label_si, {"unit": 1}),
        (label_si, {"separator": 1}),
    ],
)
def test_text_options_are_validated(factory, arguments) -> None:
    with pytest.raises(TypeError, match="must be a string"):
        factory(**arguments)


@pytest.mark.parametrize("value", [True, "1", 1 + 2j])
def test_labellers_reject_non_real_values(value) -> None:
    with pytest.raises(TypeError, match="real number"):
        label_number()(value)


def test_factory_results_are_immutable() -> None:
    labeller = label_number()
    with pytest.raises(FrozenInstanceError):
        labeller.decimals = 2  # type: ignore[attr-defined]


def test_output_does_not_depend_on_locale_module() -> None:
    source = Path("src/ggstyle/formats.py").read_text()
    assert "import locale" not in source
    assert label_number(decimals=2)(1234.5) == "1,234.50"


def test_numeric_policy_does_not_import_matplotlib() -> None:
    source = Path("src/ggstyle/formats.py").read_text()
    assert "import matplotlib" not in source
    assert "from matplotlib" not in source
