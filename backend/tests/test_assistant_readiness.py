"""Feature 017 (US4): readiness gate, the agent's run_preview tool and apply re-checking the draft
queries."""
import pytest
import yaml
from bizview_cli import authoring

from app.assistant import readiness, tools
from app.assistant.tools import run_tool
from app.config import get_settings
from app.engine import runner
from app.models import AppUser, AssistantMessage, AssistantSession
from app.projects.workview import for_session, real
from tests.conftest import chat_project_id, project_view, reauth, signed_in, sql
from tests.test_assistant_preview import LAYOUT, _draft, _schemas, _session, _with_layout
from tests.test_runner import ORIGIN
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import apply, lock
from tests.test_vibe_reporting import workspace as workspace  # fixture

# 017 readiness and the agent's run_preview/check_query through plain-mode tools; the 021
# command guard has its own tests.
pytestmark = pytest.mark.usefixtures("without_command_guard")


def _run(db, superuser, session, name, args):
    return run_tool(db, db.get(AppUser, superuser.id), session, name, args, get_settings())


def _ready_session(files, created_by=1):
    query_checks = {}
    for path in files:
        if readiness.QUERY_FILE.match(path) or readiness.REQUEST_FILE.match(path):
            query_checks[path] = {"sha256": readiness.file_sha(files[path]), "ok": True}
    return AssistantSession(
        title="t",
        created_by=created_by,
        draft={"files": files, "summary": "s"},
        validation={"valid": True},
        preview={"status": "succeeded", "fingerprint": readiness.fingerprint(files)},
        query_checks=query_checks,
        working_state=None,
    )


def _codes(result):
    return sorted(item["code"] for item in result["pending"])


def _pending(result, code):
    return next(item for item in result["pending"] if item["code"] == code)


def _checked(files: dict[str, str]) -> dict[str, str]:
    """The preview fixture draft with checks on every dataset (readiness requires them)."""
    path = "integrations/ventas-dos/integration.yaml"
    doc = yaml.safe_load(files[path])
    for dataset in doc["datasets"].values():
        if "checks" not in dataset:
            dataset["checks"] = [{"type": "row_count", "min": 1}]
    return {**files, path: yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)}


def _ready_draft(with_layout: bool = True) -> dict[str, str]:
    """The checked draft; completo (con las dos mitades del layout, 026 FR-011) por defecto."""
    return _checked(_draft(with_layout=with_layout))


def test_golden_draft_is_ready_when_checked_and_previewed():
    files = authoring.golden_files("golden")
    session = _ready_session(files)
    assert readiness.compute(session, user_texts=[]) == {"ready": True, "pending": []}

    fresh = AssistantSession(
        title="t",
        created_by=1,
        draft={"files": files, "summary": "s"},
        validation={"valid": True},
    )
    result = readiness.compute(fresh, user_texts=[])
    assert _codes(result) == ["preview", "query_check"]
    assert _pending(result, "query_check")["file"] == "integrations/facturas/queries/facturas.sql"

    invalid = AssistantSession(
        title="t",
        created_by=1,
        draft={"files": files, "summary": "s"},
        validation={"valid": False},
        preview={"status": "succeeded", "fingerprint": readiness.fingerprint(files)},
        query_checks={
            "integrations/facturas/queries/facturas.sql": {
                "sha256": readiness.file_sha(files["integrations/facturas/queries/facturas.sql"]),
                "ok": True,
            }
        },
    )
    result = readiness.compute(invalid, user_texts=[])
    assert result["ready"] is False
    assert result["pending"] == []


def test_dataset_and_report_rules():
    files = authoring.golden_files("golden")
    doc = yaml.safe_load(files["integrations/facturas/integration.yaml"])
    dataset = next(iter(doc["datasets"].values()))
    dataset.pop("primary_key")
    dataset.pop("incremental")
    dataset.pop("checks")
    files["integrations/facturas/integration.yaml"] = yaml.safe_dump(doc, sort_keys=False)
    report = yaml.safe_load(files["reports/facturas-dia/report.yaml"])
    report["pdf"]["enabled"] = False
    files["reports/facturas-dia/report.yaml"] = yaml.safe_dump(report, sort_keys=False)
    session = _ready_session(files)
    result = readiness.compute(session, user_texts=[])
    assert {"primary_key", "incremental", "checks", "pdf"} <= set(_codes(result))
    assert _pending(result, "primary_key")["file"] == "integrations/facturas/integration.yaml"
    assert _pending(result, "incremental")["file"] == "integrations/facturas/integration.yaml"
    assert _pending(result, "checks")["file"] == "integrations/facturas/integration.yaml"
    assert _pending(result, "pdf")["file"] == "reports/facturas-dia/report.yaml"

    doc = yaml.safe_load(files["integrations/facturas/integration.yaml"])
    dataset = next(iter(doc["datasets"].values()))
    dataset["incremental"] = {"mode": "full"}
    files["integrations/facturas/integration.yaml"] = yaml.safe_dump(doc, sort_keys=False)
    session = _ready_session(files)
    result = readiness.compute(session, user_texts=[])
    assert "incremental" not in _codes(result)


