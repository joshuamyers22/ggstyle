"""Lifecycle and transaction tests for axes-owned semantic scale state."""

from __future__ import annotations

import gc
import json

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.testing.decorators import check_figures_equal

import ggstyle as gs
from ggstyle._semantic_registry import (
    MappingRequest,
    ScaleKey,
    SemanticRegistry,
    discard_semantic_registry,
    registry_count,
    semantic_registry,
)
from ggstyle._semantic_scales import (
    ContinuousScaleSpec,
    DiscreteScaleSpec,
    TrainedContinuousScale,
    TrainedDiscreteScale,
)


def _request(
    layer_id: str,
    values: tuple[object, ...],
    *,
    variable: str = "series",
    scale: DiscreteScaleSpec | ContinuousScaleSpec | None = None,
) -> MappingRequest:
    return MappingRequest(
        layer_id,
        variable,
        DiscreteScaleSpec() if scale is None else scale,
        values,
    )


def test_each_axes_owns_one_weak_semantic_registry() -> None:
    figure, (left, right) = plt.subplots(1, 2)
    try:
        first = semantic_registry(left)
        assert semantic_registry(left) is first
        assert semantic_registry(right) is not first
    finally:
        discard_semantic_registry(left)
        discard_semantic_registry(right)
        plt.close(figure)


def test_registry_does_not_keep_axes_alive() -> None:
    baseline = registry_count()
    figure, ax = plt.subplots()
    semantic_registry(ax)
    assert registry_count() == baseline + 1

    plt.close(figure)
    del ax, figure
    gc.collect()

    assert registry_count() == baseline


def test_prepare_trains_one_scale_across_layers_before_commit() -> None:
    registry = SemanticRegistry()
    plan = registry.prepare(
        (
            _request("line-1", ("A", "B")),
            _request("line-2", ("B", "C")),
        )
    )

    assert registry.revision == 0
    assert registry.contributions == ()
    assert plan.base_revision == 0
    assert plan.revision == 1
    assert len(plan.scales) == 1
    trained = plan.scales[0].scale
    assert isinstance(trained, TrainedDiscreteScale)
    assert trained.levels == ("A", "B", "C")
    assert plan.assignments[0].outputs == trained.map_values(("A", "B"))
    assert plan.assignments[1].outputs == trained.map_values(("B", "C"))

    registry.commit(plan)
    assert registry.revision == 1
    assert registry.scales == plan.scales


def test_later_layers_preserve_existing_first_seen_assignments() -> None:
    registry = SemanticRegistry()
    registry.commit(registry.prepare((_request("z-first", ("B", "A")),)))
    original = registry.scales[0].scale
    assert isinstance(original, TrainedDiscreteScale)

    plan = registry.prepare((_request("a-second", ("C", "A")),))
    updated = plan.scales[0].scale
    assert isinstance(updated, TrainedDiscreteScale)

    assert updated.levels == ("B", "A", "C")
    assert updated.outputs[:2] == original.outputs


def test_pandas_categorical_order_is_preserved_explicitly() -> None:
    values = pd.Series(
        pd.Categorical(
            ["low", "high"],
            categories=["high", "medium", "low"],
            ordered=True,
        )
    )
    request = MappingRequest.from_values(
        "points-1",
        "priority",
        DiscreteScaleSpec(include_unobserved=True),
        values,
    )
    plan = SemanticRegistry().prepare((request,))
    trained = plan.scales[0].scale

    assert request.scale.order == ("high", "medium", "low")
    assert isinstance(trained, TrainedDiscreteScale)
    assert trained.levels == ("high", "medium", "low")


def test_same_aesthetic_and_variable_reject_conflicting_scale_policy() -> None:
    registry = SemanticRegistry()
    with pytest.raises(ValueError, match="conflicting color scales"):
        registry.prepare(
            (
                _request("line-1", ("A",)),
                _request(
                    "line-2",
                    ("B",),
                    scale=DiscreteScaleSpec(values=("#112233", "#445566")),
                ),
            )
        )

    assert registry.revision == 0
    assert registry.contributions == ()


