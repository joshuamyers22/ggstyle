"""Lifecycle tests for revisioned observation provenance."""

from __future__ import annotations

import gc
from weakref import WeakKeyDictionary, ref

import matplotlib
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs


def test_scatter_added_while_collapsed_refreshes_without_geometry_mutation() -> None:
    fig, ax = plt.subplots()
    try:
        initial = pd.date_range("2024-01-01", periods=2)
        later = pd.date_range("2024-01-03", periods=2)
        ax.plot(initial, [1.0, 2.0])
        handle = gs.dates(ax).collapse()
        collection = ax.scatter(later, [3.0, 4.0])
        original = np.asarray(collection.get_offsets()[:, 0], dtype=float).copy()
        limits = ax.get_xlim()

        previous_revision = handle.revision
        handle.refresh()

        assert handle.revision == previous_revision + 1
        assert list(handle.observations) == list(initial.append(later))
        assert np.array_equal(
            np.asarray(collection.get_offsets()[:, 0], dtype=float), original
        )
        assert np.allclose(ax.get_xlim(), limits)
        assert np.allclose(
            ax.xaxis.get_transform().transform(original), [2.0, 3.0]
        )
    finally:
        plt.close(fig)


def test_polygon_only_axes_discovers_dates_without_mutating_geometry() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=3)
        collection = ax.fill_between(
            dates, [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]
        )
        vertices = [path.vertices.copy() for path in collection.get_paths()]
        codes = [path.codes.copy() for path in collection.get_paths()]

        handle = gs.dates(ax).collapse().expand().collapse()

        assert list(handle.observations) == list(dates)
        assert np.allclose(
            ax.xaxis.get_transform().transform(mdates.date2num(dates)),
            np.arange(3.0),
        )
        for path, expected_vertices, expected_codes in zip(
            collection.get_paths(), vertices, codes, strict=True
        ):
            assert np.array_equal(path.vertices, expected_vertices)
            assert np.array_equal(path.codes, expected_codes)
    finally:
        plt.close(fig)


@pytest.mark.parametrize("missing", ["mask", "nan"])
def test_polygon_discovery_splits_at_missing_bounds(missing: str) -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=5)
        lower = np.ma.array(
            [1.0, 2.0, 3.0, 2.0, 1.0],
            mask=[False, False, missing == "mask", False, False],
        )
        if missing == "nan":
            lower[2] = np.nan
        collection = ax.fill_between(dates, lower, np.asarray(lower) + 1.0)

        handle = gs.dates(ax)

        assert list(handle.observations) == list(dates[[0, 1, 3, 4]])
        assert len(collection.get_paths()) == 2
    finally:
        plt.close(fig)


def test_polygon_discovery_uses_only_where_selected_source_vertices() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=5)
        selected = np.array([False, True, True, False, False])
        ax.fill_between(dates, np.arange(5.0), 0.0, where=selected)

        handle = gs.dates(ax)

        assert list(handle.observations) == list(dates[[1, 2]])
    finally:
        plt.close(fig)


def test_polygon_discovery_excludes_interpolated_crossing_vertices() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=5, freq="2D")
        values = np.array([-1.0, 1.0, -1.0, 1.0, -1.0])
        collection = ax.fill_between(
            dates,
            values,
            0.0,
            where=values > 0,
            interpolate=True,
        )
        source_numbers = mdates.date2num(dates[[1, 3]])
        rendered_numbers = np.concatenate(
            [path.vertices[:, 0] for path in collection.get_paths()]
        )

        handle = gs.dates(ax)

        assert list(handle.observations) == list(dates[[1, 3]])
        assert any(
            not np.any(np.isclose(source_numbers, number))
            for number in rendered_numbers
        )
    finally:
        plt.close(fig)


def test_polygon_path_rebuild_replaces_its_provenance() -> None:
    fig, ax = plt.subplots()
    try:
        initial = pd.date_range("2024-01-01", periods=3)
        replacement = pd.date_range("2024-02-01", periods=2)
        collection = ax.fill_between(initial, [1.0, 2.0, 1.0], 0.0)
        handle = gs.dates(ax).collapse()
        x = np.asarray(mdates.date2num(replacement), dtype=float)
        vertices = np.array(
            [
                [x[0], 0.0],
                [x[0], 1.0],
                [x[1], 2.0],
                [x[1], 0.0],
                [x[1], 0.0],
                [x[0], 0.0],
            ]
        )
        collection.set_verts([vertices])

        handle.refresh()

        assert list(handle.observations) == list(replacement)
    finally:
        plt.close(fig)


