"""Tests for timedeltaparser."""

import pytest
from datetime import timedelta
from timedeltaparser import parse_duration, ParseError, ParsedDuration


class TestBasicParsing:
    def test_single_unit(self):
        d = parse_duration("30 seconds")
        assert d == timedelta(seconds=30)

    def test_multiple_units(self):
        d = parse_duration("1 hour 30 minutes")
        assert d == timedelta(hours=1, minutes=30)

    def test_compact_format(self):
        d = parse_duration("2h30m")
        assert d == timedelta(hours=2, minutes=30)

    def test_all_units(self):
        d = parse_duration("1w 2d 3h 4m 5s")
        expected = timedelta(weeks=1, days=2, hours=3, minutes=4, seconds=5)
        assert d == expected


class TestDecimalSupport:
    def test_decimal_hours(self):
        d = parse_duration("1.5 hours")
        assert d == timedelta(hours=1, minutes=30)

    def test_leading_dot(self):
        d = parse_duration(".5 days")
        assert d == timedelta(hours=12)

    def test_decimal_cascading(self):
        d = parse_duration("2.5 minutes")
        assert d == timedelta(minutes=2, seconds=30)

    def test_decimal_seconds(self):
        d = parse_duration("1.5 seconds")
        assert d == timedelta(seconds=1, milliseconds=500)


class TestUnitAliases:
    def test_full_names(self):
        assert parse_duration("1 second") == timedelta(seconds=1)
        assert parse_duration("1 minute") == timedelta(minutes=1)
        assert parse_duration("1 hour") == timedelta(hours=1)
        assert parse_duration("1 day") == timedelta(days=1)
        assert parse_duration("1 week") == timedelta(weeks=1)

    def test_plural_names(self):
        assert parse_duration("2 seconds") == timedelta(seconds=2)
        assert parse_duration("2 minutes") == timedelta(minutes=2)
        assert parse_duration("2 hours") == timedelta(hours=2)

    def test_short_names(self):
        assert parse_duration("1s") == timedelta(seconds=1)
        assert parse_duration("1m") == timedelta(minutes=1)
        assert parse_duration("1h") == timedelta(hours=1)
        assert parse_duration("1d") == timedelta(days=1)
        assert parse_duration("1w") == timedelta(weeks=1)

    def test_medium_names(self):
        assert parse_duration("1 sec") == timedelta(seconds=1)
        assert parse_duration("1 min") == timedelta(minutes=1)
        assert parse_duration("1 hr") == timedelta(hours=1)

    def test_milliseconds(self):
        assert parse_duration("500ms") == timedelta(milliseconds=500)
        assert parse_duration("500 milliseconds") == timedelta(milliseconds=500)


class TestNegativeAndDirection:
    def test_negative_prefix(self):
        d = parse_duration("-3 days")
        assert d == timedelta(days=-3)

    def test_ago_suffix(self):
        d = parse_duration("3 days ago")
        assert d == timedelta(days=-3)

    def test_in_prefix(self):
        d = parse_duration("in 2 hours")
        assert d == timedelta(hours=2)

    def test_negative_with_ago(self):
        d = parse_duration("-2 hours ago")
        # double negative = positive
        assert d == timedelta(hours=2)


class TestFuzzyMatching:
    def test_no_tolerance_exact_only(self):
        with pytest.raises(ParseError):
            parse_duration("1 houur", strict=True, tolerance=0.0)

    def test_with_tolerance(self):
        d = parse_duration("1 houur", tolerance=0.3)
        assert d == timedelta(hours=1)

    def test_tolerance_range(self):
        with pytest.raises(ParseError, match="tolerance"):
            parse_duration("1 hour", tolerance=1.5)
        with pytest.raises(ParseError, match="tolerance"):
            parse_duration("1 hour", tolerance=-0.1)


class TestMetadata:
    def test_original_preserved(self):
        d = parse_duration("1 hour 30 minutes")
        assert d.original == "1 hour 30 minutes"

    def test_units_found(self):
        d = parse_duration("1h 30m 15s")
        assert set(d.units_found) == {"hours", "minutes", "seconds"}

    def test_parse_count(self):
        d = parse_duration("1h 30m 15s")
        assert d.parse_count == 3

    def test_is_negative(self):
        d = parse_duration("-3 days")
        assert d.is_negative is True

    def test_isinstance_timedelta(self):
        d = parse_duration("1 hour")
        assert isinstance(d, timedelta)
        assert isinstance(d, ParsedDuration)


class TestStrictMode:
    def test_strict_rejects_unknown(self):
        with pytest.raises(ParseError) as exc_info:
            parse_duration("5 foobar", strict=True)
        assert exc_info.value.reason == "unknown_unit"
        assert exc_info.value.position >= 0

    def test_non_strict_skips_unknown(self):
        d = parse_duration("1 hour 5 foobar 30 minutes")
        assert d == timedelta(hours=1, minutes=30)


class TestErrorHandling:
    def test_empty_string(self):
        with pytest.raises(ParseError) as exc_info:
            parse_duration("")
        assert exc_info.value.reason == "no_components"

    def test_no_units(self):
        with pytest.raises(ParseError):
            parse_duration("hello world", strict=True)

    def test_error_attributes(self):
        with pytest.raises(ParseError) as exc_info:
            parse_duration("")
        err = exc_info.value
        assert err.text == ""
        assert err.position == 0


class TestStats:
    def test_stats_tracking(self):
        from timedeltaparser.parser import reset_stats, get_stats

        reset_stats()
        parse_duration("1h 30m")
        stats = get_stats()
        assert stats["total_calls"] == 1
        assert stats["components_parsed"] == 2

    def test_cumulative(self):
        from timedeltaparser.parser import reset_stats, get_stats

        reset_stats()
        parse_duration("1h")
        parse_duration("2m")
        stats = get_stats()
        assert stats["total_calls"] == 2