def test_different_variables_train_distinct_scales() -> None:
    registry = SemanticRegistry()
    plan = registry.prepare(
        (
            _request("line-1", ("north", "south"), variable="region"),
            _request("line-2", ("actual", "forecast"), variable="status"),
        )
    )

    assert [(entry.key.aesthetic, entry.key.variable) for entry in plan.scales] == [
        ("color", "region"),
        ("color", "status"),
    ]


def test_continuous_domain_is_shared_across_layer_contributions() -> None:
    registry = SemanticRegistry()
    scale = ContinuousScaleSpec()
    plan = registry.prepare(
        (
            _request("points-1", (0.0, 5.0), variable="score", scale=scale),
            _request("points-2", (-5.0, 10.0), variable="score", scale=scale),
        )
    )
    trained = plan.scales[0].scale

    assert isinstance(trained, TrainedContinuousScale)
    assert trained.domain == (-5.0, 10.0)


def test_one_layer_cannot_map_an_aesthetic_twice() -> None:
    registry = SemanticRegistry()
    with pytest.raises(ValueError, match="map an aesthetic twice"):
        registry.prepare(
            (
                _request("line-1", ("A",), variable="first"),
                _request("line-1", ("B",), variable="second"),
            )
        )


def test_one_plan_cannot_add_and_remove_the_same_layer() -> None:
    registry = SemanticRegistry()
    with pytest.raises(ValueError, match="cannot be added and removed"):
        registry.prepare(
            (_request("line-1", ("A",)),),
            remove_layers=("line-1",),
        )


def test_replacement_and_removal_retrain_complete_candidate_state() -> None:
    registry = SemanticRegistry()
    registry.commit(
        registry.prepare(
            (
                _request("line-1", ("A", "B")),
                _request("line-2", ("B", "C")),
            )
        )
    )

    replaced = registry.prepare((_request("line-1", ("D", "B")),))
    trained = replaced.scales[0].scale
    assert isinstance(trained, TrainedDiscreteScale)
    assert trained.levels == ("D", "B", "C")
    assert replaced.replaced_layers == ("line-1",)
    registry.commit(replaced)

    removed = registry.prepare(remove_layers=("line-2",))
    trained = removed.scales[0].scale
    assert isinstance(trained, TrainedDiscreteScale)
    assert trained.levels == ("D", "B")
    assert removed.removed_layers == ("line-2",)


def test_stale_plan_cannot_overwrite_newer_registry_revision() -> None:
    registry = SemanticRegistry()
    first = registry.prepare((_request("line-1", ("A",)),))
    stale = registry.prepare((_request("line-2", ("B",)),))
    registry.commit(first)

    with pytest.raises(RuntimeError, match="stale semantic plan"):
        registry.commit(stale)

    assert registry.revision == 1
    assert [item.layer_id for item in registry.contributions] == ["line-1"]


def test_plan_and_snapshot_cannot_cross_axes_registry_boundaries() -> None:
    first = SemanticRegistry()
    second = SemanticRegistry()
    plan = first.prepare((_request("line-1", ("A",)),))
    snapshot = first.snapshot()

    with pytest.raises(ValueError, match="different axes registry"):
        second.commit(plan)
    with pytest.raises(ValueError, match="different axes registry"):
        second.restore(snapshot)

    assert second.revision == 0


def test_failed_apply_rolls_back_registry_and_caller_state() -> None:
    registry = SemanticRegistry()
    registry.commit(registry.prepare((_request("line-1", ("A",)),)))
    snapshot = registry.snapshot()
    plan = registry.prepare((_request("line-2", ("B",)),))
    external: list[str] = []

    def apply(_plan: object) -> None:
        external.append("artist")
        raise RuntimeError("drawing failed")

    with pytest.raises(RuntimeError, match="drawing failed"):
        registry.transact(plan, apply, lambda: external.pop())

    assert external == []
    assert registry.snapshot() == snapshot


