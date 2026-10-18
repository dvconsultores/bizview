import hashlib
import re
import shutil
from datetime import UTC

from fastapi.testclient import TestClient

from app.auth.sessions import COOKIE_NAME
from app.config import get_settings
from app.main import app
from app.security import throttle
from app.sharing.links import UNAVAILABLE
from tests.conftest import PASSWORD, client, client_from, set_mail, signed_in, sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import SELECTION, apply, lock
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture
from tests.workspace_fixture import REPORT, write

PUBLIC_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}


def enable_sharing(on: bool = True):
    set_mail(share_links_enabled=on)


def new_link(c, days=7, note=None) -> dict:
    body = {}
    if days is not None:
        body["days"] = days
    if note is not None:
        body["note"] = note
    r = c.post("/api/dashboards/ventas/links", json=body or {})
    assert r.status_code == 201, r.text
    return r.json()


def _fill(m: re.Match) -> str:
    return "ventas" if m.group(1) in {"code", "report_id"} else "1"


def test_create_requires_sharing_enabled_and_admin(applied, admin, user):
    super_client = applied
    admin_client = signed_in(admin.email)

    r = admin_client.post("/api/dashboards/ventas/links", json={"days": 7})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "sharing_disabled"

    enable_sharing()

    anon = client()
    assert anon.get("/api/dashboards/ventas/links").status_code == 401
    assert anon.post("/api/dashboards/ventas/links", json={"days": 7}).status_code == 401

    user_id = sql("SELECT id FROM app_user WHERE email = :e", e=user.email)[0][0]
    dash_id = sql("SELECT id FROM dashboard WHERE code = 'ventas'")[0][0]
    sql(
        "INSERT INTO dashboard_access (user_id, dashboard_id, granted_by) "
        "VALUES (:u, :d, :u)",
        u=user_id,
        d=dash_id,
    )
    user_client = signed_in(user.email)
    assert user_client.get("/api/dashboards/ventas/links").status_code == 403
    assert user_client.post("/api/dashboards/ventas/links", json={"days": 7}).status_code == 403

    assert admin_client.post("/api/dashboards/ventas/links", json={"days": 7}).status_code == 201
    assert super_client.post("/api/dashboards/ventas/links", json={"days": 7}).status_code == 201


def test_link_shown_once_and_stored_hashed(applied, monkeypatch):
    super_client = applied
    enable_sharing()
    link = new_link(super_client, note="  Para gerencia  ")
    token = link["token"]
    assert len(token) >= 43
    assert link["url"] == f"http://testserver/s/{token}"
    assert link["note"] == "Para gerencia"
    assert link["active"] is True
    assert link["visits"] == 0
    assert link["created_by"]["name"] == "Super Usuario"

    listing_url = "/api/dashboards/ventas/links"
    listing = super_client.get(listing_url).json()["items"][0]
    assert "token" not in listing
    assert "url" not in listing
    assert "token_hash" not in listing
    assert token not in super_client.get(listing_url).text

    rows = sql("SELECT token_hash FROM share_link ORDER BY id DESC LIMIT 1")
    stored = bytes(rows[0][0])
    assert stored == hashlib.sha256(token.encode()).digest()
    assert token.encode() not in stored

    audit_rows = sql("SELECT detail FROM audit_event WHERE kind = 'share_link_created'")
    assert audit_rows and token not in str(audit_rows[0][0])

    link_row = sql(
        "SELECT created_at, expires_at FROM share_link ORDER BY id DESC LIMIT 1"
    )[0]
    delta = link_row[1].astimezone(UTC) - link_row[0].astimezone(UTC)
    assert abs(delta.total_seconds() - 7 * 86400) < 60

    monkeypatch.setattr(get_settings(), "site_address", "bi.example.com")
    fresh = super_client.post("/api/dashboards/ventas/links", json={"days": 7}).json()
    assert fresh["url"].startswith("https://bi.example.com/s/")


