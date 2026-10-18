"""Unit tests for app.engine.schedule (feature 013): pure scheduling logic without the DB."""
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

import pytest

from app.engine.schedule import (
    MAX_CRON_LENGTH,
    PRESETS,
    ScheduleError,
    describe,
    effective_full_crons,
    effective_schedule,
    in_window,
    next_fire,
    normalize,
    schedules,
    spec_full_crons,
    trigger,
    validate_cron,
    validate_window,
)
from app.worker import cron


@dataclass
class Control:
    paused: bool = False
    schedule: str | None = None
    full_rebuild_cron: str | None = None
    window_start: time | None = None
    window_end: time | None = None


def test_normalize_collapses_whitespace():
    assert normalize("  */5  *   * * *\t") == "*/5 * * * *"


@pytest.mark.parametrize("expr", ["bad", "* * * *", "61 * * * *", "* * * * * *"])
def test_invalid_cron(expr):
    with pytest.raises(ScheduleError) as err:
        validate_cron(expr, "UTC")
    assert err.value.code == "invalid_cron"
    assert str(err.value) == "La expresión de frecuencia no es válida."


@pytest.mark.parametrize("expr", ["* * * * *", "*/2 * * * *", "0,1 3 * * *"])
def test_too_frequent(expr):
    with pytest.raises(ScheduleError) as err:
        validate_cron(expr, "UTC", now=datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    assert err.value.code == "too_frequent"
    assert str(err.value) == "La frecuencia no puede ser mayor que una vez cada 5 minutos."


@pytest.mark.parametrize("expr", ["*/5 * * * *", "*/15 * * * *", "0 3 * * *"])
def test_valid_cron_passes_and_is_normalized(expr):
    assert validate_cron(f"  {expr}  ", "UTC",
                         now=datetime(2026, 10, 2, 12, 0, tzinfo=UTC)) == normalize(expr)


def test_validate_cron_never_fires_is_invalid():
    with pytest.raises(ScheduleError) as err:
        validate_cron("0 0 31 2 *", "UTC", now=datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    assert err.value.code == "invalid_cron"


def test_validate_window_none():
    assert validate_window(None, None) is None


def test_validate_window_incomplete():
    with pytest.raises(ScheduleError) as err:
        validate_window(time(22, 0), None)
    assert err.value.code == "window_incomplete"
    with pytest.raises(ScheduleError) as err:
        validate_window(None, time(6, 0))
    assert err.value.code == "window_incomplete"


def test_validate_window_empty():
    with pytest.raises(ScheduleError) as err:
        validate_window(time(10, 0), time(10, 0, 30))
    assert err.value.code == "window_empty"


def test_validate_window_zeroes_seconds():
    assert validate_window(time(22, 0, 45), time(6, 0, 59)) == (time(22, 0), time(6, 0))


def test_in_window_same_day_boundaries():
    start, end = time(6, 0), time(22, 0)
    assert in_window(start, end, datetime(2026, 10, 2, 6, 0, tzinfo=UTC), "UTC")
    assert not in_window(start, end, datetime(2026, 10, 2, 5, 59, tzinfo=UTC), "UTC")
    assert in_window(start, end, datetime(2026, 10, 2, 21, 59, tzinfo=UTC), "UTC")
    assert not in_window(start, end, datetime(2026, 10, 2, 22, 0, tzinfo=UTC), "UTC")


def test_in_window_overnight():
    start, end = time(22, 0), time(6, 0)
    assert in_window(start, end, datetime(2026, 10, 2, 23, 30, tzinfo=UTC), "UTC")
    assert in_window(start, end, datetime(2026, 10, 3, 5, 59, tzinfo=UTC), "UTC")
    assert not in_window(start, end, datetime(2026, 10, 3, 6, 0, tzinfo=UTC), "UTC")
    assert not in_window(start, end, datetime(2026, 10, 3, 12, 0, tzinfo=UTC), "UTC")


def test_in_window_timezone_conversion():
    start, end = time(22, 0), time(6, 0)
    at = datetime(2026, 10, 2, 2, 30, tzinfo=UTC)  # 22:30 in America/Caracas (UTC-4)
    assert in_window(start, end, at, "America/Caracas")


def test_describe_presets_and_shapes():
    assert describe("*/15 * * * *") == "Cada 15 minutos"
    assert describe("*/30 * * * *") == "Cada 30 minutos"
    assert describe("0 * * * *") == "Cada hora"
    assert describe("0 3 * * *") == "Diaria a las 03:00"
    assert describe("*/1 * * * *") == "Cada minuto"
    assert describe("0 */6 * * *") == "Cada 6 horas"
    assert describe("30 14 * * *") == "Diaria a las 14:30"
    assert describe("5 4 * * 1") is None
    assert describe("*/15 * 1 * *") is None
    assert describe("") is None


def test_every_preset_is_described():
    for expr, words in PRESETS:
        assert describe(expr) == words
        assert validate_cron(expr, "UTC",
                             now=datetime(2026, 10, 2, 12, 0, tzinfo=UTC)) == expr


def test_effective_schedule_spec_and_override():
    definition = {"schedule": "0 3 * * *"}
    assert effective_schedule(definition, None) == ("0 3 * * *", "spec")
    assert effective_schedule(definition, Control(schedule="*/30 * * * *")) == (
        "*/30 * * * *",
        "override",
    )
    assert effective_schedule(definition, Control()) == ("0 3 * * *", "spec")


def test_spec_full_crons_sorted_and_deduplicated():
    definition = {
        "datasets": {
            "a": {"incremental": {"full_rebuild_cron": "0 5 * * *"}},
            "b": {"incremental": {"full_rebuild_cron": "0 5 * * *"}},
            "c": {"incremental": {"full_rebuild_cron": "0 2 * * *"}},
            "d": {},
        },
    }
    assert spec_full_crons(definition) == ["0 2 * * *", "0 5 * * *"]


def test_effective_full_crons_override():
    definition = {"datasets": {"a": {"incremental": {"full_rebuild_cron": "0 5 * * *"}}}}
    assert effective_full_crons(definition, None) == (["0 5 * * *"], "spec")
    assert effective_full_crons(definition, Control(full_rebuild_cron="0 6 * * *")) == (
        ["0 6 * * *"],
        "override",
    )
    assert effective_full_crons(definition, Control()) == (["0 5 * * *"], "spec")


def test_schedules_combines_specs_and_controls():
    definition_a = {
        "schedule": "0 3 * * *",
        "datasets": {
            "one": {"incremental": {"full_rebuild_cron": "0 5 * * *"}},
            "two": {"incremental": {"full_rebuild_cron": "0 5 * * *"}},
            "empty": {},
        },
    }
    definition_b = {
        "schedule": "0 4 * * *",
        "datasets": {"x": {"incremental": {"full_rebuild_cron": "0 6 * * *"}}},
    }
    artifacts = {"integrations": {"a": {"definition": definition_a},
                                  "b": {"definition": definition_b}}}
    controls = {
        "a": Control(schedule="*/30 * * * *", full_rebuild_cron="0 7 * * *", paused=True),
        "unknown": Control(schedule="*/5 * * * *"),
    }
    assert schedules(artifacts, controls) == [
        ("a", "incremental", "*/30 * * * *"),
        ("a", "full", "0 7 * * *"),
        ("b", "incremental", "0 4 * * *"),
        ("b", "full", "0 6 * * *"),
    ]


def test_next_fire_paused_returns_none():
    assert next_fire("*/15 * * * *", "UTC", paused=True,
                     now=datetime(2026, 10, 2, 12, 0, tzinfo=UTC)) is None


def test_next_fire_no_window_returns_first_fire():
    now = datetime(2026, 10, 2, 12, 7, tzinfo=UTC)
    assert next_fire("*/15 * * * *", "UTC", now=now) == datetime(
        2026, 10, 2, 12, 15, tzinfo=UTC)


def test_next_fire_window_skips_to_next_day():
    now = datetime(2026, 10, 2, 21, 50, tzinfo=UTC)
    window = (time(6, 0), time(22, 0))
    assert next_fire("*/15 * * * *", "UTC", now=now, window=window) == datetime(
        2026, 10, 3, 6, 0, tzinfo=UTC)


def test_next_fire_overnight_window():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    window = (time(22, 0), time(6, 0))
    assert next_fire("*/30 * * * *", "UTC", now=now, window=window) == datetime(
        2026, 10, 2, 22, 0, tzinfo=UTC)


def test_next_fire_limit_exhausted_returns_none():
    now = datetime(2026, 10, 2, 0, 0, tzinfo=UTC)
    window = (time(10, 0), time(11, 0))
    assert next_fire("0 3 * * *", "UTC", now=now, window=window, limit=5) is None


def test_dow_sunday_zero_seven_and_name():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    expected = datetime(2026, 10, 4, 3, 0, tzinfo=UTC)
    for expr in ("0 3 * * 0", "0 3 * * 7", "0 3 * * sun"):
        trg = trigger(expr, "UTC")
        fire = trg.get_next_fire_time(None, now)
        assert fire == expected
        assert fire.weekday() == 6


def test_dow_weekday_range_numbers_and_names():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    for expr in ("0 3 * * 1-5", "0 3 * * mon-fri"):
        trg = trigger(expr, "UTC")
        seen = set()
        prev = None
        current = now
        for _ in range(14):
            fire = trg.get_next_fire_time(prev, current)
            assert fire is not None
            assert fire.weekday() in (0, 1, 2, 3, 4)
            seen.add(fire.weekday())
            prev = fire
            current = fire + timedelta(seconds=1)
        assert seen == {0, 1, 2, 3, 4}


def test_dow_full_week_ranges_and_star_step_one():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    for expr in ("0 3 * * 0-6", "0 3 * * 0-7", "0 3 * * */1"):
        trg = trigger(expr, "UTC")
        weekdays = set()
        prev = None
        current = now
        for _ in range(7):
            fire = trg.get_next_fire_time(prev, current)
            assert fire is not None
            weekdays.add(fire.weekday())
            prev = fire
            current = fire + timedelta(seconds=1)
        assert weekdays == {0, 1, 2, 3, 4, 5, 6}


def test_dow_steps_and_lists():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)

    trg = trigger("0 3 * * */2", "UTC")
    prev = None
    current = now
    seen = set()
    for _ in range(4):
        fire = trg.get_next_fire_time(prev, current)
        assert fire is not None
        seen.add(fire.weekday())
        prev = fire
        current = fire + timedelta(seconds=1)
    assert seen == {6, 1, 3, 5}

    trg = trigger("0 3 * * 1-5/2", "UTC")
    prev = None
    current = now
    seen = set()
    for _ in range(3):
        fire = trg.get_next_fire_time(prev, current)
        assert fire is not None
        seen.add(fire.weekday())
        prev = fire
        current = fire + timedelta(seconds=1)
    assert seen == {0, 2, 4}

    trg = trigger("0 3 * * 5,0", "UTC")
    prev = None
    current = now
    seen = set()
    for _ in range(2):
        fire = trg.get_next_fire_time(prev, current)
        assert fire is not None
        seen.add(fire.weekday())
        prev = fire
        current = fire + timedelta(seconds=1)
    assert seen == {4, 6}


def test_dow_end_seven_range_and_single_value_step():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)

    trg = trigger("0 3 * * 5-7", "UTC")
    prev = None
    current = now
    seen = set()
    for _ in range(6):
        fire = trg.get_next_fire_time(prev, current)
        assert fire is not None
        seen.add(fire.weekday())
        prev = fire
        current = fire + timedelta(seconds=1)
    assert seen == {4, 5, 6}

    trg = trigger("0 3 * * 1/2", "UTC")
    prev = None
    current = now
    seen = set()
    for _ in range(8):
        fire = trg.get_next_fire_time(prev, current)
        assert fire is not None
        seen.add(fire.weekday())
        prev = fire
        current = fire + timedelta(seconds=1)
    assert seen == {0, 2, 4, 6}


