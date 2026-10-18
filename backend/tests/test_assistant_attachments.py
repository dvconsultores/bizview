"""Feature 024: image briefs in the chat — upload, delivery to the provider, limits and privacy.

The picture is a *brief*: the product stores it outside the project folders, the model reads it
with the message that carries it, and the bytes never reach the conversation payload or the audit.
"""
import json
import shutil
from pathlib import Path

import pytest

from app.ai import ChatReply, ChatUsage, fake
from app.config import get_settings
from tests.conftest import client, new_chat, signed_in, sql

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
GIF = b"GIF89a" + b"\x00" * 64
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'


@pytest.fixture(autouse=True)
def vision(monkeypatch):
    """The fake provider stands in for a vision model unless a test says otherwise."""
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.setenv("AI_VISION", "true")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clean_attachments():
    """The upload directory is shared by the whole run: every test starts with it empty."""
    root = Path(get_settings().attachments_dir)
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture
def chat(superuser):
    c = signed_in("root@example.com")
    return c, new_chat(c)


def _reply(text="Entendido: un reporte de ventas."):
    return ChatReply(text=text, tool_calls=(), usage=ChatUsage(input=10, output=5), model="fake")


def _upload(c, session_id, data=PNG, name="boceto.png"):
    return c.post(f"/api/assistant/sessions/{session_id}/attachments", content=data,
                  params={"name": name} if name else None,
                  headers={"Content-Type": "image/png"})


def _send(c, session_id, text, attachments=None):
    body = {"text": text, **({"attachments": attachments} if attachments is not None else {})}
    return c.post(f"/api/assistant/sessions/{session_id}/messages", json=body)


def _files(session_id):
    root = Path(get_settings().attachments_dir) / str(session_id)
    return sorted(p.name for p in root.glob("*"))


def _sha(attachment_id):
    return sql("SELECT sha256 FROM assistant_attachment WHERE id = :i", i=attachment_id)[0][0]


def test_upload_then_send_reaches_the_model_as_an_image_part(superuser, chat):
    """US1/AS1: the picture reaches the provider with its message and the untrusted-data label."""
    c, session_id = chat
    uploaded = _upload(c, session_id)
    assert uploaded.status_code == 201, uploaded.text
    image = uploaded.json()
    assert (image["media_type"], image["byte_size"]) == ("image/png", len(PNG))
    assert image["url"] == f"/api/assistant/attachments/{image['id']}"
    assert _files(session_id) == [f"{_sha(image['id'])}.png"]

    fake.SHARED.queue(_reply())
    sent = _send(c, session_id, "quiero un reporte como este", [image["id"]])
    assert sent.status_code == 202, sent.text

    message = fake.SHARED.requests[-1]["messages"][-1]
    assert message["role"] == "user"
    assert message["images"] == [("image/png", len(PNG))]
    assert message["content"].startswith("Datos no confiables")
    assert "quiero un reporte como este" in message["content"]

    # The conversation shows metadata only: no bytes, no path, no checksum.
    assert sent.json()["messages"][0]["attachments"] == [
        {"id": image["id"], "media_type": "image/png", "byte_size": len(PNG),
         "original_name": "boceto.png", "url": image["url"]}]
    stored = c.get(f"/api/assistant/sessions/{session_id}").json()
    assert [a["id"] for m in stored["messages"] for a in m.get("attachments", [])] == [image["id"]]


def test_an_image_alone_is_an_accepted_message(superuser, chat):
    """FR-001: an image with no text is a brief; the conversation is named after the file."""
    c, session_id = chat
    image = _upload(c, session_id, name="mockup.png").json()
    fake.SHARED.queue(_reply())
    sent = _send(c, session_id, "", [image["id"]])
    assert sent.status_code == 202, sent.text
    assert sent.json()["session"]["title"] == "mockup.png"
    assert fake.SHARED.requests[-1]["messages"][-1]["images"] == [("image/png", len(PNG))]


@pytest.mark.parametrize("data,media_type", [(PNG, "image/png"), (JPEG, "image/jpeg"),
                                             (GIF, "image/gif"), (WEBP, "image/webp")])
def test_the_type_is_decided_by_the_magic_bytes(superuser, chat, data, media_type):
    c, session_id = chat
    uploaded = _upload(c, session_id, data=data, name="adjunto.bin")
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["media_type"] == media_type


