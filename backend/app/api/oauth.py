"""Google sign-in endpoints (feature 027): start the flow and answer the callback.

Both are plain redirects because the browser, not our JavaScript, is talking to Google. The
`state` and the PKCE verifier live in a short-lived HttpOnly cookie of the browser that started
the flow, so a callback another site started (or a replayed one) is refused. The callback is a
GET that writes, so it opens its own transaction and commits before answering: the client may
use the session cookie as soon as the redirect arrives.
"""
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import finish_sign_in, refuse_inactive_or_locked
from app.auth import google
from app.auth.deps import client_ip
from app.config import Settings, get_settings
from app.db import get_sessionmaker
from app.errors import ApiError, not_found
from app.i18n import current as current_locale
from app.models import AppUser, GoogleLink
from app.services import audit, users

router = APIRouter()

COOKIE = "bv_google"
COOKIE_PATH = "/api/auth/google"
COOKIE_MAX_AGE = 600                     # the whole round trip to Google, generously
SIGN_IN = "/ingresar"
SIGN_IN_MFA = "/ingresar?mfa=1"   # the code prompt: a second factor is still due


def _set_state_cookie(response: RedirectResponse, state: str, verifier: str) -> None:
    response.set_cookie(COOKIE, f"{state}.{verifier}", max_age=COOKIE_MAX_AGE, httponly=True,
                        secure=get_settings().cookie_secure, samesite="lax", path=COOKIE_PATH)


def _clear_state_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(COOKIE, httponly=True, secure=get_settings().cookie_secure,
                           samesite="lax", path=COOKIE_PATH)


def _refused(code: str, *, clear: bool = True) -> RedirectResponse:
    response = RedirectResponse(f"{SIGN_IN}?google_error={code}", status_code=302)
    if clear:
        _clear_state_cookie(response)
    return response


def _state_cookie(raw: str | None) -> tuple[str | None, str | None]:
    state, _, verifier = (raw or "").partition(".")
    return (state or None), (verifier or None)


@router.get("/api/auth/google/start")
def google_start(request: Request):
    settings = get_settings()
    # Refused exactly like a missing feature, never with a hint of what is misconfigured.
    if not settings.google_enabled_effective:
        raise not_found()
    state, verifier = google.new_state(), google.new_verifier()
    response = RedirectResponse(
        google.authorize_url(settings, state, verifier, current_locale()), status_code=302)
    _set_state_cookie(response, state, verifier)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/api/auth/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None,
                    error: str | None = None):
    settings = get_settings()
    ip = client_ip(request)
    db = get_sessionmaker()()
    response = RedirectResponse("/", status_code=302)
    try:
        try:
            user = _sign_in(db, settings, request, ip, code=code, state=state, error=error)
            result = finish_sign_in(db, user, request, response, ip, method="google")
            audit.record(db, "google_sign_in", actor_id=user.id, target_id=user.id, ip=ip)
            db.commit()
        except google.GoogleError as refusal:
            db.rollback()
            # The reason code only: never the token, the code, the secret or Google's text.
            audit.record(db, "google_sign_in_refused", ip=ip, detail={"reason": refusal.code})
            db.commit()
            return _refused(refusal.code)
        except Exception:
            db.rollback()
            raise
        # A second factor is still due: the pending session only reaches the code prompt.
        response.headers["location"] = SIGN_IN_MFA if result.get("mfa_required") else "/"
        _clear_state_cookie(response)
        return response
    finally:
        db.close()


def _sign_in(db: Session, settings: Settings, request: Request, ip: str | None, *,
             code: str | None, state: str | None, error: str | None) -> AppUser:
    """Prove the identity and resolve it to an existing account; never creates a user."""
    if not settings.google_enabled_effective:
        raise google.GoogleError("disabled")

    expected, verifier = _state_cookie(request.cookies.get(COOKIE))
    if not expected or not state or not secrets.compare_digest(expected, state):
        raise google.GoogleError("state")
    if error:
        raise google.GoogleError("denied" if error == "access_denied" else "provider")
    if not code or not verifier:
        raise google.GoogleError("provider")

    identity = google.exchange(settings, code, verifier)
    _check_domain(settings, identity.email)

    link = db.scalar(select(GoogleLink).where(GoogleLink.google_sub == identity.sub))
    if link is not None:
        user = db.get(AppUser, link.user_id)      # None: the account was deleted
        if user is None:
            raise google.GoogleError("unknown_identity")
        _refuse_inactive(db, user, ip)
        link.email = identity.email               # last known address, for display only
        link.last_login_at = users.now()
        return user

    user = users.by_email(db, identity.email)
    if user is None:
        raise google.GoogleError("unknown_identity")
    _refuse_inactive(db, user, ip)
    if db.scalar(select(GoogleLink).where(GoogleLink.user_id == user.id)) is not None:
        # Already linked to a different Google identity: never repoint it silently.
        raise google.GoogleError("unknown_identity")
    now = users.now()
    db.add(GoogleLink(user_id=user.id, google_sub=identity.sub, email=identity.email,
                      created_at=now, last_login_at=now))
    db.flush()
    audit.record(db, "google_linked", actor_id=user.id, target_id=user.id, ip=ip)
    return user


def _check_domain(settings: Settings, email: str) -> None:
    allowed = settings.google_domains
    if allowed and email.rsplit("@", 1)[-1].lower() not in allowed:
        raise google.GoogleError("domain")


def _refuse_inactive(db: Session, user: AppUser, ip: str | None) -> None:
    """Inactive and locked accounts are refused with the password path's own mechanism."""
    try:
        refuse_inactive_or_locked(db, user, ip, method="google")
    except ApiError:
        raise google.GoogleError("inactive") from None
