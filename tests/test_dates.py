import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

import ggstyle as gs


@pytest.fixture
def business_days():
    """Two years of weekdays -- gaps every weekend."""
    return pd.bdate_range("2020-01-01", "2021-12-31")


@pytest.fixture
def ax(business_days):
    fig, ax = plt.subplots()
    ax.plot(business_days, np.arange(len(business_days), dtype=float))
    yield ax
    plt.close(fig)


@pytest.fixture
def intraday():
    fig, ax = plt.subplots()
    index = pd.date_range("2024-03-15 09:30", "2024-03-15 16:00", freq="min")
    ax.plot(index, np.arange(len(index), dtype=float))
    yield ax
    plt.close(fig)


def labels(ax):
    return [t.get_text() for t in ax.get_xticklabels()]


def positions(ax):
    return list(ax.xaxis.get_major_locator()())


class TestAdoption:
    def test_invalid_mode_rejected(self, ax):
        with pytest.raises(ValueError, match="mode must be"):
            gs.dates(ax, mode="typo")

    def test_adopts_plain_matplotlib_axes(self, ax):
        handle = gs.dates(ax)
        assert handle.mode == "show"
        assert len(handle.observations) > 400

    def test_same_handle_returned_twice(self, ax):
        assert gs.dates(ax) is gs.dates(ax)

    def test_rejects_non_date_axis(self):
        fig, bad = plt.subplots()
        bad.plot([1, 2, 3], [1, 2, 3])
        with pytest.raises(TypeError, match="does not look like dates"):
            gs.dates(bad)
        plt.close(fig)

    def test_empty_axes_is_tolerated(self):
        fig, empty = plt.subplots()
        assert gs.dates(empty).mode == "show"
        plt.close(fig)


class TestTickPlacement:
    @pytest.mark.parametrize("value", [0, -1, 1.5, True])
    def test_tick_count_must_be_positive_integer(self, ax, value):
        with pytest.raises(ValueError, match="positive integer"):
            gs.dates(ax).ticks(n=value)

    def test_excessive_tick_count_rejected(self, ax):
        with pytest.raises(ValueError, match="coarser cadence"):
            gs.dates(ax).ticks("minutely")

    def test_named_cadence_lands_on_quarters(self, ax):
        gs.dates(ax).ticks("quarterly").fmt("iso")
        months = {pd.Timestamp(t).month for t in pd.to_datetime(labels(ax))}
        assert months <= {1, 4, 7, 10}

    def test_anchor_start_vs_end(self, ax):
        gs.dates(ax).ticks("month-start").fmt("iso")
        assert all(pd.Timestamp(t).day == 1 for t in labels(ax))
        gs.dates(ax).ticks("month-end").fmt("iso")
        assert all(pd.Timestamp(t).day > 25 for t in labels(ax))

    def test_every_accepts_legacy_alias(self, ax):
        gs.dates(ax).ticks(every="3M").fmt("iso")
        assert len(labels(ax)) == pytest.approx(8, abs=2)

    def test_n_gives_roughly_n_ticks(self, ax):
        gs.dates(ax).ticks(n=6)
        assert 3 <= len(positions(ax)) <= 12

    def test_explicit_ticks(self, ax):
        gs.dates(ax).ticks(at=["2020-06-01", "2021-06-01"]).fmt("iso")
        assert labels(ax) == ["2020-06-01", "2021-06-01"]

    def test_conflicting_specs_rejected(self, ax):
        with pytest.raises(TypeError):
            gs.dates(ax).ticks("monthly", n=5)

    def test_minor_ticks_are_unlabelled(self, ax):
        gs.dates(ax).ticks(major="yearly", minor="quarterly")
        assert len(ax.xaxis.get_minor_locator()()) > 0
        assert all(t.get_text() == "" for t in ax.get_xticklabels(minor=True))