def test_days_and_note_validation(applied):
    super_client = applied
    enable_sharing()
    assert super_client.post("/api/dashboards/ventas/links", json={"days": 0}).status_code == 422
    assert super_client.post("/api/dashboards/ventas/links", json={"days": 91}).status_code == 422
    assert (
        super_client.post(
            "/api/dashboards/ventas/links", json={"note": "a" * 201}
        ).status_code
        == 422
    )
    link90 = new_link(super_client, days=90)
    row = sql("SELECT created_at, expires_at FROM share_link WHERE id = :i", i=link90["id"])
    created_utc = row[0][0].astimezone(UTC)
    expires_utc = row[0][1].astimezone(UTC)
    assert abs((expires_utc - created_utc).total_seconds() - 90 * 86400) < 60

    default = super_client.post("/api/dashboards/ventas/links", json={})
    assert default.status_code == 201, default.text
    default_row = sql(
        "SELECT created_at, expires_at FROM share_link WHERE id = :i",
        i=default.json()["id"],
    )
    default_utc = default_row[0][1].astimezone(UTC) - default_row[0][0].astimezone(UTC)
    assert abs(default_utc.total_seconds() - 7 * 86400) < 60


def test_at_most_twenty_active_links(applied):
    super_client = applied
    enable_sharing()
    links = [new_link(super_client) for _ in range(20)]
    r = super_client.post("/api/dashboards/ventas/links", json={"days": 7})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "too_many_links"

    assert super_client.delete(f"/api/dashboards/ventas/links/{links[0]['id']}").status_code == 204
    assert super_client.post("/api/dashboards/ventas/links", json={"days": 7}).status_code == 201

    sql(
        "UPDATE share_link SET created_at = now() - interval '2 days', "
        "expires_at = now() - interval '1 second' WHERE id = :i",
        i=links[1]["id"],
    )
    assert super_client.post("/api/dashboards/ventas/links", json={"days": 7}).status_code == 201

    r = super_client.post("/api/dashboards/ventas/links", json={"days": 7})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "too_many_links"


def test_not_shareable_dashboard(applied):
    super_client = applied
    enable_sharing()
    sql(
        "INSERT INTO dashboard (code, name, description, icon, status) "
        "VALUES ('otro', 'Otro', '', 'chart-line', 'available')"
    )
    r = super_client.post("/api/dashboards/otro/links", json={"days": 7})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "not_shareable"
    assert super_client.post("/api/dashboards/nope/links", json={"days": 7}).status_code == 404


def test_public_view_data_filters_pdf_without_session(applied):
    super_client = applied
    enable_sharing()
    link = new_link(super_client)
    token = link["token"]
    pub = client()
    base = f"/api/shared/{token}"

    r = pub.get(base)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dashboard"]["code"] == "ventas"
    assert body["report"]["title"]
    assert body["report"]["ai_narrative"] is False
    assert body["expires_at"]
    for key, value in PUBLIC_HEADERS.items():
        assert r.headers.get(key) == value

    signed = super_client.get("/api/reports/ventas/data?" + SELECTION).json()
    pub_data = pub.get(base + "/data?" + SELECTION)
    assert pub_data.status_code == 200
    assert pub_data.json()["selection"] == signed["selection"]
    assert pub_data.json()["views"] == signed["views"]
    etag = pub_data.headers.get("ETag")
    assert etag
    assert (
        pub.get(base + "/data?" + SELECTION, headers={"If-None-Match": etag}).status_code
        == 304
    )

    filtered = pub.get(base + "/data?" + SELECTION + "&filter.product=P1").json()
    assert filtered["views"][0]["items"][0]["value"] == 7.5

    filters = pub.get(base + "/filters/product?" + SELECTION)
    assert filters.status_code == 200
    assert filters.json()["items"] == ["P1", "P2"]
    assert pub.get(base + "/filters/unknown?" + SELECTION).status_code == 404

    pdf_resp = pub.post(base + "/pdf?" + SELECTION)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")
    assert "(11,75 USD)".encode("latin-1") in pdf_resp.content

    assert pub.get(base + "/narrative").status_code in (404, 405)

    # One earlier page open, plus two more here = three visits total.
    pub.get(base)
    pub.get(base)
    listed = super_client.get("/api/dashboards/ventas/links").json()["items"][0]
    assert listed["visits"] == 3
    assert listed["last_visit_at"] is not None


