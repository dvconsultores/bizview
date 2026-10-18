"""Google sign-in (feature 027): authorization URL, PKCE and the token-endpoint exchange.

This is the server-side authorization-code flow for a *confidential* client: the code is traded
against Google's token endpoint over TLS, authenticated with the client secret, so the ID token
comes from Google itself and never passes through the browser. The spec's Assumptions record the
decision that follows from it — no JWT library is added and the signature is not verified
separately — while the claims that decide *who* the user is (`iss`, `aud`, `exp`,
`email_verified`) are validated here and nothing the browser supplies is believed except the
code. Tokens, the authorization code and the client secret are never logged.
"""
import base64
import binascii
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import Settings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "openid email profile"
ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class GoogleError(Exception):
    """A refusal carrying one of the short codes the sign-in screen understands."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def client() -> httpx.Client:
    """HTTP client for the exchange; tests replace it with a MockTransport (no network)."""
    return httpx.Client(timeout=TIMEOUT, follow_redirects=False)


def new_state() -> str:
    return secrets.token_urlsafe(32)


def new_verifier() -> str:
    # PKCE takes 43 to 128 characters from the unreserved set (43 bytes of urlsafe is 58).
    return secrets.token_urlsafe(48)


def challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorize_url(settings: Settings, state: str, verifier: str,
                  locale: str | None = None) -> str:
    params = {
        "client_id": settings.google_client_id or "",
        "redirect_uri": settings.google_redirect_uri_effective,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "code_challenge": challenge(verifier),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    if locale in ("es", "en"):
        params["hl"] = locale
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


@dataclass(frozen=True)
class Identity:
    """The claims a successful exchange leaves us with."""

    sub: str
    email: str
    hd: str | None


def exchange(settings: Settings, code: str, verifier: str) -> Identity:
    """Trade the authorization code for an ID token, then check the identity claims."""
    form = {
        "client_id": settings.google_client_id or "",
        "client_secret": settings.google_client_secret or "",
        "redirect_uri": settings.google_redirect_uri_effective,
        "code": code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
    }
    try:
        with client() as http:
            response = http.post(TOKEN_URL, data=form)
    except httpx.HTTPError:
        raise GoogleError("provider") from None
    if response.status_code != 200:
        raise GoogleError("provider")
    try:
        payload = response.json()
    except ValueError:
        raise GoogleError("provider") from None
    id_token = payload.get("id_token") if isinstance(payload, dict) else None
    if not isinstance(id_token, str) or not id_token:
        raise GoogleError("provider")
    claims = decode_claims(id_token)
    verify_claims(claims, settings)
    return Identity(sub=claims["sub"], email=claims["email"].strip().lower(),
                    hd=claims.get("hd"))


def decode_claims(id_token: str) -> dict:
    """Read the claim set of the ID token (the signature is trusted by transport, see above)."""
    try:
        segment = id_token.split(".")[1]
        padded = segment + "=" * (-len(segment) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
    except (IndexError, ValueError, binascii.Error, TypeError):
        raise GoogleError("provider") from None
    if not isinstance(claims, dict):
        raise GoogleError("provider")
    return claims


def verify_claims(claims: dict, settings: Settings) -> None:
    """Refuse anything that does not speak for this client and a verified, live identity."""
    if claims.get("iss") not in ISSUERS:
        raise GoogleError("provider")
    if claims.get("aud") != settings.google_client_id:
        raise GoogleError("provider")
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)) or isinstance(exp, bool) or exp <= time.time():
        raise GoogleError("provider")
    if claims.get("email_verified") is not True:
        raise GoogleError("provider")
    sub, email = claims.get("sub"), claims.get("email")
    if not isinstance(sub, str) or not sub or not isinstance(email, str) or "@" not in email:
        raise GoogleError("provider")