def test_successful_transaction_publishes_once_and_blocks_reentry() -> None:
    registry = SemanticRegistry()
    plan = registry.prepare((_request("line-1", ("A",)),))

    def apply(committed: object) -> str:
        with pytest.raises(RuntimeError, match="already in progress"):
            registry.transact(plan, lambda _: None, lambda: None)
        assert committed is plan
        return "artist"

    assert registry.transact(plan, apply, lambda: None) == "artist"
    assert registry.revision == 1


def test_registry_inspection_is_bounded_deterministic_strict_json() -> None:
    registry = SemanticRegistry()
    plan = registry.prepare((_request("line-1", tuple("ABCDEFG")),))

    payload = plan.as_dict()
    assert payload["diagnostics"] == [
        "color mapping for 'series' has 7 levels; prefer direct labels or facets"
    ]
    assert all("outputs" not in assignment for assignment in payload["assignments"])
    assert json.loads(plan.describe()) == payload
    json.dumps(payload, allow_nan=False)

    registry.commit(plan)
    assert json.loads(registry.describe()) == registry.as_dict()


@check_figures_equal()
def test_semantic_registry_is_independent_from_date_axis_state(
    fig_test: Figure,
    fig_ref: Figure,
) -> None:
    dates = pd.to_datetime(["2024-01-05", "2024-01-08", "2024-01-19"])
    handles = []
    for figure in (fig_test, fig_ref):
        ax = figure.subplots()
        ax.plot(dates, [1.0, 2.0, 1.5])
        handles.append(gs.dates(ax).collapse())

    test_ax = fig_test.axes[0]
    test_handle = handles[0]
    date_revision = test_handle.revision
    registry = semantic_registry(test_ax)
    registry.commit(registry.prepare((_request("line-1", ("A", "A", "A")),)))

    assert test_handle.revision == date_revision
    assert len(test_ax.lines) == 1
    assert len(test_ax.collections) == 0


def test_registry_rejects_non_axes_and_mapping_request_copies_values() -> None:
    with pytest.raises(TypeError, match="matplotlib Axes"):
        semantic_registry(object())  # type: ignore[arg-type]

    values = ["A", "B"]
    request = MappingRequest(
        "line-1",
        "series",
        DiscreteScaleSpec(),
        values,  # type: ignore[arg-type]
    )
    values[0] = "changed"
    assert request.values == ("A", "B")


def test_registry_models_reject_invalid_identity_and_state_objects() -> None:
    with pytest.raises(ValueError, match="unsupported semantic aesthetic"):
        ScaleKey("size", "value")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="variable must be a string"):
        ScaleKey("color", 3)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="layer_id must not be empty"):
        MappingRequest("", "series", DiscreteScaleSpec(), ("A",))
    with pytest.raises(TypeError, match="scale must be"):
        MappingRequest("line-1", "series", object(), ("A",))  # type: ignore[arg-type]

    registry = SemanticRegistry()
    with pytest.raises(ValueError, match="must not contain duplicates"):
        registry.prepare(remove_layers=("line-1", "line-1"))
    with pytest.raises(TypeError, match="remove layer must be a string"):
        registry.prepare(remove_layers=(1,))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="plan must be a SemanticPlan"):
        registry.commit(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="snapshot must be a RegistrySnapshot"):
        registry.restore(object())  # type: ignore[arg-type]


def test_registry_properties_are_immutable_snapshots() -> None:
    registry = SemanticRegistry()
    registry.commit(registry.prepare((_request("line-1", ("A", "B")),)))

    assert isinstance(registry.contributions, tuple)
    assert isinstance(registry.scales, tuple)
    assert isinstance(registry.assignments, tuple)
    with pytest.raises(AttributeError):
        registry.contributions.append("invalid")  # type: ignore[attr-defined]


def test_registry_prepare_does_not_draw_or_mutate_axes() -> None:
    figure, ax = plt.subplots()
    try:
        registry = semantic_registry(ax)
        plan = registry.prepare((_request("line-1", ("A", "B")),))
        registry.commit(plan)

        assert isinstance(ax, Axes)
        assert len(ax.lines) == 0
        assert len(ax.collections) == 0
        assert ax.get_legend() is None
    finally:
        discard_semantic_registry(ax)
        plt.close(figure)
