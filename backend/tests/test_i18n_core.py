"""Unit tests for i18n core functions."""

import contextvars
import threading

from app import i18n
from app.config import get_settings


def test_normalize() -> None:
    assert i18n.normalize("en-US") == "en"
    assert i18n.normalize("es_VE") == "es"
    assert i18n.normalize("fr") is None
    assert i18n.normalize(None) is None
    assert i18n.normalize("EN") == "en"


def test_from_accept_language() -> None:
    assert i18n.from_accept_language("fr;q=1, en-US;q=0.8, es;q=0.9") == "es"
    assert i18n.from_accept_language("en-GB,en;q=0.9") == "en"
    assert i18n.from_accept_language("de") is None
    assert i18n.from_accept_language(None) is None
    # q=0 should be ignored
    assert i18n.from_accept_language("en;q=0, es;q=0.5") == "es"


def test_current_defaults_to_settings(monkeypatch) -> None:
    token = i18n.open_box("es")
    i18n._context.reset(token)
    assert i18n.current() == "es"
    monkeypatch.setattr(get_settings(), "default_locale", "es")
    assert i18n.current() == "es"
    monkeypatch.setattr(get_settings(), "default_locale", "en")
    assert i18n.current() == "en"


def test_use_locale() -> None:
    assert i18n.t("common.not_found") == "No encontrado."
    with i18n.use_locale("en"):
        assert i18n.t("common.not_found") == "Not found."
    assert i18n.t("common.not_found") == "No encontrado."


def test_set_locale_mutable_box_copied_context() -> None:
    box_token = i18n.open_box("es")
    try:
        def worker() -> None:
            i18n.set_locale("en")
        ctx = contextvars.copy_context()
        thread = threading.Thread(target=ctx.run, args=(worker,))
        thread.start()
        thread.join()
        # The caller's box should have been mutated due to copied context
        assert i18n.current() == "en"
    finally:
        i18n._context.reset(box_token)


def test_t_missing_key() -> None:
    assert i18n.t("missing.key") == "missing.key"


def test_t_missing_placeholder_keeps_brace() -> None:
    # Use an existing message with a placeholder that is not provided
    assert i18n.t("common.items.one") == "{n} elemento"


def test_tn() -> None:
    assert i18n.tn("common.items", 1) == "1 elemento"
    assert i18n.tn("common.items", 3) == "3 elementos"


def test_m_str() -> None:
    msg = i18n.M("common.forbidden")
    with i18n.use_locale("en"):
        assert str(msg) == "Not authorized."
    assert str(msg) == "No autorizado."


def test_localized() -> None:
    data = {"title": "Ventas", "title_en": "Sales"}
    assert i18n.localized(data, "title", "en") == "Sales"
    assert i18n.localized(data, "title", "es") == "Ventas"
    # Missing _en falls back to base
    data_no_en = {"title": "Ventas"}
    assert i18n.localized(data_no_en, "title", "en") == "Ventas"


def test_period_error_english():
    from datetime import date

    import pytest

    from app.engine import periods
    with i18n.use_locale("en"):
        with pytest.raises(periods.PeriodError) as exc_info:
            periods.resolve("bogus", "previous_period", date(2026, 10, 10))
        assert "unknown period: bogus" in str(exc_info.value.message)


def test_source_field_labels_match_catalogue():
    from app.i18n import en, es
    from app.sources import schemas
    for kind, spec in schemas.KINDS.items():
        assert es.MESSAGES[f"sources.kind.{kind}"] == spec["label"]
        assert en.MESSAGES.get(f"sources.kind.{kind}", "")
        for f in spec["fields"]:
            fid = f"sources.{kind}.{f.name}"
            assert es.MESSAGES[fid] == f.label
            assert en.MESSAGES.get(fid, "")
            if f.help:
                assert es.MESSAGES[f"{fid}.help"] == f.help
                assert en.MESSAGES.get(f"{fid}.help", "")


def test_source_types_english():
    from app.config import get_settings
    from app.sources import schemas
    with i18n.use_locale("en"):
        types = schemas.types_for(get_settings())
    assert types["postgresql"]["fields"][0]["label"] == "Host"
    assert types["rest"]["label"] == "REST API"


def test_connection_message_english():
    from app.sources.connectors import base
    with i18n.use_locale("en"):
        assert base.test_message("timeout") == "The source did not respond in time."
        assert base.test_message("weird") == "Error connecting to the source."


def test_schedule_error_english():
    import pytest

    from app.engine import schedule

    with i18n.use_locale("en"):
        with pytest.raises(schedule.ScheduleError) as exc:
            schedule.validate_cron("not a cron", "UTC")
        assert exc.value.code == "invalid_cron"
        assert str(exc.value.message) == "The frequency expression is invalid."


def test_ai_error_message_english():
    from app.ai import AIError

    with i18n.use_locale("en"):
        assert AIError("timeout").message == "The AI provider did not respond in time."


def test_ai_messages_match_catalogue():
    from app.ai import MESSAGES
    from app.i18n import en, es

    for code in MESSAGES:
        assert es.MESSAGES[f"ai.error.{code}"] == MESSAGES[code]
        assert en.MESSAGES.get(f"ai.error.{code}")


def test_to_stored_nested_rendering():
    msg = i18n.M("run.check_failed", dataset="ventas", type="contract",
                 detail=i18n.M("run.check.rows", n=3))
    text, key, params = i18n.to_stored(msg)
    assert text == "comprobación no superada en ventas (contract): 3 filas"
    assert key == "run.check_failed"
    assert params["detail"] == {"$m": "run.check.rows", "params": {"n": 3}}
    with i18n.use_locale("en"):
        rendered = i18n.render_stored(text, key, params)
    assert rendered == "check failed in ventas (contract): 3 rows"


def test_render_stored_legacy():
    with i18n.use_locale("en"):
        assert i18n.render_stored("texto viejo", None, None) == "texto viejo"


def test_to_stored_redaction():
    msg = i18n.M("run.source_missing", source="s3cr3t-src")
    text, _key, params = i18n.to_stored(
        msg, redact=lambda s: s.replace("s3cr3t", "***"))
    assert "***-src" in text
    assert params["source"] == "***-src"


def test_direct_messages_match_catalogue():
    from app.engine import direct
    from app.i18n import en, es

    for code in direct.MESSAGES:
        assert es.MESSAGES[f"direct.{code}"] == direct.MESSAGES[code]
        assert en.MESSAGES[f"direct.{code}"]


def test_direct_error_english():
    from app.engine import direct

    with i18n.use_locale("en"):
        assert direct.DirectError.timeout(15).message == (
            "The query exceeded the time limit of 15 s"
        )
        assert direct.DirectError("busy").message == "The source is busy"


def test_extract_error_stored():
    from app.engine.extract import ExtractError

    e = ExtractError(i18n.M("extract.max_pages", max=50))
    text, key, params = i18n.to_stored(e.args[0])
    assert text == "se superó el máximo de 50 páginas"
    assert key == "extract.max_pages"
    assert params == {"max": 50}