def test_report_draft_without_layout_is_ready():
    """026 FR-009/R16: un reporte sin layout sigue siendo válido y se puede aplicar.

    Declarar las dos mitades del layout (FR-011) es una recomendación que llevan la guía de
    autoría y la vista previa, no el semáforo de readiness: si lo bloqueara, ningún borrador
    completo de un reporte existente sin layout se podría aplicar.
    """
    sin_layout = _ready_session(_ready_draft(with_layout=False))
    assert readiness.compute(sin_layout, user_texts=[]) == {"ready": True, "pending": []}

    solo_web = _ready_session(_checked(_with_layout(_draft(), {"web": LAYOUT["web"]})))
    assert readiness.compute(solo_web, user_texts=[]) == {"ready": True, "pending": []}

    completo = _ready_session(_ready_draft())
    assert readiness.compute(completo, user_texts=[]) == {"ready": True, "pending": []}


def test_query_check_must_match_current_text():
    files = authoring.golden_files("golden")
    session = _ready_session(files)
    files["integrations/facturas/queries/facturas.sql"] += "\n-- cambio\n"
    session.preview["fingerprint"] = readiness.fingerprint(files)
    result = readiness.compute(session, user_texts=[])
    pending = _pending(result, "query_check")
    assert "no hay comprobación" in pending["message"]

    session.query_checks = {
        "integrations/facturas/queries/facturas.sql": {
            "sha256": readiness.file_sha(files["integrations/facturas/queries/facturas.sql"]),
            "ok": False,
            "error": "columnas que faltan: x",
        }
    }
    result = readiness.compute(session, user_texts=[])
    pending = _pending(result, "query_check")
    assert "columnas que faltan: x" in pending["message"]


def test_preview_states():
    files = authoring.golden_files("golden")
    session = _ready_session(files)
    session.preview = {"status": "succeeded", "fingerprint": "viejo"}
    result = readiness.compute(session, user_texts=[])
    assert "cambió" in _pending(result, "preview")["message"]

    session.preview = {"status": "failed"}
    result = readiness.compute(session, user_texts=[])
    assert "falló" in _pending(result, "preview")["message"]

    session.preview = {"status": "pending"}
    result = readiness.compute(session, user_texts=[])
    assert "en curso" in _pending(result, "preview")["message"]

    session.preview = None
    result = readiness.compute(session, user_texts=[])
    assert "run_preview" in _pending(result, "preview")["message"]


def test_personal_columns_need_user_request_and_spec_line():
    files = authoring.golden_files("golden")
    flags = {"origen_ventas": {"cliente_id": "document_id"}}
    session = _ready_session(files)
    session.working_state = {"personal": flags}
    result = readiness.compute(session, user_texts=[])
    assert _codes(result) == ["personal_data"]
    assert "cliente_id" in _pending(result, "personal_data")["message"]

    # A mention alone is not a confirmation.
    result = readiness.compute(session, user_texts=["incluye también cliente_id por favor"])
    assert _codes(result) == ["personal_data"]

    # Confirmation without the spec line still fails.
    session.working_state = {"personal": flags, "personal_confirmed": ["cliente_id"]}
    result = readiness.compute(session)
    assert _codes(result) == ["personal_data"]
    message = _pending(result, "personal_data")["message"]
    assert "nombrando la columna" in message

    spec = files["specs/001-facturas/spec.md"]
    files["specs/001-facturas/spec.md"] = (
        spec + "\n**Datos personales**: cliente_id (pedido por el usuario)\n"
    )
    session.draft = {"files": files, "summary": "s"}
    session.preview["fingerprint"] = readiness.fingerprint(files)

    # Spec line without confirmation still fails.
    session.working_state = {"personal": flags}
    result = readiness.compute(session, user_texts=[])
    assert _codes(result) == ["personal_data"]

    # Confirmation plus spec line is accepted; user_texts is no longer used.
    session.working_state = {"personal": flags, "personal_confirmed": ["cliente_id"]}
    assert _codes(readiness.compute(session, user_texts=["excluye cliente_id"])) == []


