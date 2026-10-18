"""Home page counters (GET /api/admin/overview): one request, one query, by role."""
from tests.conftest import make_user, signed_in, sql


def test_admin_sees_user_counts_only(admin, user):
    make_user("inactivo@example.com", active=False)
    body = signed_in("admin@example.com").get("/api/admin/overview").json()
    assert body == {"users": 3, "active_users": 2}


def test_superuser_sees_sources_and_integrations(superuser):
    sql("INSERT INTO data_source (name, kind, enabled, last_test_ok) VALUES "
        "('A', 'postgresql', true, true), ('B', 'rest', true, false), ('C', 'rest', false, true)")
    body = signed_in("root@example.com").get("/api/admin/overview").json()
    assert body == {"users": 1, "active_users": 1, "sources": 3, "connected_sources": 1,
                    "failed_integrations": 0, "integrations": 0}


def test_regular_user_is_refused(user):
    assert signed_in("user@example.com").get("/api/admin/overview").status_code == 403
