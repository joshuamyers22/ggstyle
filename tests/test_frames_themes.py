import datetime as dt

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ggstyle as gs
from ggstyle._frames import to_datetime_index

polars = pytest.importorskip("polars")


@pytest.mark.parametrize("value", ["2020-01-01", 123])
def test_scalar_date_input_rejected(value):
    with pytest.raises(TypeError, match="one-dimensional sequence"):
        to_datetime_index(value)


class TestPolarsInput:
    def test_date_series(self):
        series = polars.Series("d", [dt.date(2020, 1, 1), dt.date(2020, 1, 2)])
        index = to_datetime_index(series)
        assert list(index) == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02")]

    def test_datetime_series(self):
        series = polars.Series(
            "t", [dt.datetime(2020, 1, 1, 9, 30), dt.datetime(2020, 1, 1, 10, 30)]
        )
        index = to_datetime_index(series)
        assert index[0] == pd.Timestamp("2020-01-01 09:30")

    def test_tz_aware_becomes_utc_instants(self):
        """polars gives the underlying UTC instant, which is what the axis wants."""
        naive = polars.Series("t", [dt.datetime(2020, 1, 1, 9, 30)])
        aware = naive.dt.replace_time_zone("America/New_York")
        index = to_datetime_index(aware)
        assert index[0] == pd.Timestamp("2020-01-01 14:30")

    def test_nulls_become_nat(self):
        series = polars.Series("d", [dt.date(2020, 1, 1), None, dt.date(2020, 1, 3)])
        index = to_datetime_index(series)
        assert index.isna().sum() == 1

    def test_whole_frame_rejected(self):
        frame = polars.DataFrame({"date": [dt.date(2020, 1, 1)], "v": [1.0]})
        with pytest.raises(TypeError, match="pass a column of dates"):
            to_datetime_index(frame)

    def test_string_column_not_silently_parsed(self):
        series = polars.Series("d", ["2020-01-01", "2020-01-02"])
        with pytest.raises(TypeError, match="not a date type"):
            to_datetime_index(series)

    def test_dateaxis_accepts_polars(self):
        frame = polars.DataFrame(
            {
                "date": polars.date_range(
                    dt.date(2020, 1, 1), dt.date(2020, 6, 30), "1d", eager=True
                ),
            }
        )
        frame = frame.with_columns(
            polars.Series("v", np.arange(len(frame), dtype=float))
        )
        fig, ax = plt.subplots()
        ax.plot(frame["date"].to_numpy(), frame["v"].to_numpy())
        handle = gs.dates(ax, data=frame["date"]).ticks("monthly").fmt("month")
        assert len(handle.observations) == len(frame)
        assert [t.get_text() for t in ax.get_xticklabels()][:2] == ["Jan", "Feb"]
        plt.close(fig)

    def test_collapse_works_from_polars_dates(self):
        weekdays = [
            d for d in pd.date_range("2020-01-01", "2020-03-31") if d.weekday() < 5
        ]
        series = polars.Series("date", [d.to_pydatetime() for d in weekdays])
        fig, ax = plt.subplots()
        ax.plot(series.to_numpy(), np.arange(len(series), dtype=float))
        handle = gs.dates(ax, data=series).collapse()
        friday = handle.loc("2020-03-06")
        monday = handle.loc("2020-03-09")
        assert monday - friday == pytest.approx(1.0)
        plt.close(fig)


