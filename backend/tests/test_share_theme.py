"""Share link theme (feature 030, T047): the optional first-load theme of a public link."""

from tests.conftest import client, set_mail, sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture


def new_link(c, **body) -> dict:
    set_mail(share_links_enabled=True)
    r = c.post("/api/dashboards/ventas/links", json={"days": 7, **body})
    assert r.status_code == 201, r.text
    return r.json()


def test_link_without_theme_follows_the_viewer(applied):
    link = new_link(applied)
    assert link["theme"] is None
    assert sql("SELECT theme FROM share_link") == [(None,)]

    r = client().get(f"/api/shared/{link['token']}")
    assert r.status_code == 200, r.text
    assert r.json()["theme"] is None
    assert r.json()["dashboard"]["code"] == "ventas"


def test_link_theme_is_stored_listed_and_served(applied):
    link = new_link(applied, note="Cliente norte", theme="dark")
    assert link["theme"] == "dark"
    assert sql("SELECT theme FROM share_link") == [("dark",)]

    listing = applied.get("/api/dashboards/ventas/links").json()["items"][0]
    assert listing["theme"] == "dark"

    r = client().get(f"/api/shared/{link['token']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["theme"] == "dark"
    assert body["report"]["ai_narrative"] is False


def test_light_theme_round_trips(applied):
    link = new_link(applied, theme="light")
    assert link["theme"] == "light"
    assert client().get(f"/api/shared/{link['token']}").json()["theme"] == "light"


def test_unknown_theme_is_422_and_creates_nothing(applied):
    set_mail(share_links_enabled=True)
    r = applied.post("/api/dashboards/ventas/links", json={"days": 7, "theme": "sepia"})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["fields"] == {"theme": "literal_error"}
    assert sql("SELECT count(*) FROM share_link") == [(0,)]