def test_personal_confirmation_recorded_from_conversation(db, superuser):
    files = authoring.golden_files("golden")
    spec_path = "specs/001-facturas/spec.md"
    files[spec_path] = files[spec_path] + "\n**Datos personales**: cliente_id\n"
    session = _ready_session(files, created_by=superuser.id)
    session.project_id = chat_project_id(db, superuser.id)
    session.working_state = {"personal": {"origen_ventas": {"cliente_id": "document_id"}}}
    db.add(session)
    db.flush()

    question = AssistantMessage(
        session_id=session.id,
        role="assistant",
        content="¿Confirmas que incluya cliente_id? Es un dato personal.",
    )
    db.add(question)
    db.flush()

    assert readiness.record_personal_confirmations(session, "No, excluye cliente_id") == []
    assert _codes(readiness.compute(session)) == ["personal_data"]

    assert readiness.record_personal_confirmations(session, "Sí, incluye cliente_id") == [
        "cliente_id"
    ]
    assert session.working_state["personal_confirmed"] == ["cliente_id"]
    assert session.working_state["personal"]["origen_ventas"]["cliente_id"] == "document_id"
    assert readiness.compute(session) == {"ready": True, "pending": []}

    session2 = _ready_session(files, created_by=superuser.id)
    session2.project_id = session.project_id
    session2.working_state = {"personal": {"origen_ventas": {"cliente_id": "document_id"}}}
    db.add(session2)
    db.flush()
    user_msg = AssistantMessage(
        session_id=session2.id, role="user", content="sí, quiero cliente_id"
    )
    db.add(user_msg)
    db.flush()
    assert readiness.record_personal_confirmations(session2, "sí, quiero cliente_id") == []
    assert _codes(readiness.compute(session2)) == ["personal_data"]


def test_no_draft_is_not_ready():
    session = AssistantSession(title="t", created_by=1, draft=None)
    result = readiness.compute(session, user_texts=[])
    assert result["ready"] is False
    assert result["pending"] == [
        {"code": "draft", "file": None, "message": "Aún no hay un borrador."}
    ]


