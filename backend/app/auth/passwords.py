"""Argon2id password hashing and the password rules of FR-015."""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LEN, MAX_LEN = 10, 128
_hasher = PasswordHasher()  # Argon2id, RFC 9106 low-memory profile

# Verified against when the email is unknown, so timing does not reveal whether it exists.
DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def normalise_email(email: str) -> str:
    return email.strip().lower()


def password_problem(password: str, email: str, current: str | None = None) -> str | None:
    """Return the first broken rule as an error code, or None when the password is acceptable."""
    if len(password) < MIN_LEN:
        return "too_short"
    if len(password) > MAX_LEN:
        return "too_long"
    email = normalise_email(email)
    local = email.split("@", 1)[0]
    lowered = password.lower()
    if lowered == email or (len(local) >= 3 and local in lowered):
        return "contains_email"
    if current is not None and password == current:
        return "same_as_current"
    return None
