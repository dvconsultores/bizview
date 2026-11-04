"""Feature 023 T040: the guide API by role and language."""
from tests.conftest import signed_in


def _ids(c) -> set[str]:
    r = c.get("/api/guide")
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "private, max-age=300"
    return {topic["id"] for topic in r.json()["topics"]}


def test_each_role_sees_its_topics(superuser, admin, user):
    user_ids = _ids(signed_in("user@example.com"))
    admin_ids = _ids(signed_in("admin@example.com"))
    super_ids = _ids(signed_in("root@example.com"))
    assert {"ingreso", "tableros", "ayuda", "reportes-directos"} <= user_ids
    assert "usuarios" not in user_ids and "seguridad" not in user_ids
    assert {"usuarios", "envios-programados", "compartir-enlace"} <= admin_ids
    assert "seguridad" not in admin_ids and "proyectos" not in admin_ids
    assert user_ids < admin_ids < super_ids
    assert len(super_ids) == 54


def test_hidden_or_unknown_topic_is_404(superuser, user):
    c = signed_in("user@example.com")
    for topic in ("seguridad", "no-existe"):
        r = c.get(f"/api/guide/topics/{topic}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "guide_topic_not_found"
    r = signed_in("root@example.com").get("/api/guide/topics/seguridad")
    assert r.status_code == 200
    body = r.json()
    assert body["body"].startswith("# Seguridad\n")
    assert body["routes"] == ["/admin/seguridad"]


def test_english_request_gets_english_titles(superuser, user):
    c = signed_in("user@example.com")
    r = c.get("/api/guide", headers={"Accept-Language": "en"})
    titles = {t["id"]: t["title"] for t in r.json()["topics"]}
    assert titles["tableros"] == "Dashboards"
    r = c.get("/api/guide/topics/tableros", headers={"Accept-Language": "en"})
    assert r.json()["body"].startswith("# Dashboards\n")
    related = r.json()["related"]
    assert related and all(set(item) == {"id", "title"} for item in related)
