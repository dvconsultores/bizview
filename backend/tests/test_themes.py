"""Feature 047: the theme library — upload, replace, delete, read and the installation choice."""

import json
from pathlib import Path

import yaml

from tests.conftest import client, make_project, signed_in, sql

THEMES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "theme" / "themes"


def authored(theme_id: str = "acme-azul", **changes) -> dict:
    data = json.loads((THEMES / "impacto.json").read_text(encoding="utf-8"))
    data["id"], data["name"], data["name_en"] = theme_id, "Acme · azul", "Acme · blue"
    data["version"] = 1
    data.update(changes)
    return data


def upload(c, data: dict, *, replace: bool = False):
    path = "/api/admin/themes" + ("?replace=true" if replace else "")
    return c.post(path, json={"yaml": yaml.safe_dump(data, sort_keys=False)})


def test_only_the_super_user_reaches_the_library(admin, user):
    for c in (signed_in(admin.email), signed_in(user.email)):
        assert c.get("/api/admin/themes").status_code == 403
        assert upload(c, authored()).status_code == 403
    anon = client()
    assert anon.get("/api/admin/themes").status_code == 401
    assert sql("SELECT count(*) FROM theme WHERE origin = 'upload'") == [(0,)]


def test_the_six_themes_the_product_ships_are_always_there(superuser):
    c = signed_in(superuser.email)
    body = c.get("/api/admin/themes").json()
    assert [t["id"] for t in body["themes"]] == ["clasico", "contraste", "daltonico", "elegante",
                                                 "impacto", "monocromo"]
    assert {t["origin"] for t in body["themes"]} == {"builtin"}
    assert body["installation"] == "impacto"
    row = next(t for t in body["themes"] if t["id"] == "impacto")
    assert row["tokens"]["light"]["surface"] == "#FFFFFF"
    assert row["version"] == 1


def test_an_upload_is_listed_with_its_origin_and_audited(superuser):
    c = signed_in(superuser.email)
    r = upload(c, authored())
    assert r.status_code == 201, r.text
    theme = r.json()["theme"]
    assert theme["id"] == "acme-azul" and theme["origin"] == "upload" and theme["version"] == 1
    assert sql("SELECT kind, detail FROM audit_event WHERE kind = 'theme_uploaded'") == [
        ("theme_uploaded", {"id": "acme-azul", "version": 1})]

    listed = c.get("/api/admin/themes").json()["themes"]
    assert [t["id"] for t in listed if t["origin"] == "upload"] == ["acme-azul"]


def test_an_invalid_theme_is_422_with_every_problem_and_stores_nothing(superuser):
    c = signed_in(superuser.email)
    data = authored()
    data["light"]["text"] = "#EEEEEE"       # unreadable on its own surface
    data["dark"]["primary"] = "#101828"     # and the accent disappears on the dark page
    r = upload(c, data)
    assert r.status_code == 422, r.text
    error = r.json()["error"]
    assert error["code"] == "theme_invalid"
    paths = {p["path"] for p in error["problems"]}
    assert {"light.text", "dark.primary"} <= paths
    assert any(":1" in p["message"] for p in error["problems"])
    assert sql("SELECT count(*) FROM theme WHERE origin = 'upload'") == [(0,)]


def test_replacing_needs_the_confirmation_and_bumps_the_version(superuser):
    c = signed_in(superuser.email)
    assert upload(c, authored()).status_code == 201
    second = authored()
    second["name"] = "Acme · azul oscuro"
    conflict = upload(c, second)
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["code"] == "theme_exists"
    assert conflict.json()["error"]["version"] == 1

    replaced = upload(c, second, replace=True)
    assert replaced.status_code == 201, replaced.text
    assert replaced.json()["theme"]["version"] == 2
    assert replaced.json()["theme"]["name"] == "Acme · azul oscuro"
    assert sql("SELECT count(*) FROM theme WHERE id = 'acme-azul'") == [(1,)]
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'theme_replaced'") == [(1,)]


def test_a_builtin_can_be_neither_replaced_nor_deleted(superuser):
    c = signed_in(superuser.email)
    impostor = authored("impacto")
    assert upload(c, impostor, replace=True).status_code == 403
    assert upload(c, impostor, replace=True).json()["error"]["code"] == "theme_builtin"
    gone = c.delete("/api/admin/themes/impacto")
    assert gone.status_code == 403 and gone.json()["error"]["code"] == "theme_builtin"
    assert sql("SELECT count(*) FROM theme WHERE id = 'impacto'") == [(1,)]


