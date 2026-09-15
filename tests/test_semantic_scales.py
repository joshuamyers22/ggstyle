"""Pure policy tests for semantic aesthetic-scale training."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import ggstyle as gs
from ggstyle._semantic_scales import (
    ContinuousScaleSpec,
    DiscreteScaleSpec,
    TrainedContinuousScale,
    TrainedDiscreteScale,
    train_continuous,
    train_discrete,
)


def test_discrete_scale_trains_first_seen_order_across_batches() -> None:
    trained = train_discrete(
        DiscreteScaleSpec(),
        (("beta", "alpha", "beta"), ("gamma", "alpha")),
    )

    assert trained.levels == ("beta", "alpha", "gamma")
    assert trained.outputs == gs.palette("qualitative").colors[:3]
    assert trained.map_values(("gamma", "beta", "alpha")) == (
        trained.outputs[2],
        trained.outputs[0],
        trained.outputs[1],
    )


def test_discrete_explicit_order_controls_observed_and_unobserved_levels() -> None:
    dropped = train_discrete(
        DiscreteScaleSpec(order=("high", "medium", "low")),
        (("low", "high"),),
    )
    retained = train_discrete(
        DiscreteScaleSpec(
            order=("high", "medium", "low"),
            include_unobserved=True,
        ),
        (("low", "high"),),
    )

    assert dropped.levels == ("high", "low")
    assert retained.levels == ("high", "medium", "low")


def test_discrete_explicit_order_rejects_unknown_observed_levels() -> None:
    with pytest.raises(ValueError, match="absent from explicit order"):
        train_discrete(
            DiscreteScaleSpec(order=("planned", "complete")),
            (("planned", "blocked"),),
        )


def test_discrete_spec_is_immutable_and_defensively_copies_inputs() -> None:
    colors = ["#112233", "#445566"]
    order = ["first", "second"]
    spec = DiscreteScaleSpec(values=colors, order=order)  # type: ignore[arg-type]
    colors[0] = "#FFFFFF"
    order.reverse()

    assert spec.values == ("#112233", "#445566")
    assert spec.order == ("first", "second")
    with pytest.raises(FrozenInstanceError):
        spec.name = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        ("map", "#B3B3B3"),
        ("drop", None),
    ],
)
def test_discrete_missing_policy_is_explicit(policy: str, expected: str | None) -> None:
    spec = DiscreteScaleSpec(missing=policy)  # type: ignore[arg-type]
    trained = train_discrete(spec, (("A", None, pd.NA, np.nan),))

    assert trained.map_one(None) == expected
    assert trained.map_one(np.nan) == expected


def test_discrete_missing_raise_fails_during_training() -> None:
    with pytest.raises(ValueError, match="missing value"):
        train_discrete(DiscreteScaleSpec(missing="raise"), (("A", None),))


def test_discrete_cardinality_and_scalar_boundaries_fail_before_drawing() -> None:
    with pytest.raises(ValueError, match="at most 8 levels"):
        train_discrete(DiscreteScaleSpec(), (tuple(range(9)),))
    with pytest.raises(TypeError, match="hashable scalars"):
        train_discrete(DiscreteScaleSpec(), ((("valid"), ["not", "scalar"]),))

    too_many_colors = tuple(f"#{index:06X}" for index in range(9))
    with pytest.raises(ValueError, match="at most 8 values"):
        DiscreteScaleSpec(values=too_many_colors)


def test_discrete_linestyle_uses_a_small_validated_range() -> None:
    trained = train_discrete(
        DiscreteScaleSpec(aesthetic="linestyle"),
        (("observed", "forecast"),),
    )

    assert trained.outputs == ("solid", "dashed")
    with pytest.raises(ValueError, match="linestyle values"):
        DiscreteScaleSpec(aesthetic="linestyle", values=("solid", "invalid"))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"aesthetic": "size"}, "discrete aesthetic"),
        ({"include_unobserved": 1}, "must be a bool"),
        ({"name": ""}, "must not be empty"),
        ({"values": ()}, "must not be empty"),
        ({"values": ("#112233", "#112233")}, "must be unique"),
        ({"values": ("red",)}, "#RRGGBB"),
        ({"values": (123,)}, "#RRGGBB"),
        ({"values": ("#GGGGGG",)}, "#RRGGBB"),
        ({"order": ("A", "A")}, "unique levels"),
        ({"order": (None,)}, "cannot be discrete scale levels"),
        ({"missing": "ignore"}, "missing must be"),
        ({"missing": "drop", "missing_value": "#112233"}, "requires missing='map'"),
    ],
)
def test_discrete_spec_rejects_invalid_policy(
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        DiscreteScaleSpec(**kwargs)  # type: ignore[arg-type]


def test_discrete_order_cannot_exceed_aesthetic_range() -> None:
    with pytest.raises(ValueError, match="3 levels but only 2"):
        DiscreteScaleSpec(
            values=("#112233", "#445566"),
            order=("A", "B", "C"),
        )


def test_trained_discrete_rejects_late_missing_or_untrained_values() -> None:
    strict = train_discrete(DiscreteScaleSpec(missing="raise"), (("A",),))
    ordinary = train_discrete(DiscreteScaleSpec(), (("A",),))

    with pytest.raises(ValueError, match="missing value"):
        strict.map_one(None)
    with pytest.raises(ValueError, match="untrained discrete level"):
        ordinary.map_one("B")


def test_continuous_scale_trains_one_domain_across_batches() -> None:
    trained = train_continuous(
        ContinuousScaleSpec(),
        ((10.0, 20.0), (-10.0, 5.0)),
    )

    assert trained.domain == (-10.0, 20.0)
    assert trained.map_one(-10.0) == trained.spec.palette.at(0.0)
    assert trained.map_one(5.0) == trained.spec.palette.at(0.5)
    assert trained.map_one(20.0) == trained.spec.palette.at(1.0)


def test_continuous_constant_domain_maps_to_palette_midpoint() -> None:
    trained = train_continuous(ContinuousScaleSpec(), ((4.0, 4.0),))

    assert trained.domain == (4.0, 4.0)
    assert trained.map_one(4.0) == trained.spec.palette.at(0.5)


def test_continuous_explicit_limits_apply_palette_out_of_bounds_policy() -> None:
    clipped = train_continuous(
        ContinuousScaleSpec(limits=(0.0, 10.0)),
        ((-5.0, 5.0, 15.0),),
    )
    strict = train_continuous(
        ContinuousScaleSpec(
            palette=gs.palette("sequential", out_of_bounds="raise"),
            limits=(0.0, 10.0),
        ),
        ((5.0,),),
    )
    colored = train_continuous(
        ContinuousScaleSpec(
            palette=gs.palette(
                "sequential",
                out_of_bounds="color",
                under_color="#010203",
                over_color="#FDFCFB",
            ),
            limits=(0.0, 10.0),
        ),
        ((5.0,),),
    )

    assert clipped.map_values((-5.0, 15.0)) == (
        clipped.spec.palette.at(0.0),
        clipped.spec.palette.at(1.0),
    )
    with pytest.raises(ValueError, match="between 0 and 1"):
        strict.map_one(-5.0)
    assert colored.map_values((-5.0, 15.0)) == ("#010203", "#FDFCFB")


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        ("drop", (None, None)),
        ("clip", ("low", "high")),
        ("color", ("under", "over")),
    ],
)
def test_continuous_infinite_policy(
    policy: str,
    expected: tuple[str | None, str | None],
) -> None:
    selected = gs.palette(
        "sequential",
        out_of_bounds="color",
        under_color="#010203",
        over_color="#FDFCFB",
    )
    trained = train_continuous(
        ContinuousScaleSpec(
            palette=selected,
            limits=(0.0, 1.0),
            infinite=policy,  # type: ignore[arg-type]
        ),
        ((0.5, float("-inf"), float("inf")),),
    )
    actual = trained.map_values((float("-inf"), float("inf")))
    labels = {
        selected.at(0.0): "low",
        selected.at(1.0): "high",
        "#010203": "under",
        "#FDFCFB": "over",
        None: None,
    }

    assert tuple(labels[value] for value in actual) == expected


def test_continuous_missing_and_infinite_raise_during_training() -> None:
    with pytest.raises(ValueError, match="missing value"):
        train_continuous(ContinuousScaleSpec(missing="raise"), ((1.0, np.nan),))
    with pytest.raises(ValueError, match="infinity"):
        train_continuous(ContinuousScaleSpec(), ((1.0, float("inf")),))


def test_continuous_requires_numeric_finite_domain_or_limits() -> None:
    with pytest.raises(TypeError, match="real numbers"):
        train_continuous(ContinuousScaleSpec(), ((1.0, "2"),))
    with pytest.raises(TypeError, match="real numbers"):
        train_continuous(ContinuousScaleSpec(), ((True, 1.0),))
    with pytest.raises(ValueError, match="no finite values"):
        train_continuous(
            ContinuousScaleSpec(missing="drop", infinite="drop"),
            ((None, np.nan, float("inf")),),
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"aesthetic": "linestyle"}, "only the 'color' aesthetic"),
        ({"palette": "viridis"}, "palette must be a Palette"),
        ({"palette": gs.palette("qualitative")}, "sequential or diverging"),
        ({"missing": "ignore"}, "missing must be"),
        ({"infinite": "keep"}, "infinite must be"),
        ({"infinite": "color"}, "requires a palette"),
        ({"name": ""}, "must not be empty"),
        ({"limits": [0.0, 1.0]}, "must be a.*tuple"),
        ({"limits": (True, 1.0)}, "real number"),
        ({"limits": (0.0, float("inf"))}, "must be finite"),
        ({"limits": (1.0, 1.0)}, "lower < upper"),
    ],
)
def test_continuous_spec_rejects_invalid_policy(
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        ContinuousScaleSpec(**kwargs)  # type: ignore[arg-type]


def test_trained_continuous_applies_late_missing_infinite_and_constant_oob() -> None:
    strict = train_continuous(
        ContinuousScaleSpec(missing="raise", infinite="raise"),
        ((4.0,),),
    )
    dropping = train_continuous(
        ContinuousScaleSpec(missing="drop", limits=(0.0, 1.0)),
        ((0.5,),),
    )

    with pytest.raises(ValueError, match="missing value"):
        strict.map_one(None)
    with pytest.raises(ValueError, match="infinity"):
        strict.map_one(float("inf"))
    with pytest.raises(TypeError, match="real numbers"):
        strict.map_one("4")
    assert dropping.map_one(np.nan) is None
    assert strict.map_one(3.0) == strict.spec.palette.at(0.0)
    assert strict.map_one(5.0) == strict.spec.palette.at(1.0)


def test_explicit_limits_allow_all_missing_and_infinite_input() -> None:
    trained = train_continuous(
        ContinuousScaleSpec(
            limits=(0.0, 1.0),
            missing="drop",
            infinite="drop",
        ),
        ((None, np.nan, float("inf")),),
    )

    assert trained.domain == (0.0, 1.0)
    assert trained.map_values((None, float("inf"))) == (None, None)


def test_trained_scale_inspection_is_strict_json() -> None:
    discrete = train_discrete(DiscreteScaleSpec(), (("A", "B"),))
    continuous = train_continuous(ContinuousScaleSpec(), ((1.0, 2.0),))

    assert isinstance(discrete, TrainedDiscreteScale)
    assert isinstance(continuous, TrainedContinuousScale)
    assert json.loads(discrete.describe()) == discrete.as_dict()
    assert json.loads(continuous.describe()) == continuous.as_dict()
    json.dumps(discrete.as_dict(), allow_nan=False)
    json.dumps(continuous.as_dict(), allow_nan=False)


def test_discrete_inspection_preserves_numpy_and_datetime_scalar_values() -> None:
    trained = train_discrete(
        DiscreteScaleSpec(),
        ((np.int64(7), pd.Timestamp("2024-01-05")),),
    )

    assert trained.as_dict()["levels"] == [7, "2024-01-05T00:00:00"]


def test_semantic_scale_policy_does_not_import_matplotlib() -> None:
    source = Path("src/ggstyle/_semantic_scales.py").read_text()

    assert "import matplotlib" not in source
    assert "from matplotlib" not in source
