"""Feature 023 T036: the project overview (stages, next command, decisions, privacy, cap)."""
import json

import pytest

from app.assistant import overview
from app.config import get_settings
from app.db import get_sessionmaker
from app.models import AppUser, Project
from app.projects import service as project_service
from app.sources import service as sources
from tests.conftest import write_project


@pytest.fixture(autouse=True)
def projects_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))


SPECS = {
    "specs/001-fuente-origen-ventas/spec.md":
        "# Origen ventas\n\n**Tipo**: fuente\n**Status**: Implemented\n\n"
        "**Fuente**: Origen ventas\n",
    "specs/001-fuente-origen-ventas/plan.md": "# Plan\n",
    "specs/001-fuente-origen-ventas/tasks.md": "- [X] T001 probar\n",
    "specs/002-reporte-ventas-directo/spec.md":
        "# Ventas directo\n\n**Tipo**: reporte\n**Status**: Draft\n\n**Modo**: directo\n\n"
        "**Fuente**: bi\n",
    "specs/002-reporte-ventas-directo/plan.md": "# Plan\n",
    "specs/003-envio-semanal/spec.md": "# Envío semanal\n\n**Tipo**: distribucion\n",
    "distributions/envio-semanal.yaml":
        "id: envio-semanal\nspec: specs/003-envio-semanal\nreport: ventas-directo\n"
        "subscriptions:\n  - frequency: weekly\n    weekday: 0\n    hour: 7\n"
        "    period: last_7_days\n"
        "    recipients:\n      roles: [admin]\n      emails: [ana@example.com]\n",
}


@pytest.fixture
def project(db, superuser, pg_source_like):
    actor = db.get(AppUser, superuser.id)
    created = project_service.create(db, actor, "Ventas demo")
    db.commit()
    write_project(created.id, SPECS, superuser.id)
    return db.get(Project, created.id)


@pytest.fixture
def pg_source_like(superuser):
    with get_sessionmaker().begin() as s:
        source = sources.create(
            s, s.get(AppUser, superuser.id),
            {"name": "Origen ventas", "kind": "postgresql",
             "settings": {"host": "db.interno", "port": 5432, "database": "ventas",
                          "username": "lector", "sslmode": "prefer", "timeout_seconds": 15},
             "secrets": {"password": "clave-secreta-123"}},
            get_settings(), None)
        source.last_test_ok = True


def test_overview_stages_next_commands_and_decisions(db, project):
    data = overview.build(db, project)
    specs = {s["folder"]: s for s in data["specs"]}
    assert specs["002-reporte-ventas-directo"]["stage"] == "planificada"
    assert specs["002-reporte-ventas-directo"]["next_command"] == "/speckit-tasks"
    assert specs["002-reporte-ventas-directo"]["mode"] == "directo"
    modo = next(d for d in specs["002-reporte-ventas-directo"]["decisions"]
                if d["text"].startswith("**Modo**"))
    assert (modo["file"], modo["line"]) == ("specs/002-reporte-ventas-directo/spec.md", 6)
    assert specs["003-envio-semanal"]["next_command"] == "/speckit-plan"
    origin = next(s for s in data["sources"] if s["name"] == "Origen ventas")
    assert origin == {"name": "Origen ventas", "kind": "postgresql", "exists": True,
                      "last_test_ok": True, "direct_reports": False}
    assert any(s["name"] == "bi" for s in data["sources"])
    sub = data["distributions"][0]["subscriptions"][0]
    assert sub["recipients"] == {"users": 0, "roles": ["admin"]}   # recipients are roles only


def test_overview_never_carries_personal_data_or_connection_details(db, project):
    payload = json.dumps(overview.build(db, project), ensure_ascii=False)
    for secret in ("ana@example.com", "db.interno", "lector", "clave-secreta-123"):
        assert secret not in payload
    assert "admin" in payload


def test_overview_is_capped_with_counts(db, project, monkeypatch):
    monkeypatch.setattr(overview, "MAX_CHARS", 1500)
    data = overview.build(db, project)
    assert data.get("truncated") is True
    assert len(json.dumps(data, ensure_ascii=False)) <= 1500 or len(data["specs"]) == 1
    assert data["pending_changes"]["count"] >= 0


def test_next_steps_for_ayuda(db, project):
    text = overview.next_steps(db, project, "es")
    assert "## Qué sigue en Ventas demo" in text
    assert "002-reporte-ventas-directo (planificada) → /speckit-tasks" in text


def test_next_actions_are_readable_with_links_and_hints(db, project, superuser):
    """023 T049: action texts in the request language, the new-source link, the analyze hint."""
    from app.i18n import use_locale

    write_project(project.id, {
        "specs/004-fuente-erp/spec.md":
            "# ERP\n\n**Tipo**: fuente\n**Status**: Approved\n\n**Fuente**: ERP inexistente\n",
        "specs/004-fuente-erp/plan.md": "# Plan\n",
        "specs/004-fuente-erp/tasks.md": "- [X] T001 probar\n",
        "specs/005-reporte-margen/spec.md": "# Margen\n\n**Tipo**: reporte\n**Status**: Draft\n",
        "specs/005-reporte-margen/plan.md": "# Plan\n",
        "specs/005-reporte-margen/tasks.md": "- [ ] T001 escribir report.yaml\n",
    }, superuser.id)
    with use_locale("es"):
        specs = {s["folder"]: s for s in overview.build(db, project)["specs"]}
    erp = specs["004-fuente-erp"]
    assert erp["next_command"] is None
    assert erp["next_action"] == "Crear o probar la fuente en Administración → Fuentes de datos"
    assert erp["next_link"].startswith("app:/admin/fuentes/nueva")
    margen = specs["005-reporte-margen"]
    assert (margen["stage"], margen["next_command"], margen["next_hint"]) == (
        "tareas", "/speckit-implement", "/speckit-analyze")
    with use_locale("en"):
        erp_en = next(s for s in overview.build(db, project)["specs"]
                      if s["folder"] == "004-fuente-erp")
    assert erp_en["next_action"] == "Create or test the source in Administration → Data sources"

    text = overview.next_steps(db, project, "en")
    assert "## What is next in Ventas demo" in text
    assert "005-reporte-margen (tareas) → /speckit-implement (you can check first with " \
           "/speckit-analyze)" in text
    assert "](app:/admin/fuentes/nueva" in text
