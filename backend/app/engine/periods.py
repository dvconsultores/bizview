"""Periods and comparisons (feature 005 FR-013; the rules of feature 001 research R7).

All ranges are inclusive local dates in the installation time zone; the backend resolves them,
the browser only sends a preset or a custom range, so the screen and the PDF always agree.
"""
import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from app.i18n import M

PRESETS = ("today", "yesterday", "last_7_days", "mtd", "last_month", "qtd", "ytd",
           "last_12_months", "custom")
COMPARISONS = ("none", "previous_period", "previous_year")
MAX_CUSTOM_DAYS = 3 * 366


class PeriodError(ValueError):
    def __init__(self, message: M):
        self.message = message
        super().__init__(str(message))


@dataclass(frozen=True)
class Range:
    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def to_json(self) -> dict:
        return {"from": self.start.isoformat(), "to": self.end.isoformat()}


@dataclass(frozen=True)
class Selection:
    period: str
    current: Range
    compare: str
    previous: Range | None
    partial: bool            # the range includes today (figures still change)
    grain: str

    def to_json(self) -> dict:
        return {"period": self.period, "current": self.current.to_json(), "compare": self.compare,
                "previous": self.previous.to_json() if self.previous else None,
                "partial": self.partial, "grain": self.grain}


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _add_months(d: date, months: int) -> date:
    """Same day number `months` later/earlier, clipped to the month's last day."""
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, _last_day(year, month)))


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _quarter_start(d: date) -> date:
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def shift_year(d: date, years: int = -1) -> date:
    """Same date one year earlier; 29 Feb → 28 Feb."""
    year = d.year + years
    return date(year, d.month, min(d.day, _last_day(year, d.month)))


def current_range(period: str, today: date, custom: tuple[date, date] | None = None) -> Range:
    if period == "today":
        return Range(today, today)
    if period == "yesterday":
        y = today - timedelta(days=1)
        return Range(y, y)
    if period == "last_7_days":
        return Range(today - timedelta(days=7), today - timedelta(days=1))
    if period == "mtd":
        return Range(_month_start(today), today)
    if period == "last_month":
        end = _month_start(today) - timedelta(days=1)
        return Range(_month_start(end), end)
    if period == "qtd":
        return Range(_quarter_start(today), today)
    if period == "ytd":
        return Range(date(today.year, 1, 1), today)
    if period == "last_12_months":
        end = _month_start(today) - timedelta(days=1)
        return Range(_add_months(_month_start(today), -12), end)
    if period == "custom":
        if not custom:
            raise PeriodError(M("period.custom_needs_from_to"))
        start, end = custom
        if start > end:
            raise PeriodError(M("period.from_before_to"))
        if (end - start).days + 1 > MAX_CUSTOM_DAYS:
            raise PeriodError(M("period.custom_max_years"))
        return Range(start, end)
    raise PeriodError(M("period.unknown", period=period))


def previous_range(period: str, current: Range, compare: str) -> Range | None:
    if compare == "none":
        return None
    if compare == "previous_year":
        return Range(shift_year(current.start), shift_year(current.end))
    start, end = current.start, current.end
    if period in ("today", "yesterday", "last_7_days", "custom"):
        n = current.days
        return Range(start - timedelta(days=n), start - timedelta(days=1))
    if period == "mtd":
        prev_start = _add_months(start, -1)
        return Range(prev_start, _add_months(end, -1))
    if period == "last_month":
        prev_end = start - timedelta(days=1)
        return Range(_month_start(prev_end), prev_end)
    if period == "qtd":
        prev_start = _add_months(start, -3)
        prev_quarter_end = start - timedelta(days=1)
        return Range(prev_start, min(prev_start + (end - start), prev_quarter_end))
    if period == "ytd":
        return Range(shift_year(start), shift_year(end))
    if period == "last_12_months":
        return Range(_add_months(start, -12), start - timedelta(days=1))
    raise PeriodError(M("period.unknown", period=period))


def auto_grain(r: Range) -> str:
    if r.days <= 45:
        return "day"
    if r.days <= 190:
        return "week"
    return "month"


def resolve(period: str, compare: str, today: date, *, custom: tuple[date, date] | None = None,
            grain: str = "auto") -> Selection:
    if compare not in COMPARISONS:
        raise PeriodError(M("period.unknown_compare", compare=compare))
    current = current_range(period, today, custom)
    previous = previous_range(period, current, compare)
    return Selection(period, current, compare, previous, current.end >= today,
                     auto_grain(current) if grain == "auto" else grain)


def buckets(r: Range, grain: str) -> list[date]:
    """Bucket starts covering the range (ISO weeks start on Monday)."""
    if grain == "day":
        first, step = r.start, None
    elif grain == "week":
        first, step = r.start - timedelta(days=r.start.weekday()), None
    else:
        first, step = _month_start(r.start), "month"
    out, d = [], first
    while d <= r.end:
        out.append(d)
        d = _add_months(d, 1) if step else d + timedelta(days=1 if grain == "day" else 7)
    return out


def change(current: float | None, previous: float | None) -> dict:
    """Percentage change; a zero or missing base gives null and the flag `new`."""
    if current is None or previous is None:
        return {"pct": None, "new": previous in (None, 0) and bool(current)}
    if previous == 0:
        return {"pct": None, "new": current != 0}
    return {"pct": (current - previous) / abs(previous) * 100, "new": False}