class TestFormats:
    @pytest.mark.parametrize(
        "spec,expected",
        [
            ("iso", "2020-06-01"),
            ("year", "2020"),
            ("month", "Jun"),
            ("month-year", "Jun 2020"),
            ("quarter", "Q2 2020"),
            ("day", "Jun 1"),
            ("%b '%y", "Jun '20"),
        ],
    )
    def test_presets(self, ax, spec, expected):
        gs.dates(ax).ticks(at=["2020-06-01"]).fmt(spec)
        assert labels(ax) == [expected]

    def test_callable_format(self, ax):
        gs.dates(ax).ticks(at=["2020-06-01"]).fmt(lambda d: f"week {d.isocalendar().week}")
        assert labels(ax) == ["week 23"]

    def test_unknown_format_rejected(self, ax):
        with pytest.raises(ValueError, match="unknown format"):
            gs.dates(ax).fmt("bananas")

    def test_concise_shows_year_only_when_it_changes(self, ax):
        handle = gs.dates(ax).zoom("2020", "2021").ticks("quarterly").fmt("concise")
        text = labels(ax)
        with_year = [t for t in text if "\n" in t]
        years = {handle.date_at(p).year for p in positions(ax)}
        assert len(with_year) == len(years), text
        assert len(text) > len(with_year)  # most labels carry no year


class TestOrthogonality:
    """Placement and labelling are independent. This is a test, not a hope."""

    def test_changing_format_does_not_move_ticks(self, ax):
        handle = gs.dates(ax).ticks("quarterly")
        before = positions(ax)
        handle.fmt("month-year")
        assert positions(ax) == before

    def test_changing_cadence_does_not_change_format(self, ax):
        handle = gs.dates(ax).ticks("quarterly").fmt("iso")
        handle.ticks("monthly")
        assert all(len(t) == 10 and t.count("-") == 2 for t in labels(ax))


class TestRange:
    def test_partial_string_covers_whole_period(self, ax):
        handle = gs.dates(ax).zoom("2020", "2020")
        lo, hi = handle._visible_range()
        assert lo == pd.Timestamp("2020-01-01")
        assert hi.year == 2020 and hi.month == 12 and hi.day == 31

    def test_month_string(self, ax):
        handle = gs.dates(ax).zoom("2020-03", "2020-03")
        lo, hi = handle._visible_range()
        assert (lo.month, hi.month) == (3, 3)

    def test_open_ended(self, ax):
        handle = gs.dates(ax)
        _, original_hi = handle._visible_range()
        handle.zoom("2021-01", None)
        lo, hi = handle._visible_range()
        assert lo == pd.Timestamp("2021-01-01")
        assert abs((hi - original_hi).days) < 2

    def test_last_measures_from_final_observation_not_today(self, ax):
        handle = gs.dates(ax).zoom(last="6M")
        lo, hi = handle._visible_range()
        assert hi.year == 2021 and hi.month == 12
        assert lo.year == 2021 and lo.month == 6

    def test_ytd(self, ax):
        handle = gs.dates(ax).zoom(ytd=True)
        lo, _ = handle._visible_range()
        assert (lo.year, lo.month, lo.day) == (2021, 1, 1)

    def test_pad(self, ax):
        handle = gs.dates(ax)
        lo_before, hi_before = handle._visible_range()
        handle.pad(left="1M", right="1M")
        lo_after, hi_after = handle._visible_range()
        assert lo_after < lo_before and hi_after > hi_before