def test_removed_polygon_stops_contributing_on_refresh() -> None:
    fig, ax = plt.subplots()
    try:
        first = pd.date_range("2024-01-01", periods=2)
        second = pd.date_range("2024-02-01", periods=2)
        removed = ax.fill_between(first, [1.0, 2.0], 0.0)
        ax.fill_between(second, [2.0, 1.0], 0.0)
        handle = gs.dates(ax)

        removed.remove()
        handle.refresh()

        assert list(handle.observations) == list(second)
    finally:
        plt.close(fig)


def test_polygon_refresh_propagates_through_shared_registry() -> None:
    fig, axes = plt.subplots(2, 1)
    try:
        initial = pd.date_range("2024-01-01", periods=2)
        axes[0].plot(initial, [1.0, 2.0])
        axes[1].fill_between(initial, [2.0, 1.0], 0.0)
        left, right = gs.sync_dates(axes, mode="collapse")
        later = pd.date_range("2024-01-03", periods=2)
        axes[1].fill_between(later, [1.0, 2.0], 0.0)

        left.refresh()

        expected = initial.append(later)
        assert list(left.observations) == list(expected)
        assert left.observations.equals(right.observations)
        assert np.allclose(
            axes[0].xaxis.get_transform().transform(mdates.date2num(expected)),
            np.arange(4.0),
        )
    finally:
        plt.close(fig)


def test_midpoint_step_polygon_requires_explicit_source_dates() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=4)
        ax.fill_between(dates, [1.0, 2.0, 1.0, 2.0], 0.0, step="mid")

        with pytest.raises(gs.DateDiscoveryError, match=r"step='mid'.*dates\(ax, data="):
            gs.dates(ax)

        handle = gs.dates(ax, data=dates)
        assert list(handle.observations) == list(dates)
    finally:
        plt.close(fig)


@pytest.mark.parametrize("step", ["pre", "post"])
def test_endpoint_step_polygons_discover_source_dates(step: str) -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=4)
        ax.fill_between(dates, [1.0, 2.0, 1.0, 2.0], 0.0, step=step)

        handle = gs.dates(ax)

        assert list(handle.observations) == list(dates)
    finally:
        plt.close(fig)


def test_fill_betweenx_is_rejected_on_an_x_date_handle() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=3)
        ax.fill_betweenx(dates, [1.0, 2.0, 1.0], 0.0)

        with pytest.raises(gs.DateDiscoveryError, match="fill_betweenx"):
            gs.dates(ax, data=dates)
    finally:
        plt.close(fig)


def test_polygon_with_non_data_transform_is_rejected() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=3)
        ax.fill_between(dates, [1.0, 2.0, 1.0], 0.0)
        handle = gs.dates(ax).collapse()
        revision = handle.revision
        observations = handle.observations.copy()
        later = pd.date_range("2024-02-01", periods=3)
        collection = ax.fill_between(later, [2.0, 1.0, 2.0], 0.0)
        collection.set_transform(ax.transAxes)

        with pytest.raises(gs.DateDiscoveryError, match=r"not use ax\.transData"):
            handle.refresh()

        assert handle.revision == revision
        assert handle.observations.equals(observations)
        assert ax.get_xscale() == "ggstyle-collapsed-date"
    finally:
        plt.close(fig)


def test_scatter_discovery_excludes_masked_offsets() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=3)
        values = np.ma.array([1.0, 2.0, 3.0], mask=[False, True, False])
        ax.scatter(dates, values)

        handle = gs.dates(ax)

        assert list(handle.observations) == [dates[0], dates[2]]
        assert handle.summary().missing_values == 0
    finally:
        plt.close(fig)


def test_native_and_managed_annotations_do_not_contribute_observations() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=2)
        ax.plot(dates, [1.0, 2.0])
        handle = gs.dates(ax).vline("2024-02-01").grid("daily")
        ax.axvline(pd.Timestamp("2024-03-01"))

        handle.refresh()

        assert list(handle.observations) == list(dates)
    finally:
        plt.close(fig)


