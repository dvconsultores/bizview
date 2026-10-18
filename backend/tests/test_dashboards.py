"""US4: catalogue visibility, grants, and server-side refusal of typed URLs (FR-018 - FR-021)."""
from tests.conftest import signed_in, sql


def add_dashboard(code, status):
    sql("INSERT INTO dashboard (code, name, description, icon, sort_order, status) "
        "VALUES (:c, :n, 'd', 'chart-pie', 20, :s)", c=code, n=code.title(), s=status)


def codes(c):
    return [d["code"] for d in c.get("/api/dashboards").json()["items"]]


def test_user_without_grants_sees_nothing(user):
    assert codes(signed_in(user.email)) == []


def test_admin_sees_all_non_hidden(admin):
    add_dashboard("clinica", "available")
    add_dashboard("secreto", "hidden")
    assert codes(signed_in(admin.email)) == ["ventas", "clinica"]


def test_grant_open_and_revoke(admin, user):
    add_dashboard("clinica", "available")
    adm, usr = signed_in(admin.email), signed_in(user.email)
    r = adm.put(f"/api/admin/users/{user.id}/dashboards", json={"codes": ["clinica", "ventas"]})
    assert r.status_code == 200
    assert {d["code"]: d["granted"] for d in r.json()["dashboards"]} == \
        {"ventas": True, "clinica": True}
    assert codes(usr) == ["ventas", "clinica"]
    assert usr.get("/api/dashboards/clinica").status_code == 200
    r = usr.get("/api/dashboards/ventas")
    assert r.status_code == 403 and r.json()["error"]["code"] == "coming_soon"

    adm.put(f"/api/admin/users/{user.id}/dashboards", json={"codes": ["ventas"]})
    r = usr.get("/api/dashboards/clinica")
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    kinds = [k for (k,) in sql("SELECT kind FROM audit_event WHERE kind LIKE 'dashboard%' "
                               "ORDER BY id")]
    assert kinds == ["dashboard_granted", "dashboard_granted", "dashboard_revoked"]


def test_hidden_and_unknown_are_404(admin):
    add_dashboard("secreto", "hidden")
    c = signed_in(admin.email)
    assert c.get("/api/dashboards/secreto").status_code == 404
    assert c.get("/api/dashboards/nope").status_code == 404


def test_grant_validation(superuser, admin, user):
    c = signed_in(superuser.email)
    r = c.put(f"/api/admin/users/{user.id}/dashboards", json={"codes": ["nope"]})
    assert r.status_code == 422
    r = c.put(f"/api/admin/users/{admin.id}/dashboards", json={"codes": ["ventas"]})
    assert r.status_code == 422


def test_user_detail_lists_catalogue_with_grants(admin, user):
    detail = signed_in(admin.email).get(f"/api/admin/users/{user.id}").json()
    assert detail["dashboards"] == [{"code": "ventas", "name": "Ventas",
                                     "status": "coming_soon", "granted": False}]
    detail = signed_in(admin.email).get(f"/api/admin/users/{admin.id}").json()
    assert "granted" not in detail["dashboards"][0]
