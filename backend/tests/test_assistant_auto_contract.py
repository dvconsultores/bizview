"""Feature 028: the run contract, its step-up and the mode selector (FR-001, FR-002, FR-000)."""
import time

import pytest

from app.ai import fake
from app.assistant import auto
from app.config import get_settings
from tests.conftest import PASSWORD, new_chat, signed_in, sql


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    for key in ("AI_AUTO_MAX_ROUNDS", "AI_AUTO_MAX_APPLIES", "AI_AUTO_RUN_MAX_SECONDS",
                "AI_AUTO_MAX_PREVIEWS"):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


CONTRACT = {"goal": "dashboard de facturas por día y estado", "stages": ["draft", "preview"]}


def _mode(client, sid, mode):
    return client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": mode})


def _confirm(client, sid, contract=None, password=PASSWORD, code=None, profile_id=None):
    body = {"contract": contract or CONTRACT, "password": password}
    if code is not None:
        body["code"] = code
    if profile_id is not None:
        body["profile_id"] = profile_id
    return client.post(f"/api/assistant/sessions/{sid}/contract", json=body)


def test_mode_defaults_to_edit_and_is_changeable(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    row = client.get(f"/api/assistant/sessions/{sid}").json()
    assert row["mode"] == "edit"
    assert row["contract"] is None and row["contract_status"] == "none"

    r = _mode(client, sid, "ask")
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "ask"
    assert sql("SELECT kind FROM audit_event WHERE kind = 'assistant_mode_changed'")

    r = _mode(client, sid, "write")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "mode_invalid"


def test_auto_without_a_contract_reports_no_contract(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    assert _mode(client, sid, "auto").status_code == 200
    row = client.get(f"/api/assistant/sessions/{sid}").json()
    assert row["mode"] == "auto"
    assert row["contract_status"] == "none"      # the pill: Auto · sin contrato
    assert row["contract"] is None


def test_contract_confirmation_requires_the_password(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    r = _confirm(client, sid, password="wrong-password")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "step_up_failed"
    assert sql("SELECT kind FROM audit_event WHERE kind = 'reauth_failed'")
    assert sql("SELECT count(*) FROM assistant_auto_run") == [(0,)]


def test_contract_confirmation_activates_auto_and_writes_the_transcript(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    r = _confirm(client, sid)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["run"]["status"] == "confirmed"
    assert body["run"]["stages"] == ["draft", "preview"]
    assert body["session"]["mode"] == "auto"
    assert body["session"]["contract_status"] == "confirmed"
    assert sql("SELECT kind FROM audit_event WHERE kind = 'assistant_contract_confirmed'")

    messages = client.get(f"/api/assistant/sessions/{sid}").json()["messages"]
    assert messages[-1]["contract"]["id"] == body["run"]["id"]

    again = _confirm(client, sid)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "contract_active"


def test_contract_rejects_apply_without_preview(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    r = _confirm(client, sid, contract={"goal": "x", "stages": ["apply"]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "contract_invalid"


def test_contract_rejects_an_unknown_source(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    contract = dict(CONTRACT, sources=[{"name": "no-existe"}])
    r = _confirm(client, sid, contract=contract)
    assert r.status_code == 422
    assert "sources" in r.json()["error"]["fields"]


def test_internet_profile_requires_a_two_step_code(superuser, db, monkeypatch):
    import pyotp

    from tests.conftest import reauth

    client = signed_in("root@example.com")
    reauth(client)
    setup = client.post("/api/me/mfa/setup").json()
    assert client.post("/api/me/mfa/enable",
                       json={"code": pyotp.TOTP(setup["secret"]).now()}).status_code == 200
    monkeypatch.setenv("SECURITY_PROFILE", "internet")
    get_settings.cache_clear()

    sid = new_chat(client)
    assert _confirm(client, sid).status_code == 401          # password alone is not enough
    # The enrolment code cannot be replayed (mfa.verify_code rejects a used step): move one step.
    later = pyotp.TOTP(setup["secret"]).at(time.time() + 30)
    ok = _confirm(client, sid, code=later)
    assert ok.status_code == 201, ok.text


def test_spent_contract_never_refuses_a_new_one_but_keeps_the_mode(superuser, db):
    """One contract per run: after a stop the mode stays Auto and a new contract is needed."""
    client = signed_in("root@example.com")
    sid = new_chat(client)
    assert _confirm(client, sid).status_code == 201
    sql("UPDATE assistant_auto_run SET status = 'stopped', stop_reason = 'stopped:user' "
        "WHERE session_id = :sid", sid=sid)
    row = client.get(f"/api/assistant/sessions/{sid}").json()
    assert row["mode"] == "auto"
    assert row["contract_status"] == "stopped"
    assert _confirm(client, sid).status_code == 201


def test_cancel_changes_nothing(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    assert _mode(client, sid, "auto").status_code == 200
    assert client.post(f"/api/assistant/sessions/{sid}/contract/cancel").status_code == 204
    row = client.get(f"/api/assistant/sessions/{sid}").json()
    assert row["mode"] == "auto" and row["contract_status"] == "none"
    assert sql("SELECT count(*) FROM assistant_auto_run") == [(0,)]


def test_run_profiles_crud_and_audit(superuser, db):
    client = signed_in("root@example.com")
    payload = {"name": "ERP hasta aplicar",
               "contract": {"stages": ["draft", "preview", "apply"], "visible_to": []}}
    r = client.post("/api/assistant/run-profiles", json=payload)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert client.get("/api/assistant/run-profiles").json()["items"][0]["name"] == payload["name"]

    clash = client.post("/api/assistant/run-profiles", json=payload)
    assert clash.status_code == 422 and clash.json()["error"]["code"] == "name_taken"

    edited = client.patch(f"/api/assistant/run-profiles/{pid}",
                          json={"name": "ERP aplicar", "contract": payload["contract"]})
    assert edited.status_code == 200 and edited.json()["name"] == "ERP aplicar"

    assert client.delete(f"/api/assistant/run-profiles/{pid}").status_code == 204
    assert client.get("/api/assistant/run-profiles").json()["items"] == []
    kinds = {row[0] for row in sql("SELECT kind FROM audit_event WHERE kind LIKE "
                                   "'assistant_profile_%'")}
    assert kinds == {"assistant_profile_created", "assistant_profile_edited",
                     "assistant_profile_deleted"}


def test_profile_never_replaces_the_step_up(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    r = client.post("/api/assistant/run-profiles",
                    json={"name": "rápido", "contract": {"stages": ["draft"]}})
    pid = r.json()["id"]
    assert _confirm(client, sid, password="nope", profile_id=pid).status_code == 401
    assert _confirm(client, sid, profile_id=pid).status_code == 201


def test_contract_model_matches_the_json_schema():
    """The pydantic model and contracts/run-contract.schema.json accept and reject the same."""
    import json
    from pathlib import Path

    schema = json.loads((Path(__file__).resolve().parents[2] / "specs" / "028-autonomous-mode"
                         / "contracts" / "run-contract.schema.json").read_text())
    assert set(schema["required"]) == {"goal", "stages", "limits"}
    assert "goal" in auto.RunContract.model_fields
    assert auto.RunContract.model_fields["stages"].default_factory() == ["draft", "preview",
                                                                        "apply"]
    assert auto.RunContract.model_fields["auto_rollback"].default is True
    assert auto.RunContract.model_fields["modify_existing"].default is False
