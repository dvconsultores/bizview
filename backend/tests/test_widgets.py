"""Feature 065: a dashboard embedded in another site (widget).

The security requirements are the reason this file is long: a widget is a public door that stays
open for months. What is proved here:

* the framed document is allowed by **that widget's** sites and by nothing else, and every other
  route keeps the site-wide refusal of framing (`test_csp_matches_the_edge_default`);
* a request carrying an admin's session cookie gets exactly the anonymous payload;
* a revoked, expired, replaced, withdrawn or switched-off widget answers one neutral 404 and no
  data;
* a control switched off (PDF, filters) is refused when requested directly;
* the per-widget ceiling answers a retry, and a hammered widget does not slow the signed-in reads;
* the key is stored hashed, shown once, and every action is audited;
* the public definition publishes no site list and no internal name, only the one origin that framed
  the document (defect 3 of the review);
* the ceiling's count is committed before the PDF render, so a slow PDF never holds the widget's row
  (defect 1), and images do not spend the ceiling at all (defect 2);
* an explicit null on a control is a 422, not a 500 (defect 4).

Feature 018's own suite (`test_sharing_links.py`) runs unchanged, which is the proof that its
90-day rule and its 20-link count did not move.
"""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote

import pytest

from app.config import get_settings
from app.reports import pdf as report_pdf
from app.sharing import widgets
from app.sharing.links import UNAVAILABLE as LINK_UNAVAILABLE
from app.workspace.service import forget_active_version
from tests.conftest import PASSWORD, client, client_from, set_mail, signed_in, sql
from tests.test_project_distributions import _set_active_distributions, version
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import SELECTION
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture

ROOT = Path(__file__).resolve().parents[2]
CADDYFILE = ROOT / "deploy" / "caddy" / "Caddyfile"
PUBLIC_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}
SITE = "https://www.cliente.com"


@pytest.fixture
def embed(monkeypatch):
    """Widget embedding switched on for one test, with share links (FR-007)."""
    monkeypatch.setattr(get_settings(), "embed_widgets_enabled", True)
    set_mail(share_links_enabled=True)
    return True


