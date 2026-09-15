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


def test_single_observation_uses_a_unit_step_in_both_directions():
    knots = np.array([10.0])
    assert np.allclose(
        dates_to_positions(np.array([8.0, 12.0]), knots, "collapse"), [-2.0, 2.0]
    )
    assert np.allclose(
        positions_to_dates(np.array([-2.0, 2.0]), knots, "collapse"), [8.0, 12.0]
    )


def test_collapsed_mode_rejects_missing_observations():
    with pytest.raises(ValueError, match="at least one observed date"):
        dates_to_positions(np.array([1.0]), np.empty(0), "collapse")


def test_knots_are_sorted_and_deduplicated():
    knots = np.array([40.0, 10.0, 20.0, 20.0])
    assert np.allclose(
        dates_to_positions(np.array([10.0, 20.0, 40.0]), knots, "collapse"),
        [0.0, 1.0, 2.0],
    )


def test_unsorted_values_retain_input_order():
    knots = np.array([10.0, 20.0, 40.0])
    assert np.allclose(
        dates_to_positions(np.array([40.0, 10.0, 30.0]), knots, "collapse"),
        [2.0, 0.0, 1.5],
    )


def test_mapping_is_monotone_and_round_trips_across_domain_edges():
    knots = np.array([10.0, 20.0, 40.0])
    values = np.linspace(-20.0, 70.0, 501)
    positions = dates_to_positions(values, knots, "collapse")
    assert np.all(np.diff(positions) > 0)
    assert np.allclose(positions_to_dates(positions, knots, "collapse"), values)


def test_transform_preserves_scalar_and_matrix_shapes():
    knots = np.array([10.0, 20.0, 40.0])
    scalar = dates_to_positions(np.array(20.0), knots, "collapse")
    matrix = dates_to_positions(np.array([[10.0, 20.0], [30.0, 40.0]]), knots, "collapse")
    assert scalar.shape == ()
    assert scalar == pytest.approx(1.0)
    assert matrix.shape == (2, 2)
    assert np.allclose(positions_to_dates(matrix, knots, "collapse"), [[10, 20], [30, 40]])


def test_transform_preserves_masks_and_nonfinite_values():
    knots = np.array([10.0, 20.0, 40.0])
    values = np.ma.array([10.0, 999.0, np.nan, -np.inf, np.inf], mask=[0, 1, 0, 0, 0])
    positions = dates_to_positions(values, knots, "collapse")
    assert np.array_equal(np.ma.getmaskarray(positions), values.mask)
    assert np.isnan(positions[2])
    assert np.isneginf(positions[3])
    assert np.isposinf(positions[4])
    restored = positions_to_dates(positions, knots, "collapse")
    assert np.array_equal(np.ma.getmaskarray(restored), values.mask)
