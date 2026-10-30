"""Feature 044: the asset route — bytes, ETag, 304, and the same scope rules as the file route."""
import pytest

from app.config import get_settings
from app.models import AppUser
from app.projects import fs
from app.projects import service as project_service
from tests.conftest import signed_in

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    return tmp_path / "projects"


@pytest.fixture
def project(db, superuser):
    p = project_service.create(db, db.get(AppUser, superuser.id), "Con logos")
    db.commit()
    fs.apply_asset(p.id, "assets/coins/BTC.png", PNG,
                   {"kind": "user", "user_id": superuser.id, "session_id": None,
                    "command": "edit"})
    return p


def test_the_route_serves_the_bytes_with_an_etag(project):
    c = signed_in("root@example.com")
    r = c.get(f"/api/projects/{project.slug}/assets/coins/BTC.png")
    assert r.status_code == 200, r.text
    assert r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["etag"].startswith('"') and len(r.headers["etag"]) == 66
    assert "immutable" in r.headers["cache-control"] and "private" in r.headers["cache-control"]

    again = c.get(f"/api/projects/{project.slug}/assets/coins/BTC.png",
                  headers={"If-None-Match": r.headers["etag"]})
    assert again.status_code == 304 and again.content == b""


def test_a_missing_image_is_a_404_and_an_escape_is_a_422(project):
    c = signed_in("root@example.com")
    assert c.get(f"/api/projects/{project.slug}/assets/coins/NOPE.png").status_code == 404
    # A plain `../` is normalised away by the HTTP layer (and answers 404); the encoded form is the
    # one that actually reaches the handler, so that is the escape worth asserting.
    outside = c.get(f"/api/projects/{project.slug}/assets/%2e%2e/otro/a.png")
    assert outside.status_code == 422, outside.text
    assert outside.json()["error"]["code"] in ("path_unsafe", "path_outside_project")
    assert c.get(f"/api/projects/{project.slug}/assets/../otro/a.png").status_code == 404


def test_the_route_needs_the_super_user(project, user):
    c = signed_in(user.email)
    assert c.get(f"/api/projects/{project.slug}/assets/coins/BTC.png").status_code == 403