def test_unavailable_links_answer_the_same(applied):
    super_client = applied
    enable_sharing()
    a = new_link(super_client)
    b = new_link(super_client)
    c = new_link(super_client)
    pub = client()

    unknown = pub.get("/api/shared/" + "x" * 43)
    assert unknown.status_code == 404
    assert unknown.json()["error"]["message"] == str(UNAVAILABLE)

    malformed = pub.get("/api/shared/abc")
    assert malformed.status_code == 404
    assert malformed.json() == unknown.json()
    for key, value in PUBLIC_HEADERS.items():
        assert unknown.headers.get(key) == value

    assert super_client.delete(f"/api/dashboards/ventas/links/{a['id']}").status_code == 204
    assert super_client.delete(f"/api/dashboards/ventas/links/{a['id']}").status_code == 204
    assert len(sql("SELECT 1 FROM audit_event WHERE kind = 'share_link_revoked'")) == 1

    revoked = pub.get(f"/api/shared/{a['token']}")
    assert revoked.status_code == 404
    assert revoked.json() == unknown.json()
    assert pub.get(f"/api/shared/{a['token']}/data").status_code == 404
    assert pub.post(f"/api/shared/{a['token']}/pdf").status_code == 404

    sql(
        "UPDATE share_link SET created_at = now() - interval '2 days', "
        "expires_at = now() - interval '1 second' WHERE id = :i",
        i=b["id"],
    )
    expired = pub.get(f"/api/shared/{b['token']}")
    assert expired.status_code == 404
    assert expired.json() == unknown.json()

    enable_sharing(False)
    off = pub.get(f"/api/shared/{c['token']}")
    assert off.status_code == 404
    assert off.json() == unknown.json()
    enable_sharing(True)
    assert pub.get(f"/api/shared/{c['token']}").status_code == 200

    sql("UPDATE dashboard SET status = 'hidden' WHERE code = 'ventas'")
    hidden = pub.get(f"/api/shared/{c['token']}")
    assert hidden.status_code == 404
    assert hidden.json() == unknown.json()
    sql("UPDATE dashboard SET status = 'available' WHERE code = 'ventas'")

    for path in (f"/api/shared/{a['token']}", f"/api/shared/{b['token']}"):
        resp = pub.get(path)
        for key, value in PUBLIC_HEADERS.items():
            assert resp.headers.get(key) == value


def test_public_pdf_keeps_csrf(applied):
    super_client = applied
    enable_sharing()
    link = new_link(super_client)
    raw_client = TestClient(app)
    resp = raw_client.post(f"/api/shared/{link['token']}/pdf?" + SELECTION)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "csrf_failed"
    assert raw_client.get(f"/api/shared/{link['token']}").status_code == 200


