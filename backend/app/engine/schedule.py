"""Feature 013: effective schedules combine spec defaults with stored integration controls;
this module validates cron expressions (minimum 5-minute interval), renders Spanish
descriptions, and checks allowed-hours windows (overnight supported) in the installation
time zone. It is pure: no database access. Day-of-week uses standard cron numbering
(0 or 7 = Sunday)."""
from collections.abc import Mapping
from datetime import UTC, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from app.i18n import M

MIN_INTERVAL = timedelta(minutes=5)

MAX_CRON_LENGTH = 100

PRESETS: tuple[tuple[str, str], ...] = (
    ("*/15 * * * *", "Cada 15 minutos"),
    ("*/30 * * * *", "Cada 30 minutos"),
    ("0 * * * *", "Cada hora"),
    ("0 3 * * *", "Diaria a las 03:00"),
)


class ScheduleError(ValueError):
    def __init__(self, code: str, message: "M | str"):
        super().__init__(str(message))
        self.code = code
        self.message = message


class ControlLike(Protocol):
    paused: bool
    schedule: str | None
    full_rebuild_cron: str | None
    window_start: time | None
    window_end: time | None


def normalize(expr: str) -> str:
    return " ".join(expr.split())


_DOW_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")


def _day_of_week(field: str) -> str:
    """Expand a standard-cron day-of-week field into APScheduler day names."""

    def parse_value(value: str) -> int:
        normalized = value.strip().lower()
        if normalized in _DOW_NAMES:
            return _DOW_NAMES.index(normalized)
        if normalized.isdigit():
            number = int(normalized)
            if 0 <= number <= 7:
                return number
        raise ScheduleError("invalid_cron", M("schedule.invalid_cron"))

    days: set[int] = set()

    for part in field.split(","):
        part = part.strip()
        if not part:
            raise ScheduleError("invalid_cron", M("schedule.invalid_cron"))

        step: int | None = None
        if "/" in part:
            part, step_str = part.split("/", 1)
            try:
                step = int(step_str)
            except ValueError:
                raise ScheduleError(
                    "invalid_cron", M("schedule.invalid_cron")
                ) from None
            if step < 1:
                raise ScheduleError("invalid_cron", M("schedule.invalid_cron"))

        if part == "*":
            start, end = 0, 6
        elif "-" in part:
            start_str, end_str = part.split("-", 1)
            start = parse_value(start_str)
            end = parse_value(end_str)
            if start > end:
                raise ScheduleError("invalid_cron", M("schedule.invalid_cron"))
        else:
            start = parse_value(part)
            if step is None:
                end = start
            else:
                end = 7

        if step is None:
            days.update(d % 7 for d in range(start, end + 1))
        else:
            days.update(d % 7 for d in range(start, end + 1, step))

    if len(days) == 7:
        return "*"

    return ",".join(_DOW_NAMES[d] for d in sorted(days))


def trigger(expr: str, tz: str) -> CronTrigger:
    fields = normalize(expr).split()
    if len(fields) != 5:
        raise ScheduleError("invalid_cron", M("schedule.invalid_cron"))
    converted_dow = _day_of_week(fields[4])
    try:
        return CronTrigger(
            minute=fields[0],
            hour=fields[1],
            day=fields[2],
            month=fields[3],
            day_of_week=converted_dow,
            timezone=tz,
        )
    except (ValueError, TypeError, KeyError) as e:
        raise ScheduleError("invalid_cron", M("schedule.invalid_cron")) from e


def validate_cron(expr: str, tz: str, *, now: datetime | None = None) -> str:
    norm = normalize(expr)
    if len(norm) > MAX_CRON_LENGTH:
        raise ScheduleError("too_long", M("schedule.too_long"))
    trg = trigger(norm, tz)
    current = now or datetime.now(UTC)
    previous = None
    for _ in range(200):
        fire = trg.get_next_fire_time(previous, current if previous is None
                                      else previous + timedelta(seconds=1))
        if fire is None:
            break
        if previous is not None and fire - previous < MIN_INTERVAL:
            raise ScheduleError(
                "too_frequent",
                M("schedule.too_frequent"),
            )
        previous = fire
    if previous is None:
        raise ScheduleError("invalid_cron", M("schedule.invalid_cron"))
    return norm