class TestCollapse:
    def test_weekends_get_no_space(self, ax):
        handle = gs.dates(ax).collapse()
        assert handle.mode == "collapse"
        friday = handle.loc("2020-03-06")
        monday = handle.loc("2020-03-09")
        assert monday - friday == pytest.approx(1.0)

    def test_show_mode_keeps_the_gap(self, ax):
        handle = gs.dates(ax)
        friday = handle.loc("2020-03-06")
        monday = handle.loc("2020-03-09")
        assert monday - friday == pytest.approx(3.0)

    def test_line_data_is_remapped_and_restored(self, ax):
        handle = gs.dates(ax)
        original = np.array(ax.lines[0].get_xdata(orig=False), dtype=float)
        handle.collapse()
        collapsed = np.array(ax.lines[0].get_xdata(orig=False), dtype=float)
        assert np.allclose(collapsed, np.arange(len(original)))
        handle.expand()
        restored = np.array(ax.lines[0].get_xdata(orig=False), dtype=float)
        assert np.allclose(restored, original)

    def test_relative_order_survives_mode_change(self, ax):
        """The invariant that keeps annotations honest."""
        handle = gs.dates(ax)
        probes = ["2020-02-03", "2020-06-15", "2021-01-04", "2021-11-30"]
        shown = [handle.loc(p) for p in probes]
        handle.collapse()
        collapsed = [handle.loc(p) for p in probes]
        assert shown == sorted(shown)
        assert collapsed == sorted(collapsed)

    def test_observation_positions_are_exact_integers(self, ax):
        handle = gs.dates(ax).collapse()
        assert handle.loc("2020-01-01") == pytest.approx(0.0)
        assert handle.loc("2020-01-02") == pytest.approx(1.0)

    def test_date_in_a_gap_interpolates(self, ax):
        handle = gs.dates(ax).collapse()
        saturday = handle.loc("2020-03-07")
        assert handle.loc("2020-03-06") < saturday < handle.loc("2020-03-09")

    def test_snap_rounds_to_nearest_observation(self, ax):
        handle = gs.dates(ax).collapse()
        assert handle.loc("2020-03-07", snap=True) == pytest.approx(
            handle.loc("2020-03-06")
        )

    def test_strict_rejects_unobserved_date(self, ax):
        handle = gs.dates(ax).collapse()
        with pytest.raises(KeyError):
            handle.loc("2020-03-07", strict=True)

    def test_ticks_land_on_real_trading_days(self, ax):
        gs.dates(ax).collapse().ticks("monthly")
        for position in positions(ax):
            assert float(position) == pytest.approx(round(float(position)), abs=1e-9)

    def test_collapse_needs_observations(self):
        fig, empty = plt.subplots()
        with pytest.raises(RuntimeError, match="needs observed dates"):
            gs.dates(empty).collapse()
        plt.close(fig)

    def test_multi_series_uses_union_of_dates(self):
        fig, multi = plt.subplots()
        a = pd.bdate_range("2020-01-01", "2020-01-10")
        b = pd.date_range("2020-01-01", "2020-01-10", freq="D")
        multi.plot(a, np.arange(len(a), dtype=float))
        multi.plot(b, np.arange(len(b), dtype=float))
        handle = gs.dates(multi)
        assert len(handle.observations) == len(b)
        plt.close(fig)

    def test_date_at_inverts_loc(self, ax):
        handle = gs.dates(ax).collapse()
        assert handle.date_at(handle.loc("2020-06-15")).normalize() == pd.Timestamp(
            "2020-06-15"
        )


class TestAnnotations:
    def test_vline_lands_correctly_in_both_modes(self, ax):
        handle = gs.dates(ax).vline("2020-06-15", label="event")
        line = handle._annotations[0].artists[0]
        assert line.get_xdata()[0] == pytest.approx(handle.loc("2020-06-15"))
        handle.collapse()
        line = handle._annotations[0].artists[0]
        assert line.get_xdata()[0] == pytest.approx(handle.loc("2020-06-15"))

    def test_span_replays_on_mode_change(self, ax):
        handle = gs.dates(ax).span("2020-02-19", "2020-03-23", label="drawdown")
        rect = handle._annotations[0].artists[0]
        before = rect.get_x()
        handle.collapse()
        rect = handle._annotations[0].artists[0]
        assert rect.get_x() != pytest.approx(before)
        assert rect.get_x() == pytest.approx(handle.loc("2020-02-19"))
        assert rect.get_x() + rect.get_width() == pytest.approx(
            handle.loc("2020-03-23")
        )

    def test_spans_from_frame(self, ax):
        events = pd.DataFrame(
            {
                "start": ["2020-02-19", "2021-01-04"],
                "end": ["2020-03-23", "2021-02-01"],
                "name": ["covid", "gamestop"],
            }
        )
        handle = gs.dates(ax).spans(events, label="name")
        assert len(handle._annotations) == 2

    def test_annotation_lines_are_not_treated_as_data(self, ax):
        handle = gs.dates(ax).vline("2020-06-15")
        handle.collapse()
        data_line = ax.lines[0]
        assert np.allclose(
            np.array(data_line.get_xdata(), dtype=float),
            np.arange(len(handle.observations)),
        )