def test_guessing_is_throttled_per_address(applied, monkeypatch):
    super_client = applied
    enable_sharing()
    link = new_link(super_client)
    monkeypatch.setattr(throttle, "SHARE_GUESS_LIMIT", 3)

    guessing = client_from("203.0.113.50")
    for _ in range(3):
        assert guessing.get("/api/shared/" + "y" * 43).status_code == 404
    blocked = guessing.get(f"/api/shared/{link['token']}")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    retry = blocked.json()["error"]["retry_after_seconds"]
    assert 0 < retry <= 600
    login = guessing.post(
        "/api/auth/login",
        json={"email": "root@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    guessing.get(f"/api/shared/{link['token']}")
    rows = sql(
        "SELECT detail::text FROM audit_event WHERE kind = 'login_rate_limited'"
    )
    assert len(rows) == 1
    assert '"cause": "share_link"' in rows[0][0]

    other = client_from("203.0.113.51")
    assert other.get(f"/api/shared/{link['token']}").status_code == 200

    expired = new_link(super_client)
    sql(
        "UPDATE share_link SET created_at = now() - interval '2 days', "
        "expires_at = now() - interval '1 second' WHERE id = :i",
        i=expired["id"],
    )
    known_expired = client_from("203.0.113.52")
    for _ in range(5):
        resp = known_expired.get(f"/api/shared/{expired['token']}")
        assert resp.status_code == 404, resp.text


def test_public_requests_capped_per_address(applied, monkeypatch):
    super_client = applied
    enable_sharing()
    link = new_link(super_client)
    monkeypatch.setattr(throttle, "PUBLIC_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(throttle, "_public_hits", {})

    capped = client_from("203.0.113.60")
    assert capped.get(f"/api/shared/{link['token']}").status_code == 200
    assert capped.get(f"/api/shared/{link['token']}").status_code == 200
    limited = capped.get(f"/api/shared/{link['token']}")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"

    assert client_from("203.0.113.61").get(f"/api/shared/{link['token']}").status_code == 200


def test_link_reaches_only_its_dashboard(applied):
    super_client = applied
    enable_sharing()
    link = new_link(super_client)
    token = link["token"]

    probed = 0
    for route, ops in app.openapi()["paths"].items():
        if not route.startswith("/api/shared/"):
            url = re.sub(r"\{([^}]+)\}", _fill, route)
            for method in ops:
                if method.lower() not in {"get", "post", "put", "delete", "patch"}:
                    continue
                plain = client()
                armed = client()
                separator = "&" if "?" in url else "?"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Cookie": f"{COOKIE_NAME}={token}",
                }
                plain_resp = plain.request(method.upper(), url, json={})
                armed_resp = armed.request(
                    method.upper(),
                    url + separator + f"token={token}",
                    json={},
                    headers=headers,
                )
                probed += 1
                assert plain_resp.status_code == armed_resp.status_code, url
                if armed_resp.status_code == 200:
                    assert not route.startswith("/api/reports")
                    assert not route.startswith("/api/dashboards")
                    assert not route.startswith("/api/workspace")
                    assert not route.startswith("/api/sources")
                    assert not route.startswith("/api/admin")
                    assert not route.startswith("/api/me")
                    assert not route.startswith("/api/assistant")
                    assert not route.startswith("/api/integrations")
                    assert not route.startswith("/api/tokens")
                assert "net_sales" not in armed_resp.text
                assert "Ventas netas" not in armed_resp.text
    assert probed > 40

    pub = client()
    assert pub.get(f"/api/shared/{token}/version").status_code != 200
    assert pub.get(f"/api/shared/{token}/narrative").status_code != 200
    assert pub.get(f"/api/shared/{token}/../../reports/ventas").status_code != 200


def test_link_list_and_revoke_scoped_to_dashboard(applied):
    super_client = applied
    enable_sharing()
    link = new_link(super_client)
    sql(
        "INSERT INTO dashboard (code, name, description, icon, status) "
        "VALUES ('otro', 'Otro', '', 'chart-line', 'available')"
    )
    resp = super_client.delete(f"/api/dashboards/otro/links/{link['id']}")
    assert resp.status_code == 404
    assert client().get(f"/api/shared/{link['token']}").status_code == 200


def test_sign_in_failures_do_not_block_links(applied, monkeypatch):
    enable_sharing()
    link = new_link(applied)
    monkeypatch.setattr(get_settings(), "login_rate_limit", 3)
    c = client_from("203.0.113.70")
    for _ in range(3):
        r = c.post(
            "/api/auth/login",
            json={"email": "root@example.com", "password": "wrong-password-x"},
        )
        assert r.status_code == 401
    r = c.post(
        "/api/auth/login",
        json={"email": "root@example.com", "password": PASSWORD},
    )
    assert r.status_code == 429
    assert c.get(f"/api/shared/{link['token']}").status_code == 200
    rows = sql(
        "SELECT window_start FROM login_throttle WHERE ip = '203.0.113.70'"
    )
    assert rows
    assert all(row[0].second == 0 for row in rows)


def test_listing_marks_origin_and_counted_total(applied):
    enable_sharing()
    created = new_link(applied)
    assert created["origin"] == "manual"
    assert created["counted"] is True
    listing = applied.get("/api/dashboards/ventas/links").json()
    assert listing["active_count"] == 1
    assert listing["items"][0]["origin"] == "manual"
    r = applied.delete(f"/api/dashboards/ventas/links/{created['id']}")
    assert r.status_code == 204
    listing = applied.get("/api/dashboards/ventas/links").json()
    assert listing["active_count"] == 0
    assert listing["items"][0]["active"] is False


def test_link_follows_workspace_versions(applied, workspace):
    enable_sharing()
    c = applied
    pub = client()
    link = new_link(c)

    # New version with the report: same link returns the new title.
    write(workspace, "reports/ventas/report.yaml", REPORT.format(title="Ventas 2"))
    lock(workspace)
    apply(c)

    signed_title = c.get("/api/reports/ventas").json()["title"]
    shared = pub.get(f"/api/shared/{link['token']}")
    assert shared.status_code == 200
    assert shared.json()["report"]["title"] == "Ventas 2"
    assert shared.json()["report"]["title"] == signed_title

    data = pub.get(f"/api/shared/{link['token']}/data?{SELECTION}")
    assert data.status_code == 200

    pdf = pub.post(f"/api/shared/{link['token']}/pdf?{SELECTION}")
    assert pdf.status_code == 200

    # New version without the report: same neutral 404 as an unknown token.
    shutil.rmtree(workspace / "reports")
    lock(workspace)
    apply(c)
    assert sql("SELECT status FROM dashboard WHERE code = 'ventas'")[0][0] == "hidden"

    unknown = pub.get("/api/shared/" + "x" * 43)
    assert unknown.status_code == 404
    assert unknown.json()["error"]["message"] == str(UNAVAILABLE)
    for key, value in PUBLIC_HEADERS.items():
        assert unknown.headers[key] == value

    for method, path in (
        ("get", f"/api/shared/{link['token']}"),
        ("get", f"/api/shared/{link['token']}/data?{SELECTION}"),
        ("post", f"/api/shared/{link['token']}/pdf?{SELECTION}"),
    ):
        resp = getattr(pub, method)(path)
        assert resp.status_code == 404
        assert resp.json() == unknown.json()
        for key, value in PUBLIC_HEADERS.items():
            assert resp.headers[key] == value


def test_admin_networks_cover_share_links_and_keep_user_reads(applied, user, monkeypatch):
    """FR-022: a stolen admin session outside the allow-list cannot mint a public link."""
    enable_sharing()
    monkeypatch.setattr(get_settings(), "admin_allowed_networks", "10.0.0.0/8")
    outside = client_from("198.51.100.50")
    r = outside.post("/api/auth/login", json={"email": "root@example.com",
                                              "password": PASSWORD})
    assert r.status_code == 200, r.text
    r = outside.post("/api/dashboards/ventas/links", json={"days": 7})
    assert r.status_code == 403 and r.json()["error"]["code"] == "address_not_allowed"
    assert sql("SELECT count(*) FROM share_link")[0][0] == 0
    assert outside.post("/api/dashboards/ventas/email", json={}).status_code == 403
    assert outside.post("/api/dashboards/ventas/subscriptions",
                        json={"frequency": "daily", "hour": 8, "period": "last_month"}
                        ).status_code == 403
    assert outside.get("/api/projects").status_code == 403
    assert outside.post("/api/projects", json={"name": "Robado"}).status_code == 403
    assert outside.post("/api/assistant/sessions", json={"project": "x"}).status_code == 403
    # Reading the share controls and the dashboard catalogue is not a state change.
    assert outside.get("/api/dashboards/ventas/links").status_code == 200

    normal = client_from("198.51.100.50")
    assert normal.post("/api/auth/login", json={"email": user.email,
                                                "password": PASSWORD}).status_code == 200
    assert normal.get("/api/dashboards").status_code == 200

    inside = client_from("10.1.2.3")
    assert inside.post("/api/auth/login", json={"email": "root@example.com",
                                                "password": PASSWORD}).status_code == 200
    assert inside.post("/api/dashboards/ventas/links", json={"days": 7}).status_code == 201