@pytest.mark.parametrize(
    "expr",
    ("0 3 * * 8", "0 3 * * 5-1", "0 3 * * */0", "0 3 * * xyz", "0 3 * * 1-"),
)
def test_dow_invalid_raises_invalid_cron(expr):
    with pytest.raises(ScheduleError) as excinfo:
        validate_cron(expr, "UTC")
    assert excinfo.value.code == "invalid_cron"


def test_dow_seven_every_minute_is_too_frequent():
    now = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
    with pytest.raises(ScheduleError) as excinfo:
        validate_cron("* * * * 7", "UTC", now=now)
    assert excinfo.value.code == "too_frequent"


def test_worker_cron_sunday_zero():
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    expected = datetime(2026, 10, 4, 3, 0, tzinfo=UTC)
    assert cron("0 3 * * 0", "UTC").get_next_fire_time(None, now) == expected


def test_describe_non_dividing_minute_step_returns_none():
    assert describe("*/25 * * * *") is None


def test_describe_non_dividing_hour_step_returns_none():
    assert describe("0 */15 * * *") is None


def test_describe_dividing_steps():
    assert describe("*/15 * * * *") == "Cada 15 minutos"
    assert describe("*/1 * * * *") == "Cada minuto"
    assert describe("*/20 * * * *") == "Cada 20 minutos"
    assert describe("0 */6 * * *") == "Cada 6 horas"
    assert describe("0 */8 * * *") == "Cada 8 horas"


def test_validate_cron_rejects_too_long_expression():
    long_expr = "0 3 * * " + ",".join(["1"] * 60)
    with pytest.raises(ScheduleError) as exc:
        validate_cron(long_expr, "UTC")
    assert exc.value.code == "too_long"


def test_validate_cron_accepts_expression_at_max_length():
    days = ",".join(f"{day:02d}" for day in range(1, 32))
    expr = f"0 0 {days} * *"
    assert len(expr) == MAX_CRON_LENGTH
    assert validate_cron(expr, "UTC") == expr