def test_removed_and_mutated_artists_rebuild_their_contributions() -> None:
    fig, ax = plt.subplots()
    try:
        first = pd.date_range("2024-01-01", periods=2)
        second = pd.date_range("2024-01-03", periods=2)
        first_line = ax.plot(first, [1.0, 2.0])[0]
        second_line = ax.plot(second, [3.0, 4.0])[0]
        handle = gs.dates(ax)

        first_line.remove()
        replacement = pd.date_range("2024-01-05", periods=2)
        second_line.set_xdata(replacement)
        handle.refresh()

        assert list(handle.observations) == list(replacement)
    finally:
        plt.close(fig)


def test_collapsed_refresh_shrinks_registry_and_replaces_scale_snapshot() -> None:
    fig, ax = plt.subplots()
    try:
        first = pd.date_range("2024-01-01", periods=2)
        second = pd.date_range("2024-01-03", periods=2)
        ax.plot(first, [1.0, 2.0])
        removed = ax.plot(second, [3.0, 4.0])[0]
        handle = gs.dates(ax).collapse()
        removed.remove()

        handle.refresh()

        assert list(handle.observations) == list(first)
        assert np.allclose(
            ax.xaxis.get_transform().transform(mdates.date2num(first)), [0.0, 1.0]
        )
    finally:
        plt.close(fig)


def test_collapsed_refresh_rejects_empty_candidate_without_committing() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=2)
        line = ax.plot(dates, [1.0, 2.0])[0]
        handle = gs.dates(ax).collapse()
        revision = handle.revision
        line.remove()

        with pytest.raises(RuntimeError, match="collapsed registry"):
            handle.refresh()

        assert handle.revision == revision
        assert list(handle.observations) == list(dates)
        assert ax.get_xscale() == "ggstyle-collapsed-date"
    finally:
        plt.close(fig)


def test_explicit_observations_remain_after_artist_removal() -> None:
    fig, ax = plt.subplots()
    try:
        plotted = pd.date_range("2024-01-01", periods=2)
        explicit = pd.Timestamp("2024-01-10")
        line = ax.plot(plotted, [1.0, 2.0])[0]
        handle = gs.dates(ax, data=[explicit])

        line.remove()
        handle.refresh()

        assert list(handle.observations) == [explicit]
    finally:
        plt.close(fig)


def test_shared_refresh_rolls_back_every_member_on_apply_failure(monkeypatch) -> None:
    fig, axes = plt.subplots(2, 1)
    try:
        initial = pd.date_range("2024-01-01", periods=2)
        for ax in axes:
            ax.plot(initial, [1.0, 2.0])
        handles = gs.sync_dates(axes, mode="collapse")
        registry = handles[0]._registry
        failing = registry.members[-1]
        original_set_xscale = failing.ax.set_xscale
        calls = 0

        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("injected scale failure")
            return original_set_xscale(*args, **kwargs)

        monkeypatch.setattr(failing.ax, "set_xscale", fail_once)
        axes[0].plot([pd.Timestamp("2024-01-03")], [3.0])
        revision = handles[0].revision
        observations = handles[0].observations.copy()
        limits = [ax.get_xlim() for ax in axes]

        with pytest.raises(RuntimeError, match="injected scale failure"):
            handles[0].refresh()

        assert all(handle.revision == revision for handle in handles)
        assert all(handle.observations.equals(observations) for handle in handles)
        assert all(
            np.allclose(ax.get_xlim(), limit)
            for ax, limit in zip(axes, limits, strict=True)
        )
        assert all(ax.get_xscale() == "ggstyle-collapsed-date" for ax in axes)
    finally:
        plt.close(fig)


def test_sync_preflight_failure_does_not_refresh_existing_handles() -> None:
    fig, axes = plt.subplots(2, 1)
    try:
        dates = pd.date_range("2024-01-01", periods=2)
        for ax in axes:
            ax.plot(dates, [1.0, 2.0])
        handles = [gs.dates(ax) for ax in axes]
        revisions = [handle.revision for handle in handles]
        axes[1].plot(dates, [0.2, 0.8], transform=axes[1].transAxes)

        with pytest.raises(gs.DateDiscoveryError):
            gs.sync_dates(axes)

        assert [handle.revision for handle in handles] == revisions
        assert handles[0]._registry is not handles[1]._registry
    finally:
        plt.close(fig)