def validate_window(start: time | None, end: time | None) -> tuple[time, time] | None:
    if start is None and end is None:
        return None
    if start is None or end is None:
        raise ScheduleError("window_incomplete", "Indica la hora de inicio y la de fin.")
    start = start.replace(second=0, microsecond=0)
    end = end.replace(second=0, microsecond=0)
    if start == end:
        raise ScheduleError("window_empty", M("schedule.window_empty"))
    return start, end


def in_window(start: time | None, end: time | None, at: datetime, tz: str) -> bool:
    if start is None or end is None:
        return True
    if start == end:
        return True
    local = at.astimezone(ZoneInfo(tz)).time().replace(tzinfo=None)
    if start < end:
        return start <= local < end
    return local >= start or local < end


def describe(expr: str) -> str | None:
    norm = normalize(expr)
    fields = norm.split()
    if len(fields) != 5:
        return None
    if fields[2:] != ["*", "*", "*"]:
        return None
    minute, hour, *_ = fields
    if minute.startswith("*/") and hour == "*":
        try:
            n = int(minute[2:])
        except ValueError:
            return None
        if 1 <= n <= 59 and 60 % n == 0:
            return "Cada minuto" if n == 1 else f"Cada {n} minutos"
    if minute == "0" and hour == "*":
        return "Cada hora"
    if minute == "0" and hour.startswith("*/"):
        try:
            n = int(hour[2:])
        except ValueError:
            return None
        if 2 <= n <= 23 and 24 % n == 0:
            return f"Cada {n} horas"
    if minute.isdigit() and hour.isdigit():
        m, h = int(minute), int(hour)
        if 0 <= m <= 59 and 0 <= h <= 23:
            return f"Diaria a las {h:02d}:{m:02d}"
    return None


def effective_schedule(definition: dict, control: ControlLike | None) -> tuple[str, str]:
    if control is not None and control.schedule:
        return control.schedule, "override"
    return definition["schedule"], "spec"


def spec_full_crons(definition: dict) -> list[str]:
    fulls = {
        ds.get("incremental", {}).get("full_rebuild_cron")
        for ds in definition["datasets"].values()
    }
    return sorted(f for f in fulls if f)


def effective_full_crons(definition: dict, control: ControlLike | None) -> tuple[list[str], str]:
    if control is not None and control.full_rebuild_cron:
        return [control.full_rebuild_cron], "override"
    return spec_full_crons(definition), "spec"


def schedules(artifacts: dict, controls: Mapping[str, ControlLike] | None = None) -> list[
    tuple[str, str, str]
]:
    out: list[tuple[str, str, str]] = []
    controls = controls or {}
    for iid, item in sorted(artifacts.get("integrations", {}).items()):
        definition = item["definition"]
        control = controls.get(iid)
        inc, _ = effective_schedule(definition, control)
        out.append((iid, "incremental", inc))
        fulls, _ = effective_full_crons(definition, control)
        out.extend((iid, "full", c) for c in fulls)
    return out


def next_fire(
    expr: str,
    tz: str,
    *,
    now: datetime | None = None,
    paused: bool = False,
    window: tuple[time, time] | None = None,
    limit: int = 2000,
) -> datetime | None:
    if paused:
        return None
    trg = trigger(expr, tz)
    current = now or datetime.now(UTC)
    previous = None
    for _ in range(limit):
        fire = trg.get_next_fire_time(previous, current if previous is None
                                      else previous + timedelta(seconds=1))
        if fire is None:
            return None
        if window is None or in_window(window[0], window[1], fire, tz):
            return fire
        previous = fire
    return None
