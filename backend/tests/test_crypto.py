"""Feature 004 / US4: encryption at rest, key check, rotation (FR-013 - FR-015, SC-006)."""
import base64
import os
import time

import pytest
from pydantic import SecretStr

from app.models import DataSource
from app.security import crypto
from app.security.crypto import CryptoError, Keyring, source_aad
from tests.conftest import sql


def new_key() -> bytes:
    return os.urandom(32)


def b64(key: bytes) -> SecretStr:
    return SecretStr(base64.urlsafe_b64encode(key).decode())


def test_round_trip_and_format():
    kr = Keyring(new_key())
    blob, kid = kr.encrypt_json({"password": "s3cret"}, source_aad(1))
    assert kid == kr.current_id and len(kid) == 8
    assert b"s3cret" not in blob and len(blob) > crypto.NONCE_BYTES + 16
    assert kr.decrypt_json(blob, kid, source_aad(1)) == {"password": "s3cret"}
    blob2, _ = kr.encrypt_json({"password": "s3cret"}, source_aad(1))
    assert blob != blob2  # random nonce


def test_tampering_and_wrong_row_are_detected():
    kr = Keyring(new_key())
    blob, kid = kr.encrypt_json({"password": "x"}, source_aad(1))
    with pytest.raises(CryptoError):
        kr.decrypt(blob, kid, source_aad(2))                      # copied to another row
    with pytest.raises(CryptoError):
        kr.decrypt(blob, kid, crypto.totp_aad(1))                 # another purpose
    tampered = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(CryptoError):
        kr.decrypt(tampered, kid, source_aad(1))


def test_wrong_key_is_rejected():
    blob, kid = Keyring(new_key()).encrypt(b"x", "aad")
    with pytest.raises(CryptoError, match="no configured key"):
        Keyring(new_key()).decrypt(blob, kid, "aad")


@pytest.mark.parametrize("value,fragment", [("not base64!!", "base64url"),
                                            (base64.urlsafe_b64encode(b"short").decode(), "32")])
def test_invalid_key_settings(value, fragment):
    with pytest.raises(CryptoError, match=fragment):
        crypto.parse_key(SecretStr(value), "BIZVIEW_SECRET_KEY")


def test_encrypt_without_key_refuses():
    with pytest.raises(CryptoError, match="not set"):
        Keyring(None).encrypt(b"x", "aad")


def add_source(db, kr: Keyring, n: int, secret: str = "pw") -> DataSource:
    src = DataSource(name=f"s{n}", kind="postgresql", settings={}, secret_fields=["password"])
    db.add(src)
    db.flush()
    src.secrets_ct, src.secrets_key_id = kr.encrypt_json({"password": secret}, source_aad(src.id))
    return src


def test_start_check(db):
    kr = Keyring(new_key())
    assert crypto.verify_key_at_start(db, kr) == "no encrypted data"
    add_source(db, kr, 1)
    crypto.ensure_key_check(db, kr)
    assert crypto.verify_key_at_start(db, kr) == "ok"
    with pytest.raises(CryptoError, match="not set"):
        crypto.verify_key_at_start(db, Keyring(None))
    with pytest.raises(CryptoError, match="does not match"):
        crypto.verify_key_at_start(db, Keyring(new_key()))


def test_rotation_reencrypts_everything_quickly(db):
    old, new = new_key(), new_key()
    kr_old = Keyring(old)
    crypto.ensure_key_check(db, kr_old)
    for i in range(1000):
        add_source(db, kr_old, i, secret=f"pw{i}")
    db.flush()
    kr_rot = Keyring(new, previous=old)
    assert crypto.verify_key_at_start(db, kr_rot) == "rotation pending"
    started = time.monotonic()
    counts = crypto.rotate(db, kr_rot)
    elapsed = time.monotonic() - started
    db.commit()
    assert counts == {"data_source": 1000, "app_user": 0, "telegram_settings": 0,
                      "email_send": 0}
    assert elapsed < 60, elapsed                                   # SC-006
    kr_new = Keyring(new)
    assert crypto.verify_key_at_start(db, kr_new) == "ok"
    rows = sql("SELECT id, secrets_ct, secrets_key_id FROM data_source ORDER BY id")
    assert {r[2] for r in rows} == {kr_new.current_id}
    first = rows[0]
    assert kr_new.decrypt_json(first[1], first[2], source_aad(first[0])) == {"password": "pw0"}
    with pytest.raises(CryptoError):                               # old key alone: useless now
        Keyring(old).decrypt(first[1], first[2], source_aad(first[0]))
    assert sql("SELECT key_rotated_at IS NOT NULL FROM security_state")[0][0]