def test_shared_refresh_rescans_all_members_and_updates_every_scale() -> None:
    fig, axes = plt.subplots(2, 1)
    try:
        left_dates = pd.date_range("2024-01-01", periods=2)
        right_dates = pd.date_range("2024-01-03", periods=2)
        axes[0].plot(left_dates, [1.0, 2.0])
        axes[1].plot(right_dates, [3.0, 4.0])
        left, right = gs.sync_dates(axes, mode="collapse")
        new_date = pd.Timestamp("2024-01-05")
        axes[1].plot([new_date], [5.0])

        left.refresh()

        assert new_date in left.observations
        assert left.observations.equals(right.observations)
        expected = np.arange(len(left.observations), dtype=float)
        numbers = mdates.date2num(left.observations)
        assert np.allclose(axes[0].xaxis.get_transform().transform(numbers), expected)
        assert np.allclose(axes[1].xaxis.get_transform().transform(numbers), expected)
    finally:
        plt.close(fig)


def test_artist_provenance_uses_weak_keys() -> None:
    fig, ax = plt.subplots()
    try:
        line = ax.plot(pd.date_range("2024-01-01", periods=2), [1.0, 2.0])[0]
        handle = gs.dates(ax)
        provenance = handle._registry.artist_values
        assert isinstance(provenance, WeakKeyDictionary)
        assert line in provenance

        weak_line = ref(line)
        line.remove()
        del line
        gc.collect()
        assert weak_line() is None
        assert len(provenance) == 0
    finally:
        plt.close(fig)


def test_dispose_is_idempotent_and_allows_fresh_adoption() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=2)
        ax.plot(dates, [1.0, 2.0])
        handle = gs.dates(ax).vline(dates[0]).grid("daily")
        data_lines = len(ax.lines)

        handle.dispose()
        handle.dispose()

        assert handle.disposed
        assert handle not in handle._registry.members
        assert len(ax.lines) == data_lines
        replacement = gs.dates(ax)
        assert replacement is not handle
        assert not replacement.disposed
    finally:
        plt.close(fig)


def test_disposed_member_stops_contributing_on_the_next_shared_refresh() -> None:
    fig, axes = plt.subplots(2, 1)
    try:
        axes[0].plot(pd.date_range("2024-01-01", periods=2), [1.0, 2.0])
        axes[1].plot(pd.date_range("2024-02-01", periods=2), [3.0, 4.0])
        left, right = gs.sync_dates(axes)

        right.dispose()
        left.refresh()

        assert all(timestamp.month == 1 for timestamp in left.observations)
        assert right not in left._registry.members
    finally:
        plt.close(fig)


def test_unsupported_line_transform_fails_before_registry_commit() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=2)
        ax.plot(dates, [1.0, 2.0])
        handle = gs.dates(ax).collapse()
        revision = handle.revision
        observations = handle.observations.copy()
        transform = ax.transAxes
        ax.plot(dates, [0.2, 0.8], transform=transform)

        with pytest.raises(gs.DateDiscoveryError, match=r"not ax\.transData"):
            handle.refresh()

        assert handle.revision == revision
        assert handle.observations.equals(observations)
        assert ax.get_xscale() == "ggstyle-collapsed-date"
        assert np.allclose(
            ax.xaxis.get_transform().transform(mdates.date2num(dates)), [0.0, 1.0]
        )
    finally:
        plt.close(fig)


def test_numeric_line_on_date_axis_requires_complete_explicit_observations() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=2)
        ax.plot(dates, [1.0, 2.0])
        numbers = mdates.date2num(dates + pd.Timedelta(days=2))
        ax.plot(numbers, [3.0, 4.0])

        with pytest.raises(gs.DateDiscoveryError, match="numeric Line2D"):
            gs.dates(ax)

        handle = gs.dates(ax, data=dates.append(dates + pd.Timedelta(days=2)))
        assert len(handle.observations) == 4
    finally:
        plt.close(fig)


def test_numeric_decoration_outside_data_space_is_ignored() -> None:
    fig, ax = plt.subplots()
    try:
        dates = pd.date_range("2024-01-01", periods=2)
        ax.plot(dates, [1.0, 2.0])
        ax.plot([0.1, 0.9], [0.2, 0.8], transform=ax.transAxes)

        handle = gs.dates(ax)

        assert list(handle.observations) == list(dates)
    finally:
        plt.close(fig)
