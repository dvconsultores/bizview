"""Feature 020 T045: project distributions own their subscriptions."""
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db import get_sessionmaker
from app.mail import subscriptions
from app.models import AppUser, Project
from app.projects import distributions
from app.workspace.service import forget_active_version
from tests.conftest import make_user, signed_in, sql
from tests.test_mail_subscriptions import enable_mail, grant_user
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture

WEEKLY = {"frequency": "weekly", "weekday": 0, "hour": 7, "period": "last_7_days",
          "recipients": {"roles": ["admin"]}, "attach_pdf": True, "link_days": None}
OWNED = "FROM email_subscription WHERE project_id IS NOT NULL"


def version(*items, report="ventas", share=None):
    definition = {"id": "envio", "spec": "specs/003-envio", "report": report,
                  "subscriptions": list(items), **({"share": share} if share else {})}
    return SimpleNamespace(artifacts={"distributions": {
        "envio": {"project": "demo", "definition": definition}}})


@pytest.fixture
def project(applied):
    with get_sessionmaker().begin() as db:
        db.add(Project(slug="demo", name="Demo"))


def run_sync(v, previous=None):
    with get_sessionmaker().begin() as db:
        actor = db.scalar(select(AppUser).where(AppUser.email == "root@example.com"))
        return distributions.sync(db, v, actor, previous=previous)


def counts(created=0, updated=0, deleted=0):
    return {"created": created, "updated": updated, "deleted": deleted}


def test_sync_create_update_delete(project):
    assert run_sync(version(WEEKLY)) == counts(created=1)
    rows = sql(f"SELECT distribution_id, distribution_index, frequency, weekday, hour, "
               f"recipients {OWNED}")
    assert [tuple(r) for r in rows] == [("envio", 0, "weekly", 0, 7, [{"role": "admin"}])]
    assert run_sync(version(WEEKLY)) == counts()
    assert run_sync(version({**WEEKLY, "hour": 9})) == counts(updated=1)
    assert sql(f"SELECT hour {OWNED}")[0][0] == 9
    assert run_sync(SimpleNamespace(artifacts={})) == counts(deleted=1)
    kinds = sql("SELECT kind FROM audit_event WHERE kind LIKE 'email_subscription_%' ORDER BY id")
    assert [r[0] for r in kinds] == ["email_subscription_created", "email_subscription_updated",
                                     "email_subscription_deleted"]


def test_hand_made_rows_untouched(project):
    enable_mail()
    r = signed_in("root@example.com").post("/api/dashboards/ventas/subscriptions", json={
        "frequency": "daily", "hour": 8, "period": "mtd", "attach_pdf": True, "users": [],
        "emails": ["gerente@cliente.com"]})
    assert r.status_code == 201, r.text
    run_sync(version(WEEKLY))
    run_sync(SimpleNamespace(artifacts={}))
    assert sql("SELECT count(*) FROM email_subscription WHERE project_id IS NULL")[0][0] == 1


def test_paused_kept_unless_yaml_changes(project):
    run_sync(version(WEEKLY))
    sql(f"UPDATE email_subscription SET paused = true WHERE id IN (SELECT id {OWNED})")
    assert run_sync(version({**WEEKLY, "hour": 9}), previous=version(WEEKLY)) == counts(updated=1)
    assert sql(f"SELECT paused {OWNED}")[0][0] is True
    assert run_sync(version({**WEEKLY, "hour": 9, "paused": False}),
                    previous=version({**WEEKLY, "hour": 9, "paused": True})) == counts(updated=1)
    assert sql(f"SELECT paused {OWNED}")[0][0] is False


def test_owned_rows_only_pause(project):
    enable_mail()
    run_sync(version(WEEKLY))
    sub_id = sql(f"SELECT id {OWNED}")[0][0]
    c = signed_in("root@example.com")
    url = f"/api/dashboards/ventas/subscriptions/{sub_id}"
    for r in (c.patch(url, json={"hour": 10}), c.delete(url)):
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "managed_by_project"
    r = c.patch(url, json={"paused": True})
    assert r.status_code == 200, r.text
    assert r.json()["paused"] is True
    items = c.get("/api/dashboards/ventas/subscriptions").json()["items"]
    owned = next(i for i in items if i["id"] == sub_id)
    assert owned["managed_by"] == {"project": "Demo", "slug": "demo", "distribution": "envio"}
    assert owned["recipients"] == [{"role": "admin"}]


def test_role_recipients_at_tick(project):
    enable_mail()
    make_user("ana@cliente.com", role="admin", full_name="Ana")
    grant_user(make_user("luis@cliente.com", role="user", full_name="Luis").id)
    make_user("off@cliente.com", role="admin", full_name="Off", active=False)
    run_sync(version({**WEEKLY, "recipients": {"roles": ["admin", "user"]}}))
    sql(f"UPDATE email_subscription SET next_due_at = now() - interval '1 minute' "
        f"WHERE id IN (SELECT id {OWNED})")
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, datetime.now(UTC)) == 1
    recipients = [r[0] for r in sql("SELECT recipient FROM email_delivery")]
    assert {"ana@cliente.com", "luis@cliente.com", "root@example.com"} <= set(recipients)
    assert "off@cliente.com" not in recipients
    assert len(recipients) == len(set(recipients))


def _set_active_distributions(dists):
    sql("UPDATE workspace_version SET artifacts = jsonb_set(artifacts::jsonb, '{distributions}', "
        "CAST(:d AS jsonb)) WHERE state = 'active'", d=json.dumps(dists))
    forget_active_version()


def test_share_policy(project):
    enable_mail(sharing=True)
    c = signed_in("root@example.com")
    _set_active_distributions(version(WEEKLY, share={"allowed": False}).artifacts["distributions"])
    r = c.post("/api/dashboards/ventas/links", json={"days": 7})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "sharing_disabled_by_project"
    _set_active_distributions(
        version(WEEKLY, share={"allowed": True, "max_days": 5}).artifacts["distributions"])
    r = c.post("/api/dashboards/ventas/links", json={"days": 7})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "share_days_exceed_project"
    assert c.post("/api/dashboards/ventas/links", json={"days": 5}).status_code == 201


def test_validation_warns_past_the_subscription_cap(project):
    """020 T091, plan §6: distributions + hand-made rows over the cap → one warning."""
    from app.projects.compose import _subscription_cap_warnings

    enable_mail()
    c = signed_in("root@example.com")
    for hour in (6, 7):
        assert c.post("/api/dashboards/ventas/subscriptions", json={
            "frequency": "daily", "hour": hour, "period": "mtd", "attach_pdf": True,
            "users": [], "emails": ["gerente@cliente.com"]}).status_code == 201

    def result(n):
        entry = SimpleNamespace(id="envio", project="demo",
                                artifact={"report": "ventas", "subscriptions": [WEEKLY] * n})
        return SimpleNamespace(distributions={"envio": entry})

    with get_sessionmaker()() as db:
        demo = db.scalar(select(Project).where(Project.slug == "demo"))
        assert _subscription_cap_warnings(db, demo, result(18)) == []          # 18 + 2 = 20
        warnings = _subscription_cap_warnings(db, demo, result(19))            # 19 + 2 = 21
    assert [(w["code"], w["file"], w["project"]) for w in warnings] == [
        ("subscription_cap", "distributions/envio.yaml", "demo")]
    assert "21" in warnings[0]["message"] and "20" in warnings[0]["message"]