class TestPandasStillWorks:
    """Adding polars must not change pandas behaviour."""

    def test_series(self):
        series = pd.Series(pd.date_range("2020-01-01", periods=3))
        assert list(to_datetime_index(series)) == list(series)

    def test_tz_aware_series(self):
        series = pd.Series(
            pd.date_range("2020-01-01 09:30", periods=2, tz="America/New_York")
        )
        assert to_datetime_index(series)[0] == pd.Timestamp("2020-01-01 14:30")

    def test_dataframe_rejected(self):
        with pytest.raises(TypeError, match="pass a column of dates"):
            to_datetime_index(pd.DataFrame({"date": [1]}))

    def test_plain_list_of_strings(self):
        index = to_datetime_index(["2020-01-01", "2020-02-01"])
        assert index[1] == pd.Timestamp("2020-02-01")

    def test_numpy_datetime64(self):
        values = np.array(["2020-01-01", "2020-01-02"], dtype="datetime64[D]")
        assert to_datetime_index(values)[0] == pd.Timestamp("2020-01-01")

    def test_mixed_awareness_still_rejected(self):
        with pytest.raises(TypeError, match="mixed timezone"):
            to_datetime_index(
                [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02", tz="UTC")]
            )


class TestThemes:
    def test_minimal_is_the_default(self):
        assert gs.DEFAULT_THEME == "minimal"
        assert gs.available_themes()[0] == "minimal"

    def test_grey_is_second(self):
        assert gs.available_themes() == ["minimal", "grey"]

    def test_gray_spelling_accepted(self):
        assert gs.stylesheet("gray") == gs.stylesheet("grey")

    def test_unknown_theme_rejected(self):
        with pytest.raises(ValueError, match="unknown theme"):
            gs.use_theme("solarized")

    def test_minimal_has_white_panel_and_no_spines(self):
        with gs.theme("minimal"):
            assert plt.rcParams["axes.facecolor"] == "white"
            assert plt.rcParams["grid.color"] == "#D9D9D9"
            assert not plt.rcParams["axes.spines.left"]
            assert not plt.rcParams["axes.spines.top"]

    def test_grey_has_grey_panel_and_white_grid(self):
        with gs.theme("grey"):
            assert plt.rcParams["axes.facecolor"] == "#EBEBEB"
            assert plt.rcParams["grid.color"] == "#FFFFFF"

    def test_gridlines_are_behind_the_data(self):
        for name in gs.available_themes():
            with gs.theme(name):
                assert plt.rcParams["axes.axisbelow"] is True

    def test_titles_are_left_aligned(self):
        for name in gs.available_themes():
            with gs.theme(name):
                assert plt.rcParams["axes.titlelocation"] == "left"

    def test_themes_share_type_scale_and_cycle(self):
        """Switching theme changes the surface, not the identity."""
        captured = {}
        for name in gs.available_themes():
            with gs.theme(name):
                captured[name] = (
                    plt.rcParams["axes.prop_cycle"],
                    plt.rcParams["font.size"],
                    plt.rcParams["axes.titlesize"],
                )
        assert len(set(map(str, captured.values()))) == 1

    def test_context_manager_restores_exactly(self):
        before = dict(plt.rcParams)
        with gs.theme("grey"):
            plt.rcParams["lines.linewidth"] = 99
        after = dict(plt.rcParams)
        assert after["axes.facecolor"] == before["axes.facecolor"]
        assert after["lines.linewidth"] == before["lines.linewidth"]

    def test_import_does_not_mutate_rcparams(self):
        """Importing the package must be inert."""
        import importlib

        default_face = matplotlib.rcParamsDefault["axes.facecolor"]
        plt.rcParams.update(matplotlib.rcParamsDefault)
        importlib.reload(gs)
        assert plt.rcParams["axes.facecolor"] == default_face

    def test_stylesheet_usable_standalone(self):
        plt.style.use(str(gs.stylesheet()))
        assert plt.rcParams["axes.facecolor"] == "white"
        plt.rcParams.update(matplotlib.rcParamsDefault)

    def test_theme_does_not_disturb_the_date_axis(self):
        days = pd.bdate_range("2020-01-01", "2021-12-31")
        with gs.theme("grey"):
            fig, ax = plt.subplots()
            ax.plot(days, np.arange(len(days), dtype=float))
            gs.dates(ax).ticks("quarterly").fmt("quarter")
            assert next(t.get_text() for t in ax.get_xticklabels()) == "Q1 2020"
            plt.close(fig)
