"""Encryption of credentials at rest (feature 004, research R1).

AES-256-GCM with a key that exists only in the installation settings (BIZVIEW_SECRET_KEY), never
in the database. Stored format: nonce (12 bytes) || ciphertext+tag, plus the key id (first 8 hex
chars of SHA-256 of the key). Associated data binds each value to its row and purpose, so a
ciphertext copied to another row or column cannot be decrypted.
"""
import base64
import binascii
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings

log = logging.getLogger("app.security")

NONCE_BYTES = 12
KEY_CHECK_AAD = "bizview:v1:security_state:key_check"
KEY_CHECK_VALUE = b"bizview-key-check-v1"


class CryptoError(Exception):
    """Configuration or integrity problem. Messages never contain key material."""


def source_aad(source_id: int) -> str:
    return f"bizview:v1:data_source:{source_id}:secrets"


TELEGRAM_AAD = "bizview:v1:telegram_settings:token"
EMAIL_LINK_AAD = "bizview:v1:email_send:link"


def totp_aad(user_id: int) -> str:
    return f"bizview:v1:app_user:{user_id}:totp"


def parse_key(value: SecretStr | None, setting: str) -> bytes | None:
    if value is None:
        return None
    raw = value.get_secret_value().strip()
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (binascii.Error, ValueError):
        raise CryptoError(f"{setting} is not valid base64url") from None
    if len(key) != 32:
        raise CryptoError(f"{setting} must encode exactly 32 bytes (256 bits)")
    return key


def key_id(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:8]


@dataclass(frozen=True)
class Keyring:
    current: bytes | None
    previous: bytes | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "Keyring":
        return cls(parse_key(settings.bizview_secret_key, "BIZVIEW_SECRET_KEY"),
                   parse_key(settings.bizview_secret_key_previous, "BIZVIEW_SECRET_KEY_PREVIOUS"))

    @property
    def current_id(self) -> str | None:
        return key_id(self.current) if self.current else None

    def _key_for(self, kid: str) -> bytes:
        for key in (self.current, self.previous):
            if key is not None and key_id(key) == kid:
                return key
        raise CryptoError(f"no configured key matches key id {kid}")

    def encrypt(self, plaintext: bytes, aad: str) -> tuple[bytes, str]:
        if self.current is None:
            raise CryptoError("BIZVIEW_SECRET_KEY is not set; credentials cannot be stored")
        nonce = os.urandom(NONCE_BYTES)
        ct = AESGCM(self.current).encrypt(nonce, plaintext, aad.encode())
        return nonce + ct, key_id(self.current)

    def decrypt(self, blob: bytes, kid: str, aad: str) -> bytes:
        key = self._key_for(kid)
        try:
            return AESGCM(key).decrypt(bytes(blob[:NONCE_BYTES]), bytes(blob[NONCE_BYTES:]),
                                       aad.encode())
        except InvalidTag:
            raise CryptoError("stored value failed integrity check (wrong key or tampered)") \
                from None

    def encrypt_json(self, obj: dict, aad: str) -> tuple[bytes, str]:
        return self.encrypt(json.dumps(obj, separators=(",", ":"), sort_keys=True).encode(), aad)

    def decrypt_json(self, blob: bytes, kid: str, aad: str) -> dict:
        return json.loads(self.decrypt(blob, kid, aad))


@lru_cache
def get_keyring() -> Keyring:
    return Keyring.from_settings(get_settings())


# --- key check and rotation ------------------------------------------------------------------

def _encrypted_data_exists(db: Session) -> bool:
    from app.models import AppUser, DataSource, EmailSend, TelegramSettings
    return bool(db.scalar(select(or_(
        exists().where(DataSource.secrets_ct.is_not(None)),
        exists().where(AppUser.totp_secret_ct.is_not(None)),
        exists().where(TelegramSettings.token_ct.is_not(None)),
        exists().where(EmailSend.selection["link"].has_key("ct"))))))


def ensure_key_check(db: Session, keyring: Keyring) -> None:
    """Record which key encrypts the data (first encryption only)."""
    from app.models import SecurityState
    if db.get(SecurityState, 1) is None:
        blob, kid = keyring.encrypt(KEY_CHECK_VALUE, KEY_CHECK_AAD)
        db.add(SecurityState(id=1, key_id=kid, key_check=blob))
        db.flush()


