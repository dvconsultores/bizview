"""Feature 038: an apply replaces the project preview, and a preview that lost its schemas says so.

The production defect of 2026-10-26: `apply` dropped the preview schemas but left the state at
`succeeded`, so the page kept the «Vista previa» links and pressing one answered the generic 500.
"""
import pytest

from app.assistant import preview
from app.config import get_settings
from tests.coinmarketcap_fixture import (
    create_project,
    crypto_origin_data,
    fixture_files,
    project_id,
    put_files,
    run_preview,
    validate_project,
)
from tests.conftest import reauth, signed_in, sql
from tests.test_runner import pg_source as pg_source


@pytest.fixture(autouse=True)
def projects_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))


@pytest.fixture
def crypto_origin(pg_source):
    with crypto_origin_data():
        yield


# --- Preview after apply ----------------------------------------------------------------------

def test_apply_replaces_the_preview_and_the_links_stop_answering(db, superuser, crypto_origin):
    c = reauth(signed_in("root@example.com"))
    slug = create_project(c)
    put_files(c, slug, fixture_files())
    assert validate_project(c, slug)["validation"]["valid"] is True
    run_preview(c, slug)

    applied = c.post(f"/api/projects/{slug}/apply")
    assert applied.status_code == 200, applied.text
    version = applied.json()["version"]["id"]
    state = sql("SELECT preview FROM project WHERE id = :p", p=project_id(slug))[0][0]
    assert state["status"] == "replaced" and state["version"] == version

    # The page no longer offers the preview; a stale tab that asks for it gets a typed 409.
    answer = c.get(f"/api/projects/{slug}/preview/report/panorama-cripto/data")
    assert answer.status_code == 409, answer.text
    error = answer.json()["error"]
    assert error["code"] == "preview_expired"
    assert str(version) in error["message"]
    assert c.get(f"/api/projects/{slug}/preview/report/panorama-cripto").json()["error"][
        "code"] == "preview_expired"


def test_a_preview_whose_schemas_went_away_expires_instead_of_failing(db, superuser, crypto_origin):
    c = reauth(signed_in("root@example.com"))
    slug = create_project(c)
    put_files(c, slug, fixture_files())
    assert validate_project(c, slug)["validation"]["valid"] is True
    run_preview(c, slug)
    session_id = sql("SELECT preview FROM project WHERE id = :p", p=project_id(slug))[0][0]
    preview.drop_for_session(session_id["session_id"])

    answer = c.get(f"/api/projects/{slug}/preview/report/panorama-cripto/data")
    assert answer.status_code == 409, answer.text
    assert answer.json()["error"]["code"] == "preview_expired"
    # The read retires the preview, so the page stops offering a link that cannot work.
    state = sql("SELECT preview FROM project WHERE id = :p", p=project_id(slug))[0][0]
    assert state["status"] == "expired"
