"""Installation appearance (feature 030, T036/T037): the palette preset endpoint and /api/config."""

from tests.conftest import client, signed_in, sql

PRESETS = ["impacto", "clasico", "monocromo", "contraste", "daltonico"]


def test_only_the_super_user_reaches_the_settings(admin, user):
    for c in (signed_in(admin.email), signed_in(user.email)):
        assert c.get("/api/admin/appearance").status_code == 403
        r = c.put("/api/admin/appearance", json={"palette_preset": "clasico"})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "forbidden"
    anon = client()
    assert anon.get("/api/admin/appearance").status_code == 401
    assert anon.put("/api/admin/appearance",
                    json={"palette_preset": "clasico"}).status_code == 401
    assert sql("SELECT count(*) FROM appearance_settings") == [(0,)]


def test_get_defaults_to_impacto_without_a_row(superuser):
    c = signed_in(superuser.email)
    r = c.get("/api/admin/appearance")
    assert r.status_code == 200, r.text
    assert r.json() == {"palette_preset": "impacto", "presets": PRESETS}
    assert sql("SELECT count(*) FROM appearance_settings") == [(0,)]


def test_put_saves_the_singleton_and_audits(superuser):
    c = signed_in(superuser.email)
    r = c.put("/api/admin/appearance", json={"palette_preset": "contraste"})
    assert r.status_code == 200, r.text
    assert r.json() == {"palette_preset": "contraste"}
    assert sql("SELECT id, palette_preset, updated_by FROM appearance_settings") == [
        (1, "contraste", superuser.id)]
    assert c.get("/api/admin/appearance").json()["palette_preset"] == "contraste"

    assert sql("SELECT actor_id, detail FROM audit_event WHERE kind = 'appearance_updated'") == [
        (superuser.id, {"palette_preset": {"from": "impacto", "to": "contraste"}})]

    # A second save updates the same row and records the change from the saved value.
    r = c.put("/api/admin/appearance", json={"palette_preset": "monocromo"})
    assert r.status_code == 200, r.text
    assert sql("SELECT count(*) FROM appearance_settings") == [(1,)]
    assert sql("SELECT detail FROM audit_event WHERE kind = 'appearance_updated' "
               "ORDER BY id DESC LIMIT 1") == [
        ({"palette_preset": {"from": "contraste", "to": "monocromo"}},)]


def test_unknown_preset_is_422_and_writes_nothing(superuser):
    c = signed_in(superuser.email)
    r = c.put("/api/admin/appearance", json={"palette_preset": "arcoiris"})
    assert r.status_code == 422, r.text
    body = r.json()["error"]
    assert body["code"] == "validation_error"
    assert body["message"] == "Esa paleta no existe. Elige una de las disponibles."
    assert body["fields"] == {"palette_preset": "invalid"}
    assert sql("SELECT count(*) FROM appearance_settings") == [(0,)]
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'appearance_updated'") == [(0,)]

    r = c.put("/api/admin/appearance", json={"palette_preset": 3})
    assert r.status_code == 422
    assert sql("SELECT count(*) FROM appearance_settings") == [(0,)]


def test_the_message_follows_the_request_language(superuser):
    r = signed_in(superuser.email).put("/api/admin/appearance",
                                       json={"palette_preset": "arcoiris"},
                                       headers={"Accept-Language": "en"})
    assert r.status_code == 422
    assert r.json()["error"]["message"] == (
        "That palette does not exist. Choose one of the available ones.")


def test_put_requires_the_csrf_header(superuser):
    c = signed_in(superuser.email)
    r = c.put("/api/admin/appearance", json={"palette_preset": "clasico"},
              headers={"X-Requested-With": "xmlhttprequest"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"


def test_config_exposes_the_installation_preset(superuser):
    body = client().get("/api/config").json()
    assert body["palette_preset"] == "impacto"
    assert body["palette_presets"] == PRESETS

    assert signed_in(superuser.email).put(
        "/api/admin/appearance", json={"palette_preset": "daltonico"}).status_code == 200
    body = client().get("/api/config").json()
    assert body["palette_preset"] == "daltonico"
    assert body["palette_presets"] == PRESETS
