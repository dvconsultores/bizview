"""Feature 005 FR-013: period and comparison rules (feature 001 research R7)."""
from datetime import date

import pytest

from app.engine import periods
from app.engine.periods import PeriodError, Range, resolve


def rng(sel_range: Range | None) -> tuple[str, str] | None:
    return (sel_range.start.isoformat(), sel_range.end.isoformat()) if sel_range else None


@pytest.mark.parametrize("period,today,current,previous", [
    ("today", "2026-09-29", ("2026-09-29", "2026-09-29"), ("2026-09-28", "2026-09-28")),
    ("yesterday", "2026-09-29", ("2026-09-28", "2026-09-28"), ("2026-09-27", "2026-09-27")),
    ("last_7_days", "2026-09-29", ("2026-09-22", "2026-09-28"), ("2026-09-15", "2026-09-21")),
    ("mtd", "2026-09-29", ("2026-09-01", "2026-09-29"), ("2026-08-01", "2026-08-29")),
    ("mtd", "2026-03-31", ("2026-03-01", "2026-03-31"), ("2026-02-01", "2026-02-28")),
    ("last_month", "2026-03-15", ("2026-02-01", "2026-02-28"), ("2026-01-01", "2026-01-31")),
    ("qtd", "2026-05-20", ("2026-04-01", "2026-05-20"), ("2026-01-01", "2026-02-19")),
    ("qtd", "2026-06-30", ("2026-04-01", "2026-06-30"), ("2026-01-01", "2026-03-31")),
    ("ytd", "2028-02-29", ("2028-01-01", "2028-02-29"), ("2027-01-01", "2027-02-28")),
    ("last_12_months", "2026-09-29", ("2025-09-01", "2026-08-31"),
     ("2024-09-01", "2025-08-31")),
])
def test_presets_and_previous_period(period, today, current, previous):
    sel = resolve(period, "previous_period", date.fromisoformat(today))
    assert rng(sel.current) == current
    assert rng(sel.previous) == previous


def test_custom_previous_is_same_length_before():
    sel = resolve("custom", "previous_period", date(2026, 9, 29),
                  custom=(date(2026, 9, 10), date(2026, 9, 19)))
    assert rng(sel.previous) == ("2026-08-31", "2026-09-09")
    assert not sel.partial


def test_previous_year_leap_day():
    sel = resolve("custom", "previous_year", date(2028, 3, 1),
                  custom=(date(2028, 2, 29), date(2028, 2, 29)))
    assert rng(sel.previous) == ("2027-02-28", "2027-02-28")


def test_no_comparison_and_partial_flag():
    sel = resolve("mtd", "none", date(2026, 9, 29))
    assert sel.previous is None and sel.partial


@pytest.mark.parametrize("custom", [(date(2026, 9, 2), date(2026, 9, 1)),
                                    (date(2020, 1, 1), date(2026, 1, 1))])
def test_custom_limits(custom):
    with pytest.raises(PeriodError):
        resolve("custom", "none", date(2026, 9, 29), custom=custom)


def test_unknown_values_refused():
    with pytest.raises(PeriodError):
        resolve("forever", "none", date(2026, 9, 29))
    with pytest.raises(PeriodError):
        resolve("mtd", "sideways", date(2026, 9, 29))


def test_grain_and_iso_week_buckets():
    assert periods.auto_grain(Range(date(2026, 9, 1), date(2026, 9, 29))) == "day"
    assert periods.auto_grain(Range(date(2026, 4, 1), date(2026, 9, 29))) == "week"
    assert periods.auto_grain(Range(date(2025, 9, 1), date(2026, 8, 31))) == "month"
    weeks = periods.buckets(Range(date(2026, 9, 2), date(2026, 9, 15)), "week")
    assert weeks == [date(2026, 8, 31), date(2026, 9, 7), date(2026, 9, 14)]
    months = periods.buckets(Range(date(2026, 1, 31), date(2026, 3, 1)), "month")
    assert months == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_change_with_zero_base():
    assert periods.change(10, 0) == {"pct": None, "new": True}
    assert periods.change(0, 0) == {"pct": None, "new": False}
    assert periods.change(15, 10) == {"pct": 50.0, "new": False}
    assert periods.change(5, None) == {"pct": None, "new": True}
    assert periods.change(None, 5) == {"pct": None, "new": False}