def test_settings_keyring_uses_test_key():
    kr = crypto.get_keyring()
    assert kr.current is not None and kr.previous is None


def test_b64_helper_round_trip():
    k = new_key()
    assert crypto.parse_key(b64(k), "X") == k


def test_missing_key_gives_clear_api_error(superuser, monkeypatch):
    from tests.conftest import reauth, signed_in
    monkeypatch.setattr(crypto, "get_keyring", lambda: Keyring(None))
    c = reauth(signed_in(superuser.email))
    r = c.post("/api/me/mfa/setup")
    assert r.status_code == 503 and r.json()["error"]["code"] == "encryption_unavailable"


def test_rotation_reencrypts_email_link_ciphertexts(db):
    from sqlalchemy import select

    from app.models import Dashboard, EmailSend

    old = new_key()
    new = new_key()
    kr_old = Keyring(old)
    crypto.ensure_key_check(db, kr_old)
    dash_id = db.scalar(select(Dashboard.id).where(Dashboard.code == "ventas"))
    ct_a, kid_old = kr_old.encrypt(b"tok-A", crypto.EMAIL_LINK_AAD)
    ct_b, _ = kr_old.encrypt(b"tok-B", crypto.EMAIL_LINK_AAD)

    def b64(v: bytes) -> str:
        return base64.b64encode(v).decode()

    a = EmailSend(
        dashboard_id=dash_id,
        subject="a",
        status="sending",
        selection={
            "params": [["period", "mtd"]],
            "link": {"id": 11, "ct": b64(ct_a), "kid": kid_old},
        },
    )
    b = EmailSend(
        dashboard_id=dash_id,
        subject="b",
        status="sent",
        selection={"link": {"id": 12, "ct": b64(ct_b), "kid": kid_old, "sub": 5}},
    )
    c = EmailSend(
        dashboard_id=dash_id,
        subject="c",
        status="sent",
        selection={"link": {"id": 13}},
    )
    db.add_all([a, b, c])
    db.flush()
    new_keyring = Keyring(new, previous=old)
    assert crypto.verify_key_at_start(db, new_keyring) == "rotation pending"
    counts = crypto.rotate(db, new_keyring)
    db.flush()
    assert counts["email_send"] == 2
    for row in (a, b, c):
        db.refresh(row)
    assert a.selection["params"] == [["period", "mtd"]]
    assert a.selection["link"]["id"] == 11
    assert a.selection["link"]["kid"] == new_keyring.current_id
    assert Keyring(new).decrypt(
        base64.b64decode(a.selection["link"]["ct"]),
        a.selection["link"]["kid"],
        crypto.EMAIL_LINK_AAD,
    ) == b"tok-A"
    assert b.selection["link"]["sub"] == 5
    assert Keyring(new).decrypt(
        base64.b64decode(b.selection["link"]["ct"]),
        b.selection["link"]["kid"],
        crypto.EMAIL_LINK_AAD,
    ) == b"tok-B"
    assert c.selection == {"link": {"id": 13}}
    with pytest.raises(CryptoError):
        Keyring(old).decrypt(
            base64.b64decode(a.selection["link"]["ct"]),
            a.selection["link"]["kid"],
            crypto.EMAIL_LINK_AAD,
        )
    assert crypto.rotate(db, Keyring(new))["email_send"] == 0


def test_encrypted_email_link_requires_key_check(db):
    from sqlalchemy import select

    from app.models import Dashboard, EmailSend

    dash_id = db.scalar(select(Dashboard.id).where(Dashboard.code == "ventas"))
    kr = Keyring(new_key())
    ct, kid = kr.encrypt(b"tok", crypto.EMAIL_LINK_AAD)
    db.add(
        EmailSend(
            dashboard_id=dash_id,
            subject="x",
            status="sending",
            selection={
                "link": {
                    "id": 1,
                    "ct": base64.b64encode(ct).decode(),
                    "kid": kid,
                }
            },
        )
    )
    db.flush()
    with pytest.raises(CryptoError, match="key check is missing"):
        crypto.verify_key_at_start(db, Keyring(new_key()))


def test_rotate_cli_reports_every_count(db, monkeypatch):
    from app import cli

    old = new_key()
    new = new_key()
    crypto.ensure_key_check(db, Keyring(old))
    monkeypatch.setattr(crypto, "get_keyring", lambda: Keyring(new, previous=old))
    msg = cli.rotate_secret_key(db)
    assert "0 sources" in msg
    assert "two-step secrets" in msg
    assert "Telegram tokens" in msg
    assert "SMTP" not in msg
    assert "0 email links" in msg
    assert "BIZVIEW_SECRET_KEY_PREVIOUS" in msg
