"""Two-step sign-in with time-based one-time codes (feature 004, FR-018, research R5)."""
import hmac
import secrets
import time
from datetime import UTC, datetime

import pyotp
import segno
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import passwords
from app.models import AppUser, RecoveryCode
from app.security.crypto import Keyring, totp_aad

PERIOD = 30
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_secret() -> str:
    return pyotp.random_base32(32)  # 160 bits


def store_pending_secret(user: AppUser, secret: str, keyring: Keyring) -> None:
    """Store a new secret for enrollment; not active until confirmed (totp_enabled_at stays)."""
    user.totp_secret_ct, user.totp_key_id = keyring.encrypt(secret.encode(), totp_aad(user.id))
    user.totp_last_step = None


def secret_of(user: AppUser, keyring: Keyring) -> str | None:
    if user.totp_secret_ct is None:
        return None
    return keyring.decrypt(user.totp_secret_ct, user.totp_key_id, totp_aad(user.id)).decode()


def provisioning_uri(secret: str, email: str, issuer: str) -> str:
    return pyotp.TOTP(secret, interval=PERIOD).provisioning_uri(name=email, issuer_name=issuer)


def qr_svg_data_uri(uri: str) -> str:
    # Own white background: QR scanners need dark-on-light, whatever the page theme (feature 006).
    return segno.make(uri, error="m").svg_data_uri(scale=5, border=2, dark="#0f172a",
                                                   light="#ffffff")


def verify_code(user: AppUser, code: str, keyring: Keyring, *, now: float | None = None) -> bool:
    """Accept the current, previous, or next 30-s code, never a step already used (replay)."""
    code = "".join(ch for ch in code if ch.isdigit())
    secret = secret_of(user, keyring)
    if secret is None or len(code) != 6:
        return False
    totp = pyotp.TOTP(secret, interval=PERIOD)
    current = int((now if now is not None else time.time()) // PERIOD)
    for step in (current - 1, current, current + 1):
        if user.totp_last_step is not None and step <= user.totp_last_step:
            continue
        if hmac.compare_digest(totp.at(step * PERIOD), code):
            user.totp_last_step = step
            return True
    return False


def enabled(user: AppUser) -> bool:
    return user.totp_enabled_at is not None


def enable(user: AppUser) -> None:
    user.totp_enabled_at = datetime.now(UTC)


def disable(db: Session, user: AppUser) -> None:
    user.totp_secret_ct = user.totp_key_id = user.totp_enabled_at = user.totp_last_step = None
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))


def _normalise(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def new_recovery_codes(db: Session, user: AppUser, count: int = 10) -> list[str]:
    """Replace the user's recovery codes; returns the plain codes (shown once)."""
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
        db.add(RecoveryCode(user_id=user.id, code_hash=passwords.hash_password(raw)))
    db.flush()
    return codes


def use_recovery_code(db: Session, user: AppUser, code: str) -> bool:
    raw = _normalise(code)
    if len(raw) != 10:
        return False
    for row in db.scalars(select(RecoveryCode).where(RecoveryCode.user_id == user.id,
                                                     RecoveryCode.used_at.is_(None))):
        if passwords.verify_password(row.code_hash, raw):
            row.used_at = datetime.now(UTC)
            return True
    return False


def recovery_codes_left(db: Session, user: AppUser) -> int:
    return len(db.scalars(select(RecoveryCode.id).where(RecoveryCode.user_id == user.id,
                                                        RecoveryCode.used_at.is_(None))).all())
