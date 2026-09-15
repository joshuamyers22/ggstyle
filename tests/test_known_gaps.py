"""Regression tests for the v0.2 safety gaps resolved during v0.3 work."""

from zoneinfo import ZoneInfoNotFoundError

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs


@pytest.fixture
def dates() -> pd.DatetimeIndex:
    """Irregular observations that make calendar and ordinal positions diverge."""
    return pd.bdate_range("2024-01-01", periods=5)


def test_repeated_adoption_rescans_lines_added_after_adoption() -> None:
    """A later accessor call must not leave an accidentally incomplete registry."""
    fig, ax = plt.subplots()
    try:
        first = pd.date_range("2024-01-01", periods=2)
        later = pd.date_range("2024-01-03", periods=2)
        ax.plot(first, [1.0, 2.0])
        handle = gs.dates(ax)

        ax.plot(later, [3.0, 4.0])
        assert gs.dates(ax) is handle
        assert list(handle.observations) == list(first.append(later))
    finally:
        plt.close(fig)


def test_sync_dates_shares_live_registry_updates() -> None:
    """Explicit observations on one member propagate through the shared registry."""
    fig, axes = plt.subplots(2, 1)
    try:
        initial = pd.date_range("2024-01-01", periods=3)
        for ax in axes:
            ax.plot(initial, np.arange(len(initial), dtype=float))

        left, right = gs.sync_dates(axes, mode="collapse")
        new_date = pd.Timestamp("2024-01-04")
        gs.dates(axes[0], data=[new_date])

        assert new_date in left.observations
        assert new_date in right.observations
    finally:
        plt.close(fig)


def test_synchronized_handles_share_live_registry_updates() -> None:
    """A registry revision must propagate to every synchronized handle."""
    fig, axes = plt.subplots(2, 1)
    try:
        initial = pd.date_range("2024-01-01", periods=3)
        for ax in axes:
            ax.plot(initial, np.arange(len(initial), dtype=float))

        left, right = gs.sync_dates(axes, mode="collapse")
        new_date = pd.Timestamp("2024-01-04")
        gs.dates(axes[0], data=[new_date])

        assert new_date in left.observations
        assert new_date in right.observations
        assert left.loc(new_date) == right.loc(new_date)
    finally:
        plt.close(fig)


def test_single_observation_mapping_round_trips_outside_the_knot() -> None:
    """Forward and inverse rules must agree for a one-observation registry."""
    fig, ax = plt.subplots()
    try:
        handle = gs.dates(ax, data=[pd.Timestamp("2024-01-01")]).collapse()
        probe = pd.Timestamp("2024-01-02")
        assert handle.date_at(handle.loc(probe)) == probe
    finally:
        plt.close(fig)


def test_invalid_timezone_does_not_poison_valid_configuration(
    dates: pd.DatetimeIndex,
) -> None:
    """A failed mutator must leave the previous configuration usable."""
    fig, ax = plt.subplots()
    try:
        ax.plot(dates, np.arange(len(dates), dtype=float))
        handle = gs.dates(ax).fmt("iso")

        with pytest.raises(ZoneInfoNotFoundError):
            handle.tz("Not/A_Real_Timezone")

        assert handle.summary().timezone is None
        handle.ticks("daily")
    finally:
        plt.close(fig)


def test_false_disables_previously_enabled_minor_labels(
    dates: pd.DatetimeIndex,
) -> None:
    """False must mean disable, not leave an earlier minor formatter unchanged."""
    fig, ax = plt.subplots()
    try:
        ax.plot(dates, np.arange(len(dates), dtype=float))
        handle = gs.dates(ax).ticks(major="daily", minor="12h").fmt(minor="time")
        assert any(text.get_text() for text in ax.get_xticklabels(minor=True))

        handle.fmt(minor=False)
        assert all(text.get_text() == "" for text in ax.get_xticklabels(minor=True))
    finally:
        plt.close(fig)


def test_externally_removed_annotation_is_safe_across_mode_changes(
    dates: pd.DatetimeIndex,
) -> None:
    """Mode changes must not touch an externally removed managed artist."""
    fig, ax = plt.subplots()
    try:
        ax.plot(dates, np.arange(len(dates), dtype=float))
        handle = gs.dates(ax).vline("2024-01-03", label="event")
        handle._annotations[0].artists[0].remove()

        handle.collapse()
        assert handle.mode == "collapse"
    finally:
        plt.close(fig)


def test_externally_removed_caption_is_safe_to_replace(
    dates: pd.DatetimeIndex,
) -> None:
    """Caption replacement must tolerate external removal of its prior artist."""
    fig, ax = plt.subplots()
    try:
        ax.plot(dates, np.arange(len(dates), dtype=float))
        handle = gs.dates(ax)
        handle.caption(add=True)
        assert handle._caption_artist is not None
        handle._caption_artist.remove()

        handle.caption(add=True)
        assert len(ax.texts) == 1
    finally:
        plt.close(fig)


def test_scale_architecture_keeps_no_artist_geometry_snapshots(
    dates: pd.DatetimeIndex,
) -> None:
    """Scale-based coordinates cannot associate stale geometry with reused IDs."""
    fig, ax = plt.subplots()
    try:
        ax.plot(dates, np.arange(len(dates), dtype=float))
        handle = gs.dates(ax).collapse()

        assert not hasattr(handle, "_original_x")
    finally:
        plt.close(fig)
