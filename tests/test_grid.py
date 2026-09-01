import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ggstyle._grid import render


def test_render_replaces_existing_artists_and_applies_overrides() -> None:
    _, ax = plt.subplots()
    old = ax.axvline(0)

    artists = render(
        ax,
        [old],
        "yearly",
        {"color": "red"},
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2025-01-01"),
        lambda cadence, lo, hi: (pd.DatetimeIndex([lo, hi]), np.array([1.0, 2.0])),
    )

    assert old not in ax.lines
    assert len(artists) == 2
    assert all(artist.get_color() == "red" for artist in artists)
    plt.close(ax.figure)


def test_render_with_no_spec_only_removes_existing_artists() -> None:
    _, ax = plt.subplots()
    old = ax.axvline(0)
    artists = render(
        ax,
        [old],
        None,
        {},
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2025-01-01"),
        lambda cadence, lo, hi: (pd.DatetimeIndex([]), np.empty(0)),
    )
    assert artists == []
    assert old not in ax.lines
    plt.close(ax.figure)
