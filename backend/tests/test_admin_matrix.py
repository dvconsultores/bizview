"""US2: user administration and the permission matrix of research R6 (SC-003, SC-009)."""
import pytest

from app.main import app
from tests.conftest import PASSWORD, client, make_user, reauth, signed_in, sql

TEMP = "Temporary-pass-77"


def audit_count():
    return sql("SELECT count(*) FROM audit_event WHERE kind NOT LIKE 'login%' "
               "AND kind NOT LIKE 'reauth%'")[0][0]


def test_every_admin_route_refuses_regular_users(user):
    c = signed_in(user.email)
    paths = {p: ops for p, ops in app.openapi()["paths"].items() if p.startswith("/api/admin")}
    assert sum(len(ops) for ops in paths.values()) >= 8
    for path, ops in paths.items():
        for method in ops:
            r = c.request(method.upper(), path.replace("{user_id}", "1"), json={})
            assert r.status_code == 403, (method, path, r.status_code)
            assert r.json()["error"]["code"] == "forbidden"


def test_audit_log_is_super_user_only(superuser, admin):
    assert signed_in(admin.email).get("/api/admin/audit").status_code == 403
    r = signed_in(superuser.email).get("/api/admin/audit")
    assert r.status_code == 200 and r.json()["items"][0]["kind"] == "login_ok"


def test_admin_creates_user_with_temporary_password(admin):
    c = signed_in(admin.email)
    r = c.post("/api/admin/users", json={"email": " New@Example.com ", "full_name": " Nora ",
                                         "role": "user", "temporary_password": TEMP})
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["email"], body["full_name"], body["must_change_password"]) == \
        ("new@example.com", "Nora", True)
    assert audit_count() == 1
    assert "Temporary" not in str(sql("SELECT detail FROM audit_event"))
    new = signed_in("new@example.com", TEMP)
    assert new.get("/api/dashboards").json()["error"]["code"] == "password_change_required"


def test_duplicate_email_any_case_conflicts(admin, user):
    r = signed_in(admin.email).post("/api/admin/users", json={
        "email": "USER@example.com", "full_name": "X", "role": "user",
        "temporary_password": TEMP})
    assert r.status_code == 409


@pytest.mark.parametrize("payload,field", [
    ({"email": "not-an-email"}, "email"),
    ({"full_name": "   "}, "full_name"),
    ({"temporary_password": "short"}, "temporary_password"),
    ({"role": "owner"}, "role"),
])
def test_create_validation(admin, payload, field):
    body = {"email": "v@example.com", "full_name": "V", "role": "user",
            "temporary_password": TEMP, **payload}
    r = signed_in(admin.email).post("/api/admin/users", json=body)
    assert r.status_code == 422
    assert field in r.json()["error"]["fields"]


def test_only_super_user_creates_admins(superuser, admin):
    body = {"email": "a2@example.com", "full_name": "A2", "role": "admin",
            "temporary_password": TEMP}
    assert signed_in(admin.email).post("/api/admin/users", json=body).status_code == 403
    assert signed_in(superuser.email).post("/api/admin/users", json=body).status_code == 201


# (actor, target, action) → allowed?   Targets: user, admin (another), super, self
ACTIONS = {
    "edit": ("PATCH", "", {"full_name": "Renamed"}),
    "deactivate": ("PATCH", "", {"is_active": False}),
    "promote": ("PATCH", "", {"role": "admin"}),
    "demote": ("PATCH", "", {"role": "user"}),
    "reset": ("POST", "/password", {"temporary_password": TEMP}),
}
EXPECTED = {
    # actor=admin
    ("admin", "user"): {"edit", "deactivate", "reset"},
    ("admin", "admin2"): set(),
    ("admin", "super"): set(),
    ("admin", "self"): set(),
    # actor=super
    ("super", "user"): {"edit", "deactivate", "reset", "promote"},
    ("super", "admin2"): {"edit", "deactivate", "reset", "demote"},
    ("super", "super"): set(),  # super user acting on itself
}


