"""Feature 022 T036: assistant texts shown in the UI follow the language."""

import pytest

from app.assistant import activity, preview, readiness
from app.i18n import use_locale


@pytest.mark.parametrize(
    ("name", "args", "expected_es", "expected_en"),
    [
        ("list_sources", {}, "Lista de fuentes", "List sources"),
        ("describe_source", {"name": "bi"}, "Estructura de la base BI", "BI database structure"),
        (
            "describe_source",
            {"name": "ventas_db"},
            "Estructura de «ventas_db»",
            'Structure of "ventas_db"',
        ),
        (
            "check_query",
            {"path": "reports/ventas/report.yaml"},
            "Comprobar reporte directo «ventas»",
            'Check direct report "ventas"',
        ),
        (
            "read_draft",
            {"paths": ["a.sql", "b.sql"]},
            "Leer borrador · a.sql, b.sql",
            "Read draft · a.sql, b.sql",
        ),
        ("run_preview", {}, "Vista previa", "Preview"),
    ],
)
def test_tool_label(name, args, expected_es, expected_en):
    assert activity.tool_label(name, args) == expected_es
    with use_locale("en"):
        assert activity.tool_label(name, args) == expected_en


@pytest.mark.parametrize(
    ("preview_data", "expected_es", "expected_en"),
    [
        (
            {
                "status": "succeeded",
                "integrations": {"i1": {"datasets": {"ventas": {"rows": 3}}}},
                "reports": {"r1": {}},
            },
            "Vista previa lista: ventas 3 filas, reporte directo r1.",
            "Preview ready: ventas 3 rows, direct report r1.",
        ),
        (
            {"status": "succeeded", "integrations": {}, "reports": {}},
            "Vista previa lista.",
            "Preview ready.",
        ),
        (
            {"status": "failed", "integrations": {}, "reports": {}},
            "La vista previa falló: comprobación no superada",
            "Preview failed: check failed",
        ),
    ],
)
def test_summary_text(preview_data, expected_es, expected_en):
    assert preview.summary_text(preview_data) == expected_es
    with use_locale("en"):
        assert preview.summary_text(preview_data) == expected_en


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Yes, include cliente_email", ["cliente_email"]),
        ("Confirmed: cliente_email", ["cliente_email"]),
        ("No, exclude cliente_email", []),
        ("Yes, but without cliente_email", []),
        ("Remove cliente_email", []),
        ("Yes, include it", []),
        ("Sí, incluye cliente_email", ["cliente_email"]),
    ],
)
def test_confirmed_columns(answer, expected):
    question = "Should I include cliente_email in the report?"
    flagged = ["cliente_email"]
    assert readiness.confirmed_columns(question, answer, flagged) == expected


@pytest.fixture
def ai_on(monkeypatch, tmp_path):
    from app.config import get_settings

    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    yield
    get_settings.cache_clear()


def test_default_conversation_title_follows_the_viewer(superuser, ai_on):
    """022 T048: the stored default title is shown in the viewer's language."""
    from tests.conftest import signed_in

    c = signed_in("root@example.com")
    project = c.post("/api/projects", json={"name": "Ventas"}).json()
    sid = c.post("/api/assistant/sessions", json={"project": project["slug"]}).json()["id"]
    assert c.get(f"/api/assistant/sessions/{sid}").json()["title"] == "Nueva conversación"
    assert c.patch("/api/me/preferences", json={"locale": "en"}).status_code == 200
    assert c.get(f"/api/assistant/sessions/{sid}").json()["title"] == "New conversation"
    detail = c.get(f"/api/projects/{project['slug']}").json()
    assert [conv["title"] for conv in detail["conversations"]] == ["New conversation"]