def verify_key_at_start(db: Session, keyring: Keyring) -> str:
    """Refuse to run with a missing or wrong key when encrypted data exists (FR-014)."""
    from app.models import SecurityState
    state = db.get(SecurityState, 1)
    if state is None:
        if _encrypted_data_exists(db):
            raise CryptoError("encrypted data exists but its key check is missing")
        return "no encrypted data"
    if keyring.current is None:
        raise CryptoError("BIZVIEW_SECRET_KEY is not set but stored credentials are encrypted; "
                          "restore the key from your backup")
    try:
        keyring.decrypt(state.key_check, state.key_id, KEY_CHECK_AAD)
    except CryptoError:
        raise CryptoError("BIZVIEW_SECRET_KEY does not match the key used to encrypt the stored "
                          "credentials") from None
    if state.key_id != keyring.current_id:
        log.warning("data is still encrypted with the previous key; run: "
                    "python -m app.cli rotate-secret-key")
        return "rotation pending"
    return "ok"


def rotate(db: Session, keyring: Keyring) -> dict:
    """Re-encrypt every stored secret with the current key, in the caller's transaction."""
    from app.models import (
        AppUser,
        DataSource,
        EmailSend,
        SecurityState,
        TelegramSettings,
    )
    if keyring.current is None:
        raise CryptoError("BIZVIEW_SECRET_KEY (the new key) is not set")
    current = keyring.current_id
    counts = {
        "data_source": 0,
        "app_user": 0,
        "telegram_settings": 0,
        "email_send": 0,
    }
    for src in db.scalars(select(DataSource).where(DataSource.secrets_ct.is_not(None))
                          .with_for_update()):
        if src.secrets_key_id != current:
            plain = keyring.decrypt(src.secrets_ct, src.secrets_key_id, source_aad(src.id))
            src.secrets_ct, src.secrets_key_id = keyring.encrypt(plain, source_aad(src.id))
            counts["data_source"] += 1
    for user in db.scalars(select(AppUser).where(AppUser.totp_secret_ct.is_not(None))
                           .with_for_update()):
        if user.totp_key_id != current:
            plain = keyring.decrypt(user.totp_secret_ct, user.totp_key_id, totp_aad(user.id))
            user.totp_secret_ct, user.totp_key_id = keyring.encrypt(plain, totp_aad(user.id))
            counts["app_user"] += 1
    for bot in db.scalars(select(TelegramSettings).where(TelegramSettings.token_ct.is_not(None))
                          .with_for_update()):
        if bot.token_key_id != current:
            plain = keyring.decrypt(bot.token_ct, bot.token_key_id, TELEGRAM_AAD)
            bot.token_ct, bot.token_key_id = keyring.encrypt(plain, TELEGRAM_AAD)
            counts["telegram_settings"] += 1
    for send in db.scalars(
        select(EmailSend).where(EmailSend.selection["link"].has_key("ct")).with_for_update()
    ):
        link = send.selection["link"]
        if link.get("kid") != current:
            try:
                blob = base64.b64decode(link["ct"])
                plain = keyring.decrypt(blob, link["kid"], EMAIL_LINK_AAD)
                blob, kid = keyring.encrypt(plain, EMAIL_LINK_AAD)
            except (binascii.Error, ValueError, TypeError, KeyError):
                log.warning("email send %s: link ciphertext unreadable, skipped", send.id)
                continue
            send.selection = {
                **send.selection,
                "link": {**link, "ct": base64.b64encode(blob).decode(), "kid": kid},
            }
            counts["email_send"] += 1
    state = db.get(SecurityState, 1, with_for_update=True)
    blob, kid = keyring.encrypt(KEY_CHECK_VALUE, KEY_CHECK_AAD)
    if state is None:
        db.add(SecurityState(id=1, key_id=kid, key_check=blob, key_rotated_at=datetime.now(UTC)))
    else:
        state.key_id, state.key_check, state.key_rotated_at = kid, blob, datetime.now(UTC)
    db.flush()
    return counts