class TestGrid:
    def test_grid_cadence_independent_of_ticks(self, ax):
        handle = gs.dates(ax).ticks("monthly").grid("yearly")
        assert 2 <= len(handle._grid_artists) <= 3
        assert len(positions(ax)) > 4 * len(handle._grid_artists)

    def test_grid_false_removes(self, ax):
        handle = gs.dates(ax).grid("yearly").grid(False)
        assert handle._grid_artists == []


class TestTimezone:
    def test_display_only(self):
        fig, tz_ax = plt.subplots()
        index = pd.date_range("2024-03-15 12:00", periods=6, freq="h")
        tz_ax.plot(index, np.arange(6, dtype=float))
        handle = gs.dates(tz_ax)
        before = np.array(tz_ax.lines[0].get_xdata(), dtype=float)
        handle.tz("America/New_York").ticks(at=["2024-03-15 12:00"]).fmt("time")
        assert labels(tz_ax) == ["08:00"]
        assert np.allclose(np.array(tz_ax.lines[0].get_xdata(), dtype=float), before)
        plt.close(fig)

    def test_mixed_awareness_rejected(self):
        fig, mixed = plt.subplots()
        with pytest.raises(TypeError, match="mixed timezone"):
            gs.dates(
                mixed,
                data=[pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02", tz="UTC")],
            )
        plt.close(fig)


class TestIntraday:
    def test_auto_cadence_is_hourly(self, intraday):
        gs.dates(intraday)
        assert len(labels(intraday)) >= 5

    def test_concise_prepends_date_on_first_tick(self, intraday):
        gs.dates(intraday).fmt("concise")
        assert "\n" in labels(intraday)[0]


class TestRefresh:
    def test_labels_track_interactive_zoom(self, ax):
        gs.dates(ax)
        wide = len(positions(ax))
        ax.set_xlim(
            mdates.date2num(pd.Timestamp("2020-03-01")),
            mdates.date2num(pd.Timestamp("2020-04-01")),
        )
        assert positions(ax) != wide or len(labels(ax)) > 0
        assert all(
            pd.Timestamp("2020-02-01") <= pd.Timestamp(mdates.num2date(p)).tz_localize(None)
            <= pd.Timestamp("2020-05-01")
            for p in positions(ax)
        )


class TestRegressions:
    """Bugs the suite missed and the smoke test caught. One test each."""

    def test_anchored_candidates_land_at_midnight(self):
        """pandas keeps the start's time-of-day even for anchored offsets.

        A padded start of 13:30 produced "month starts" at 13:30 on the 1st,
        which sort *after* the midnight observation they are meant to mark.
        """
        from ggstyle._cadence import Cadence, periods_between

        candidates = periods_between(
            Cadence("month"), pd.Timestamp("2020-01-01"), pd.Timestamp("2020-06-30")
        )
        assert all(ts.hour == 0 and ts.minute == 0 for ts in candidates)
        assert all(ts.day == 1 for ts in candidates)

    def test_no_phantom_tick_before_first_observation(self, ax):
        """A period containing no observations must not borrow its neighbour's."""
        handle = gs.dates(ax).collapse().ticks("monthly").zoom("2020-01", "2020-06")
        first = handle.date_at(positions(ax)[0])
        assert first >= pd.Timestamp("2020-01-01")
        assert len(set(positions(ax))) == len(positions(ax))  # no duplicates

    def test_hourly_ticks_land_on_the_hour(self, intraday):
        """A session starting at 09:30 must not produce 09:10, 10:10, ..."""
        gs.dates(intraday).ticks(every="1h").fmt("time")
        assert all(t.endswith(":00") for t in labels(intraday)), labels(intraday)

    def test_daily_ticks_land_at_midnight(self, ax):
        handle = gs.dates(ax).ticks("daily").zoom("2020-03-02", "2020-03-06")
        for position in positions(ax):
            assert handle.date_at(position).normalize() == handle.date_at(position)