@pytest.mark.parametrize("pair", sorted(EXPECTED))
@pytest.mark.parametrize("action", sorted(ACTIONS))
def test_permission_matrix(pair, action):
    actor_kind, target_kind = pair
    people = {
        "super": make_user("root@example.com", is_superuser=True),
        "admin": make_user("admin@example.com", role="admin"),
        "admin2": make_user("admin2@example.com", role="admin"),
        "user": make_user("user@example.com"),
    }
    actor = people[actor_kind]
    target = actor if target_kind == "self" else people[target_kind]
    method, suffix, body = ACTIONS[action]
    no_op = (action == "promote" and target.role == "admin") or \
            (action == "demote" and target.role == "user")
    before = audit_count()
    r = reauth(signed_in(actor.email)).request(method, f"/api/admin/users/{target.id}{suffix}",
                                               json=body)
    if action in EXPECTED[pair] and not no_op:
        assert r.status_code in (200, 204), (pair, action, r.text)
        assert audit_count() == before + 1  # SC-009: exactly one audit record
    elif no_op:
        assert r.status_code in (200, 403)
    else:
        assert r.status_code == 403, (pair, action, r.status_code)
        assert audit_count() == before


def test_deactivation_ends_sessions_and_blocks_login(admin, user):
    phone, laptop = signed_in(user.email), signed_in(user.email)
    r = signed_in(admin.email).patch(f"/api/admin/users/{user.id}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert phone.get("/api/me").status_code == 401
    assert laptop.get("/api/me").status_code == 401
    assert client().post("/api/auth/login",
                         json={"email": user.email, "password": PASSWORD}).status_code == 401
    signed_in(admin.email).patch(f"/api/admin/users/{user.id}", json={"is_active": True})
    signed_in(user.email)


def test_reset_password_ends_sessions_clears_lock_and_sets_temporary(admin, user):
    session = signed_in(user.email)
    sql("UPDATE app_user SET locked_until = now() + interval '10 minutes', "
        "failed_attempts = 3 WHERE id = :i", i=user.id)
    r = signed_in(admin.email).post(f"/api/admin/users/{user.id}/password",
                                    json={"temporary_password": TEMP})
    assert r.status_code == 204
    assert session.get("/api/me").status_code == 401
    assert sql("SELECT must_change_password, failed_attempts, locked_until FROM app_user "
               "WHERE id = :i", i=user.id) == [(True, 0, None)]
    signed_in(user.email, TEMP)


def test_list_search_and_filters(superuser, admin, user):
    make_user("off@example.com", active=False, full_name="Olga Off")
    c = signed_in(admin.email)
    assert c.get("/api/admin/users").json()["total"] == 4
    assert [u["email"] for u in c.get("/api/admin/users?q=ULIS").json()["items"]] == \
        ["user@example.com"]
    assert c.get("/api/admin/users?q=%25").json()["total"] == 0  # LIKE wildcard is literal
    assert c.get("/api/admin/users?role=admin").json()["total"] == 2
    assert [u["email"] for u in c.get("/api/admin/users?status=inactive").json()["items"]] == \
        ["off@example.com"]
    sql("UPDATE app_user SET locked_until = now() + interval '5 minutes' WHERE id = :i",
        i=user.id)
    assert c.get("/api/admin/users?status=locked").json()["total"] == 1
    page = c.get("/api/admin/users?limit=2&offset=2").json()
    assert page["total"] == 4 and len(page["items"]) == 2


def test_unknown_user_is_404(admin):
    assert signed_in(admin.email).get("/api/admin/users/999999").status_code == 404


def test_role_change_requires_recent_password_confirmation(superuser, user):
    c = signed_in(superuser.email)
    r = c.patch(f"/api/admin/users/{user.id}", json={"role": "admin"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "reauth_required"
    assert c.patch(f"/api/admin/users/{user.id}", json={"full_name": "Otro"}).status_code == 200
    reauth(c)
    assert c.patch(f"/api/admin/users/{user.id}", json={"role": "admin"}).status_code == 200
    sql("UPDATE user_session SET reauth_at = now() - interval '6 minutes'")
    r = c.patch(f"/api/admin/users/{user.id}", json={"role": "user"})
    assert r.json()["error"]["code"] == "reauth_required"
