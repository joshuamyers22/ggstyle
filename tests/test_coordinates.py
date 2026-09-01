import numpy as np
import pytest

from ggstyle._coordinates import dates_to_positions, positions_to_dates


def test_show_mode_is_identity():
    values = np.array([10.0, 20.0])
    assert np.array_equal(dates_to_positions(values, np.empty(0), "show"), values)
    assert np.array_equal(positions_to_dates(values, np.empty(0), "show"), values)


def test_collapsed_mode_interpolates_between_observations():
    knots = np.array([10.0, 20.0, 40.0])
    positions = dates_to_positions(np.array([15.0, 30.0]), knots, "collapse")
    assert np.allclose(positions, [0.5, 1.5])
    assert np.allclose(
        positions_to_dates(positions, knots, "collapse"), [15.0, 30.0]
    )


def test_collapsed_mode_extrapolates_with_typical_spacing():
    knots = np.array([10.0, 20.0, 40.0])
    positions = dates_to_positions(np.array([-5.0, 55.0]), knots, "collapse")
    assert np.allclose(positions, [-1.0, 3.0])
    assert np.allclose(
        positions_to_dates(positions, knots, "collapse"), [-5.0, 55.0]
    )


def test_single_observation_uses_a_unit_step_for_forward_mapping():
    knots = np.array([10.0])
    assert np.allclose(
        dates_to_positions(np.array([8.0, 12.0]), knots, "collapse"), [-2.0, 2.0]
    )
    assert np.allclose(
        positions_to_dates(np.array([-2.0, 2.0]), knots, "collapse"), [10.0, 10.0]
    )


def test_collapsed_mode_rejects_missing_observations():
    with pytest.raises(ValueError, match="at least one observed date"):
        dates_to_positions(np.array([1.0]), np.empty(0), "collapse")