def test_a_theme_in_use_cannot_be_deleted(superuser):
    c = signed_in(superuser.email)
    assert upload(c, authored()).status_code == 201
    # A live project whose report names the theme: its next apply would break the same way.
    slug = make_project("Proyecto Tema", "proyecto-tema")
    saved = c.put(f"/api/projects/{slug}/file",
                  json={"path": "reports/ventas/report.yaml",
                        "content": "id: ventas\nname: Ventas\ntitle: Ventas\n"
                                   "layout:\n  theme:\n    id: acme-azul\n"})
    assert saved.status_code in (200, 201), saved.text

    refused = c.delete("/api/admin/themes/acme-azul")
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "theme_in_use"
    assert refused.json()["error"]["reports"] == ["ventas"]
    assert sql("SELECT count(*) FROM theme WHERE id = 'acme-azul'") == [(1,)]

    # Removing the report frees the theme (the delete carries the revision it saw).
    removed = c.post(f"/api/projects/{slug}/ops",
                     json={"ops": [{"op": "delete", "path": "reports/ventas/report.yaml",
                                    "base_sha256": saved.json()["file"]["sha256"]}]})
    assert removed.status_code == 200, removed.text
    assert c.delete("/api/admin/themes/acme-azul").status_code == 204
    assert sql("SELECT count(*) FROM theme WHERE id = 'acme-azul'") == [(0,)]
    assert sql("SELECT kind FROM audit_event WHERE kind = 'theme_deleted'") == [
        ("theme_deleted",)]


def test_an_unknown_theme_is_404_and_writes_no_audit(superuser):
    c = signed_in(superuser.email)
    assert c.delete("/api/admin/themes/nadie").status_code == 404
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'theme_deleted'") == [(0,)]


def test_the_download_is_the_file_the_author_uploaded(superuser):
    c = signed_in(superuser.email)
    assert upload(c, authored()).status_code == 201
    r = c.get("/api/admin/themes/acme-azul/download")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/yaml")
    assert 'filename="acme-azul.yaml"' in r.headers["content-disposition"]
    assert yaml.safe_load(r.text) == authored()


def test_a_viewer_reads_a_theme_and_the_second_read_is_a_304(user):
    c = signed_in(user.email)
    first = c.get("/api/themes/impacto")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["tokens"]["light"]["surface"] == "#FFFFFF"
    assert body["light"]["kpi_text"] == body["tokens"]["light"]["text"]
    etag = first.headers["etag"]
    assert etag
    again = c.get("/api/themes/impacto", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.content == b""
    assert c.get("/api/themes/nadie").status_code == 404


def test_the_installation_choice_is_saved_and_audited(superuser):
    c = signed_in(superuser.email)
    assert upload(c, authored()).status_code == 201
    r = c.put("/api/admin/settings/theme", json={"theme_id": "acme-azul"})
    assert r.status_code == 200, r.text
    assert r.json() == {"theme_id": "acme-azul"}
    assert c.get("/api/admin/themes").json()["installation"] == "acme-azul"
    # A custom id cannot live in `palette_preset` (its check lists the five), so it stays as it was.
    assert sql("SELECT theme_id, palette_preset FROM appearance_settings") == [
        ("acme-azul", "impacto")]
    assert sql("SELECT detail FROM audit_event WHERE kind = 'theme_applied'") == [
        ({"theme_id": {"from": "impacto", "to": "acme-azul"}},)]

    assert c.put("/api/admin/settings/theme",
                 json={"theme_id": "clasico"}).status_code == 200
    assert sql("SELECT theme_id, palette_preset FROM appearance_settings") == [
        ("clasico", "clasico")]
    assert c.put("/api/admin/settings/theme",
                 json={"theme_id": "nadie"}).status_code == 422


def test_bootstrap_brings_a_shipped_colour_back_to_an_installation_that_never_touched_it(superuser):
    """047 T012: a correction to a built-in reaches installations that already migrated."""
    from app.services import themes as store

    c = signed_in(superuser.email)
    assert c.get("/api/admin/themes").json()["themes"]
    # Somebody edited the row (or a release changed the file): the refresh puts the product back.
    sql("UPDATE theme SET tokens = jsonb_set(tokens, '{light,surface}', '\"#123456\"') "
        "WHERE id = 'impacto'")
    edited = next(t for t in c.get("/api/admin/themes").json()["themes"] if t["id"] == "impacto")
    assert edited["tokens"]["light"]["surface"] == "#123456"

    from app.db import get_sessionmaker

    with get_sessionmaker().begin() as session:
        changed = store.refresh_builtins(session, store.builtin_files())
    assert changed == 1
    row = next(t for t in c.get("/api/admin/themes").json()["themes"] if t["id"] == "impacto")
    assert row["tokens"]["light"]["surface"] == "#FFFFFF"
    assert row["origin"] == "builtin"