def test_run_preview_tool_reaches_ready(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    session = for_session(db, _session(db, superuser, _ready_draft()))
    for path in session.files():
        if "/queries/" in path and path.endswith(".sql"):
            _run(db, superuser, session, "check_query",
                 {"source": "Origen prueba", "path": path})
    result, summary = _run(db, superuser, session, "run_preview", {})
    assert result["status"] == "succeeded"
    assert result["lines"][0] == "Vista previa: succeeded"
    for check in result["checks"]:
        assert set(check.keys()) == {"dataset", "type", "ok"}
    assert result["readiness"] == {"ready": True, "pending": []}
    assert summary == "Ejecutó una vista previa (correcta)."
    assert session.preview["fingerprint"] == readiness.fingerprint(session.files())
    assert session.stats["previews"] == 1
    db.commit()
    names = _schemas("%ventas\\_dos")
    assert any(f"preview_{session.id}__ds_ventas_dos" in n for n in names)
    assert not any(n.endswith("__ds_ventas_dos") and "preview_" not in n for n in names)
    assert sql(
        "SELECT count(*) FROM integration_run WHERE integration_id = 'ventas-dos'"
    )[0][0] == 0
    assert sql(
        "SELECT count(*) FROM assistant_message "
        "WHERE session_id = :s AND tool_name = 'preview'",
        s=session.id,
    )[0][0] == 1


def test_run_preview_tool_guards(db, superuser, monkeypatch):
    session = project_view(db, superuser.id, {"reports/xx/report.yaml": "id: xx\n"})
    session.validation = {"valid": False}
    with pytest.raises(tools.ToolError, match="válido"):
        _run(db, superuser, session, "run_preview", {})

    session.validation = {"valid": True}
    session.preview = {"status": "pending"}
    with pytest.raises(tools.ToolError, match="en curso"):
        _run(db, superuser, session, "run_preview", {})

    session.preview = None
    session.stats = {"previews": 1}
    monkeypatch.setattr(get_settings(), "ai_chat_max_previews", 1)
    with pytest.raises(tools.ToolError, match="máximo de 1"):
        _run(db, superuser, session, "run_preview", {})

    session.status = "archived"
    session.stats = {}
    with pytest.raises(tools.ToolError, match="abierta"):
        _run(db, superuser, session, "run_preview", {})


def test_apply_blocked_by_failing_query_check(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    files = _draft()
    path = "integrations/ventas-dos/queries/lines.sql"
    files[path] = files[path].replace(", amount AS net_amount", "")
    session = for_session(db, _session(db, superuser, files, valid=False))
    before = sql("SELECT count(*) FROM workspace_version")[0][0]
    client = reauth(signed_in("root@example.com"))
    resp = client.post(f"/api/assistant/sessions/{session.id}/apply")
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "query_check_failed"
    assert error["errors"][0]["path"] == path
    assert "net_amount" in error["errors"][0]["error"]
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == before

    files[path] = f"SELECT no_existe_col FROM {ORIGIN}\n"
    session = for_session(db, _session(db, superuser, files, valid=False))
    resp = client.post(f"/api/assistant/sessions/{session.id}/apply")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "query_check_failed"
    assert "no_existe_col" not in resp.text


def test_apply_rechecks_and_stores_query_checks(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    session = for_session(db, _session(db, superuser, _ready_draft()))
    session.preview = {
        "status": "succeeded",
        "fingerprint": readiness.fingerprint(session.files()),
    }
    db.commit()
    client = reauth(signed_in("root@example.com"))
    resp = client.post(f"/api/assistant/sessions/{session.id}/apply")
    assert resp.status_code == 200
    checks = sql("SELECT query_checks FROM project WHERE id = :i", i=session.project.id)[0][0]
    assert len(checks) == 3
    for path in checks:
        assert checks[path]["ok"] is True


def test_personal_alias_detected_from_query():
    files = authoring.golden_files("golden")
    query_path = next(
        p for p in files if p == "integrations/facturas/queries/facturas.sql"
    )
    query = files[query_path]
    needle = "    f.numero AS numero,\n"
    assert needle in query
    query = query.replace(needle, needle + "    f.correo AS contacto,\n")
    files[query_path] = query

    int_path = next(
        p for p in files if p == "integrations/facturas/integration.yaml"
    )
    doc = yaml.safe_load(files[int_path])
    doc["datasets"]["facturas"]["columns"]["contacto"] = {"type": "text"}
    files[int_path] = yaml.safe_dump(doc, sort_keys=False)

    session = _ready_session(files)
    result = readiness.compute(session)
    assert _codes(result) == ["personal_data"]
    assert "correo" in _pending(result, "personal_data")["message"]
    assert not any("contacto" in item["message"] for item in result["pending"])

    spec_path = next(p for p in files if p == "specs/001-facturas/spec.md")
    files[spec_path] = files[spec_path] + "\n**Datos personales**: correo (pedido por el usuario)\n"
    session = _ready_session(files)
    session.working_state = {"personal_confirmed": ["correo"]}
    assert _codes(readiness.compute(session)) == []


def test_personal_detected_from_request_fields():
    files = authoring.golden_files("golden-supabase")
    request_path = next(
        p for p in files if p.endswith("/requests/facturas.yaml")
    )
    request = files[request_path]
    needle = "  numero: \"$.numero\"\n"
    assert needle in request
    request = request.replace(needle, needle + "  contacto: \"$.cliente.email\"\n")
    files[request_path] = request

    int_path = next(
        p for p in files if p.endswith("/integration.yaml")
    )
    doc = yaml.safe_load(files[int_path])
    doc["datasets"]["facturas"]["columns"]["contacto"] = {"type": "text"}
    files[int_path] = yaml.safe_dump(doc, sort_keys=False)

    session = _ready_session(files)
    result = readiness.compute(session)
    codes = _codes(result)
    assert "personal_data" in codes
    assert any("email" in _pending(result, "personal_data")["message"]
               for _ in [0])


def test_apply_requires_readiness(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    before = sql("SELECT count(*) FROM workspace_version")[0][0]

    session = for_session(db, _session(db, superuser, _ready_draft()))
    client = reauth(signed_in("root@example.com"))
    resp = client.post(f"/api/assistant/sessions/{session.id}/apply")
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "not_ready"
    assert "preview" in [p["code"] for p in error["pending"]]
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == before

    session.preview = {
        "status": "succeeded",
        "fingerprint": readiness.fingerprint(session.files()),
    }
    db.commit()
    resp = client.post(f"/api/assistant/sessions/{session.id}/apply")
    assert resp.status_code == 200


def test_apply_blocked_by_unconfirmed_personal_data(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    before = sql("SELECT count(*) FROM workspace_version")[0][0]

    session = for_session(db, _session(db, superuser, _ready_draft()))
    session.working_state = {"personal": {"origen prueba": {"product_code": "name"}}}
    session.preview = {
        "status": "succeeded",
        "fingerprint": readiness.fingerprint(session.files()),
    }
    db.commit()
    client = reauth(signed_in("root@example.com"))
    resp = client.post(f"/api/assistant/sessions/{session.id}/apply")
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "not_ready"
    codes = [p["code"] for p in error["pending"]]
    assert set(codes) == {"personal_data"}
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == before


def test_run_preview_unexpected_error_is_tool_error(db, superuser, workspace, monkeypatch):
    lock(workspace)
    apply(signed_in("root@example.com"))
    session = for_session(db, _session(db, superuser, _ready_draft()))

    def boom(definition, files, *, session_id, time_limit_s):
        raise RuntimeError("boom zeta-db.interno")

    monkeypatch.setattr(runner, "run_preview", boom)
    with pytest.raises(tools.ToolError, match="No se pudo ejecutar la vista previa") as exc:
        _run(db, superuser, session, "run_preview", {})
    assert "zeta" not in str(exc.value)
    assert (session.stats or {}).get("previews") == 1
    db.commit()
    assert sql("SELECT 1")[0][0] == 1
    db.refresh(real(session))
    preview_state = sql("SELECT preview FROM project WHERE id = :i", i=session.project.id)[0][0]
    assert (preview_state or {}).get("status") != "succeeded"


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("sí, incluye cliente_email", ["cliente_email"]),
        ("excluye cliente_email", []),
        ("no incluyas cliente_email", []),
        ("sí", []),
        ("cliente_email", []),
        ("Confirmo cliente_email", ["cliente_email"]),
        ("de acuerdo con CLIENTE_EMAIL", ["cliente_email"]),
        ("si, incluye cliente_email y el nombre del producto", ["cliente_email"]),
    ],
)
def test_confirmed_columns_requires_affirmative_answer_naming_the_column(answer, expected):
    question = "¿Incluyo cliente_email en el dataset?"
    assert readiness.confirmed_columns(question, answer, flagged=["cliente_email"]) == expected


def test_confirmed_columns_edges():
    question = "¿Incluyo cliente_email en el dataset?"
    assert readiness.confirmed_columns(None, "sí, incluye cliente_email") == []
    assert readiness.confirmed_columns(
        question, "si, incluye cliente_email pero sin telefono", flagged=["cliente_email"]
    ) == []
    assert readiness.confirmed_columns("¿Incluyo codigo_x?", "sí, incluye codigo_x") == []
    assert readiness.confirmed_columns(
        "¿Incluyo codigo_x?", "sí, incluye codigo_x", flagged=["codigo_x"]
    ) == ["codigo_x"]


def test_report_without_dimensions_or_filters_is_pending():
    files = authoring.golden_files("golden")
    report_path = "reports/facturas-dia/report.yaml"
    doc = yaml.safe_load(files[report_path])
    doc.pop("dimensions", None)
    doc.pop("filters", None)
    doc["views"] = [v for v in doc.get("views", []) if v.get("type") in ("kpis", "trend")]
    files[report_path] = yaml.safe_dump(doc, sort_keys=False)
    session = _ready_session(files)
    result = readiness.compute(session)
    assert _codes(result) == ["report_dimensions", "report_dimensions"]
    assert all(item["file"] == report_path for item in result["pending"])
    assert any(
        "dimensions: {estado: {label: Estado, sql: f.estado}}" in item["message"]
        for item in result["pending"]
    )
    assert any("filters" in item["message"] for item in result["pending"])

    original = authoring.golden_files("golden")
    doc = yaml.safe_load(original[report_path])
    doc.pop("filters", None)
    files[report_path] = yaml.safe_dump(doc, sort_keys=False)
    session = _ready_session(files)
    result = readiness.compute(session)
    assert _codes(result) == ["report_dimensions"]
    assert "filters: [estado, moneda]" in result["pending"][0]["message"]
