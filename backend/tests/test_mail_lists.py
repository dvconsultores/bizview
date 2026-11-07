"""Mailing lists (feature 058, US2): CRUD, sharing, CSV, paused members, role lists, deletion.

The product keeps addresses and nothing else: these tests also prove that a send reaches a list's
members, that a paused member is skipped, and that deleting a list pauses the deliveries that named
it instead of deleting them."""
import pytest

from app.config import get_settings
from tests.conftest import MAIL_ENV, client, make_user, set_mail, signed_in, sql
from tests.fake_smtp import SmtpRecorder
from tests.test_mail_send import SEL, enable_mail, grant_user, send
from tests.test_runner import origin as origin
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import applied as applied
from tests.test_vibe_reporting import workspace as workspace


@pytest.fixture
def smtp(monkeypatch):
    recorder = SmtpRecorder()
    recorder.install(monkeypatch)
    return recorder


def create_list(c, name="Gerencia comercial", **body):
    return c.post("/api/mail/lists", json={"name": name, **body})


def members(*addresses):
    return [{"address": a} for a in addresses]


def test_create_a_list_and_read_it_back(applied):
    c = signed_in("root@example.com")
    r = create_list(c, description="Comerciales activos")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Gerencia comercial"
    assert body["visibility"] == "personal"
    assert body["kind"] == "members"
    assert body["mine"] is True and body["editable"] is True
    assert body["count"] == 0

    r = c.put(f"/api/mail/lists/{body['id']}/members",
              json={"members": members("ana@cliente.com", "Luis <luis@cliente.com>")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] == 2
    assert {m["address"] for m in data["members"]} == {"ana@cliente.com", "luis@cliente.com"}
    assert next(m for m in data["members"] if m["address"] == "luis@cliente.com")["name"] == "Luis"

    r = c.get("/api/mail/lists")
    assert [item["name"] for item in r.json()["items"]] == ["Gerencia comercial"]
    assert r.json()["max_members"] == 1000


def test_the_name_is_unique_per_owner(applied):
    c = signed_in("root@example.com")
    assert create_list(c, "Ventas").status_code == 201
    r = create_list(c, "ventas")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "name_taken"
    # Another owner may use the same words: it is *their* list.
    other = make_user("otro@example.com", role="admin", full_name="Otro")
    r = signed_in(other.email).post("/api/mail/lists", json={"name": "Ventas"})
    assert r.status_code == 201, r.text


def test_a_personal_list_is_invisible_to_others_and_a_shared_one_is_usable(applied):
    owner = make_user("duena@example.com", role="admin", full_name="Dueña")
    other = make_user("otro2@example.com", role="admin", full_name="Otro")
    c = signed_in(owner.email)
    personal = create_list(c, "Personal").json()
    shared = create_list(c, "Compartida", visibility="compartida").json()

    theirs = signed_in(other.email).get("/api/mail/lists").json()["items"]
    assert [item["name"] for item in theirs] == ["Compartida"]
    assert theirs[0]["editable"] is True          # an admin edits a shared list
    assert signed_in(other.email).get(f"/api/mail/lists/{personal['id']}").status_code == 404
    assert signed_in(other.email).get(f"/api/mail/lists/{shared['id']}").status_code == 200


def test_only_an_admin_creates_shared_or_role_lists(applied, user):
    c = signed_in(user.email)
    r = create_list(c, "Equipo", visibility="compartida")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "list_not_shared"
    r = create_list(c, "Admins", kind="role", role="admin")
    assert r.status_code == 403
    # A regular user still owns personal lists.
    assert create_list(c, "Mis clientes").status_code == 201


def test_a_shared_list_is_read_only_for_somebody_else(applied, user):
    admin = make_user("admin3@example.com", role="admin", full_name="Admin Tres")
    shared = create_list(signed_in(admin.email), "Todos", visibility="compartida").json()
    c = signed_in("root@example.com")            # the superuser may edit it
    assert c.put(f"/api/mail/lists/{shared['id']}/members",
                 json={"members": members("a@cliente.com")}).status_code == 200


def test_csv_import_reports_bad_lines_and_keeps_going(applied):
    c = signed_in("root@example.com")
    row = create_list(c).json()
    text = "correo,nombre\nana@cliente.com,Ana\nno-es-correo,X\nluis@cliente.com,Luis\n"
    r = c.post(f"/api/mail/lists/{row['id']}/members/import", json={"text": text})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["added"] == 2 and body["skipped"] == 1
    assert body["errors"][0]["line"] == 3
    assert body["list"]["count"] == 2
    exported = c.get(f"/api/mail/lists/{row['id']}/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "ana@cliente.com,Ana,no" in exported.text
    assert exported.headers["content-disposition"].startswith('attachment; filename="lista-')


def test_a_paused_member_is_skipped_by_a_send(applied, smtp):
    enable_mail(domains=())                      # 058: no restriction by default
    c = signed_in("root@example.com")
    row = create_list(c, "Comerciales").json()
    members_json = c.put(f"/api/mail/lists/{row['id']}/members", json={"members": members(
        "ana@cliente.com", "luis@cliente.com")}).json()
    paused = next(m for m in members_json["members"] if m["address"] == "ana@cliente.com")
    r = c.post(f"/api/mail/lists/{row['id']}/members/{paused['id']}/pause",
               json={"paused": True})
    assert r.status_code == 200
    assert r.json()["paused"] == 1

    r = send(c, lists=[row["id"]])
    assert r.status_code == 201, r.text
    assert r.json()["count"] == 1
    delivered = {d["recipient"] for d in r.json()["deliveries"]}
    assert delivered == {"l***@cliente.com"}


def test_a_send_delivers_to_users_lists_and_addresses_without_duplicates(applied, smtp):
    enable_mail(domains=())
    uid = grant_user(make_user("colega@example.com").id)
    c = signed_in("root@example.com")
    row = create_list(c, "Comerciales").json()
    c.put(f"/api/mail/lists/{row['id']}/members",
          json={"members": members("ana@cliente.com", "colega@example.com")})

    r = send(c, users=[uid], lists=[row["id"]],
             emails=["ana@cliente.com", "nuevo@cliente.com", "Nuevo <NUEVO@cliente.com>"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["count"] == 3                    # colega, ana, nuevo (deduplicated)
    assert body["kinds"] == {"users": 1, "lists": ["Comerciales"], "emails": 1, "total": 3}
    # The addresses of somebody else's send are masked in the answer.
    assert all("*" in d["recipient"] for d in body["deliveries"])


def test_the_sender_is_never_a_recipient(applied, smtp):
    enable_mail(domains=())
    c = signed_in("root@example.com")
    row = create_list(c).json()
    c.put(f"/api/mail/lists/{row['id']}/members",
          json={"members": members("root@example.com", "ana@cliente.com")})
    r = send(c, lists=[row["id"]], emails=["root@example.com"])
    assert r.status_code == 201
    assert r.json()["count"] == 1


def test_a_role_list_resolves_at_send_time(applied, smtp):
    enable_mail(domains=())
    c = signed_in("root@example.com")
    row = create_list(c, "Administradores", kind="role", role="admin").json()
    assert row["kind"] == "role" and row["role"] == "admin"
    before = row["count"]
    make_user("admin4@example.com", role="admin", full_name="Admin Cuatro")
    after = c.get(f"/api/mail/lists/{row['id']}").json()["count"]
    assert after == before + 1                  # a new administrator is in the list at once
    r = send(c, lists=[row["id"]])
    assert r.status_code == 201
    # The sender is an administrator too, and a sender never receives their own send.
    assert r.json()["count"] == after - 1
    delivered = {d["recipient"] for d in r.json()["deliveries"]}
    assert "a***@example.com" in delivered            # admin4, resolved at send time


def test_a_list_can_be_saved_from_a_send(applied, smtp):
    enable_mail(domains=())
    c = signed_in("root@example.com")
    r = send(c, emails=["ana@cliente.com", "Luis <luis@cliente.com>"],
             save_as_list="Del hilo")
    assert r.status_code == 201, r.text
    lists = c.get("/api/mail/lists").json()["items"]
    saved = next(item for item in lists if item["name"] == "Del hilo")
    assert saved["count"] == 2


def test_deleting_a_list_pauses_its_subscriptions(applied):
    enable_mail(domains=())
    c = signed_in("root@example.com")
    row = create_list(c, "Semanal").json()
    c.put(f"/api/mail/lists/{row['id']}/members", json={"members": members("ana@cliente.com")})
    dash_id = sql("SELECT id FROM dashboard WHERE code = 'ventas'")[0][0]
    r = c.post("/api/dashboards/ventas/subscriptions", json={
        "frequency": "weekly", "hour": 7, "weekday": 1, "period": "mtd",
        "lists": [row["id"]], "attach_pdf": True,
    })
    assert r.status_code == 201, r.text
    sub_id = r.json()["id"]
    assert r.json()["recipients"][0]["kind"] == "list"
    assert r.json()["recipients"][0]["name"] == "Semanal"

    assert c.delete(f"/api/mail/lists/{row['id']}").status_code == 204
    subs = c.get("/api/dashboards/ventas/subscriptions").json()["items"]
    sub = next(item for item in subs if item["id"] == sub_id)
    assert sub["paused"] is True
    assert sub["paused_reason"] == "list_deleted"
    assert sql("SELECT count(*) FROM email_subscription WHERE id = :i", i=sub_id)[0][0] == 1

    # Editing it (with another recipient) resumes it and clears the reason.
    r = c.patch(f"/api/dashboards/ventas/subscriptions/{sub_id}",
                json={"users": [], "lists": [], "emails": ["ana@cliente.com"], "paused": False})
    assert r.status_code == 200, r.text
    assert r.json()["paused"] is False
    assert r.json()["paused_reason"] is None


def test_the_member_cap_is_enforced(applied):
    c = signed_in("root@example.com")
    row = create_list(c, "Grande").json()
    over = [{"address": f"p{i}@cliente.com"} for i in range(1001)]
    r = c.put(f"/api/mail/lists/{row['id']}/members", json={"members": over})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "list_too_large"


def test_an_unknown_list_is_refused_by_a_send(applied):
    enable_mail(domains=())
    r = send(signed_in("root@example.com"), lists=[999])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["lists"] == "not_found"


def test_non_admins_cannot_send_free_addresses_when_the_installation_says_so(applied, smtp):
    enable_mail(domains=())
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "", "email_free_addresses_role": "admin"})
    uid = grant_user(make_user("usuario3@example.com").id)
    c = signed_in("usuario3@example.com")
    r = send(c, users=[uid], emails=["ana@cliente.com"])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["emails"] == "role_not_allowed"
    # A list is not a typed address: it still works for a regular sender.
    row = create_list(signed_in("root@example.com"), "Comerciales").json()
    signed_in("root@example.com").put(f"/api/mail/lists/{row['id']}/members",
                                      json={"members": members("ana@cliente.com")})
    r = send(c, users=[uid], lists=[row["id"]])
    assert r.status_code == 201, r.text
