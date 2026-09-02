import numpy as np
import pytest

from ggstyle import _axis_sync


def test_union_plan_shares_all_observations() -> None:
    plan = _axis_sync.plan(
        [np.array([1.0, 2.0]), np.array([2.0, 4.0])],
        ["show", "show"],
        mode=None,
        limits="union",
    )

    assert plan.mode == "show"
    assert (plan.lower, plan.upper) == (1.0, 4.0)
    assert np.array_equal(plan.observations, np.array([1.0, 2.0, 4.0]))


def test_intersection_plan_keeps_shared_coordinate_domain() -> None:
    plan = _axis_sync.plan(
        [np.array([1.0, 3.0]), np.array([2.0, 4.0])],
        ["show", "show"],
        mode="collapse",
        limits="intersection",
    )

    assert plan.mode == "collapse"
    assert (plan.lower, plan.upper) == (2.0, 3.0)
    assert np.array_equal(plan.observations, np.array([1.0, 2.0, 3.0, 4.0]))


def test_plan_rejects_incompatible_modes_without_override() -> None:
    with pytest.raises(ValueError, match="different modes"):
        _axis_sync.plan(
            [np.array([1.0]), np.array([1.0])],
            ["show", "collapse"],
            mode=None,
            limits="union",
        )


def test_plan_rejects_disjoint_intersection() -> None:
    with pytest.raises(ValueError, match="no overlapping"):
        _axis_sync.plan(
            [np.array([1.0]), np.array([2.0])],
            ["show", "show"],
            mode=None,
            limits="intersection",
        )


def test_sync_options_and_empty_axes_are_rejected() -> None:
    with pytest.raises(ValueError, match="mode must be"):
        _axis_sync.validate_options("hidden", "union")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="limits must be"):
        _axis_sync.validate_options(None, "outer")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="at least one"):
        _axis_sync.plan([], [], mode=None, limits="union")