def new_widget(c, *, name="Ventas cliente", sites=(SITE,), **extra) -> dict:
    body = {"name": name, "sites": list(sites), **extra}
    r = c.post("/api/dashboards/ventas/widgets", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def token_of(widget: dict) -> str:
    return widget["key"]


def frame_ancestors(csp: str) -> str:
    match = re.search(r"frame-ancestors ([^;]+);", csp)
    assert match, csp
    return match.group(1).strip()


# --------------------------------------------------------------------------------- creation

def test_create_requires_admin_share_links_and_embedding(applied, admin, user, monkeypatch):
    c = applied

    # Embedding off (the installation's default) → refused, with the reason.
    set_mail(share_links_enabled=True)
    r = c.post("/api/dashboards/ventas/widgets", json={"name": "x", "sites": [SITE]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "widgets_disabled"

    # Embedding on but share links off → refused too (FR-007).
    monkeypatch.setattr(get_settings(), "embed_widgets_enabled", True)
    set_mail(share_links_enabled=False)
    r = c.post("/api/dashboards/ventas/widgets", json={"name": "x", "sites": [SITE]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "sharing_disabled"

    set_mail(share_links_enabled=True)
    admin_client = signed_in(admin.email)
    assert admin_client.post("/api/dashboards/ventas/widgets",
                             json={"name": "x", "sites": [SITE]}).status_code == 201

    anon = client()
    assert anon.get("/api/dashboards/ventas/widgets").status_code == 401
    assert anon.post("/api/dashboards/ventas/widgets",
                     json={"name": "x", "sites": [SITE]}).status_code == 401

    user_id = sql("SELECT id FROM app_user WHERE email = :e", e=user.email)[0][0]
    dash_id = sql("SELECT id FROM dashboard WHERE code = 'ventas'")[0][0]
    sql("INSERT INTO dashboard_access (user_id, dashboard_id, granted_by) VALUES (:u, :d, :u)",
        u=user_id, d=dash_id)
    user_client = signed_in(user.email)
    assert user_client.get("/api/dashboards/ventas/widgets").status_code == 403
    assert user_client.post("/api/dashboards/ventas/widgets",
                            json={"name": "x", "sites": [SITE]}).status_code == 403


def test_not_shareable_dashboard_refused(applied, embed):
    sql("INSERT INTO dashboard (code, name, description, icon, status) "
        "VALUES ('otro', 'Otro', '', 'chart-line', 'available')")
    r = applied.post("/api/dashboards/otro/widgets", json={"name": "x", "sites": [SITE]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "widget_not_shareable"
    assert applied.post("/api/dashboards/nope/widgets",
                        json={"name": "x", "sites": [SITE]}).status_code == 404


def test_project_policy_forbids_widgets(applied, embed):
    _set_active_distributions(
        version(share={"allowed": False}).artifacts["distributions"])
    forget_active_version()
    r = applied.post("/api/dashboards/ventas/widgets", json={"name": "x", "sites": [SITE]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "widget_not_shareable"

    # And a widget created while the policy allowed sharing stops serving when it does not.
    _set_active_distributions(version().artifacts["distributions"])
    forget_active_version()
    widget = new_widget(applied)
    _set_active_distributions(
        version(share={"allowed": False}).artifacts["distributions"])
    forget_active_version()
    assert client().get(f"/api/widgets/{token_of(widget)}").status_code == 404


def test_key_once_hashed_and_audited(applied, embed):
    widget = new_widget(applied, name="  Ventas · cliente  ")
    key = token_of(widget)
    assert len(key) >= 43
    assert widget["name"] == "Ventas · cliente"
    assert widget["url"] == f"http://testserver/w/{key}"
    assert widget["url"] in widget["snippet"]
    assert "<iframe" in widget["snippet"] and "data-bizview-widget" in widget["snippet"]
    assert widget["state"] == "active" and widget["active"] is True
    assert widget["pdf"] is False
    assert widget["sites"] == [{"origin": SITE, "development": False}]
    assert widget["created_by"]["name"] == "Super Usuario"

    listing_url = "/api/dashboards/ventas/widgets"
    listing = applied.get(listing_url).json()
    assert listing["enabled"] is True
    assert listing["max_active"] == 50 and listing["active_count"] == 1
    assert listing["max_sites"] == 10
    assert "token" not in listing["items"][0]
    assert "snippet" not in listing["items"][0]
    assert "key" not in listing["items"][0]
    assert key not in applied.get(listing_url).text

    stored = bytes(sql("SELECT key_hash FROM dashboard_widget ORDER BY id DESC LIMIT 1")[0][0])
    assert stored == hashlib.sha256(key.encode()).digest()

    detail = sql("SELECT detail FROM audit_event WHERE kind = 'widget_created'")[0][0]
    if not isinstance(detail, dict):
        detail = json.loads(str(detail))
    assert detail["dashboard"] == "ventas"
    assert detail["sites"] == [SITE]
    assert key not in str(detail)

    # The activity trail is the admin's help screen: creator, dates, usage.
    items = applied.get(listing_url).json()["items"]
    assert items[0]["visits"] == 0 and items[0]["last_visit_at"] is None


def test_site_validation(applied, embed):
    url = "/api/dashboards/ventas/widgets"
    cases = [
        ({"name": "x", "sites": []}, 422),
        ({"name": "", "sites": [SITE]}, 422),
        ({"name": "a" * 81, "sites": [SITE]}, 422),
        ({"name": "x", "sites": ["www.cliente.com"]}, 422),           # no scheme
        ({"name": "x", "sites": ["ftp://www.cliente.com"]}, 422),     # not http(s)
        ({"name": "x", "sites": [SITE + "/ventas"]}, 422),            # a path
        ({"name": "x", "sites": [SITE + "?a=1"]}, 422),               # a query
        ({"name": "x", "sites": ["https://*.cliente.com"]}, 422),     # a wildcard
        ({"name": "x", "sites": ["*"]}, 422),
        ({"name": "x", "sites": ["https://user:pass@cliente.com"]}, 422),
        ({"name": "x", "sites": ["https://cliente.com:notaport"]}, 422),
        ({"name": "x", "sites": [SITE, SITE]}, 422),                  # repeated
        ({"name": "x", "sites": [f"https://s{i}.cliente.com" for i in range(11)]}, 422),
        ({"name": "x", "sites": [SITE], "expires_at": "2020-01-01T00:00:00Z"}, 422),
    ]
    for body, status in cases:
        r = applied.post(url, json=body)
        assert r.status_code == status, (body, r.text)
    assert sql("SELECT count(*) FROM dashboard_widget")[0][0] == 0

    # A local development address is accepted and marked (FR-020).
    widget = new_widget(applied, sites=["http://localhost:5173"])
    assert widget["sites"] == [{"origin": "http://localhost:5173", "development": True}]
    widget = new_widget(applied, sites=["https://192.168.1.40:8443"])
    assert widget["sites"][0]["development"] is True
    assert widget["sites"][0]["origin"] == "https://192.168.1.40:8443"
    widget = new_widget(applied, sites=["https://CLIENTE.com:443"])
    assert widget["sites"] == [{"origin": "https://cliente.com", "development": False}]


def test_fifty_active_and_counted_apart_from_share_links(applied, embed):
    links_url = "/api/dashboards/ventas/links"
    made = [new_widget(applied, name=f"w{i}") for i in range(50)]
    r = applied.post("/api/dashboards/ventas/widgets", json={"name": "51", "sites": [SITE]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "too_many_widgets"
    assert "50" in r.json()["error"]["message"]

    listing = applied.get("/api/dashboards/ventas/widgets").json()
    assert listing["active_count"] == 50

    # A revoked widget frees its place, an expired one too.
    assert applied.delete(f"/api/dashboards/ventas/widgets/{made[0]['id']}").status_code == 204
    assert applied.post("/api/dashboards/ventas/widgets",
                        json={"name": "extra", "sites": [SITE]}).status_code == 201
    sql("UPDATE dashboard_widget SET created_at = now() - interval '2 days', "
        "expires_at = now() - interval '1 second' WHERE id = :i", i=made[1]["id"])
    assert applied.post("/api/dashboards/ventas/widgets",
                        json={"name": "extra2", "sites": [SITE]}).status_code == 201
    assert applied.get("/api/dashboards/ventas/widgets").json()["active_count"] == 50

    # The 20-link limit of feature 018 is exactly where it was.
    for _ in range(20):
        assert applied.post(links_url, json={"days": 7}).status_code == 201
    r = applied.post(links_url, json={"days": 7})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "too_many_links"


# ---------------------------------------------------------------------------------- the door

def test_public_view_matches_the_signed_in_reader(applied, embed):
    widget = new_widget(applied)
    key = token_of(widget)
    pub = client()
    base = f"/api/widgets/{key}"

    r = pub.get(base)
    assert r.status_code == 200, r.text
    body = r.json()
    # Defect 3: the page gets no site list and no internal name, only (at most) the origin that
    # framed it. Nothing in the answer may disclose either listed domain.
    assert "frame_origins" not in body["widget"] and "name" not in body["widget"]
    assert body["widget"]["parent_origin"] is None          # no ?parent= asked
    assert "www.cliente.com" not in r.text and "localhost:5173" not in r.text
    assert body["widget"]["preview"] is False
    assert body["widget"]["show_title"] is True and body["widget"]["show_filters"] is True
    assert body["dashboard"]["code"] == "ventas"
    assert body["report"]["title"]
    assert body["report"]["ai_narrative"] is False
    for header, value in PUBLIC_HEADERS.items():
        assert r.headers.get(header) == value
    assert "set-cookie" not in {k.lower() for k in r.headers}

    signed = applied.get("/api/reports/ventas/data?" + SELECTION).json()
    data = pub.get(base + "/data?" + SELECTION)
    assert data.status_code == 200, data.text
    assert data.json()["selection"] == signed["selection"]
    assert data.json()["views"] == signed["views"]
    etag = data.headers.get("ETag")
    assert etag
    assert pub.get(base + "/data?" + SELECTION,
                   headers={"If-None-Match": etag}).status_code == 304

    filtered = pub.get(base + "/data?" + SELECTION + "&filter.product=P1").json()
    assert filtered["views"][0]["items"][0]["value"] == 7.5
    options = pub.get(base + "/filters/product?" + SELECTION)
    assert options.status_code == 200
    assert options.json()["items"] == ["P1", "P2"]
    assert pub.get(base + "/filters/unknown?" + SELECTION).status_code == 404

    # The widget is read-only: nothing about it answers a write.
    assert pub.post(base + "/data").status_code == 405
    assert pub.delete(base).status_code == 405

    # The usage figures are the document loads, not every data refresh.
    pub.get(base)
    pub.get(base + "/data?" + SELECTION)
    listed = applied.get("/api/dashboards/ventas/widgets").json()["items"][0]
    assert listed["visits"] == 2
    assert listed["last_visit_at"] is not None


def test_admin_cookie_gets_the_anonymous_view(applied, embed):
    widget = new_widget(applied)
    key = token_of(widget)
    base = f"/api/widgets/{key}"

    anon = client()
    admin_session = applied  # signed in as root@example.com, cookie carries the session
    anonymous = anon.get(base).json()
    with_cookie = admin_session.get(base)
    assert with_cookie.status_code == 200
    assert with_cookie.json() == anonymous
    assert "set-cookie" not in {k.lower() for k in with_cookie.headers}

    data_anon = anon.get(base + "/data?" + SELECTION).json()
    data_cookie = admin_session.get(base + "/data?" + SELECTION).json()
    assert data_cookie == data_anon

    # The widget offers no route into the rest of the product: only its own paths exist, and a
    # token cannot be walked out of (`..` is normalised by the client, so a cookieless visitor
    # still lands on a product route that refuses them).
    for path in (f"{base}/version", f"{base}/narrative", f"{base}/assets/x/y"):
        assert admin_session.get(path).status_code != 200
    assert anon.get(f"{base}/../../reports/ventas").status_code in (401, 403, 404)
    assert admin_session.get("/api/reports/ventas").status_code == 200  # the product still works


def test_public_definition_confirms_one_parent_and_never_lists_the_sites(applied, embed):
    """Defect 3: one widget may serve two customers' sites; neither may learn the other's.

    The page needs a single origin to post its height to, so it asks about the origin that framed it
    (from `document.referrer`) and the answer is that origin or nothing — never the list.
    """
    widget = new_widget(applied, sites=[SITE, "https://otro-cliente.com"])
    key = widget["key"]
    pub = client()
    base = f"/api/widgets/{key}"

    def ask(parent: str | None) -> dict:
        url = base if parent is None else f"{base}?parent={quote(parent, safe='')}"
        response = pub.get(url)
        assert response.status_code == 200, response.text
        return response.json()["widget"]

    assert ask(None)["parent_origin"] is None
    assert ask(SITE)["parent_origin"] == SITE
    # The other customer's site is allowed too, but a viewer of one page learns only their own.
    assert ask("https://otro-cliente.com")["parent_origin"] == "https://otro-cliente.com"
    # Not on the list, malformed, or a full page URL: no confirmation, and never a 422.
    assert ask("https://intruso.com")["parent_origin"] is None
    assert ask("https://www.cliente.com.otro.com")["parent_origin"] is None
    assert ask("no es una url")["parent_origin"] is None
    assert ask("ftp://www.cliente.com")["parent_origin"] is None
    assert ask("https://WWW.CLIENTE.COM:443")["parent_origin"] == SITE   # canonical origins
    assert ask("https://www.cliente.com/pagina?x=1#y")["parent_origin"] is None

    # Only the one confirmed origin travels; the list, and the other customer's domain, never do.
    assert "otro-cliente.com" not in pub.get(f"{base}?parent={quote(SITE, safe='')}").text
    anonymous = pub.get(base).text
    assert "cliente.com" not in anonymous and "otro-cliente.com" not in anonymous

    # The admin's own list still shows everything (that door is administrator-only).
    items = applied.get("/api/dashboards/ventas/widgets").json()["items"]
    assert {site["origin"] for site in items[0]["sites"]} == {SITE, "https://otro-cliente.com"}


def test_preview_confirms_the_installation_origin_for_its_own_test_page(applied, embed):
    """The admin's test page is same-origin: that one origin is confirmed for a preview ticket."""
    widget = new_widget(applied, sites=["http://localhost:5173"])
    r = applied.post(f"/api/dashboards/ventas/widgets/{widget['id']}/frame")
    assert r.status_code == 200, r.text
    ticket = r.json()["url"].rsplit("/w/", 1)[1]
    pub = client()
    base = f"/api/widgets/{ticket}"

    installation = "http://testserver"   # what the request's base_url is in the suite
    widget_payload = pub.get(f"{base}?parent={quote(installation, safe='')}").json()["widget"]
    assert widget_payload["preview"] is True
    assert widget_payload["parent_origin"] == installation
    assert pub.get(f"{base}?parent={quote('https://intruso.com', safe='')}").json()[
        "widget"]["parent_origin"] is None
    # A real key does not confirm the installation's own origin (only a preview does).
    real = new_widget(applied, name="Real")
    assert pub.get(f"/api/widgets/{real['key']}?parent={quote(installation, safe='')}").json()[
        "widget"]["parent_origin"] is None


def test_pdf_commits_the_ceiling_before_it_renders(applied, embed, monkeypatch):
    """Defect 1: a slow PDF must not hold the widget's row while every other viewer waits.

    The check reads the counter from a second connection *while the render is still running*: it has
    to see the request already counted. With the counter left inside the PDF's transactional
    session, this read sees the previous value and every other request for the widget waits on the
    locked row.
    """
    widget = new_widget(applied, name="Con PDF", pdf=True)
    base = f"/api/widgets/{widget['key']}"
    pub = client()

    seen: dict[str, object] = {}
    real_render = report_pdf.render

    def slow_render(*args, **kwargs):
        # Another connection, while this request is still inside the render.
        seen["count"] = sql("SELECT rate_count FROM dashboard_widget WHERE id = :i",
                            i=widget["id"])[0][0]
        return real_render(*args, **kwargs)

    monkeypatch.setattr(report_pdf, "render", slow_render)
    response = pub.post(f"{base}/pdf?{SELECTION}")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert seen["count"] == 1, (
        "the ceiling's count must be committed before the PDF renders, or the widget's row "
        "stays locked until it finishes")
    # And the count is still there afterwards, for the next request in this window.
    assert sql("SELECT rate_count FROM dashboard_widget WHERE id = :i",
               i=widget["id"])[0][0] == 1


def test_images_do_not_spend_the_ceiling(applied, embed, monkeypatch):
    """Defect 2: a dashboard with many image tiles must not exhaust the ceiling by itself.

    Measured on the layout report, the one in the fixture with image tiles: its page renders the
    cards and the two tables that carry pictures, 4 + 25 + 25 images in one view. The test loads the
    page the way a browser does — definition, data, then one request per image tile — and compares
    the counter with images excluded against the old behaviour (forced back on by patching
    `_widget_access`), so the two numbers come from the same request profile.
    """
    import io

    from PIL import Image as Pillow
    from sqlalchemy import select

    from app.db import get_sessionmaker
    from app.models import Project
    from app.projects import fs as project_fs
    from tests.conftest import make_project

    buffer = io.BytesIO()
    Pillow.new("RGB", (8, 8), (30, 60, 90)).save(buffer, format="PNG")
    png = buffer.getvalue()

    # The workspace fixture has no project, and a folder asset needs one to resolve; give the layout
    # report a project with the two pictures its rows name, so the tiles are real 200s.
    slug = make_project("Con imágenes")
    with get_sessionmaker()() as session:
        project = session.scalar(select(Project).where(Project.slug == slug))
        project_fs.apply_asset(project.id, "assets/productos/Alimento_premium.png", png,
                              {"kind": "user", "user_id": None, "session_id": None,
                               "command": "edit"})
        project_fs.apply_asset(project.id, "assets/productos/Vacuna_triple.png", png,
                              {"kind": "user", "user_id": None, "session_id": None,
                               "command": "edit"})
    sql("UPDATE workspace_version SET artifacts = jsonb_set(artifacts::jsonb, "
        "'{reports,ventas-layout,project}', to_jsonb(CAST(:slug AS text))) WHERE state = 'active'",
        slug=slug)
    forget_active_version()

    layout = applied.get("/api/reports/ventas-layout").json()
    sets = layout["images"]
    # Every picture tile of the page: one request each, through the set's own door. The card and the
    # detail table read a project folder (assets); the catalogue reads a cached URL column (images).
    asset_tiles = cached_tiles = 0
    for component in layout["layout"]["web"]["components"]:
        spec = sets.get(component.get("image") or "")
        if not spec:
            continue
        tiles = component.get("page_size") or component.get("limit") or 0
        if spec.get("column"):
            cached_tiles += tiles
        else:
            asset_tiles += tiles
    assert (asset_tiles, cached_tiles) == (29, 25), (asset_tiles, cached_tiles)
    tiles = asset_tiles + cached_tiles

    def page_view(key: str) -> None:
        base = f"/api/widgets/{key}"
        public = client()
        definition = public.get(base)
        assert definition.status_code == 200, definition.text
        assert definition.json()["report"]["images"]["productos"]["url"] == \
            f"{base}/assets/productos/"
        assert public.get(f"{base}/data?{SELECTION}").status_code == 200
        for tile in range(asset_tiles):
            name = "Alimento_premium" if tile % 2 == 0 else "Vacuna_triple"
            response = public.get(f"{base}/assets/productos/{name}")
            assert response.status_code == 200, (name, response.text)
        for _ in range(cached_tiles):
            # Nothing is cached for this fixture's URL column; the browser makes the request all the
            # same, which is exactly what used to spend the ceiling.
            assert public.get(f"{base}/images/{'0' * 64}.png").status_code == 404

    def count(widget_id: int) -> int:
        return sql("SELECT rate_count FROM dashboard_widget WHERE id = :i", i=widget_id)[0][0]

    def new_layout_widget(name: str) -> dict:
        response = applied.post("/api/dashboards/ventas-layout/widgets",
                                json={"name": name, "sites": [SITE]})
        assert response.status_code == 201, response.text
        return response.json()

    # The ceiling is charged by `check_rate`; its call count is the exact measure of what one page
    # view spends (a rate window can roll between two requests, so the stored counter alone can read
    # 1 instead of 2 at a minute boundary).
    calls = {"rate": 0}
    real_rate = widgets.check_rate

    def counting_rate(db, widget):
        calls["rate"] += 1
        return real_rate(db, widget)

    monkeypatch.setattr(widgets, "check_rate", counting_rate)

    after = new_layout_widget("Con imágenes")
    page_view(after["key"])
    assert calls["rate"] == 2, (
        f"2 of the {2 + tiles} requests spend the ceiling; the {tiles} pictures do not")
    assert count(after["id"]) >= 1, "the two report requests are counted in the database"
    print(f"page view: 2 report requests + {tiles} image requests ({asset_tiles} assets, "
          f"{cached_tiles} cached); ceiling calls: {calls['rate']}")
    print(f"before the change: {2 + tiles} requests of the ceiling per page view (the profile's "
          f"{2 + tiles} requests, of which {tiles} are pictures)")


def test_images_keep_the_address_limits_and_the_validity_checks(applied, embed, monkeypatch):
    """Excluding images from the ceiling does not open the door: the limits and checks stay."""
    from app.security import throttle

    widget = new_widget(applied, name="Imágenes")
    url = f"/api/widgets/{widget['key']}/images/does-not-exist"
    pub = client()

    # A revoked widget serves no image either (the neutral answer, not a file).
    assert applied.delete(f"/api/dashboards/ventas/widgets/{widget['id']}").status_code == 204
    assert pub.get(url).status_code == 404

    live = new_widget(applied, name="Imágenes 2")
    url = f"/api/widgets/{live['key']}/images/does-not-exist"
    monkeypatch.setattr(throttle, "PUBLIC_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(throttle, "_public_hits", {})
    capped = client_from("203.0.113.93")
    assert capped.get(url).status_code == 404      # a missing file, not a rate answer
    assert capped.get(url).status_code == 404
    limited = capped.get(url)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"


def test_null_control_is_a_validation_error(applied, embed):
    """Defect 4: an explicit null on a NOT NULL control is a 422 naming the field, not a 500."""
    from sqlalchemy import update as sa_update
    from sqlalchemy.exc import IntegrityError

    from app.db import get_sessionmaker
    from app.models import DashboardWidget

    widget = new_widget(applied, name="Controles")
    url = f"/api/dashboards/ventas/widgets/{widget['id']}"
    for field in ("show_title", "show_filters", "pdf"):
        response = applied.patch(url, json={field: None})
        assert response.status_code == 422, (field, response.text)
        assert response.json()["error"]["code"] == "validation_error"
        assert response.json()["error"]["fields"] == {field: "required"}
        # Nothing was written.
        row = sql("SELECT show_title, show_filters, pdf_enabled FROM dashboard_widget "
                  "WHERE id = :i", i=widget["id"])[0]
        assert tuple(row) == (True, True, False)

    # The database is what used to answer: the columns are NOT NULL.
    with pytest.raises(IntegrityError):
        with get_sessionmaker().begin() as db:
            db.execute(sa_update(DashboardWidget).where(DashboardWidget.id == widget["id"])
                       .values(pdf_enabled=None))

    # Null keeps its meaning where the column allows it: theme and language follow the visitor,
    # and expires_at clears the date.
    ok = applied.patch(url, json={"theme": None, "language": None, "expires_at": None})
    assert ok.status_code == 200, ok.text
    assert ok.json()["theme"] is None and ok.json()["language"] is None
    assert ok.json()["expires_at"] is None


def test_frame_decision_lists_only_the_widgets_sites(applied, embed):
    widget = new_widget(applied, sites=[SITE, "http://localhost:5173"])
    key = token_of(widget)

    r = client().get(f"/api/widgets/frame/{key}")
    assert r.status_code == 200
    allowed = frame_ancestors(r.headers["Content-Security-Policy"])
    assert allowed == f"{SITE} http://localhost:5173"
    assert "x-frame-options" not in {k.lower() for k in r.headers}
    for header, value in PUBLIC_HEADERS.items():
        assert r.headers.get(header) == value

    # An unknown key may be framed by nobody — the failure mode is closed.
    unknown = client().get("/api/widgets/frame/" + "z" * 43)
    assert unknown.status_code == 200
    assert frame_ancestors(unknown.headers["Content-Security-Policy"]) == "'none'"
    assert frame_ancestors(client().get("/api/widgets/frame/_")
                           .headers["Content-Security-Policy"]) == "'none'"

    # Removing a site stops that site only (FR-022/US3-4).
    r = applied.patch(f"/api/dashboards/ventas/widgets/{widget['id']}",
                      json={"sites": [SITE]})
    assert r.status_code == 200, r.text
    allowed = frame_ancestors(client().get(f"/api/widgets/frame/{key}")
                              .headers["Content-Security-Policy"])
    assert allowed == SITE

    # Replacing the key: the old snippet is refused by everyone, the new one by its sites.
    replaced = applied.post(f"/api/dashboards/ventas/widgets/{widget['id']}/replace")
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["snippet"] != widget["snippet"]
    assert frame_ancestors(client().get(f"/api/widgets/frame/{key}")
                           .headers["Content-Security-Policy"]) == "'none'"
    new_key = replaced.json()["key"]
    assert frame_ancestors(client().get(f"/api/widgets/frame/{new_key}")
                           .headers["Content-Security-Policy"]) == SITE

    # Revoked: no data, but its sites may still frame the neutral message (FR-013).
    assert applied.delete(f"/api/dashboards/ventas/widgets/{widget['id']}").status_code == 204
    assert client().get(f"/api/widgets/{new_key}").status_code == 404
    assert frame_ancestors(client().get(f"/api/widgets/frame/{new_key}")
                           .headers["Content-Security-Policy"]) == SITE


def test_csp_matches_the_edge_default():
    """The edge's default policy and the widget policy differ only in frame-ancestors (R2)."""
    caddy = CADDYFILE.read_text()
    assert widgets.csp_for(["'none'"]) in caddy, (
        "the widget CSP and the Caddyfile default disagree; update both")
    # Every route but /w/* keeps the refusal.
    assert '@not_widget not path /w/*' in caddy
    assert caddy.index("handle_path /w/*") > caddy.index("@not_widget")


def test_unavailable_states_look_identical(applied, embed, monkeypatch):
    widget = new_widget(applied)
    key = token_of(widget)
    pub = client()
    unknown = pub.get("/api/widgets/" + "x" * 43)
    assert unknown.status_code == 404
    assert unknown.json()["error"]["message"] == str(widgets.UNAVAILABLE)
    malformed = pub.get("/api/widgets/abc")
    assert malformed.json() == unknown.json()
    for header, value in PUBLIC_HEADERS.items():
        assert unknown.headers.get(header) == value

    def same(path: str) -> None:
        resp = pub.get(path)
        assert resp.status_code == 404, (path, resp.text)
        assert resp.json() == unknown.json(), path
        for header, value in PUBLIC_HEADERS.items():
            assert resp.headers.get(header) == value

    # Revoked.
    assert applied.delete(f"/api/dashboards/ventas/widgets/{widget['id']}").status_code == 204
    same(f"/api/widgets/{key}")
    same(f"/api/widgets/{key}/data?{SELECTION}")
    assert pub.post(f"/api/widgets/{key}/pdf?{SELECTION}").status_code == 404

    # Expired (a fresh widget whose date passed).
    second = new_widget(applied, name="Vence")
    sql("UPDATE dashboard_widget SET created_at = now() - interval '2 days', "
        "expires_at = now() - interval '1 second' WHERE id = :i", i=second["id"])
    same(f"/api/widgets/{second['key']}")
    assert frame_ancestors(pub.get(f"/api/widgets/frame/{second['key']}")
                           .headers["Content-Security-Policy"]) == SITE

    # Replaced.
    third = new_widget(applied, name="Rota")
    old = third["key"]
    assert applied.post(f"/api/dashboards/ventas/widgets/{third['id']}/replace").status_code == 200
    same(f"/api/widgets/{old}")

    # Share links switched off: the widget door closes with them (FR-007).
    fourth = new_widget(applied, name="Enlaces")
    set_mail(share_links_enabled=False)
    same(f"/api/widgets/{fourth['key']}")
    set_mail(share_links_enabled=True)
    assert pub.get(f"/api/widgets/{fourth['key']}").status_code == 200

    # Embedding switched off.
    set_mail(share_links_enabled=True)
    monkeypatch.setattr(get_settings(), "embed_widgets_enabled", False)
    same(f"/api/widgets/{fourth['key']}")
    monkeypatch.setattr(get_settings(), "embed_widgets_enabled", True)

    # The dashboard is withdrawn.
    sql("UPDATE dashboard SET status = 'hidden' WHERE code = 'ventas'")
    same(f"/api/widgets/{fourth['key']}")
    sql("UPDATE dashboard SET status = 'available' WHERE code = 'ventas'")
    assert pub.get(f"/api/widgets/{fourth['key']}").status_code == 200


def test_widget_never_mixes_with_share_link_doors(applied, embed):
    widget = new_widget(applied)
    key = token_of(widget)
    link = applied.post("/api/dashboards/ventas/links", json={"days": 7}).json()
    pub = client()
    # A share-link token is not a widget key and vice versa.
    assert pub.get(f"/api/widgets/{link['token']}").status_code == 404
    assert pub.get(f"/api/shared/{key}").status_code == 404
    assert str(LINK_UNAVAILABLE) != str(widgets.UNAVAILABLE)


# ------------------------------------------------------------------------------- controls

def test_pdf_off_by_default_and_refused_when_off(applied, embed):
    widget = new_widget(applied)
    base = f"/api/widgets/{widget['key']}"
    pub = client()
    assert pub.get(base).json()["report"]["pdf"] is False
    assert pub.get(base).json()["widget"]["pdf"] is False
    resp = pub.post(base + "/pdf?" + SELECTION)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"

    on = new_widget(applied, name="Con PDF", pdf=True)
    definition = pub.get(f"/api/widgets/{on['key']}").json()
    assert definition["report"]["pdf"] is True and definition["widget"]["pdf"] is True
    pdf = pub.post(f"/api/widgets/{on['key']}/pdf?" + SELECTION)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_filters_off_cannot_be_reached_by_the_address(applied, embed):
    widget = new_widget(applied, name="Sin filtros", show_filters=False)
    base = f"/api/widgets/{widget['key']}"
    pub = client()
    assert pub.get(base).json()["widget"]["show_filters"] is False

    plain = pub.get(base + "/data?" + SELECTION).json()
    tampered = pub.get(base + "/data?" + SELECTION + "&filter.product=P1").json()
    assert tampered["selection"] == plain["selection"]
    assert tampered["views"] == plain["views"]
    other_period = pub.get(base + "/data?period=last_7_days").json()
    assert other_period["selection"] == plain["selection"]

    # With the controls on, the same address does change the payload (filters are a convenience).
    on = new_widget(applied, name="Con filtros")
    plain = pub.get(f"/api/widgets/{on['key']}/data?" + SELECTION).json()
    filtered = pub.get(f"/api/widgets/{on['key']}/data?" + SELECTION + "&filter.product=P1").json()
    assert filtered["views"][0]["items"][0]["value"] == 7.5
    assert plain["views"][0]["items"][0]["value"] != 7.5


def test_widget_theme_language_and_title(applied, embed):
    widget = new_widget(applied, theme="dark", language="en", show_title=False)
    body = client().get(f"/api/widgets/{widget['key']}").json()
    assert body["widget"]["theme"] == "dark"
    assert body["widget"]["language"] == "en"
    assert body["widget"]["show_title"] is False

    r = applied.patch(f"/api/dashboards/ventas/widgets/{widget['id']}",
                      json={"theme": None, "language": "es", "show_filters": False})
    assert r.status_code == 200, r.text
    body = client().get(f"/api/widgets/{widget['key']}").json()
    assert body["widget"]["theme"] is None
    assert body["widget"]["language"] == "es"
    assert body["widget"]["show_filters"] is False

    # Only the accepted vocabularies.
    assert applied.patch(f"/api/dashboards/ventas/widgets/{widget['id']}",
                         json={"theme": "sepia"}).status_code == 422


# -------------------------------------------------------------------------------- the ceiling

def test_per_widget_ceiling_answers_retry(applied, embed, monkeypatch):
    first = new_widget(applied, name="Uno")
    second = new_widget(applied, name="Dos")
    monkeypatch.setattr(get_settings(), "widget_rate_limit", 3)
    pub = client_from("203.0.113.90")
    base = f"/api/widgets/{first['key']}"
    assert pub.get(base).status_code == 200
    assert pub.get(base + "/data?" + SELECTION).status_code == 200
    assert pub.get(base + "/filters/product?" + SELECTION).status_code == 200
    limited = pub.get(base)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    retry = limited.json()["error"]["retry_after_seconds"]
    assert 0 < retry <= 60
    assert pub.get(base + "/data?" + SELECTION).status_code == 429

    # Another widget, another ceiling.
    assert pub.get(f"/api/widgets/{second['key']}").status_code == 200

    # The document decision never fails: the host page renders the neutral message, not a broken
    # navigation.
    assert pub.get(f"/api/widgets/frame/{first['key']}").status_code == 200

    # The signed-in readers of the installation are untouched (SC-009).
    assert applied.get("/api/reports/ventas/data?" + SELECTION).status_code == 200

    # The next minute starts a new window.
    sql("UPDATE dashboard_widget SET rate_window_start = now() - interval '1 minute' "
        "WHERE id = :i", i=first["id"])
    assert pub.get(base).status_code == 200


def test_address_limits_still_apply(applied, embed, monkeypatch):
    from app.security import throttle

    new_widget(applied)
    monkeypatch.setattr(throttle, "PUBLIC_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(throttle, "_public_hits", {})
    capped = client_from("203.0.113.91")
    widget = new_widget(applied, name="Tope")
    assert capped.get(f"/api/widgets/{widget['key']}").status_code == 200
    assert capped.get(f"/api/widgets/{widget['key']}").status_code == 200
    assert capped.get(f"/api/widgets/{widget['key']}").status_code == 429
    assert client_from("203.0.113.92").get(f"/api/widgets/{widget['key']}").status_code == 200


# --------------------------------------------------------------------------------- the preview

def test_preview_test_page_needs_no_external_site(applied, embed):
    # Only a local address: the test page must still work (FR-019).
    widget = new_widget(applied, sites=["http://localhost:5173"])
    r = applied.post(f"/api/dashboards/ventas/widgets/{widget['id']}/frame")
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert "/w/pv." in url
    ticket = url.rsplit("/w/", 1)[1]
    assert "." in ticket and ticket.startswith("pv.")
    listing = applied.get("/api/dashboards/ventas/widgets").json()["items"]
    assert any(item["id"] == widget["id"] for item in listing)

    pub = client()
    body = pub.get(f"/api/widgets/{ticket}")
    assert body.status_code == 200, body.text
    assert body.json()["widget"]["preview"] is True
    assert pub.get(f"/api/widgets/{ticket}/data?" + SELECTION).status_code == 200

    # Framed by the product's own page, and only same-origin (FR-018).
    allowed = frame_ancestors(pub.get(f"/api/widgets/frame/{ticket}")
                              .headers["Content-Security-Policy"])
    assert allowed == "'self' http://localhost:5173"

    # The test page does not count towards the usage figures (FR-019).
    listed = applied.get("/api/dashboards/ventas/widgets").json()["items"][0]
    assert listed["visits"] == 0 and listed["last_visit_at"] is None

    # A tampered ticket serves nothing.
    bad = ticket[:-1] + ("A" if ticket[-1] != "A" else "B")
    assert pub.get(f"/api/widgets/{bad}").status_code == 404
    assert frame_ancestors(pub.get(f"/api/widgets/frame/{bad}")
                           .headers["Content-Security-Policy"]) == "'none'"

    # A ticket cannot outlive its window.
    expired, _ = widgets.preview_ticket(widget["id"], minutes=-1)
    assert pub.get(f"/api/widgets/{expired}").status_code == 404

    # A revoked widget has no test page either.
    assert applied.delete(f"/api/dashboards/ventas/widgets/{widget['id']}").status_code == 204
    assert applied.post(f"/api/dashboards/ventas/widgets/{widget['id']}/frame").status_code == 404
    assert pub.get(f"/api/widgets/{ticket}").status_code == 404

    # Only admins may mint one.
    nobody = client()
    assert nobody.post(f"/api/dashboards/ventas/widgets/{widget['id']}/frame").status_code == 401


# --------------------------------------------------------------------------------- management

def test_manage_list_edit_replace_revoke_audited(applied, embed):
    widget = new_widget(applied, name="Marca", sites=[SITE])
    url = f"/api/dashboards/ventas/widgets/{widget['id']}"

    r = applied.patch(url, json={"name": "Marca 2026", "sites": [SITE, "https://blog.cliente.com"]})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Marca 2026"
    assert [s["origin"] for s in r.json()["sites"]] == [SITE, "https://blog.cliente.com"]

    # The key, the sites and the history survive a replacement (FR-022).
    pub = client()
    pub.get(f"/api/widgets/{widget['key']}")
    replaced = applied.post(url + "/replace").json()
    assert replaced["id"] == widget["id"]
    assert replaced["name"] == "Marca 2026"
    assert [s["origin"] for s in replaced["sites"]] == [SITE, "https://blog.cliente.com"]
    assert pub.get(f"/api/widgets/{replaced['key']}").status_code == 200

    assert applied.delete(url).status_code == 204
    assert applied.delete(url).status_code == 204   # idempotent
    assert applied.patch(url, json={"name": "No"}).status_code == 409
    assert applied.post(url + "/replace").status_code == 409
    assert pub.get(f"/api/widgets/{replaced['key']}").status_code == 404

    kinds = [row[0] for row in sql(
        "SELECT kind FROM audit_event WHERE kind LIKE 'widget%' ORDER BY id")]
    assert kinds == ["widget_created", "widget_updated", "widget_key_replaced", "widget_revoked"]
    for row in sql("SELECT detail::text FROM audit_event WHERE kind LIKE 'widget%'"):
        assert widget["key"] not in row[0] and replaced["key"] not in row[0]

    # One dashboard's widget cannot be managed from another dashboard.
    sql("INSERT INTO dashboard (code, name, description, icon, status) "
        "VALUES ('otro', 'Otro', '', 'chart-line', 'available')")
    other = new_widget(applied, name="Otro")
    assert applied.delete(f"/api/dashboards/otro/widgets/{other['id']}").status_code == 404


def test_admin_networks_cover_widgets(applied, embed, monkeypatch):
    """FR-018 of 004: a stolen admin session outside the allowed networks cannot mint a widget."""
    monkeypatch.setattr(get_settings(), "admin_allowed_networks", "10.0.0.0/8")
    outside = client_from("198.51.100.60")
    assert outside.post("/api/auth/login", json={"email": "root@example.com",
                                                 "password": PASSWORD}).status_code == 200
    r = outside.post("/api/dashboards/ventas/widgets", json={"name": "x", "sites": [SITE]})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "address_not_allowed"
    assert sql("SELECT count(*) FROM dashboard_widget")[0][0] == 0
    # Reading the controls is not a state change.
    assert outside.get("/api/dashboards/ventas/widgets").status_code == 200
    inside = client_from("10.1.2.3")
    assert inside.post("/api/auth/login", json={"email": "root@example.com",
                                                "password": PASSWORD}).status_code == 200
    assert inside.post("/api/dashboards/ventas/widgets",
                       json={"name": "x", "sites": [SITE]}).status_code == 201