def test_limits_and_rejected_types(superuser, chat, monkeypatch):
    """FR-003: 5 MB, images only, and a bounded number waiting in one conversation."""
    c, session_id = chat
    monkeypatch.setenv("ATTACHMENTS_MAX_MB", "1")
    get_settings.cache_clear()
    too_large = _upload(c, session_id, data=PNG + b"\x00" * (1024 * 1024))
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "attachment_too_large"

    for not_an_image in (b"%PDF-1.7\n" + b"\x00" * 32, SVG, b"P K\x03\x04" + b"\x00" * 32):
        rejected = _upload(c, session_id, data=not_an_image)
        assert rejected.status_code == 415, rejected.text
        assert rejected.json()["error"]["code"] == "attachment_type"

    monkeypatch.setenv("ATTACHMENTS_MAX_MB", "5")
    get_settings.cache_clear()
    for _ in range(get_settings().attachments_max_per_message):
        assert _upload(c, session_id).status_code == 201
    over = _upload(c, session_id)
    assert over.status_code == 409
    assert over.json()["error"]["code"] == "attachment_limit"


def test_another_conversation_and_unknown_ids_are_not_found(superuser, chat):
    """FR-009: an id of another conversation is indistinguishable from one that does not exist."""
    c, session_id = chat
    image = _upload(c, session_id).json()
    other = new_chat(c)
    assert _send(c, other, "otro reporte", [image["id"]]).status_code == 404
    assert _send(c, session_id, "hola", [999_999]).status_code == 404
    empty = _send(c, session_id, "", [])
    assert empty.status_code == 422
    assert empty.json()["error"]["fields"] == {"text": "empty"}


def test_vision_disabled_refuses_the_image_but_not_the_text(superuser, chat, monkeypatch):
    """US2/SC-002: no silent drop — the call says why, and plain text keeps working."""
    c, session_id = chat
    image = _upload(c, session_id).json()
    monkeypatch.setenv("AI_VISION", "false")
    get_settings.cache_clear()

    refused = _upload(c, session_id)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "vision_unavailable"
    refused_send = _send(c, session_id, "un reporte", [image["id"]])
    assert refused_send.status_code == 409
    assert refused_send.json()["error"]["code"] == "vision_unavailable"
    assert refused_send.json()["error"]["message"] == refused.json()["error"]["message"]
    assert sql("SELECT count(*) FROM assistant_message WHERE session_id = :s",
               s=session_id)[0][0] == 0

    fake.SHARED.queue(_reply("Sin imagen."))
    assert _send(c, session_id, "un reporte sin imagen").status_code == 202
    assert fake.SHARED.requests[-1]["messages"][-1]["images"] == []


def test_read_and_delete_move_the_file_with_the_row(superuser, chat):
    """FR-010: deleting an image leaves the project and the message text alone."""
    c, session_id = chat
    image = _upload(c, session_id).json()
    fake.SHARED.queue(_reply())
    _send(c, session_id, "mira el boceto", [image["id"]])

    fetched = c.get(image["url"])
    assert fetched.status_code == 200
    assert fetched.content == PNG
    assert fetched.headers["content-type"] == "image/png"
    assert "private" in fetched.headers["cache-control"]

    assert c.delete(image["url"]).status_code == 204
    assert c.get(image["url"]).status_code == 404
    assert _files(session_id) == []
    assert sql("SELECT content FROM assistant_message WHERE session_id = :s AND role = 'user'",
               s=session_id)[0][0] == "mira el boceto"


def test_the_bytes_never_reach_the_audit_or_the_payload(superuser, chat):
    """FR-007/SC-003: the log keeps the size and a short hash, never the content."""
    c, session_id = chat
    image = _upload(c, session_id).json()
    fake.SHARED.queue(_reply())
    _send(c, session_id, "mira el boceto", [image["id"]])

    rows = sql("SELECT kind, detail::text FROM audit_event "
               "WHERE kind LIKE 'assistant_attachment%' ORDER BY id")
    assert [kind for kind, _ in rows] == ["assistant_attachment_uploaded"]
    detail = json.loads(rows[0][1])
    assert detail["byte_size"] == len(PNG)
    assert detail["media_type"] == "image/png"
    assert detail["sha256"] == _sha(image["id"])[:12]
    assert "boceto.png" not in rows[0][1]

    payload = str(c.get(f"/api/assistant/sessions/{session_id}").json())
    for token in ("iVBOR", "base64", str(get_settings().attachments_dir)):
        assert token not in payload


