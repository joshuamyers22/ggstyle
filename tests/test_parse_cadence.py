import pandas as pd
import pytest

from ggstyle._cadence import Cadence, auto_cadence, best_for_count, resolve
from ggstyle._parse import normalize_alias, to_offset, to_timestamp


class TestPartialStrings:
    """Partial date strings expand to whole periods, pandas-style."""

    @pytest.mark.parametrize(
        "text,start,end",
        [
            ("2020", "2020-01-01 00:00:00", "2020-12-31 23:59:59.999999"),
            ("2020-03", "2020-03-01 00:00:00", "2020-03-31 23:59:59.999999"),
            ("2020-03-15", "2020-03-15 00:00:00", "2020-03-15 23:59:59.999999"),
        ],
    )
    def test_period_bounds(self, text, start, end):
        assert to_timestamp(text, "start") == pd.Timestamp(start)
        assert to_timestamp(text, "end") == pd.Timestamp(end)

    def test_specific_instant_ignores_side(self):
        ts = pd.Timestamp("2020-03-15 14:30:00")
        assert to_timestamp(ts, "start") == ts
        assert to_timestamp(ts, "end") == ts

    def test_rejects_nonsense(self):
        with pytest.raises(TypeError):
            to_timestamp("not a date")

    def test_rejects_bad_side(self):
        with pytest.raises(ValueError):
            to_timestamp("2020", side="middle")


class TestLegacyAliases:
    """pandas 3.0 dropped M/Q/Y/H; a decade of muscle memory did not."""

    @pytest.mark.parametrize(
        "legacy,modern",
        [("6M", "6ME"), ("M", "ME"), ("Q", "QE"), ("Y", "YE"), ("H", "h"), ("T", "min")],
    )
    def test_normalized(self, legacy, modern):
        assert to_offset(legacy) == to_offset(modern)

    def test_modern_untouched(self):
        assert to_offset("3ME") == to_offset("3ME")

    def test_anchored_suffix_survives(self):
        assert normalize_alias("W-MON") == "W-MON"


class TestCadenceResolution:
    @pytest.mark.parametrize(
        "spec,expected",
        [
            ("monthly", Cadence("month", 1, "start")),
            ("quarterly", Cadence("quarter", 1, "start")),
            ("month-end", Cadence("month", 1, "end")),
            ("quarter-end", Cadence("quarter", 1, "end")),
            ("3M", Cadence("month", 3, "end")),
            ("3MS", Cadence("month", 3, "start")),
            ("2W", Cadence("week", 2, "start")),
        ],
    )
    def test_named_and_alias(self, spec, expected):
        assert resolve(spec) == expected

    def test_anchor_changes_freq(self):
        assert Cadence("month", 1, "start").freq == "MS"
        assert Cadence("month", 1, "end").freq == "ME"
        assert Cadence("month", 3, "start").freq == "3MS"

    def test_rejects_unknown_unit(self):
        with pytest.raises(ValueError):
            Cadence("fortnight")


class TestAutoCadenceTable:
    """Section 6.7 of the plan, as executable spec.

    Boundaries are tested on both sides so a threshold cannot drift unnoticed.
    """

    @pytest.mark.parametrize(
        "span,unit",
        [
            (pd.Timedelta(hours=6), "hour"),
            (pd.Timedelta(hours=23), "hour"),
            (pd.Timedelta(days=1), "day"),
            (pd.Timedelta(days=7), "day"),
            (pd.Timedelta(days=8), "week"),
            (pd.Timedelta(days=92), "week"),
            (pd.Timedelta(days=93), "month"),
            (pd.Timedelta(days=548), "month"),
            (pd.Timedelta(days=549), "quarter"),
            (pd.Timedelta(days=1826), "quarter"),
            (pd.Timedelta(days=1827), "year"),
            (pd.Timedelta(days=5479), "year"),
            (pd.Timedelta(days=5480), "year"),
        ],
    )
    def test_major_unit(self, span, unit):
        assert auto_cadence(span)[0].unit == unit

    def test_very_long_span_uses_multi_year(self):
        major, _, _ = auto_cadence(pd.Timedelta(days=365 * 40))
        assert (major.unit, major.interval) == ("year", 5)

    def test_minor_is_always_finer(self):
        for days in (0.5, 3, 30, 200, 1000, 3000, 12000):
            major, minor, _ = auto_cadence(pd.Timedelta(days=days))
            assert minor.approx_seconds < major.approx_seconds


class TestCountSearch:
    @pytest.mark.parametrize("n", [3, 5, 8, 12])
    def test_roughly_n_ticks(self, n):
        span = pd.Timedelta(days=365 * 3)
        cadence = best_for_count(span, n)
        count = span.total_seconds() / cadence.approx_seconds
        assert 0.5 * n <= count <= 2.0 * n

    def test_rejects_zero(self):
        with pytest.raises(ValueError):
            best_for_count(pd.Timedelta(days=1), 0)