def test_a_pending_upload_is_swept_after_a_day(superuser, chat):
    """FR-008: an image that never becomes a message does not stay forever."""
    c, session_id = chat
    old = _upload(c, session_id).json()
    old_file = _files(session_id)[0]
    sql("UPDATE assistant_attachment SET created_at = now() - interval '25 hours' WHERE id = :i",
        i=old["id"])
    fresh = _upload(c, session_id, data=WEBP, name="nuevo.webp").json()

    assert c.get(old["url"]).status_code == 404
    assert c.get(fresh["url"]).status_code == 200
    assert _files(session_id) == [f"{_sha(fresh['id'])}.webp"]
    assert old_file not in _files(session_id)


def test_the_same_image_is_stored_once(superuser, chat):
    """Two rows of identical bytes share one file; removing one keeps the other readable."""
    c, session_id = chat
    first = _upload(c, session_id, name="uno.png").json()
    second = _upload(c, session_id, name="dos.png").json()
    assert _sha(first["id"]) == _sha(second["id"])
    assert len(_files(session_id)) == 1

    assert c.delete(first["url"]).status_code == 204
    assert _files(session_id) == [f"{_sha(second['id'])}.png"]
    assert c.get(second["url"]).content == PNG


def test_text_only_messages_are_unchanged(superuser, chat):
    """FR-012: without attachments the payload and the provider call are today's."""
    c, session_id = chat
    fake.SHARED.queue(_reply())
    sent = _send(c, session_id, "un reporte de ventas")
    assert sent.status_code == 202
    assert fake.SHARED.requests[-1]["messages"][-1]["images"] == []
    assert "attachments" not in sent.json()["messages"][0]


def test_the_refusal_is_localized(superuser, chat, monkeypatch):
    """FR-013: the reason is in the viewer's language."""
    c, session_id = chat
    assert c.patch("/api/me/preferences", json={"locale": "en"}).status_code == 200
    monkeypatch.setenv("AI_VISION", "false")
    get_settings.cache_clear()
    refused = _upload(c, session_id)
    assert refused.status_code == 409
    assert "cannot read images" in refused.json()["error"]["message"]


def test_the_upload_needs_a_session(superuser):
    """The route is behind the same authentication as the rest of the assistant."""
    anonymous = client()
    response = anonymous.post("/api/assistant/sessions/1/attachments", content=PNG)
    assert response.status_code in (401, 403)
    assert "PNG" not in response.text


def test_a_model_that_refuses_the_picture_answers_the_text_and_says_so(superuser, chat):
    """US2/FR-004: no silent drop and no invented report when the provider rejects the image."""
    from app.ai import AIError

    c, session_id = chat
    image = _upload(c, session_id).json()

    def refuse(*_args, **_kwargs):
        raise AIError("provider_error", "this model does not accept image_url")

    fake.SHARED.queue(refuse, _reply("Puedo ayudarte con el texto."))
    sent = _send(c, session_id, "quiero un reporte asi", [image["id"]])
    assert sent.status_code == 202, sent.text

    contents = [m["content"] for m in sent.json()["messages"]]
    assert any("no puede leer imágenes" in text for text in contents)
    assert any("Puedo ayudarte con el texto." in text for text in contents)
    # The retry carried the text alone; the picture stays in the conversation and on disk.
    assert fake.SHARED.requests[-1]["messages"][-1]["images"] == []
    assert sent.json()["messages"][0]["attachments"][0]["id"] == image["id"]
    assert _files(session_id)


def test_purging_a_project_removes_its_images(superuser, chat):
    """FR-008: the images of a deleted project do not stay on disk."""
    from datetime import UTC, datetime, timedelta

    from app.db import get_sessionmaker
    from app.projects import service as project_service
    from tests.conftest import reauth

    c, session_id = chat
    image = _upload(c, session_id).json()
    fake.SHARED.queue(_reply())
    _send(c, session_id, "mira el boceto", [image["id"]])
    assert _files(session_id)

    slug = sql("SELECT p.slug FROM project p JOIN assistant_session s ON s.project_id = p.id"
               " WHERE s.id = :i", i=session_id)[0][0]
    assert reauth(c).delete(f"/api/projects/{slug}").status_code == 204
    with get_sessionmaker().begin() as session:
        assert project_service.purge_trash(session,
                                           datetime.now(UTC) + timedelta(days=31)) >= 1

    assert _files(session_id) == []
    assert sql("SELECT count(*) FROM assistant_attachment WHERE session_id = :i",
               i=session_id)[0][0] == 0
